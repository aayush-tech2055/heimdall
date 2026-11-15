"""Who is signed in: the frontend routes by role with this."""

from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import Conn, User

router = APIRouter(tags=["me"])


class Me(BaseModel):
    id: UUID
    email: str | None
    display_name: str | None
    role: str
    brand_id: UUID
    brand_name: str


@router.get("/me", response_model=Me)
def me(user: User, conn: Conn) -> Me:
    (brand_name,) = conn.execute(
        "select name from public.brands where id = %s", (user.brand_id,)
    ).fetchone()
    return Me(id=user.id, email=user.email, display_name=user.display_name, role=user.role,
              brand_id=user.brand_id, brand_name=brand_name)  # fmt: skip
