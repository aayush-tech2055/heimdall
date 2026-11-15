"""Hybrid search (decision 13): pgvector cosine top 20 + Postgres full-text top 20 (keywords
OR-ed), merged with reciprocal rank fusion (k = 60).

Used for rules (approved, semantic, per brand; top 6 per unit plus every always-on rule) and
for facts (approved, per brand; after an exact entity match, top 3 per claim).
"""

from collections.abc import Sequence
from uuid import UUID

import psycopg

from app.rag.rules_store import to_vector

RRF_K = 60
CANDIDATES = 20


def rrf(rankings: Sequence[Sequence[str]], k: int = RRF_K) -> list[str]:
    """Merge ranked id lists: score(id) = sum over lists of 1 / (k + rank), rank from 1.

    Ties keep the order in which ids were first seen, so results are deterministic.
    """
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
    first_seen = {item: i for i, item in enumerate(dict.fromkeys(x for r in rankings for x in r))}
    return sorted(scores, key=lambda item: (-scores[item], first_seen[item]))


# The OR-ed keyword query, built in SQL from the text's own lexemes (stop words removed).
_OR_QUERY = (
    "(select coalesce(string_agg(quote_literal(lexeme), ' | '), '')::tsquery "
    "from unnest(to_tsvector('english', %s))) as q(query)"
)


def _hybrid(
    conn: psycopg.Connection,
    *,
    table: str,
    id_column: str,
    where: str,
    params: list[object],
    text: str,
    vector: list[float],
    limit: int,
) -> list[str]:
    vec_rows = conn.execute(
        f"select {id_column} from public.{table} where {where} and embedding is not null "
        "order by embedding operator(extensions.<=>) %s::extensions.vector limit %s",
        [*params, to_vector(vector), CANDIDATES],
    ).fetchall()
    fts_rows = conn.execute(
        f"select {id_column} from public.{table}, {_OR_QUERY} where {where} and tsv @@ q.query "
        "order by ts_rank(tsv, q.query) desc limit %s",
        [text, *params, CANDIDATES],
    ).fetchall()
    return rrf([[r[0] for r in vec_rows], [r[0] for r in fts_rows]])[:limit]


def search_rules(
    conn: psycopg.Connection, brand_id: UUID, text: str, vector: list[float], limit: int = 6
) -> list[str]:
    """Rule codes of the best approved semantic rules for a unit."""
    return _hybrid(
        conn, table="rules", id_column="rule_code",
        where="brand_id = %s and status = 'approved' and check_type = 'semantic'",
        params=[brand_id], text=text, vector=vector, limit=limit,
    )  # fmt: skip


def search_facts(
    conn: psycopg.Connection, brand_id: UUID, text: str, vector: list[float], limit: int = 3
) -> list[str]:
    """Fact codes of the best approved facts for a claim."""
    return _hybrid(
        conn, table="facts", id_column="fact_code",
        where="brand_id = %s and status = 'approved'",
        params=[brand_id], text=text, vector=vector, limit=limit,
    )  # fmt: skip
