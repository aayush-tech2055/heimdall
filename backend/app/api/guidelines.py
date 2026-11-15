"""Guidelines and rules API (task 4.5)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status

from app.api.deps import LLM, Admin, AdminOrManager, Conn, Emb, User, check_brand
from app.llm.errors import LLMUnavailableError
from app.models.rules import (
    GuidelineUploadResult,
    Rule,
    RuleStatus,
    RuleStatusChange,
    RuleUpdate,
    VerificationReport,
)
from app.processing.documents import DocumentError, PageText, parse_pdf, split_text
from app.rag.embeddings import EmbeddingError
from app.rag.extraction import extract_rules
from app.rag.rules_store import (
    RuleNotFoundError,
    get_rule,
    list_rules,
    next_rule_number,
    set_rule_status,
    store_rules,
    update_rule,
)
from app.rag.verification import latest_report, verify_guidelines

router = APIRouter(tags=["guidelines"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def _pages_from_upload(file: UploadFile | None, text: str | None) -> tuple[str, list[PageText]]:
    if file is not None and file.filename:
        data = file.file.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "PDF is over 10 MB")
        if not data.startswith(b"%PDF"):
            raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Upload a PDF file")
        return file.filename, parse_pdf(data)
    if text and text.strip():
        return "pasted text", split_text(text)
    raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Send a PDF file or some text")


@router.post("/brands/{brand_id}/guidelines", response_model=GuidelineUploadResult)
def upload_guidelines(
    brand_id: UUID,
    user: Admin,
    conn: Conn,
    client: LLM,
    emb: Emb,
    file: Annotated[UploadFile | None, File()] = None,
    text: Annotated[str | None, Form()] = None,
    source_doc: Annotated[str | None, Form()] = None,
) -> GuidelineUploadResult:
    """Upload → extract rules (pending) → embed and store → verify → report."""
    check_brand(user, brand_id)
    try:
        name, pages = _pages_from_upload(file, text)
        name = source_doc or name
        drafts = extract_rules(
            pages, source_doc=name, client=client,
            first_number=next_rule_number(conn, brand_id), brand_id=brand_id,
        )  # fmt: skip
        rules = store_rules(conn, brand_id, drafts, emb)
        report = verify_guidelines(conn, brand_id, client, source_doc=name, actor_id=user.id)
    except DocumentError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except (LLMUnavailableError, EmbeddingError) as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    return GuidelineUploadResult(source_doc=name, pages=len(pages), rules=rules, report=report)


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


@router.post("/brands/{brand_id}/guidelines/verify", response_model=VerificationReport)
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
