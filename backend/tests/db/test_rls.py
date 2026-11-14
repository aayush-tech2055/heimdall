"""db/policies.sql: row-level security as seen by Supabase API callers.

Setup runs as the database owner; each check then switches to the `authenticated` role with
a JWT `sub` (or to `anon`), exactly as PostgREST does for the frontend.
"""

from dataclasses import dataclass
from uuid import UUID

import psycopg
import pytest
from psycopg import errors

from tests.db.helpers import (
    as_user,
    insert_flag,
    insert_rule,
    insert_unit,
    make_brand,
    make_content,
    make_user,
)

pytestmark = pytest.mark.db


@dataclass
class World:
    brand: UUID
    other_brand: UUID
    admin: UUID
    manager: UUID
    creator_a: UUID
    creator_b: UUID
    other_admin: UUID
    content_a: UUID
    version_a: UUID
    content_b: UUID
    version_b: UUID
    other_content: UUID


@pytest.fixture
def world(db: psycopg.Connection) -> World:
    brand, other_brand = make_brand(db), make_brand(db)
    admin = make_user(db, brand, "admin")
    manager = make_user(db, brand, "manager")
    creator_a = make_user(db, brand, "creator")
    creator_b = make_user(db, brand, "creator")
    other_admin = make_user(db, other_brand, "admin")
    other_creator = make_user(db, other_brand, "creator")

    content_a, version_a = make_content(db, brand, creator_a, "A's post")
    content_b, version_b = make_content(db, brand, creator_b, "B's post")
    other_content, other_version = make_content(db, other_brand, other_creator, "Other brand")
    for b, v, author in (
        (brand, version_a, creator_a),
        (brand, version_b, creator_b),
        (other_brand, other_version, other_creator),
    ):
        insert_unit(db, b, v)
        flag = insert_flag(db, b, v)
        db.execute(
            "insert into public.comments (version_id, brand_id, author_id, body, flag_id) "
            "values (%s, %s, %s, 'Fixed.', %s)",
            (v, b, author, flag),
        )
        db.execute(
            "insert into public.dropped_flags (version_id, brand_id, payload, reason) "
            "values (%s, %s, '{}', 'evidence_not_found')",
            (v, b),
        )
        db.execute(
            "insert into public.ai_calls (brand_id, provider, model, purpose, "
            "content_version_id, ok) values (%s, 'gemini', 'm', 'judge', %s, true)",
            (b, v),
        )
    insert_rule(db, brand, "R-001")
    insert_rule(db, other_brand, "R-001")
    db.execute(
        "insert into public.audit_log (brand_id, actor_id, action, entity_type, entity_id) "
        "values (%s, %s, 'content.submit', 'content', %s)",
        (brand, creator_a, str(content_a)),
    )
    return World(
        brand, other_brand, admin, manager, creator_a, creator_b, other_admin,
        content_a, version_a, content_b, version_b, other_content,
    )  # fmt: skip


def _ids(conn: psycopg.Connection, sql: str) -> set:
    return {row[0] for row in conn.execute(sql).fetchall()}


# --- Done when: a creator cannot read another creator's content -----------------------------


def test_creator_sees_only_their_own_content(db, world):
    with as_user(db, world.creator_a):
        assert _ids(db, "select id from public.contents") == {world.content_a}
        assert _ids(db, "select id from public.content_versions") == {world.version_a}
        assert _ids(db, "select version_id from public.review_units") == {world.version_a}
        assert _ids(db, "select version_id from public.flags") == {world.version_a}
        assert _ids(db, "select version_id from public.comments") == {world.version_a}
        assert _ids(db, "select content_version_id from public.ai_calls") == {world.version_a}


def test_creator_cannot_fetch_another_creators_content_by_id(db, world):
    with as_user(db, world.creator_a):
        row = db.execute(
            "select title from public.contents where id = %s", (world.content_b,)
        ).fetchone()
        flags = db.execute(
            "select count(*) from public.flags where version_id = %s", (world.version_b,)
        ).fetchone()[0]
    assert row is None
    assert flags == 0


@pytest.mark.parametrize("role", ["manager", "admin"])
def test_manager_and_admin_see_all_content_of_their_brand_only(db, world, role):
    with as_user(db, getattr(world, role)):
        assert _ids(db, "select id from public.contents") == {world.content_a, world.content_b}
        assert _ids(db, "select version_id from public.flags") == {
            world.version_a,
            world.version_b,
        }
        assert len(_ids(db, "select id from public.dropped_flags")) == 2
        assert len(_ids(db, "select id from public.audit_log")) == 1


