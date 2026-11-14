"""Facts API end to end on the real database (rolled back), fake embedder."""

from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import deps, facts
from app.api.deps import CurrentUser
from app.main import app
from tests.db.helpers import make_brand, make_user
from tests.rag.fakes import FakeEmbedder

pytestmark = pytest.mark.db
CSV = (Path(__file__).resolve().parents[3] / "test-data/brands/acmelearn/facts.csv").read_bytes()


@pytest.fixture
def setup(db):
    brand = make_brand(db)
    users = {r: CurrentUser(make_user(db, brand, r), r, brand) for r in ("admin", "creator")}
    current = {"user": users["admin"]}
    app.dependency_overrides[deps.get_conn] = lambda: db
    app.dependency_overrides[deps.embedder] = lambda: FakeEmbedder()
    app.dependency_overrides[deps.get_current_user] = lambda: current["user"]
    app.dependency_overrides[facts.today] = lambda: date(2026, 11, 15)
    yield TestClient(app), brand, users, current
    app.dependency_overrides.clear()


def test_import_approve_add_edit_and_search(setup):
    api, brand, users, current = setup
    base = f"/brands/{brand}/facts"

    imported = api.post(f"{base}/import", files={"file": ("facts.csv", CSV, "text/csv")})
    assert imported.status_code == 200, imported.text
    rows = imported.json()["imported"]
    assert len(rows) == 17 and {r["status"] for r in rows} == {"pending"}
    assert [r["fact_code"] for r in rows][:2] == ["F-001", "F-002"]
    assert [r["fact_code"] for r in rows if r["expiry"] == "expired"] == ["F-014", "F-015"]
    assert [r["fact_code"] for r in rows if r["expiry"] == "expiring"] == ["F-005"]

    approved = api.post(f"{base}/approve", json={"codes": ["F-001", "F-002"], "action": "approve"})
    assert [f["status"] for f in approved.json()] == ["approved", "approved"]

    added = api.post(base, json={"entity": "AcmeLearn", "attribute": "cities", "value": "40",
                                 "statement": "AcmeLearn has learners in 40 cities."})  # fmt: skip
    assert added.status_code == 201 and added.json()["fact_code"] == "F-018"
    assert added.json()["status"] == "approved"

    edited = api.patch(f"{base}/F-002", json={"value": "649", "statement": "Pro costs ₹649."})
    assert edited.json()["value"] == "649" and edited.json()["fact_code"] == "F-002"
    assert api.patch(f"{base}/F-999", json={"value": "1"}).status_code == 404

    assert [f["fact_code"] for f in api.get(base, params={"q": "trial"}).json()] == ["F-006"]
    assert len(api.get(base, params={"status": "approved"}).json()) == 3

    current["user"] = users["creator"]
    assert len(api.get(base).json()) == 18  # creators can read facts
    assert api.post(base, json={"entity": "x", "attribute": "y", "value": "z",
                                "statement": "s"}).status_code == 403  # fmt: skip


def test_bad_csv_imports_nothing_and_lists_row_errors(setup):
    api, brand, _, _ = setup
    bad = (
        b"entity,attribute,value,statement,valid_until\n"
        b"Pro,price,599,Pro costs 599.,soon\n"
        b",a,b,c,\n"
    )
    response = api.post(f"/brands/{brand}/facts/import", files={"file": ("f.csv", bad, "text/csv")})
    assert response.status_code == 422
    assert response.json()["detail"][0].startswith("Row 2: valid_until")
    assert response.json()["detail"][1].startswith("Row 3: entity")
    assert api.get(f"/brands/{brand}/facts").json() == []
