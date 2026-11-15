"""Guidelines and rules API (task 4.5)."""

from collections.abc import Callable
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

from app.api.deps import LLM, Admin, AdminOrManager, Conn, Emb, User, check_brand
from app.api.ratelimit import limited
from app.llm.errors import LLMUnavailableError
from app.models.rules import (
    GuidelineJob,
    Rule,
    RuleStatus,
    RuleStatusChange,
    RuleUpdate,
    VerificationReport,
)
from app.processing.documents import (
    DocumentError,
    UnsupportedFileError,
    parse_guideline_file,
    split_text,
)
from app.rag.embeddings import EmbeddingError
from app.rag.guideline_jobs import GuidelineDoc, create_job, list_jobs, run_job
from app.rag.rules_store import (
    RuleNotFoundError,
    get_rule,
    list_rules,
    set_rule_status,
    update_rule,
)
from app.rag.verification import latest_report, verify_guidelines

router = APIRouter(tags=["guidelines"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_FILES = 10

GuidelineRunner = Callable[[UUID, UUID, list[GuidelineDoc], UUID | None], None]


def guideline_runner() -> GuidelineRunner:
    """Runs a guideline job in the background with its own connection (overridden in tests)."""
    from app.db import get_pool
    from app.llm import get_llm_client
    from app.rag.embeddings import get_embedder

    def run(job_id: UUID, brand_id: UUID, docs: list[GuidelineDoc], actor_id: UUID | None) -> None:
        with get_pool().connection() as conn:
            run_job(conn, job_id, brand_id, docs, client=get_llm_client(),
                    embedder=get_embedder(), actor_id=actor_id)  # fmt: skip

    return run


Runner = Annotated[GuidelineRunner, Depends(guideline_runner)]


def _read_file(file: UploadFile) -> GuidelineDoc:
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"{file.filename} is over 10 MB"
        )
    try:
        return GuidelineDoc(file.filename, parse_guideline_file(file.filename, data))
    except UnsupportedFileError as exc:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, f"{file.filename}: {exc}"
        ) from exc
    except DocumentError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, f"{file.filename}: {exc}"
        ) from exc


def _docs_from_upload(
    files: list[UploadFile], text: str | None, source_doc: str | None
) -> list[GuidelineDoc]:
    """Read every uploaded file (PDF, Word, PowerPoint, text, Markdown or CSV) and/or pasted
    text, refusing the whole upload if any file can't be read."""
    files = [f for f in files if f is not None and f.filename]
    if len(files) > MAX_FILES:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, f"Upload at most {MAX_FILES} files at once"
        )
    docs = [_read_file(f) for f in files]
    if text and text.strip():
        try:
            docs.append(GuidelineDoc(source_doc or "pasted text", split_text(text)))
        except DocumentError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    elif source_doc and len(docs) == 1:
        docs = [GuidelineDoc(source_doc, docs[0].pages)]
    if not docs:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Send a file or some text")
    return docs


@router.post(
    "/brands/{brand_id}/guidelines",
    response_model=GuidelineJob,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(limited("guideline upload", 10))],
)
def upload_guidelines(
    brand_id: UUID,
    user: Admin,
    conn: Conn,
    background: BackgroundTasks,
    run: Runner,
    files: Annotated[list[UploadFile] | None, File()] = None,
    file: Annotated[UploadFile | None, File()] = None,
    text: Annotated[str | None, Form()] = None,
    source_doc: Annotated[str | None, Form()] = None,
) -> GuidelineJob:
    """Check the files, then extract rules in the background (one job for all files).

    Returns at once; poll `GET /brands/{id}/guideline-jobs`. Rules appear as `pending` as each
    file finishes, and the guideline is verified after the last one.
    """
    check_brand(user, brand_id)
    docs = _docs_from_upload([*(files or []), *([file] if file else [])], text, source_doc)
    job = create_job(conn, brand_id, docs, user.id)
    conn.commit()
    background.add_task(run, job["id"], brand_id, docs, user.id)
    return GuidelineJob.model_validate(job)


@router.get("/brands/{brand_id}/guideline-jobs", response_model=list[GuidelineJob])
def get_guideline_jobs(brand_id: UUID, user: AdminOrManager, conn: Conn) -> list[GuidelineJob]:
    """The brand's recent guideline uploads, newest first, with their progress."""
    check_brand(user, brand_id)
    return [GuidelineJob.model_validate(j) for j in list_jobs(conn, brand_id)]


@router.get("/brands/{brand_id}/rules", response_model=list[Rule])
def get_rules(
    brand_id: UUID,
    user: User,
    conn: Conn,
    status_filter: Annotated[RuleStatus | None, Query(alias="status")] = None,
) -> list[Rule]:
    """All rules of the brand, optionally filtered by `?status=`."""
    check_brand(user, brand_id)
    return list_rules(conn, brand_id, status_filter)


@router.get("/brands/{brand_id}/guidelines/report", response_model=VerificationReport | None)
def get_report(brand_id: UUID, user: AdminOrManager, conn: Conn) -> VerificationReport | None:
    check_brand(user, brand_id)
    return latest_report(conn, brand_id)


@router.post(
    "/brands/{brand_id}/guidelines/verify",
    response_model=VerificationReport,
    dependencies=[Depends(limited("guideline upload", 10))],
)
def reverify(brand_id: UUID, user: Admin, conn: Conn, client: LLM) -> VerificationReport:
    """Re-run verification (for example after rejecting or editing rules)."""
    check_brand(user, brand_id)
    try:
        return verify_guidelines(conn, brand_id, client, actor_id=user.id)
    except LLMUnavailableError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc


@router.get("/rules/{code}", response_model=Rule)
def read_rule(code: str, user: User, conn: Conn) -> Rule:
    try:
        return get_rule(conn, user.brand_id, code)
    except RuleNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No rule {code}") from exc


@router.patch("/rules/{code}", response_model=Rule)
def edit_rule(code: str, change: RuleUpdate, user: Admin, conn: Conn, emb: Emb) -> Rule:
    """Edit a rule of the admin's brand (text, category, always_on, deterministic terms)."""
    try:
        return update_rule(conn, user.brand_id, code, change, emb, user.id)
    except RuleNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No rule {code}") from exc
    except EmbeddingError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc


@router.post("/rules/approve", response_model=list[Rule])
def approve_rules(change: RuleStatusChange, user: Admin, conn: Conn) -> list[Rule]:
    """Bulk approve or reject rules of the admin's brand."""
    new_status = "approved" if change.action == "approve" else "rejected"
    try:
        return set_rule_status(conn, user.brand_id, change.codes, new_status, user.id)
    except RuleNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown rule codes: {exc}") from exc
