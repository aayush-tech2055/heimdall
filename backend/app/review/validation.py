"""Citation validation (task 6.6, decisions 1 and 20). Plain code, never a model.

A candidate is dropped, with the reason kept, if:
* its unit is unknown                                   -> "unknown_unit"
* its source was not supplied to the model              -> "source_not_supplied"
* its evidence is not in the unit (case, whitespace and
  curly/straight quotes ignored; AI evidence is searched
  in the redacted unit the model saw)                    -> "evidence_not_found"
* it matches an approved exception (same source,
  overlapping evidence)                                  -> "approved_exception"
* an AI flag whose evidence lies inside text the brand
  requires (an approved required phrase, e.g. its own
  disclaimer)                                            -> "brand_required_text"
* it repeats (unit, source, normalised evidence)         -> "duplicate"
* it does not fit the flag contract                      -> "invalid_flag"
Kept candidates become `Flag`s with absolute evidence offsets in the original text.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from pydantic import ValidationError

from app.models.flag import Flag, ImageLocation, PdfLocation, TextLocation
from app.processing.redaction import Redacted
from app.review.candidates import Candidate
from app.review.segment import Unit
from app.review.text import find_normalised, normalise, overlaps

SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}


@dataclass(frozen=True)
class ApprovedException:
    source_id: str
    evidence: str


@dataclass
class ValidationResult:
    flags: list[Flag] = field(default_factory=list)
    dropped: list[tuple[dict, str]] = field(default_factory=list)


def _locate(candidate: Candidate, unit: Unit, redacted: Redacted | None) -> tuple[int, int] | None:
    """The evidence span in the ORIGINAL unit text, or None if it is not there."""
    if candidate.span is not None:
        return candidate.span
    if not candidate.evidence.strip():
        return None
    if redacted is not None:
        found = find_normalised(redacted.text, candidate.evidence)
        return redacted.to_original(*found) if found else None
    return find_normalised(unit.text, candidate.evidence)


def _location(
    unit: Unit,
    span: tuple[int, int],
    c: Candidate,
    evidence_box: Callable[[str, int, int], tuple] | None,
) -> tuple[TextLocation | PdfLocation | ImageLocation, tuple]:
    """The flag location for the unit's format, and a sort key (reading order)."""
    loc = unit.location
    if "image_id" in loc:
        region = c.extra.get("region")
        region = tuple(region) if region and len(region) == 4 else None
        return ImageLocation(image_id=loc["image_id"], region=region), (unit.position, 0)
    if "page" in loc:
        box = evidence_box(unit.unit_id, *span) if evidence_box and span[1] > span[0] else None
        return PdfLocation(page=loc["page"], bbox=tuple(box or loc["bbox"])), (
            unit.position,
            span[0],
        )
    return TextLocation(
        paragraph=loc["paragraph"], char_start=unit.char_start, char_end=unit.char_end,
        evidence_start=unit.char_start + span[0], evidence_end=unit.char_start + span[1],
    ), (unit.char_start + span[0], 0)  # fmt: skip


def _phrase_spans(text: str, phrases: list[str]) -> list[tuple[int, int]]:
    """Every lenient occurrence of each phrase in `text`."""
    spans: list[tuple[int, int]] = []
    for phrase in phrases:
        start = 0
        while (found := find_normalised(text, phrase, start)) is not None:
            spans.append(found)
            start = found[1]
    return spans


def validate(
    candidates: list[Candidate],
    units: list[Unit],
    redacted: dict[str, Redacted],
    exceptions: list[ApprovedException] = (),
    required_phrases: list[str] = (),
    evidence_box: Callable[[str, int, int], tuple] | None = None,
) -> ValidationResult:
    """Text units get character offsets; PDF units ({page, bbox}) get the evidence's box on
    the page via `evidence_box`; image units ({image_id}) take visual flags, whose evidence is
    a region description and is not matched against text."""
    result = ValidationResult()
    by_id = {u.unit_id: u for u in units}
    protected = {u.unit_id: _phrase_spans(u.text, required_phrases) for u in units}
    seen: set[tuple[str, str, str]] = set()
    kept: list[tuple[Flag, int]] = []

    for c in candidates:
        unit = by_id.get(c.unit_id)
        if unit is None:
            result.dropped.append((c.payload(), "unknown_unit"))
            continue
        if c.supplied is not None and c.source_id not in c.supplied:
            result.dropped.append((c.payload(), "source_not_supplied"))
            continue
        is_image = "image_id" in unit.location
        if is_image:
            if c.layer != "visuals" or not c.evidence.strip():
                result.dropped.append((c.payload(), "evidence_not_found"))
                continue
            span, evidence = (0, 0), c.evidence.strip()
        elif c.allow_empty_evidence and not c.evidence:
            span = c.span or (len(unit.text), len(unit.text))
            evidence = ""
        else:
            span = _locate(c, unit, redacted.get(c.unit_id))
            if span is None:
                result.dropped.append((c.payload(), "evidence_not_found"))
                continue
            evidence = unit.text[span[0] : span[1]] if span[1] > span[0] else ""
        if (
            c.supplied is not None
            and evidence
            and not is_image
            and any(s <= span[0] and span[1] <= e for s, e in protected[c.unit_id])
        ):
            result.dropped.append((c.payload(), "brand_required_text"))
            continue
        if evidence and any(
            e.source_id == c.source_id and overlaps(e.evidence, evidence) for e in exceptions
        ):
            result.dropped.append((c.payload(), "approved_exception"))
            continue
        key = (c.unit_id, c.source_id, normalise(evidence))
        if key in seen:
            result.dropped.append((c.payload(), "duplicate"))
            continue
        seen.add(key)
        try:
            location, order = _location(unit, span, c, evidence_box)
            flag = Flag(
                unit_id=c.unit_id, source_type=c.source_type, source_id=c.source_id,
                category=c.category, severity=c.severity, evidence=evidence,
                explanation=c.explanation, suggested_fix=c.suggested_fix,
                confidence=max(0.0, min(1.0, c.confidence)), layer=c.layer, location=location,
            )  # fmt: skip
        except (ValidationError, ValueError) as exc:
            result.dropped.append((c.payload() | {"error": str(exc)[:300]}, "invalid_flag"))
            continue
        kept.append((flag, order))

    kept.sort(key=lambda item: (*item[1], SEVERITY_RANK[item[0].severity]))
    result.flags = [flag for flag, _ in kept]
    return result
