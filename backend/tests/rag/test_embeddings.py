"""Embedder: batching, normalisation, caching, retry and backoff (mock transport, no network)."""

import json
import math

import httpx
import pytest

from app.llm.cache import SQLiteCache
from app.llm.call_log import MemoryCallLogger
from app.rag.embeddings import Embedder, EmbeddingError, normalise

DIMS = 768


class FakeGemini:
    """Mock batchEmbedContents: vector i is [len(text), i+1, 0, ...], with scripted failures."""

    def __init__(self, failures: list[httpx.Response] | None = None) -> None:
        self.failures = list(failures or [])
        self.requests: list[dict] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        self.requests.append(body)
        if self.failures:
            return self.failures.pop(0)
        embeddings = []
        for i, r in enumerate(body["requests"]):
            length = float(len(r["content"]["parts"][0]["text"]))
            embeddings.append({"values": [length, float(i + 1)] + [0.0] * (DIMS - 2)})
        return httpx.Response(200, json={"embeddings": embeddings})

    @property
    def texts_sent(self) -> list[str]:
        return [r["content"]["parts"][0]["text"] for b in self.requests for r in b["requests"]]


def make_embedder(fake: FakeGemini, cache=None, **kwargs):
    sleeps: list[float] = []
    logger = MemoryCallLogger()
    embedder = Embedder(
        "key", "gemini-embedding-001", cache or SQLiteCache(":memory:", "embeddings"), logger,
        client=httpx.Client(transport=httpx.MockTransport(fake)), sleep=sleeps.append, **kwargs,
    )  # fmt: skip
    return embedder, sleeps, logger


def test_request_shape_task_types_and_dimensions():
    fake = FakeGemini()
    embedder, _, _ = make_embedder(fake)
    embedder.embed_documents(["Never call the course cheap."])
    embedder.embed_queries(["Our cheap course!"])
    doc, query = fake.requests
    assert doc["requests"][0]["taskType"] == "RETRIEVAL_DOCUMENT"
    assert query["requests"][0]["taskType"] == "RETRIEVAL_QUERY"
    assert doc["requests"][0]["outputDimensionality"] == 768
    assert doc["requests"][0]["model"] == "models/gemini-embedding-001"


def test_vectors_are_normalised_and_in_input_order():
    embedder, _, _ = make_embedder(FakeGemini())
    vectors = embedder.embed_documents(["abc", "abcdefgh"])
    assert len(vectors) == 2 and all(len(v) == DIMS for v in vectors)
    for v in vectors:
        assert math.isclose(math.sqrt(sum(x * x for x in v)), 1.0, rel_tol=1e-9)
    assert vectors[0][0] == pytest.approx(3 / math.sqrt(3**2 + 1**2))
    assert vectors[1][0] == pytest.approx(8 / math.sqrt(8**2 + 2**2))


def test_batches_of_100():
    fake = FakeGemini()
    embedder, _, logger = make_embedder(fake)
    texts = [f"rule number {i}" for i in range(250)]
    vectors = embedder.embed_documents(texts)
    assert [len(b["requests"]) for b in fake.requests] == [100, 100, 50]
    assert len(vectors) == 250
    assert len(logger.records) == 3 and all(r.ok for r in logger.records)


def test_cache_hit_makes_no_call_and_only_missing_texts_are_sent():
    cache = SQLiteCache(":memory:", "embeddings")
    first = FakeGemini()
    embedder, _, _ = make_embedder(first, cache)
    a = embedder.embed_documents(["alpha", "beta"])

    second = FakeGemini()
    embedder2, _, _ = make_embedder(second, cache)
    assert embedder2.embed_documents(["alpha", "beta"]) == a
    assert second.requests == []
    embedder2.embed_documents(["beta", "gamma", "gamma"])
    assert second.texts_sent == ["gamma"]  # cached and duplicate texts are not sent


def test_document_and_query_vectors_are_cached_separately():
    fake = FakeGemini()
    embedder, _, _ = make_embedder(fake)
    embedder.embed_documents(["same text"])
    embedder.embed_queries(["same text"])
    assert len(fake.requests) == 2


def test_rate_limit_is_retried_with_exponential_backoff():
    fake = FakeGemini([httpx.Response(429), httpx.Response(503), httpx.Response(429)])
    embedder, sleeps, logger = make_embedder(fake, base_delay=1.0)
    assert len(embedder.embed_documents(["x"])) == 1
    assert sleeps == [1.0, 2.0, 4.0]
    assert [r.ok for r in logger.records] == [False, False, False, True]


def test_retry_after_header_is_respected_and_delay_is_capped():
    fake = FakeGemini(
        [httpx.Response(429, headers={"retry-after": "7"})] + [httpx.Response(429)] * 5
    )
    embedder, sleeps, _ = make_embedder(fake, max_attempts=6, base_delay=4.0, max_delay=10.0)
    with pytest.raises(EmbeddingError, match="after 6 attempts"):
        embedder.embed_documents(["x"])
    assert sleeps == [7.0, 8.0, 10.0, 10.0, 10.0]


def test_client_errors_are_not_retried():
    fake = FakeGemini([httpx.Response(400, text="bad request")])
    embedder, sleeps, _ = make_embedder(fake)
    with pytest.raises(EmbeddingError, match="HTTP 400"):
        embedder.embed_documents(["x"])
    assert sleeps == [] and len(fake.requests) == 1


def test_wrong_dimensions_are_rejected():
    fake = FakeGemini([httpx.Response(200, json={"embeddings": [{"values": [1.0, 0.0]}]})])
    embedder, _, _ = make_embedder(fake)
    with pytest.raises(EmbeddingError, match="768"):
        embedder.embed_documents(["x"])


def test_empty_text_and_missing_key_fail_clearly():
    embedder, _, _ = make_embedder(FakeGemini())
    with pytest.raises(EmbeddingError, match="empty"):
        embedder.embed_documents(["ok", "  "])
    no_key = Embedder("", "m", SQLiteCache(":memory:"), MemoryCallLogger())
    with pytest.raises(EmbeddingError, match="no fallback"):
        no_key.embed_documents(["x"])


def test_normalise_rejects_zero_vector():
    with pytest.raises(EmbeddingError):
        normalise([0.0, 0.0])
