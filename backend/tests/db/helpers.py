"""Row builders and a role switcher shared by the database tests."""

import json
import uuid
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from psycopg.pq import TransactionStatus


def make_brand(conn: psycopg.Connection, slug: str | None = None) -> uuid.UUID:
    slug = slug or f"test-{uuid.uuid4().hex[:8]}"
    row = conn.execute(
        "insert into public.brands (name, slug) values (%s, %s) returning id", (slug, slug)
    ).fetchone()
    return row[0]


def make_user(conn: psycopg.Connection, brand_id: uuid.UUID, role: str) -> uuid.UUID:
    user_id = uuid.uuid4()
    conn.execute(
        "insert into auth.users (id, email, aud, role) "
        "values (%s, %s, 'authenticated', 'authenticated')",
        (user_id, f"{role}-{user_id.hex[:8]}@example.com"),
    )
    conn.execute(
        "insert into public.profiles (id, brand_id, role) values (%s, %s, %s)",
        (user_id, brand_id, role),
    )
    return user_id


def make_content(
    conn: psycopg.Connection, brand_id: uuid.UUID, creator_id: uuid.UUID, title: str = "Post"
) -> tuple[uuid.UUID, uuid.UUID]:
    """Create a text content item with version 1; return (content_id, version_id)."""
    content_id = conn.execute(
        "insert into public.contents (brand_id, title, format, creator_id) "
        "values (%s, %s, 'text', %s) returning id",
        (brand_id, title, creator_id),
    ).fetchone()[0]
    version_id = conn.execute(
        "insert into public.content_versions "
        "(content_id, brand_id, version_number, extracted_text) "
        "values (%s, %s, 1, 'Hello world.') returning id",
        (content_id, brand_id),
    ).fetchone()[0]
    return content_id, version_id


def _insert(conn: psycopg.Connection, table: str, values: dict) -> uuid.UUID:
    names = ", ".join(values)
    marks = ", ".join(["%s"] * len(values))
    return conn.execute(
        f"insert into public.{table} ({names}) values ({marks}) returning id",
        list(values.values()),
    ).fetchone()[0]


def insert_rule(conn: psycopg.Connection, brand_id: uuid.UUID, code: str = "R-001", **cols):
    values = {"brand_id": brand_id, "rule_code": code, "category": "tone", "text": "Be warm."}
    return _insert(conn, "rules", values | cols)


def insert_unit(
    conn: psycopg.Connection, brand_id: uuid.UUID, version_id: uuid.UUID, unit_id: str = "u1"
):
    location = {"paragraph": 0, "char_start": 0, "char_end": 12}
    values = {
        "version_id": version_id, "brand_id": brand_id, "unit_id": unit_id, "position": 0,
        "text": "Hello world.", "location": json.dumps(location),
    }  # fmt: skip
    return _insert(conn, "review_units", values)


def insert_flag(
    conn: psycopg.Connection,
    brand_id: uuid.UUID,
    version_id: uuid.UUID,
    unit_id: str = "u1",
    **cols,
):
    location = {"paragraph": 0, "char_start": 0, "char_end": 12,
                "evidence_start": 0, "evidence_end": 5}  # fmt: skip
    values = {
        "version_id": version_id, "brand_id": brand_id, "unit_id": unit_id,
        "source_type": "rule", "source_id": "R-001", "category": "tone", "severity": "low",
        "evidence": "Hello", "explanation": "Too casual.", "confidence": 0.8,
        "location": json.dumps(location), "layer": "guidelines",
    }  # fmt: skip
    return _insert(conn, "flags", values | cols)


@contextmanager
def as_user(conn: psycopg.Connection, user_id: uuid.UUID | None) -> Iterator[psycopg.Connection]:
    """Run statements as a Supabase API caller: `authenticated` with a JWT `sub`, or `anon`.

    This mirrors what PostgREST does per request, so the RLS policies apply exactly as they
    would to the frontend. Uses SET LOCAL, so it never outlives the test's transaction.
    """
    role = "authenticated" if user_id else "anon"
    claims = json.dumps({"sub": str(user_id), "role": role}) if user_id else ""
    conn.execute(f"set local role {role}")
    conn.execute("select set_config('request.jwt.claims', %s, true)", (claims,))
    try:
        yield conn
    finally:
        if conn.info.transaction_status != TransactionStatus.INERROR:
            conn.execute("reset role")
            conn.execute("select set_config('request.jwt.claims', '', true)")


class NoCommit:
    """Wraps the test connection for API tests: routes may call commit(), which must not
    commit the test's transaction (it is always rolled back)."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def commit(self) -> None:
        pass

    def __getattr__(self, name: str):  # noqa: ANN204
        return getattr(self._conn, name)
