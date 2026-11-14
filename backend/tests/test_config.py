from app.config import Settings


def test_provider_order_parsed_and_lowercased(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER_ORDER", " Gemini , groq,,OpenRouter ")
    settings = Settings(_env_file=None)
    assert settings.provider_order == ["gemini", "groq", "openrouter"]


def test_cors_origins_split(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "http://a.test, http://b.test")
    settings = Settings(_env_file=None)
    assert settings.cors_origin_list == ["http://a.test", "http://b.test"]
