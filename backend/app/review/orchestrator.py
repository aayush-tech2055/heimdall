"""The review pipeline (task 6.7).

    units -> redact -> (a) rules in code [original text]
                     -> (b) retrieval + judge  } in parallel, on redacted text
                     -> (c) claims vs facts    }
          -> citation validation -> sort by position, then severity
          -> save units, flags and dropped flags -> status creator_review

`review_text` is the pure pipeline (also used by the evaluation); `review_content` loads the
brand context, runs it for one content version and saves the results. It runs as a FastAPI
background task, borrowing short-lived pooled connections instead of holding one open
during model calls.
"""

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date
from uuid import UUID

import psycopg
from psycopg_pool import ConnectionPool

from app.llm.client import LLMClient
from app.models.flag import Flag
from app.models.llm import ExtractedClaim
from app.models.rules import Rule
from app.processing.redaction import Redacted, redact
from app.rag.embeddings import Embedder
from app.rag.facts_store import lookup_facts
from app.rag.retrieval import search_rules
from app.rag.rules_store import list_rules
from app.review.claims import run_claims
from app.review.judge import run_judge
from app.review.rules_engine import check_deterministic
from app.review.segment import Unit, segment_text
from app.review.text import normalise
from app.review.validation import ApprovedException, validate
from app.review.workflow import transition

log = logging.getLogger(__name__)


@dataclass
class BrandContext:
    brand_id: UUID
    rules: list[Rule]
    confidential_terms: list[str] = field(default_factory=list)
    claim_policy_enabled: bool = True
    exceptions: list[ApprovedException] = field(default_factory=list)
    exempt_terms: list[str] = field(default_factory=list)  # brand and product names


@dataclass
class ReviewOutcome:
    units: list[Unit]
    redacted: dict[str, Redacted]
    flags: list[Flag]
    dropped: list[tuple[dict, str]]
    retrieved: dict[str, list[str]]
    claims: list[ExtractedClaim]
    seconds: float


def load_brand_context(conn: psycopg.Connection, brand_id: UUID) -> BrandContext:
    settings = conn.execute(
        "select confidential_terms, claim_policy_enabled from public.brand_settings "
        "where brand_id = %s",
        (brand_id,),
    ).fetchone()
    exceptions = conn.execute(
        "select source_id, evidence from public.approved_exceptions where brand_id = %s",
        (brand_id,),
    ).fetchall()
    names = conn.execute(
        "select name from public.brands where id = %s union "
        "select distinct entity from public.facts where brand_id = %s and status = 'approved'",
        (brand_id, brand_id),
    ).fetchall()
    return BrandContext(
        brand_id=brand_id,
        rules=list_rules(conn, brand_id, "approved"),
        confidential_terms=list(settings[0]) if settings else [],
        claim_policy_enabled=settings[1] if settings else True,
        exceptions=[ApprovedException(s, e) for s, e in exceptions],
        exempt_terms=[n[0] for n in names],
    )


def review_text(
    text: str,
    ctx: BrandContext,
    *,
    pool: ConnectionPool,
    client: LLMClient,
    embedder: Embedder,
    today: date,
    content_version_id: UUID | None = None,
    use_presidio: bool = True,
) -> ReviewOutcome:
    started = time.perf_counter()
    units = segment_text(text)
    redacted = {
        u.unit_id: redact(u.text, ctx.confidential_terms, use_presidio=use_presidio,
                          exempt_terms=ctx.exempt_terms)
        for u in units
    }  # fmt: skip

    def search(query: str, vector: list[float], k: int) -> list[str]:
        with pool.connection() as conn:
            return search_rules(conn, ctx.brand_id, query, vector, k)

    def lookup(claim: ExtractedClaim, vector: list[float]):  # noqa: ANN202
        with pool.connection() as conn:
            return lookup_facts(conn, ctx.brand_id, entity=claim.entity, claim=claim.claim,
                                vector=vector, today=today)  # fmt: skip

    common = {"embedder": embedder, "client": client, "brand_id": ctx.brand_id,
              "content_version_id": content_version_id}  # fmt: skip
    with ThreadPoolExecutor(max_workers=2) as pool_exec:
        judged = pool_exec.submit(run_judge, units, redacted, ctx.rules, search=search, **common)
        claimed = pool_exec.submit(
            run_claims, units, redacted, lookup=lookup,
            claim_policy_enabled=ctx.claim_policy_enabled, **common,
        )  # fmt: skip
        coded = check_deterministic(units, ctx.rules)
        judge_result, claims_result = judged.result(), claimed.result()

    validated = validate(
        [*coded, *judge_result.candidates, *claims_result.candidates],
        units, redacted, ctx.exceptions,
    )  # fmt: skip
    return ReviewOutcome(
        units=units, redacted=redacted, flags=validated.flags,
        dropped=[*claims_result.dropped, *validated.dropped],
        retrieved=judge_result.retrieved, claims=claims_result.claims,
        seconds=time.perf_counter() - started,
    )  # fmt: skip


