"""Citation validation (task 6.6, decisions 1 and 20). Plain code, never a model.

A candidate is dropped, with the reason kept, if:
* its unit is unknown                                   -> "unknown_unit"
* its source was not supplied to the model              -> "source_not_supplied"
* its evidence is not in the unit (case, whitespace and
  curly/straight quotes ignored; AI evidence is searched
  in the redacted unit the model saw)                    -> "evidence_not_found"
* it matches an approved exception (same source,
  overlapping evidence)                                  -> "approved_exception"
* it repeats (unit, source, normalised evidence)         -> "duplicate"
* it does not fit the flag contract                      -> "invalid_flag"
Kept candidates become `Flag`s with absolute evidence offsets in the original text.
"""

from dataclasses import dataclass, field

from pydantic import ValidationError

from app.models.flag import Flag, TextLocation
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


def validate(
    candidates: list[Candidate],
    units: list[Unit],
    redacted: dict[str, Redacted],
    exceptions: list[ApprovedException] = (),
) -> ValidationResult:
    result = ValidationResult()
    by_id = {u.unit_id: u for u in units}
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
        if c.allow_empty_evidence and not c.evidence:
            span = c.span or (len(unit.text), len(unit.text))
        else:
            span = _locate(c, unit, redacted.get(c.unit_id))
            if span is None:
                result.dropped.append((c.payload(), "evidence_not_found"))
                continue
        evidence = unit.text[span[0] : span[1]] if span[1] > span[0] else ""
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
            flag = Flag(
                unit_id=c.unit_id, source_type=c.source_type, source_id=c.source_id,
                category=c.category, severity=c.severity, evidence=evidence,
                explanation=c.explanation, suggested_fix=c.suggested_fix,
                confidence=max(0.0, min(1.0, c.confidence)), layer=c.layer,
                location=TextLocation(
                    paragraph=unit.location["paragraph"], char_start=unit.char_start,
                    char_end=unit.char_end, evidence_start=unit.char_start + span[0],
                    evidence_end=unit.char_start + span[1],
                ),
            )  # fmt: skip
        except ValidationError as exc:
            result.dropped.append((c.payload() | {"error": str(exc)[:300]}, "invalid_flag"))
            continue
        kept.append((flag, unit.char_start + span[0]))

    kept.sort(key=lambda item: (item[1], SEVERITY_RANK[item[0].severity]))
    result.flags = [flag for flag, _ in kept]
    return result
