"""Health check route."""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    service: str


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Liveness probe used by deploys and CI."""
    return HealthResponse(status="ok", service="heimdall-backend")
