"""Flag actions, approval and comments (tasks 7.2, 7.3, 7.4).

* accept / edit: apply the suggested fix (or the creator's own replacement) to the text,
  create a new version and re-check it; dismissed flags stay dismissed on the new version.
* accept several (or all) fixes at once: apply every chosen fix to the text in one go, so there
  is one new version and one re-check. Where fixes overlap, the most severe flag wins; the
  others stay open on the old version (the re-check raises them again if still relevant).
* dismiss (creator) and except (manager) always store a reason (decision 2); an exception
  also creates an `approved_exceptions` row, so citation validation drops the same flag later.
* submit for approval needs every high-severity flag resolved.
"""

from dataclasses import dataclass
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from app.audit import audit
from app.models.users import CurrentUser
from app.review.content_store import NotFoundError, add_version

EDITABLE = ("creator_review", "changes_requested")


class ActionError(Exception):
    """A rule of the workflow was broken (the API returns 409 or 422)."""

    def __init__(self, message: str, status_code: int = 409) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass
class FlagContext:
    id: UUID
    version_id: UUID
    content_id: UUID
    brand_id: UUID
    creator_id: UUID
    content_status: str
    latest_version_id: UUID
    text: str
    status: str
    source_id: str
    evidence: str
    evidence_start: int
    evidence_end: int
    suggested_fix: str | None


def load_flag(conn: psycopg.Connection, user: CurrentUser, flag_id: UUID) -> FlagContext:
    sql = """
        select f.id, f.version_id, v.content_id, f.brand_id, c.creator_id,
               c.status as content_status,
               (select id from public.content_versions lv where lv.content_id = c.id
                order by lv.version_number desc limit 1) as latest_version_id,
               coalesce(v.extracted_text, '') as text, f.status, f.source_id, f.evidence,
               (f.location->>'evidence_start')::int as evidence_start,
               (f.location->>'evidence_end')::int as evidence_end, f.suggested_fix
        from public.flags f
        join public.content_versions v on v.id = f.version_id
        join public.contents c on c.id = v.content_id
        where f.id = %s and c.brand_id = %s
    """
    params: list[object] = [flag_id, user.brand_id]
    if user.role == "creator":
        sql += " and c.creator_id = %s"
        params.append(user.id)
    with conn.cursor(row_factory=dict_row) as cur:
        row = cur.execute(sql, params).fetchone()
    if row is None:
        raise NotFoundError("flag")
    return FlagContext(**row)


def apply_fix(text: str, start: int, end: int, replacement: str) -> str:
    """Replace text[start:end]; an empty span (missing phrase) inserts with a space."""
    if start == end:
        before = text[:start]
        sep = "" if not before or before[-1].isspace() else " "
        return before + sep + replacement + text[start:]
    return text[:start] + replacement + text[end:]


def _require_creator_edit(flag: FlagContext, user: CurrentUser) -> None:
    if user.role != "creator" or flag.creator_id != user.id:
        raise ActionError("Only the content's creator can do this", 403)
    if flag.content_status not in EDITABLE:
        raise ActionError(f"Content is {flag.content_status}; flags can't change now")
    if flag.version_id != flag.latest_version_id:
        raise ActionError("This flag belongs to an older version")
    if flag.status != "open":
        raise ActionError(f"This flag is already {flag.status}")


def fix_flag(
    conn: psycopg.Connection,
    user: CurrentUser,
    flag_id: UUID,
    replacement: str | None,
) -> tuple[UUID, UUID]:
    """Accept (replacement None: use the suggested fix) or edit. Returns (content, version)."""
    flag = load_flag(conn, user, flag_id)
    _require_creator_edit(flag, user)
    fmt = conn.execute(
        "select format from public.contents where id = %s", (flag.content_id,)
    ).fetchone()[0]
    if fmt != "text":
        raise ActionError(
            f"Fixes can't be applied inside a {fmt}; upload a corrected file as a new version", 409
        )
    status = "accepted" if replacement is None else "edited"
    new = flag.suggested_fix if replacement is None else replacement
    if new is None:
        raise ActionError("This flag has no suggested fix; edit the text instead", 422)
    if flag.text[flag.evidence_start : flag.evidence_end] != flag.evidence:
        raise ActionError("The text no longer matches this flag")
    new_text = apply_fix(flag.text, flag.evidence_start, flag.evidence_end, new)
    note = None if status == "accepted" else f"Replaced with: {new}"
    conn.execute(
        "update public.flags set status = %s, resolution_note = %s, resolved_by = %s, "
        "resolved_at = now() where id = %s",
        (status, note, user.id, flag_id),
    )
    version_id = add_version(conn, user, flag.content_id, new_text)
    audit(conn, brand_id=flag.brand_id, actor_id=user.id, action=f"flag.{status}",
          entity_type="flag", entity_id=str(flag_id),
          after={"replacement": new, "new_version_id": str(version_id)})  # fmt: skip
    return flag.content_id, version_id


SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}


@dataclass
class FixCandidate:
    id: UUID
    severity: str
    start: int
    end: int
    fix: str


@dataclass
class BulkFixResult:
    content_id: UUID
    version_id: UUID
    applied: list[UUID]
    skipped: list[UUID]


def _overlaps(a: FixCandidate, b: FixCandidate) -> bool:
    """Two fixes clash if their spans overlap, or both insert at the same point."""
    if a.start == a.end and b.start == b.end:
        return a.start == b.start
    if a.start == a.end:
        return b.start < a.start < b.end
    if b.start == b.end:
        return a.start < b.start < a.end
    return a.start < b.end and b.start < a.end


def choose_fixes(candidates: list[FixCandidate]) -> tuple[list[FixCandidate], list[FixCandidate]]:
    """Pick a set of non-clashing fixes: most severe first, then the longer span.

    A fix identical to a chosen one (same span, same text) counts as chosen too.
    Returns (chosen, skipped).
    """
    order = sorted(
        candidates, key=lambda c: (SEVERITY_RANK.get(c.severity, 3), -(c.end - c.start), c.start)
    )
    chosen: list[FixCandidate] = []
    skipped: list[FixCandidate] = []
    for cand in order:
        same = next(
            (c for c in chosen if (c.start, c.end, c.fix) == (cand.start, cand.end, cand.fix)),
            None,
        )
        if same is None and any(_overlaps(cand, c) for c in chosen):
            skipped.append(cand)
        else:
            chosen.append(cand)
    return chosen, skipped


def apply_fixes(text: str, fixes: list[FixCandidate]) -> str:
    """Apply non-clashing fixes from the end of the text backwards, so offsets stay valid."""
    unique = {(f.start, f.end, f.fix): f for f in fixes}.values()
    for fix in sorted(unique, key=lambda f: (f.start, f.end), reverse=True):
        text = apply_fix(text, fix.start, fix.end, fix.fix)
    return text


def fix_many(
    conn: psycopg.Connection,
    user: CurrentUser,
    content_id: UUID,
    flag_ids: list[UUID] | None,
) -> BulkFixResult:
    """Accept the suggested fixes of `flag_ids` (None: every open flag with a fix) on the
    latest version, in one new version."""
    row = conn.execute(
        "select c.creator_id, c.status, c.format, c.brand_id, v.id, coalesce(v.extracted_text, '') "
        "from public.contents c join public.content_versions v on v.content_id = c.id "
        "where c.id = %s and c.brand_id = %s order by v.version_number desc limit 1",
        (content_id, user.brand_id),
    ).fetchone()
    if row is None or (user.role == "creator" and row[0] != user.id):
        raise NotFoundError("content")
    creator_id, content_status, fmt, brand_id, version_id, text = row
    if user.role != "creator" or creator_id != user.id:
        raise ActionError("Only the content's creator can do this", 403)
    if content_status not in EDITABLE:
        raise ActionError(f"Content is {content_status}; flags can't change now")
    if fmt != "text":
        raise ActionError(
            f"Fixes can't be applied inside a {fmt}; upload a corrected file as a new version"
        )
    rows = conn.execute(
        "select id, severity, evidence, suggested_fix, "
        "(location->>'evidence_start')::int, (location->>'evidence_end')::int "
        "from public.flags where version_id = %s and status = 'open' "
        "and suggested_fix is not null",
        (version_id,),
    ).fetchall()
    by_id = {r[0]: r for r in rows}
    if flag_ids is not None:
        unknown = [f for f in flag_ids if f not in by_id]
        if unknown:
            raise ActionError(
                f"{len(unknown)} of the chosen flags are not open flags with a fix on the "
                "latest version; reload and try again"
            )
        rows = [by_id[f] for f in dict.fromkeys(flag_ids)]
    candidates = [
        FixCandidate(fid, sev, start, end, fix)
        for fid, sev, evidence, fix, start, end in rows
        if start is not None and end is not None and text[start:end] == evidence
    ]
    if not candidates:
        raise ActionError("There are no fixes to apply", 422)
    chosen, skipped = choose_fixes(candidates)
    new_text = apply_fixes(text, chosen)
    applied = [c.id for c in chosen]
    conn.execute(
        "update public.flags set status = 'accepted', resolved_by = %s, resolved_at = now() "
        "where id = any(%s)",
        (user.id, applied),
    )
    new_version = add_version(conn, user, content_id, new_text)
    audit(conn, brand_id=brand_id, actor_id=user.id, action="flag.accepted_bulk",
          entity_type="content", entity_id=str(content_id),
          after={"flags": [str(a) for a in applied], "skipped": [str(s.id) for s in skipped],
                 "new_version_id": str(new_version)})  # fmt: skip
    return BulkFixResult(content_id, new_version, applied, [s.id for s in skipped])


