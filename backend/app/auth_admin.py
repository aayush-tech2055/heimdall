"""Supabase Auth admin operations the API needs (create accounts for sign-up)."""

import httpx

from app.config import get_settings


class AuthAdminError(Exception):
    """Supabase refused the request (for example, the email is already registered)."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


class SupabaseAuthAdmin:
    """`/auth/v1/admin/users`, authorised with the service role key."""

    def __init__(self, supabase_url: str, service_role_key: str) -> None:
        self._client = httpx.Client(
            base_url=f"{supabase_url.rstrip('/')}/auth/v1/admin",
            headers={"apikey": service_role_key, "Authorization": f"Bearer {service_role_key}"},
            timeout=30,
        )

    def create_user(self, email: str, password: str, display_name: str) -> str:
        """Create a confirmed email/password user; return its id."""
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
            body = (
                resp.json()
                if resp.headers.get("content-type", "").startswith("application/json")
                else {}
            )
            msg = (
                body.get("msg") or body.get("message") or body.get("error_description") or resp.text
            )
            if resp.status_code == 422 and "already" in str(msg).lower():
                raise AuthAdminError("An account with this email already exists", 409)
            raise AuthAdminError(str(msg)[:200], 400)
        return resp.json()["id"]


def get_auth_admin() -> SupabaseAuthAdmin:
    s = get_settings()
    return SupabaseAuthAdmin(s.supabase_url, s.supabase_service_role_key)
