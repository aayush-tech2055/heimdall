"""Accounts, roles and teams.

* Sign-up (email and password) and onboarding (after Google sign-in): the person picks a role
  (admin, manager or creator). An admin names a brand and owns it.
* `/me`: the signed-in person, their teams (brands) and their active brand.
* Teams: an admin adds creators and managers to their brand (a creator can follow several
  admins' brands and switches between them); a creator checks a manager's email before
  submitting to them.
"""

import re
import secrets
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query, status
from psycopg.rows import dict_row
from pydantic import BaseModel, Field, model_validator

from app.api.deps import Admin, Conn, Ident, User, check_brand
from app.api.ratelimit import limited_by_ip
from app.audit import audit
from app.auth_admin import AuthAdminError, SupabaseAuthAdmin, get_auth_admin

router = APIRouter(tags=["accounts"])

Role = Literal["admin", "manager", "creator"]
EMAIL_RE = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class Membership(BaseModel):
    brand_id: UUID
    brand_name: str
    role: Role


class Me(BaseModel):
    id: UUID
    email: str | None
    display_name: str | None
    role: Role | None
    brand_id: UUID | None
    brand_name: str | None
    memberships: list[Membership] = []
    needs_onboarding: bool = False


class Profile(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)
    role: Role
    brand_name: str | None = Field(default=None, max_length=80)

    @model_validator(mode="after")
    def _admin_names_a_brand(self) -> "Profile":
        if self.role == "admin" and not (self.brand_name and self.brand_name.strip()):
            raise ValueError("An admin must name their brand")
        return self


class SignupIn(Profile):
    email: str = Field(pattern=EMAIL_RE, max_length=200)
    password: str = Field(min_length=6, max_length=72)


class ActiveBrand(BaseModel):
    brand_id: UUID


class Member(BaseModel):
    user_id: UUID
    email: str | None
    display_name: str | None
    role: Role
    added_at: datetime


class Person(BaseModel):
    user_id: UUID
    email: str | None
    display_name: str | None
    role: Role


class AddMember(BaseModel):
    user_id: UUID


class ManagerCheck(BaseModel):
    found: bool
    display_name: str | None = None
    message: str


# --- helpers ------------------------------------------------------------------------------


def _slug(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "brand"
    return f"{base}-{secrets.token_hex(2)}"


def create_profile(conn: psycopg.Connection, user_id: UUID, p: Profile) -> None:
    """Create the profile; an admin also gets their own brand, settings and team."""
    conn.execute(
        "insert into public.profiles (id, role, display_name) values (%s, %s, %s)",
        (user_id, p.role, p.display_name.strip()),
    )
    if p.role != "admin":
        return
    brand_id = conn.execute(
        "insert into public.brands (name, slug, owner_id) values (%s, %s, %s) returning id",
        (p.brand_name.strip(), _slug(p.brand_name), user_id),
    ).fetchone()[0]
    conn.execute(
        "insert into public.brand_settings (brand_id, confidential_terms, claim_policy_enabled, "
        "readability_target) values (%s, '{}', true, 60)",
        (brand_id,),
    )
    conn.execute(
        "insert into public.brand_members (brand_id, user_id, role, added_by) "
        "values (%s, %s, 'admin', %s)",
        (brand_id, user_id, user_id),
    )
    conn.execute("update public.profiles set brand_id = %s where id = %s", (brand_id, user_id))
    audit(conn, brand_id=brand_id, actor_id=user_id, action="brand.create",
          entity_type="brand", entity_id=str(brand_id), after={"name": p.brand_name})  # fmt: skip


def _me(conn: psycopg.Connection, user_id: UUID, email: str | None) -> Me:
    with conn.cursor(row_factory=dict_row) as cur:
        prof = cur.execute(
            "select role, brand_id, display_name from public.profiles where id = %s", (user_id,)
        ).fetchone()
        if prof is None:
            return Me(id=user_id, email=email, display_name=None, role=None, brand_id=None,
                      brand_name=None, needs_onboarding=True)  # fmt: skip
        teams = cur.execute(
            "select m.brand_id, b.name as brand_name, m.role from public.brand_members m "
            "join public.brands b on b.id = m.brand_id where m.user_id = %s order by b.name",
            (user_id,),
        ).fetchall()
    memberships = [Membership(**t) for t in teams]
    active = next((m for m in memberships if m.brand_id == prof["brand_id"]), None)
    if active is None and memberships:  # first team, or the old one was removed
        active = memberships[0]
        conn.execute("update public.profiles set brand_id = %s where id = %s",
                     (active.brand_id, user_id))  # fmt: skip
    return Me(id=user_id, email=email, display_name=prof["display_name"], role=prof["role"],
              brand_id=active.brand_id if active else None,
              brand_name=active.brand_name if active else None,
              memberships=memberships)  # fmt: skip


# --- sign-up, onboarding, me --------------------------------------------------------------


@router.post(
    "/auth/signup",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(limited_by_ip("sign-up", 10))],
)
def signup(
    body: SignupIn,
    conn: Conn,
    auth: Annotated[SupabaseAuthAdmin, Depends(get_auth_admin)],
) -> dict:
    """Create an account with a role. The client then signs in with the same email/password."""
    try:
        user_id = UUID(auth.create_user(body.email.strip(), body.password, body.display_name))
    except AuthAdminError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
    create_profile(conn, user_id, body)
    conn.commit()
    return {"user_id": str(user_id), "role": body.role}


@router.post("/me/onboard", response_model=Me)
def onboard(body: Profile, conn: Conn, ident: Ident) -> Me:
    """First sign-in with Google: pick a role (and an admin names their brand)."""
    exists = conn.execute(
        "select 1 from public.profiles where id = %s", (ident.user_id,)
    ).fetchone()
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "This account already has a role")
    create_profile(conn, ident.user_id, body)
    conn.commit()
    return _me(conn, ident.user_id, ident.email)


