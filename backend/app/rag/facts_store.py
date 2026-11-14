"""Approved facts: add, edit, import CSV, embed, look up (tasks 5.1 and 5.2).

* Facts typed in by an admin are approved immediately; imported facts are `pending` until an
  admin approves them (decision 3). Codes are F-NNN in insertion order, and edits keep them.
* The `statement` is what gets embedded (RETRIEVAL_DOCUMENT), decision 9.
* Expiry is computed here from `valid_until`, never by a model (decision 10).
* Lookup: exact `entity` match first, then hybrid search, top 3 per claim (decision 14).
"""

import csv
import io
from datetime import date, timedelta
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from pydantic import ValidationError

from app.audit import audit
from app.models.facts import Expiry, Fact, FactCreate, FactUpdate, ImportProblem
from app.rag.embeddings import Embedder
from app.rag.retrieval import search_facts
from app.rag.rules_store import to_vector

EXPIRING_DAYS = 30
FACT_COLUMNS = (
    "fact_code, entity, attribute, value, unit, statement, source, valid_until, status, updated_at"
)
CSV_REQUIRED = ("entity", "attribute", "value", "statement")
CSV_COLUMNS = (*CSV_REQUIRED, "unit", "source", "valid_until")


class FactNotFoundError(LookupError):
    pass


def expiry_status(valid_until: date | None, today: date) -> Expiry:
    """`expired` if valid_until < today; `expiring` within 30 days; else `valid`/`no_expiry`."""
    if valid_until is None:
        return "no_expiry"
    if valid_until < today:
        return "expired"
    if valid_until <= today + timedelta(days=EXPIRING_DAYS):
        return "expiring"
    return "valid"


def _fact(row: dict, today: date) -> Fact:
    return Fact.model_validate(row | {"expiry": expiry_status(row["valid_until"], today)})


def parse_facts_csv(text: str) -> tuple[list[FactCreate], list[ImportProblem]]:
    """Parse a facts CSV (header row required). Returns valid rows and per-row errors."""
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    header = [h.strip().lower() for h in (reader.fieldnames or [])]
    missing = [c for c in CSV_REQUIRED if c not in header]
    if missing:
        return [], [ImportProblem(row=1, message=f"missing columns: {', '.join(missing)}")]
    facts: list[FactCreate] = []
    errors: list[ImportProblem] = []
    for number, raw in enumerate(reader, start=2):
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items()}
        if not any(row.values()):
            continue
        data = {c: row.get(c) or None for c in CSV_COLUMNS}
        try:
            facts.append(FactCreate.model_validate(data))
        except ValidationError as exc:
            problems = "; ".join(f"{e['loc'][0]}: {e['msg']}" for e in exc.errors())
            errors.append(ImportProblem(row=number, message=problems))
    return facts, errors


def next_fact_number(conn: psycopg.Connection, brand_id: UUID) -> int:
    row = conn.execute(
        "select coalesce(max(substring(fact_code from 3)::int), 0) from public.facts "
        "where brand_id = %s",
        (brand_id,),
    ).fetchone()
    return row[0] + 1


def create_facts(
    conn: psycopg.Connection,
    brand_id: UUID,
    items: list[FactCreate],
    embedder: Embedder,
    *,
    status: str,
    actor_id: UUID | None,
    today: date,
) -> list[Fact]:
    if not items:
        return []
    vectors = embedder.embed_documents(
        [f.statement for f in items], purpose="fact_embedding", brand_id=brand_id
    )
    number = next_fact_number(conn, brand_id)
    created: list[Fact] = []
    with conn.cursor(row_factory=dict_row) as cur:
        for i, (item, vector) in enumerate(zip(items, vectors, strict=True)):
            row = cur.execute(
                "insert into public.facts (brand_id, fact_code, entity, attribute, value, unit, "
                "statement, source, valid_until, status, embedding, approved_by, approved_at) "
                "values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::extensions.vector, "
                "case when %s = 'approved' then %s::uuid end, "
                "case when %s = 'approved' then now() end) "
                f"returning {FACT_COLUMNS}",
                (
                    brand_id, f"F-{number + i:03d}", item.entity, item.attribute, item.value,
                    item.unit, item.statement, item.source, item.valid_until, status,
                    to_vector(vector), status, actor_id, status,
                ),
            ).fetchone()  # fmt: skip
            created.append(_fact(row, today))
    audit(conn, brand_id=brand_id, actor_id=actor_id, action=f"facts.create.{status}",
          entity_type="fact", entity_id=",".join(f.fact_code for f in created))  # fmt: skip
    return created


