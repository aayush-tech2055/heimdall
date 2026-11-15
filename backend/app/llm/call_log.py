"""Per-call logging to `ai_calls` (decision 25); drives the "AI used" disclosure labels."""

import logging
from dataclasses import asdict, dataclass
from typing import Protocol
from uuid import UUID

from psycopg_pool import ConnectionPool

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class CallRecord:
    provider: str
    model: str
    purpose: str
    ok: bool
    cached: bool = False
    latency_ms: int | None = None
    error: str | None = None
    brand_id: UUID | None = None
    content_version_id: UUID | None = None


class CallLogger(Protocol):
    def log(self, record: CallRecord) -> None: ...


class MemoryCallLogger:
    """Keeps records in a list (tests, scripts)."""

    def __init__(self) -> None:
        self.records: list[CallRecord] = []

    def log(self, record: CallRecord) -> None:
        self.records.append(record)


class DBCallLogger:
    """Writes each record to `public.ai_calls`. A logging failure never fails the AI call."""

    def __init__(self, pool: ConnectionPool) -> None:
        self._pool = pool

    def log(self, record: CallRecord) -> None:
        try:
            with self._pool.connection() as conn:
                conn.execute(
                    "insert into public.ai_calls (brand_id, provider, model, purpose, "
                    "content_version_id, ok, cached, latency_ms, error) values "
                    "(%(brand_id)s, %(provider)s, %(model)s, %(purpose)s, "
                    "%(content_version_id)s, %(ok)s, %(cached)s, %(latency_ms)s, %(error)s)",
                    asdict(record),
                )
        except Exception:  # noqa: BLE001 - logging must not break the review
            log.exception("could not write ai_calls row for %s", record.purpose)
