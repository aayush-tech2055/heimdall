"""Chat model providers (decision 23): Gemini, then Groq and OpenRouter (OpenAI-compatible).

A provider does one thing: send a system prompt and a user prompt, and return the reply text.
Validation, repair, fallback, caching and logging live in `LLMClient`.
"""

from typing import Protocol

import httpx

from app.config import Settings
from app.llm.errors import ProviderError, RateLimitError

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
TIMEOUT_SECONDS = 90.0


class Provider(Protocol):
    name: str
    model: str

    def complete(self, system: str, prompt: str) -> str:
        """Return the model's reply text, or raise `ProviderError` / `RateLimitError`."""
        ...


def _post(client: httpx.Client, name: str, url: str, **kwargs: object) -> dict:
    try:
        resp = client.post(url, **kwargs)
    except httpx.HTTPError as exc:
        raise ProviderError(f"{name} request failed: {exc.__class__.__name__}") from exc
    if resp.status_code == 429:
        raise RateLimitError(f"{name} rate limited (HTTP 429)", _retry_after(resp))
    if resp.is_error:
        raise ProviderError(f"{name} HTTP {resp.status_code}: {resp.text[:200]}")
    try:
        return resp.json()
    except ValueError as exc:
        raise ProviderError(f"{name} returned a non-JSON response") from exc


def _retry_after(resp: httpx.Response) -> float | None:
    try:
        return float(resp.headers["retry-after"])
    except (KeyError, ValueError):
        return None


class GeminiProvider:
    """Google Gemini `generateContent`, with JSON output mode and temperature 0."""

    name = "gemini"

    def __init__(self, api_key: str, model: str, client: httpx.Client | None = None) -> None:
        self.model = model
        self._client = client or httpx.Client(timeout=TIMEOUT_SECONDS)
        self._headers = {"x-goog-api-key": api_key}

    def complete(self, system: str, prompt: str) -> str:
        data = _post(
            self._client,
            self.name,
            f"{GEMINI_BASE_URL}/models/{self.model}:generateContent",
            headers=self._headers,
            json={
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
            },
        )
        try:
            parts = data["candidates"][0]["content"]["parts"]
            text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        except (KeyError, IndexError, TypeError) as exc:
            reason = data.get("promptFeedback", {}).get("blockReason", "no candidates")
            raise ProviderError(f"gemini returned no text ({reason})") from exc
        if not text.strip():
            raise ProviderError("gemini returned an empty reply")
        return text


class OpenAICompatibleProvider:
    """Any OpenAI-compatible `/chat/completions` endpoint (Groq, OpenRouter)."""

    def __init__(
        self,
        name: str,
        base_url: str,
        api_key: str,
        model: str,
        *,
        json_mode: bool,
        client: httpx.Client | None = None,
    ) -> None:
        self.name = name
        self.model = model
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._json_mode = json_mode
        self._client = client or httpx.Client(timeout=TIMEOUT_SECONDS)
        self._headers = {"Authorization": f"Bearer {api_key}"}

    def complete(self, system: str, prompt: str) -> str:
        body: dict = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        }
        if self._json_mode:
            body["response_format"] = {"type": "json_object"}
        data = _post(self._client, self.name, self._url, headers=self._headers, json=body)
        try:
            text = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"{self.name} returned no choices") from exc
        if not text.strip():
            raise ProviderError(f"{self.name} returned an empty reply")
        return text


def build_providers(settings: Settings, client: httpx.Client | None = None) -> list[Provider]:
    """Providers in `LLM_PROVIDER_ORDER`, skipping any without a key or model (decision 23)."""
    available: dict[str, Provider] = {}
    if settings.gemini_api_key and settings.gemini_model:
        available["gemini"] = GeminiProvider(settings.gemini_api_key, settings.gemini_model, client)
    if settings.groq_api_key and settings.groq_model:
        available["groq"] = OpenAICompatibleProvider(
            "groq", GROQ_BASE_URL, settings.groq_api_key, settings.groq_model,
            json_mode=True, client=client,
        )  # fmt: skip
    if settings.openrouter_api_key and settings.openrouter_model:
        # Free OpenRouter models vary in JSON-mode support, so rely on the prompt instead.
        available["openrouter"] = OpenAICompatibleProvider(
            "openrouter", OPENROUTER_BASE_URL, settings.openrouter_api_key,
            settings.openrouter_model, json_mode=False, client=client,
        )  # fmt: skip
    return [available[name] for name in settings.provider_order if name in available]
