"""SQLite key-value cache for model outputs (decision 24).

The key is a hash of (schema name, system prompt, prompt), deliberately without the provider,
so a demo re-run hits the cache whichever provider answered first.
"""

import hashlib
import json
import sqlite3
import threading
from pathlib import Path


def cache_key(*parts: str) -> str:
    """A stable SHA-256 key over the given parts (length-prefixed so parts can't run together)."""
    digest = hashlib.sha256()
    for part in parts:
        data = part.encode("utf-8")
        digest.update(f"{len(data)}:".encode())
        digest.update(data)
    return digest.hexdigest()


class SQLiteCache:
    """A small thread-safe key-value store. Values are JSON-serialisable objects."""

    def __init__(self, path: str | Path, table: str = "llm_cache") -> None:
        if not table.isidentifier():
            raise ValueError(f"invalid table name: {table!r}")
        self._table = table
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock, self._conn:
            self._conn.execute(
                f"create table if not exists {table} ("
                "key text primary key, value text not null, "
                "created_at text not null default current_timestamp)"
            )

    def get(self, key: str) -> object | None:
        with self._lock:
            row = self._conn.execute(
                f"select value from {self._table} where key = ?", (key,)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def get_many(self, keys: list[str]) -> dict[str, object]:
        found: dict[str, object] = {}
        with self._lock:
            for start in range(0, len(keys), 500):
                chunk = keys[start : start + 500]
                marks = ",".join("?" * len(chunk))
                rows = self._conn.execute(
                    f"select key, value from {self._table} where key in ({marks})", chunk
                ).fetchall()
                found.update({k: json.loads(v) for k, v in rows})
        return found

    def set(self, key: str, value: object) -> None:
        self.set_many({key: value})

    def set_many(self, items: dict[str, object]) -> None:
        with self._lock, self._conn:
            self._conn.executemany(
                f"insert or replace into {self._table} (key, value) values (?, ?)",
                [(k, json.dumps(v)) for k, v in items.items()],
            )
