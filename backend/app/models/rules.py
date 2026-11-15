"""API shapes for rules and the guideline verification report."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.flag import Category

RuleStatus = Literal["pending", "approved", "rejected"]


class Rule(BaseModel):
    rule_code: str
    category: Category
    text: str
    source_doc: str | None
    source_page: int | None
    check_type: Literal["deterministic", "semantic"]
    det_kind: Literal["banned_terms", "required_phrase"] | None
    terms: list[str]
    examples_bad: list[str]
    examples_good: list[str]
    always_on: bool
    status: RuleStatus
    updated_at: datetime


class RuleUpdate(BaseModel):
    """Admin edit of a rule (PATCH). Omitted fields are unchanged."""

    text: str | None = Field(default=None, min_length=1)
    category: Category | None = None
    always_on: bool | None = None
    check_type: Literal["deterministic", "semantic"] | None = None
    det_kind: Literal["banned_terms", "required_phrase"] | None = None
    terms: list[str] | None = None


class RuleStatusChange(BaseModel):
    codes: list[str] = Field(min_length=1)
    action: Literal["approve", "reject"]


class PairIssue(BaseModel):
    rule_a: str
    rule_b: str
    similarity: float
    explanation: str


class VagueIssue(BaseModel):
    rule_code: str
    reason: str
    suggested_rewrite: str | None


class VerificationReport(BaseModel):
    duplicates: list[PairIssue] = []
    contradictions: list[PairIssue] = []
    vague: list[VagueIssue] = []
    missing_categories: list[str] = []
    pairs_checked: int = 0
    rules_checked: int = 0


class GuidelineJobFile(BaseModel):
    name: str
    pages: int


class GuidelineJob(BaseModel):
    """A guideline upload of one or more files, extracted in the background."""

    id: UUID
    status: Literal["queued", "running", "done", "failed"]
    files: list[GuidelineJobFile]
    files_done: int
    rules_added: int
    error: str | None
    created_at: datetime
    finished_at: datetime | None
