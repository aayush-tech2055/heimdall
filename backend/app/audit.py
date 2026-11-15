"""Write `audit_log` rows: who did what to which entity, with before/after snapshots."""

import json
from uuid import UUID

import psycopg


def _jsonable(value: object) -> str | None:
    return None if value is None else json.dumps(value, default=str)


def audit(
    conn: psycopg.Connection,
    *,
    brand_id: UUID,
    actor_id: UUID | None,
    action: str,
    entity_type: str,
    entity_id: str,
    before: object = None,
    after: object = None,
) -> None:
    conn.execute(
        "insert into public.audit_log (brand_id, actor_id, action, entity_type, entity_id, "
        "before, after) values (%s, %s, %s, %s, %s, %s, %s)",
        (brand_id, actor_id, action, entity_type, entity_id, _jsonable(before), _jsonable(after)),
    )
