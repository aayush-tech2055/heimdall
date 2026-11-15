"""Shared API dependencies: database connection, the signed-in user, role and brand checks.

Authentication: the frontend signs in with Supabase Auth and sends the access token as
`Authorization: Bearer <jwt>`. Tokens are verified against the project's public keys (JWKS;
the project uses ECC signing keys), or with SUPABASE_JWT_SECRET for legacy HS256 projects.
The backend connects as the database owner, so every route checks brand and role here.
"""

import ssl
from collections.abc import Callable, Iterator
from functools import lru_cache
from typing import Annotated
from uuid import UUID

import certifi
import jwt
import psycopg
from fastapi import Depends, Header, HTTPException, status

from app.config import get_settings
from app.db import get_pool
from app.llm import LLMClient, get_llm_client
from app.models.users import CurrentUser
from app.rag.embeddings import Embedder, get_embedder


class TokenVerifier:
    """Verifies Supabase access tokens and returns their claims."""

    def __init__(self, supabase_url: str, jwt_secret: str = "") -> None:
        self._secret = jwt_secret
        # certifi's CA bundle: some Python installs (python.org macOS builds) ship without one.
        self._jwks = (
            jwt.PyJWKClient(
                f"{supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json",
                ssl_context=ssl.create_default_context(cafile=certifi.where()),
            )
            if supabase_url
            else None
        )

    def verify(self, token: str) -> dict:
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") == "HS256":
                if not self._secret:
                    raise jwt.InvalidTokenError("HS256 tokens need SUPABASE_JWT_SECRET")
                key: object = self._secret
            else:
                if self._jwks is None:
                    raise jwt.InvalidTokenError("SUPABASE_URL is not set")
                key = self._jwks.get_signing_key_from_jwt(token).key
            return jwt.decode(
                token, key, algorithms=["ES256", "RS256", "HS256"], audience="authenticated",
                options={"require": ["exp", "sub"]},
            )  # fmt: skip
        except (jwt.PyJWTError, jwt.PyJWKClientError) as exc:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid token: {exc}") from exc


@lru_cache
def get_verifier() -> TokenVerifier:
    settings = get_settings()
    return TokenVerifier(settings.supabase_url, settings.supabase_jwt_secret)


def get_conn() -> Iterator[psycopg.Connection]:
    """One pooled connection per request; committed on success, rolled back on error."""
    with get_pool().connection() as conn:
        yield conn


def llm_client() -> LLMClient:
    return get_llm_client()


def embedder() -> Embedder:
    return get_embedder()


Conn = Annotated[psycopg.Connection, Depends(get_conn)]
LLM = Annotated[LLMClient, Depends(llm_client)]
Emb = Annotated[Embedder, Depends(embedder)]


def load_user(conn: psycopg.Connection, user_id: UUID, email: str | None = None) -> CurrentUser:
    row = conn.execute(
        "select role, brand_id, display_name from public.profiles where id = %s", (user_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No Heimdall profile for this account")
    return CurrentUser(id=user_id, role=row[0], brand_id=row[1], display_name=row[2], email=email)


def get_current_user(
    conn: Conn,
    authorization: Annotated[str | None, Header()] = None,
    verifier: TokenVerifier = Depends(get_verifier),  # noqa: B008
) -> CurrentUser:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in first (missing bearer token)")
    claims = verifier.verify(authorization.split(" ", 1)[1].strip())
    try:
        user_id = UUID(claims["sub"])
    except ValueError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token subject") from exc
    return load_user(conn, user_id, claims.get("email"))


User = Annotated[CurrentUser, Depends(get_current_user)]


def require_roles(*roles: str) -> Callable[[CurrentUser], CurrentUser]:
    def check(user: User) -> CurrentUser:
        if user.role not in roles:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, f"Only {' or '.join(roles)} users can do this"
            )
        return user

    return check


Admin = Annotated[CurrentUser, Depends(require_roles("admin"))]
AdminOrManager = Annotated[CurrentUser, Depends(require_roles("admin", "manager"))]
Manager = Annotated[CurrentUser, Depends(require_roles("manager", "admin"))]
Creator = Annotated[CurrentUser, Depends(require_roles("creator"))]


def check_brand(user: CurrentUser, brand_id: UUID) -> None:
    """A user only ever works on their own brand."""
    if user.brand_id != brand_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have access to this brand")
