"""Scoring the review engine against the answer key (task 6.9). Pure functions, no I/O.

* A planted error is **caught** if some flag on the item has overlapping evidence (normalised;
  for a missing required phrase: a flag with empty evidence citing the expected rule).
* It is caught **with the right source** if that flag cites the expected source or one of
  its alternatives.
* A flag is **correct** (for precision) if it catches some planted error on the item.
* **Retrieval recall**: for expected semantic-rule flags, was the rule among those retrieved
  for the unit that holds the evidence?
* **Flags without a valid source** cite something that is not an approved rule, fact or
  policy of the brand. The target is 0.
"""

import re
from collections import defaultdict
from dataclasses import dataclass, field

from app.review.text import normalise


def words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9#&]+", text.lower()))


def similarity(a: str, b: str) -> float:
    wa, wb = words(a), words(b)
    return len(wa & wb) / max(1, len(wa | wb))


def map_rule_keys(key_rules: dict[str, str], extracted: dict[str, str]) -> dict[str, str]:
    """Answer-key rule key -> extracted rule code, by best word overlap (each code used once
    if possible). `extracted` maps rule code -> rule text (plus terms)."""
    pairs = sorted(
        ((similarity(text, rule_text), key, code)
         for key, text in key_rules.items() for code, rule_text in extracted.items()),
        reverse=True,
    )  # fmt: skip
    mapping: dict[str, str] = {}
    used: set[str] = set()
    for score, key, code in pairs:
        if key in mapping or code in used or score <= 0:
            continue
        mapping[key] = code
        used.add(code)
    for key in key_rules:  # fall back to the best code even if already used
        if key not in mapping:
            best = max(extracted, key=lambda c: similarity(key_rules[key], extracted[c]))
            mapping[key] = best
    return mapping


def evidence_overlaps(expected: str, actual: str) -> bool:
    e, a = normalise(expected), normalise(actual)
    if not e or not a:
        return False
    return e in a or a in e


@dataclass
class ExpectedFlag:
    evidence: str
    sources: set[str]  # resolved codes: primary + alternatives
    category: str
    source_type: str
    error: str


@dataclass
class ActualFlag:
    evidence: str
    source_id: str
    category: str
    layer: str
    unit_id: str


@dataclass
class ItemScore:
    item_id: str
    expected: list[ExpectedFlag]
    actual: list[ActualFlag]
    caught: list[bool] = field(default_factory=list)
    caught_with_source: list[bool] = field(default_factory=list)
    correct: list[bool] = field(default_factory=list)


def _matches(exp: ExpectedFlag, act: ActualFlag) -> bool:
    if exp.evidence == "":
        return act.evidence == "" and act.source_id in exp.sources
    return evidence_overlaps(exp.evidence, act.evidence)


def score_item(item_id: str, expected: list[ExpectedFlag], actual: list[ActualFlag]) -> ItemScore:
    s = ItemScore(item_id, expected, actual)
    for exp in expected:
        hits = [a for a in actual if _matches(exp, a)]
        s.caught.append(bool(hits))
        s.caught_with_source.append(any(a.source_id in exp.sources for a in hits))
    s.correct = [any(_matches(e, a) for e in expected) for a in actual]
    return s


@dataclass
class Totals:
    expected: int = 0
    caught: int = 0
    caught_with_source: int = 0
    flags: int = 0
    correct: int = 0

    @property
    def recall(self) -> float:
        return self.caught / self.expected if self.expected else 1.0

    @property
    def source_recall(self) -> float:
        return self.caught_with_source / self.expected if self.expected else 1.0

    @property
    def precision(self) -> float:
        return self.correct / self.flags if self.flags else 1.0


def totals(scores: list[ItemScore]) -> tuple[Totals, dict[str, Totals]]:
    """Overall totals and totals per category (expected category for recall, flag category
    for precision)."""
    overall = Totals()
    by_cat: dict[str, Totals] = defaultdict(Totals)
    for s in scores:
        for exp, caught, with_src in zip(s.expected, s.caught, s.caught_with_source, strict=True):
            for t in (overall, by_cat[exp.category]):
                t.expected += 1
                t.caught += caught
                t.caught_with_source += with_src
        for act, ok in zip(s.actual, s.correct, strict=True):
            for t in (overall, by_cat[act.category]):
                t.flags += 1
                t.correct += ok
    return overall, dict(sorted(by_cat.items()))
