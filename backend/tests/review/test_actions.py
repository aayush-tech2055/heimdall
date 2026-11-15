"""Applying fixes to the text (task 7.2)."""

from uuid import uuid4

from app.review.actions import (
    FixCandidate,
    apply_fix,
    apply_fixes,
    apply_fixes_mapped,
    choose_fixes,
    map_position,
)


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


def test_inserts_at_the_same_point_are_all_added_but_not_inside_a_replacement():
    end_insert, other_insert = cand(10, 10, "T&Cs apply."), cand(10, 10, "Results vary.")
    inside = cand(5, 5, "x")
    replace = cand(2, 8, "y", "high")
    chosen, skipped = choose_fixes([end_insert, other_insert, inside, replace])
    assert {c.id for c in skipped} == {inside.id}
    edge = cand(8, 8, "z")
    chosen, skipped = choose_fixes([replace, edge])
    assert not skipped
    text = "Buy today."
    out = apply_fixes(text, [cand(10, 10, "T&Cs apply."), cand(10, 10, "Results vary.")])
    assert out == "Buy today. T&Cs apply. Results vary."


def test_positions_move_to_the_new_text_after_fixes():
    text = "A cheap course. Never cheap. End"
    new, edits = apply_fixes_mapped(text, [cand(2, 7, "low-cost"), cand(32, 32, "T&Cs apply.")])
    assert new == "A low-cost course. Never cheap. End T&Cs apply."
    # The second "cheap" (22-27) moves right by 3; its slice still reads "cheap".
    s, e = map_position(22, edits), map_position(27, edits, is_end=True)
    assert new[s:e] == "cheap"
    # A span ending where text is inserted does not swallow the insertion.
    assert new[map_position(29, edits) : map_position(32, edits, is_end=True)] == "End"
    # The replaced span's new place is recorded on its edit.
    first = edits[0]
    assert new[first.new_start : first.new_start + first.length] == "low-cost"


def test_moved_locations_keep_end_after_start():
    from app.review.actions import _move_location

    text = "Buy today."
    _, edits = apply_fixes_mapped(text, [cand(10, 10, "T&Cs apply.")])
    # Another missing-phrase flag at the same point moves past the insertion, still empty.
    loc = _move_location({"char_start": 0, "char_end": 10, "evidence_start": 10,
                          "evidence_end": 10}, edits)  # fmt: skip
    assert loc["evidence_start"] == loc["evidence_end"] == 22
    # The unit grows to include the inserted line.
    assert (loc["char_start"], loc["char_end"]) == (0, 22)
