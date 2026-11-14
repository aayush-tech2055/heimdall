"""Fake providers for AI-layer tests (no network)."""

from app.llm.errors import ProviderError


class FakeProvider:
    """Returns scripted replies in order; an Exception in the script is raised instead."""

    def __init__(self, name: str, replies: list[str | Exception], model: str = "fake-1") -> None:
        self.name = name
        self.model = model
        self._replies = list(replies)
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, prompt: str) -> str:
        self.calls.append((system, prompt))
        if not self._replies:
            raise ProviderError(f"{self.name}: no scripted reply left")
        reply = self._replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply
