"""Flag actions, approval and comments (tasks 7.2, 7.3, 7.4).

* One AI check per upload, one fix round per check: the creator chooses which suggested fixes
  to accept (and may reword any of them), and all of them are applied to the text at once.
  That makes one new version, which is NOT checked again: its flags are copied from the
  checked version with their positions moved to the new text, the fixed ones marked accepted
  or edited. A version made by fixes cannot be fixed again; the creator submits it, and the
  manager decides on what is left. To have the AI check the script again, the creator uploads
  a revised version.
* Where fixes overlap, the most severe flag wins; the others stay open on the new version.
* dismiss (creator) and except (manager) always store a reason (decision 2); an exception
  also creates an `approved_exceptions` row, so citation validation drops the same flag later.
"""

import json
from dataclasses import dataclass
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from app.audit import audit
from app.models.users import CurrentUser
from app.review.content_store import NotFoundError, add_version

ALREADY_FIXED = (
    "Fixes were already applied to this script. Submit it to your manager, or upload a "
    "revised script to have it checked again."
)

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
    """Accept one suggested fix (replacement None) or reword it: a fix round of one flag.

    Returns (content, new version)."""
    flag = load_flag(conn, user, flag_id)
    _require_creator_edit(flag, user)
    if replacement is None:
        result = fix_round(conn, user, flag.content_id, [flag_id], {})
    else:
        result = fix_round(conn, user, flag.content_id, [], {flag_id: replacement})
    if not result.applied:
        raise ActionError("This fix overlaps another change and could not be applied")
    return result.content_id, result.version_id


SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}


@dataclass
class FixCandidate:
    id: UUID
    severity: str
    start: int
    end: int
    fix: str
    edited: bool = False


@dataclass
class BulkFixResult:
    content_id: UUID
    version_id: UUID
    applied: list[UUID]
    skipped: list[UUID]


def _overlaps(a: FixCandidate, b: FixCandidate) -> bool:
    """Two fixes clash if their spans overlap. Insertions at the same point (several missing
    required lines) do not clash: they are added one after another."""
    if a.start == a.end and b.start == b.end:
        return False
    if a.start == a.end:
        return b.start < a.start < b.end
    if b.start == b.end:
        return a.start < b.start < a.end
    return a.start < b.end and b.start < a.end