def dismiss_flag(conn: psycopg.Connection, user: CurrentUser, flag_id: UUID, reason: str) -> None:
    flag = load_flag(conn, user, flag_id)
    _require_creator_edit(flag, user)
    conn.execute(
        "update public.flags set status = 'dismissed', resolution_note = %s, resolved_by = %s, "
        "resolved_at = now() where id = %s",
        (reason.strip(), user.id, flag_id),
    )
    audit(conn, brand_id=flag.brand_id, actor_id=user.id, action="flag.dismissed",
          entity_type="flag", entity_id=str(flag_id), after={"reason": reason.strip()})  # fmt: skip


def except_flag(conn: psycopg.Connection, user: CurrentUser, flag_id: UUID, reason: str) -> None:
    """Manager approves an exception: the flag is excepted and the same source + evidence
    will not be flagged again for this brand."""
    flag = load_flag(conn, user, flag_id)
    if user.role not in ("manager", "admin"):
        raise ActionError("Only managers can approve exceptions", 403)
    if flag.content_status != "manager_review":
        raise ActionError("Exceptions are approved while the content is in manager review")
    if flag.status not in ("open", "dismissed"):
        raise ActionError(f"This flag is already {flag.status}")
    if not flag.evidence.strip():
        raise ActionError("A missing required phrase cannot be excepted; add it instead", 422)
    conn.execute(
        "update public.flags set status = 'excepted', resolution_note = %s, resolved_by = %s, "
        "resolved_at = now() where id = %s",
        (reason.strip(), user.id, flag_id),
    )
    conn.execute(
        "insert into public.approved_exceptions (brand_id, source_id, evidence, reason, flag_id, "
        "approved_by) values (%s, %s, %s, %s, %s, %s)",
        (flag.brand_id, flag.source_id, flag.evidence, reason.strip(), flag_id, user.id),
    )
    audit(conn, brand_id=flag.brand_id, actor_id=user.id, action="flag.excepted",
          entity_type="flag", entity_id=str(flag_id),
          after={"reason": reason.strip(), "source_id": flag.source_id})  # fmt: skip


def open_high_flags(conn: psycopg.Connection, content_id: UUID) -> int:
    return conn.execute(
        "select count(*) from public.flags f where f.version_id = (select id from "
        "public.content_versions where content_id = %s order by version_number desc limit 1) "
        "and f.status = 'open' and f.severity = 'high'",
        (content_id,),
    ).fetchone()[0]


def add_comment(
    conn: psycopg.Connection,
    user: CurrentUser,
    version_id: UUID,
    body: str,
    flag_id: UUID | None = None,
) -> dict:
    if flag_id is not None:
        ok = conn.execute(
            "select 1 from public.flags where id = %s and version_id = %s", (flag_id, version_id)
        ).fetchone()
        if ok is None:
            raise ActionError("That flag is not on this version", 422)
    with conn.cursor(row_factory=dict_row) as cur:
        return cur.execute(
            "insert into public.comments (version_id, brand_id, author_id, body, flag_id) "
            "values (%s, %s, %s, %s, %s) returning id, version_id, author_id, body, flag_id, "
            "created_at",
            (version_id, user.brand_id, user.id, body.strip(), flag_id),
        ).fetchone()


def list_comments(conn: psycopg.Connection, version_id: UUID) -> list[dict]:
    with conn.cursor(row_factory=dict_row) as cur:
        return cur.execute(
            "select c.id, c.version_id, c.author_id, p.display_name as author_name, "
            "p.role as author_role, c.body, c.flag_id, c.created_at from public.comments c "
            "left join public.profiles p on p.id = c.author_id where c.version_id = %s "
            "order by c.created_at",
            (version_id,),
        ).fetchall()
