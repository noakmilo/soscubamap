import pytest
import sys
import types

import app.services.ai_text as ai_text


class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, content):
        self._content = content

    def create(self, **kwargs):
        return _FakeResponse(self._content)


class _FakeChat:
    def __init__(self, content):
        self.completions = _FakeCompletions(content)


class _FakeClient:
    def __init__(self, content):
        self.chat = _FakeChat(content)


class TestOptimizeReportText:
    def test_invalid_field(self, app):
        with app.app_context():
            with pytest.raises(ValueError):
                ai_text.optimize_report_text("invalid", "texto")

    def test_rejects_empty_text(self, app):
        with app.app_context():
            with pytest.raises(ValueError):
                ai_text.optimize_report_text("title", "   ")

    def test_rejects_too_long_title(self, app):
        with app.app_context():
            with pytest.raises(ValueError):
                ai_text.optimize_report_text("title", "a" * 201)

    def test_rejects_malicious_text(self, app):
        with app.app_context():
            with pytest.raises(ValueError):
                ai_text.optimize_report_text("description", "<script>alert(1)</script>")

    def test_returns_optimized_title(self, app, monkeypatch):
        with app.app_context():
            monkeypatch.setattr(ai_text, "_load_openai_client", lambda: _FakeClient("  Titulo corregido  "))
            result = ai_text.optimize_report_text(
                "title",
                "titulo original",
                title_context="Contexto de titulo",
                description_context="Contexto de descripcion",
            )
            assert result == "Titulo corregido"

    def test_returns_optimized_description(self, app, monkeypatch):
        with app.app_context():
            monkeypatch.setattr(
                ai_text,
                "_load_openai_client",
                lambda: _FakeClient("Descripcion corregida con mejor redaccion."),
            )
            result = ai_text.optimize_report_text(
                "description",
                "descripcion original con faltas",
                title_context="Titulo relacionado",
                description_context="Descripcion relacionada",
            )
            assert result == "Descripcion corregida con mejor redaccion."


class TestLoadOpenAIClientCompatibility:
    def test_fallback_when_openai_raises_proxies_typeerror(self, app, monkeypatch):
        with app.app_context():
            app.config["OPENAI_API_KEY"] = "test-key"
            app.config["OPENAI_TIMEOUT_SECONDS"] = 11

            calls = {"count": 0}

            class FakeOpenAI:
                def __init__(self, **kwargs):
                    calls["count"] += 1
                    if calls["count"] == 1:
                        raise TypeError(
                            "Client.__init__() got an unexpected keyword argument 'proxies'"
                        )
                    self.kwargs = kwargs

            class FakeHttpClient:
                def __init__(self, timeout=None, follow_redirects=None):
                    self.timeout = timeout
                    self.follow_redirects = follow_redirects

            fake_openai_module = types.SimpleNamespace(OpenAI=FakeOpenAI)
            fake_httpx_module = types.SimpleNamespace(Client=FakeHttpClient)
            monkeypatch.setitem(sys.modules, "openai", fake_openai_module)
            monkeypatch.setitem(sys.modules, "httpx", fake_httpx_module)

            client = ai_text._load_openai_client()
            assert isinstance(client, FakeOpenAI)
            assert "http_client" in client.kwargs
            assert client.kwargs["api_key"] == "test-key"
