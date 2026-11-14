"""Guideline verification (task 4.4, decision 21).

1. Rule pairs with cosine >= 0.75 go to the LLM in batches of 20, labelled duplicate,
   contradiction or compatible.
2. Semantic rules go to the LLM in batches to find vague, untestable ones, with a rewrite.
3. Code lists the required categories that have no rule.
Rejected rules are ignored. Each report is stored in `guideline_reports`.
"""

import json
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from app.llm import prompts
from app.llm.client import LLMClient
from app.llm.prompts import RuleRef
from app.models.llm import PairChecks, VaguenessCheck
from app.models.rules import PairIssue, Rule, VagueIssue, VerificationReport
from app.rag.rules_store import list_rules

REQUIRED_CATEGORIES = ("tone", "terminology", "claims", "visuals", "accessibility", "legal")
SIMILARITY_THRESHOLD = 0.75
PAIRS_PER_CALL = 20
RULES_PER_VAGUENESS_CALL = 15

Pair = tuple[str, str, float]  # (rule_code_a, rule_code_b, cosine similarity)


def _batches(items: list, size: int) -> list[list]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def _ref(rule: Rule) -> RuleRef:
    return RuleRef(rule.rule_code, rule.category, rule.text, rule.examples_bad, rule.examples_good)


def candidate_pairs(
    conn: psycopg.Connection, brand_id: UUID, threshold: float = SIMILARITY_THRESHOLD
) -> list[Pair]:
    """Pairs of non-rejected rules at or above the cosine threshold, most similar first."""
    rows = conn.execute(
        "select a.rule_code, b.rule_code, "
        "1 - (a.embedding operator(extensions.<=>) b.embedding) as similarity "
        "from public.rules a join public.rules b "
        "on b.brand_id = a.brand_id and a.rule_code < b.rule_code "
        "where a.brand_id = %s and a.status <> 'rejected' and b.status <> 'rejected' "
        "and a.embedding is not null and b.embedding is not null "
        "and 1 - (a.embedding operator(extensions.<=>) b.embedding) >= %s "
        "order by similarity desc",
        (brand_id, threshold),
    ).fetchall()
    return [(a, b, float(sim)) for a, b, sim in rows]


def missing_categories(rules: list[Rule]) -> list[str]:
    present = {r.category for r in rules if r.status != "rejected"}
    return [c for c in REQUIRED_CATEGORIES if c not in present]


def verify_rules(
    rules: list[Rule],
    pairs: list[Pair],
    client: LLMClient,
    *,
    brand_id: UUID | None = None,
    max_workers: int = 2,
) -> VerificationReport:
    """Run the three checks on already-loaded rules and candidate pairs."""
    active = [r for r in rules if r.status != "rejected"]
    by_code = {r.rule_code: r for r in active}
    pairs = [p for p in pairs if p[0] in by_code and p[1] in by_code]

    def check_pairs(batch: list[tuple[str, Pair]]) -> PairChecks:
        p = prompts.pair_check(
            [(pid, _ref(by_code[a]), _ref(by_code[b])) for pid, (a, b, _) in batch]
        )
        return client.json(p.schema, p.system, p.prompt, purpose=p.purpose, brand_id=brand_id)

    def check_vagueness(batch: list[Rule]) -> VaguenessCheck:
        p = prompts.vagueness_check([_ref(r) for r in batch])
        return client.json(p.schema, p.system, p.prompt, purpose=p.purpose, brand_id=brand_id)

    numbered = [(f"p{i + 1}", pair) for i, pair in enumerate(pairs)]
    semantic = [r for r in active if r.check_type == "semantic"]
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        pair_results = list(pool.map(check_pairs, _batches(numbered, PAIRS_PER_CALL)))
        vague_results = list(
            pool.map(check_vagueness, _batches(semantic, RULES_PER_VAGUENESS_CALL))
        )

    report = VerificationReport(
        missing_categories=missing_categories(active),
        pairs_checked=len(pairs),
        rules_checked=len(active),
    )
    pair_by_id = dict(numbered)
    for result in pair_results:
        for verdict in result.results:
            if verdict.pair_id not in pair_by_id or verdict.label == "compatible":
                continue  # unknown ids are ignored; only problems are reported
            a, b, similarity = pair_by_id.pop(verdict.pair_id)
            issue = PairIssue(rule_a=a, rule_b=b, similarity=round(similarity, 3),
                              explanation=verdict.explanation)  # fmt: skip
            (report.duplicates if verdict.label == "duplicate" else report.contradictions).append(
                issue
            )
    semantic_codes = {r.rule_code for r in semantic}
    seen: set[str] = set()
    for result in vague_results:
        for item in result.results:
            if item.vague and item.rule_code in semantic_codes and item.rule_code not in seen:
                seen.add(item.rule_code)
                report.vague.append(
                    VagueIssue(
                        rule_code=item.rule_code,
                        reason=item.reason,
                        suggested_rewrite=item.suggested_rewrite,
                    )  # fmt: skip
                )
    report.vague.sort(key=lambda v: v.rule_code)
    return report


def verify_guidelines(
    conn: psycopg.Connection,
    brand_id: UUID,
    client: LLMClient,
    *,
    source_doc: str | None = None,
    actor_id: UUID | None = None,
) -> VerificationReport:
    """Verify every non-rejected rule of the brand and store the report."""
    report = verify_rules(
        list_rules(conn, brand_id), candidate_pairs(conn, brand_id), client, brand_id=brand_id
    )
    conn.execute(
        "insert into public.guideline_reports (brand_id, source_doc, report, created_by) "
        "values (%s, %s, %s, %s)",
        (brand_id, source_doc, json.dumps(report.model_dump(mode="json")), actor_id),
    )
    return report


def latest_report(conn: psycopg.Connection, brand_id: UUID) -> VerificationReport | None:
    with conn.cursor(row_factory=dict_row) as cur:
        row = cur.execute(
            "select report from public.guideline_reports where brand_id = %s "
            "order by created_at desc limit 1",
            (brand_id,),
        ).fetchone()
    return VerificationReport.model_validate(row["report"]) if row else None
