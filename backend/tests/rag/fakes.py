"""A fake embedder (no network) for tests that store or search rules and facts."""

import hashlib
import math


def unit_vector(seed: str, dims: int = 768) -> list[float]:
    """A deterministic pseudo-random unit vector for `seed`."""
    values: list[float] = []
    counter = 0
    while len(values) < dims:
        digest = hashlib.sha256(f"{seed}:{counter}".encode()).digest()
        values.extend((b - 127.5) / 127.5 for b in digest)
        counter += 1
    values = values[:dims]
    norm = math.sqrt(sum(v * v for v in values))
    return [v / norm for v in values]


def blend(a: list[float], b: list[float], weight: float) -> list[float]:
    """A unit vector between a and b (weight 0 -> a, 1 -> b)."""
    mixed = [(1 - weight) * x + weight * y for x, y in zip(a, b, strict=True)]
    norm = math.sqrt(sum(v * v for v in mixed))
    return [v / norm for v in mixed]


class FakeEmbedder:
    """Returns `overrides[text]` if given, else a stable vector per text."""

    model = "fake-embedding"
    dimensions = 768

    def __init__(self, overrides: dict[str, list[float]] | None = None) -> None:
        self.overrides = overrides or {}
        self.calls: list[tuple[str, list[str]]] = []

    def _vectors(self, texts: list[str]) -> list[list[float]]:
        return [self.overrides.get(t) or unit_vector(t) for t in texts]

    def embed_documents(self, texts: list[str], **_: object) -> list[list[float]]:
        self.calls.append(("doc", list(texts)))
        return self._vectors(texts)

    def embed_queries(self, texts: list[str], **_: object) -> list[list[float]]:
        self.calls.append(("query", list(texts)))
        return self._vectors(texts)
