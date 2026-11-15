"""Gemini embeddings (decision 12): 768 dimensions, normalised, batches of 100, cached.

`RETRIEVAL_DOCUMENT` for rules and facts, `RETRIEVAL_QUERY` for content. There is no fallback
provider, because vectors from different models cannot be compared. Rate limits and server
errors are retried with exponential backoff; anything else fails fast with a clear message.
"""

import math
import time
from collections.abc import Callable
from functools import lru_cache
from typing import Literal
from uuid import UUID

import httpx

from app.config import get_settings
from app.llm.cache import SQLiteCache, cache_key
from app.llm.call_log import CallLogger, CallRecord
from app.llm.providers import GEMINI_BASE_URL, TIMEOUT_SECONDS

TaskType = Literal["RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"]
DIMENSIONS = 768
BATCH_SIZE = 100


class EmbeddingError(RuntimeError):
    """Embeddings could not be produced (no key, bad input, or the API kept failing)."""


def normalise(vector: list[float]) -> list[float]:
    """Scale to unit length, so cosine similarity is a dot product."""
    norm = math.sqrt(sum(x * x for x in vector))
    if norm == 0 or not math.isfinite(norm):
        raise EmbeddingError("the API returned a zero or invalid vector")
    return [x / norm for x in vector]


class Embedder:
    def __init__(
        self,
        api_key: str,
        model: str,
        cache: SQLiteCache,
        logger: CallLogger,
        *,
        dimensions: int = DIMENSIONS,
        batch_size: int = BATCH_SIZE,
        max_attempts: int = 5,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.model = model
        self.dimensions = dimensions
        self._api_key = api_key
        self._cache = cache
        self._logger = logger
        self._batch_size = batch_size
        self._max_attempts = max_attempts
        self._base_delay = base_delay
        self._max_delay = max_delay
        self._client = client or httpx.Client(timeout=TIMEOUT_SECONDS)
        self._sleep = sleep

    def embed_documents(
        self, texts: list[str], *, purpose: str = "embedding", brand_id: UUID | None = None
    ) -> list[list[float]]:
        """Vectors for rules and facts (`RETRIEVAL_DOCUMENT`)."""
        return self._embed(texts, "RETRIEVAL_DOCUMENT", purpose=purpose, brand_id=brand_id)

    def embed_queries(
        self,
        texts: list[str],
        *,
        purpose: str = "embedding",
        brand_id: UUID | None = None,
        content_version_id: UUID | None = None,
    ) -> list[list[float]]:
        """Vectors for review units and claims (`RETRIEVAL_QUERY`)."""
        return self._embed(
            texts, "RETRIEVAL_QUERY", purpose=purpose, brand_id=brand_id,
            content_version_id=content_version_id,
        )  # fmt: skip

    def _key(self, task: TaskType, text: str) -> str:
        return cache_key("embedding", self.model, task, str(self.dimensions), text)

    def _embed(self, texts: list[str], task: TaskType, **context: object) -> list[list[float]]:
        if not self._api_key:
            raise EmbeddingError("GEMINI_API_KEY is not set; embeddings have no fallback provider")
        if any(not t.strip() for t in texts):
            raise EmbeddingError("cannot embed empty text")

        keys = {text: self._key(task, text) for text in texts}
        found = self._cache.get_many(list(set(keys.values())))
        vectors: dict[str, list[float]] = {t: found[k] for t, k in keys.items() if k in found}

        missing = [t for t in dict.fromkeys(texts) if t not in vectors]
        for start in range(0, len(missing), self._batch_size):
            batch = missing[start : start + self._batch_size]
            fresh = [normalise(v) for v in self._request(batch, task, context)]
            vectors.update(zip(batch, fresh, strict=True))
            self._cache.set_many({keys[t]: v for t, v in zip(batch, fresh, strict=True)})
        return [vectors[t] for t in texts]

    def _request(self, batch: list[str], task: TaskType, context: dict) -> list[list[float]]:
        """One batchEmbedContents call, retried on rate limits and server errors."""
        body = {
            "requests": [
                {
                    "model": f"models/{self.model}",
                    "content": {"parts": [{"text": text}]},
                    "taskType": task,
                    "outputDimensionality": self.dimensions,
                }
                for text in batch
            ]
        }
        url = f"{GEMINI_BASE_URL}/models/{self.model}:batchEmbedContents"
        last_problem = ""
        for attempt in range(1, self._max_attempts + 1):
            started = time.perf_counter()
            retry_after: float | None = None
            try:
                resp = self._client.post(url, headers={"x-goog-api-key": self._api_key}, json=body)
            except httpx.HTTPError as exc:
                last_problem = f"request failed: {exc.__class__.__name__}"
            else:
                if resp.status_code == 429 or resp.status_code >= 500:
                    last_problem = f"HTTP {resp.status_code}"
                    retry_after = _retry_after_seconds(resp)
                elif resp.is_error:
                    self._log(started, context, ok=False, error=f"HTTP {resp.status_code}")
                    raise EmbeddingError(
                        f"Gemini embeddings HTTP {resp.status_code}: {resp.text[:200]}"
                    )
                else:
                    vectors = self._parse(resp, len(batch))
                    self._log(started, context, ok=True)
                    return vectors
            self._log(started, context, ok=False, error=last_problem)
            if attempt < self._max_attempts:
                delay = min(self._max_delay, self._base_delay * 2 ** (attempt - 1))
                self._sleep(max(delay, retry_after or 0.0))
        raise EmbeddingError(
            f"Gemini embeddings failed after {self._max_attempts} attempts ({last_problem})"
        )

    def _parse(self, resp: httpx.Response, expected: int) -> list[list[float]]:
        try:
            vectors = [e["values"] for e in resp.json()["embeddings"]]
        except (ValueError, KeyError, TypeError) as exc:
            raise EmbeddingError("Gemini embeddings returned an unexpected response") from exc
        if len(vectors) != expected:
            raise EmbeddingError(f"expected {expected} embeddings, got {len(vectors)}")
        if any(len(v) != self.dimensions for v in vectors):
            raise EmbeddingError(f"expected {self.dimensions}-dimensional embeddings")
        return vectors

    def _log(self, started: float, context: dict, *, ok: bool, error: str | None = None) -> None:
        self._logger.log(
            CallRecord(
                provider="gemini",
                model=self.model,
                purpose=str(context.get("purpose", "embedding")),
                ok=ok,
                latency_ms=int((time.perf_counter() - started) * 1000),
                error=error,
                brand_id=context.get("brand_id"),
                content_version_id=context.get("content_version_id"),
            )
        )


def _retry_after_seconds(resp: httpx.Response) -> float | None:
    value = resp.headers.get("retry-after")
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None


@lru_cache
def get_embedder() -> Embedder:
    """The process-wide embedder, sharing the LLM cache file and the `ai_calls` logger."""
    from app.db import get_pool
    from app.llm.call_log import DBCallLogger

    settings = get_settings()
    return Embedder(
        settings.gemini_api_key,
        settings.gemini_embedding_model,
        SQLiteCache(settings.llm_cache_path, table="embeddings"),
        DBCallLogger(get_pool()),
    )
