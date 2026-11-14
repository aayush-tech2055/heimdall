"""scripts/seed.py against the real database, with a fake Supabase Auth admin (rolled back)."""

import uuid

import psycopg
import pytest

from scripts.seed import DEFAULT_CONFIG, load_config, run_seed

pytestmark = pytest.mark.db


class FakeAuthAdmin:
    """Creates auth.users rows inside the test transaction instead of calling Supabase."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn
        self.created: list[str] = []

    def find_user_id(self, email: str) -> uuid.UUID | None:
        row = self.conn.execute(
            "select id from auth.users where lower(email) = lower(%s)", (email,)
        ).fetchone()
        return row[0] if row else None

    def create_user(self, email: str, password: str, display_name: str) -> uuid.UUID:
        user_id = uuid.uuid4()
        self.conn.execute(
            "insert into auth.users (id, email, aud, role) "
            "values (%s, %s, 'authenticated', 'authenticated')",
            (user_id, email),
        )
        self.created.append(email)
        return user_id


@pytest.fixture
def config():
    # A unique slug and emails so the test never collides with a real seeded brand.
    cfg = load_config(DEFAULT_CONFIG)
    tag = uuid.uuid4().hex[:8]
    cfg.brand.slug = f"{cfg.brand.slug}-{tag}"
    for user in cfg.users:
        user.email = user.email.replace("@", f"+{tag}@")
    return cfg


def test_seed_creates_brand_settings_and_one_profile_per_user(db, config):
    auth = FakeAuthAdmin(db)
    user_ids = run_seed(db, auth, config, "password123")

    brand_id, name = db.execute(
        "select id, name from public.brands where slug = %s", (config.brand.slug,)
    ).fetchone()
    assert name == config.brand.name
    terms, claim_policy = db.execute(
        "select confidential_terms, claim_policy_enabled from public.brand_settings "
        "where brand_id = %s",
        (brand_id,),
    ).fetchone()
    assert terms == config.settings.confidential_terms
    assert claim_policy is True
    roles = dict(
        db.execute(
            "select id, role from public.profiles where brand_id = %s", (brand_id,)
        ).fetchall()
    )
    assert roles == {user_ids[u.email]: u.role for u in config.users}
    assert set(roles.values()) == {"admin", "manager", "creator"}


def test_seed_is_idempotent(db, config):
    auth = FakeAuthAdmin(db)
    first = run_seed(db, auth, config, "password123")
    config.users[0].display_name = "Renamed"
    second = run_seed(db, auth, config, "password123")

    assert first == second
    assert len(auth.created) == len(config.users)  # users created once, then reused
    count = db.execute(
        "select count(*) from public.brands where slug = %s", (config.brand.slug,)
    ).fetchone()[0]
    assert count == 1
    name = db.execute(
        "select display_name from public.profiles where id = %s",
        (first[config.users[0].email],),
    ).fetchone()[0]
    assert name == "Renamed"
