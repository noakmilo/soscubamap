import pytest

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