def test_creator_cannot_read_dropped_flags_or_audit_log(db, world):
    with as_user(db, world.creator_a):
        assert _ids(db, "select id from public.dropped_flags") == set()
        assert _ids(db, "select id from public.audit_log") == set()


def test_other_brand_sees_nothing_of_this_brand(db, world):
    with as_user(db, world.other_admin):
        assert _ids(db, "select id from public.contents") == {world.other_content}
        assert _ids(db, "select brand_id from public.rules") == {world.other_brand}
        assert _ids(db, "select id from public.brands") == {world.other_brand}
        assert world.brand not in _ids(db, "select brand_id from public.profiles")


def test_anonymous_caller_sees_nothing(db, world):
    with as_user(db, None):
        for table in ("brands", "profiles", "rules", "contents", "flags", "ai_calls"):
            assert db.execute(f"select count(*) from public.{table}").fetchone()[0] == 0


# --- Only admins write rules and facts ------------------------------------------------------


def test_every_brand_member_can_read_rules(db, world):
    with as_user(db, world.creator_a):
        assert _ids(db, "select rule_code from public.rules") == {"R-001"}


@pytest.mark.parametrize("role", ["creator_a", "manager"])
def test_non_admin_cannot_insert_rules_or_facts(db, world, role):
    with as_user(db, getattr(world, role)):
        with pytest.raises(errors.InsufficientPrivilege), db.transaction():
            insert_rule(db, world.brand, "R-002")
        with pytest.raises(errors.InsufficientPrivilege), db.transaction():
            db.execute(
                "insert into public.facts (brand_id, fact_code, entity, attribute, value, "
                "statement) values (%s, 'F-001', 'Pro plan', 'price', '599', 'Pro is 599.')",
                (world.brand,),
            )


@pytest.mark.parametrize("role", ["creator_a", "manager"])
def test_non_admin_updates_and_deletes_of_rules_change_nothing(db, world, role):
    with as_user(db, getattr(world, role)):
        updated = db.execute("update public.rules set text = 'Hacked.' returning id").fetchall()
        deleted = db.execute("delete from public.rules returning id").fetchall()
    assert updated == [] and deleted == []
    assert db.execute(
        "select text from public.rules where brand_id = %s", (world.brand,)
    ).fetchone() == ("Be warm.",)


def test_admin_writes_rules_and_facts_in_own_brand_only(db, world):
    with as_user(db, world.admin):
        insert_rule(db, world.brand, "R-002")
        db.execute(
            "insert into public.facts (brand_id, fact_code, entity, attribute, value, statement) "
            "values (%s, 'F-001', 'Pro plan', 'price', '599', 'Pro costs 599 a month.')",
            (world.brand,),
        )
        updated = db.execute(
            "update public.rules set status = 'approved' where rule_code = 'R-002' returning id"
        ).fetchall()
        assert len(updated) == 1
        with pytest.raises(errors.InsufficientPrivilege), db.transaction():
            insert_rule(db, world.other_brand, "R-003")


# --- Workflow tables are read-only through the API ------------------------------------------


def test_creator_cannot_change_status_or_resolve_flags_directly(db, world):
    with as_user(db, world.creator_a):
        assert (
            db.execute("update public.contents set status = 'approved' returning id").fetchall()
            == []
        )
        assert (
            db.execute(
                "update public.flags set status = 'dismissed', resolution_note = 'x' returning id"
            ).fetchall()
            == []
        )
        with pytest.raises(errors.InsufficientPrivilege), db.transaction():
            db.execute(
                "insert into public.contents (brand_id, title, format, creator_id) "
                "values (%s, 'Sneaky', 'text', %s)",
                (world.brand, world.creator_a),
            )


def test_user_cannot_change_their_own_role(db, world):
    with as_user(db, world.creator_a):
        updated = db.execute(
            "update public.profiles set role = 'admin' where id = %s returning id",
            (world.creator_a,),
        ).fetchall()
    assert updated == []
    role = db.execute("select role from public.profiles where id = %s", (world.creator_a,))
    assert role.fetchone() == ("creator",)


def test_manager_can_record_an_exception_but_creator_cannot(db, world):
    sql = (
        "insert into public.approved_exceptions (brand_id, source_id, evidence, reason) "
        "values (%s, 'R-001', 'Hello', 'Approved campaign wording')"
    )
    with as_user(db, world.manager):
        db.execute(sql, (world.brand,))
    with (
        as_user(db, world.creator_a),
        pytest.raises(errors.InsufficientPrivilege),
        db.transaction(),
    ):
        db.execute(sql, (world.brand,))
