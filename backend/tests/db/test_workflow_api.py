"""The full creator -> manager loop through the API on the real database (rolled back).

This is the end-to-end API test of task 14.1: upload, review, fix, submit, send back,
dismiss with a reason, exception, comments and approval, with fake AI.
"""

import json
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


class ToneLLM:
    """Flags 'embarrassing' (high) under R-001 with a fix; no claims."""

    name, model = "fake", "fake-1"

    def complete(self, system: str, prompt: str) -> str:
        if "Content units to review" in prompt:
            flags = []
            if "embarrassing" in prompt.split("Content units to review")[1]:
                flags.append(
                    {
                        "unit_id": "u1",
                        "rule_code": "R-001",
                        "severity": "high",
                        "evidence": "That is embarrassing.",
                        "explanation": "Shames learners.",
                        "suggested_fix": "Everyone starts somewhere.",
                        "confidence": 0.9,
                    }
                )
            return json.dumps({"flags": flags})
        if "Find every claim" in prompt:
            return '{"claims": []}'
        return '{"verdicts": []}'


@pytest.fixture
def loop(db):
    brand = make_brand(db)
    users = {r: CurrentUser(make_user(db, brand, r), r, brand) for r in ("creator", "manager")}
    store_rules(db, brand, [
        RuleDraft("R-001", "tone", "Never shame learners.", "g", 1, always_on=True),
        RuleDraft("R-002", "terminology", "Never say cheap.", "g", 2, check_type="deterministic",
                  det_kind="banned_terms", terms=["cheap"]),
    ], FakeEmbedder())  # fmt: skip
    set_rule_status(db, brand, ["R-001", "R-002"], "approved", None)

    class OnePool:
        @contextmanager
        def connection(self):
            yield db

    client = LLMClient([ToneLLM()], SQLiteCache(":memory:"), MemoryCallLogger())

    def run(version_id, actor_id):
        review_content(
            version_id,
            pool=OnePool(),
            client=client,
            embedder=FakeEmbedder(),
            today=date(2026, 11, 15),
            actor_id=actor_id,
            use_presidio=False,
        )

    current = {"user": users["creator"]}
    app.dependency_overrides[deps.get_conn] = lambda: NoCommit(db)
    app.dependency_overrides[deps.get_current_user] = lambda: current["user"]
    app.dependency_overrides[contents_api.review_runner] = lambda: run
    yield TestClient(app), users, current, db
    app.dependency_overrides.clear()


def flags_of(api, content):
    return api.get(f"/versions/{content['latest_version_id']}/flags").json()["flags"]


