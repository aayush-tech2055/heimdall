"""Row builders shared by the database tests."""

import uuid

import psycopg


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
