"""Brand settings API on the real database (rolled back)."""

import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.main import app
from app.models.users import CurrentUser
from tests.db.helpers import NoCommit, make_brand, make_user

pytestmark = pytest.mark.db


@pytest.fixture
def setup(db):
    brand = make_brand(db)
    users = {r: CurrentUser(make_user(db, brand, r), r, brand) for r in ("admin", "creator")}
    current = {"user": users["admin"]}
    app.dependency_overrides[deps.get_conn] = lambda: NoCommit(db)
    app.dependency_overrides[deps.get_current_user] = lambda: current["user"]
    yield TestClient(app), brand, users, current, db
    app.dependency_overrides.clear()


def test_defaults_update_and_permissions(setup):
    api, brand, users, current, db = setup
    url = f"/brands/{brand}/settings"
    first = api.get(url).json()
    assert first["confidential_terms"] == [] and first["claim_policy_enabled"] is True
    assert first["claim_policy_id"] == "SYS-CLAIM-001"

    saved = api.put(
        url,
        json={
            "confidential_terms": ["Project  Falcon", "project falcon", " "],
            "claim_policy_enabled": False,
            "readability_target": 60,
        },
    )
    assert saved.status_code == 200
    assert saved.json()["confidential_terms"] == ["Project Falcon"]
    assert saved.json()["claim_policy_enabled"] is False
    assert api.put(url, json={"readability_target": 150}).status_code == 422

    current["user"] = users["creator"]
    assert api.get(url).json()["readability_target"] == 60
    assert api.put(url, json={}).status_code == 403
    audited = db.execute(
        "select count(*) from public.audit_log where action = 'settings.update' and brand_id = %s",
        (brand,),
    ).fetchone()[0]
    assert audited == 1
