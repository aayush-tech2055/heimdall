"""Facts API (task 5.2)."""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from app.api.deps import Admin, Conn, Emb, User, check_brand
from app.models.facts import (
    Fact,
    FactCreate,
    FactImportResult,
    FactStatus,
    FactStatusChange,
    FactUpdate,
)
from app.rag.embeddings import EmbeddingError
from app.rag.facts_store import (
    FactNotFoundError,
    create_facts,
    list_facts,
    parse_facts_csv,
    set_fact_status,
    update_fact,
)

router = APIRouter(tags=["facts"])

MAX_CSV_BYTES = 2 * 1024 * 1024


def today() -> date:
    """The date expiry is measured against (overridable in tests)."""
    return date.today()


Today = Annotated[date, Depends(today)]


@router.get("/brands/{brand_id}/facts", response_model=list[Fact])
def get_facts(
    brand_id: UUID,
    user: User,
    conn: Conn,
    day: Today,
    status_filter: Annotated[FactStatus | None, Query(alias="status")] = None,
    q: str | None = None,
) -> list[Fact]:
    check_brand(user, brand_id)
    return list_facts(conn, brand_id, day, status=status_filter, query=q)


@router.post("/brands/{brand_id}/facts", response_model=Fact, status_code=201)
def add_fact(
    brand_id: UUID, fact: FactCreate, user: Admin, conn: Conn, emb: Emb, day: Today
) -> Fact:
    """An admin typing a fact in approves it at the same time."""
    check_brand(user, brand_id)
    try:
        (created,) = create_facts(
            conn, brand_id, [fact], emb, status="approved", actor_id=user.id, today=day
        )
    except EmbeddingError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    return created


@router.patch("/brands/{brand_id}/facts/{code}", response_model=Fact)
def edit_fact(
    brand_id: UUID, code: str, change: FactUpdate, user: Admin, conn: Conn, emb: Emb, day: Today
) -> Fact:
    check_brand(user, brand_id)
    try:
        return update_fact(conn, brand_id, code, change, emb, actor_id=user.id, today=day)
    except FactNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No fact {code}") from exc
    except EmbeddingError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc


@router.post("/brands/{brand_id}/facts/import", response_model=FactImportResult)
def import_facts(
    brand_id: UUID,
    user: Admin,
    conn: Conn,
    emb: Emb,
    day: Today,
    file: Annotated[UploadFile, File()],
) -> FactImportResult:
    """Import a CSV (entity, attribute, value, unit, statement, source, valid_until).

    All or nothing: if any row is invalid, nothing is imported and every error is returned.
    Imported facts are pending until approved.
    """
    check_brand(user, brand_id)
    data = file.file.read(MAX_CSV_BYTES + 1)
    if len(data) > MAX_CSV_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "CSV is over 2 MB")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "CSV must be UTF-8") from exc
    facts, errors = parse_facts_csv(text)
    if errors:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            [f"Row {e.row}: {e.message}" for e in errors],
        )
    if not facts:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "The CSV has no fact rows")
    try:
        imported = create_facts(
            conn, brand_id, facts, emb, status="pending", actor_id=user.id, today=day
        )
    except EmbeddingError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    return FactImportResult(imported=imported)


@router.post("/brands/{brand_id}/facts/approve", response_model=list[Fact])
def approve_facts(
    brand_id: UUID, change: FactStatusChange, user: Admin, conn: Conn, day: Today
) -> list[Fact]:
    check_brand(user, brand_id)
    new_status = "approved" if change.action == "approve" else "rejected"
    try:
        return set_fact_status(
            conn, brand_id, change.codes, new_status, actor_id=user.id, today=day
        )
    except FactNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown fact codes: {exc}") from exc
