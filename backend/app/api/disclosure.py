"""AI disclosure (task 9.2): which services see what, and how often they were used."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import Conn, User
from app.config import get_settings
from app.processing.redaction import presidio_available

router = APIRouter(tags=["disclosure"])


class Service(BaseModel):
    name: str
    role: str
    models: list[str]
    data_sent: str
    configured: bool


class UsageRow(BaseModel):
    provider: str
    model: str
    purpose: str
    calls: int
    cached: int
    failed: int


class Disclosure(BaseModel):
    services: list[Service]
    provider_order: list[str]
    redaction: list[str]
    presidio_active: bool
    usage_last_30_days: list[UsageRow]


@router.get("/disclosure", response_model=Disclosure)
def disclosure(user: User, conn: Conn) -> Disclosure:
    s = get_settings()
    text_data = (
        "Redacted excerpts of content (about 4 paragraphs per call), the rules or facts "
        "they are checked against, and guideline pages when guidelines are uploaded."
    )
    images_note = " Images for visual checks." if s.openrouter_supports_images else ""
    services = [
        Service(name="Google Gemini", role="Primary model; embeddings; image checks",
                models=[s.gemini_model, s.gemini_vision_model, s.gemini_embedding_model],
                data_sent=text_data + " Rule texts, fact statements and redacted units for "
                "embeddings. Images inside PDFs and uploaded images for visual checks.",
                configured=bool(s.gemini_api_key)),
        Service(name="Groq", role="Fallback model (text only)", models=[s.groq_model],
                data_sent=text_data, configured=bool(s.groq_api_key)),
        Service(name="OpenRouter", role="Second fallback model",
                models=[s.openrouter_model] if s.openrouter_model else [],
                data_sent=text_data + images_note,
                configured=bool(s.openrouter_api_key and s.openrouter_model)),
        Service(name="Supabase", role="Database, sign-in and file storage (not an AI service)",
                models=[], data_sent="Everything stored in Heimdall, including original uploads.",
                configured=bool(s.database_url)),
    ]  # fmt: skip
    rows = conn.execute(
        "select provider, model, purpose, count(*), count(*) filter (where cached), "
        "count(*) filter (where not ok) from public.ai_calls where brand_id = %s "
        "and created_at > now() - interval '30 days' group by provider, model, purpose "
        "order by count(*) desc",
        (user.brand_id,),
    ).fetchall()
    return Disclosure(
        services=services,
        provider_order=s.provider_order,
        redaction=[
            "Email addresses", "Phone numbers", "PAN numbers", "Aadhaar numbers",
            "Card numbers (Luhn-checked)", "Your brand's confidential terms",
            "Names and places (when Presidio is installed)",
        ],
        presidio_active=presidio_available(),
        usage_last_30_days=[UsageRow(provider=r[0], model=r[1], purpose=r[2], calls=r[3],
                                     cached=r[4], failed=r[5]) for r in rows],
    )  # fmt: skip
