"""Insights (task 13.1) and guideline health (task 13.2).

Guideline health: a rule's dismissal rate is dismissed flags / all its flags (latest version
of each content item, so a flag re-raised on every new version is counted once). A rule with
at least 5 flags and a dismissal rate of at least 40% is "probably unclear"; its most common
dismissal reasons are listed so the admin can rewrite it.
"""

from collections import Counter
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.api.deps import AdminOrManager, Conn, check_brand
from app.review.text import normalise

router = APIRouter(tags=["insights"])

UNCLEAR_RATE = 0.40
UNCLEAR_MIN_FLAGS = 5

# Each content item's latest version: flags there are the current state of that item.
_LATEST = """
latest as (
  select distinct on (v.content_id) v.id, v.content_id
  from public.content_versions v join public.contents c on c.id = v.content_id
  where c.brand_id = %(brand)s order by v.content_id, v.version_number desc
)"""


class WeekPoint(BaseModel):
    week: str
    flags: int
    high: int


class CountRow(BaseModel):
    key: str
    count: int


class RuleRow(BaseModel):
    rule_code: str
    text: str | None
    category: str | None
    flags: int
    open: int
    dismissed: int


class CreatorRow(BaseModel):
    creator: str
    items: int
    flags: int
    high: int


class Insights(BaseModel):
    days: int
    contents: int
    flags: int
    open_flags: int
    dismissal_rate: float | None
    avg_hours_to_approval: float | None
    approved: int
    sent_back: int
    submissions: int
    send_back_rate: float | None
    by_week: list[WeekPoint]
    by_category: list[CountRow]
    by_severity: list[CountRow]
    top_rules: list[RuleRow]
    by_creator: list[CreatorRow]


class HealthRow(BaseModel):
    source_id: str
    text: str | None
    category: str | None
    flags: int
    dismissed: int
    dismissal_rate: float
    probably_unclear: bool
    top_reasons: list[str]


@router.get("/brands/{brand_id}/insights", response_model=Insights)
def insights(
    brand_id: UUID, user: AdminOrManager, conn: Conn, days: int = Query(90, ge=7, le=365)
) -> Insights:
    check_brand(user, brand_id)
    p = {"brand": brand_id, "days": days}
    window = "f.created_at > now() - make_interval(days => %(days)s)"
    flags_cte = f"with {_LATEST}, fl as (select f.* from public.flags f join latest l on l.id = f.version_id where {window})"

    def rows(sql: str) -> list[tuple]:
        return conn.execute(sql, p).fetchall()

    totals = rows(f"""{flags_cte} select count(*), count(*) filter (where status = 'open'),
        count(*) filter (where status = 'dismissed'),
        count(*) filter (where status <> 'open') from fl""")[0]
    contents = rows("select count(*) from public.contents where brand_id = %(brand)s "
                    "and created_at > now() - make_interval(days => %(days)s)")[0][0]  # fmt: skip
    by_week = rows(f"""{flags_cte} select to_char(date_trunc('week', created_at), 'YYYY-MM-DD'),
        count(*), count(*) filter (where severity = 'high') from fl group by 1 order by 1""")
    by_cat = rows(f"{flags_cte} select category, count(*) from fl group by 1 order by 2 desc")
    by_sev = rows(f"{flags_cte} select severity, count(*) from fl group by 1 order by 2 desc")
    top = rows(f"""{flags_cte} select fl.source_id, r.text, r.category, count(*),
        count(*) filter (where fl.status = 'open'), count(*) filter (where fl.status = 'dismissed')
        from fl left join public.rules r on r.brand_id = fl.brand_id and r.rule_code = fl.source_id
        where fl.source_type = 'rule' group by 1, 2, 3 order by 4 desc limit 10""")
    creators = rows(f"""{flags_cte} select coalesce(p.display_name, 'Unknown'),
        count(distinct c.id), count(fl.id), count(fl.id) filter (where fl.severity = 'high')
        from fl join public.content_versions v on v.id = fl.version_id
        join public.contents c on c.id = v.content_id
        left join public.profiles p on p.id = c.creator_id group by 1 order by 3 desc""")
    timing = rows("""select avg(extract(epoch from (a.created_at - c.created_at)) / 3600), count(*)
        from public.contents c join public.audit_log a on a.entity_id = c.id::text
        and a.action = 'content.approve' where c.brand_id = %(brand)s
        and a.created_at > now() - make_interval(days => %(days)s)""")[0]
    loops = rows("""select count(*) filter (where action = 'content.request_changes'),
        count(*) filter (where action = 'content.submit_for_approval') from public.audit_log
        where brand_id = %(brand)s and created_at > now() - make_interval(days => %(days)s)""")[0]
    return Insights(
        days=days, contents=contents, flags=totals[0], open_flags=totals[1],
        dismissal_rate=(totals[2] / totals[3]) if totals[3] else None,
        avg_hours_to_approval=float(timing[0]) if timing[0] is not None else None,
        approved=timing[1], sent_back=loops[0], submissions=loops[1],
        send_back_rate=(loops[0] / loops[1]) if loops[1] else None,
        by_week=[WeekPoint(week=w, flags=n, high=h) for w, n, h in by_week],
        by_category=[CountRow(key=k, count=n) for k, n in by_cat],
        by_severity=[CountRow(key=k, count=n) for k, n in by_sev],
        top_rules=[RuleRow(rule_code=c, text=t, category=g, flags=n, open=o, dismissed=d)
                   for c, t, g, n, o, d in top],
        by_creator=[CreatorRow(creator=c, items=i, flags=n, high=h) for c, i, n, h in creators],
    )  # fmt: skip


