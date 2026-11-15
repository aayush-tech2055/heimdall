"""Brand settings API (tasks 9.1 and 9.3): confidential terms, claim policy, readability."""

from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, Field, field_validator

from app.api.deps import Admin, Conn, User, check_brand
from app.audit import audit
from app.processing.redaction import presidio_available
from app.review.claims import CLAIM_POLICY_ID, CLAIM_POLICY_TEXT

router = APIRouter(tags=["settings"])


class BrandSettings(BaseModel):
    confidential_terms: list[str] = Field(default_factory=list, max_length=200)
    claim_policy_enabled: bool = True
    readability_target: float | None = Field(default=None, ge=0, le=100)

    @field_validator("confidential_terms")
    @classmethod
    def _tidy(cls, terms: list[str]) -> list[str]:
        out: list[str] = []
        for t in terms:
            t = " ".join(t.split())
            if t and t.lower() not in {x.lower() for x in out}:
                out.append(t[:100])
        return out


class SettingsOut(BrandSettings):
    claim_policy_id: str = CLAIM_POLICY_ID
    claim_policy_text: str = CLAIM_POLICY_TEXT
    presidio_available: bool = False


def _load(conn, brand_id: UUID) -> SettingsOut:  # noqa: ANN001
    row = conn.execute(
        "select confidential_terms, claim_policy_enabled, readability_target "
        "from public.brand_settings where brand_id = %s",
        (brand_id,),
    ).fetchone()
    base = BrandSettings() if row is None else BrandSettings(
        confidential_terms=list(row[0]), claim_policy_enabled=row[1], readability_target=row[2]
    )  # fmt: skip
    return SettingsOut(**base.model_dump(), presidio_available=presidio_available())


@router.get("/brands/{brand_id}/settings", response_model=SettingsOut)
def get_settings_(brand_id: UUID, user: User, conn: Conn) -> SettingsOut:
    check_brand(user, brand_id)
    return _load(conn, brand_id)


@router.put("/brands/{brand_id}/settings", response_model=SettingsOut)
def put_settings(brand_id: UUID, body: BrandSettings, user: Admin, conn: Conn) -> SettingsOut:
    check_brand(user, brand_id)
    before = _load(conn, brand_id)
    conn.execute(
        "insert into public.brand_settings (brand_id, confidential_terms, claim_policy_enabled, "
        "readability_target) values (%s, %s, %s, %s) on conflict (brand_id) do update set "
        "confidential_terms = excluded.confidential_terms, "
        "claim_policy_enabled = excluded.claim_policy_enabled, "
        "readability_target = excluded.readability_target",
        (brand_id, body.confidential_terms, body.claim_policy_enabled, body.readability_target),
    )
    audit(conn, brand_id=brand_id, actor_id=user.id, action="settings.update",
          entity_type="brand_settings", entity_id=str(brand_id),
          before=before.model_dump(include=set(BrandSettings.model_fields)),
          after=body.model_dump())  # fmt: skip
    return _load(conn, brand_id)
