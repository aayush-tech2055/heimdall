"""Sign-up, onboarding, /me, active brand, teams and the manager email check (real DB)."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.api.deps import Identity
from app.auth_admin import AuthAdminError, get_auth_admin
from app.main import app
from tests.db.helpers import NoCommit, email_of, make_brand, make_user

pytestmark = pytest.mark.db


class FakeAuthAdmin:
    def __init__(self, db):
        self.db = db
        self.emails: set[str] = set()

    def create_user(self, email: str, password: str, display_name: str) -> str:
        if email in self.emails:
            raise AuthAdminError("An account with this email already exists", 409)
        self.emails.add(email)
        uid = uuid.uuid4()
        self.db.execute(
            "insert into auth.users (id, email, aud, role) values (%s, %s, 'authenticated', 'authenticated')",
            (uid, email),
        )
        return str(uid)


@pytest.fixture
def api(db):
    who = {"ident": None}
    app.dependency_overrides[deps.get_conn] = lambda: NoCommit(db)
    app.dependency_overrides[deps.get_identity] = lambda: who["ident"]
    fake = FakeAuthAdmin(db)
    app.dependency_overrides[get_auth_admin] = lambda: fake
    yield TestClient(app), who, db
    app.dependency_overrides.clear()


def as_(who, db, user_id):
    who["ident"] = Identity(user_id, email_of(db, user_id))


def test_admin_signup_creates_a_brand_and_lands_on_it(api):
    client, who, db = api
    r = client.post(
        "/auth/signup",
        json={
            "email": "ada@acme.example",
            "password": "secret1",
            "display_name": "Ada",
            "role": "admin",
            "brand_name": "Acme",
        },
    )
    assert r.status_code == 201, r.text
    uid = uuid.UUID(r.json()["user_id"])
    as_(who, db, uid)
    me = client.get("/me").json()
    assert me["role"] == "admin" and me["brand_name"] == "Acme" and not me["needs_onboarding"]
    assert [m["role"] for m in me["memberships"]] == ["admin"]
    again = client.post(
        "/auth/signup",
        json={
            "email": "ada@acme.example",
            "password": "secret1",
            "display_name": "Ada",
            "role": "creator",
        },
    )
    assert again.status_code == 409


def test_admin_must_name_a_brand_and_roles_are_fixed(api):
    client, _, _ = api
    bad = client.post(
        "/auth/signup",
        json={"email": "x@y.example", "password": "secret1", "display_name": "X", "role": "admin"},
    )
    assert bad.status_code == 422
    wrong = client.post(
        "/auth/signup",
        json={"email": "x@y.example", "password": "secret1", "display_name": "X", "role": "owner"},
    )
    assert wrong.status_code == 422


def test_google_user_onboards_once(api):
    client, who, db = api
    uid = uuid.uuid4()
    db.execute(
        "insert into auth.users (id, email, aud, role) values (%s, %s, 'authenticated', "
        "'authenticated')",
        (uid, "g@gmail.example"),
    )
    as_(who, db, uid)
    assert client.get("/me").json()["needs_onboarding"] is True
    r = client.post("/me/onboard", json={"display_name": "Gia", "role": "creator"})
    assert r.status_code == 200 and r.json()["role"] == "creator" and r.json()["brand_id"] is None
    assert (
        client.post(
            "/me/onboard", json={"display_name": "Gia", "role": "admin", "brand_name": "B"}
        ).status_code
        == 409
    )


def test_team_add_switch_remove_and_manager_check(api):
    client, who, db = api
    brand_a, brand_b = make_brand(db), make_brand(db)
    admin_a = make_user(db, brand_a, "admin")
    admin_b = make_user(db, brand_b, "admin")
    creator = make_user(db, brand_a, "creator")
    manager = make_user(db, brand_a, "manager")
    # The creator is only on brand A for now; admin B finds and adds them.
    as_(who, db, admin_b)
    found = client.get(
        f"/brands/{brand_b}/directory", params={"role": "creator", "q": email_of(db, creator)}
    ).json()
    assert [p["user_id"] for p in found] == [str(creator)]
    assert (
        client.post(f"/brands/{brand_b}/members", json={"user_id": str(creator)}).status_code == 201
    )
    assert {m["role"] for m in client.get(f"/brands/{brand_b}/members").json()} == {
        "admin",
        "creator",
    }
    # Admin B cannot manage brand A's team.
    assert client.get(f"/brands/{brand_a}/members").status_code == 403
    # The creator now follows two admins and switches between them.
    as_(who, db, creator)
    me = client.get("/me").json()
    assert {m["brand_id"] for m in me["memberships"]} == {str(brand_a), str(brand_b)}
    switched = client.post("/me/active-brand", json={"brand_id": str(brand_b)}).json()
    assert switched["brand_id"] == str(brand_b)
    assert (
        client.post("/me/active-brand", json={"brand_id": str(make_brand(db))}).status_code == 403
    )
    # Manager email check is scoped to the active brand's team.
    client.post("/me/active-brand", json={"brand_id": str(brand_a)})
    ok = client.get(
        f"/brands/{brand_a}/managers/check", params={"email": email_of(db, manager)}
    ).json()
    assert ok["found"] is True
    no = client.get(
        f"/brands/{brand_a}/managers/check", params={"email": email_of(db, admin_a)}
    ).json()
    assert no["found"] is False
    # Removing the creator from brand A moves their active brand to the remaining team.
    as_(who, db, admin_a)
    assert client.delete(f"/brands/{brand_a}/members/{creator}").status_code == 204
    assert client.delete(f"/brands/{brand_a}/members/{admin_a}").status_code == 409
    as_(who, db, creator)
    assert client.get("/me").json()["brand_id"] == str(brand_b)


def test_creators_cannot_manage_teams(api):
    client, who, db = api
    brand = make_brand(db)
    creator = make_user(db, brand, "creator")
    as_(who, db, creator)
    assert client.get(f"/brands/{brand}/members").status_code == 403
