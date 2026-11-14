"""Guideline verification logic with a fake LLM (task 4.4)."""

import json
import re
from datetime import UTC, datetime

from app.llm.cache import SQLiteCache
from app.llm.call_log import MemoryCallLogger
from app.llm.client import LLMClient
from app.models.rules import Rule
from app.rag.verification import PAIRS_PER_CALL, missing_categories, verify_rules


def rule(code, category="tone", text="Be warm.", check_type="semantic", status="pending"):
    return Rule(
        rule_code=code, category=category, text=text, source_doc="g.pdf", source_page=1,
        check_type=check_type, det_kind="banned_terms" if check_type == "deterministic" else None,
        terms=["x"] if check_type == "deterministic" else [], examples_bad=[], examples_good=[],
        always_on=False, status=status, updated_at=datetime.now(UTC),
    )  # fmt: skip


class ScriptedLLM:
    """Pair calls: label by rule codes; vagueness calls: vague if 'on-brand' in the text."""

    name, model = "fake", "fake-1"

    def __init__(self, labels: dict[frozenset, str]) -> None:
        self.labels = labels
        self.pair_calls = 0
        self.vague_calls = 0

    def complete(self, system: str, prompt: str) -> str:
        if "<pair id=" in prompt:
            self.pair_calls += 1
            results = []
            for pid, body in re.findall(r'<pair id="(p\d+)">\n(.*?)</pair>', prompt, re.S):
                codes = frozenset(re.findall(r"\[(R-\d+)\]", body))
                results.append({"pair_id": pid, "label": self.labels.get(codes, "compatible"),
                                "explanation": "because"})  # fmt: skip
            results.append({"pair_id": "p999", "label": "duplicate", "explanation": "invented"})
            return json.dumps({"results": results})
        self.vague_calls += 1
        rules = re.findall(r"\[(R-\d+)\] \(\w+\) (.*)", prompt)
        results = [
            {"rule_code": c, "vague": "on-brand" in t, "reason": "r",
             "suggested_rewrite": "Use concrete words." if "on-brand" in t else None}
            for c, t in rules
        ]  # fmt: skip
        results.append({"rule_code": "R-999", "vague": True, "reason": "invented code"})
        return json.dumps({"results": results})


def run(rules, pairs, labels=None):
    llm = ScriptedLLM(labels or {})
    client = LLMClient([llm], SQLiteCache(":memory:"), MemoryCallLogger())
    return verify_rules(rules, pairs, client), llm


def test_report_classifies_pairs_flags_vague_rules_and_ignores_invented_ids():
    rules = [
        rule("R-001", "tone", "Be warm."),
        rule("R-002", "tone", "Keep it on-brand."),
        rule("R-003", "terminology", "Never say cheap.", "deterministic"),
        rule("R-004", "terminology", "Do not call things cheap."),
        rule("R-005", "claims", "Always state the price."),
        rule("R-006", "legal", "Never mention prices in captions."),
    ]
    pairs = [("R-003", "R-004", 0.85), ("R-005", "R-006", 0.80), ("R-001", "R-002", 0.77)]
    labels = {frozenset({"R-003", "R-004"}): "duplicate",
              frozenset({"R-005", "R-006"}): "contradiction"}  # fmt: skip
    report, llm = run(rules, pairs, labels)

    assert [(d.rule_a, d.rule_b, d.similarity) for d in report.duplicates] == [
        ("R-003", "R-004", 0.85)
    ]
    assert [(c.rule_a, c.rule_b) for c in report.contradictions] == [("R-005", "R-006")]
    assert [(v.rule_code, v.suggested_rewrite) for v in report.vague] == [
        ("R-002", "Use concrete words.")
    ]
    assert report.missing_categories == ["visuals", "accessibility"]
    assert (report.pairs_checked, report.rules_checked) == (3, 6)
    assert llm.pair_calls == 1


def test_deterministic_and_rejected_rules_are_not_checked_for_vagueness():
    rules = [rule("R-001", text="Keep it on-brand.", status="rejected"),
             rule("R-002", text="on-brand words", check_type="deterministic")]  # fmt: skip
    report, _ = run(rules, [("R-001", "R-002", 0.9)])
    assert report.vague == [] and report.pairs_checked == 0 and report.rules_checked == 1


def test_pairs_are_sent_in_batches():
    rules = [rule(f"R-{i:03d}") for i in range(1, 8)]
    pairs = [(a.rule_code, b.rule_code, 0.8) for i, a in enumerate(rules) for b in rules[i + 1 :]]
    report, llm = run(rules, pairs)
    assert report.pairs_checked == 21
    assert llm.pair_calls == -(-21 // PAIRS_PER_CALL)


def test_missing_categories_ignores_rejected_rules():
    rules = [rule("R-001", c) for c in ("tone", "terminology", "claims", "visuals", "legal")]
    rules.append(rule("R-006", "accessibility", status="rejected"))
    assert missing_categories(rules) == ["accessibility"]
