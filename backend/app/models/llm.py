"""What each model call must return (validated by `LLMClient.json`).

These schemas carry only what the model is trusted to decide. Rule codes, pages, status,
locations, layers and categories of judged flags are set in code (decisions 1, 8 and 20).
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.flag import Category, Severity


class _Out(BaseModel):
    model_config = ConfigDict(extra="ignore")


# --- Guidelines (tasks 4.2 and 4.4) --------------------------------------------------------


class ExtractedRule(_Out):
    category: Category
    text: str = Field(min_length=1, description="The rule as one testable instruction")
    check_type: Literal["deterministic", "semantic"] = "semantic"
    det_kind: Literal["banned_terms", "required_phrase"] | None = None
    terms: list[str] = Field(
        default_factory=list, description="Exact words for deterministic rules"
    )
    examples_bad: list[str] = Field(default_factory=list)
    examples_good: list[str] = Field(default_factory=list)
    always_on: bool = False


class RuleExtraction(_Out):
    rules: list[ExtractedRule]


class PairVerdict(_Out):
    pair_id: str
    label: Literal["duplicate", "contradiction", "compatible"]
    explanation: str = Field(min_length=1)


class PairChecks(_Out):
    results: list[PairVerdict]


class VagueRule(_Out):
    rule_code: str
    vague: bool
    reason: str
    suggested_rewrite: str | None = None


class VaguenessCheck(_Out):
    results: list[VagueRule]


# --- Review (tasks 6.4 and 6.5) -------------------------------------------------------------


class JudgedFlag(_Out):
    unit_id: str
    rule_code: str
    severity: Severity
    evidence: str = Field(description="Exact, shortest quote from the unit")
    explanation: str = Field(min_length=1)
    suggested_fix: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)


class JudgeOutput(_Out):
    flags: list[JudgedFlag]


class ExtractedClaim(_Out):
    unit_id: str
    claim: str = Field(min_length=1, description="Exact, shortest quote containing the claim")
    entity: str = Field(min_length=1)
    attribute: str | None = None
    value: str | None = None


class ClaimExtraction(_Out):
    claims: list[ExtractedClaim]


class ClaimVerdict(_Out):
    claim_id: str
    verdict: Literal["supported", "contradicted", "unsupported"]
    fact_code: str | None = None
    explanation: str = Field(min_length=1)
    suggested_fix: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)


class ClaimVerification(_Out):
    verdicts: list[ClaimVerdict]


class VisualFlag(_Out):
    rule_code: str
    severity: Severity
    evidence: str = Field(min_length=1, description="Short description of the image region")
    explanation: str = Field(min_length=1)
    suggested_fix: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    region: list[float] | None = Field(
        default=None, description="[x0, y0, x1, y1] as fractions of the image (0 to 1), or null"
    )


class VisualCheck(_Out):
    flags: list[VisualFlag]


class ScreenText(_Out):
    text: str = Field(description="All text visible in the frame, in reading order; '' if none")


# --- Website facts (task 12.2) --------------------------------------------------------------


class ExtractedFact(_Out):
    entity: str = Field(min_length=1)
    attribute: str = Field(min_length=1)
    value: str
    unit: str | None = None
    statement: str = Field(min_length=1, description="One plain sentence stating the fact")


class FactExtraction(_Out):
    facts: list[ExtractedFact]
