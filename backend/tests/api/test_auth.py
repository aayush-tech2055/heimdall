"""Token verification and role/brand checks (no database, no network)."""

import time
import uuid

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException

from app.api.deps import TokenVerifier
from tests.api.conftest import sign_in_as

PRIVATE_KEY = ec.generate_private_key(ec.SECP256R1())


class StaticJWKS:
    def get_signing_key_from_jwt(self, token):
        return type("Key", (), {"key": PRIVATE_KEY.public_key()})()


def verifier(secret: str = "") -> TokenVerifier:
    v = TokenVerifier("", secret)
    v._jwks = StaticJWKS()
    return v


def token(**overrides) -> str:
    claims = {"sub": str(uuid.uuid4()), "aud": "authenticated", "exp": int(time.time()) + 600,
              "email": "creator@acmelearn.example"} | overrides  # fmt: skip
    return jwt.encode(claims, PRIVATE_KEY, algorithm="ES256", headers={"kid": "test"})


def test_valid_es256_token_returns_claims():
    claims = verifier().verify(token(sub="00000000-0000-0000-0000-000000000001"))
    assert claims["sub"] == "00000000-0000-0000-0000-000000000001"


@pytest.mark.parametrize("bad", [{"exp": int(time.time()) - 10}, {"aud": "anon"}, {"sub": None}])
def test_expired_wrong_audience_or_missing_subject_is_401(bad):
    claims = {k: v for k, v in bad.items() if v is not None}
    tok = token(**claims) if bad.get("sub", 1) is not None else jwt.encode(
        {"aud": "authenticated", "exp": int(time.time()) + 60}, PRIVATE_KEY, algorithm="ES256"
    )  # fmt: skip
    with pytest.raises(HTTPException) as exc_info:
        verifier().verify(tok)
    assert exc_info.value.status_code == 401


def test_hs256_needs_the_shared_secret():
    tok = jwt.encode({"sub": "x", "aud": "authenticated", "exp": int(time.time()) + 60},
                     "s3cret-with-enough-length-for-hs256!", algorithm="HS256")  # fmt: skip
    assert verifier("s3cret-with-enough-length-for-hs256!").verify(tok)["sub"] == "x"
    with pytest.raises(HTTPException):
        verifier().verify(tok)


def test_missing_bearer_token_is_401(api):
    response = api.get("/me")
    assert response.status_code == 401
    assert "Sign in" in response.json()["detail"]


@pytest.mark.parametrize("role", ["creator", "manager"])
def test_only_admins_approve_or_edit_rules(api, role):
    sign_in_as(role)
    assert (
        api.post("/rules/approve", json={"codes": ["R-001"], "action": "approve"}).status_code
        == 403
    )
    assert api.patch("/rules/R-001", json={"text": "x"}).status_code == 403


def test_users_cannot_touch_another_brand(api):
    sign_in_as("admin")
    other = uuid.uuid4()
    assert api.get(f"/brands/{other}/rules").status_code == 403
    assert api.post(f"/brands/{other}/guidelines", data={"text": "Be warm."}).status_code == 403


def test_upload_needs_a_pdf_or_text(api):
    user = sign_in_as("admin")
    response = api.post(
        f"/brands/{user.brand_id}/guidelines",
        files={"file": ("guide.docx", b"PK\x03\x04 not a pdf", "application/octet-stream")},
    )
    assert response.status_code == 415
