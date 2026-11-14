"""db/schema.sql: tables exist, RLS is on, and the constraints encode the locked decisions."""

import json

import psycopg
import pytest
from psycopg import errors

from tests.db.helpers import make_brand, make_content, make_user

pytestmark = pytest.mark.db

TABLES = {
    "brands", "profiles", "brand_settings", "rules", "facts", "assets", "approved_exceptions",
    "contents", "content_versions", "review_units", "flags", "dropped_flags", "comments",
    "audit_log", "ai_calls",
}  # fmt: skip


def _insert_rule(conn: psycopg.Connection, brand_id, code: str = "R-001", **cols) -> None:
    values = {"brand_id": brand_id, "rule_code": code, "category": "tone", "text": "Be warm."}
    values.update(cols)
    names = ", ".join(values)
    marks = ", ".join(["%s"] * len(values))
    conn.execute(f"insert into public.rules ({names}) values ({marks})", list(values.values()))


def _insert_unit(conn: psycopg.Connection, brand_id, version_id, unit_id: str = "u1") -> None:
    conn.execute(
        "insert into public.review_units (version_id, brand_id, unit_id, position, text, location) "
        "values (%s, %s, %s, 0, 'Hello world.', %s)",
        (
            version_id,
            brand_id,
            unit_id,
            json.dumps({"paragraph": 0, "char_start": 0, "char_end": 12}),
        ),
    )


def _insert_flag(conn: psycopg.Connection, brand_id, version_id, unit_id: str = "u1", **cols):
    values = {
        "version_id": version_id, "brand_id": brand_id, "unit_id": unit_id,
        "source_type": "rule", "source_id": "R-001", "category": "tone", "severity": "low",
        "evidence": "Hello", "explanation": "Too casual.", "confidence": 0.8,
        "location": json.dumps({"paragraph": 0, "char_start": 0, "char_end": 12,
                                "evidence_start": 0, "evidence_end": 5}),
        "layer": "guidelines",
    }  # fmt: skip
    values.update(cols)
    names = ", ".join(values)
    marks = ", ".join(["%s"] * len(values))
    return conn.execute(
        f"insert into public.flags ({names}) values ({marks}) returning id", list(values.values())
    ).fetchone()[0]


def test_all_tables_exist_with_rls_enabled(db):
    rows = db.execute(
        "select tablename, rowsecurity from pg_tables where schemaname = 'public'"
    ).fetchall()
    found = dict(rows)
    assert set(found) >= TABLES
    assert all(found[t] for t in TABLES), "every table must have row-level security enabled"


def test_rule_tsvector_is_generated(db):
    brand = make_brand(db)
    _insert_rule(db, brand, text="Never call the product cheap.")
    tsv = db.execute("select tsv::text from public.rules where brand_id = %s", (brand,)).fetchone()
    assert "'cheap'" in tsv[0]


def test_deterministic_rule_needs_kind_and_terms(db):
    brand = make_brand(db)
    with pytest.raises(errors.CheckViolation), db.transaction():
        _insert_rule(db, brand, check_type="deterministic", det_kind="banned_terms")
    with pytest.raises(errors.CheckViolation), db.transaction():
        _insert_rule(db, brand, check_type="semantic", det_kind="banned_terms", terms=["cheap"])
    _insert_rule(db, brand, check_type="deterministic", det_kind="banned_terms", terms=["cheap"])


def test_rule_code_format_and_uniqueness_per_brand(db):
    brand, other = make_brand(db), make_brand(db)
    with pytest.raises(errors.CheckViolation), db.transaction():
        _insert_rule(db, brand, code="12")
    _insert_rule(db, brand, code="R-012")
    _insert_rule(db, other, code="R-012")  # same code in another brand is fine
    with pytest.raises(errors.UniqueViolation), db.transaction():
        _insert_rule(db, brand, code="R-012")


def test_embedding_must_have_768_dimensions(db):
    brand = make_brand(db)
    with pytest.raises(psycopg.Error), db.transaction():
        _insert_rule(db, brand, embedding="[0.1, 0.2, 0.3]")
    _insert_rule(db, brand, embedding=str([0.0] * 767 + [1.0]))


def test_content_creator_must_belong_to_the_brand(db):
    brand, other = make_brand(db), make_brand(db)
    outsider = make_user(db, other, "creator")
    with pytest.raises(errors.ForeignKeyViolation), db.transaction():
        make_content(db, brand, outsider)


def test_version_cannot_point_at_content_from_another_brand(db):
    brand, other = make_brand(db), make_brand(db)
    creator = make_user(db, brand, "creator")
    content_id, _ = make_content(db, brand, creator)
    with pytest.raises(errors.ForeignKeyViolation), db.transaction():
        db.execute(
            "insert into public.content_versions (content_id, brand_id, version_number) "
            "values (%s, %s, 2)",
            (content_id, other),
        )


def test_flag_unit_must_exist_in_its_version(db):
    brand = make_brand(db)
    creator = make_user(db, brand, "creator")
    _, version = make_content(db, brand, creator)
    _insert_unit(db, brand, version, "u1")
    _insert_flag(db, brand, version, "u1")
    with pytest.raises(errors.ForeignKeyViolation), db.transaction():
        _insert_flag(db, brand, version, "u9")


@pytest.mark.parametrize("status", ["dismissed", "excepted"])
def test_dismissed_or_excepted_flag_needs_a_reason(db, status):
    brand = make_brand(db)
    creator = make_user(db, brand, "creator")
    _, version = make_content(db, brand, creator)
    _insert_unit(db, brand, version)
    flag = _insert_flag(db, brand, version)
    with pytest.raises(errors.CheckViolation), db.transaction():
        db.execute("update public.flags set status = %s where id = %s", (status, flag))
    with pytest.raises(errors.CheckViolation), db.transaction():
        db.execute(
            "update public.flags set status = %s, resolution_note = '  ' where id = %s",
            (status, flag),
        )
    db.execute(
        "update public.flags set status = %s, resolution_note = 'Approved wording' where id = %s",
        (status, flag),
    )


def test_flag_rejects_values_outside_the_contract(db):
    brand = make_brand(db)
    creator = make_user(db, brand, "creator")
    _, version = make_content(db, brand, creator)
    _insert_unit(db, brand, version)
    for bad in ({"severity": "critical"}, {"category": "seo"}, {"confidence": 1.5},
                {"layer": "magic"}, {"source_type": "guess"}):  # fmt: skip
        with pytest.raises(errors.CheckViolation), db.transaction():
            _insert_flag(db, brand, version, **bad)


def test_updated_at_is_set_by_trigger(db):
    brand = make_brand(db)
    _insert_rule(db, brand)
    db.execute("update public.rules set updated_at = '2000-01-01' where brand_id = %s", (brand,))
    year = db.execute(
        "select extract(year from updated_at) from public.rules where brand_id = %s", (brand,)
    ).fetchone()[0]
    assert year > 2000, "the trigger must overwrite updated_at with now()"
