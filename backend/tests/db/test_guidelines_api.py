"""Guidelines API end to end on the real database (rolled back), with fake AI."""

import json

import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.api.deps import CurrentUser
from app.llm.cache import SQLiteCache
from app.llm.call_log import MemoryCallLogger
from app.llm.client import LLMClient
from app.main import app
from tests.db.helpers import make_brand, make_user
from tests.rag.fakes import FakeEmbedder

pytestmark = pytest.mark.db


class GuidelineLLM:
    name, model = "fake", "fake-1"

    def complete(self, system: str, prompt: str) -> str:
        if "Extract every rule" in prompt:
            return json.dumps({"rules": [
                {"category": "tone", "text": "Keep it on-brand."},
                {"category": "terminology", "text": "Never say cheap.",
                 "check_type": "deterministic", "det_kind": "banned_terms", "terms": ["cheap"]},
            ]})  # fmt: skip
        if "<pair id=" in prompt:
            return json.dumps({"results": []})
        return json.dumps({"results": [
            {"rule_code": "R-001", "vague": True, "reason": "No observable property.",
             "suggested_rewrite": "Use the words in the tone list."}]})  # fmt: skip


@pytest.fixture
def setup(db):
    brand = make_brand(db)
    admin_id = make_user(db, brand, "admin")
    creator_id = make_user(db, brand, "creator")
    users = {
        "admin": CurrentUser(admin_id, "admin", brand),
        "creator": CurrentUser(creator_id, "creator", brand),
    }
    client = LLMClient([GuidelineLLM()], SQLiteCache(":memory:"), MemoryCallLogger())
    app.dependency_overrides[deps.get_conn] = lambda: db
    app.dependency_overrides[deps.llm_client] = lambda: client
    app.dependency_overrides[deps.embedder] = lambda: FakeEmbedder()
    current = {"user": users["admin"]}
    app.dependency_overrides[deps.get_current_user] = lambda: current["user"]
    yield TestClient(app), brand, users, current
    app.dependency_overrides.clear()


def test_upload_list_edit_approve_and_report(setup):
    api, brand, users, current = setup

    response = api.post(f"/brands/{brand}/guidelines", data={"text": "Tone\n\nBe on-brand."})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source_doc"] == "pasted text" and body["pages"] == 1
    assert [(r["rule_code"], r["status"], r["check_type"]) for r in body["rules"]] == [
        ("R-001", "pending", "semantic"),
        ("R-002", "pending", "deterministic"),
    ]
    assert [v["rule_code"] for v in body["report"]["vague"]] == ["R-001"]
    assert set(body["report"]["missing_categories"]) == {
        "claims",
        "visuals",
        "accessibility",
        "legal",
    }

    pending = api.get(f"/brands/{brand}/rules", params={"status": "pending"}).json()
    assert [r["rule_code"] for r in pending] == ["R-001", "R-002"]

    edited = api.patch("/rules/R-001", json={"text": "Use a warm, friendly tone."})
    assert edited.status_code == 200 and edited.json()["text"] == "Use a warm, friendly tone."

    approved = api.post("/rules/approve", json={"codes": ["R-001", "R-002"], "action": "approve"})
    assert [r["status"] for r in approved.json()] == ["approved", "approved"]
    assert (
        api.post("/rules/approve", json={"codes": ["R-404"], "action": "reject"}).status_code == 404
    )

    assert api.get(f"/brands/{brand}/guidelines/report").json()["vague"][0]["rule_code"] == "R-001"

    current["user"] = users["creator"]  # creators can read rules but not the report
    assert len(api.get(f"/brands/{brand}/rules").json()) == 2
    assert api.get(f"/brands/{brand}/guidelines/report").status_code == 403


def test_second_upload_continues_rule_numbering(setup):
    api, brand, _, _ = setup
    api.post(f"/brands/{brand}/guidelines", data={"text": "First guide."})
    second = api.post(f"/brands/{brand}/guidelines", data={"text": "Second guide."}).json()
    assert [r["rule_code"] for r in second["rules"]] == ["R-003", "R-004"]
