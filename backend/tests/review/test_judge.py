"""Layer (b): retrieval per unit, batching and candidate shape (task 6.4)."""

import json
import re
from datetime import UTC, datetime

from app.llm.cache import SQLiteCache
from app.llm.call_log import MemoryCallLogger
from app.llm.client import LLMClient
from app.models.rules import Rule
from app.processing.redaction import redact
from app.review.judge import UNITS_PER_CALL, run_judge
from app.review.segment import segment_text
from tests.rag.fakes import FakeEmbedder


def rule(code, text, always_on=False, check_type="semantic", status="approved", category="tone"):
    return Rule(
        rule_code=code, category=category, text=text, source_doc="g", source_page=1,
        check_type=check_type, det_kind="banned_terms" if check_type == "deterministic" else None,
        terms=["x"] if check_type == "deterministic" else [], examples_bad=[], examples_good=[],
        always_on=always_on, status=status, updated_at=datetime.now(UTC),
    )  # fmt: skip


class JudgeLLM:
    """Flags 'embarrassing' under R-001; records which rules and units each call saw."""

    name, model = "fake", "fake-1"

    def __init__(self) -> None:
        self.calls: list[tuple[list[str], list[str]]] = []

    def complete(self, system: str, prompt: str) -> str:
        units = re.findall(r'<content unit_id="(u\d+)">\n(.*?)\n</content>', prompt, re.S)
        codes = re.findall(r"^\[(R-\d+)\]", prompt, re.M)
        self.calls.append(([u for u, _ in units], codes))
        flags = [
            {"unit_id": u, "rule_code": "R-001", "severity": "medium", "evidence": "embarrassing",
             "explanation": "Shames learners.", "suggested_fix": "tricky", "confidence": 0.9}
            for u, text in units if "embarrassing" in text
        ]  # fmt: skip
        return json.dumps({"flags": flags})


def run(text, rules, search):
    units = segment_text(text)
    redacted = {u.unit_id: redact(u.text, use_presidio=False) for u in units}
    llm = JudgeLLM()
    client = LLMClient([llm], SQLiteCache(":memory:"), MemoryCallLogger())
    result = run_judge(
        units, redacted, rules, search=search, embedder=FakeEmbedder(), client=client
    )
    return result, llm


def test_retrieval_adds_always_on_rules_and_skips_deterministic_or_unapproved():
    rules = [
        rule("R-001", "Be warm."),
        rule("R-002", "Use you.", always_on=True),
        rule("R-003", "Banned words.", check_type="deterministic"),
        rule("R-004", "Pending.", status="pending"),
    ]
    search = lambda text, vec, k: ["R-003", "R-004", "R-001"]  # noqa: E731
    result, llm = run("That is embarrassing.", rules, search)
    assert result.retrieved == {"u1": ["R-001", "R-002"]}
    assert llm.calls == [(["u1"], ["R-001", "R-002"])]
    (flag,) = result.candidates
    assert (flag.source_id, flag.category, flag.layer) == ("R-001", "tone", "guidelines")
    assert flag.supplied == frozenset({"R-001", "R-002"})


def test_units_are_batched_with_the_union_of_their_rules():
    text = "\n\n".join(f"Paragraph {i}." for i in range(10))
    rules = [rule(f"R-{i:03d}", f"Rule {i}.") for i in range(1, 11)]
    search = lambda text, vec, k: [f"R-{int(text.split()[1][:-1]) + 1:03d}"]  # noqa: E731
    result, llm = run(text, rules, search)
    assert [len(units) for units, _ in llm.calls] == [UNITS_PER_CALL, UNITS_PER_CALL, 2]
    assert llm.calls[0][1] == ["R-001", "R-002", "R-003", "R-004"]
    assert result.candidates == []


def test_units_reach_the_judge_redacted():
    rules = [rule("R-001", "Be warm.")]
    seen = []
    result, llm = run("Mail me at a@b.co, that is embarrassing.", rules,
                      lambda text, vec, k: seen.append(text) or ["R-001"])  # fmt: skip
    assert seen == ["Mail me at [EMAIL], that is embarrassing."]


def test_no_semantic_rules_means_no_calls():
    result, llm = run("Anything.", [rule("R-003", "x", check_type="deterministic")], lambda *a: [])
    assert result.candidates == [] and llm.calls == []
