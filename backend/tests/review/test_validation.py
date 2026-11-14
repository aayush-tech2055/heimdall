"""Citation validation (task 6.6): no source, no flag."""

from app.processing.redaction import redact
from app.review.candidates import Candidate
from app.review.segment import segment_text
from app.review.validation import ApprovedException, validate

TEXT = "Intro line.\n\nIt’s honestly “embarrassing”, mail a@b.co today.\n\nAll good."
UNITS = segment_text(TEXT)
REDACTED = {u.unit_id: redact(u.text, use_presidio=False) for u in UNITS}


def cand(evidence, unit_id="u2", source_id="R-001", supplied=frozenset({"R-001"}), **kw):
    base = dict(unit_id=unit_id, source_type="rule", source_id=source_id, category="tone",
                severity="medium", evidence=evidence, explanation="Why.", suggested_fix=None,
                confidence=0.9, layer="guidelines", supplied=supplied)  # fmt: skip
    return Candidate(**(base | kw))


def run(cands, exceptions=()):
    return validate(cands, UNITS, REDACTED, list(exceptions))


def reasons(result):
    return [reason for _, reason in result.dropped]


def test_valid_flag_gets_absolute_offsets_in_the_original_text():
    (flag,) = run([cand('"embarrassing"')]).flags  # straight quotes match curly ones
    assert flag.evidence == "“embarrassing”"
    loc = flag.location
    assert TEXT[loc.evidence_start : loc.evidence_end] == "“embarrassing”"
    assert TEXT[loc.char_start : loc.char_end] == UNITS[1].text
    assert loc.paragraph == 2


def test_evidence_quoted_from_redacted_text_maps_back_to_the_original():
    (flag,) = run([cand("mail [EMAIL] today")]).flags
    assert flag.evidence == "mail a@b.co today"
    assert TEXT[flag.location.evidence_start : flag.location.evidence_end] == "mail a@b.co today"


def test_drop_reasons():
    result = run([
        cand("embarrassing", unit_id="u9"),
        cand("embarrassing", source_id="R-404"),
        cand("disgraceful"),
        cand(""),
        cand("embarrassing", severity="critical"),
    ])  # fmt: skip
    assert result.flags == []
    assert reasons(result) == [
        "unknown_unit", "source_not_supplied", "evidence_not_found", "evidence_not_found",
        "invalid_flag",
    ]  # fmt: skip


def test_duplicates_by_unit_source_and_normalised_evidence():
    other = cand("embarrassing", source_id="R-002", supplied=frozenset({"R-002"}))
    result = run([cand("embarrassing"), cand("EMBARRASSING"), other])
    assert [f.source_id for f in result.flags] == ["R-001", "R-002"]
    assert reasons(result) == ["duplicate"]


def test_approved_exception_with_overlapping_evidence_is_dropped():
    exceptions = [
        ApprovedException("R-001", "honestly “embarrassing”"),
        ApprovedException("R-002", "embarrassing"),
    ]
    result = run([cand("embarrassing")], exceptions)
    assert result.flags == [] and reasons(result) == ["approved_exception"]


def test_code_flags_need_no_supplied_set_and_missing_phrase_keeps_empty_evidence():
    missing = cand(
        "", unit_id="u3", source_id="R-009", supplied=None, layer="rules",
        allow_empty_evidence=True, span=(9, 9), category="legal", severity="high",
    )  # fmt: skip
    banned = cand(
        "Intro", unit_id="u1", source_id="R-008", supplied=None, layer="rules", span=(0, 5)
    )
    flags = run([missing, banned]).flags
    assert [(f.source_id, f.evidence) for f in flags] == [("R-008", "Intro"), ("R-009", "")]
    assert flags[1].location.evidence_start == flags[1].location.char_end


def test_flags_are_sorted_by_position_then_severity():
    flags = run([
        cand("today", severity="low"),
        cand("embarrassing", source_id="R-002", supplied=frozenset({"R-002"}), severity="low"),
        cand("embarrassing", severity="high"),
    ]).flags  # fmt: skip
    assert [(f.evidence, f.severity) for f in flags] == [
        ("embarrassing", "high"), ("embarrassing", "low"), ("today", "low"),
    ]  # fmt: skip


def test_ai_flags_inside_brand_required_text_are_dropped_but_code_flags_are_kept():
    text = "Great beans. Contains caffeine. Not recommended for children."
    units = segment_text(text)
    red = {u.unit_id: redact(u.text, use_presidio=False) for u in units}
    phrase = ["Contains caffeine. Not recommended for children."]
    ai_inside = cand("Contains caffeine", unit_id="u1")
    ai_outside = cand("Great beans", unit_id="u1")
    code_inside = cand("caffeine", unit_id="u1", supplied=None, layer="rules", span=(22, 30))
    result = validate([ai_inside, ai_outside, code_inside], units, red, [], phrase)
    assert [f.evidence for f in result.flags] == ["Great beans", "caffeine"]
    assert [r for _, r in result.dropped] == ["brand_required_text"]
