"""Provider HTTP handling with a mock transport (no network), and provider selection."""

import json

import httpx
import pytest

from app.config import Settings
from app.llm.errors import ProviderError, RateLimitError
from app.llm.providers import GeminiProvider, OpenAICompatibleProvider, build_providers


def client_for(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_gemini_request_and_reply():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["key"] = request.headers["x-goog-api-key"]
        seen["body"] = json.loads(request.content)
        parts = [{"text": "thinking...", "thought": True}, {"text": '{"ok": true}'}]
        return httpx.Response(200, json={"candidates": [{"content": {"parts": parts}}]})

    provider = GeminiProvider("k-123", "gemini-2.5-flash", client_for(handler))
    assert provider.complete("SYS", "USER") == '{"ok": true}'
    assert seen["url"].endswith("/models/gemini-2.5-flash:generateContent")
    assert seen["key"] == "k-123"
    assert seen["body"]["systemInstruction"]["parts"][0]["text"] == "SYS"
    assert seen["body"]["contents"][0]["parts"][0]["text"] == "USER"
    assert seen["body"]["generationConfig"]["responseMimeType"] == "application/json"
    assert seen["body"]["generationConfig"]["temperature"] == 0


def test_gemini_blocked_prompt_is_a_provider_error():
    handler = lambda r: httpx.Response(200, json={"promptFeedback": {"blockReason": "SAFETY"}})  # noqa: E731
    provider = GeminiProvider("k", "m", client_for(handler))
    with pytest.raises(ProviderError, match="SAFETY"):
        provider.complete("s", "p")


def test_openai_compatible_request_and_reply():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"ok": 1}'}}]})

    provider = OpenAICompatibleProvider(
        "groq", "https://api.groq.com/openai/v1/", "gk", "openai/gpt-oss-120b",
        json_mode=True, client=client_for(handler),
    )  # fmt: skip
    assert provider.complete("SYS", "USER") == '{"ok": 1}'
    assert seen["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert seen["auth"] == "Bearer gk"
    assert seen["body"]["model"] == "openai/gpt-oss-120b"
    assert seen["body"]["messages"] == [
        {"role": "system", "content": "SYS"},
        {"role": "user", "content": "USER"},
    ]
    assert seen["body"]["response_format"] == {"type": "json_object"}


def test_openai_compatible_without_json_mode_sends_no_response_format():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "response_format" not in json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})

    provider = OpenAICompatibleProvider(
        "openrouter", "https://x", "k", "m", json_mode=False, client=client_for(handler)
    )
    assert provider.complete("s", "p") == "{}"


@pytest.mark.parametrize(
    "make",
    [
        lambda c: GeminiProvider("k", "m", c),
        lambda c: OpenAICompatibleProvider("groq", "https://x", "k", "m", json_mode=True, client=c),
    ],
)
def test_http_errors_map_to_provider_errors(make):
    with pytest.raises(RateLimitError):
        make(client_for(lambda r: httpx.Response(429, json={}))).complete("s", "p")
    with pytest.raises(ProviderError, match="HTTP 503"):
        make(client_for(lambda r: httpx.Response(503, text="overloaded"))).complete("s", "p")

    def boom(request):
        raise httpx.ConnectTimeout("slow", request=request)

    with pytest.raises(ProviderError, match="ConnectTimeout"):
        make(client_for(boom)).complete("s", "p")


def test_empty_reply_is_a_provider_error():
    handler = lambda r: httpx.Response(200, json={"choices": [{"message": {"content": ""}}]})  # noqa: E731
    provider = OpenAICompatibleProvider("groq", "https://x", "k", "m", json_mode=True,
                                        client=client_for(handler))  # fmt: skip
    with pytest.raises(ProviderError, match="empty"):
        provider.complete("s", "p")


def _settings(**env) -> Settings:
    base = {"gemini_api_key": "", "groq_api_key": "", "openrouter_api_key": ""}
    return Settings(_env_file=None, **(base | env))


def test_build_providers_follows_order_and_skips_missing_keys():
    settings = _settings(
        gemini_api_key="g", groq_api_key="q", openrouter_api_key="o",
        openrouter_model="free/model", llm_provider_order="groq,gemini,openrouter",
    )  # fmt: skip
    assert [p.name for p in build_providers(settings)] == ["groq", "gemini", "openrouter"]
    assert [p.name for p in build_providers(_settings(groq_api_key="q"))] == ["groq"]
    assert build_providers(_settings()) == []


def test_openrouter_needs_a_model_name():
    settings = _settings(openrouter_api_key="o", openrouter_model="")
    assert build_providers(settings) == []


def test_retry_after_header_is_carried_on_rate_limit():
    handler = lambda r: httpx.Response(429, headers={"retry-after": "7"}, json={})  # noqa: E731
    with pytest.raises(RateLimitError) as exc_info:
        GeminiProvider("k", "m", client_for(handler)).complete("s", "p")
    assert exc_info.value.retry_after == 7.0


def test_gemini_sends_images_inline_with_the_vision_model():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["parts"] = json.loads(request.content)["contents"][0]["parts"]
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "{}"}]}}]})

    provider = GeminiProvider("k", "text-model", client_for(handler), vision_model="vision-model")
    provider.complete("s", "look", [b"\x89PNGdata"])
    assert seen["url"].endswith("/models/vision-model:generateContent")
    assert seen["parts"][1]["inline_data"]["mime_type"] == "image/png"


def test_openai_compatible_sends_data_uri_images():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["content"] = json.loads(request.content)["messages"][1]["content"]
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})

    provider = OpenAICompatibleProvider("openrouter", "https://x", "k", "m", json_mode=False,
                                        client=client_for(handler), supports_images=True)  # fmt: skip
    provider.complete("s", "look", [b"\xff\xd8\xffjpeg"])
    assert seen["content"][0] == {"type": "text", "text": "look"}
    assert seen["content"][1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
