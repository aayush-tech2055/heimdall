"""Errors raised by the AI layer."""


class ProviderError(Exception):
    """A provider call failed (network error, HTTP error, empty or unreadable reply)."""


class RateLimitError(ProviderError):
    """The provider rejected the call with a rate limit (HTTP 429 or quota exhausted)."""

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class LLMUnavailableError(RuntimeError):
    """No provider produced a valid answer. The message lists what happened with each one."""

    def __init__(self, purpose: str, attempts: list[tuple[str, str]]) -> None:
        self.purpose = purpose
        self.attempts = attempts
        if attempts:
            detail = "; ".join(f"{name}: {reason}" for name, reason in attempts)
            message = f"Every AI provider failed for '{purpose}': {detail}"
        else:
            message = (
                f"No AI provider is configured for '{purpose}': set GEMINI_API_KEY, "
                "GROQ_API_KEY or OPENROUTER_API_KEY (and OPENROUTER_MODEL) in backend/.env"
            )
        super().__init__(message)
