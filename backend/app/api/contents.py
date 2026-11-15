"""Content API (task 6.8): upload, status, versions and flags."""

import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from functools import partial
from pathlib import Path
from typing import Annotated
from uuid import UUID

import psycopg
import pymupdf
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from pydantic import BaseModel

from app.api.deps import Conn, Creator, CurrentUser, User
from app.api.ratelimit import limited
from app.audit import audit
from app.models.contents import ContentDetail, ContentStatus, ContentSummary, VersionFlags
from app.processing.documents import DocumentError
from app.processing.pdf_content import parse_pdf_content
from app.processing.video import MAX_SECONDS as MAX_VIDEO_SECONDS
from app.processing.video import VideoError
from app.processing.video import duration as video_duration
from app.review.content_store import (
    NotFoundError,
    add_version,
    create_content,
    get_content,
    list_contents,
    version_flags,
)
from app.review.workflow import InvalidTransitionError, transition
from app.storage import Storage, StorageError, get_storage

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


MAX_PDF_BYTES = 20 * 1024 * 1024
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_VIDEO_BYTES = 20 * 1024 * 1024
MAX_CAPTION_BYTES = 512 * 1024
SUFFIXES = {
    "application/pdf": "pdf", "image/png": "png", "image/jpeg": "jpg",
    "video/mp4": "mp4", "video/quicktime": "mov", "video/webm": "webm",
}  # fmt: skip
IMAGE_TYPES = {b"\x89PNG": "image/png", b"\xff\xd8\xff": "image/jpeg"}


@dataclass
class Upload:
    fmt: str  # text | pdf | image
    text: str  # extracted text ("" for images)
    data: bytes | None = None
    mime: str | None = None
    filename: str | None = None


def _read_upload(file: UploadFile | None, text: str | None) -> Upload:
    """Text, a .txt/.md file, a PDF (text extracted) or a PNG/JPEG image."""
    if file is not None and file.filename:
        name = file.filename.lower()
        data = file.file.read(MAX_PDF_BYTES + 1)
        if data.startswith(b"%PDF"):
            if len(data) > MAX_PDF_BYTES:
                raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "PDF is over 20 MB")
            try:
                pdf = parse_pdf_content(data)
            except DocumentError as exc:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
            return Upload("pdf", pdf.text, data, "application/pdf", file.filename)
        video = _video_mime(data)
        if video:
            if len(data) > MAX_VIDEO_BYTES:
                raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Video is over 20 MB")
            _check_video_length(data)
            return Upload("video", "", data, video, file.filename)
        mime = next((m for magic, m in IMAGE_TYPES.items() if data.startswith(magic)), None)
        if mime:
            if len(data) > MAX_IMAGE_BYTES:
                raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Image is over 10 MB")
            return Upload("image", "", data, mime, file.filename)
        if not name.endswith(TEXT_SUFFIXES):
            raise HTTPException(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                "Upload a PDF, a PNG or JPEG image, or a .txt or .md file, or paste text",
            )
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
    return Upload("text", text)


def _video_mime(data: bytes) -> str | None:
    if data[4:8] == b"ftyp":
        return "video/quicktime" if data[8:10] == b"qt" else "video/mp4"
    if data.startswith(b"\x1a\x45\xdf\xa3"):
        return "video/webm"
    return None


def _check_video_length(data: bytes) -> None:
    """Refuse clips over 60 s at upload time (decision: clips <= 60 s)."""
    with tempfile.NamedTemporaryFile() as f:
        f.write(data)
        f.flush()
        try:
            seconds = video_duration(Path(f.name))
        except VideoError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    if seconds > MAX_VIDEO_SECONDS + 0.5:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"The clip is {seconds:.0f} s long; videos can be at most {MAX_VIDEO_SECONDS:.0f} s",
        )


def _read_captions(captions: UploadFile | None) -> bytes | None:
    if captions is None or not captions.filename:
        return None
    if not captions.filename.lower().endswith((".srt", ".vtt")):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Captions must be .srt or .vtt")
    data = captions.file.read(MAX_CAPTION_BYTES + 1)
    if len(data) > MAX_CAPTION_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Captions file is too large")
    return data


def storage_dep() -> Storage:
    return get_storage()


StorageDep = Annotated[Storage, Depends(storage_dep)]


def _store_file(
    conn: psycopg.Connection, store: Storage, brand_id: UUID, content_id: UUID,
    version_id: UUID, up: Upload, alt_text: str | None, captions: bytes | None = None,
) -> None:  # fmt: skip
    if up.data is None:
        return
    suffix = SUFFIXES[up.mime]
    path = f"{brand_id}/{content_id}/{version_id}.{suffix}"
    captions_path = f"{brand_id}/{content_id}/{version_id}.captions.vtt" if captions else None
    try:
        store.upload(path, up.data, up.mime)
        if captions:
            store.upload(captions_path, captions, "text/vtt")
    except StorageError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    conn.execute(
        "update public.content_versions set storage_path = %s, mime_type = %s, alt_text = %s, "
        "captions_path = %s where id = %s",
        (path, up.mime, (alt_text or "").strip() or None, captions_path, version_id),
    )


