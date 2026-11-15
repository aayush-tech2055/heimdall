"""API shapes for content, versions, units and stored flags."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.models.flag import Flag

ContentStatus = Literal[
    "draft", "checking", "creator_review", "manager_review", "changes_requested", "approved"
]
FlagStatus = Literal["open", "accepted", "edited", "dismissed", "excepted"]


class FlagCounts(BaseModel):
    open: int = 0
    open_high: int = 0
    resolved: int = 0


class VersionInfo(BaseModel):
    id: UUID
    version_number: int
    created_at: datetime
    review_started_at: datetime | None
    review_finished_at: datetime | None
    review_error: str | None
    counts: FlagCounts


class ContentSummary(BaseModel):
    id: UUID
    title: str
    format: str
    status: ContentStatus
    creator_id: UUID
    creator_name: str | None
    created_at: datetime
    updated_at: datetime
    latest_version_id: UUID | None
    latest_version_number: int | None
    counts: FlagCounts


class ContentDetail(ContentSummary):
    versions: list[VersionInfo]
    text: str | None  # the latest version's text
    review_error: str | None
    # The latest version was made by the creator's fix round (not checked by AI): no more
    # fixes; submit it, or upload a revised version to have it checked again.
    fixes_applied: bool = False


class ReviewUnitOut(BaseModel):
    unit_id: str
    position: int
    text: str
    location: dict


class StoredFlag(Flag):
    id: UUID
    status: FlagStatus
    resolution_note: str | None
    resolved_at: datetime | None
    source_text: str | None  # rule text, fact statement or policy text, for the source chip


class AIUsage(BaseModel):
    """Which model did a step for this version (from ai_calls), for the AI-used labels."""

    purpose: str  # judge | claim_extraction | claim_verification | visual_check | *_embedding
    provider: str
    model: str
    calls: int
    cached: int


class VersionFlags(BaseModel):
    version_id: UUID
    content_id: UUID
    version_number: int
    text: str
    units: list[ReviewUnitOut]
    flags: list[StoredFlag]
    ai_usage: list[AIUsage] = []
