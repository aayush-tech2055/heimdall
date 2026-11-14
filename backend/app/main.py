"""FastAPI application entry point. Run with `uvicorn app.main:app --reload`."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.contents import router as contents_router
from app.api.facts import router as facts_router
from app.api.guidelines import router as guidelines_router
from app.api.health import router as health_router
from app.api.me import router as me_router
from app.api.workflow import router as workflow_router
from app.config import get_settings


def create_app() -> FastAPI:
    """Build the FastAPI app with middleware and routers."""
    settings = get_settings()
    app = FastAPI(title="Heimdall", version="0.1.0", description="Nothing crosses unchecked.")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router)
    app.include_router(me_router)
    app.include_router(guidelines_router)
    app.include_router(facts_router)
    app.include_router(contents_router)
    app.include_router(workflow_router)
    return app


app = create_app()