def list_facts(
    conn: psycopg.Connection,
    brand_id: UUID,
    today: date,
    *,
    status: str | None = None,
    query: str | None = None,
) -> list[Fact]:
    sql = f"select {FACT_COLUMNS} from public.facts where brand_id = %s"
    params: list[object] = [brand_id]
    if status:
        sql += " and status = %s"
        params.append(status)
    if query:
        sql += (
            " and (entity ilike %s or attribute ilike %s or statement ilike %s"
            " or fact_code ilike %s)"
        )
        params += [f"%{query}%"] * 4
    with conn.cursor(row_factory=dict_row) as cur:
        rows = cur.execute(sql + " order by fact_code", params).fetchall()
    return [_fact(r, today) for r in rows]


def get_facts(
    conn: psycopg.Connection, brand_id: UUID, codes: list[str], today: date
) -> list[Fact]:
    with conn.cursor(row_factory=dict_row) as cur:
        rows = cur.execute(
            f"select {FACT_COLUMNS} from public.facts where brand_id = %s and fact_code = any(%s)",
            (brand_id, codes),
        ).fetchall()
    by_code = {r["fact_code"]: _fact(r, today) for r in rows}
    return [by_code[c] for c in codes if c in by_code]


def update_fact(
    conn: psycopg.Connection,
    brand_id: UUID,
    code: str,
    change: FactUpdate,
    embedder: Embedder,
    *,
    actor_id: UUID | None,
    today: date,
) -> Fact:
    """Edit a fact in place (its code never changes, so old citations stay valid)."""
    found = get_facts(conn, brand_id, [code], today)
    if not found:
        raise FactNotFoundError(code)
    before = found[0]
    fields = change.model_dump(exclude_unset=True)
    if not fields:
        return before
    sets = [f"{name} = %s" for name in fields]
    params: list[object] = list(fields.values())
    if "status" in fields:
        sets.append("approved_by = case when %s = 'approved' then %s::uuid end")
        sets.append("approved_at = case when %s = 'approved' then now() end")
        params += [fields["status"], actor_id, fields["status"]]
    if "statement" in fields and fields["statement"] != before.statement:
        (vector,) = embedder.embed_documents(
            [fields["statement"]], purpose="fact_embedding", brand_id=brand_id
        )
        sets.append("embedding = %s::extensions.vector")
        params.append(to_vector(vector))
    with conn.cursor(row_factory=dict_row) as cur:
        row = cur.execute(
            f"update public.facts set {', '.join(sets)} where brand_id = %s and fact_code = %s "
            f"returning {FACT_COLUMNS}",
            [*params, brand_id, code],
        ).fetchone()
    after = _fact(row, today)
    audit(conn, brand_id=brand_id, actor_id=actor_id, action="fact.edit", entity_type="fact",
          entity_id=code, before=before.model_dump(mode="json"),
          after=after.model_dump(mode="json"))  # fmt: skip
    return after


def set_fact_status(
    conn: psycopg.Connection,
    brand_id: UUID,
    codes: list[str],
    status: str,
    *,
    actor_id: UUID | None,
    today: date,
) -> list[Fact]:
    found = {f.fact_code for f in get_facts(conn, brand_id, codes, today)}
    unknown = [c for c in codes if c not in found]
    if unknown:
        raise FactNotFoundError(", ".join(unknown))
    with conn.cursor(row_factory=dict_row) as cur:
        rows = cur.execute(
            "update public.facts set status = %s, "
            "approved_by = case when %s = 'approved' then %s::uuid end, "
            "approved_at = case when %s = 'approved' then now() end "
            f"where brand_id = %s and fact_code = any(%s) returning {FACT_COLUMNS}",
            (status, status, actor_id, status, brand_id, codes),
        ).fetchall()
    audit(conn, brand_id=brand_id, actor_id=actor_id, action=f"facts.{status}",
          entity_type="fact", entity_id=",".join(sorted(codes)))  # fmt: skip
    return sorted((_fact(r, today) for r in rows), key=lambda f: f.fact_code)


def lookup_facts(
    conn: psycopg.Connection,
    brand_id: UUID,
    *,
    entity: str,
    claim: str,
    vector: list[float],
    today: date,
    limit: int = 3,
) -> list[Fact]:
    """Approved facts for one claim: exact entity matches first, then hybrid search."""
    exact = [
        r[0]
        for r in conn.execute(
            "select fact_code from public.facts where brand_id = %s and status = 'approved' "
            "and lower(entity) = lower(%s) order by fact_code",
            (brand_id, entity.strip()),
        ).fetchall()
    ]
    codes = list(dict.fromkeys([*exact, *search_facts(conn, brand_id, claim, vector, limit)]))
    # Exact matches can exceed the limit (an entity with many facts); keep the most relevant
    # ones by putting hybrid hits that are also exact matches first.
    if len(exact) > limit:
        hybrid = search_facts(conn, brand_id, claim, vector, limit=20)
        ranked_exact = [c for c in hybrid if c in exact] + [c for c in exact if c not in hybrid]
        codes = ranked_exact[:limit]
    return get_facts(conn, brand_id, codes[:limit], today)
