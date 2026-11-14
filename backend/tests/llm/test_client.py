"""LLMClient.json(): cache, fallback, repair, validation and logging (decision 22)."""

import json
import uuid

import pytest
from pydantic import BaseModel

from app.llm.cache import SQLiteCache
from app.llm.call_log import MemoryCallLogger
from app.llm.client import LLMClient, parse_output, strip_code_fences
from app.llm.errors import LLMUnavailableError, ProviderError, RateLimitError
from app.llm.safety import CONTENT_GUARD
from tests.llm.fakes import FakeProvider


class Verdict(BaseModel):
    label: str
    score: float


GOOD = json.dumps({"label": "compatible", "score": 0.9})


def make_client(*providers, cache=None):
    logger = MemoryCallLogger()
    client = LLMClient(list(providers), cache or SQLiteCache(":memory:"), logger)
    return client, logger


def ask(client, prompt="Compare R-001 and R-002.", **kwargs):
    return client.json(Verdict, "You compare rules.", prompt, purpose="pair_check", **kwargs)


# --- Done when ------------------------------------------------------------------------------


def test_cache_hit_makes_no_call():
    cache = SQLiteCache(":memory:")
    first = FakeProvider("gemini", [GOOD])
    client, _ = make_client(first, cache=cache)
    assert ask(client) == Verdict(label="compatible", score=0.9)

    second = FakeProvider("gemini", [])  # would raise if called
    client2, logger = make_client(second, cache=cache)
    assert ask(client2) == Verdict(label="compatible", score=0.9)
    assert second.calls == []
    assert len(logger.records) == 1
    record = logger.records[0]
    assert record.cached and record.ok and record.provider == "gemini" and record.model == "fake-1"


def test_rate_limit_falls_through_to_next_provider():
    gemini = FakeProvider("gemini", [RateLimitError("gemini rate limited (HTTP 429)")])
    groq = FakeProvider("groq", [GOOD])
    client, logger = make_client(gemini, groq)

    assert ask(client).label == "compatible"
    assert len(gemini.calls) == 1  # no repair or retry on a rate limit
    assert len(groq.calls) == 1
    assert [(r.provider, r.ok) for r in logger.records] == [("gemini", False), ("groq", True)]


def test_invalid_json_is_repaired_once_by_the_same_provider():
    gemini = FakeProvider("gemini", ['{"label": "compatible", "score": ', GOOD])
    groq = FakeProvider("groq", [GOOD])
    client, logger = make_client(gemini, groq)

    assert ask(client).score == 0.9
    assert len(gemini.calls) == 2
    assert groq.calls == []
    repair = gemini.calls[1][1]
    assert repair.startswith("Compare R-001 and R-002.")
    assert '{"label": "compatible", "score": ' in repair
    assert "invalid JSON" in repair
    assert [r.ok for r in logger.records] == [False, True]


def test_output_still_invalid_after_one_repair_falls_through():
    gemini = FakeProvider("gemini", ['{"label": 1}', '{"label": 2}', GOOD])
    groq = FakeProvider("groq", [GOOD])
    client, _ = make_client(gemini, groq)

    assert ask(client).label == "compatible"
    assert len(gemini.calls) == 2  # original + exactly one repair, never a third
    assert len(groq.calls) == 1


def test_clear_error_when_every_provider_fails():
    gemini = FakeProvider("gemini", [RateLimitError("gemini rate limited (HTTP 429)")])
    groq = FakeProvider("groq", [ProviderError("groq HTTP 500: upstream error")])
    openrouter = FakeProvider("openrouter", ["not json", "still not json"])
    client, logger = make_client(gemini, groq, openrouter)

    with pytest.raises(LLMUnavailableError) as exc_info:
        ask(client)
    message = str(exc_info.value)
    assert "pair_check" in message
    assert "gemini: rate limited" in message
    assert "groq: groq HTTP 500" in message
    assert "openrouter: invalid output after one repair" in message
    assert [name for name, _ in exc_info.value.attempts] == ["gemini", "groq", "openrouter"]
    assert len(logger.records) == 4 and not any(r.ok for r in logger.records)


def test_clear_error_when_no_provider_is_configured():
    client, _ = make_client()
    with pytest.raises(LLMUnavailableError, match="No AI provider is configured"):
        ask(client)


# --- Behaviour around the edges -------------------------------------------------------------


def test_failed_calls_are_not_cached():
    cache = SQLiteCache(":memory:")
    client, _ = make_client(FakeProvider("gemini", [ProviderError("down")]), cache=cache)
    with pytest.raises(LLMUnavailableError):
        ask(client)
    client2, _ = make_client(FakeProvider("gemini", [GOOD]), cache=cache)
    assert ask(client2).label == "compatible"


