"""A flag before citation validation: what a layer proposes."""

from dataclasses import dataclass, field


@dataclass
class Candidate:
    unit_id: str
    source_type: str  # rule | fact | policy
    source_id: str
    category: str
    severity: str
    evidence: str
    explanation: str
    suggested_fix: str | None
    confidence: float
    layer: str  # rules | guidelines | claims | visuals
    # Only layer (a)'s missing-required-phrase flag may have empty evidence.
    allow_empty_evidence: bool = False
    # Layer (a) knows the exact span in the ORIGINAL unit text; AI layers do not.
    span: tuple[int, int] | None = None
    # Sources that were given to the model for this candidate (decision 20). None = code.
    supplied: frozenset[str] | None = None
    extra: dict = field(default_factory=dict)

    def payload(self) -> dict:
        """The candidate as stored in dropped_flags."""
        return {
            "unit_id": self.unit_id, "source_type": self.source_type,
            "source_id": self.source_id, "category": self.category, "severity": self.severity,
            "evidence": self.evidence, "explanation": self.explanation,
            "suggested_fix": self.suggested_fix, "confidence": self.confidence,
            "layer": self.layer, **self.extra,
        }  # fmt: skip
