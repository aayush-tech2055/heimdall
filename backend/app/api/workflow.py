"""Workflow API: flag actions (7.2), manager actions (7.3), comments (7.4)."""

from datetime import datetime
from functools import partial
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from pydantic import BaseModel, Field

from app.api.contents import Runner
from app.api.deps import Conn, Manager, User
from app.models.contents import ContentDetail
from app.review.actions import (
    ActionError,
    add_comment,
    dismiss_flag,
    except_flag,
    fix_flag,
    list_comments,
    open_high_flags,
)
from app.review.content_store import NotFoundError, get_content, version_flags
from app.review.workflow import InvalidTransitionError, transition

router = APIRouter(tags=["workflow"])


class Reason(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


class Replacement(BaseModel):
    text: str = Field(max_length=5000)


class CommentIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)
    flag_id: UUID | None = None


class Comment(BaseModel):
    id: UUID
    version_id: UUID
    author_id: UUID
    author_name: str | None = None
    author_role: str | None = None
    body: str
    flag_id: UUID | None
    created_at: datetime


class ManagerNote(BaseModel):
    comment: str | None = Field(default=None, max_length=4000)


class ChangeRequest(BaseModel):
    comment: str = Field(min_length=3, max_length=4000)


def _fail(exc: Exception) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    if isinstance(exc, ActionError):
        return HTTPException(exc.status_code, str(exc))
    if isinstance(exc, InvalidTransitionError):
        return HTTPException(status.HTTP_409_CONFLICT, str(exc))
    raise exc


def _content(conn, user, content_id: UUID) -> ContentDetail:  # noqa: ANN001
    try:
        return get_content(conn, user, content_id)
    except NotFoundError as exc:
        raise _fail(exc) from exc


# --- 7.2 flag actions (creator) -------------------------------------------------------------


def _fix(conn, user, flag_id, replacement, background, run) -> ContentDetail:  # noqa: ANN001
    try:
        content_id, version_id = fix_flag(conn, user, flag_id, replacement)
        transition(conn, content_id, "checking", actor_id=user.id,
                   detail={"version_id": str(version_id)})  # fmt: skip
    except (NotFoundError, ActionError, InvalidTransitionError) as exc:
        raise _fail(exc) from exc
    conn.commit()
    background.add_task(partial(run, version_id, user.id))
    return _content(conn, user, content_id)


@router.post("/flags/{flag_id}/accept", response_model=ContentDetail)
def accept_flag(
    flag_id: UUID, user: User, conn: Conn, background: BackgroundTasks, run: Runner
) -> ContentDetail:
    """Apply the suggested fix, creating a new version that is checked again."""
    return _fix(conn, user, flag_id, None, background, run)


@router.post("/flags/{flag_id}/edit", response_model=ContentDetail)
def edit_flag(
    flag_id: UUID, body: Replacement, user: User, conn: Conn, background: BackgroundTasks,
    run: Runner,
) -> ContentDetail:  # fmt: skip
    """Replace the flagged words with the creator's own text (new version, checked again)."""
    return _fix(conn, user, flag_id, body.text, background, run)


@router.post("/flags/{flag_id}/dismiss", status_code=204)
def dismiss(flag_id: UUID, body: Reason, user: User, conn: Conn) -> None:
    try:
        dismiss_flag(conn, user, flag_id, body.reason)
    except (NotFoundError, ActionError) as exc:
        raise _fail(exc) from exc


@router.post("/contents/{content_id}/submit", response_model=ContentDetail)
def submit_for_approval(content_id: UUID, user: User, conn: Conn) -> ContentDetail:
    """Creator sends the content to a manager once no high-severity flag is open."""
    content = _content(conn, user, content_id)
    if user.role != "creator" or content.creator_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the creator can submit")
    high = open_high_flags(conn, content_id)
    if high:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{high} high-severity flag{'s are' if high > 1 else ' is'} still open: fix or "
            "dismiss with a reason first",
        )
    try:
        transition(conn, content_id, "manager_review", actor_id=user.id)
    except InvalidTransitionError as exc:
        raise _fail(exc) from exc
    return _content(conn, user, content_id)


@router.post("/contents/{content_id}/reopen", response_model=ContentDetail)
def reopen(content_id: UUID, user: User, conn: Conn) -> ContentDetail:
    """Creator starts working on requested changes (changes_requested -> creator_review)."""
    content = _content(conn, user, content_id)
    if user.role != "creator" or content.creator_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the creator can do this")
    try:
        transition(conn, content_id, "creator_review", actor_id=user.id)
    except InvalidTransitionError as exc:
        raise _fail(exc) from exc
    return _content(conn, user, content_id)


# --- 7.3 manager actions --------------------------------------------------------------------


@router.post("/contents/{content_id}/approve", response_model=ContentDetail)
def approve(content_id: UUID, body: ManagerNote, user: Manager, conn: Conn) -> ContentDetail:
    content = _content(conn, user, content_id)
    try:
        transition(conn, content_id, "approved", actor_id=user.id,
                   detail={"comment": body.comment} if body.comment else None)  # fmt: skip
        if body.comment and content.latest_version_id:
            add_comment(conn, user, content.latest_version_id, body.comment)
    except InvalidTransitionError as exc:
        raise _fail(exc) from exc
    return _content(conn, user, content_id)


@router.post("/contents/{content_id}/request-changes", response_model=ContentDetail)
def request_changes(
    content_id: UUID, body: ChangeRequest, user: Manager, conn: Conn
) -> ContentDetail:
    """Send content back to the creator; a comment saying what to change is required."""
    content = _content(conn, user, content_id)
    try:
        transition(conn, content_id, "changes_requested", actor_id=user.id,
                   detail={"comment": body.comment})  # fmt: skip
    except InvalidTransitionError as exc:
        raise _fail(exc) from exc
    add_comment(conn, user, content.latest_version_id, body.comment)
    return _content(conn, user, content_id)


@router.post("/flags/{flag_id}/except", status_code=204)
def approve_exception(flag_id: UUID, body: Reason, user: Manager, conn: Conn) -> None:
    try:
        except_flag(conn, user, flag_id, body.reason)
    except (NotFoundError, ActionError) as exc:
        raise _fail(exc) from exc


# --- 7.4 comments ---------------------------------------------------------------------------


def _check_version(conn, user, version_id: UUID) -> None:  # noqa: ANN001
    try:
        version_flags(conn, user, version_id)
    except NotFoundError as exc:
        raise _fail(exc) from exc


@router.get("/versions/{version_id}/comments", response_model=list[Comment])
def get_comments(version_id: UUID, user: User, conn: Conn) -> list[dict]:
    _check_version(conn, user, version_id)
    return list_comments(conn, version_id)


@router.post("/versions/{version_id}/comments", response_model=Comment, status_code=201)
def post_comment(version_id: UUID, body: CommentIn, user: User, conn: Conn) -> dict:
    _check_version(conn, user, version_id)
    try:
        return add_comment(conn, user, version_id, body.body, body.flag_id)
    except ActionError as exc:
        raise _fail(exc) from exc