def health_rows(rows: list[tuple], reasons: dict[str, list[str]]) -> list[HealthRow]:
    """Pure: (source_id, text, category, flags, dismissed) + dismissal notes -> health rows,
    least healthy first."""
    out = []
    for source_id, text, category, flags, dismissed in rows:
        rate = dismissed / flags if flags else 0.0
        common = Counter(normalise(r) for r in reasons.get(source_id, []) if r.strip())
        originals = {normalise(r): r.strip() for r in reasons.get(source_id, [])}
        out.append(HealthRow(
            source_id=source_id, text=text, category=category, flags=flags, dismissed=dismissed,
            dismissal_rate=round(rate, 3),
            probably_unclear=flags >= UNCLEAR_MIN_FLAGS and rate >= UNCLEAR_RATE,
            top_reasons=[originals[k] for k, _ in common.most_common(3)],
        ))  # fmt: skip
    out.sort(key=lambda h: (not h.probably_unclear, -h.dismissal_rate, -h.flags))
    return out


@router.get("/brands/{brand_id}/guideline-health", response_model=list[HealthRow])
def guideline_health(brand_id: UUID, user: AdminOrManager, conn: Conn) -> list[HealthRow]:
    check_brand(user, brand_id)
    p = {"brand": brand_id}
    rows = conn.execute(f"""with {_LATEST}
        select f.source_id, r.text, r.category, count(*), count(*) filter (where f.status = 'dismissed')
        from public.flags f join latest l on l.id = f.version_id
        left join public.rules r on r.brand_id = f.brand_id and r.rule_code = f.source_id
        where f.source_type in ('rule', 'policy') group by 1, 2, 3""", p).fetchall()  # fmt: skip
    notes: dict[str, list[str]] = {}
    for source_id, note in conn.execute(f"""with {_LATEST}
        select f.source_id, f.resolution_note from public.flags f join latest l on l.id = f.version_id
        where f.status = 'dismissed' and f.resolution_note is not null""", p).fetchall():  # fmt: skip
        notes.setdefault(source_id, []).append(note)
    return health_rows(rows, notes)