def test_cache_key_ignores_provider_but_not_prompt_or_schema():
    cache = SQLiteCache(":memory:")
    client, _ = make_client(FakeProvider("gemini", [GOOD]), cache=cache)
    ask(client)

    other = FakeProvider("groq", [json.dumps({"label": "duplicate", "score": 1})] * 2)
    client2, _ = make_client(other, cache=cache)
    assert ask(client2).label == "compatible"  # same prompt, other provider: cache hit
    assert ask(client2, prompt="Compare R-003 and R-004.").label == "duplicate"
    assert len(other.calls) == 1


def test_stale_cache_entry_that_no_longer_validates_is_ignored():
    cache = SQLiteCache(":memory:")
    from app.llm.cache import cache_key

    cache.set(cache_key("Verdict", "You compare rules.", "Compare R-001 and R-002."),
              {"provider": "gemini", "model": "old", "output": {"label": "x"}})  # fmt: skip
    gemini = FakeProvider("gemini", [GOOD])
    client, _ = make_client(gemini, cache=cache)
    assert ask(client).score == 0.9
    assert len(gemini.calls) == 1


def test_system_prompt_carries_guard_and_schema():
    gemini = FakeProvider("gemini", [GOOD])
    client, _ = make_client(gemini)
    ask(client)
    system = gemini.calls[0][0]
    assert system.startswith("You compare rules.")
    assert CONTENT_GUARD in system
    assert '"label"' in system and '"score"' in system


def test_log_records_carry_purpose_brand_and_version():
    brand, version = uuid.uuid4(), uuid.uuid4()
    client, logger = make_client(FakeProvider("gemini", [GOOD]))
    ask(client, brand_id=brand, content_version_id=version)
    record = logger.records[0]
    assert (record.purpose, record.brand_id, record.content_version_id) == (
        "pair_check",
        brand,
        version,
    )
    assert record.latency_ms is not None and record.latency_ms >= 0


@pytest.mark.parametrize(
    "reply",
    [
        '```json\n{"label": "a", "score": 1}\n```',
        '```\n{"label": "a", "score": 1}\n```',
        'Here you go:\n{"label": "a", "score": 1}\nHope that helps.',
        '  {"label": "a", "score": 1}  ',
    ],
)
def test_parse_output_tolerates_fences_and_chatter(reply):
    assert parse_output(Verdict, reply) == Verdict(label="a", score=1)


def test_strip_code_fences_leaves_plain_text_alone():
    assert strip_code_fences('{"a": "```"}') == '{"a": "```"}'


# --- Rate-limit rounds (every provider busy) -------------------------------------------------


def _limited(name, retry_after=None):
    return RateLimitError(f"{name} rate limited (HTTP 429)", retry_after)


def test_when_every_provider_is_rate_limited_the_chain_is_retried_after_a_wait():
    sleeps: list[float] = []
    gemini = FakeProvider("gemini", [_limited("gemini"), GOOD])
    groq = FakeProvider("groq", [_limited("groq", retry_after=12)])
    client = LLMClient([gemini, groq], SQLiteCache(":memory:"), MemoryCallLogger(),
                       rate_limit_wait=5, sleep=sleeps.append)  # fmt: skip
    assert ask(client).label == "compatible"
    assert sleeps == [12]  # Retry-After (12 s) beats the 5 s backoff
    assert len(gemini.calls) == 2 and len(groq.calls) == 1


def test_rate_limit_rounds_give_up_with_a_clear_error_and_capped_waits():
    sleeps: list[float] = []
    gemini = FakeProvider("gemini", [_limited("gemini", retry_after=90)] * 3)
    client = LLMClient([gemini], SQLiteCache(":memory:"), MemoryCallLogger(),
                       rate_limit_rounds=3, rate_limit_wait=5, sleep=sleeps.append)  # fmt: skip
    with pytest.raises(LLMUnavailableError, match="gemini: rate limited"):
        ask(client)
    assert sleeps == [30.0, 30.0]  # two waits between three rounds, each capped at 30 s
    assert len(gemini.calls) == 3


def test_no_extra_round_when_a_failure_was_not_a_rate_limit():
    sleeps: list[float] = []
    gemini = FakeProvider("gemini", [_limited("gemini")])
    groq = FakeProvider("groq", [ProviderError("groq HTTP 500")])
    client = LLMClient([gemini, groq], SQLiteCache(":memory:"), MemoryCallLogger(),
                       sleep=sleeps.append)  # fmt: skip
    with pytest.raises(LLMUnavailableError):
        ask(client)
    assert sleeps == []


def test_image_calls_skip_text_only_providers_and_cache_by_image():
    groq = FakeProvider("groq", [GOOD])
    gemini = FakeProvider("gemini", [GOOD, json.dumps({"label": "other", "score": 0})],
                          supports_images=True)  # fmt: skip
    client, _ = make_client(groq, gemini)
    assert ask(client, images=[b"\x89PNG-a"]).label == "compatible"
    assert groq.calls == [] and gemini.images == [[b"\x89PNG-a"]]
    assert ask(client, images=[b"\x89PNG-a"]).label == "compatible"  # cached
    assert ask(client, images=[b"\x89PNG-b"]).label == "other"  # different image, new call
