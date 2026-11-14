"""scripts/seed.py: seed file validation and the Supabase Auth admin client (no network)."""

import json
import uuid

import httpx
import pytest
from pydantic import ValidationError

from scripts.seed import DEFAULT_CONFIG, SeedConfig, SupabaseAuthAdmin, load_config, main


def _config(**overrides) -> dict:
    data = {
        "brand": {"name": "Test Brand", "slug": "test-brand"},
        "users": [
            {"email": "a@x.example", "role": "admin", "display_name": "A"},
            {"email": "m@x.example", "role": "manager", "display_name": "M"},
            {"email": "c@x.example", "role": "creator", "display_name": "C"},
        ],
    }
    data.update(overrides)
    return data


def test_repo_seed_file_is_valid_and_has_every_role():
    config = load_config(DEFAULT_CONFIG)
    assert {u.role for u in config.users} == {"admin", "manager", "creator"}
    assert sum(u.role == "creator" for u in config.users) >= 2  # two creators for the RLS demo
    assert all(u.email.endswith(".example") for u in config.users)  # reserved, fictional domain


def test_seed_needs_every_role():
    data = _config()
    data["users"] = [u for u in data["users"] if u["role"] != "manager"]
    with pytest.raises(ValidationError, match="missing"):
        SeedConfig.model_validate(data)


def test_seed_rejects_duplicate_emails_case_insensitively():
    data = _config()
    data["users"].append({"email": "A@X.example", "role": "creator", "display_name": "Dup"})
    with pytest.raises(ValidationError, match="unique"):
        SeedConfig.model_validate(data)


@pytest.mark.parametrize(
    "bad",
    [
        {"brand": {"name": "B", "slug": "Bad Slug"}},
        {"users": [{"email": "a@x.example", "role": "owner", "display_name": "A"}]},
    ],
)
def test_seed_rejects_invalid_values(bad):
    with pytest.raises(ValidationError):
        SeedConfig.model_validate(_config(**bad))


def _admin_with(handler) -> SupabaseAuthAdmin:
    admin = SupabaseAuthAdmin("https://proj.supabase.co/", "service-key")
    admin._client = httpx.Client(
        base_url="https://proj.supabase.co/auth/v1/admin",
        headers=admin._client.headers,
        transport=httpx.MockTransport(handler),
    )
    return admin


def test_auth_admin_finds_existing_users_and_creates_missing_ones():
    existing = uuid.uuid4()
    created = uuid.uuid4()
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        assert request.headers["apikey"] == "service-key"
        assert request.headers["authorization"] == "Bearer service-key"
        if request.method == "GET":
            return httpx.Response(
                200, json={"users": [{"id": str(existing), "email": "A@x.example"}]}
            )
        body = json.loads(request.content)
        assert body["email_confirm"] is True
        assert body["user_metadata"] == {"display_name": "New"}
        return httpx.Response(200, json={"id": str(created), "email": body["email"]})

    admin = _admin_with(handler)
    assert admin.find_user_id("a@X.example") == existing
    assert admin.find_user_id("new@x.example") is None
    assert admin.create_user("new@x.example", "password123", "New") == created
    assert admin.find_user_id("new@x.example") == created
    assert calls == [("GET", "/auth/v1/admin/users"), ("POST", "/auth/v1/admin/users")]


def test_auth_admin_create_error_is_clear():
    admin = _admin_with(lambda request: httpx.Response(422, json={"msg": "weak password"}))
    with pytest.raises(RuntimeError, match="422"):
        admin.create_user("new@x.example", "x", "New")


def test_main_reports_missing_settings(monkeypatch, capsys):
    from scripts import seed

    class Empty:
        database_url = supabase_url = supabase_service_role_key = seed_user_password = ""

    monkeypatch.setattr(seed, "get_settings", lambda: Empty())
    assert main([]) == 1
    assert "SEED_USER_PASSWORD" in capsys.readouterr().err
