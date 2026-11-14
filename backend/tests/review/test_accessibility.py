"""Accessibility checks in code (task 8.3)."""

from datetime import UTC, datetime

import pytest

from app.models.rules import Rule
from app.processing.pdf_content import TextStyle
from app.review.accessibility import (
    check_alt_text,
    check_contrast,
    check_readability,
    contrast_ratio,
    count_syllables,
    reading_ease,
)
from app.review.segment import segment_text


def rule(code, text, category="accessibility"):
    return Rule(rule_code=code, category=category, text=text, source_doc="g", source_page=4,
                check_type="semantic", det_kind=None, terms=[], examples_bad=[], examples_good=[],
                always_on=False, status="approved", updated_at=datetime.now(UTC))  # fmt: skip


RULES = [
    rule("R-020", "Text must have a contrast ratio of at least 4.5:1."),
    rule("R-021", "Every image needs alt text that describes it."),
    rule("R-022", "Write so that a 14-year-old can follow: keep sentences under 25 words."),
]


def test_wcag_contrast_ratio():
    assert contrast_ratio((0, 0, 0)) == pytest.approx(21.0)
    assert contrast_ratio((255, 255, 255)) == pytest.approx(1.0)
    assert contrast_ratio((118, 118, 118)) == pytest.approx(4.54, abs=0.02)  # the AA boundary grey


def test_low_contrast_text_cites_the_brand_contrast_rule():
    styles = [TextStyle("u1", "Light grey text", (204, 204, 204), 11),
              TextStyle("u1", "Dark text", (17, 17, 17), 11),
              TextStyle("u2", "Big mid-grey heading", (120, 120, 120), 24)]  # fmt: skip
    flags = check_contrast(styles, RULES)
    assert [(f.unit_id, f.evidence, f.source_id) for f in flags] == [
        ("u1", "Light grey text", "R-020")
    ]
    assert "1.6:1" in flags[0].explanation


def test_alt_text_and_no_rule_means_no_check():
    assert [f.source_id for f in check_alt_text("img-1", None, RULES)] == ["R-021"]
    assert check_alt_text("img-1", "A latte on a wooden table", RULES) == []
    assert check_alt_text("img-1", None, [rule("R-001", "Be warm.", "tone")]) == []
    assert check_contrast([TextStyle("u1", "x", (230, 230, 230), 11)], []) == []


def test_reading_ease_and_syllables():
    assert count_syllables("cat") == 1 and count_syllables("course") == 1
    assert count_syllables("education") == 4 and count_syllables("table") == 2
    assert reading_ease("The cat sat on the mat. It was happy.") > 90
    hard = (
        "Notwithstanding considerable institutional heterogeneity, comprehensive "
        "organisational transformation necessitates multidimensional stakeholder alignment."
    )
    assert reading_ease(hard) < 0


def test_hard_units_are_flagged_with_their_hardest_sentence():
    easy = "You can learn to code. Start with one short lesson a day. It is fun and it is free to try today."
    hard = (
        "Learn to code today. Notwithstanding considerable institutional heterogeneity, comprehensive "
        "organisational transformation necessitates multidimensional stakeholder alignment across "
        "interdisciplinary programmes and departments."
    )
    flags = check_readability(segment_text(easy + "\n\n" + hard), RULES, target=60)
    assert [(f.unit_id, f.source_id, f.severity) for f in flags] == [("u2", "R-022", "low")]
    assert flags[0].evidence.startswith("Notwithstanding")
    assert check_readability(segment_text(hard), RULES, target=None) == []


def test_caption_checks_use_a_video_caption_rule_not_social_media_captions():
    from app.review.accessibility import check_captions, find_rule
    from app.review.segment import Unit

    social = rule("R-030", "Social media captions must not mention prices.", "legal")
    video = rule("R-031", "Every video needs captions that match what is said.")
    assert find_rule([social], "captions") is None
    assert find_rule([social, video], "captions") is video
    speech = [
        Unit(
            "s1",
            0,
            "Learn Python with AcmeLearn and build your first project today.",
            {"start": 0.0, "end": 6.0, "source": "speech"},
        )
    ]
    missing = check_captions(speech, None, [social, video])
    assert [(f.source_id, f.evidence, f.allow_empty_evidence) for f in missing] == [
        ("R-031", "", True)
    ]
    good = [(0.0, 6.0, "Learn Python with AcmeLearn and build your first project today.")]
    assert check_captions(speech, good, [video]) == []
    bad = [(0.0, 6.0, "Hello there.")]
    (flag,) = check_captions(speech, bad, [video])
    assert "cover only" in flag.explanation
    assert check_captions(speech, None, [social]) == []
