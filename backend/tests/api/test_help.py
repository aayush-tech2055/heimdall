import json

from app.api import help as help_api
from app.llm.cache import SQLiteCache
from app.llm.call_log import MemoryCallLogger
from app.llm.client import LLMClient
from app.llm.errors import ProviderError
from app.main import app
from tests.api.conftest import sign_in_as
from tests.llm.fakes import FakeProvider


def _client(*replies):
    provider = FakeProvider("groq", list(replies), model="openai/gpt-oss-20b")
    logger = MemoryCallLogger()
    client = LLMClient([provider], SQLiteCache(":memory:"), logger, rate_limit_rounds=1)
    app.dependency_overrides[help_api.help_client] = lambda: client
    return provider, logger


def test_help_answers_with_role_and_page_context(api):
    sign_in_as("creator")
    provider, logger = _client(json.dumps({"answer": 'Press "Submit to manager".'}))
    response = api.post(
        "/help/chat",
        json={
            "question": "How do I send this to my manager? I am cass@x.example",
            "path": "/creator/content/123",
            "history": [{"role": "user", "text": "hi"}, {"role": "assistant", "text": "Hello"}],
        },
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"answer": 'Press "Submit to manager".'}
    [(system, prompt)] = provider.calls
    assert "help assistant" in system
    assert "CREATOR portal" in prompt and "ADMIN portal" not in prompt
    assert "Content review (creator)" in prompt
    assert "cass@x.example" not in prompt  # redacted before the AI call
    assert "<content>" in prompt and "User: hi" in prompt
    assert logger.records[0].purpose == "help"


def test_help_is_busy_when_no_provider_answers(api):
    sign_in_as("manager")
    _client(ProviderError("down"))
    response = api.post("/help/chat", json={"question": "What is Re-evaluate?"})
    assert response.status_code == 503


def test_help_needs_sign_in(api):
    response = api.post("/help/chat", json={"question": "hi"})
    assert response.status_code == 401
