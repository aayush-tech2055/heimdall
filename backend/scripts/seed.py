"""Seed one fictional test brand plus a user for each role (task 2.3).

    cd backend
    .venv/bin/python -m scripts.seed                 # uses ../db/seed.json
    .venv/bin/python -m scripts.seed --config path/to/seed.json

Needs DATABASE_URL, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY and SEED_USER_PASSWORD in
backend/.env. Safe to re-run: the brand, settings and profiles are upserted, and existing
auth users are reused (their passwords are left unchanged).

Rules and facts are not seeded here: they go through guideline ingestion (M4) and the fact
store (M5) so that they are embedded and verified like real data.
"""

import argparse
import json
import sys
import uuid
from pathlib import Path
from typing import Literal, Protocol

import httpx
import psycopg
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.config import get_settings

DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "db" / "seed.json"
ROLES = ("admin", "manager", "creator")


class SeedBrand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    slug: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")


class SeedSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confidential_terms: list[str] = []
    claim_policy_enabled: bool = True
    readability_target: float | None = None


class SeedUser(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    role: Literal["admin", "manager", "creator"]
    display_name: str = Field(min_length=1)


class SeedConfig(BaseModel):
    """The contents of db/seed.json."""

    model_config = ConfigDict(extra="forbid")

    brand: SeedBrand
    settings: SeedSettings = SeedSettings()
    users: list[SeedUser]

    @model_validator(mode="after")
    def _every_role_once_and_unique_emails(self) -> "SeedConfig":
        emails = [u.email.lower() for u in self.users]
        if len(emails) != len(set(emails)):
            raise ValueError("user emails must be unique")
        missing = set(ROLES) - {u.role for u in self.users}
        if missing:
            raise ValueError(f"seed needs at least one user per role; missing: {sorted(missing)}")
        return self


def load_config(path: Path) -> SeedConfig:
    """Read and validate a seed file."""
    return SeedConfig.model_validate(json.loads(path.read_text(encoding="utf-8")))


class AuthAdmin(Protocol):
    """The two Supabase Auth admin operations the seed needs."""

    def find_user_id(self, email: str) -> uuid.UUID | None: ...

    def create_user(self, email: str, password: str, display_name: str) -> uuid.UUID: ...


class SupabaseAuthAdmin:
    """Supabase Auth admin API (`/auth/v1/admin/users`), authorised with the service role key."""

    def __init__(self, supabase_url: str, service_role_key: str) -> None:
        self._client = httpx.Client(
            base_url=f"{supabase_url.rstrip('/')}/auth/v1/admin",
            headers={"apikey": service_role_key, "Authorization": f"Bearer {service_role_key}"},
            timeout=30,
        )
        self._by_email: dict[str, uuid.UUID] | None = None

    def _load_users(self) -> dict[str, uuid.UUID]:
        users: dict[str, uuid.UUID] = {}
        page = 1
        while True:
            resp = self._client.get("/users", params={"page": page, "per_page": 1000})
            resp.raise_for_status()
            batch = resp.json().get("users", [])
            users.update({u["email"].lower(): uuid.UUID(u["id"]) for u in batch if u.get("email")})
            if len(batch) < 1000:
                return users
            page += 1

    def find_user_id(self, email: str) -> uuid.UUID | None:
        if self._by_email is None:
            self._by_email = self._load_users()
        return self._by_email.get(email.lower())

    def create_user(self, email: str, password: str, display_name: str) -> uuid.UUID:
        resp = self._client.post(
            "/users",
            json={
                "email": email,
                "password": password,
                "email_confirm": True,
                "user_metadata": {"display_name": display_name},
            },
        )
        if resp.is_error:
            raise RuntimeError(f"creating {email} failed: {resp.status_code} {resp.text}")
        user_id = uuid.UUID(resp.json()["id"])
        if self._by_email is not None:
            self._by_email[email.lower()] = user_id
        return user_id


def run_seed(
    conn: psycopg.Connection, auth: AuthAdmin, config: SeedConfig, password: str
) -> dict[str, uuid.UUID]:
    """Upsert the brand, its settings, the auth users and their profiles.

    Returns {email: user_id}. Does not commit; the caller owns the transaction.
    """
    brand_id = conn.execute(
        "insert into public.brands (name, slug) values (%s, %s) "
        "on conflict (slug) do update set name = excluded.name returning id",
        (config.brand.name, config.brand.slug),
    ).fetchone()[0]

    s = config.settings
    conn.execute(
        "insert into public.brand_settings "
        "(brand_id, confidential_terms, claim_policy_enabled, readability_target) "
        "values (%s, %s, %s, %s) on conflict (brand_id) do update set "
        "confidential_terms = excluded.confidential_terms, "
        "claim_policy_enabled = excluded.claim_policy_enabled, "
        "readability_target = excluded.readability_target",
        (brand_id, s.confidential_terms, s.claim_policy_enabled, s.readability_target),
    )

    user_ids: dict[str, uuid.UUID] = {}
    for user in config.users:
        user_id = auth.find_user_id(user.email)
        if user_id is None:
            user_id = auth.create_user(user.email, password, user.display_name)
        conn.execute(
            "insert into public.profiles (id, brand_id, role, display_name) "
            "values (%s, %s, %s, %s) on conflict (id) do update set "
            "brand_id = excluded.brand_id, role = excluded.role, "
            "display_name = excluded.display_name",
            (user_id, brand_id, user.role, user.display_name),
        )
        user_ids[user.email] = user_id
    return user_ids


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args(argv)

    settings = get_settings()
    missing = [
        name
        for name, value in (
            ("DATABASE_URL", settings.database_url),
            ("SUPABASE_URL", settings.supabase_url),
            ("SUPABASE_SERVICE_ROLE_KEY", settings.supabase_service_role_key),
            ("SEED_USER_PASSWORD", settings.seed_user_password),
        )
        if not value
    ]
    if missing:
        print(f"Missing in backend/.env: {', '.join(missing)}", file=sys.stderr)
        return 1
    if len(settings.seed_user_password) < 8:
        print("SEED_USER_PASSWORD must be at least 8 characters", file=sys.stderr)
        return 1

    config = load_config(args.config)
    auth = SupabaseAuthAdmin(settings.supabase_url, settings.supabase_service_role_key)
    with psycopg.connect(settings.database_url) as conn:  # commits on clean exit
        user_ids = run_seed(conn, auth, config, settings.seed_user_password)

    print(f"Seeded brand '{config.brand.name}' ({config.brand.slug}) with:")
    for user in config.users:
        print(f"  {user.role:<8} {user.email:<32} {user_ids[user.email]}")
    print("Sign in with these emails and SEED_USER_PASSWORD from backend/.env.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
