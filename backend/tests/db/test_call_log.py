"""DBCallLogger writes ai_calls rows (rolled back), and never raises."""

from contextlib import contextmanager

import pytest

from app.llm.call_log import CallRecord, DBCallLogger
from tests.db.helpers import make_brand

pytestmark = pytest.mark.db


class OneConnectionPool:
    """Pool stand-in that hands out the test's (rolled-back) connection."""

    def __init__(self, conn) -> None:
        self.conn = conn

    @contextmanager
    def connection(self):
        yield self.conn


def test_db_logger_writes_a_row(db):
    brand = make_brand(db)
    DBCallLogger(OneConnectionPool(db)).log(
        CallRecord(provider="gemini", model="gemini-2.5-flash", purpose="judge", ok=False,
                   latency_ms=812, error="rate limited", brand_id=brand)
    )  # fmt: skip
    row = db.execute(
        "select provider, model, purpose, ok, cached, latency_ms, error "
        "from public.ai_calls where brand_id = %s",
        (brand,),
    ).fetchone()
    assert row == ("gemini", "gemini-2.5-flash", "judge", False, False, 812, "rate limited")


def test_db_logger_swallows_errors(caplog):
    class BrokenPool:
        @contextmanager
        def connection(self):
            raise RuntimeError("database down")
            yield

    DBCallLogger(BrokenPool()).log(CallRecord(provider="g", model="m", purpose="p", ok=True))
    assert "could not write ai_calls row" in caplog.text
