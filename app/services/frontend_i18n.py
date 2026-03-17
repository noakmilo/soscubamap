import json
from functools import lru_cache
from pathlib import Path

from babel import Locale
from babel.core import UnknownLocaleError
from flask import current_app


def _translations_root() -> Path:
    configured_paths = current_app.config.get(
        "BABEL_TRANSLATION_DIRECTORIES", "../translations"
    )
    primary = configured_paths.split(";")[0].split(",")[0].strip() or "../translations"
    return (Path(current_app.root_path) / primary).resolve()


@lru_cache(maxsize=1)
def get_supported_frontend_locales() -> list[str]:
    frontend_dir = _translations_root() / "frontend"
    locales = sorted(
        path.stem for path in frontend_dir.glob("*.json") if path.is_file()
    )
    if locales:
        return locales
    default_locale = str(current_app.config.get("BABEL_DEFAULT_LOCALE", "es"))
    return [default_locale]


def normalize_frontend_locale(locale: str | None) -> str:
    supported_locales = get_supported_frontend_locales()
    if locale in supported_locales:
        return locale
    default_locale = str(current_app.config.get("BABEL_DEFAULT_LOCALE", "es"))
    if default_locale in supported_locales:
        return default_locale
    return supported_locales[0]


def _display_name(locale_code: str) -> str:
    normalized_code = locale_code.replace("-", "_")
    try:
        locale = Locale.parse(normalized_code)
        return locale.get_display_name(normalized_code).title()
    except (UnknownLocaleError, ValueError):
        return locale_code.upper()


def get_language_choices() -> list[dict[str, str]]:
    return [
        {
            "code": locale_code,
            "label": _display_name(locale_code),
        }
        for locale_code in get_supported_frontend_locales()
    ]


@lru_cache(maxsize=8)
def _load_frontend_translations(locale: str) -> dict[str, str]:
    path = _translations_root() / "frontend" / f"{locale}.json"
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v) for k, v in data.items()}


def get_frontend_translations(locale: str | None) -> dict[str, str]:
    return _load_frontend_translations(normalize_frontend_locale(locale)).copy()