def _carry_over_dismissals(conn: psycopg.Connection, content_id: UUID, version_id: UUID) -> dict:
    """Dismissals on earlier versions, keyed by (source_id, normalised evidence) (task 7.2)."""
    rows = conn.execute(
        "select f.source_id, f.evidence, f.resolution_note, f.resolved_by from public.flags f "
        "join public.content_versions v on v.id = f.version_id "
        "where v.content_id = %s and v.id <> %s and f.status = 'dismissed' "
        "order by v.version_number",
        (content_id, version_id),
    ).fetchall()
    return {(s, normalise(e)): (note, by) for s, e, note, by in rows}


def save_outcome(
    conn: psycopg.Connection,
    *,
    version_id: UUID,
    content_id: UUID,
    brand_id: UUID,
    outcome: ReviewOutcome,
) -> None:
    conn.execute("delete from public.flags where version_id = %s", (version_id,))
    conn.execute("delete from public.dropped_flags where version_id = %s", (version_id,))
    conn.execute("delete from public.review_units where version_id = %s", (version_id,))
    with conn.cursor() as cur:
        cur.executemany(
            "insert into public.review_units (version_id, brand_id, unit_id, position, text, "
            "location, retrieved_rules) values (%s, %s, %s, %s, %s, %s, %s)",
            [(version_id, brand_id, u.unit_id, u.position, u.text, json.dumps(u.location),
              outcome.retrieved.get(u.unit_id, [])) for u in outcome.units],
        )  # fmt: skip
        dismissed = _carry_over_dismissals(conn, content_id, version_id)
        for flag in outcome.flags:
            carried = dismissed.get((flag.source_id, normalise(flag.evidence)))
            cur.execute(
                "insert into public.flags (version_id, brand_id, unit_id, source_type, source_id, "
                "category, severity, evidence, explanation, suggested_fix, confidence, location, "
                "layer, status, resolution_note, resolved_by, resolved_at) values (%s, %s, %s, "
                "%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
                "case when %s then now() end)",
                (version_id, brand_id, flag.unit_id, flag.source_type, flag.source_id,
                 flag.category, flag.severity, flag.evidence, flag.explanation,
                 flag.suggested_fix, flag.confidence, flag.location.model_dump_json(), flag.layer,
                 "dismissed" if carried else "open", carried[0] if carried else None,
                 carried[1] if carried else None, bool(carried)),
            )  # fmt: skip
        cur.executemany(
            "insert into public.dropped_flags (version_id, brand_id, payload, reason) "
            "values (%s, %s, %s, %s)",
            [(version_id, brand_id, json.dumps(payload, default=str), reason)
             for payload, reason in outcome.dropped],
        )  # fmt: skip


def review_content(
    version_id: UUID,
    *,
    pool: ConnectionPool,
    client: LLMClient,
    embedder: Embedder,
    today: date,
    actor_id: UUID | None = None,
    use_presidio: bool = True,
) -> ReviewOutcome | None:
    """Review one content version end to end. Never raises: failures are recorded."""
    with pool.connection() as conn:
        row = conn.execute(
            "select v.content_id, v.brand_id, coalesce(v.extracted_text, '') from "
            "public.content_versions v where v.id = %s",
            (version_id,),
        ).fetchone()
        if row is None:
            log.error("review_content: no version %s", version_id)
            return None
        content_id, brand_id, text = row
        conn.execute(
            "update public.content_versions set review_started_at = now(), "
            "review_finished_at = null, review_error = null where id = %s",
            (version_id,),
        )
        (status,) = conn.execute(
            "select status from public.contents where id = %s", (content_id,)
        ).fetchone()
        if status != "checking":  # the API moves content to checking before scheduling us
            transition(conn, content_id, "checking", actor_id=actor_id)
        ctx = load_brand_context(conn, brand_id)
    try:
        outcome = review_text(
            text, ctx, pool=pool, client=client, embedder=embedder, today=today,
            content_version_id=version_id, use_presidio=use_presidio,
        )  # fmt: skip
        with pool.connection() as conn:
            save_outcome(conn, version_id=version_id, content_id=content_id,
                         brand_id=brand_id, outcome=outcome)  # fmt: skip
            conn.execute(
                "update public.content_versions set review_finished_at = now() where id = %s",
                (version_id,),
            )
            transition(conn, content_id, "creator_review", actor_id=actor_id, detail={
                "version_id": str(version_id), "flags": len(outcome.flags),
                "seconds": round(outcome.seconds, 1),
            })  # fmt: skip
        return outcome
    except Exception as exc:  # noqa: BLE001 - recorded for the creator, never lost
        log.exception("review of version %s failed", version_id)
        with pool.connection() as conn:
            conn.execute(
                "update public.content_versions set review_error = %s, "
                "review_finished_at = now() where id = %s",
                (str(exc)[:1000], version_id),
            )
            transition(conn, content_id, "draft", actor_id=actor_id,
                       detail={"error": str(exc)[:300]})  # fmt: skip
        return None