@router.get("/me", response_model=Me)
def me(conn: Conn, ident: Ident) -> Me:
    out = _me(conn, ident.user_id, ident.email)
    conn.commit()
    return out


@router.post("/me/active-brand", response_model=Me)
def set_active_brand(body: ActiveBrand, user: User, conn: Conn) -> Me:
    """Switch which brand's guidelines you work under (you must be on its team)."""
    ok = conn.execute(
        "select 1 from public.brand_members where user_id = %s and brand_id = %s",
        (user.id, body.brand_id),
    ).fetchone()
    if not ok:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You are not on this brand's team")
    conn.execute("update public.profiles set brand_id = %s where id = %s", (body.brand_id, user.id))
    conn.commit()
    return _me(conn, user.id, user.email)


# --- teams --------------------------------------------------------------------------------


@router.get("/brands/{brand_id}/members", response_model=list[Member])
def list_members(brand_id: UUID, user: Admin, conn: Conn) -> list[Member]:
    check_brand(user, brand_id)
    with conn.cursor(row_factory=dict_row) as cur:
        rows = cur.execute(
            "select m.user_id, u.email, p.display_name, m.role, m.created_at as added_at "
            "from public.brand_members m join public.profiles p on p.id = m.user_id "
            "left join auth.users u on u.id = m.user_id where m.brand_id = %s "
            "order by array_position(array['admin','manager','creator'], m.role), p.display_name",
            (brand_id,),
        ).fetchall()
    return [Member(**r) for r in rows]


@router.get("/brands/{brand_id}/directory", response_model=list[Person])
def directory(
    brand_id: UUID,
    user: Admin,
    conn: Conn,
    role: Annotated[Literal["creator", "manager"], Query()],
    q: Annotated[str, Query(max_length=100)] = "",
) -> list[Person]:
    """Creators or managers on Heimdall who are not yet on this brand's team."""
    check_brand(user, brand_id)
    like = f"%{q.strip()}%"
    with conn.cursor(row_factory=dict_row) as cur:
        rows = cur.execute(
            "select p.id as user_id, u.email, p.display_name, p.role from public.profiles p "
            "left join auth.users u on u.id = p.id "
            "where p.role = %s and not exists (select 1 from public.brand_members m "
            "where m.brand_id = %s and m.user_id = p.id) "
            "and (%s = '%%%%' or u.email ilike %s or p.display_name ilike %s) "
            "order by p.display_name nulls last limit 50",
            (role, brand_id, like, like, like),
        ).fetchall()
    return [Person(**r) for r in rows]


@router.post("/brands/{brand_id}/members", response_model=Member, status_code=201)
def add_member(brand_id: UUID, body: AddMember, user: Admin, conn: Conn) -> Member:
    check_brand(user, brand_id)
    row = conn.execute("select role from public.profiles where id = %s", (body.user_id,)).fetchone()
    if row is None or row[0] not in ("creator", "manager"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No creator or manager with this account")
    conn.execute(
        "insert into public.brand_members (brand_id, user_id, role, added_by) "
        "values (%s, %s, %s, %s) on conflict do nothing",
        (brand_id, body.user_id, row[0], user.id),
    )
    conn.execute(
        "update public.profiles set brand_id = %s where id = %s and brand_id is null",
        (brand_id, body.user_id),
    )
    audit(conn, brand_id=brand_id, actor_id=user.id, action="team.add", entity_type="profile",
          entity_id=str(body.user_id), after={"role": row[0]})  # fmt: skip
    conn.commit()
    return next(m for m in list_members(brand_id, user, conn) if m.user_id == body.user_id)


@router.delete("/brands/{brand_id}/members/{user_id}", status_code=204)
def remove_member(brand_id: UUID, user_id: UUID, user: Admin, conn: Conn) -> None:
    check_brand(user, brand_id)
    row = conn.execute(
        "select role from public.brand_members where brand_id = %s and user_id = %s",
        (brand_id, user_id),
    ).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not on this team")
    if row[0] == "admin":
        raise HTTPException(status.HTTP_409_CONFLICT, "Admins cannot be removed from their brand")
    conn.execute(
        "delete from public.brand_members where brand_id = %s and user_id = %s", (brand_id, user_id)
    )
    audit(conn, brand_id=brand_id, actor_id=user.id, action="team.remove",
          entity_type="profile", entity_id=str(user_id), after=None)  # fmt: skip
    conn.commit()


def find_manager(conn: psycopg.Connection, brand_id: UUID, email: str) -> tuple[UUID, str] | None:
    """A manager on this brand's team with this email: (id, display name)."""
    row = conn.execute(
        "select p.id, p.display_name from auth.users u join public.profiles p on p.id = u.id "
        "join public.brand_members m on m.user_id = p.id and m.brand_id = %s "
        "where lower(u.email) = lower(%s) and m.role = 'manager'",
        (brand_id, email.strip()),
    ).fetchone()
    return (row[0], row[1] or email) if row else None


@router.get("/brands/{brand_id}/managers/check", response_model=ManagerCheck)
def check_manager(
    brand_id: UUID, user: User, conn: Conn, email: Annotated[str, Query(max_length=200)]
) -> ManagerCheck:
    """Live check while a creator types the manager's email."""
    check_brand(user, brand_id)
    if not re.fullmatch(EMAIL_RE, email.strip()):
        return ManagerCheck(found=False, message="Type the manager's full email address")
    found = find_manager(conn, brand_id, email)
    if not found:
        return ManagerCheck(found=False, message="No manager with this email on this brand's team")
    return ManagerCheck(found=True, display_name=found[1], message=f"{found[1]} · manager")
