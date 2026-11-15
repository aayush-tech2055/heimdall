"""The full review pipeline on the real database (rolled back), with fake AI (task 6.7)."""

import json
import re
from contextlib import contextmanager
from datetime import date

import pytest

from app.llm.cache import SQLiteCache
from app.llm.call_log import MemoryCallLogger
from app.llm.client import LLMClient
from app.models.facts import FactCreate
from app.rag.extraction import RuleDraft
from app.rag.facts_store import create_facts
from app.rag.rules_store import set_rule_status, store_rules
from app.review.orchestrator import review_content
from tests.db.helpers import make_brand, make_content, make_user
from tests.rag.fakes import FakeEmbedder

pytestmark = pytest.mark.db
TODAY = date(2026, 11, 15)
TEXT = (
    "Cheap course for everyone!\n\n"
    "Still stuck? That is embarrassing. AcmeLearn has 3 million learners. Mail a@b.co now."
)


class OnePool:
    def __init__(self, conn):
        self.conn = conn

    @contextmanager
    def connection(self):
        yield self.conn


class PipelineLLM:
    name, model = "fake", "fake-1"

    def __init__(self):
        self.prompts: list[str] = []

    def complete(self, system: str, prompt: str) -> str:
        self.prompts.append(prompt)
        if "Content units to review" in prompt:
            flags = [
                {"unit_id": u, "rule_code": "R-001", "severity": "medium",
                 "evidence": "That is embarrassing.", "explanation": "Shames learners.",
                 "suggested_fix": "Let's fix that together.", "confidence": 0.9}
                for u, t in re.findall(r'<content unit_id="(u\d+)">\n(.*?)\n</content>', prompt, re.S)
                if "embarrassing" in t
            ] + [{"unit_id": "u2", "rule_code": "R-999", "severity": "low", "evidence": "now",
                  "explanation": "Not a supplied rule.", "confidence": 0.5}]  # fmt: skip
            return json.dumps({"flags": flags})
        if "Find every claim" in prompt:
            return json.dumps({"claims": [{"unit_id": "u2", "claim": "3 million learners",
                                           "entity": "AcmeLearn", "attribute": "learners"}]})  # fmt: skip
        codes = re.findall(r"^\[(F-\d+)\]", prompt, re.M)
        return json.dumps({"verdicts": [{"claim_id": "c1", "verdict": "contradicted",
                                         "fact_code": codes[0], "explanation": "Fact says 2 million.",
                                         "suggested_fix": "2 million learners", "confidence": 0.9}]})  # fmt: skip


@pytest.fixture
def brand_setup(db):
    brand = make_brand(db)
    creator = make_user(db, brand, "creator")
    store_rules(db, brand, [
        RuleDraft("R-001", "tone", "Use a warm tone; never shame learners.", "g", 1, always_on=True),
        RuleDraft("R-002", "terminology", "Never say cheap.", "g", 2, check_type="deterministic",
                  det_kind="banned_terms", terms=["cheap"]),
        RuleDraft("R-003", "legal", "End with T&Cs apply.", "g", 5, check_type="deterministic",
                  det_kind="required_phrase", terms=["T&Cs apply."]),
    ], FakeEmbedder())  # fmt: skip
    set_rule_status(db, brand, ["R-001", "R-002", "R-003"], "approved", None)
    create_facts(db, brand, [FactCreate(entity="AcmeLearn", attribute="learners", value="2000000",
                 statement="More than 2 million learners have registered.")], FakeEmbedder(),
                 status="approved", actor_id=None, today=TODAY)  # fmt: skip
    content_id, version_id = make_content(db, brand, creator)
    db.execute("update public.content_versions set extracted_text = %s where id = %s",
               (TEXT, version_id))  # fmt: skip
    return brand, creator, content_id, version_id


def run(db, version_id, providers):
    client = LLMClient(providers, SQLiteCache(":memory:"), MemoryCallLogger(),
                       rate_limit_rounds=1)  # fmt: skip
    return review_content(version_id, pool=OnePool(db), client=client, embedder=FakeEmbedder(),
                          today=TODAY, use_presidio=False)  # fmt: skip


def test_review_flags_every_layer_validates_and_saves(db, brand_setup):
    _, _, content_id, version_id = brand_setup
    llm = PipelineLLM()
    outcome = run(db, version_id, [llm])

    flags = db.execute(
        "select source_id, layer, evidence, status from public.flags where version_id = %s "
        "order by (location->>'evidence_start')::int, source_id", (version_id,),
    ).fetchall()  # fmt: skip
    assert flags == [
        ("R-002", "rules", "Cheap", "open"),
        ("R-001", "guidelines", "That is embarrassing.", "open"),
        ("F-001", "claims", "3 million learners", "open"),
        ("R-003", "rules", "", "open"),
    ]
    dropped = db.execute("select reason from public.dropped_flags where version_id = %s",
                         (version_id,)).fetchall()  # fmt: skip
    assert dropped == [("source_not_supplied",)]
    units = db.execute("select unit_id, retrieved_rules from public.review_units "
                       "where version_id = %s order by position", (version_id,)).fetchall()  # fmt: skip
    assert units[0][0] == "u1" and "R-001" in units[1][1]
    status = db.execute(
        "select status from public.contents where id = %s", (content_id,)
    ).fetchone()
    assert status == ("creator_review",)
    assert all("a@b.co" not in p for p in llm.prompts) and any("[EMAIL]" in p for p in llm.prompts)
    assert outcome.seconds >= 0


def test_failed_review_goes_back_to_draft_with_the_error(db, brand_setup):
    _, _, content_id, version_id = brand_setup
    assert run(db, version_id, []) is None
    status = db.execute(
        "select status from public.contents where id = %s", (content_id,)
    ).fetchone()
    error = db.execute("select review_error from public.content_versions where id = %s",
                       (version_id,)).fetchone()[0]  # fmt: skip
    assert status == ("draft",) and "No AI provider is configured" in error


def test_dismissals_carry_over_to_the_next_version(db, brand_setup):
    brand, creator, content_id, version_id = brand_setup
    run(db, version_id, [PipelineLLM()])
    db.execute("update public.flags set status = 'dismissed', resolution_note = 'Approved pun' "
               "where version_id = %s and source_id = 'R-002'", (version_id,))  # fmt: skip
    v2 = db.execute(
        "insert into public.content_versions (content_id, brand_id, version_number, extracted_text) "
        "values (%s, %s, 2, %s) returning id", (content_id, brand, TEXT),
    ).fetchone()[0]  # fmt: skip
    run(db, v2, [PipelineLLM()])
    rows = db.execute("select source_id, status, resolution_note from public.flags "
                      "where version_id = %s and source_id = 'R-002'", (v2,)).fetchall()  # fmt: skip
    assert rows == [("R-002", "dismissed", "Approved pun")]
