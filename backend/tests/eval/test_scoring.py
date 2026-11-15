"""Evaluation scoring (task 6.9)."""

from eval.scoring import (
    ActualFlag,
    ExpectedFlag,
    evidence_overlaps,
    map_rule_keys,
    score_item,
    totals,
)


def exp(evidence, sources, category="terminology"):
    return ExpectedFlag(evidence, set(sources), category, "rule", "e")


def act(evidence, source, category="terminology"):
    return ActualFlag(evidence, source, category, "rules", "u1")


def test_rule_keys_map_to_the_best_matching_extracted_rule():
    key_rules = {"BANNED": 'Never use these words: "cheap", "hack".', "TONE": "Use a warm tone."}
    extracted = {"R-001": "Use a warm, encouraging tone.", "R-002": "Never use: cheap hack"}
    assert map_rule_keys(key_rules, extracted) == {"BANNED": "R-002", "TONE": "R-001"}


def test_evidence_overlap_is_lenient_and_containment_based():
    assert evidence_overlaps("4.9 stars", "rate the app 4.9 STARS")
    assert evidence_overlaps("Honestly, that’s embarrassing.", "that's embarrassing")
    assert not evidence_overlaps("cheap", "") and not evidence_overlaps("cheap", "hack")


def test_item_scoring_recall_source_and_precision():
    s = score_item(
        "acme-22",
        [exp("hack", ["R-006"]), exp("", ["R-025"], "legal")],
        [act("hack", "R-006"), act("", "R-025", "legal"), act("Watch the lesson", "R-002", "tone")],
    )
    assert s.caught == [True, True] and s.caught_with_source == [True, True]
    assert s.correct == [True, True, False]


def test_caught_with_the_wrong_source_and_missing_phrase_needs_the_right_rule():
    s = score_item("x", [exp("3 million", ["F-003"], "claims"), exp("", ["R-025"], "legal")],
                   [act("over 3 million learners", "SYS-CLAIM-001", "claims"), act("", "R-999", "legal")])  # fmt: skip
    assert s.caught == [True, False] and s.caught_with_source == [False, False]


def test_totals_overall_and_by_category():
    a = score_item("a", [exp("cheap", ["R-1"])], [act("cheap", "R-1")])
    b = score_item("b", [exp("4.9", ["F-5"], "claims")], [act("x", "R-2", "tone")])
    clean = score_item("c", [], [])
    overall, by_cat = totals([a, b, clean])
    assert (overall.expected, overall.caught, overall.flags, overall.correct) == (2, 1, 2, 1)
    assert overall.recall == 0.5 and overall.precision == 0.5
    assert by_cat["claims"].recall == 0.0 and by_cat["tone"].precision == 0.0
    assert by_cat["terminology"].recall == 1.0
