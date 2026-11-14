"""The signed-in user, as the API sees them."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class CurrentUser:
    id: UUID
    role: str  # admin | creator | manager
    brand_id: UUID
    display_name: str | None = None
    email: str | None = None
