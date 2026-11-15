"""Store, list, edit and approve rules (tasks 4.3 and 4.5).

Rules are embedded as `RETRIEVAL_DOCUMENT` when stored or when their text changes, and are
stored as `pending` until an admin approves them (decision 3).
"""

from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from app.audit import audit
from app.models.llm import ExtractedRule
from app.models.rules import Rule, RuleUpdate
from app.rag.embeddings import Embedder
from app.rag.extraction import RuleDraft, normalise_rule

RULE_COLUMNS = (
    "rule_code, category, text, source_doc, source_page, check_type, det_kind, terms, "
    "examples_bad, examples_good, always_on, status, updated_at"
)


class RuleNotFoundError(LookupError):
    pass


def to_vector(values: list[float]) -> str:
    """pgvector text format."""
    return "[" + ",".join(f"{v:.7f}" for v in values) + "]"


def embedding_text(text: str, examples_bad: list[str]) -> str:
    """What is embedded for a rule: its text, plus bad examples to help retrieval."""
    if examples_bad:
        return f"{text} Examples of breaking it: " + "; ".join(examples_bad)
    return text


def next_rule_number(conn: psycopg.Connection, brand_id: UUID) -> int:
    row = conn.execute(
        "select coalesce(max(substring(rule_code from 3)::int), 0) from public.rules "
        "where brand_id = %s",
        (brand_id,),
    ).fetchone()
    return row[0] + 1


def store_rules(
    conn: psycopg.Connection, brand_id: UUID, drafts: list[RuleDraft], embedder: Embedder
) -> list[Rule]:
    """Embed and insert extracted rules as `pending`."""
    if not drafts:
        return []
    vectors = embedder.embed_documents(
        [embedding_text(d.text, d.examples_bad) for d in drafts],
        purpose="rule_embedding",
        brand_id=brand_id,
    )
    stored: list[Rule] = []
    with conn.cursor(row_factory=dict_row) as cur:
        for draft, vector in zip(drafts, vectors, strict=True):
            cur.execute(
                "insert into public.rules (brand_id, rule_code, category, text, source_doc, "
                "source_page, check_type, det_kind, terms, examples_bad, examples_good, "
                "always_on, status, embedding) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
                f"%s, %s, 'pending', %s::extensions.vector) returning {RULE_COLUMNS}",
                (
                    brand_id, draft.rule_code, draft.category, draft.text, draft.source_doc,
                    draft.source_page, draft.check_type, draft.det_kind, draft.terms,
                    draft.examples_bad, draft.examples_good, draft.always_on, to_vector(vector),
                ),
            )  # fmt: skip
            stored.append(Rule.model_validate(cur.fetchone()))
    return stored


def list_rules(conn: psycopg.Connection, brand_id: UUID, status: str | None = None) -> list[Rule]:
    sql = f"select {RULE_COLUMNS} from public.rules where brand_id = %s"
    params: list[object] = [brand_id]
    if status:
        sql += " and status = %s"
        params.append(status)
    with conn.cursor(row_factory=dict_row) as cur:
        rows = cur.execute(sql + " order by rule_code", params).fetchall()
    return [Rule.model_validate(r) for r in rows]


def get_rule(conn: psycopg.Connection, brand_id: UUID, code: str) -> Rule:
    with conn.cursor(row_factory=dict_row) as cur:
        row = cur.execute(
            f"select {RULE_COLUMNS} from public.rules where brand_id = %s and rule_code = %s",
            (brand_id, code),
        ).fetchone()
    if row is None:
        raise RuleNotFoundError(code)
    return Rule.model_validate(row)


def update_rule(
    conn: psycopg.Connection,
    brand_id: UUID,
    code: str,
    change: RuleUpdate,
    embedder: Embedder,
    actor_id: UUID | None,
) -> Rule:
    """Apply an admin edit; re-embed if the text changed; keep decision 7 true."""
    before = get_rule(conn, brand_id, code)
    merged = before.model_dump() | change.model_dump(exclude_unset=True)
    fields = normalise_rule(ExtractedRule.model_validate(merged))
    params: list[object] = [
        fields["category"], fields["text"], fields["check_type"], fields["det_kind"],
        fields["terms"], fields["always_on"],
    ]  # fmt: skip
    vector_sql = ""
    if fields["text"] != before.text:
        (vector,) = embedder.embed_documents(
            [embedding_text(fields["text"], before.examples_bad)],
            purpose="rule_embedding",
            brand_id=brand_id,
        )
        vector_sql = ", embedding = %s::extensions.vector"
        params.append(to_vector(vector))
    params += [brand_id, code]
    with conn.cursor(row_factory=dict_row) as cur:
        row = cur.execute(
            "update public.rules set category = %s, text = %s, check_type = %s, det_kind = %s, "
            f"terms = %s, always_on = %s{vector_sql} where brand_id = %s and rule_code = %s "
            f"returning {RULE_COLUMNS}",
            params,
        ).fetchone()
    after = Rule.model_validate(row)
    audit(conn, brand_id=brand_id, actor_id=actor_id, action="rule.edit", entity_type="rule",
          entity_id=code, before=before.model_dump(mode="json"),
          after=after.model_dump(mode="json"))  # fmt: skip
    return after


def set_rule_status(
    conn: psycopg.Connection,
    brand_id: UUID,
    codes: list[str],
    status: str,
    actor_id: UUID | None,
) -> list[Rule]:
    """Bulk approve or reject; unknown codes raise before anything changes."""
    existing = {r.rule_code: r for r in list_rules(conn, brand_id)}
    unknown = [c for c in codes if c not in existing]
    if unknown:
        raise RuleNotFoundError(", ".join(unknown))
    with conn.cursor(row_factory=dict_row) as cur:
        rows = cur.execute(
            "update public.rules set status = %s, "
            "approved_by = case when %s = 'approved' then %s::uuid else null end, "
            "approved_at = case when %s = 'approved' then now() else null end "
            f"where brand_id = %s and rule_code = any(%s) returning {RULE_COLUMNS}",
            (status, status, actor_id, status, brand_id, codes),
        ).fetchall()
    for code in codes:
        audit(conn, brand_id=brand_id, actor_id=actor_id, action=f"rule.{status}",
              entity_type="rule", entity_id=code, before={"status": existing[code].status},
              after={"status": status})  # fmt: skip
    return sorted((Rule.model_validate(r) for r in rows), key=lambda r: r.rule_code)
