"""Layer (a): deterministic rules (task 6.3) and lenient matching helpers."""

from datetime import UTC, datetime

from app.models.rules import Rule
from app.review.rules_engine import check_deterministic
from app.review.segment import segment_text
from app.review.text import find_normalised, normalise, overlaps


def rule(code, kind, terms, category="terminology", status="approved"):
    return Rule(
        rule_code=code, category=category, text="Rule text.", source_doc="g", source_page=1,
        check_type="deterministic", det_kind=kind, terms=terms, examples_bad=[],
        examples_good=[], always_on=False, status=status, updated_at=datetime.now(UTC),
    )  # fmt: skip


def test_banned_terms_flag_every_whole_word_occurrence_with_spans():
    units = segment_text("Cheap courses, cheap!\n\nNot cheapest. A hack-a-thon? No hack.")
    flags = check_deterministic(units, [rule("R-001", "banned_terms", ["cheap", "hack"])])
    found = [(f.unit_id, f.evidence, f.span) for f in flags]
    assert found == [
        ("u1", "Cheap", (0, 5)),
        ("u1", "cheap", (15, 20)),
        ("u2", "hack", (16, 20)),  # "hack-a-thon": hyphen is a word boundary
        ("u2", "hack", (32, 36)),
    ]
    assert all(f.layer == "rules" and f.confidence == 1.0 for f in flags)
    assert "cheapest" not in {f.evidence.lower() for f in flags}


def test_multi_word_terms_match_across_whitespace_and_case():
    units = segment_text("Our Premium\n  Plan is great.")
    flags = check_deterministic(units, [rule("R-002", "banned_terms", ["premium plan"])])
    assert [f.evidence for f in flags] == ["Premium\n  Plan"]


def test_required_phrase_checked_across_the_whole_document():
    units = segment_text("Para one.\n\nPara two ends with t&cs   APPLY.")
    assert (
        check_deterministic(units, [rule("R-003", "required_phrase", ["T&Cs apply."], "legal")])
        == []
    )

    units = segment_text("Para one.\n\nPara two.")
    (flag,) = check_deterministic(
        units, [rule("R-003", "required_phrase", ["T&Cs apply."], "legal")]
    )
    assert (flag.unit_id, flag.evidence, flag.allow_empty_evidence) == ("u2", "", True)
    assert flag.severity == "high" and flag.suggested_fix == "T&Cs apply."


def test_curly_quotes_count_as_straight_for_required_phrases():
    units = segment_text("Don’t forget: “Contains caffeine.”")
    assert (
        check_deterministic(units, [rule("R-004", "required_phrase", ['"Contains caffeine."'])])
        == []
    )


def test_only_approved_deterministic_rules_run():
    units = segment_text("cheap")
    assert (
        check_deterministic(units, [rule("R-001", "banned_terms", ["cheap"], status="pending")])
        == []
    )


def test_lenient_matching_helpers():
    assert normalise("  It’s   “Fine” \n") == 'it\'s "fine"'
    text = "Learners rate the app 4.9 stars."
    assert find_normalised(text, "RATE  the APP") == (9, 21)
    assert find_normalised(text, "5 stars") is None
    assert overlaps("4.9 stars", "rate the app 4.9 STARS") and not overlaps("a", "")