@router.post(
    "/contents",
    response_model=ContentDetail,
    status_code=201,
    dependencies=[Depends(limited("review", 30))],
)
def upload_content(
    user: Creator,
    conn: Conn,
    background: BackgroundTasks,
    run: Runner,
    store: StorageDep,
    title: Annotated[str, Form(min_length=1, max_length=200)],
    text: Annotated[str | None, Form()] = None,
    file: Annotated[UploadFile | None, File()] = None,
    alt_text: Annotated[str | None, Form(max_length=1000)] = None,
    captions: Annotated[UploadFile | None, File()] = None,
) -> ContentDetail:
    """Upload text, a PDF, an image or a short video → new content, version 1 → review in the
    background."""
    up = _read_upload(file, text)
    caption_bytes = _read_captions(captions) if up.fmt == "video" else None
    content_id, version_id = create_content(
        conn, user, title=title.strip(), fmt=up.fmt, text=up.text
    )
    _store_file(conn, store, user.brand_id, content_id, version_id, up, alt_text, caption_bytes)
    audit(conn, brand_id=user.brand_id, actor_id=user.id, action="content.create",
          entity_type="content", entity_id=str(content_id),
          after={"status": "draft", "format": up.fmt})  # fmt: skip
    transition(conn, content_id, "checking", actor_id=user.id)
    conn.commit()  # the background review reads these rows from another connection
    background.add_task(partial(run, version_id, user.id))
    return get_content(conn, user, content_id)


@router.post(
    "/contents/{content_id}/versions",
    response_model=ContentDetail,
    status_code=201,
    dependencies=[Depends(limited("review", 30))],
)
def upload_version(
    content_id: UUID,
    user: Creator,
    conn: Conn,
    background: BackgroundTasks,
    run: Runner,
    store: StorageDep,
    text: Annotated[str | None, Form()] = None,
    file: Annotated[UploadFile | None, File()] = None,
    alt_text: Annotated[str | None, Form(max_length=1000)] = None,
    captions: Annotated[UploadFile | None, File()] = None,
) -> ContentDetail:
    """A corrected text or file as a new version of the same content (checked again)."""
    content = _content_or_404(conn, user, content_id)
    if content.creator_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Content not found")
    up = _read_upload(file, text)
    if up.fmt != content.format:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"This content is a {content.format}; upload the same kind",
        )
    try:
        transition(conn, content_id, "checking", actor_id=user.id)
    except InvalidTransitionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    version_id = add_version(conn, user, content_id, up.text)
    caption_bytes = _read_captions(captions) if up.fmt == "video" else None
    _store_file(conn, store, user.brand_id, content_id, version_id, up, alt_text, caption_bytes)
    conn.commit()
    background.add_task(partial(run, version_id, user.id))
    return _content_or_404(conn, user, content_id)


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


@router.post(
    "/contents/{content_id}/recheck",
    response_model=ContentDetail,
    dependencies=[Depends(limited("review", 30))],
)
def recheck(
    content_id: UUID, user: User, conn: Conn, background: BackgroundTasks, run: Runner
) -> ContentDetail:
    """Run the review again on the latest version, only when its check failed."""
    content = _content_or_404(conn, user, content_id)
    if user.role == "creator" and content.creator_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Content not found")
    if not content.review_error:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Each upload is checked once. Upload a revised version to have it checked again.",
        )
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


# --- Files for the PDF and image viewers (task 8.4) ------------------------------------------


def _version_file(conn, user, version_id: UUID, store: Storage) -> tuple[bytes, str]:  # noqa: ANN001
    try:
        version_flags(conn, user, version_id)  # visibility check
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Version not found") from exc
    row = conn.execute(
        "select storage_path, mime_type from public.content_versions where id = %s", (version_id,)
    ).fetchone()
    if not row or not row[0]:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This version has no file")
    try:
        return store.download(row[0]), row[1] or "application/octet-stream"
    except StorageError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc


@router.get("/versions/{version_id}/file")
def get_file(version_id: UUID, user: User, conn: Conn, store: StorageDep) -> Response:
    data, mime = _version_file(conn, user, version_id, store)
    return Response(data, media_type=mime, headers={"Cache-Control": "private, max-age=3600"})


class PageSize(BaseModel):
    page: int
    width: float
    height: float


@router.get("/versions/{version_id}/pages", response_model=list[PageSize])
def get_pages(version_id: UUID, user: User, conn: Conn, store: StorageDep) -> list[PageSize]:
    data, mime = _version_file(conn, user, version_id, store)
    if mime != "application/pdf":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Not a PDF")
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        return [
            PageSize(page=i + 1, width=p.rect.width, height=p.rect.height)
            for i, p in enumerate(doc)
        ]


@router.get("/versions/{version_id}/pages/{page}.png")
def get_page_image(
    version_id: UUID, page: int, user: User, conn: Conn, store: StorageDep
) -> Response:
    data, mime = _version_file(conn, user, version_id, store)
    if mime != "application/pdf":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Not a PDF")
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        if not 1 <= page <= doc.page_count:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No such page")
        png = doc[page - 1].get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5)).tobytes("png")
    return Response(png, media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})
