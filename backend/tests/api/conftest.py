"""Helpers for API tests: a signed-in user without a database, and fake AI dependencies."""

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.api.deps import CurrentUser
from app.main import app


class NoDB:
    """Stands in for a connection in tests that must never reach the database."""

    def execute(self, *args, **kwargs):
        raise AssertionError("this test should not touch the database")


@pytest.fixture
def api() -> Iterator[TestClient]:
    app.dependency_overrides[deps.get_conn] = lambda: NoDB()
    yield TestClient(app)
    app.dependency_overrides.clear()


def sign_in_as(role: str, brand_id: uuid.UUID | None = None) -> CurrentUser:
    user = CurrentUser(id=uuid.uuid4(), role=role, brand_id=brand_id or uuid.uuid4())
    app.dependency_overrides[deps.get_current_user] = lambda: user
    return user
