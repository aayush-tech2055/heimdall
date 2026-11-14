import pytest
from pydantic import ValidationError

from app.models.flag import (
    CATEGORIES,
    LAYERS,
    SEVERITIES,
    SOURCE_TYPES,
    Flag,
    ImageLocation,
    PdfLocation,
    TextLocation,
    VideoLocation,
)

CONTRACT_EXAMPLE = {
    "unit_id": "u3",
    "source_type": "rule",
    "source_id": "R-012",
    "category": "claims",
    "severity": "high",
    "evidence": "India's No. 1 learning app",
    "explanation": "Ranking claim with no approved supporting fact.",
    "suggested_fix": "Trusted by over 2 million learners",
    "confidence": 0.86,
    "location": {
        "paragraph": 1,
        "char_start": 0,
        "char_end": 120,
        "evidence_start": 13,
        "evidence_end": 39,
    },
    "layer": "claims",
}


def test_contract_example_parses_and_round_trips():
    flag = Flag.model_validate(CONTRACT_EXAMPLE)
    assert isinstance(flag.location, TextLocation)
    assert flag.model_dump() == CONTRACT_EXAMPLE


def test_enums_match_locked_decisions():
    assert CATEGORIES == (
        "tone",
        "terminology",
        "messaging",
        "claims",
        "visuals",
        "accessibility",
        "legal",
        "other",
    )
    assert SEVERITIES == ("low", "medium", "high")
    assert LAYERS == ("rules", "guidelines", "claims", "visuals")
    assert SOURCE_TYPES == ("rule", "fact", "policy")


@pytest.mark.parametrize(
    ("location", "expected"),
    [
        ({"page": 2, "bbox": [10, 20, 200, 40]}, PdfLocation),
        ({"start": 12.0, "end": 27.5}, VideoLocation),
        ({"image_id": "img-1", "region": [0, 0, 50, 50]}, ImageLocation),
        ({"image_id": "img-1"}, ImageLocation),
    ],
)
def test_location_variants(location, expected):
    flag = Flag.model_validate({**CONTRACT_EXAMPLE, "location": location})
    assert isinstance(flag.location, expected)


def test_missing_required_phrase_has_empty_evidence():
    flag = Flag.model_validate({**CONTRACT_EXAMPLE, "evidence": "", "suggested_fix": None})
    assert flag.evidence == ""


@pytest.mark.parametrize(
    "override",
    [
        {"category": "pricing"},
        {"severity": "critical"},
        {"source_type": "guess"},
        {"layer": "llm"},
        {"confidence": 1.5},
        {"unit_id": ""},
        {"extra_field": 1},
        {
            "location": {
                "paragraph": 1,
                "char_start": 10,
                "char_end": 5,
                "evidence_start": 0,
                "evidence_end": 1,
            }
        },
        {"location": {"start": 10, "end": 5}},
        {"location": {"page": 0, "bbox": [0, 0, 1, 1]}},
    ],
)
def test_invalid_flags_rejected(override):
    with pytest.raises(ValidationError):
        Flag.model_validate({**CONTRACT_EXAMPLE, **override})
