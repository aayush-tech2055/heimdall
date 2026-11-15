"""Content API (task 6.8): upload, status, versions and flags."""

from collections.abc import Callable
from datetime import date
from functools import partial
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)

from app.api.deps import Conn, Creator, CurrentUser, User
from app.audit import audit
from app.models.contents import ContentDetail, ContentStatus, ContentSummary, VersionFlags
from app.review.content_store import (
    NotFoundError,
    create_content,
    get_content,
    list_contents,
    version_flags,
)
from app.review.workflow import InvalidTransitionError, transition

router = APIRouter(tags=["contents"])

MAX_TEXT_CHARS = 100_000
TEXT_SUFFIXES = (".txt", ".md", ".markdown")

ReviewRunner = Callable[[UUID, UUID | None], None]


def review_runner() -> ReviewRunner:
    """Runs a review in the background (overridden in tests)."""
    from app.db import get_pool
    from app.llm import get_llm_client
    from app.rag.embeddings import get_embedder
    from app.review.orchestrator import review_content

    def run(version_id: UUID, actor_id: UUID | None) -> None:
        review_content(
            version_id, pool=get_pool(), client=get_llm_client(), embedder=get_embedder(),
            today=date.today(), actor_id=actor_id,
        )  # fmt: skip

    return run


Runner = Annotated[ReviewRunner, Depends(review_runner)]


def _read_text(file: UploadFile | None, text: str | None) -> tuple[str, str]:
    """(format, text) from the upload."""
    if file is not None and file.filename:
        name = file.filename.lower()
        if not name.endswith(TEXT_SUFFIXES):
            raise HTTPException(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Upload a .txt or .md file, or paste text"
            )
        data = file.file.read(MAX_TEXT_CHARS * 4 + 1)
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HTTPException(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "File must be UTF-8"
            ) from exc
    if not text or not text.strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "There is no text to check")
    if len(text) > MAX_TEXT_CHARS:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"Text is over {MAX_TEXT_CHARS} characters"
        )
    return "text", text


@router.post("/contents", response_model=ContentDetail, status_code=201)
def upload_content(
    user: Creator,
    conn: Conn,
    background: BackgroundTasks,
    run: Runner,
    title: Annotated[str, Form(min_length=1, max_length=200)],
    text: Annotated[str | None, Form()] = None,
    file: Annotated[UploadFile | None, File()] = None,
) -> ContentDetail:
    """Upload text or a file → new content, version 1 → start the review in the background."""
    fmt, body = _read_text(file, text)
    content_id, version_id = create_content(conn, user, title=title.strip(), fmt=fmt, text=body)
    audit(conn, brand_id=user.brand_id, actor_id=user.id, action="content.create",
          entity_type="content", entity_id=str(content_id),
          after={"status": "draft"})  # fmt: skip
    transition(conn, content_id, "checking", actor_id=user.id)
    conn.commit()  # the background review reads these rows from another connection
    background.add_task(partial(run, version_id, user.id))
    return get_content(conn, user, content_id)


@router.get("/contents", response_model=list[ContentSummary])
def get_contents(
    user: User,
    conn: Conn,
    status_filter: Annotated[ContentStatus | None, Query(alias="status")] = None,
) -> list[ContentSummary]:
    """Creators see their own content; managers and admins see the whole brand."""
    return list_contents(conn, user, status_filter)


def _content_or_404(conn, user: CurrentUser, content_id: UUID) -> ContentDetail:  # noqa: ANN001
    try:
        return get_content(conn, user, content_id)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Content not found") from exc


@router.get("/contents/{content_id}", response_model=ContentDetail)
def read_content(content_id: UUID, user: User, conn: Conn) -> ContentDetail:
    return _content_or_404(conn, user, content_id)


@router.post("/contents/{content_id}/recheck", response_model=ContentDetail)
def recheck(
    content_id: UUID, user: User, conn: Conn, background: BackgroundTasks, run: Runner
) -> ContentDetail:
    """Run the review again on the latest version (for example after a failed review)."""
    content = _content_or_404(conn, user, content_id)
    if user.role == "creator" and content.creator_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Content not found")
    try:
        transition(conn, content_id, "checking", actor_id=user.id, detail={"recheck": True})
    except InvalidTransitionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    conn.commit()
    background.add_task(partial(run, content.latest_version_id, user.id))
    return _content_or_404(conn, user, content_id)


@router.get("/versions/{version_id}/flags", response_model=VersionFlags)
def get_version_flags(version_id: UUID, user: User, conn: Conn) -> VersionFlags:
    try:
        return version_flags(conn, user, version_id)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Version not found") from exc
