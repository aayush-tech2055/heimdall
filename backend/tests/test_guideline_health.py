"""Guideline health rule (task 13.2): >= 40% dismissed with >= 5 flags is probably unclear."""

from app.api.insights import health_rows


def test_probably_unclear_needs_both_the_rate_and_enough_flags():
    rows = [
        ("R-001", "Be on-brand.", "tone", 5, 2),  # 40% of 5: unclear
        ("R-002", "Never say cheap.", "terminology", 20, 1),
        ("R-003", "Be exciting.", "tone", 4, 4),  # 100% but only 4 flags
        ("SYS-CLAIM-001", None, None, 10, 5),
    ]  # policies count too
    notes = {"R-001": ["Too vague", "too  vague", "It is our tagline"]}
    out = health_rows(rows, notes)
    assert [(h.source_id, h.probably_unclear) for h in out] == [
        ("SYS-CLAIM-001", True),
        ("R-001", True),
        ("R-003", False),
        ("R-002", False),
    ]
    assert out[1].top_reasons == ["too  vague", "It is our tagline"]  # most common first
    assert out[1].dismissal_rate == 0.4
