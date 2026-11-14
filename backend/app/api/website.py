"""Website fact check (tasks 12.1–12.3) and the asset library (task 12.4)."""

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

import psycopg
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from psycopg.rows import dict_row
from pydantic import BaseModel, Field

from app.api.contents import IMAGE_TYPES, StorageDep
from app.api.deps import LLM, Admin, Conn, Emb, User, check_brand
from app.api.ratelimit import limited
from app.audit import audit
from app.llm.errors import LLMUnavailableError
from app.models.facts import FactCreate, FactUpdate
from app.rag.facts_store import FactNotFoundError, create_facts, list_facts, update_fact
from app.rag.website import WebsiteError, diff_facts, extract_page_facts, fetch_pages
from app.storage import StorageError

router = APIRouter(tags=["website", "assets"])


# --- 12.1–12.3 website check ------------------------------------------------------------------


class WebsiteCheck(BaseModel):
    urls: list[str] = Field(min_length=1, max_length=10)
    render_js: bool = False


class FactChangeOut(BaseModel):
    id: UUID
    kind: Literal["new", "changed"]
    fact_code: str | None
    entity: str
    attribute: str
    old_value: str | None
    new_value: str
    unit: str | None
    statement: str
    source_url: str
    status: Literal["pending", "accepted", "rejected"]
    created_at: datetime


_CHANGE_COLS = (
    "id, kind, fact_code, entity, attribute, old_value, new_value, unit, statement, source_url, "
    "status, created_at"
)


@router.post(
    "/brands/{brand_id}/website-check",
    response_model=list[FactChangeOut],
    dependencies=[Depends(limited("website check", 10))],
)
def website_check(
    brand_id: UUID, body: WebsiteCheck, user: Admin, conn: Conn, client: LLM
) -> list[dict]:
    """Fetch the pages, extract facts, and store new or changed facts for review."""
    check_brand(user, brand_id)
    try:
        pages = fetch_pages(body.urls, render_js=body.render_js)
        extracted = extract_page_facts(pages, client, brand_id)
    except WebsiteError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except LLMUnavailableError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    approved = list_facts(conn, brand_id, date.today(), status="approved")
    changes = diff_facts(extracted, approved)
    pending = {
        (r[0].lower(), r[1].lower(), r[2])
        for r in conn.execute(
            "select entity, attribute, new_value from public.fact_changes "
            "where brand_id = %s and status = 'pending'",
            (brand_id,),
        ).fetchall()
    }
    with conn.cursor(row_factory=dict_row) as cur:
        for c in changes:
            if (c.entity.lower(), c.attribute.lower(), c.new_value) in pending:
                continue  # already waiting for a decision
            cur.execute(
                "insert into public.fact_changes (brand_id, kind, fact_code, entity, attribute, "
                "old_value, new_value, unit, statement, source_url, created_by) values "
                "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (brand_id, c.kind, c.fact_code, c.entity, c.attribute, c.old_value, c.new_value,
                 c.unit, c.statement, c.source_url, user.id),
            )  # fmt: skip
        rows = cur.execute(
            f"select {_CHANGE_COLS} from public.fact_changes where brand_id = %s "
            "and status = 'pending' order by created_at desc",
            (brand_id,),
        ).fetchall()
    audit(conn, brand_id=brand_id, actor_id=user.id, action="website.check", entity_type="brand",
          entity_id=str(brand_id), after={"urls": body.urls, "changes": len(changes)})  # fmt: skip
    return rows


@router.get("/brands/{brand_id}/fact-changes", response_model=list[FactChangeOut])
def get_fact_changes(
    brand_id: UUID,
    user: Admin,
    conn: Conn,
    status_filter: Annotated[str | None, Query(alias="status")] = "pending",
) -> list[dict]:
    check_brand(user, brand_id)
    with conn.cursor(row_factory=dict_row) as cur:
        return cur.execute(
            f"select {_CHANGE_COLS} from public.fact_changes where brand_id = %s "
            "and (%s::text is null or status = %s) order by created_at desc",
            (brand_id, status_filter, status_filter),
        ).fetchall()


def _change(conn: psycopg.Connection, brand_id: UUID, change_id: UUID) -> dict:
    with conn.cursor(row_factory=dict_row) as cur:
        row = cur.execute(
            f"select {_CHANGE_COLS} from public.fact_changes where id = %s and brand_id = %s "
            "for update",
            (change_id, brand_id),
        ).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Change not found")
    if row["status"] != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, f"This change was already {row['status']}")
    return row


@router.post("/fact-changes/{change_id}/accept", response_model=FactChangeOut)
def accept_change(change_id: UUID, user: Admin, conn: Conn, emb: Emb) -> dict:
    """New facts are added as approved; changed facts are updated in place and keep their
    code, so earlier citations stay valid (task 12.3)."""
    c = _change(conn, user.brand_id, change_id)
    today = date.today()
    try:
        if c["kind"] == "new":
            create_facts(conn, user.brand_id, [FactCreate(
                entity=c["entity"], attribute=c["attribute"], value=c["new_value"],
                unit=c["unit"], statement=c["statement"], source=c["source_url"],
            )], emb, status="approved", actor_id=user.id, today=today)  # fmt: skip
        else:
            update_fact(conn, user.brand_id, c["fact_code"], FactUpdate(
                value=c["new_value"], unit=c["unit"], statement=c["statement"],
                source=c["source_url"],
            ), emb, actor_id=user.id, today=today)  # fmt: skip
    except FactNotFoundError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "The fact no longer exists") from exc
    return _decide(conn, change_id, "accepted", user.id)


