"""The AI layer: one client for every model call (decisions 22–26)."""

from functools import lru_cache

from app.config import get_settings
from app.llm.cache import SQLiteCache
from app.llm.call_log import DBCallLogger
from app.llm.client import LLMClient
from app.llm.errors import LLMUnavailableError, ProviderError, RateLimitError
from app.llm.providers import build_providers

__all__ = [
    "LLMClient",
    "LLMUnavailableError",
    "ProviderError",
    "RateLimitError",
    "get_llm_client",
]


@lru_cache
def get_llm_client() -> LLMClient:
    """The process-wide client: providers from settings, SQLite cache, logging to `ai_calls`."""
    from app.db import get_pool

    settings = get_settings()
    return LLMClient(
        providers=build_providers(settings),
        cache=SQLiteCache(settings.llm_cache_path),
        logger=DBCallLogger(get_pool()),
    )
