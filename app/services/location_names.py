import re
import unicodedata
from typing import Any

from app.services.cuba_locations import MUNICIPALITIES, PROVINCES

_CAMEL_BOUNDARY_RE = re.compile(r"(?<=[a-záéíóúñü])(?=[A-ZÁÉÍÓÚÑÜ])")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_CONNECTOR_WORDS = {"de", "del", "la", "las", "los", "y", "el"}
_UNKNOWN_KEYS = {
    "na",
    "nd",
    "nondisponible",
    "nodisponible",
    "desconocido",
    "sindatos",
    "unknown",
    "none",
    "null",
}


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _split_words(value: str) -> str:
    text = value.replace("_", " ").replace("-", " ")
    text = _CAMEL_BOUNDARY_RE.sub(" ", text)
    return " ".join(text.split())


def _normalize_key(value: Any) -> str:
    text = _clean_text(value)
    if not text:
        return ""
    normalized = _split_words(text).lower()
    normalized = unicodedata.normalize("NFKD", normalized)
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return _NON_ALNUM_RE.sub("", normalized)


def _humanize(value: str) -> str:
    spaced = _split_words(value)
    if not spaced:
        return value
    words = []
    for index, raw_word in enumerate(spaced.split()):
        lower = raw_word.lower()
        if index > 0 and lower in _CONNECTOR_WORDS:
            words.append(lower)
        else:
            words.append(lower.capitalize())
    return " ".join(words)


_PROVINCE_BY_KEY = {_normalize_key(name): name for name in PROVINCES}
_PROVINCE_ALIAS_BY_KEY = {
    "ciudaddelahabana": "La Habana",
    "habana": "La Habana",
    "isladepinos": "Isla de la Juventud",
}

_MUNICIPALITY_BY_KEY: dict[str, str] = {}
_MUNICIPALITY_BY_PROVINCE_KEY: dict[str, dict[str, str]] = {}
for province_name, municipality_names in MUNICIPALITIES.items():
    province_key = _normalize_key(province_name)
    bucket = _MUNICIPALITY_BY_PROVINCE_KEY.setdefault(province_key, {})
    for municipality_name in municipality_names:
        municipality_key = _normalize_key(municipality_name)
        if municipality_key not in _MUNICIPALITY_BY_KEY:
            _MUNICIPALITY_BY_KEY[municipality_key] = municipality_name
        bucket[municipality_key] = municipality_name

_MUNICIPALITY_ALIAS_BY_KEY = {
    "habanavieja": "La Habana Vieja",
}


def normalize_location_key(value: Any) -> str:
    return _normalize_key(value)


def canonicalize_province_name(value: Any) -> str | None:
    text = _clean_text(value)
    if text is None:
        return None
    key = _normalize_key(text)
    if not key or key in _UNKNOWN_KEYS:
        return None
    alias = _PROVINCE_ALIAS_BY_KEY.get(key)
    if alias:
        return alias
    canonical = _PROVINCE_BY_KEY.get(key)
    if canonical:
        return canonical
    return _humanize(text)


def canonicalize_municipality_name(value: Any, province_name: Any = None) -> str | None:
    text = _clean_text(value)
    if text is None:
        return None
    key = _normalize_key(text)
    if not key or key in _UNKNOWN_KEYS:
        return None

    canonical_province = canonicalize_province_name(province_name)
    if canonical_province:
        province_key = _normalize_key(canonical_province)
        province_bucket = _MUNICIPALITY_BY_PROVINCE_KEY.get(province_key, {})
        canonical_in_province = province_bucket.get(key)
        if canonical_in_province:
            return canonical_in_province

    alias = _MUNICIPALITY_ALIAS_BY_KEY.get(key)
    if alias:
        return alias

    canonical_global = _MUNICIPALITY_BY_KEY.get(key)
    if canonical_global:
        return canonical_global

    return _humanize(text)


def canonicalize_location_names(
    province_name: Any,
    municipality_name: Any,
) -> tuple[str | None, str | None]:
    canonical_province = canonicalize_province_name(province_name)
    canonical_municipality = canonicalize_municipality_name(
        municipality_name,
        canonical_province,
    )
    return canonical_province, canonical_municipality
