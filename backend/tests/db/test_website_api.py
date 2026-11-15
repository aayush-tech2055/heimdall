"""Fact-change approval keeps codes (12.3) and the asset library (12.4), on the real database."""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.main import app
from app.models.facts import FactCreate
from app.models.users import CurrentUser
from app.rag.facts_store import create_facts, list_facts
from tests.db.helpers import NoCommit, make_brand, make_user
from tests.rag.fakes import FakeEmbedder

pytestmark = pytest.mark.db


@pytest.fixture
def setup(db):
    brand = make_brand(db)
    users = {r: CurrentUser(make_user(db, brand, r), r, brand) for r in ("admin", "creator")}
    create_facts(db, brand, [FactCreate(entity="AcmeLearn Pro", attribute="monthly price",
                 value="599", unit="INR", statement="Pro costs ₹599 a month.")], FakeEmbedder(),
                 status="approved", actor_id=None, today=date.today())  # fmt: skip
    current = {"user": users["admin"]}
    app.dependency_overrides[deps.get_conn] = lambda: NoCommit(db)
    app.dependency_overrides[deps.get_current_user] = lambda: current["user"]
    app.dependency_overrides[deps.embedder] = lambda: FakeEmbedder()
    yield TestClient(app), brand, users, current, db
    app.dependency_overrides.clear()


def _change(db, brand, kind, code, value):
    return db.execute(
        "insert into public.fact_changes (brand_id, kind, fact_code, entity, attribute, old_value, "
        "new_value, unit, statement, source_url) values (%s, %s, %s, 'AcmeLearn Pro', %s, %s, %s, "
        "'INR', %s, 'https://acmelearn.example/pricing') returning id",
        (brand, kind, code, "monthly price" if code else "seats", "599" if code else None, value,
         f"Statement {value}."),
    ).fetchone()[0]  # fmt: skip


def test_accepting_a_change_keeps_the_fact_code_and_new_facts_are_added(setup):
    api, brand, _, _, db = setup
    changed = _change(db, brand, "changed", "F-001", "649")
    new = _change(db, brand, "new", None, "5")
    assert api.post(f"/fact-changes/{changed}/accept").json()["status"] == "accepted"
    assert api.post(f"/fact-changes/{new}/accept").json()["status"] == "accepted"
    assert api.post(f"/fact-changes/{new}/reject").status_code == 409  # already decided
    facts = {f.fact_code: f for f in list_facts(db, brand, date.today())}
    assert (
        facts["F-001"].value == "649"
        and facts["F-001"].source == "https://acmelearn.example/pricing"
    )
    assert facts["F-002"].value == "5" and facts["F-002"].status == "approved"
    assert api.get(f"/brands/{brand}/fact-changes").json() == []


def test_assets_add_list_delete_and_admin_only(setup):
    api, brand, users, current, _ = setup
    base = f"/brands/{brand}/assets"
    made = api.post(
        base, data={"kind": "disclaimer", "name": "T&Cs line", "text_content": "T&Cs apply."}
    )
    assert made.status_code == 201 and made.json()["has_file"] is False
    assert api.post(base, data={"kind": "logo", "name": "Empty"}).status_code == 422
    current["user"] = users["creator"]
    assert [a["name"] for a in api.get(base).json()] == ["T&Cs line"]
    assert (
        api.post(base, data={"kind": "other", "name": "x", "description": "y"}).status_code == 403
    )
    current["user"] = users["admin"]
    assert api.delete(f"{base}/{made.json()['id']}").status_code == 204
    assert api.get(base).json() == []
