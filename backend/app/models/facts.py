"""API shapes for approved facts (decision 9)."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

FactStatus = Literal["pending", "approved", "rejected"]
Expiry = Literal["valid", "expiring", "expired", "no_expiry"]


class Fact(BaseModel):
    fact_code: str
    entity: str
    attribute: str
    value: str
    unit: str | None
    statement: str
    source: str | None
    valid_until: date | None
    status: FactStatus
    expiry: Expiry = "no_expiry"  # computed in code (decision 10)
    updated_at: datetime


class FactCreate(BaseModel):
    entity: str = Field(min_length=1)
    attribute: str = Field(min_length=1)
    value: str = Field(min_length=1)
    unit: str | None = None
    statement: str = Field(min_length=1)
    source: str | None = None
    valid_until: date | None = None


class FactUpdate(BaseModel):
    entity: str | None = Field(default=None, min_length=1)
    attribute: str | None = Field(default=None, min_length=1)
    value: str | None = Field(default=None, min_length=1)
    unit: str | None = None
    statement: str | None = Field(default=None, min_length=1)
    source: str | None = None
    valid_until: date | None = None
    status: FactStatus | None = None


class FactStatusChange(BaseModel):
    codes: list[str] = Field(min_length=1)
    action: Literal["approve", "reject"]


class ImportProblem(BaseModel):
    row: int
    message: str


class FactImportResult(BaseModel):
    imported: list[Fact]
    errors: list[ImportProblem] = []
