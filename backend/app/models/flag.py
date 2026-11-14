"""The flag contract (frozen on day one).

Every layer of the review engine produces `Flag` objects, and the frontend renders them.
This model must stay identical to `frontend/src/types/flag.ts`.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SourceType = Literal["rule", "fact", "policy"]
Category = Literal[
    "tone", "terminology", "messaging", "claims", "visuals", "accessibility", "legal", "other"
]
Severity = Literal["low", "medium", "high"]
Layer = Literal["rules", "guidelines", "claims", "visuals"]

CATEGORIES: tuple[str, ...] = Category.__args__
SEVERITIES: tuple[str, ...] = Severity.__args__
LAYERS: tuple[str, ...] = Layer.__args__
SOURCE_TYPES: tuple[str, ...] = SourceType.__args__

BBox = tuple[float, float, float, float]
"""A box as (x0, y0, x1, y1) in page or image coordinates."""


class _Location(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TextLocation(_Location):
    """Text content: paragraph number and character spans within the full text."""

    paragraph: int = Field(ge=0)
    char_start: int = Field(ge=0)
    char_end: int = Field(ge=0)
    evidence_start: int = Field(ge=0)
    evidence_end: int = Field(ge=0)

    @model_validator(mode="after")
    def _spans_ordered(self) -> "TextLocation":
        if self.char_end < self.char_start:
            raise ValueError("char_end must be >= char_start")
        if self.evidence_end < self.evidence_start:
            raise ValueError("evidence_end must be >= evidence_start")
        return self


class PdfLocation(_Location):
    """PDF content: 1-based page number and a bounding box on that page."""

    page: int = Field(ge=1)
    bbox: BBox


class VideoLocation(_Location):
    """Video content: start and end in seconds."""

    start: float = Field(ge=0)
    end: float = Field(ge=0)

    @model_validator(mode="after")
    def _ordered(self) -> "VideoLocation":
        if self.end < self.start:
            raise ValueError("end must be >= start")
        return self


class ImageLocation(_Location):
    """Image content: which image, and an optional region on it."""

    image_id: str
    region: BBox | None = None


Location = TextLocation | PdfLocation | VideoLocation | ImageLocation


class Flag(BaseModel):
    """One issue found in one review unit, citing exactly one source."""

    model_config = ConfigDict(extra="forbid")

    unit_id: str = Field(min_length=1)
    source_type: SourceType
    source_id: str = Field(min_length=1, description="Rule code (R-012), fact code or SYS-… id")
    category: Category
    severity: Severity
    evidence: str = Field(description="Exact quote from the content; '' for a missing phrase")
    explanation: str = Field(min_length=1)
    suggested_fix: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    location: Location
    layer: Layer
