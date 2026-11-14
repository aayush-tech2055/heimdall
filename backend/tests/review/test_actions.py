"""Applying fixes to the text (task 7.2)."""

from app.review.actions import apply_fix


def test_replace_the_evidence_span():
    assert apply_fix("A cheap course.", 2, 7, "affordable") == "A affordable course."


def test_missing_phrase_is_inserted_with_a_space():
    assert apply_fix("Start today.", 12, 12, "T&Cs apply.") == "Start today. T&Cs apply."
    assert apply_fix("Start today.\n", 13, 13, "T&Cs apply.") == "Start today.\nT&Cs apply."
    assert apply_fix("", 0, 0, "T&Cs apply.") == "T&Cs apply."