@router.post("/fact-changes/{change_id}/reject", response_model=FactChangeOut)
def reject_change(change_id: UUID, user: Admin, conn: Conn) -> dict:
    _change(conn, user.brand_id, change_id)
    return _decide(conn, change_id, "rejected", user.id)


def _decide(conn: psycopg.Connection, change_id: UUID, decision: str, actor: UUID) -> dict:
    with conn.cursor(row_factory=dict_row) as cur:
        return cur.execute(
            "update public.fact_changes set status = %s, decided_by = %s, decided_at = now() "
            f"where id = %s returning {_CHANGE_COLS}",
            (decision, actor, change_id),
        ).fetchone()


# --- 12.4 assets ------------------------------------------------------------------------------

AssetKind = Literal["logo", "disclaimer", "product_description", "template", "other"]
MAX_ASSET_BYTES = 5 * 1024 * 1024


class AssetOut(BaseModel):
    id: UUID
    kind: AssetKind
    name: str
    description: str
    text_content: str | None
    has_file: bool
    created_at: datetime


_ASSET_COLS = (
    "id, kind, name, description, text_content, storage_path is not null as has_file, created_at"
)


@router.get("/brands/{brand_id}/assets", response_model=list[AssetOut])
def get_assets(brand_id: UUID, user: User, conn: Conn) -> list[dict]:
    check_brand(user, brand_id)
    with conn.cursor(row_factory=dict_row) as cur:
        return cur.execute(
            f"select {_ASSET_COLS} from public.assets where brand_id = %s order by kind, name",
            (brand_id,),
        ).fetchall()


@router.post("/brands/{brand_id}/assets", response_model=AssetOut, status_code=201)
def add_asset(
    brand_id: UUID,
    user: Admin,
    conn: Conn,
    store: StorageDep,
    kind: Annotated[AssetKind, Form()],
    name: Annotated[str, Form(min_length=1, max_length=200)],
    description: Annotated[str, Form(max_length=2000)] = "",
    text_content: Annotated[str | None, Form(max_length=5000)] = None,
    file: Annotated[UploadFile | None, File()] = None,
) -> dict:
    """A logo or other image (with a description the vision model reads), or text such as an
    approved disclaimer (used as the fix when a required phrase is missing)."""
    check_brand(user, brand_id)
    path = None
    if file is not None and file.filename:
        data = file.file.read(MAX_ASSET_BYTES + 1)
        mime = next((m for magic, m in IMAGE_TYPES.items() if data.startswith(magic)), None)
        if mime is None:
            raise HTTPException(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Assets must be PNG or JPEG"
            )
        if len(data) > MAX_ASSET_BYTES:
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Asset is over 5 MB")
        path = f"{brand_id}/assets/{name.strip().replace('/', '-')}.{mime.split('/')[1]}"
        try:
            store.upload(path, data, mime)
        except StorageError as exc:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    if path is None and not (text_content or "").strip() and not description.strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "Give a file, a description or the approved text")  # fmt: skip
    with conn.cursor(row_factory=dict_row) as cur:
        row = cur.execute(
            "insert into public.assets (brand_id, kind, name, description, storage_path, "
            "text_content, created_by) values (%s, %s, %s, %s, %s, %s, %s) "
            f"returning {_ASSET_COLS}",
            (brand_id, kind, name.strip(), description.strip(), path,
             (text_content or "").strip() or None, user.id),
        ).fetchone()  # fmt: skip
    audit(conn, brand_id=brand_id, actor_id=user.id, action="asset.create", entity_type="asset",
          entity_id=str(row["id"]), after={"kind": kind, "name": name})  # fmt: skip
    return row


@router.delete("/brands/{brand_id}/assets/{asset_id}", status_code=204)
def delete_asset(brand_id: UUID, asset_id: UUID, user: Admin, conn: Conn) -> None:
    check_brand(user, brand_id)
    deleted = conn.execute(
        "delete from public.assets where id = %s and brand_id = %s returning id",
        (asset_id, brand_id),
    ).fetchone()
    if deleted is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Asset not found")
    audit(conn, brand_id=brand_id, actor_id=user.id, action="asset.delete", entity_type="asset",
          entity_id=str(asset_id))  # fmt: skip


@router.get("/assets/{asset_id}/file")
def asset_file(asset_id: UUID, user: User, conn: Conn, store: StorageDep) -> Response:
    row = conn.execute(
        "select storage_path from public.assets where id = %s and brand_id = %s",
        (asset_id, user.brand_id),
    ).fetchone()
    if row is None or row[0] is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No file for this asset")
    try:
        data = store.download(row[0])
    except StorageError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    mime = "image/png" if row[0].endswith(".png") else "image/jpeg"
    return Response(data, media_type=mime, headers={"Cache-Control": "private, max-age=3600"})
