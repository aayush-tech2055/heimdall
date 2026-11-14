"""Fixtures for tests that run against the real Supabase Postgres database.

These tests are skipped unless `HEIMDALL_DB_TESTS=1` and `DATABASE_URL` is set (CI has no
database). Each test runs inside one transaction that is always rolled back, so nothing it
creates (including `auth.users` rows) is ever committed.

    HEIMDALL_DB_TESTS=1 pytest tests/db
"""

import os
from collections.abc import Iterator

import psycopg
import pytest

from app.config import get_settings


@pytest.fixture
def db() -> Iterator[psycopg.Connection]:
    if os.environ.get("HEIMDALL_DB_TESTS") != "1":
        pytest.skip("database tests are opt-in: set HEIMDALL_DB_TESTS=1")
    url = get_settings().database_url
    if not url:
        pytest.skip("DATABASE_URL is not set")
    conn = psycopg.connect(url, autocommit=False)
    try:
        yield conn
    finally:
        conn.rollback()
        conn.close()
