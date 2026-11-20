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
from tests.db.helpers import NoCommit, email_of, make_brand, make_user
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


def submit_to(db, users):
    return {"manager_email": email_of(db, users["manager"].id)}


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

    # A manager cannot approve before submission (invalid transition).
    as_("manager")
    assert api.post(f"/contents/{cid}/approve", json={}).status_code == 409
    as_("creator")

    # Accept the fix: version 2 with the fixed text, NOT checked again; its flags are carried
    # over with their positions moved to the new text.
    tone = next(f for f in flags_of(api, c) if f["source_id"] == "R-001")
    accepted = api.post(f"/flags/{tone['id']}/accept")
    assert accepted.status_code == 200, accepted.text
    c = api.get(f"/contents/{cid}").json()
    assert c["latest_version_number"] == 2 and c["status"] == "creator_review"
    assert c["fixes_applied"] is True
    assert c["text"] == "Everyone starts somewhere. A cheap course."
    v2 = {f["source_id"]: f for f in flags_of(api, c)}
    assert v2["R-001"]["status"] == "accepted" and v2["R-002"]["status"] == "open"
    loc = v2["R-002"]["location"]
    assert c["text"][loc["evidence_start"] : loc["evidence_end"]] == "cheap"
    # One fix round only: the old version's flag and the new version's flags are refused.
    assert api.post(f"/flags/{tone['id']}/accept").status_code == 409
    again = api.post(
        f"/contents/{cid}/accept-fixes", json={"edits": {v2["R-002"]["id"]: "affordable"}}
    )
    assert again.status_code == 409 and "already applied" in again.json()["detail"]

    # Submit.
    assert (
        api.post(f"/contents/{cid}/submit", json=submit_to(db, users)).json()["status"]
        == "manager_review"
    )

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
    cheap = next(f for f in flags_of(api, c) if f["source_id"] == "R-002")
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
    assert (
        api.post(f"/contents/{cid}/submit", json=submit_to(db, users)).json()["status"]
        == "manager_review"
    )

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
        "flag.fix_round",  # the creator's fixes: a new version, not checked again
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


def test_fix_round_applies_accepted_and_reworded_fixes_at_once(loop):
    api, users, current, db = loop
    c = api.post(
        "/contents",
        data={"title": "Bulk", "text": "That is embarrassing. A cheap course."},
    ).json()
    cid = c["id"]
    c = api.get(f"/contents/{cid}").json()
    flags = {f["source_id"]: f for f in flags_of(api, c)}
    tone, cheap = flags["R-001"], flags["R-002"]

    # A manager can't run a creator's fix round; an unknown flag id is refused; a flag with
    # no suggested fix can only be reworded.
    current.update(user=users["manager"])
    assert api.post(f"/contents/{cid}/accept-fixes", json={}).status_code == 403
    current.update(user=users["creator"])
    url = f"/contents/{cid}/accept-fixes"
    bad = api.post(url, json={"flag_ids": ["00000000-0000-0000-0000-000000000000"]})
    assert bad.status_code == 409
    assert api.post(url, json={"flag_ids": [cheap["id"]]}).status_code == 422

    # All suggested fixes plus the creator's own wording for "cheap", in one version.
    out = api.post(url, json={"edits": {cheap["id"]: "low-cost"}})
    assert out.status_code == 200, out.text
    body = out.json()
    assert set(body["applied"]) == {tone["id"], cheap["id"]} and body["skipped"] == []
    assert body["content"]["status"] == "creator_review"  # not checked again
    c = api.get(f"/contents/{cid}").json()
    assert c["latest_version_number"] == 2 and c["fixes_applied"] is True
    assert c["text"] == "Everyone starts somewhere. A low-cost course."
    v2 = {f["source_id"]: f for f in flags_of(api, c)}
    assert v2["R-001"]["status"] == "accepted"
    assert v2["R-002"]["status"] == "edited"
    assert v2["R-002"]["resolution_note"] == "Replaced with: low-cost"
    assert db.execute(
        "select review_started_at from public.content_versions where id = %s",
        (c["latest_version_id"],),
    ).fetchone() == (None,)

    # No second round; a revised upload is checked again and allows a new round.
    assert api.post(url, json={}).status_code == 409
    revised = api.post(
        f"/contents/{cid}/versions", data={"text": "That is embarrassing. Great course."}
    )
    assert revised.status_code == 201, revised.text
    c = api.get(f"/contents/{cid}").json()
    assert c["latest_version_number"] == 3 and c["fixes_applied"] is False
    assert [f["source_id"] for f in flags_of(api, c)] == ["R-001"]


def test_submit_with_open_high_flags_leaves_them_to_the_manager(loop):
    api, users, current, db = loop
    c = api.post("/contents", data={"title": "Direct", "text": "That is embarrassing."}).json()
    assert api.get(f"/contents/{c['id']}").json()["counts"]["open_high"] == 1
    sent = api.post(f"/contents/{c['id']}/submit", json=submit_to(db, users))
    assert sent.status_code == 200 and sent.json()["status"] == "manager_review"


def test_submit_needs_a_manager_on_the_team(loop):
    api, users, current, db = loop
    c = api.post("/contents", data={"title": "Who", "text": "That is embarrassing."}).json()
    bad = api.post(f"/contents/{c['id']}/submit", json={"manager_email": "nobody@example.com"})
    assert bad.status_code == 422 and "No manager" in bad.json()["detail"]
    other_brand = make_brand(db)
    outsider = make_user(db, other_brand, "manager")  # a manager, but on another team
    out = api.post(f"/contents/{c['id']}/submit", json={"manager_email": email_of(db, outsider)})
    assert out.status_code == 422
    ok = api.post(f"/contents/{c['id']}/submit", json=submit_to(db, users)).json()
    assert ok["status"] == "manager_review"
    assert ok["manager_id"] == str(users["manager"].id)
    assert ok["creator_email"] == email_of(db, users["creator"].id)


def test_managers_see_only_what_was_sent_to_them(loop):
    api, users, current, db = loop
    brand = users["creator"].brand_id
    second = CurrentUser(make_user(db, brand, "manager"), "manager", brand)
    c = api.post("/contents", data={"title": "Mine", "text": "Fine words."}).json()
    api.post(f"/contents/{c['id']}/submit", json=submit_to(db, users))
    current.update(user=users["manager"])
    assert [x["id"] for x in api.get("/contents").json()] == [c["id"]]
    current.update(user=second)
    assert api.get("/contents").json() == []


def test_manager_reevaluates_back_to_the_same_creator(loop):
    api, users, current, db = loop
    c = api.post("/contents", data={"title": "Again", "text": "That is embarrassing."}).json()
    api.post(f"/contents/{c['id']}/submit", json=submit_to(db, users))
    current.update(user=users["creator"])
    assert api.post(f"/contents/{c['id']}/reevaluate", json={}).status_code == 403
    current.update(user=users["manager"])
    out = api.post(f"/contents/{c['id']}/reevaluate", json={"comment": "Check the tone again."})
    assert out.status_code == 200, out.text
    after = api.get(f"/contents/{c['id']}").json()
    assert after["status"] == "creator_review" and after["creator_id"] == str(users["creator"].id)
    comments = api.get(f"/versions/{after['latest_version_id']}/comments").json()
    assert comments[-1]["body"] == "Re-evaluation requested. Check the tone again."
