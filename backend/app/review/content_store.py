"""Read and create content, versions and their flags (task 6.8).

Visibility mirrors the RLS policies: creators see their own content, managers and admins see
every item of their brand. Anything a user may not see is reported as not found.
"""

from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from app.models.contents import (
    ContentDetail,
    ContentSummary,
    FlagCounts,
    ReviewUnitOut,
    StoredFlag,
    VersionFlags,
    VersionInfo,
)
from app.models.users import CurrentUser
from app.review.claims import CLAIM_POLICY_ID, CLAIM_POLICY_TEXT


class NotFoundError(LookupError):
    pass


_COUNTS = (
    "count(*) filter (where f.status = 'open') as open, "
    "count(*) filter (where f.status = 'open' and f.severity = 'high') as open_high, "
    "count(*) filter (where f.status <> 'open') as resolved"
)

_SUMMARY_SQL = f"""
select c.id, c.title, c.format, c.status, c.creator_id, p.display_name as creator_name,
       c.created_at, c.updated_at, lv.id as latest_version_id,
       lv.version_number as latest_version_number,
       (select row_to_json(x) from (select {_COUNTS} from public.flags f
                                    where f.version_id = lv.id) x) as counts
from public.contents c
left join public.profiles p on p.id = c.creator_id
left join lateral (select v.id, v.version_number from public.content_versions v
                   where v.content_id = c.id order by v.version_number desc limit 1) lv on true
"""


def _visible(user: CurrentUser) -> tuple[str, list[object]]:
    if user.role == "creator":
        return "c.brand_id = %s and c.creator_id = %s", [user.brand_id, user.id]
    return "c.brand_id = %s", [user.brand_id]


def _summary(row: dict) -> dict:
    return row | {"counts": FlagCounts(**(row["counts"] or {}))}


def list_contents(
    conn: psycopg.Connection, user: CurrentUser, status: str | None = None
) -> list[ContentSummary]:
    where, params = _visible(user)
    if status:
        where += " and c.status = %s"
        params.append(status)
    with conn.cursor(row_factory=dict_row) as cur:
        rows = cur.execute(
            f"{_SUMMARY_SQL} where {where} order by c.updated_at desc", params
        ).fetchall()
    return [ContentSummary.model_validate(_summary(r)) for r in rows]


def get_content(conn: psycopg.Connection, user: CurrentUser, content_id: UUID) -> ContentDetail:
    where, params = _visible(user)
    with conn.cursor(row_factory=dict_row) as cur:
        row = cur.execute(
            f"{_SUMMARY_SQL} where c.id = %s and {where}", [content_id, *params]
        ).fetchone()
        if row is None:
            raise NotFoundError("content")
        versions = cur.execute(
            f"""select v.id, v.version_number, v.created_at, v.review_started_at,
                       v.review_finished_at, v.review_error, v.extracted_text,
                       (select row_to_json(x) from (select {_COUNTS} from public.flags f
                                                    where f.version_id = v.id) x) as counts
                from public.content_versions v where v.content_id = %s
                order by v.version_number""",
            (content_id,),
        ).fetchall()
    latest = versions[-1] if versions else None
    return ContentDetail.model_validate(
        _summary(row)
        | {
            "versions": [VersionInfo.model_validate(_summary(v)) for v in versions],
            "text": latest["extracted_text"] if latest else None,
            "review_error": latest["review_error"] if latest else None,
        }
    )


def create_content(
    conn: psycopg.Connection, user: CurrentUser, *, title: str, fmt: str, text: str,
    storage_path: str | None = None,
) -> tuple[UUID, UUID]:  # fmt: skip
    """Create the content (status checking) and its version 1; return (content, version)."""
    content_id = conn.execute(
        "insert into public.contents (brand_id, title, format, status, creator_id) "
        "values (%s, %s, %s, 'checking', %s) returning id",
        (user.brand_id, title, fmt, user.id),
    ).fetchone()[0]
    version_id = add_version(conn, user, content_id, text, storage_path=storage_path)
    return content_id, version_id


def add_version(
    conn: psycopg.Connection, user: CurrentUser, content_id: UUID, text: str,
    storage_path: str | None = None,
) -> UUID:  # fmt: skip
    return conn.execute(
        "insert into public.content_versions (content_id, brand_id, version_number, "
        "extracted_text, storage_path, created_by) values (%s, %s, "
        "(select coalesce(max(version_number), 0) + 1 from public.content_versions "
        "where content_id = %s), %s, %s, %s) returning id",
        (content_id, user.brand_id, content_id, text, storage_path, user.id),
    ).fetchone()[0]


def version_flags(conn: psycopg.Connection, user: CurrentUser, version_id: UUID) -> VersionFlags:
    where, params = _visible(user)
    with conn.cursor(row_factory=dict_row) as cur:
        v = cur.execute(
            "select v.id as version_id, v.content_id, v.version_number, "
            "coalesce(v.extracted_text, '') as text from public.content_versions v "
            f"join public.contents c on c.id = v.content_id where v.id = %s and {where}",
            [version_id, *params],
        ).fetchone()
        if v is None:
            raise NotFoundError("version")
        units = cur.execute(
            "select unit_id, position, text, location from public.review_units "
            "where version_id = %s order by position",
            (version_id,),
        ).fetchall()
        flags = cur.execute(
            """select f.id, f.unit_id, f.source_type, f.source_id, f.category, f.severity,
                      f.evidence, f.explanation, f.suggested_fix, f.confidence, f.location,
                      f.layer, f.status, f.resolution_note, f.resolved_at,
                      case f.source_type
                        when 'rule' then (select r.text from public.rules r
                                          where r.brand_id = f.brand_id
                                            and r.rule_code = f.source_id)
                        when 'fact' then (select x.statement from public.facts x
                                          where x.brand_id = f.brand_id
                                            and x.fact_code = f.source_id)
                        else %s end as source_text
               from public.flags f where f.version_id = %s
               order by (f.location->>'evidence_start')::int nulls last,
                        array_position(array['high','medium','low'], f.severity)""",
            (CLAIM_POLICY_TEXT, version_id),
        ).fetchall()
    return VersionFlags.model_validate(
        v
        | {
            "units": [ReviewUnitOut.model_validate(u) for u in units],
            "flags": [StoredFlag.model_validate(f) for f in flags],
        }
    )


__all__ = ["CLAIM_POLICY_ID", "NotFoundError"]
