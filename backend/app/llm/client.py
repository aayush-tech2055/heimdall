"""`LLMClient.json()`: the one function every model call goes through (decision 22).

    cache → providers in order → validate against the Pydantic schema
          → invalid? ask the same provider once to repair → still invalid, rate limited
            or failed? fall through to the next provider → none left? LLMUnavailableError

Every provider call and every cache hit is logged (decision 25).
"""

import json
import re
import time
from typing import TypeVar
from uuid import UUID

from pydantic import BaseModel, ValidationError

from app.llm.cache import SQLiteCache, cache_key
from app.llm.call_log import CallLogger, CallRecord
from app.llm.errors import LLMUnavailableError, ProviderError, RateLimitError
from app.llm.providers import Provider
from app.llm.safety import CONTENT_GUARD

T = TypeVar("T", bound=BaseModel)

_FENCE = re.compile(r"^\s*```[a-zA-Z0-9_-]*\s*\n?(.*?)\n?\s*```\s*$", re.DOTALL)


class InvalidOutputError(ValueError):
    """The reply was not valid JSON for the schema."""


def strip_code_fences(text: str) -> str:
    """Remove a surrounding Markdown code fence (```json ... ```), if there is one."""
    match = _FENCE.match(text)
    return match.group(1).strip() if match else text.strip()


def parse_output(schema: type[T], text: str) -> T:
    """Parse model text into `schema`, tolerating code fences and chatter around one object."""
    body = strip_code_fences(text)
    if not body.startswith(("{", "[")):
        start, end = body.find("{"), body.rfind("}")
        if start == -1 or end <= start:
            raise InvalidOutputError("reply contains no JSON object")
        body = body[start : end + 1]
    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise InvalidOutputError(f"invalid JSON: {exc.msg} at line {exc.lineno}") from exc
    try:
        return schema.model_validate(data)
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in err['loc']) or '(root)'}: {err['msg']}"
            for err in exc.errors()[:10]
        )
        raise InvalidOutputError(f"does not match the schema: {problems}") from exc


def schema_instructions(schema: type[BaseModel]) -> str:
    """The output contract appended to every system prompt (schema in the prompt)."""
    return (
        "Reply with a single JSON object and nothing else: no Markdown, no code fences, "
        "no commentary. It must validate against this JSON Schema:\n"
        + json.dumps(schema.model_json_schema(), separators=(",", ":"))
    )


def repair_prompt(prompt: str, bad_reply: str, problem: str) -> str:
    return (
        f"{prompt}\n\n"
        "Your previous reply could not be used because it "
        f"{problem}.\n<previous_reply>\n{bad_reply[:4000]}\n</previous_reply>\n"
        "Reply again with only the corrected JSON object."
    )


class LLMClient:
    def __init__(
        self,
        providers: list[Provider],
        cache: SQLiteCache,
        logger: CallLogger,
    ) -> None:
        self._providers = providers
        self._cache = cache
        self._logger = logger

    @property
    def provider_names(self) -> list[str]:
        return [p.name for p in self._providers]

    def json(
        self,
        schema: type[T],
        system: str,
        prompt: str,
        *,
        purpose: str,
        brand_id: UUID | None = None,
        content_version_id: UUID | None = None,
    ) -> T:
        """Return the model's answer to `prompt` as a validated `schema` instance."""
        key = cache_key(schema.__name__, system, prompt)
        context = {
            "purpose": purpose,
            "brand_id": brand_id,
            "content_version_id": content_version_id,
        }

        cached = self._cache.get(key)
        if isinstance(cached, dict):
            try:
                result = schema.model_validate(cached["output"])
            except (KeyError, ValidationError):
                pass  # stale entry (schema changed): ask a provider again
            else:
                self._logger.log(
                    CallRecord(provider=cached.get("provider", "cache"),
                               model=cached.get("model", ""), ok=True, cached=True,
                               latency_ms=0, **context)
                )  # fmt: skip
                return result

        full_system = f"{system}\n\n{CONTENT_GUARD}\n\n{schema_instructions(schema)}"
        attempts: list[tuple[str, str]] = []
        for provider in self._providers:
            try:
                result = self._ask(provider, schema, full_system, prompt, context)
            except RateLimitError:
                attempts.append((provider.name, "rate limited"))
                continue
            except ProviderError as exc:
                attempts.append((provider.name, str(exc)))
                continue
            except InvalidOutputError as exc:
                attempts.append((provider.name, f"invalid output after one repair ({exc})"))
                continue
            self._cache.set(
                key,
                {"provider": provider.name, "model": provider.model,
                 "output": result.model_dump(mode="json")},
            )  # fmt: skip
            return result
        raise LLMUnavailableError(purpose, attempts)

    def _ask(
        self, provider: Provider, schema: type[T], system: str, prompt: str, context: dict
    ) -> T:
        """One provider: a call, plus at most one repair call if the output is invalid.

        Each call is logged once: ok only if its reply validated against the schema.
        """
        failure: tuple[str, InvalidOutputError] | None = None
        for _ in range(2):
            ask = prompt if failure is None else repair_prompt(prompt, failure[0], str(failure[1]))
            started = time.perf_counter()
            try:
                reply = provider.complete(system, ask)
            except ProviderError as exc:
                self._log(provider, started, context, ok=False, error=str(exc))
                raise
            try:
                result = parse_output(schema, reply)
            except InvalidOutputError as exc:
                self._log(provider, started, context, ok=False, error=f"invalid output: {exc}")
                failure = (reply, exc)
                continue
            self._log(provider, started, context, ok=True)
            return result
        assert failure is not None
        raise failure[1]

    def _log(
        self, provider: Provider, started: float, context: dict, *, ok: bool,
        error: str | None = None,
    ) -> None:  # fmt: skip
        self._logger.log(
            CallRecord(provider=provider.name, model=provider.model, ok=ok,
                       latency_ms=int((time.perf_counter() - started) * 1000),
                       error=error[:500] if error else None, **context)
        )  # fmt: skip
