"""Postgres connection pool for the Supabase database (`DATABASE_URL`).

The backend connects as the database owner, so row-level security does not apply to it; API
routes must check the caller's brand and role themselves.
"""

from functools import lru_cache

from psycopg_pool import ConnectionPool

from app.config import get_settings


@lru_cache
def get_pool() -> ConnectionPool:
    """The process-wide pool, opened on first use. `pool.connection()` commits on success."""
    url = get_settings().database_url
    if not url:
        raise RuntimeError("DATABASE_URL is not set in backend/.env")
    # Small pool: the Supabase session pooler allows few connections on the free tier.
    return ConnectionPool(url, min_size=1, max_size=5, open=True, name="heimdall")
