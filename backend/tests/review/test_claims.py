"""Layer (c): claims against facts (task 6.5)."""

import json
import re
from datetime import UTC, date, datetime

from app.llm.cache import SQLiteCache
from app.llm.call_log import MemoryCallLogger
from app.llm.client import LLMClient
from app.models.facts import Fact
from app.processing.redaction import redact
from app.review.claims import CLAIM_POLICY_ID, run_claims
from app.review.segment import segment_text
from tests.rag.fakes import FakeEmbedder


def fact(code, entity, statement, expiry="valid"):
    return Fact(
        fact_code=code, entity=entity, attribute="a", value="v", unit=None, statement=statement,
        source=None, valid_until=date(2026, 6, 30) if expiry == "expired" else None,
        status="approved", expiry=expiry, updated_at=datetime.now(UTC),
    )  # fmt: skip


FACTS = {
    "AcmeLearn Plus": [fact("F-014", "AcmeLearn Plus", "Plus costs ₹2,999 a year.", "expired")],
    "AcmeLearn": [fact("F-003", "AcmeLearn", "More than 2 million learners.")],
}


class ClaimsLLM:
    """Extraction: returns scripted claims. Verification: scripted verdicts by claim text."""

    name, model = "fake", "fake-1"

    def __init__(self, claims, verdicts):
        self.claims, self.verdicts, self.verify_prompts = claims, verdicts, []

    def complete(self, system: str, prompt: str) -> str:
        if "Find every claim" in prompt:
            return json.dumps({"claims": self.claims})
        self.verify_prompts.append(prompt)
        out = []
        for cid, quote in re.findall(r"claim_id=(c\d+).*?\nquote: (.*)", prompt):
            verdict, code = self.verdicts[quote]
            out.append({"claim_id": cid, "verdict": verdict, "fact_code": code,
                        "explanation": f"{verdict} by {code}", "confidence": 0.8})  # fmt: skip
        out.append({"claim_id": "c99", "verdict": "contradicted", "fact_code": "F-003",
                    "explanation": "invented", "confidence": 0.5})  # fmt: skip
        return json.dumps({"verdicts": out})


TEXT = (
    "Save with an annual AcmeLearn Plus plan for just ₹2,999 a year.\n\n"
    "AcmeLearn has over 3 million registered learners.\n\n"
    "AcmeLearn is India's No. 1 learning app."
)
CLAIMS = [
    {
        "unit_id": "u1",
        "claim": "₹2,999 a year",
        "entity": "AcmeLearn Plus",
        "attribute": "annual price",
    },
    {"unit_id": "u2", "claim": "over 3 million registered learners", "entity": "AcmeLearn"},
    {"unit_id": "u3", "claim": "India's No. 1 learning app", "entity": "AcmeLearn"},
    {"unit_id": "u3", "claim": "the best app in the world", "entity": "AcmeLearn"},  # not a quote
    {"unit_id": "u9", "claim": "anything", "entity": "x"},  # unknown unit
]
VERDICTS = {
    "₹2,999 a year": ("supported", "F-014"),
    "over 3 million registered learners": ("contradicted", "F-003"),
    "India's No. 1 learning app": ("unsupported", None),
}


def run(claims=CLAIMS, verdicts=VERDICTS, policy=True):
    units = segment_text(TEXT)
    redacted = {u.unit_id: redact(u.text, use_presidio=False) for u in units}
    llm = ClaimsLLM(claims, verdicts)
    client = LLMClient([llm], SQLiteCache(":memory:"), MemoryCallLogger())
    lookup = lambda claim, vector: FACTS.get(claim.entity, [])  # noqa: E731
    result = run_claims(units, redacted, lookup=lookup, embedder=FakeEmbedder(), client=client,
                        claim_policy_enabled=policy)  # fmt: skip
    return result, llm


def test_verdicts_become_cited_candidates():
    result, llm = run()
    got = [
        (c.unit_id, c.source_type, c.source_id, c.severity, c.evidence) for c in result.candidates
    ]
    assert got == [
        ("u1", "fact", "F-014", "high", "₹2,999 a year"),  # supported by an expired fact
        ("u2", "fact", "F-003", "high", "over 3 million registered learners"),
        ("u3", "policy", CLAIM_POLICY_ID, "medium", "India's No. 1 learning app"),
    ]
    assert "expired on 2026-06-30" in result.candidates[0].explanation
    assert all(c.layer == "claims" and c.category == "claims" for c in result.candidates)
    assert result.candidates[1].supplied >= {"F-003", CLAIM_POLICY_ID}


def test_claims_that_are_not_real_quotes_are_dropped():
    result, _ = run()
    assert [(d[0]["claim"], reason) for d, reason in [(x, x[1]) for x in result.dropped]
            if reason == "claim_not_quoted"] == [("the best app in the world", "claim_not_quoted"),
                                                 ("anything", "claim_not_quoted")]  # fmt: skip
    assert len(result.claims) == 3


def test_contradicted_without_a_supplied_fact_is_dropped():
    verdicts = dict(VERDICTS)
    verdicts["over 3 million registered learners"] = ("contradicted", "F-777")
    result, _ = run(verdicts=verdicts)
    assert "F-777" not in {c.source_id for c in result.candidates}
    assert "no_fact_cited" in {reason for _, reason in result.dropped}


def test_supported_by_a_current_fact_and_policy_off_give_no_flags():
    verdicts = {k: ("supported", "F-003") for k in VERDICTS}
    verdicts["India's No. 1 learning app"] = ("unsupported", None)
    result, _ = run(verdicts=verdicts, policy=False)
    assert result.candidates == []


def test_verification_never_sees_expiry_dates():
    _, llm = run()
    assert all("2026-06-30" not in p for p in llm.verify_prompts)
