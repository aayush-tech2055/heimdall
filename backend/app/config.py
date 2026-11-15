"""Application settings, read from environment variables and `backend/.env`."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime configuration. Secrets come only from the environment or a local `.env`."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    cors_origins: str = "http://localhost:3000"

    # Database (Supabase Postgres with pgvector)
    database_url: str = ""
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_jwt_secret: str = ""

    # Seed script (task 2.3): password for the seeded demo users
    seed_user_password: str = ""

    # AI providers (decision 23: tried in this order, providers without a key are skipped)
    llm_provider_order: str = "gemini,groq,openrouter"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"
    gemini_vision_model: str = "gemini-3.5-flash"
    gemini_embedding_model: str = "gemini-embedding-001"
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    groq_whisper_model: str = "whisper-large-v3"
    openrouter_api_key: str = ""
    openrouter_model: str = ""

    # LLM cache (decision 24)
    llm_cache_path: str = ".cache/llm_cache.sqlite3"

    @property
    def cors_origin_list(self) -> list[str]:
        """CORS origins as a list, from a comma-separated string."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def provider_order(self) -> list[str]:
        """Provider names in fallback order, lower-cased."""
        return [p.strip().lower() for p in self.llm_provider_order.split(",") if p.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings instance."""
    return Settings()
