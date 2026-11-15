"""Content API end to end on the real database (rolled back), with a fake review run."""

from contextlib import contextmanager
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.api import contents as contents_api
from app.api import deps
from app.llm.cache import SQLiteCache
from app.llm.call_log import MemoryCallLogger
from app.llm.client import LLMClient
from app.main import app
from app.models.users import CurrentUser
from app.rag.extraction import RuleDraft
from app.rag.rules_store import set_rule_status, store_rules
from app.review.orchestrator import review_content
from tests.db.helpers import NoCommit, make_brand, make_user
from tests.rag.fakes import FakeEmbedder


class NoFlagsLLM:
    name, model = "fake", "fake-1"

    def complete(self, system: str, prompt: str) -> str:
        if "Content units to review" in prompt:
            return '{"flags": []}'
        if "Find every claim" in prompt:
            return '{"claims": []}'
        return '{"verdicts": []}'


@pytest.fixture
def setup(db):
    brand = make_brand(db)
    users = {
        "creator": CurrentUser(make_user(db, brand, "creator"), "creator", brand),
        "other": CurrentUser(make_user(db, brand, "creator"), "creator", brand),
        "manager": CurrentUser(make_user(db, brand, "manager"), "manager", brand),
    }
    store_rules(db, brand, [RuleDraft("R-001", "terminology", "Never say cheap.", "g", 2,
                check_type="deterministic", det_kind="banned_terms", terms=["cheap"])],
                FakeEmbedder())  # fmt: skip
    set_rule_status(db, brand, ["R-001"], "approved", None)

    class OnePool:
        @contextmanager
        def connection(self):
            yield db

    client = LLMClient([NoFlagsLLM()], SQLiteCache(":memory:"), MemoryCallLogger())

    def run(version_id, actor_id):
        review_content(version_id, pool=OnePool(), client=client, embedder=FakeEmbedder(),
                       today=date(2026, 11, 15), actor_id=actor_id, use_presidio=False)  # fmt: skip

    current = {"user": users["creator"]}
    app.dependency_overrides[deps.get_conn] = lambda: NoCommit(db)
    app.dependency_overrides[deps.get_current_user] = lambda: current["user"]
    app.dependency_overrides[contents_api.review_runner] = lambda: run
    yield TestClient(app), users, current
    app.dependency_overrides.clear()


def test_upload_review_and_read_back(setup):
    api, users, current = setup
    created = api.post("/contents", data={"title": "Python on a budget",
                                           "text": "A cheap way to learn.\n\nStart today."})  # fmt: skip
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["status"] == "checking" and body["latest_version_number"] == 1

    content = api.get(f"/contents/{body['id']}").json()
    assert content["status"] == "creator_review"
    assert content["counts"] == {"open": 1, "open_high": 0, "resolved": 0}
    assert content["text"] == "A cheap way to learn.\n\nStart today."

    flags = api.get(f"/versions/{content['latest_version_id']}/flags").json()
    assert [u["unit_id"] for u in flags["units"]] == ["u1", "u2"]
    (flag,) = flags["flags"]
    assert (flag["source_id"], flag["evidence"], flag["status"]) == ("R-001", "cheap", "open")
    assert flag["source_text"] == "Never say cheap."
    assert flag["location"]["evidence_start"] == 2

    assert [c["title"] for c in api.get("/contents").json()] == ["Python on a budget"]

    current["user"] = users["other"]  # another creator cannot see it
    assert api.get(f"/contents/{body['id']}").status_code == 404
    assert api.get(f"/versions/{content['latest_version_id']}/flags").status_code == 404
    assert api.get("/contents").json() == []

    current["user"] = users["manager"]  # the manager sees the whole brand
    assert len(api.get("/contents", params={"status": "creator_review"}).json()) == 1
    assert api.post("/contents", data={"title": "x", "text": "y"}).status_code == 403


def test_bad_uploads(setup):
    api, _, _ = setup
    assert api.post("/contents", data={"title": "Empty", "text": "  "}).status_code == 422
    pdf = api.post("/contents", data={"title": "PDF"},
                   files={"file": ("x.docx", b"PK..", "application/octet-stream")})  # fmt: skip
    assert pdf.status_code == 415
    ok = api.post("/contents", data={"title": "File"},
                  files={"file": ("post.md", b"Hello there.", "text/markdown")})  # fmt: skip
    assert ok.status_code == 201


def test_recheck_only_after_a_failed_check(setup, db):
    api, _, _ = setup
    body = api.post("/contents", data={"title": "T", "text": "Fine text."}).json()
    # Each upload is checked once: a finished check can't be re-run.
    done = api.post(f"/contents/{body['id']}/recheck")
    assert done.status_code == 409 and "Upload a revised version" in done.json()["detail"]
    # After a failed check, "Try again" works.
    db.execute("update public.contents set status = 'draft' where id = %s", (body["id"],))
    db.execute(
        "update public.content_versions set review_error = 'AI busy' where content_id = %s",
        (body["id"],),
    )
    again = api.post(f"/contents/{body['id']}/recheck")
    assert again.status_code == 200 and again.json()["status"] == "checking"  # before the run
    assert api.get(f"/contents/{body['id']}").json()["status"] == "creator_review"  # after it


def test_recheck_while_checking_is_409(setup, db):
    api, _, _ = setup
    body = api.post("/contents", data={"title": "T", "text": "Fine text."}).json()
    db.execute("update public.contents set status = 'checking' where id = %s", (body["id"],))
    assert api.post(f"/contents/{body['id']}/recheck").status_code == 409
