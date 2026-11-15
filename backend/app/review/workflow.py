"""The content workflow state machine (task 7.1).

    draft -> checking -> creator_review -> manager_review -> approved
    manager_review -> changes_requested -> creator_review     (send back)
    checking -> draft                                         (review failed)
    creator_review / changes_requested -> checking            (new version or re-check)

Every transition locks the content row, is checked here, and is written to `audit_log`.
An invalid transition raises `InvalidTransitionError` (the API returns 409).
"""

from uuid import UUID

import psycopg

from app.audit import audit

# (from, to) -> action name recorded in the audit log
TRANSITIONS: dict[tuple[str, str], str] = {
    ("draft", "checking"): "content.submit",
    ("checking", "creator_review"): "content.review_done",
    ("checking", "draft"): "content.review_failed",
    ("creator_review", "checking"): "content.new_version",
    ("creator_review", "manager_review"): "content.submit_for_approval",
    ("manager_review", "approved"): "content.approve",
    ("manager_review", "changes_requested"): "content.request_changes",
    ("changes_requested", "creator_review"): "content.reopen",
    ("changes_requested", "checking"): "content.new_version",
}


class InvalidTransitionError(Exception):
    def __init__(self, current: str, target: str) -> None:
        self.current, self.target = current, target
        super().__init__(f"Cannot move content from {current} to {target}")


def allowed(current: str, target: str) -> bool:
    return (current, target) in TRANSITIONS


def transition(
    conn: psycopg.Connection,
    content_id: UUID,
    target: str,
    *,
    actor_id: UUID | None,
    detail: dict | None = None,
) -> str:
    """Move content to `target`; return the previous status."""
    row = conn.execute(
        "select status, brand_id from public.contents where id = %s for update", (content_id,)
    ).fetchone()
    if row is None:
        raise LookupError(f"content {content_id}")
    current, brand_id = row
    if not allowed(current, target):
        raise InvalidTransitionError(current, target)
    conn.execute("update public.contents set status = %s where id = %s", (target, content_id))
    audit(conn, brand_id=brand_id, actor_id=actor_id, action=TRANSITIONS[(current, target)],
          entity_type="content", entity_id=str(content_id), before={"status": current},
          after={"status": target, **(detail or {})})  # fmt: skip
    return current
