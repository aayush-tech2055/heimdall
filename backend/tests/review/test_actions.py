"""Applying fixes to the text (task 7.2)."""

from uuid import uuid4

from app.review.actions import FixCandidate, apply_fix, apply_fixes, choose_fixes


def test_replace_the_evidence_span():
    assert apply_fix("A cheap course.", 2, 7, "affordable") == "A affordable course."


def test_missing_phrase_is_inserted_with_a_space():
    assert apply_fix("Start today.", 12, 12, "T&Cs apply.") == "Start today. T&Cs apply."
    assert apply_fix("Start today.\n", 13, 13, "T&Cs apply.") == "Start today.\nT&Cs apply."
    assert apply_fix("", 0, 0, "T&Cs apply.") == "T&Cs apply."


# --- accepting several fixes at once ---------------------------------------------------------


def cand(start: int, end: int, fix: str, severity: str = "medium") -> FixCandidate:
    return FixCandidate(uuid4(), severity, start, end, fix)


def test_apply_fixes_works_back_to_front_so_offsets_stay_valid():
    text = "A cheap hack for dummies."
    fixes = [cand(2, 7, "low-cost"), cand(8, 12, "tip"), cand(17, 24, "everyone")]
    assert apply_fixes(text, fixes) == "A low-cost tip for everyone."


def test_apply_fixes_with_an_insert_at_the_end_and_a_replacement():
    text = "Only cheap courses."
    out = apply_fixes(text, [cand(5, 10, "affordable"), cand(19, 19, "T&Cs apply.")])
    assert out == "Only affordable courses. T&Cs apply."


def test_overlapping_fixes_keep_the_most_severe_then_the_longest():
    low = cand(0, 5, "x", "low")
    high = cand(3, 9, "y", "high")
    medium_long = cand(10, 20, "z", "medium")
    medium_short = cand(12, 15, "w", "medium")
    apart = cand(25, 30, "v", "low")
    chosen, skipped = choose_fixes([low, high, medium_long, medium_short, apart])
    assert {c.id for c in chosen} == {high.id, medium_long.id, apart.id}
    assert {c.id for c in skipped} == {low.id, medium_short.id}


def test_identical_fixes_count_once_and_both_are_accepted():
    a, b = cand(2, 7, "affordable"), cand(2, 7, "affordable")
    chosen, skipped = choose_fixes([a, b])
    assert len(chosen) == 2 and not skipped
    assert apply_fixes("A cheap course.", chosen) == "A affordable course."


def test_inserts_clash_only_at_the_same_point_or_inside_a_replacement():
    end_insert, other_insert = cand(10, 10, "T&Cs apply."), cand(10, 10, "Results vary.")
    inside = cand(5, 5, "x")
    replace = cand(2, 8, "y", "high")
    chosen, skipped = choose_fixes([end_insert, other_insert, inside, replace])
    assert {c.id for c in skipped} == {other_insert.id, inside.id}
    edge = cand(8, 8, "z")
    chosen, skipped = choose_fixes([replace, edge])
    assert not skipped