def test_full_loop(loop):
    api, users, current, db = loop
    as_ = lambda role: current.update(user=users[role])  # noqa: E731

    c = api.post(
        "/contents", data={"title": "Loop", "text": "That is embarrassing. A cheap course."}
    ).json()
    cid = c["id"]
    c = api.get(f"/contents/{cid}").json()
    assert c["status"] == "creator_review" and c["counts"]["open_high"] == 1

    # Submitting with an open high-severity flag is refused.
    blocked = api.post(f"/contents/{cid}/submit")
    assert blocked.status_code == 409 and "high-severity" in blocked.json()["detail"]

    # A manager cannot approve before submission (invalid transition).
    as_("manager")
    assert api.post(f"/contents/{cid}/approve", json={}).status_code == 409
    as_("creator")

    # Accept the fix: new version 2 with the fixed text, reviewed again.
    tone = next(f for f in flags_of(api, c) if f["source_id"] == "R-001")
    accepted = api.post(f"/flags/{tone['id']}/accept")
    assert accepted.status_code == 200, accepted.text
    c = api.get(f"/contents/{cid}").json()
    assert c["latest_version_number"] == 2 and c["status"] == "creator_review"
    assert c["text"] == "Everyone starts somewhere. A cheap course."
    assert [f["source_id"] for f in flags_of(api, c)] == ["R-002"]  # only "cheap" is left
    # Accepting an old version's flag is refused.
    assert api.post(f"/flags/{tone['id']}/accept").status_code == 409

    # Submit (only a medium flag is open).
    assert api.post(f"/contents/{cid}/submit").json()["status"] == "manager_review"

    # Manager sends it back with a comment.
    as_("manager")
    assert api.post(f"/contents/{cid}/request-changes", json={"comment": "x"}).status_code == 422
    sent_back = api.post(
        f"/contents/{cid}/request-changes", json={"comment": "Please check the wording."}
    )
    assert sent_back.json()["status"] == "changes_requested"
    comments = api.get(f"/versions/{c['latest_version_id']}/comments").json()
    assert [cm["body"] for cm in comments] == ["Please check the wording."]

    # Creator reopens, dismisses the remaining flag with a reason, comments, resubmits.
    as_("creator")
    assert api.post(f"/contents/{cid}/reopen").json()["status"] == "creator_review"
    cheap = flags_of(api, c)[0]
    assert api.post(f"/flags/{cheap['id']}/dismiss", json={"reason": ""}).status_code == 422
    assert (
        api.post(
            f"/flags/{cheap['id']}/dismiss", json={"reason": "Quoting a reader review."}
        ).status_code
        == 204
    )
    note = api.post(
        f"/versions/{c['latest_version_id']}/comments",
        json={"body": "Kept it as a quote.", "flag_id": cheap["id"]},
    )
    assert note.status_code == 201 and note.json()["flag_id"] == cheap["id"]
    assert api.post(f"/contents/{cid}/submit").json()["status"] == "manager_review"

    # Creators cannot except; the manager approves an exception, then the content.
    assert (
        api.post(f"/flags/{cheap['id']}/except", json={"reason": "Fine as a quote."}).status_code
        == 403
    )
    as_("manager")
    assert (
        api.post(
            f"/flags/{cheap['id']}/except", json={"reason": "Reader quotes may use it."}
        ).status_code
        == 204
    )
    exception = db.execute(
        "select source_id, evidence, reason from public.approved_exceptions where flag_id = %s",
        (cheap["id"],),
    ).fetchone()
    assert exception == ("R-002", "cheap", "Reader quotes may use it.")
    approved = api.post(f"/contents/{cid}/approve", json={"comment": "Good to go."})
    assert approved.json()["status"] == "approved"

    # Approved is final, and every transition was audited.
    assert (
        api.post(f"/contents/{cid}/request-changes", json={"comment": "Too late now."}).status_code
        == 409
    )
    actions = [
        a
        for (a,) in db.execute(
            "select action from public.audit_log where entity_type = 'content' and entity_id = %s "
            "order by id",
            (cid,),
        ).fetchall()
    ]
    assert actions == [
        "content.create",
        "content.submit",
        "content.review_done",
        "content.new_version",
        "content.review_done",
        "content.submit_for_approval",
        "content.request_changes",
        "content.reopen",
        "content.submit_for_approval",
        "content.approve",
    ]


def test_another_creator_cannot_act_on_flags(loop, db):
    api, users, current, _ = loop
    c = api.post("/contents", data={"title": "Mine", "text": "That is embarrassing."}).json()
    flag = flags_of(api, api.get(f"/contents/{c['id']}").json())[0]
    current["user"] = CurrentUser(
        make_user(db, users["creator"].brand_id, "creator"), "creator", users["creator"].brand_id
    )
    assert api.post(f"/flags/{flag['id']}/dismiss", json={"reason": "Not mine."}).status_code == 404
    assert api.post(f"/flags/{flag['id']}/accept").status_code == 404


def test_accept_all_fixes_makes_one_new_version(loop):
    api, users, current, db = loop
    c = api.post(
        "/contents",
        data={"title": "Bulk", "text": "That is embarrassing. A cheap course."},
    ).json()
    cid = c["id"]
    c = api.get(f"/contents/{cid}").json()
    flags = flags_of(api, c)
    assert {f["source_id"] for f in flags} == {"R-001", "R-002"}

    # A manager can't accept a creator's fixes; an unknown flag id is refused.
    current.update(user=users["manager"])
    assert api.post(f"/contents/{cid}/accept-fixes", json={}).status_code == 403
    current.update(user=users["creator"])
    bad = api.post(
        f"/contents/{cid}/accept-fixes",
        json={"flag_ids": ["00000000-0000-0000-0000-000000000000"]},
    )
    assert bad.status_code == 409

    # All fixes: only R-001 has a suggested fix (banned words have none), so one is applied.
    out = api.post(f"/contents/{cid}/accept-fixes", json={})
    assert out.status_code == 200, out.text
    body = out.json()
    tone = next(f for f in flags if f["source_id"] == "R-001")
    assert body["applied"] == [tone["id"]] and body["skipped"] == []
    c = api.get(f"/contents/{cid}").json()
    assert c["latest_version_number"] == 2 and c["status"] == "creator_review"
    assert c["text"] == "Everyone starts somewhere. A cheap course."
    assert [f["source_id"] for f in flags_of(api, c)] == ["R-002"]

    # Nothing left with a fix on the new version.
    again = api.post(f"/contents/{cid}/accept-fixes", json={})
    assert again.status_code == 422