def choose_fixes(candidates: list[FixCandidate]) -> tuple[list[FixCandidate], list[FixCandidate]]:
    """Pick a set of non-clashing fixes: most severe first, then the longer span.

    A fix identical to a chosen one (same span, same text) counts as chosen too, and so does
    another insertion at the same point. Returns (chosen, skipped), chosen in priority order.
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


@dataclass(frozen=True)
class Edit:
    """One change to the text: old [start, end) became `length` characters at `new_start`."""

    start: int
    end: int
    length: int
    new_start: int


def apply_fixes(text: str, fixes: list[FixCandidate]) -> str:
    """Apply non-clashing fixes from the end of the text backwards, so offsets stay valid."""
    return apply_fixes_mapped(text, fixes)[0]


def apply_fixes_mapped(text: str, fixes: list[FixCandidate]) -> tuple[str, list[Edit]]:
    """Like `apply_fixes`, and also return the edits needed to move positions to the new text.

    Insertions at the same point are joined with a space, in the order given."""
    replacement: dict[tuple[int, int], list[str]] = {}
    for f in fixes:
        parts = replacement.setdefault((f.start, f.end), [])
        if f.fix not in parts:
            parts.append(f.fix)
    lengths: dict[tuple[int, int], int] = {}
    for (start, end), parts in sorted(replacement.items(), reverse=True):
        before = len(text)
        text = apply_fix(text, start, end, " ".join(parts))
        lengths[(start, end)] = len(text) - before + (end - start)
    edits: list[Edit] = []
    shift = 0
    for start, end in sorted(lengths):
        edits.append(Edit(start, end, lengths[(start, end)], start + shift))
        shift += lengths[(start, end)] - (end - start)
    return text, edits


def map_position(pos: int, edits: list[Edit], *, is_end: bool = False) -> int:
    """Where an old position lands in the new text.

    A start moves past every edit that ends at or before it; an end does too, except for an
    insertion exactly at it (so a span never swallows text inserted right after it).
    """
    shift = 0
    for e in edits:
        before = e.end < pos or (e.end == pos and (not is_end or e.start < e.end))
        if before:
            shift += e.length - (e.end - e.start)
    return pos + shift


def _covering_edit(start: int, end: int, edits: list[Edit]) -> Edit | None:
    for e in edits:
        if e.start == e.end:
            if start < e.start < end:
                return e
        elif e.start < end and start < e.end or (start == end and e.start <= start < e.end):
            return e
    return None


def fix_round(
    conn: psycopg.Connection,
    user: CurrentUser,
    content_id: UUID,
    accept_ids: list[UUID] | None,
    edits: dict[UUID, str],
) -> BulkFixResult:
    """The creator's one fix round on a checked version.

    `accept_ids`: flags whose suggested fix to accept (None: every open flag with a fix that
    is not reworded in `edits`). `edits`: {flag id: the creator's own wording}. Everything is
    applied at once into one new version that is not checked again.
    """
    row = conn.execute(
        "select c.creator_id, c.status, c.format, c.brand_id, v.id, "
        "coalesce(v.extracted_text, ''), v.review_finished_at is not null "
        "from public.contents c join public.content_versions v on v.content_id = c.id "
        "where c.id = %s and c.brand_id = %s order by v.version_number desc limit 1",
        (content_id, user.brand_id),
    ).fetchone()
    if row is None or (user.role == "creator" and row[0] != user.id):
        raise NotFoundError("content")
    creator_id, content_status, fmt, brand_id, version_id, text, checked = row
    if user.role != "creator" or creator_id != user.id:
        raise ActionError("Only the content's creator can do this", 403)
    if content_status not in EDITABLE:
        raise ActionError(f"Content is {content_status}; flags can't change now")
    if fmt != "text":
        raise ActionError(
            f"Fixes can't be applied inside a {fmt}; upload a corrected file as a new version"
        )
    if not checked:
        raise ActionError(ALREADY_FIXED)

    with conn.cursor(row_factory=dict_row) as cur:
        flags = cur.execute(
            "select * from public.flags where version_id = %s order by created_at, id",
            (version_id,),
        ).fetchall()
        units = cur.execute(
            "select * from public.review_units where version_id = %s order by position",
            (version_id,),
        ).fetchall()
    open_flags = {f["id"]: f for f in flags if f["status"] == "open"}
    if accept_ids is None:
        accept_ids = [i for i, f in open_flags.items() if f["suggested_fix"] and i not in edits]
    wanted = list(dict.fromkeys([*accept_ids, *edits]))
    unknown = [i for i in wanted if i not in open_flags]
    if unknown:
        raise ActionError(
            f"{len(unknown)} of the chosen flags are not open on the latest version; "
            "reload and try again"
        )
    no_fix = [i for i in accept_ids if i not in edits and not open_flags[i]["suggested_fix"]]
    if no_fix:
        raise ActionError("Some chosen flags have no suggested fix; reword them instead", 422)

    candidates = []
    for fid in wanted:
        f = open_flags[fid]
        loc = f["location"] or {}
        start, end = loc.get("evidence_start"), loc.get("evidence_end")
        if start is None or end is None or text[start:end] != f["evidence"]:
            continue
        new = edits.get(fid, f["suggested_fix"])
        candidates.append(FixCandidate(fid, f["severity"], start, end, new, fid in edits))
    if not candidates:
        raise ActionError("There are no fixes to apply", 422)
    chosen, skipped = choose_fixes(candidates)
    new_text, text_edits = apply_fixes_mapped(text, chosen)
    by_id = {c.id: c for c in chosen}

    new_version = add_version(conn, user, content_id, new_text)
    _copy_units(conn, units, new_version, new_text, text_edits)
    _copy_flags(conn, user, flags, new_version, new_text, text_edits, by_id)
    for cand in chosen:  # the checked version keeps the decision too (history)
        conn.execute(
            "update public.flags set status = %s, resolution_note = %s, resolved_by = %s, "
            "resolved_at = now() where id = %s",
            (*_resolution(cand), user.id, cand.id),
        )
    audit(conn, brand_id=brand_id, actor_id=user.id, action="flag.fix_round",
          entity_type="content", entity_id=str(content_id),
          after={"accepted": [str(c.id) for c in chosen if not c.edited],
                 "edited": [str(c.id) for c in chosen if c.edited],
                 "skipped": [str(s.id) for s in skipped],
                 "new_version_id": str(new_version)})  # fmt: skip
    return BulkFixResult(content_id, new_version, [c.id for c in chosen], [s.id for s in skipped])


def fix_many(
    conn: psycopg.Connection,
    user: CurrentUser,
    content_id: UUID,
    flag_ids: list[UUID] | None,
    edits: dict[UUID, str] | None = None,
) -> BulkFixResult:
    """Accept the suggested fixes of `flag_ids` (None: all) plus any reworded ones."""
    return fix_round(conn, user, content_id, flag_ids, edits or {})


def _resolution(cand: FixCandidate) -> tuple[str, str | None]:
    return ("edited", f"Replaced with: {cand.fix}") if cand.edited else ("accepted", None)


def _move_location(loc: dict, edits: list[Edit]) -> dict:
    """Move a text location to the new text. A unit grows to take in text inserted at its end
    (missing lines are added there); an evidence span does not, and an empty span (a missing
    phrase) moves past insertions at its point. Ends never come before starts."""
    out = dict(loc)
    for start_key, end_key, unit in (("char_start", "char_end", True),
                                     ("evidence_start", "evidence_end", False)):  # fmt: skip
        start, end = out.get(start_key), out.get(end_key)
        if not (isinstance(start, int) and isinstance(end, int)):
            continue
        new_start = map_position(start, edits)
        new_end = map_position(end, edits, is_end=not unit and start != end)
        out[start_key], out[end_key] = new_start, max(new_start, new_end)
    return out


def _copy_units(
    conn: psycopg.Connection, units: list[dict], version_id: UUID, text: str, edits: list[Edit]
) -> None:
    for u in units:
        loc = _move_location(u["location"] or {}, edits)
        unit_text = (
            text[loc["char_start"] : loc["char_end"]]
            if isinstance(loc.get("char_start"), int) and isinstance(loc.get("char_end"), int)
            else u["text"]
        )
        conn.execute(
            "insert into public.review_units (version_id, brand_id, unit_id, position, text, "
            "location, retrieved_rules) values (%s, %s, %s, %s, %s, %s, %s)",
            (version_id, u["brand_id"], u["unit_id"], u["position"], unit_text,
             json.dumps(loc), u["retrieved_rules"]),
        )  # fmt: skip


def _copy_flags(
    conn: psycopg.Connection,
    user: CurrentUser,
    flags: list[dict],
    version_id: UUID,
    text: str,
    edits: list[Edit],
    chosen: dict[UUID, FixCandidate],
) -> None:
    """Copy the checked version's flags to the fixed version, positions moved to the new text."""
    for f in flags:
        loc = dict(f["location"] or {})
        evidence = f["evidence"]
        status, note, by, at = f["status"], f["resolution_note"], f["resolved_by"], f["resolved_at"]
        start, end = loc.get("evidence_start"), loc.get("evidence_end")
        has_span = isinstance(start, int) and isinstance(end, int)
        cand = chosen.get(f["id"])
        if cand is not None:
            edit = next(e for e in edits if (e.start, e.end) == (cand.start, cand.end))
            loc = _move_location(loc, edits)
            loc["evidence_start"], loc["evidence_end"] = (
                edit.new_start,
                edit.new_start + edit.length,
            )
            status, note = _resolution(cand)
            by, at = user.id, None
        elif has_span and (edit := _covering_edit(start, end, edits)) is not None:
            # Its words were rewritten by another fix: point at the new words, keep its status.
            loc = _move_location(loc, edits)
            loc["evidence_start"], loc["evidence_end"] = (
                edit.new_start,
                edit.new_start + edit.length,
            )
            evidence = text[edit.new_start : edit.new_start + edit.length]
        else:
            loc = _move_location(loc, edits)
        conn.execute(
            """insert into public.flags (version_id, brand_id, unit_id, source_type, source_id,
                   category, severity, evidence, explanation, suggested_fix, confidence,
                   location, layer, status, resolution_note, resolved_by, resolved_at)
               values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                       coalesce(%s, case when %s <> 'open' then now() end))""",
            (version_id, f["brand_id"], f["unit_id"], f["source_type"], f["source_id"],
             f["category"], f["severity"], evidence, f["explanation"], f["suggested_fix"],
             f["confidence"], json.dumps(loc), f["layer"], status, note, by, at, status),
        )  # fmt: skip


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
