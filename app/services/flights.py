from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
from flask import current_app, has_app_context
from sqlalchemy import func, or_
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models.flight_aircraft import FlightAircraft
from app.models.flight_aircraft_photo_revision import FlightAircraftPhotoRevision
from app.models.flight_airport import FlightAirport
from app.models.flight_event import FlightEvent
from app.models.flight_ingestion_run import FlightIngestionRun
from app.models.flight_layer_snapshot import FlightLayerSnapshot
from app.models.flight_position import FlightPosition


logger = logging.getLogger(__name__)


WINDOW_HOURS_SUPPORTED = (168, 24, 6, 2)
_CLEAN_TOKEN_RE = re.compile(r"[^a-z0-9]+")
_AIRPORT_CODE_TOKEN_RE = re.compile(r"[A-Z0-9]{3,4}")
DEFAULT_CUBA_LIVE_BOUNDS = "24.2,19.4,-85.2,-73.9"
DEFAULT_CUBA_AIRPORT_CODES = (
    "MUHA,HAV,MUCU,SCU,MUVR,VRA,MUCC,CCC,MUCM,CMW,"
    "MUSC,SNU,MUBY,BCA,MUGT,BWW,MUMZ,MZG,MUCL,CYO,MUBA"
)
DEFAULT_OPENSKY_TOKEN_URL = (
    "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"
)
DEFAULT_OPENSKY_API_BASE_URL = "https://opensky-network.org/api"
_OPENSKY_TOKEN_CACHE: dict[str, Any] = {
    "access_token": "",
    "expires_at_epoch": 0.0,
}
_WORLD_AIRPORTS_BY_CODE: dict[str, dict[str, Any]] | None = None
_WORLD_AIRPORTS_LOAD_ATTEMPTED = False


def _build_cuba_code_aliases() -> dict[str, str]:
    tokens = [
        str(chunk or "").strip().upper()[:8]
        for chunk in str(DEFAULT_CUBA_AIRPORT_CODES or "").split(",")
    ]
    tokens = [token for token in tokens if token]
    aliases: dict[str, str] = {}
    for idx in range(0, max(0, len(tokens) - 1), 2):
        first = tokens[idx]
        second = tokens[idx + 1]
        if len(first) == 4 and len(second) == 3:
            aliases[first] = second
            aliases[second] = first
        elif len(first) == 3 and len(second) == 4:
            aliases[first] = second
            aliases[second] = first
    return aliases


_CUBA_CODE_ALIASES = _build_cuba_code_aliases()


@dataclass
class RequestContext:
    request_cap: int
    rate_limit_per_second: int
    request_count: int = 0
    estimated_credits: int = 0
    budget_exhausted: bool = False
    last_request_epoch: float = 0.0


@dataclass
class FetchBatch:
    records: list[dict[str, Any]] = field(default_factory=list)
    seen: int = 0
    errors: list[str] = field(default_factory=list)
    budget_exhausted: bool = False
    rate_limited: bool = False


class RequestBudgetExhausted(RuntimeError):
    pass


class FlightsApiRateLimited(RuntimeError):
    pass


def _config_value(name: str, default: Any):
    if has_app_context():
        return current_app.config.get(name, default)
    return default


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        numeric = float(value)
    except Exception:
        return default
    if not math.isfinite(numeric):
        return default
    return numeric


def _safe_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if not text:
        return default
    return text in {"1", "true", "yes", "on"}


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _normalize_utc_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _parse_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None

    normalized = text
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    normalized = normalized.replace(" UTC", "")

    try:
        parsed = datetime.fromisoformat(normalized)
        return _normalize_utc_datetime(parsed)
    except Exception:
        pass

    patterns = [
        "%Y-%m-%d %H:%M:%S.%f %z",
        "%Y-%m-%d %H:%M:%S %z",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
    ]
    for pattern in patterns:
        try:
            parsed = datetime.strptime(text, pattern)
            return _normalize_utc_datetime(parsed)
        except Exception:
            continue

    return None


def serialize_flight_time(value: datetime | None) -> str | None:
    normalized = _normalize_utc_datetime(value)
    if not normalized:
        return None
    return normalized.isoformat() + "Z"


def _clean_text(value: Any, *, upper: bool = False, limit: int = 255) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if upper:
        text = text.upper()
    if len(text) > limit:
        return text[:limit]
    return text


def _world_airports_json_path() -> Path:
    return Path(__file__).resolve().parents[1] / "static" / "data" / "aeropuertos.json"


def _parse_world_airport_row(row: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None

    # Legacy local schema:
    # { "codigo": "HAV", "ciudad": "Havana", "pais": "CU", "latitud": 23.0, "longitud": -82.0 }
    legacy_code = _clean_text(row.get("codigo"), upper=True, limit=8)
    if legacy_code:
        legacy_iata = _clean_text(row.get("iata"), upper=True, limit=8)
        legacy_icao = _clean_text(row.get("icao"), upper=True, limit=8)
        if not legacy_iata and len(legacy_code) == 3:
            legacy_iata = legacy_code
        if not legacy_icao and len(legacy_code) == 4:
            legacy_icao = legacy_code
        codes = [code for code in (legacy_iata, legacy_icao, legacy_code) if code]
        # Remove duplicates preserving order.
        codes = list(dict.fromkeys(codes))
        return {
            "codes": codes,
            "name": _clean_text(row.get("nombre"), limit=255),
            "city": _clean_text(row.get("ciudad"), limit=120),
            "country": _clean_text(row.get("pais"), upper=True, limit=120),
            "latitude": _safe_float(row.get("latitud")),
            "longitude": _safe_float(row.get("longitud")),
            "iata": legacy_iata,
            "icao": legacy_icao,
        }

    # CDN airports-json schema:
    # { "ident": "MUHA", "iata_code": "HAV", "municipality": "Havana", "iso_country": "CU", ... }
    icao = _clean_text(row.get("ident"), upper=True, limit=8)
    iata = _clean_text(row.get("iata_code"), upper=True, limit=8)
    codes = [code for code in (iata, icao) if code]
    if not codes:
        return None

    return {
        "codes": codes,
        "name": _clean_text(row.get("name"), limit=255),
        "city": _clean_text(row.get("municipality"), limit=120),
        "country": _clean_text(row.get("iso_country"), upper=True, limit=120),
        "latitude": _safe_float(row.get("latitude_deg")),
        "longitude": _safe_float(row.get("longitude_deg")),
        "iata": iata,
        "icao": icao,
    }


def _merge_world_airport_record(
    current: dict[str, Any] | None,
    incoming: dict[str, Any],
) -> dict[str, Any]:
    if current is None:
        return dict(incoming)

    merged = dict(current)
    for key in ("name", "city", "country", "iata", "icao"):
        if (not _clean_text(merged.get(key), limit=255)) and _clean_text(incoming.get(key), limit=255):
            merged[key] = incoming.get(key)

    if merged.get("latitude") is None and incoming.get("latitude") is not None:
        merged["latitude"] = incoming.get("latitude")
    if merged.get("longitude") is None and incoming.get("longitude") is not None:
        merged["longitude"] = incoming.get("longitude")

    return merged


def _load_world_airports_index() -> dict[str, dict[str, Any]]:
    global _WORLD_AIRPORTS_BY_CODE, _WORLD_AIRPORTS_LOAD_ATTEMPTED
    if _WORLD_AIRPORTS_BY_CODE is not None:
        return _WORLD_AIRPORTS_BY_CODE
    if _WORLD_AIRPORTS_LOAD_ATTEMPTED:
        return {}

    _WORLD_AIRPORTS_LOAD_ATTEMPTED = True
    path = _world_airports_json_path()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("No se pudo leer el catalogo de aeropuertos (%s): %s", path, exc)
        _WORLD_AIRPORTS_BY_CODE = {}
        return _WORLD_AIRPORTS_BY_CODE

    index: dict[str, dict[str, Any]] = {}
    rows = payload if isinstance(payload, list) else []
    for row in rows:
        parsed = _parse_world_airport_row(row)
        if not parsed:
            continue

        for code in parsed.get("codes") or []:
            if not code:
                continue
            record = {
                "code": code,
                "name": _clean_text(parsed.get("name"), limit=255) or code,
                "city": _clean_text(parsed.get("city"), limit=120),
                "country": _clean_text(parsed.get("country"), upper=True, limit=120),
                "latitude": _safe_float(parsed.get("latitude")),
                "longitude": _safe_float(parsed.get("longitude")),
                "iata": _clean_text(parsed.get("iata"), upper=True, limit=8),
                "icao": _clean_text(parsed.get("icao"), upper=True, limit=8),
            }
            current = index.get(code)
            index[code] = _merge_world_airport_record(current, record)

    _WORLD_AIRPORTS_BY_CODE = index
    logger.info("Catalogo de aeropuertos estatico cargado: %s codigos", len(index))
    return _WORLD_AIRPORTS_BY_CODE


def _lookup_world_airport(
    icao_code: str | None,
    iata_code: str | None,
) -> dict[str, Any]:
    iata = _clean_text(iata_code, upper=True, limit=8)
    icao = _clean_text(icao_code, upper=True, limit=8)
    if not iata and not icao:
        return {}

    index = _load_world_airports_index()
    for code in (iata, icao):
        if not code:
            continue
        match = index.get(code)
        if match:
            return match

    # Fallback Cuba ICAO<->IATA aliases (e.g. MUHA <-> HAV)
    for code in (iata, icao):
        if not code:
            continue
        alias = _CUBA_CODE_ALIASES.get(code)
        if not alias:
            continue
        match = index.get(alias)
        if match:
            return match
    return {}


def _infer_airport_codes_from_text(value: Any) -> tuple[str, str]:
    text = _clean_text(value, upper=True, limit=255)
    if not text:
        return "", ""

    icao = ""
    iata = ""
    for token in _AIRPORT_CODE_TOKEN_RE.findall(text):
        if not any(ch.isalpha() for ch in token):
            continue
        if len(token) == 4 and not icao:
            icao = token
        elif len(token) == 3 and not iata:
            iata = token
        if icao and iata:
            break
    return icao, iata


def _normalize_token(value: Any) -> str:
    text = _clean_text(value, upper=False, limit=255).lower()
    if not text:
        return ""
    return _CLEAN_TOKEN_RE.sub("", text)


def _get_nested(payload: Any, path: str) -> Any:
    current = payload
    for key in path.split("."):
        if isinstance(current, dict) and key in current:
            current = current.get(key)
            continue
        return None
    return current


def _pick(payload: Any, *paths: str) -> Any:
    for path in paths:
        value = _get_nested(payload, path)
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def _walk_for_list(value: Any, max_depth: int = 3, depth: int = 0) -> list[Any] | None:
    if depth > max_depth:
        return None
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for child in value.values():
            found = _walk_for_list(child, max_depth=max_depth, depth=depth + 1)
            if found is not None:
                return found
    return None


def _extract_dict_map_items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, dict):
        return []

    # Direct record dict.
    if _pick(
        value,
        "fr24_id",
        "id",
        "flight_id",
        "callsign",
        "lat",
        "latitude",
        "lon",
        "longitude",
    ) is not None:
        return [value]

    records: list[dict[str, Any]] = []
    for child in value.values():
        if not isinstance(child, dict):
            continue
        marker = _pick(
            child,
            "fr24_id",
            "id",
            "flight_id",
            "callsign",
            "lat",
            "latitude",
            "lon",
            "longitude",
        )
        if marker is None:
            continue
        records.append(child)
    return records


def _walk_for_dict_map(value: Any, max_depth: int = 4, depth: int = 0) -> list[dict[str, Any]] | None:
    if depth > max_depth:
        return None

    mapped = _extract_dict_map_items(value)
    if mapped:
        return mapped

    if isinstance(value, dict):
        for child in value.values():
            found = _walk_for_dict_map(child, max_depth=max_depth, depth=depth + 1)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _walk_for_dict_map(child, max_depth=max_depth, depth=depth + 1)
            if found:
                return found
    return None


def _extract_items(payload: Any, preferred_paths: tuple[str, ...]) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if not isinstance(payload, dict):
        return []

    for path in preferred_paths:
        candidate = _get_nested(payload, path)
        if isinstance(candidate, list):
            return [item for item in candidate if isinstance(item, dict)]
        mapped = _extract_dict_map_items(candidate)
        if mapped:
            return mapped

    fallback = _walk_for_list(payload)
    if isinstance(fallback, list):
        return [item for item in fallback if isinstance(item, dict)]

    mapped_fallback = _walk_for_dict_map(payload)
    if mapped_fallback:
        return mapped_fallback
    return []


def _country_is_cuba(country_name: Any, country_code: Any) -> bool:
    code = _clean_text(country_code, upper=True, limit=8)
    if code in {"CU", "CUB"}:
        return True

    name = _normalize_token(country_name)
    if not name:
        return False
    return "cuba" in name


def _normalize_identity_key(
    call_sign: str,
    model: str,
    registration: str,
    external_flight_id: str,
) -> str:
    call_token = _normalize_token(call_sign)
    model_token = _normalize_token(model)
    reg_token = _normalize_token(registration)
    ext_token = _normalize_token(external_flight_id)

    if call_token and model_token:
        return f"{call_token}|{model_token}"[:255]
    if call_token and reg_token:
        return f"{call_token}|{reg_token}"[:255]
    if reg_token and model_token:
        return f"{reg_token}|{model_token}"[:255]
    if call_token:
        return call_token[:255]
    if reg_token:
        return reg_token[:255]
    if ext_token:
        return f"flight|{ext_token}"[:255]

    return "unknown"


def _build_event_key(
    external_flight_id: str,
    identity_key: str,
    departure_at_utc: datetime | None,
    destination_icao: str,
    destination_iata: str,
    destination_name: str,
) -> str:
    ext = _normalize_token(external_flight_id)
    if ext:
        return f"fr24|{ext}"[:255]

    dep = serialize_flight_time(departure_at_utc) or ""
    destination_token = (
        _normalize_token(destination_icao)
        or _normalize_token(destination_iata)
        or _normalize_token(destination_name)
    )
    base = "|".join(
        part
        for part in [
            _normalize_token(identity_key),
            _normalize_token(dep),
            destination_token,
        ]
        if part
    )
    if not base:
        base = "unknown"

    if len(base) <= 200:
        return base

    digest = hashlib.sha1(base.encode("utf-8")).hexdigest()
    return f"event|{digest}"[:255]


def get_flights_enabled() -> bool:
    return bool(_config_value("FLIGHTS_ENABLED", False))


def get_flights_api_key() -> str:
    return str(_config_value("FLIGHTS_API_KEY", "") or "").strip()


def get_flights_api_base_url() -> str:
    raw = str(
        _config_value(
            "FLIGHTS_API_BASE_URL",
            "https://fr24api.flightradar24.com/api",
        )
        or ""
    ).strip()
    return raw.rstrip("/")


def get_flights_api_auth_header() -> str:
    return str(_config_value("FLIGHTS_API_AUTH_HEADER", "Authorization") or "Authorization").strip()


def get_flights_api_auth_prefix() -> str:
    return str(_config_value("FLIGHTS_API_AUTH_PREFIX", "Bearer") or "Bearer")


def get_flights_api_accept_version() -> str:
    return str(_config_value("FLIGHTS_API_ACCEPT_VERSION", "v1") or "").strip()


def get_flights_api_timeout_seconds() -> int:
    raw = _safe_int(_config_value("FLIGHTS_API_TIMEOUT_SECONDS", 20), 20)
    return max(raw, 5)


def get_flights_response_limit() -> int:
    raw = _safe_int(_config_value("FLIGHTS_API_RESPONSE_LIMIT", 20), 20)
    return max(1, min(raw, 200))


def get_flights_request_rate_limit() -> int:
    raw = _safe_int(_config_value("FLIGHTS_API_REQUEST_RATE_LIMIT", 10), 10)
    return max(raw, 1)


def get_flights_api_max_retries() -> int:
    raw = _safe_int(_config_value("FLIGHTS_API_MAX_RETRIES", 2), 2)
    return max(raw, 0)


def get_flights_api_retry_backoff_seconds() -> float:
    raw = _safe_float(_config_value("FLIGHTS_API_RETRY_BACKOFF_SECONDS", 1.5), 1.5)
    value = float(raw or 1.5)
    if value <= 0:
        return 1.5
    return value


def get_flights_request_cap_per_run() -> int:
    raw = _safe_int(_config_value("FLIGHTS_REQUEST_CAP_PER_RUN", 120), 120)
    return max(raw, 1)


def get_flights_safe_request_cap_per_run() -> int:
    raw = _safe_int(_config_value("FLIGHTS_SAFE_REQUEST_CAP_PER_RUN", 40), 40)
    return max(raw, 1)


def get_flights_guardrail_percent() -> float:
    raw = _safe_float(_config_value("FLIGHTS_GUARDRAIL_PERCENT", 85), 85.0)
    return max(1.0, min(float(raw or 85.0), 100.0))


def get_flights_monthly_credit_budget() -> int:
    raw = _safe_int(_config_value("FLIGHTS_MONTHLY_CREDIT_BUDGET", 60000), 60000)
    return max(raw, 1)


def get_flights_credit_per_request() -> int:
    raw = _safe_int(_config_value("FLIGHTS_ESTIMATED_CREDIT_PER_REQUEST", 1), 1)
    return max(raw, 1)


def get_flights_backfill_days() -> int:
    raw = _safe_int(_config_value("FLIGHTS_BACKFILL_DAYS", 7), 7)
    return max(raw, 0)


def get_flights_backfill_chunk_hours() -> int:
    raw = _safe_int(_config_value("FLIGHTS_BACKFILL_CHUNK_HOURS", 24), 24)
    return max(raw, 1)


def get_flights_polling_historic_hours() -> int:
    raw = _safe_int(_config_value("FLIGHTS_POLLING_HISTORIC_HOURS", 24), 24)
    return max(raw, 0)


def get_flights_backfill_on_empty_db() -> bool:
    return _safe_bool(_config_value("FLIGHTS_BACKFILL_ON_EMPTY_DB", False), False)


def get_flights_safe_mode_skip_backfill() -> bool:
    return _safe_bool(_config_value("FLIGHTS_SAFE_MODE_SKIP_BACKFILL", True), True)


def get_flights_backfill_historic_enabled() -> bool:
    return _safe_bool(_config_value("FLIGHTS_BACKFILL_HISTORIC_ENABLED", False), False)


def get_flights_snapshot_stale_after_seconds() -> int:
    raw = _safe_int(_config_value("FLIGHTS_STALE_AFTER_SECONDS", 1800), 1800)
    return max(raw, 60)


def get_flights_frontend_refresh_seconds() -> int:
    raw = _safe_int(_config_value("FLIGHTS_FRONTEND_REFRESH_SECONDS", 300), 300)
    return max(raw, 30)


def get_flights_ingestion_interval_seconds() -> int:
    raw = _safe_int(_config_value("FLIGHTS_INGESTION_INTERVAL_SECONDS", 900), 900)
    return max(raw, 60)


def get_flights_snapshot_point_limit() -> int:
    raw = _safe_int(_config_value("FLIGHTS_LAYER_MAX_POINTS", 2000), 2000)
    return max(raw, 100)


def get_flights_track_point_limit() -> int:
    raw = _safe_int(_config_value("FLIGHTS_TRACK_POINT_LIMIT", 2000), 2000)
    return max(raw, 100)


def get_flights_airports_sync_interval_seconds() -> int:
    raw = _safe_int(_config_value("FLIGHTS_AIRPORTS_SYNC_INTERVAL_SECONDS", 86400), 86400)
    return max(raw, 300)


def get_flights_airports_sync_enabled() -> bool:
    return _safe_bool(_config_value("FLIGHTS_AIRPORTS_SYNC_ENABLED", False), False)


def get_flights_airports_max_pages() -> int:
    raw = _safe_int(_config_value("FLIGHTS_AIRPORTS_MAX_PAGES", 10), 10)
    return max(raw, 1)


def get_flights_events_max_pages() -> int:
    raw = _safe_int(_config_value("FLIGHTS_EVENTS_MAX_PAGES", 5), 5)
    return max(raw, 1)


def get_flights_safe_mode_events_max_pages() -> int:
    raw = _safe_int(_config_value("FLIGHTS_SAFE_EVENTS_MAX_PAGES", 2), 2)
    return max(raw, 1)


def get_flights_airports_light_path() -> str:
    return str(
        _config_value("FLIGHTS_API_AIRPORTS_LIGHT_PATH", "/static/airports/{code}/light")
        or "/static/airports/{code}/light"
    ).strip()


def get_flights_live_positions_light_path() -> str:
    return str(
        _config_value(
            "FLIGHTS_API_LIVE_POSITIONS_LIGHT_PATH",
            "/live/flight-positions/light",
        )
        or "/live/flight-positions/light"
    ).strip()


def get_flights_historic_events_light_path() -> str:
    return str(
        _config_value(
            "FLIGHTS_API_HISTORIC_EVENTS_LIGHT_PATH",
            "/historic/flight-events/light",
        )
        or "/historic/flight-events/light"
    ).strip()


def get_flights_historic_positions_light_path() -> str:
    return str(
        _config_value(
            "FLIGHTS_API_HISTORIC_POSITIONS_LIGHT_PATH",
            "/historic/flight-positions/light",
        )
        or "/historic/flight-positions/light"
    ).strip()


def get_flights_summary_light_path() -> str:
    return str(
        _config_value(
            "FLIGHTS_API_FLIGHT_SUMMARY_LIGHT_PATH",
            "/flight-summary/light",
        )
        or "/flight-summary/light"
    ).strip()


def get_flights_tracks_path() -> str:
    return str(_config_value("FLIGHTS_API_TRACKS_PATH", "/flights/tracks") or "/flights/tracks").strip()


def get_flights_live_filter_bounds() -> str:
    raw = str(_config_value("FLIGHTS_LIVE_FILTER_BOUNDS", "") or "").strip()
    if not raw:
        return ""
    parts = [chunk.strip() for chunk in raw.split(",")]
    if len(parts) != 4:
        return DEFAULT_CUBA_LIVE_BOUNDS
    for chunk in parts:
        if _safe_float(chunk) is None:
            return DEFAULT_CUBA_LIVE_BOUNDS
    return ",".join(parts)


def get_flights_live_filter_airports() -> str:
    return str(_config_value("FLIGHTS_LIVE_FILTER_AIRPORTS", "") or "").strip()


def get_flights_cuba_airport_codes() -> set[str]:
    raw = str(_config_value("FLIGHTS_CUBA_AIRPORT_CODES", DEFAULT_CUBA_AIRPORT_CODES) or "").strip()
    if not raw:
        return set()
    codes: set[str] = set()
    for token in raw.split(","):
        code = _clean_text(token, upper=True, limit=8)
        if len(code) >= 3:
            codes.add(code)
    return codes


def get_flights_summary_on_demand_enabled() -> bool:
    return _safe_bool(_config_value("FLIGHTS_SUMMARY_ON_DEMAND_ENABLED", True), True)


def get_flights_summary_on_demand_hours() -> int:
    raw = _safe_int(_config_value("FLIGHTS_SUMMARY_ON_DEMAND_HOURS", 48), 48)
    return max(raw, 1)


def get_flights_summary_on_demand_limit() -> int:
    raw = _safe_int(_config_value("FLIGHTS_SUMMARY_ON_DEMAND_LIMIT", 20), 20)
    return max(1, min(raw, 200))


def get_flights_opensky_enabled() -> bool:
    return _safe_bool(_config_value("FLIGHTS_OPENSKY_ENABLED", False), False)


def get_flights_opensky_client_id() -> str:
    return str(_config_value("FLIGHTS_OPENSKY_CLIENT_ID", "") or "").strip()


def get_flights_opensky_client_secret() -> str:
    return str(_config_value("FLIGHTS_OPENSKY_CLIENT_SECRET", "") or "").strip()


def get_flights_opensky_token_url() -> str:
    raw = str(_config_value("FLIGHTS_OPENSKY_TOKEN_URL", DEFAULT_OPENSKY_TOKEN_URL) or "").strip()
    return raw or DEFAULT_OPENSKY_TOKEN_URL


def get_flights_opensky_api_base_url() -> str:
    raw = str(_config_value("FLIGHTS_OPENSKY_API_BASE_URL", DEFAULT_OPENSKY_API_BASE_URL) or "").strip()
    return raw.rstrip("/") or DEFAULT_OPENSKY_API_BASE_URL


def get_flights_opensky_timeout_seconds() -> int:
    raw = _safe_int(_config_value("FLIGHTS_OPENSKY_TIMEOUT_SECONDS", 20), 20)
    return max(raw, 5)


def get_flights_opensky_request_rate_limit() -> int:
    raw = _safe_int(_config_value("FLIGHTS_OPENSKY_REQUEST_RATE_LIMIT", 2), 2)
    return max(raw, 1)


def get_flights_opensky_request_cap_per_run() -> int:
    raw = _safe_int(_config_value("FLIGHTS_OPENSKY_REQUEST_CAP_PER_RUN", 180), 180)
    return max(raw, 1)


def get_flights_opensky_max_retries() -> int:
    raw = _safe_int(_config_value("FLIGHTS_OPENSKY_MAX_RETRIES", 2), 2)
    return max(raw, 0)


def get_flights_opensky_retry_backoff_seconds() -> float:
    raw = _safe_float(_config_value("FLIGHTS_OPENSKY_RETRY_BACKOFF_SECONDS", 1.5), 1.5)
    value = float(raw or 1.5)
    return value if value > 0 else 1.5


def get_flights_opensky_fallback_on_rate_limited() -> bool:
    return _safe_bool(_config_value("FLIGHTS_OPENSKY_FALLBACK_ON_RATE_LIMITED", True), True)


def get_flights_opensky_fallback_on_budget_exhausted() -> bool:
    return _safe_bool(_config_value("FLIGHTS_OPENSKY_FALLBACK_ON_BUDGET_EXHAUSTED", True), True)


def get_flights_opensky_fallback_on_empty() -> bool:
    return _safe_bool(_config_value("FLIGHTS_OPENSKY_FALLBACK_ON_EMPTY", False), False)


def get_flights_opensky_include_live_states() -> bool:
    return _safe_bool(_config_value("FLIGHTS_OPENSKY_INCLUDE_LIVE_STATES", True), True)


def get_flights_opensky_include_arrivals() -> bool:
    return _safe_bool(_config_value("FLIGHTS_OPENSKY_INCLUDE_ARRIVALS", True), True)


def get_flights_opensky_live_bounds() -> str:
    raw = str(_config_value("FLIGHTS_OPENSKY_LIVE_BOUNDS", "") or "").strip()
    if not raw:
        raw = get_flights_live_filter_bounds() or DEFAULT_CUBA_LIVE_BOUNDS
    parts = [chunk.strip() for chunk in raw.split(",")]
    if len(parts) != 4:
        return DEFAULT_CUBA_LIVE_BOUNDS
    for chunk in parts:
        if _safe_float(chunk) is None:
            return DEFAULT_CUBA_LIVE_BOUNDS
    return ",".join(parts)


def get_flights_opensky_arrival_chunk_hours() -> int:
    raw = _safe_int(_config_value("FLIGHTS_OPENSKY_ARRIVAL_CHUNK_HOURS", 48), 48)
    return max(1, min(raw, 48))


def _opensky_credentials_ready() -> bool:
    return bool(get_flights_opensky_client_id() and get_flights_opensky_client_secret())


def _build_api_url(path: str) -> str:
    base = get_flights_api_base_url()
    if not base:
        return ""
    suffix = "/" + str(path or "").lstrip("/")
    return f"{base}{suffix}"


def _apply_rate_limit(request_ctx: RequestContext) -> None:
    interval = 1.0 / float(max(request_ctx.rate_limit_per_second, 1))
    now_epoch = time.time()
    elapsed = now_epoch - request_ctx.last_request_epoch
    if request_ctx.last_request_epoch > 0 and elapsed < interval:
        time.sleep(interval - elapsed)
    request_ctx.last_request_epoch = time.time()


def _api_get(path: str, params: dict[str, Any], request_ctx: RequestContext) -> Any:
    api_key = get_flights_api_key()
    if not api_key:
        raise RuntimeError("FLIGHTS_API_KEY no configurada")

    url = _build_api_url(path)
    if not url:
        raise RuntimeError("FLIGHTS_API_BASE_URL no configurada")

    headers = {
        "Accept": "application/json",
    }
    accept_version = get_flights_api_accept_version()
    if accept_version:
        headers["Accept-Version"] = accept_version

    header_name = get_flights_api_auth_header()
    header_prefix = get_flights_api_auth_prefix()
    if header_name:
        prefix = header_prefix
        if prefix and not prefix.endswith(" "):
            prefix = f"{prefix} "
        headers[header_name] = f"{prefix}{api_key}" if prefix else api_key

    max_retries = get_flights_api_max_retries()
    base_backoff_seconds = get_flights_api_retry_backoff_seconds()
    attempt = 0

    while True:
        if request_ctx.request_count >= request_ctx.request_cap:
            request_ctx.budget_exhausted = True
            raise RequestBudgetExhausted("FLIGHTS request cap reached for this run")

        _apply_rate_limit(request_ctx)
        response = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=get_flights_api_timeout_seconds(),
        )
        request_ctx.request_count += 1
        request_ctx.estimated_credits += get_flights_credit_per_request()

        if response.ok:
            try:
                return response.json()
            except Exception as exc:
                raise RuntimeError(f"Respuesta no JSON desde flights API: {exc}") from exc

        snippet = (response.text or "").strip()
        if len(snippet) > 240:
            snippet = snippet[:237] + "..."

        if response.status_code == 429:
            retry_after_raw = (response.headers or {}).get("Retry-After")
            retry_after_seconds = _safe_float(retry_after_raw, None)
            if attempt < max_retries:
                delay = (
                    float(retry_after_seconds)
                    if retry_after_seconds is not None and retry_after_seconds >= 0
                    else float(base_backoff_seconds) * (2 ** attempt)
                )
                time.sleep(max(0.5, delay))
                attempt += 1
                continue
            raise FlightsApiRateLimited(
                f"HTTP 429 from flights API: {snippet or 'Rate limit exceeded'}"
            )

        raise RuntimeError(f"HTTP {response.status_code} from flights API: {snippet or 'sin detalle'}")


def _build_opensky_api_url(path: str) -> str:
    base = get_flights_opensky_api_base_url()
    if not base:
        return ""
    suffix = "/" + str(path or "").lstrip("/")
    return f"{base}{suffix}"


def _consume_request_budget(request_ctx: RequestContext) -> None:
    if request_ctx.request_count >= request_ctx.request_cap:
        request_ctx.budget_exhausted = True
        raise RequestBudgetExhausted("OpenSky request cap reached for this run")


def _opensky_epoch_to_datetime(value: Any) -> datetime | None:
    try:
        epoch = int(float(value))
    except Exception:
        return None
    if epoch <= 0:
        return None
    try:
        return datetime.utcfromtimestamp(epoch)
    except Exception:
        return None


def _opensky_token(request_ctx: RequestContext) -> str:
    now_epoch = time.time()
    cached_token = str(_OPENSKY_TOKEN_CACHE.get("access_token") or "").strip()
    expires_at = _safe_float(_OPENSKY_TOKEN_CACHE.get("expires_at_epoch"), 0.0) or 0.0
    if cached_token and now_epoch < max(0.0, expires_at - 30.0):
        return cached_token

    client_id = get_flights_opensky_client_id()
    client_secret = get_flights_opensky_client_secret()
    if not client_id or not client_secret:
        raise RuntimeError("OpenSky credentials no configuradas (client_id/client_secret)")

    _consume_request_budget(request_ctx)
    _apply_rate_limit(request_ctx)

    response = requests.post(
        get_flights_opensky_token_url(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=get_flights_opensky_timeout_seconds(),
    )
    request_ctx.request_count += 1

    if not response.ok:
        snippet = (response.text or "").strip()
        if len(snippet) > 240:
            snippet = snippet[:237] + "..."
        raise RuntimeError(
            f"HTTP {response.status_code} obteniendo token OpenSky: {snippet or 'sin detalle'}"
        )

    try:
        payload = response.json()
    except Exception as exc:
        raise RuntimeError(f"Token OpenSky no devolvió JSON válido: {exc}") from exc

    access_token = _clean_text(payload.get("access_token"), limit=5000)
    expires_in = _safe_int(payload.get("expires_in"), 1800)
    if not access_token:
        raise RuntimeError("Respuesta de token OpenSky sin access_token")

    _OPENSKY_TOKEN_CACHE["access_token"] = access_token
    _OPENSKY_TOKEN_CACHE["expires_at_epoch"] = now_epoch + max(60, expires_in)
    return access_token


def _opensky_api_get(path: str, params: dict[str, Any], request_ctx: RequestContext) -> Any:
    url = _build_opensky_api_url(path)
    if not url:
        raise RuntimeError("FLIGHTS_OPENSKY_API_BASE_URL no configurada")

    max_retries = get_flights_opensky_max_retries()
    base_backoff_seconds = get_flights_opensky_retry_backoff_seconds()
    attempt = 0
    force_refresh_token = False

    while True:
        _consume_request_budget(request_ctx)
        _apply_rate_limit(request_ctx)

        access_token = _opensky_token(request_ctx)
        if force_refresh_token:
            _OPENSKY_TOKEN_CACHE["access_token"] = ""
            _OPENSKY_TOKEN_CACHE["expires_at_epoch"] = 0.0
            access_token = _opensky_token(request_ctx)
            force_refresh_token = False

        response = requests.get(
            url,
            params=params,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {access_token}",
            },
            timeout=get_flights_opensky_timeout_seconds(),
        )
        request_ctx.request_count += 1

        if response.ok:
            try:
                return response.json()
            except Exception as exc:
                raise RuntimeError(f"Respuesta no JSON desde OpenSky API: {exc}") from exc

        if response.status_code == 404:
            return []

        snippet = (response.text or "").strip()
        if len(snippet) > 240:
            snippet = snippet[:237] + "..."

        if response.status_code == 401 and attempt <= max_retries:
            attempt += 1
            force_refresh_token = True
            continue

        if response.status_code == 429:
            retry_after_raw = (response.headers or {}).get("Retry-After")
            retry_after_seconds = _safe_float(retry_after_raw, None)
            if attempt < max_retries:
                delay = (
                    float(retry_after_seconds)
                    if retry_after_seconds is not None and retry_after_seconds >= 0
                    else float(base_backoff_seconds) * (2 ** attempt)
                )
                time.sleep(max(0.5, delay))
                attempt += 1
                continue
            raise FlightsApiRateLimited(
                f"HTTP 429 from OpenSky API: {snippet or 'Rate limit exceeded'}"
            )

        if 500 <= response.status_code <= 599 and attempt < max_retries:
            time.sleep(max(0.5, float(base_backoff_seconds) * (2 ** attempt)))
            attempt += 1
            continue

        raise RuntimeError(
            f"HTTP {response.status_code} from OpenSky API: {snippet or 'sin detalle'}"
        )


def _build_cuba_airport_lookup(known_cuba_codes: set[str]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    rows = FlightAirport.query.filter(FlightAirport.is_cuba.is_(True)).all()
    for row in rows:
        payload = {
            "icao": _clean_text(row.airport_code_icao, upper=True, limit=8),
            "iata": _clean_text(row.airport_code_iata, upper=True, limit=8),
            "name": _clean_text(row.name, limit=255),
            "latitude": _safe_float(row.latitude),
            "longitude": _safe_float(row.longitude),
        }
        for code in [payload["icao"], payload["iata"]]:
            if code:
                lookup[code] = payload

    for code in known_cuba_codes:
        clean_code = _clean_text(code, upper=True, limit=8)
        if clean_code and clean_code not in lookup:
            lookup[clean_code] = {
                "icao": clean_code if len(clean_code) == 4 else "",
                "iata": clean_code if len(clean_code) == 3 else "",
                "name": f"Aeropuerto {clean_code}",
                "latitude": None,
                "longitude": None,
            }

    return lookup


def _parse_opensky_state_record(
    row: Any,
    airport_lookup: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    if not isinstance(row, list) or len(row) < 11:
        return None

    icao24 = _clean_text(row[0], upper=True, limit=16)
    call_sign = _clean_text(row[1], upper=True, limit=64)
    origin_country = _clean_text(row[2], limit=120)
    longitude = _safe_float(row[5])
    latitude = _safe_float(row[6])
    if latitude is None or longitude is None:
        return None

    altitude = _safe_float(row[13], None)
    if altitude is None:
        altitude = _safe_float(row[7], None)
    speed = _safe_float(row[9], None)
    heading = _safe_float(row[10], None)
    on_ground = bool(row[8]) if isinstance(row[8], bool) else False
    observed_at = _opensky_epoch_to_datetime(row[4]) or _opensky_epoch_to_datetime(row[3]) or _utc_now_naive()

    destination_name = "Espacio aéreo cubano"
    destination_icao = ""
    destination_iata = ""
    for candidate_code, airport_payload in airport_lookup.items():
        if not airport_payload:
            continue
        # Keep ICAO/IATA assignment stable if provided in OpenSky call-sign-like fields.
        if candidate_code and candidate_code in call_sign:
            destination_name = _clean_text(airport_payload.get("name"), limit=255) or destination_name
            destination_icao = _clean_text(airport_payload.get("icao"), upper=True, limit=8)
            destination_iata = _clean_text(airport_payload.get("iata"), upper=True, limit=8)
            break

    external_id = f"opensky-live:{icao24 or call_sign or 'unknown'}"
    identity_key = _normalize_identity_key(call_sign, "opensky", icao24, external_id)
    event_key = _clean_text(f"opensky-live|{icao24 or identity_key}", limit=255)

    return {
        "event_key": event_key,
        "external_flight_id": external_id,
        "identity_key": identity_key,
        "call_sign": call_sign,
        "model": "",
        "registration": icao24,
        "origin_airport_icao": "",
        "origin_airport_iata": "",
        "origin_airport_name": "",
        "origin_country": origin_country,
        "destination_airport_icao": destination_icao,
        "destination_airport_iata": destination_iata,
        "destination_airport_name": destination_name,
        "destination_country": "Cuba",
        "destination_country_code": "CU",
        "destination_fr_airport_id": "",
        "status": "ground" if on_ground else "live",
        "departure_at_utc": None,
        "arrival_at_utc": None,
        "observed_at_utc": observed_at,
        "latitude": latitude,
        "longitude": longitude,
        "altitude": altitude,
        "speed": speed,
        "heading": heading,
        "source_kind": "opensky_live",
    }


def _parse_opensky_arrival_record(
    row: dict[str, Any],
    airport_code: str,
    airport_lookup: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    icao24 = _clean_text(_pick(row, "icao24", "icao_24"), upper=True, limit=16)
    call_sign = _clean_text(_pick(row, "callsign", "call_sign"), upper=True, limit=64)
    origin_icao = _clean_text(_pick(row, "estDepartureAirport", "departure_airport"), upper=True, limit=8)
    destination_icao = _clean_text(
        _pick(row, "estArrivalAirport", "arrival_airport"),
        upper=True,
        limit=8,
    ) or _clean_text(airport_code, upper=True, limit=8)

    departure_at = _opensky_epoch_to_datetime(_pick(row, "firstSeen", "first_seen"))
    arrival_at = _opensky_epoch_to_datetime(_pick(row, "lastSeen", "last_seen"))
    observed_at = arrival_at or departure_at or _utc_now_naive()

    destination_payload = airport_lookup.get(destination_icao) or {}
    destination_name = (
        _clean_text(destination_payload.get("name"), limit=255)
        or f"Aeropuerto {destination_icao or 'Cuba'}"
    )
    destination_iata = _clean_text(destination_payload.get("iata"), upper=True, limit=8)
    latitude = _safe_float(destination_payload.get("latitude"))
    longitude = _safe_float(destination_payload.get("longitude"))

    external_id = _clean_text(
        f"opensky-arrival:{icao24 or call_sign or 'unknown'}:{int(observed_at.timestamp())}:{destination_icao or 'CU'}",
        limit=255,
    )
    identity_key = _normalize_identity_key(call_sign, "opensky", icao24, external_id)
    event_key = _clean_text(
        f"opensky-arrival|{icao24 or identity_key}|{int(observed_at.timestamp())}|{destination_icao or 'CU'}",
        limit=255,
    )

    return {
        "event_key": event_key,
        "external_flight_id": external_id,
        "identity_key": identity_key,
        "call_sign": call_sign,
        "model": "",
        "registration": icao24,
        "origin_airport_icao": origin_icao,
        "origin_airport_iata": "",
        "origin_airport_name": origin_icao or "",
        "origin_country": "",
        "destination_airport_icao": destination_icao,
        "destination_airport_iata": destination_iata,
        "destination_airport_name": destination_name,
        "destination_country": "Cuba",
        "destination_country_code": "CU",
        "destination_fr_airport_id": "",
        "status": "landed",
        "departure_at_utc": departure_at,
        "arrival_at_utc": arrival_at,
        "observed_at_utc": observed_at,
        "latitude": latitude,
        "longitude": longitude,
        "altitude": None,
        "speed": None,
        "heading": None,
        "source_kind": "opensky_arrival",
    }


def _collect_opensky_live_records(
    request_ctx: RequestContext,
    airport_lookup: dict[str, dict[str, Any]],
) -> FetchBatch:
    batch = FetchBatch()
    if not get_flights_opensky_include_live_states():
        return batch

    bounds = get_flights_opensky_live_bounds()
    north, south, west, east = [chunk.strip() for chunk in bounds.split(",")]
    params = {
        "lamin": south,
        "lamax": north,
        "lomin": west,
        "lomax": east,
    }

    try:
        payload = _opensky_api_get("/states/all", params, request_ctx)
    except RequestBudgetExhausted:
        batch.budget_exhausted = True
        return batch
    except FlightsApiRateLimited as exc:
        batch.rate_limited = True
        batch.errors.append(str(exc))
        return batch
    except Exception as exc:
        batch.errors.append(str(exc))
        return batch

    rows = []
    if isinstance(payload, dict):
        states = payload.get("states")
        if isinstance(states, list):
            rows = states

    batch.seen = len(rows)
    for row in rows:
        parsed = _parse_opensky_state_record(row, airport_lookup)
        if parsed:
            batch.records.append(parsed)

    return batch


def _collect_opensky_arrival_records(
    request_ctx: RequestContext,
    known_cuba_codes: set[str],
    historic_hours: int,
    airport_lookup: dict[str, dict[str, Any]],
) -> FetchBatch:
    batch = FetchBatch()
    if not get_flights_opensky_include_arrivals() or historic_hours <= 0:
        return batch

    airport_codes = sorted(
        code
        for code in known_cuba_codes
        if len(_clean_text(code, upper=True, limit=8)) == 4
    )
    if not airport_codes:
        return batch

    now_utc = _utc_now_naive()
    start_utc = now_utc - timedelta(hours=int(historic_hours))
    chunk_hours = get_flights_opensky_arrival_chunk_hours()
    cursor = start_utc
    step = timedelta(hours=chunk_hours)

    while cursor < now_utc:
        end_cursor = min(cursor + step, now_utc)
        begin_epoch = int(cursor.replace(tzinfo=timezone.utc).timestamp())
        end_epoch = int(end_cursor.replace(tzinfo=timezone.utc).timestamp())

        for airport_code in airport_codes:
            params = {
                "airport": airport_code,
                "begin": begin_epoch,
                "end": end_epoch,
            }
            try:
                payload = _opensky_api_get("/flights/arrival", params, request_ctx)
            except RequestBudgetExhausted:
                batch.budget_exhausted = True
                return batch
            except FlightsApiRateLimited as exc:
                batch.rate_limited = True
                batch.errors.append(str(exc))
                return batch
            except Exception as exc:
                batch.errors.append(str(exc))
                continue

            rows: list[dict[str, Any]] = []
            if isinstance(payload, list):
                rows = [item for item in payload if isinstance(item, dict)]
            elif isinstance(payload, dict):
                rows = _extract_items(payload, ("data", "items", "results"))

            batch.seen += len(rows)
            for row in rows:
                parsed = _parse_opensky_arrival_record(row, airport_code, airport_lookup)
                if parsed:
                    batch.records.append(parsed)

        cursor = end_cursor

    return batch


def _should_use_opensky_fallback(
    *,
    fr24_available: bool,
    fr24_records_count: int,
    fr24_rate_limited: bool,
    fr24_budget_exhausted: bool,
) -> tuple[bool, str]:
    if not get_flights_opensky_enabled():
        return False, "disabled"
    if not _opensky_credentials_ready():
        return False, "missing_credentials"
    if (not fr24_available) and get_flights_opensky_enabled():
        return True, "fr24_unavailable"
    if fr24_rate_limited and get_flights_opensky_fallback_on_rate_limited():
        return True, "fr24_rate_limited"
    if fr24_budget_exhausted and get_flights_opensky_fallback_on_budget_exhausted():
        return True, "fr24_budget_exhausted"
    if fr24_records_count <= 0 and get_flights_opensky_fallback_on_empty():
        return True, "fr24_empty"
    return False, "not_needed"


def _collect_opensky_fallback_records(
    request_ctx: RequestContext,
    known_cuba_codes: set[str],
    historic_hours: int,
) -> FetchBatch:
    combined = FetchBatch()
    airport_lookup = _build_cuba_airport_lookup(known_cuba_codes)

    arrival_batch = _collect_opensky_arrival_records(
        request_ctx,
        known_cuba_codes,
        historic_hours,
        airport_lookup,
    )
    combined.records.extend(arrival_batch.records)
    combined.seen += int(arrival_batch.seen)
    combined.errors.extend(arrival_batch.errors)
    if arrival_batch.budget_exhausted:
        combined.budget_exhausted = True
    if getattr(arrival_batch, "rate_limited", False):
        combined.rate_limited = True

    if not combined.budget_exhausted and not combined.rate_limited:
        live_batch = _collect_opensky_live_records(request_ctx, airport_lookup)
        combined.records.extend(live_batch.records)
        combined.seen += int(live_batch.seen)
        combined.errors.extend(live_batch.errors)
        if live_batch.budget_exhausted:
            combined.budget_exhausted = True
        if getattr(live_batch, "rate_limited", False):
            combined.rate_limited = True

    return combined


def _month_range(now_utc: datetime) -> tuple[datetime, datetime]:
    start = datetime(now_utc.year, now_utc.month, 1)
    if now_utc.month == 12:
        end = datetime(now_utc.year + 1, 1, 1)
    else:
        end = datetime(now_utc.year, now_utc.month + 1, 1)
    return start, end


def get_monthly_credit_usage(now_utc: datetime | None = None) -> int:
    now = _normalize_utc_datetime(now_utc) or _utc_now_naive()
    month_start, month_end = _month_range(now)
    value = (
        db.session.query(func.coalesce(func.sum(FlightIngestionRun.estimated_credits), 0))
        .filter(
            FlightIngestionRun.started_at_utc >= month_start,
            FlightIngestionRun.started_at_utc < month_end,
        )
        .scalar()
    )
    return int(value or 0)


def _safe_mode_active(monthly_used: int, monthly_budget: int) -> bool:
    if monthly_budget <= 0:
        return False
    threshold = (monthly_budget * get_flights_guardrail_percent()) / 100.0
    return float(monthly_used) >= float(threshold)


def _known_cuba_airport_codes() -> set[str]:
    rows = FlightAirport.query.filter(FlightAirport.is_cuba.is_(True)).all()
    codes: set[str] = set(get_flights_cuba_airport_codes())
    for row in rows:
        if row.airport_code_icao:
            codes.add(str(row.airport_code_icao).strip().upper())
        if row.airport_code_iata:
            codes.add(str(row.airport_code_iata).strip().upper())
    return codes


def _airport_code_key(icao: str, iata: str, fr_airport_id: str, name: str) -> str:
    if icao:
        return f"icao:{icao}"
    if iata:
        return f"iata:{iata}"
    if fr_airport_id:
        return f"fr:{fr_airport_id}"

    normalized_name = _normalize_token(name)
    if normalized_name:
        digest = hashlib.sha1(normalized_name.encode("utf-8")).hexdigest()[:14]
        return f"name:{digest}"

    return "unknown"


def _parse_airport_row(item: dict[str, Any]) -> dict[str, Any] | None:
    icao = _clean_text(
        _pick(
            item,
            "icao",
            "airport_code_icao",
            "codes.icao",
            "airport.icao",
        ),
        upper=True,
        limit=8,
    )
    iata = _clean_text(
        _pick(
            item,
            "iata",
            "airport_code_iata",
            "codes.iata",
            "airport.iata",
        ),
        upper=True,
        limit=8,
    )
    fr_airport_id = _clean_text(_pick(item, "id", "airport_id", "fr_airport_id"), limit=64)
    name = _clean_text(_pick(item, "name", "airport_name", "airport.name"), limit=255)

    if not (icao or iata or fr_airport_id or name):
        return None

    city = _clean_text(_pick(item, "city", "location.city"), limit=120)
    province = _clean_text(_pick(item, "province", "state", "location.state"), limit=120)
    country_code = _clean_text(
        _pick(item, "country_code", "country.code", "countryCode"),
        upper=True,
        limit=8,
    )
    country_name = _clean_text(
        _pick(item, "country", "country_name", "country.name"),
        limit=120,
    )

    lat = _safe_float(_pick(item, "latitude", "lat", "location.latitude", "location.lat"))
    lng = _safe_float(_pick(item, "longitude", "lon", "lng", "location.longitude", "location.lon"))

    return {
        "code_key": _airport_code_key(icao, iata, fr_airport_id, name),
        "fr_airport_id": fr_airport_id,
        "airport_code_icao": icao,
        "airport_code_iata": iata,
        "name": name or iata or icao or fr_airport_id,
        "city": city,
        "province": province,
        "country_code": country_code,
        "country_name": country_name,
        "latitude": lat,
        "longitude": lng,
        "is_cuba": _country_is_cuba(country_name, country_code),
    }


def _parse_event_row(
    item: dict[str, Any],
    known_cuba_codes: set[str],
    source_kind: str,
    *,
    force_destination_cuba: bool = False,
) -> dict[str, Any] | None:
    external_flight_id = _clean_text(
        _pick(
            item,
            "flight_id",
            "id",
            "fr24_id",
            "identifier",
            "flight_identification.id",
        ),
        limit=128,
    )

    call_sign = _clean_text(
        _pick(
            item,
            "callsign",
            "call_sign",
            "identification.callsign",
            "flight",
            "flight_number",
        ),
        limit=64,
    )
    model = _clean_text(
        _pick(
            item,
            "model",
            "aircraft.model",
            "aircraft_model",
            "aircraft.type",
            "type",
        ),
        limit=120,
    )
    registration = _clean_text(
        _pick(item, "registration", "aircraft.registration", "tail_number", "reg"),
        limit=64,
    )

    origin_icao = _clean_text(
        _pick(
            item,
            "origin.icao",
            "origin_airport_icao",
            "departure.airport.icao",
            "origin_icao",
            "orig_icao",
        ),
        upper=True,
        limit=8,
    )
    origin_iata = _clean_text(
        _pick(
            item,
            "origin.iata",
            "origin_airport_iata",
            "departure.airport.iata",
            "origin_iata",
            "orig_iata",
        ),
        upper=True,
        limit=8,
    )
    origin_name = _clean_text(
        _pick(
            item,
            "origin.name",
            "origin_airport_name",
            "departure.airport.name",
        ),
        limit=255,
    )
    origin_country = _clean_text(
        _pick(
            item,
            "origin.country",
            "origin_country",
            "departure.airport.country",
        ),
        limit=120,
    )

    dest_icao = _clean_text(
        _pick(
            item,
            "destination.icao",
            "destination_airport_icao",
            "arrival.airport.icao",
            "destination_icao",
            "dest_icao",
            "destination_icao_actual",
            "dest_icao_actual",
        ),
        upper=True,
        limit=8,
    )
    dest_iata = _clean_text(
        _pick(
            item,
            "destination.iata",
            "destination_airport_iata",
            "arrival.airport.iata",
            "destination_iata",
            "dest_iata",
            "destination_iata_actual",
            "dest_iata_actual",
        ),
        upper=True,
        limit=8,
    )
    dest_name = _clean_text(
        _pick(
            item,
            "destination.name",
            "destination_airport_name",
            "arrival.airport.name",
        ),
        limit=255,
    )
    dest_country = _clean_text(
        _pick(
            item,
            "destination.country",
            "destination_country",
            "arrival.airport.country",
        ),
        limit=120,
    )
    dest_country_code = _clean_text(
        _pick(
            item,
            "destination.country_code",
            "destination_country_code",
            "arrival.airport.country_code",
        ),
        upper=True,
        limit=8,
    )
    dest_airport_id = _clean_text(
        _pick(item, "destination.id", "destination_airport_id"),
        limit=64,
    )

    destination_is_cuba = _country_is_cuba(dest_country, dest_country_code)
    if not destination_is_cuba:
        if dest_icao and dest_icao in known_cuba_codes:
            destination_is_cuba = True
        if dest_iata and dest_iata in known_cuba_codes:
            destination_is_cuba = True
    if not destination_is_cuba and force_destination_cuba:
        destination_is_cuba = True
        if not dest_country:
            dest_country = "Cuba"
        if not dest_country_code:
            dest_country_code = "CU"
        if not dest_name:
            dest_name = "Aeropuerto Cuba"

    if not destination_is_cuba:
        return None

    departure_at_utc = _parse_datetime(
        _pick(
            item,
            "departure_at_utc",
            "departure_time",
            "departure.scheduled",
            "departure.actual",
            "times.departure",
            "datetime_takeoff",
            "first_seen",
        )
    )
    arrival_at_utc = _parse_datetime(
        _pick(
            item,
            "arrival_at_utc",
            "arrival_time",
            "arrival.scheduled",
            "arrival.actual",
            "times.arrival",
            "datetime_landed",
        )
    )
    observed_at_utc = _parse_datetime(
        _pick(
            item,
            "observed_at_utc",
            "timestamp",
            "last_seen_at",
            "last_seen_at_utc",
            "position.timestamp",
            "last_seen",
            "first_seen",
        )
    )

    latitude = _safe_float(
        _pick(
            item,
            "latitude",
            "lat",
            "position.latitude",
            "position.lat",
        )
    )
    longitude = _safe_float(
        _pick(
            item,
            "longitude",
            "lon",
            "lng",
            "position.longitude",
            "position.lon",
        )
    )
    altitude = _safe_float(_pick(item, "altitude", "position.altitude", "position.alt", "alt"))
    speed = _safe_float(_pick(item, "speed", "ground_speed", "position.speed", "position.gs", "gspeed"))
    heading = _safe_float(
        _pick(item, "heading", "course", "position.heading", "position.track", "track")
    )
    status = _clean_text(_pick(item, "status", "state", "flight_status"), limit=64)
    if not status:
        flight_ended = _pick(item, "flight_ended")
        if isinstance(flight_ended, bool):
            status = "landed" if flight_ended else "live"
        else:
            ended_text = _clean_text(flight_ended, upper=True, limit=16)
            if ended_text in {"TRUE", "1"}:
                status = "landed"
            elif ended_text in {"FALSE", "0"}:
                status = "live"

    identity_key = _normalize_identity_key(call_sign, model, registration, external_flight_id)
    event_key = _build_event_key(
        external_flight_id,
        identity_key,
        departure_at_utc,
        dest_icao,
        dest_iata,
        dest_name,
    )

    return {
        "event_key": event_key,
        "external_flight_id": external_flight_id,
        "identity_key": identity_key,
        "call_sign": call_sign,
        "model": model,
        "registration": registration,
        "origin_airport_icao": origin_icao,
        "origin_airport_iata": origin_iata,
        "origin_airport_name": origin_name,
        "origin_country": origin_country,
        "destination_airport_icao": dest_icao,
        "destination_airport_iata": dest_iata,
        "destination_airport_name": dest_name,
        "destination_country": dest_country or "Cuba",
        "destination_country_code": dest_country_code or "CU",
        "destination_fr_airport_id": dest_airport_id,
        "status": status,
        "departure_at_utc": departure_at_utc,
        "arrival_at_utc": arrival_at_utc,
        "observed_at_utc": observed_at_utc,
        "latitude": latitude,
        "longitude": longitude,
        "altitude": altitude,
        "speed": speed,
        "heading": heading,
        "source_kind": source_kind,
    }


def _upsert_airport(parsed: dict[str, Any], airport_cache: dict[str, FlightAirport]) -> FlightAirport:
    key = parsed["code_key"]
    row = airport_cache.get(key)
    if row is None:
        row = FlightAirport.query.filter_by(code_key=key).first()
        if row is None:
            row = FlightAirport(code_key=key)
            db.session.add(row)
        airport_cache[key] = row

    row.fr_airport_id = parsed.get("fr_airport_id") or row.fr_airport_id
    row.airport_code_icao = parsed.get("airport_code_icao") or row.airport_code_icao
    row.airport_code_iata = parsed.get("airport_code_iata") or row.airport_code_iata
    row.name = parsed.get("name") or row.name or "Aeropuerto"
    row.city = parsed.get("city") or row.city
    row.province = parsed.get("province") or row.province
    row.country_code = parsed.get("country_code") or row.country_code
    row.country_name = parsed.get("country_name") or row.country_name
    row.latitude = parsed.get("latitude") if parsed.get("latitude") is not None else row.latitude
    row.longitude = parsed.get("longitude") if parsed.get("longitude") is not None else row.longitude
    row.is_cuba = bool(parsed.get("is_cuba") or row.is_cuba)

    return row


def _upsert_aircraft(record: dict[str, Any], aircraft_cache: dict[str, FlightAircraft]) -> FlightAircraft:
    identity_key = _clean_text(record.get("identity_key"), limit=255) or "unknown"
    row = aircraft_cache.get(identity_key)
    if row is None:
        row = FlightAircraft.query.filter_by(identity_key=identity_key).first()
        if row is None:
            row = FlightAircraft(identity_key=identity_key)
            db.session.add(row)
        aircraft_cache[identity_key] = row

    row.call_sign = record.get("call_sign") or row.call_sign
    row.model = record.get("model") or row.model
    row.registration = record.get("registration") or row.registration

    observed_at = record.get("observed_at_utc")
    if observed_at:
        if row.first_seen_at_utc is None or observed_at < row.first_seen_at_utc:
            row.first_seen_at_utc = observed_at
        if row.last_seen_at_utc is None or observed_at > row.last_seen_at_utc:
            row.last_seen_at_utc = observed_at

    return row


def _resolve_destination_airport(
    record: dict[str, Any],
    airport_cache: dict[str, FlightAirport],
) -> FlightAirport:
    parsed = {
        "code_key": _airport_code_key(
            _clean_text(record.get("destination_airport_icao"), upper=True, limit=8),
            _clean_text(record.get("destination_airport_iata"), upper=True, limit=8),
            _clean_text(record.get("destination_fr_airport_id"), limit=64),
            _clean_text(record.get("destination_airport_name"), limit=255),
        ),
        "fr_airport_id": _clean_text(record.get("destination_fr_airport_id"), limit=64),
        "airport_code_icao": _clean_text(record.get("destination_airport_icao"), upper=True, limit=8),
        "airport_code_iata": _clean_text(record.get("destination_airport_iata"), upper=True, limit=8),
        "name": _clean_text(record.get("destination_airport_name"), limit=255) or "Aeropuerto Cuba",
        "country_code": _clean_text(record.get("destination_country_code"), upper=True, limit=8) or "CU",
        "country_name": _clean_text(record.get("destination_country"), limit=120) or "Cuba",
        "is_cuba": True,
    }

    return _upsert_airport(parsed, airport_cache)


def _upsert_event(
    record: dict[str, Any],
    aircraft: FlightAircraft,
    destination_airport: FlightAirport,
    ingestion_run: FlightIngestionRun,
    event_cache: dict[str, FlightEvent],
) -> tuple[FlightEvent, bool]:
    event_key = _clean_text(record.get("event_key"), limit=255) or "unknown"
    row = event_cache.get(event_key)
    created = False
    if row is None:
        row = FlightEvent.query.filter_by(event_key=event_key).first()
        if row is None:
            row = FlightEvent(event_key=event_key)
            db.session.add(row)
            created = True
        event_cache[event_key] = row

    row.external_flight_id = record.get("external_flight_id") or row.external_flight_id
    row.aircraft = aircraft
    row.destination_airport = destination_airport
    row.ingestion_run = ingestion_run
    row.identity_key = record.get("identity_key") or row.identity_key
    row.call_sign = record.get("call_sign") or row.call_sign
    row.model = record.get("model") or row.model
    row.registration = record.get("registration") or row.registration

    row.origin_airport_icao = record.get("origin_airport_icao") or row.origin_airport_icao
    row.origin_airport_iata = record.get("origin_airport_iata") or row.origin_airport_iata
    row.origin_airport_name = record.get("origin_airport_name") or row.origin_airport_name
    row.origin_country = record.get("origin_country") or row.origin_country

    row.destination_airport_icao = (
        record.get("destination_airport_icao") or row.destination_airport_icao
    )
    row.destination_airport_iata = (
        record.get("destination_airport_iata") or row.destination_airport_iata
    )
    row.destination_airport_name = (
        record.get("destination_airport_name")
        or (destination_airport.name if destination_airport else "")
        or row.destination_airport_name
    )
    row.destination_country = record.get("destination_country") or row.destination_country or "Cuba"

    row.status = record.get("status") or row.status
    row.departure_at_utc = record.get("departure_at_utc") or row.departure_at_utc
    row.arrival_at_utc = record.get("arrival_at_utc") or row.arrival_at_utc

    observed_at = record.get("observed_at_utc")
    if observed_at:
        if row.first_seen_at_utc is None or observed_at < row.first_seen_at_utc:
            row.first_seen_at_utc = observed_at
        if row.last_seen_at_utc is None or observed_at > row.last_seen_at_utc:
            row.last_seen_at_utc = observed_at

    lat = record.get("latitude")
    lng = record.get("longitude")
    if lat is not None and lng is not None:
        row.latest_latitude = lat
        row.latest_longitude = lng
        row.latest_altitude = record.get("altitude")
        row.latest_speed = record.get("speed")
        row.latest_heading = record.get("heading")
        row.last_source_kind = record.get("source_kind") or row.last_source_kind

    return row, created


def _store_position(event: FlightEvent, record: dict[str, Any]) -> bool:
    lat = record.get("latitude")
    lng = record.get("longitude")
    if lat is None or lng is None:
        return False

    observed_at = record.get("observed_at_utc") or event.last_seen_at_utc or _utc_now_naive()
    source_kind = _clean_text(record.get("source_kind"), limit=64) or "live"

    exists = FlightPosition.query.filter_by(
        event_id=event.id,
        observed_at_utc=observed_at,
        source_kind=source_kind,
    ).first()
    if exists:
        return False

    row = FlightPosition(
        event=event,
        observed_at_utc=observed_at,
        latitude=float(lat),
        longitude=float(lng),
        altitude=record.get("altitude"),
        speed=record.get("speed"),
        heading=record.get("heading"),
        source_kind=source_kind,
    )
    db.session.add(row)
    return True


def _query_events_from_endpoint(
    path: str,
    base_params: dict[str, Any],
    preferred_paths: tuple[str, ...],
    known_cuba_codes: set[str],
    source_kind: str,
    request_ctx: RequestContext,
    max_pages: int,
    force_destination_cuba: bool = False,
) -> FetchBatch:
    batch = FetchBatch()
    limit = get_flights_response_limit()

    for page in range(1, max_pages + 1):
        params = dict(base_params)
        params["limit"] = limit
        params["page"] = page

        try:
            payload = _api_get(path, params, request_ctx)
        except RequestBudgetExhausted:
            batch.budget_exhausted = True
            break
        except FlightsApiRateLimited as exc:
            batch.rate_limited = True
            batch.errors.append(str(exc))
            break
        except Exception as exc:
            batch.errors.append(str(exc))
            break

        rows = _extract_items(payload, preferred_paths)
        if not rows:
            break

        for row in rows:
            batch.seen += 1
            parsed = _parse_event_row(
                row,
                known_cuba_codes,
                source_kind,
                force_destination_cuba=force_destination_cuba,
            )
            if parsed is None:
                continue
            batch.records.append(parsed)

        if len(rows) < limit:
            break

    return batch


def _sync_cuba_airports(request_ctx: RequestContext) -> tuple[int, list[str], bool]:
    if not get_flights_airports_sync_enabled():
        return 0, [], False

    stored = 0
    errors: list[str] = []
    budget_exhausted = False
    limit = get_flights_response_limit()
    max_pages = get_flights_airports_max_pages()

    airport_cache: dict[str, FlightAirport] = {}
    path = get_flights_airports_light_path()

    if "{code}" in path:
        codes = sorted(get_flights_cuba_airport_codes())
        for code in codes:
            endpoint = path.replace("{code}", code)
            try:
                payload = _api_get(endpoint, {}, request_ctx)
            except RequestBudgetExhausted:
                budget_exhausted = True
                break
            except Exception as exc:
                errors.append(str(exc))
                continue

            rows = _extract_items(payload, ("airport", "data.airport", "data", "item"))
            if not rows and isinstance(payload, dict):
                rows = [payload]

            for row in rows:
                parsed = _parse_airport_row(row)
                if parsed is None:
                    continue
                parsed["is_cuba"] = True
                _upsert_airport(parsed, airport_cache)
                stored += 1

        return stored, errors, budget_exhausted

    for page in range(1, max_pages + 1):
        params = {
            "country": "CU",
            "limit": limit,
            "page": page,
        }
        try:
            payload = _api_get(get_flights_airports_light_path(), params, request_ctx)
        except RequestBudgetExhausted:
            budget_exhausted = True
            break
        except Exception as exc:
            errors.append(str(exc))
            break

        rows = _extract_items(payload, ("airports", "data.airports", "data.items", "data", "items"))
        if not rows:
            break

        for row in rows:
            parsed = _parse_airport_row(row)
            if parsed is None:
                continue
            parsed["is_cuba"] = True
            _upsert_airport(parsed, airport_cache)
            stored += 1

        if len(rows) < limit:
            break

    return stored, errors, budget_exhausted


def _needs_airport_sync(now_utc: datetime, safe_mode: bool) -> bool:
    if not get_flights_airports_sync_enabled():
        return False

    total = db.session.query(func.count(FlightAirport.id)).scalar() or 0
    if total <= 0:
        return True

    if safe_mode:
        return False

    latest_updated = (
        db.session.query(func.max(FlightAirport.updated_at))
        .filter(FlightAirport.is_cuba.is_(True))
        .scalar()
    )
    if latest_updated is None:
        return True

    age_seconds = (now_utc - latest_updated).total_seconds()
    return age_seconds >= float(get_flights_airports_sync_interval_seconds())


def _collect_backfill_records(
    request_ctx: RequestContext,
    known_cuba_codes: set[str],
    hours: int,
) -> FetchBatch:
    batch = FetchBatch()
    if hours <= 0:
        return batch
    if not get_flights_backfill_historic_enabled():
        batch.errors.append(
            "Backfill historico desactivado: configura FLIGHTS_BACKFILL_HISTORIC_ENABLED=1."
        )
        return batch

    now_utc = _utc_now_naive()
    start_utc = now_utc - timedelta(hours=hours)
    cursor = start_utc
    chunk_hours = get_flights_backfill_chunk_hours()
    max_pages = get_flights_events_max_pages()

    def _tokenize_airports(raw_airports: str) -> list[tuple[str, str]]:
        tokens: list[tuple[str, str]] = []
        for raw in str(raw_airports or "").split(","):
            part = raw.strip()
            if not part:
                continue
            direction = ""
            code = part
            if ":" in part:
                direction, code = part.split(":", 1)
            direction = _clean_text(direction, upper=True, limit=16)
            code = _clean_text(code, upper=True, limit=16)
            if not code:
                continue
            tokens.append((direction, code))
        return tokens

    def _force_destination_for_airports(raw_airports: str) -> bool:
        for direction, code in _tokenize_airports(raw_airports):
            if direction and direction != "INBOUND":
                continue
            if code in {"CU", "CUB"} or code in known_cuba_codes:
                return True
        return False

    def _expand_country_airports(raw_airports: str) -> str:
        tokens = _tokenize_airports(raw_airports)
        has_country_selector = any(code in {"CU", "CUB"} for _direction, code in tokens)
        if not has_country_selector:
            return ""
        codes = sorted(code for code in known_cuba_codes if 3 <= len(code) <= 4)
        if not codes:
            return ""
        selected = codes[:15]
        return ",".join(f"inbound:{code}" for code in selected)

    backfill_airports = get_flights_live_filter_airports() or "inbound:CU"
    backfill_bounds = get_flights_live_filter_bounds()

    attempts: list[tuple[dict[str, Any], bool]] = []
    seen_attempts: set[tuple[tuple[tuple[str, str], ...], bool]] = set()

    def _add_attempt(params: dict[str, Any], force_destination_cuba: bool) -> None:
        normalized = tuple(sorted((str(key), str(value)) for key, value in params.items()))
        signature = (normalized, bool(force_destination_cuba))
        if signature in seen_attempts:
            return
        seen_attempts.add(signature)
        attempts.append((dict(params), bool(force_destination_cuba)))

    if backfill_airports:
        params = {"light": 1, "airports": backfill_airports}
        if backfill_bounds:
            params["bounds"] = backfill_bounds
        _add_attempt(params, _force_destination_for_airports(backfill_airports))

        expanded_airports = _expand_country_airports(backfill_airports)
        if expanded_airports and expanded_airports != backfill_airports:
            expanded_params = {"light": 1, "airports": expanded_airports}
            if backfill_bounds:
                expanded_params["bounds"] = backfill_bounds
            _add_attempt(expanded_params, True)

    if not attempts:
        fallback_params: dict[str, Any] = {"light": 1}
        fallback_params["bounds"] = backfill_bounds or DEFAULT_CUBA_LIVE_BOUNDS
        _add_attempt(fallback_params, False)

    snapshot_step = timedelta(hours=max(1, chunk_hours))
    while cursor < now_utc:
        timestamp = int(cursor.replace(tzinfo=timezone.utc).timestamp())

        for base_params, force_destination_cuba in attempts:
            params = dict(base_params)
            params["timestamp"] = timestamp

            chunk = _query_events_from_endpoint(
                get_flights_historic_positions_light_path(),
                params,
                (
                    "positions",
                    "flights",
                    "data.positions",
                    "data.flights",
                    "data.items",
                    "items",
                    "data",
                ),
                known_cuba_codes,
                "historic",
                request_ctx,
                max_pages=max_pages,
                force_destination_cuba=force_destination_cuba,
            )
            batch.records.extend(chunk.records)
            batch.seen += chunk.seen
            batch.errors.extend(chunk.errors)
            if getattr(chunk, "rate_limited", False):
                batch.rate_limited = True
                break
            if chunk.budget_exhausted:
                batch.budget_exhausted = True
                break
            if chunk.seen > 0 or chunk.records:
                break

        if batch.budget_exhausted or batch.rate_limited:
            break
        cursor = min(cursor + snapshot_step, now_utc)

    return batch


def _collect_live_records(
    request_ctx: RequestContext,
    known_cuba_codes: set[str],
    safe_mode: bool,
) -> FetchBatch:
    max_pages = get_flights_safe_mode_events_max_pages() if safe_mode else get_flights_events_max_pages()
    live_airports = get_flights_live_filter_airports()
    live_bounds = get_flights_live_filter_bounds()

    def _tokenize_airports(raw_airports: str) -> list[tuple[str, str]]:
        tokens: list[tuple[str, str]] = []
        for raw in str(raw_airports or "").split(","):
            part = raw.strip()
            if not part:
                continue
            direction = ""
            code = part
            if ":" in part:
                direction, code = part.split(":", 1)
            direction = _clean_text(direction, upper=True, limit=16)
            code = _clean_text(code, upper=True, limit=16)
            if not code:
                continue
            tokens.append((direction, code))
        return tokens

    def _force_destination_for_airports(raw_airports: str) -> bool:
        for direction, code in _tokenize_airports(raw_airports):
            if direction and direction != "INBOUND":
                continue
            if code in {"CU", "CUB"} or code in known_cuba_codes:
                return True
        return False

    def _expand_country_airports(raw_airports: str) -> str:
        tokens = _tokenize_airports(raw_airports)
        has_country_selector = any(code in {"CU", "CUB"} for _direction, code in tokens)
        if not has_country_selector:
            return ""

        codes = sorted(code for code in known_cuba_codes if 3 <= len(code) <= 4)
        if not codes:
            return ""
        # Keep the selector short to avoid provider-side size limits.
        selected = codes[:15]
        return ",".join(f"inbound:{code}" for code in selected)

    attempts: list[tuple[dict[str, Any], bool]] = []
    seen_attempts: set[tuple[tuple[tuple[str, str], ...], bool]] = set()

    def _add_attempt(params: dict[str, Any], force_destination_cuba: bool) -> None:
        normalized = tuple(sorted((str(key), str(value)) for key, value in params.items()))
        signature = (normalized, bool(force_destination_cuba))
        if signature in seen_attempts:
            return
        seen_attempts.add(signature)
        attempts.append((dict(params), bool(force_destination_cuba)))

    if live_airports:
        params = {"light": 1, "airports": live_airports}
        if live_bounds:
            params["bounds"] = live_bounds
        _add_attempt(params, _force_destination_for_airports(live_airports))

        expanded_airports = _expand_country_airports(live_airports)
        if expanded_airports and expanded_airports != live_airports:
            expanded_params = {"light": 1, "airports": expanded_airports}
            if live_bounds:
                expanded_params["bounds"] = live_bounds
            _add_attempt(expanded_params, True)

    if not attempts:
        fallback_params: dict[str, Any] = {"light": 1}
        fallback_params["bounds"] = live_bounds or DEFAULT_CUBA_LIVE_BOUNDS
        _add_attempt(fallback_params, False)

    combined = FetchBatch()
    for params, force_destination_cuba in attempts:
        chunk = _query_events_from_endpoint(
            get_flights_live_positions_light_path(),
            params,
            ("positions", "flights", "data.positions", "data.flights", "data.items", "items", "data"),
            known_cuba_codes,
            "live",
            request_ctx,
            max_pages=max_pages,
            force_destination_cuba=force_destination_cuba,
        )
        combined.records.extend(chunk.records)
        combined.seen += int(chunk.seen)
        combined.errors.extend(chunk.errors)
        if getattr(chunk, "rate_limited", False):
            combined.rate_limited = True
            break
        if chunk.budget_exhausted:
            combined.budget_exhausted = True
            break
        if chunk.seen > 0 or chunk.records:
            break

    return combined


def _persist_records(
    records: list[dict[str, Any]],
    ingestion_run: FlightIngestionRun,
) -> tuple[int, int]:
    events_stored = 0
    positions_stored = 0

    airport_cache: dict[str, FlightAirport] = {}
    aircraft_cache: dict[str, FlightAircraft] = {}
    event_cache: dict[str, FlightEvent] = {}

    sorted_records = sorted(
        records,
        key=lambda item: (
            item.get("event_key") or "",
            item.get("observed_at_utc") or datetime.min,
        ),
    )

    for record in sorted_records:
        destination_airport = _resolve_destination_airport(record, airport_cache)
        aircraft = _upsert_aircraft(record, aircraft_cache)
        db.session.flush()

        event, created = _upsert_event(
            record,
            aircraft,
            destination_airport,
            ingestion_run,
            event_cache,
        )
        db.session.flush()

        if created:
            events_stored += 1

        if _store_position(event, record):
            positions_stored += 1

    return events_stored, positions_stored


def _windows() -> tuple[int, ...]:
    return WINDOW_HOURS_SUPPORTED


def _build_snapshot_payload(window_hours: int, now_utc: datetime | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    now = _normalize_utc_datetime(now_utc) or _utc_now_naive()
    window_start = now - timedelta(hours=int(window_hours))

    rows = (
        FlightEvent.query.options(
            selectinload(FlightEvent.aircraft),
            selectinload(FlightEvent.destination_airport),
        )
        .filter(
            FlightEvent.last_seen_at_utc.isnot(None),
            FlightEvent.last_seen_at_utc >= window_start,
            FlightEvent.latest_latitude.isnot(None),
            FlightEvent.latest_longitude.isnot(None),
            or_(
                FlightEvent.destination_airport_id.isnot(None),
                func.lower(func.coalesce(FlightEvent.destination_country, "")).contains("cuba"),
                FlightEvent.destination_country == "CU",
            ),
        )
        .order_by(FlightEvent.last_seen_at_utc.desc(), FlightEvent.id.desc())
        .limit(get_flights_snapshot_point_limit())
        .all()
    )

    points: list[dict[str, Any]] = []
    by_destination: Counter[str] = Counter()
    airport_lookup_cache: dict[tuple[str, str], dict[str, Any]] = {}

    for row in rows:
        lat = _safe_float(row.latest_latitude)
        lng = _safe_float(row.latest_longitude)
        if lat is None or lng is None:
            continue

        origin_ref = _find_airport_point(
            row.origin_airport_icao,
            row.origin_airport_iata,
            cache=airport_lookup_cache,
        )
        destination_ref = _find_airport_point(
            row.destination_airport_icao,
            row.destination_airport_iata,
            cache=airport_lookup_cache,
        )
        aircraft = row.aircraft
        destination_name = (
            (row.destination_airport.name if row.destination_airport else "")
            or row.destination_airport_name
            or _clean_text(destination_ref.get("name"), limit=255)
            or "Aeropuerto Cuba"
        )
        by_destination[destination_name] += 1

        photo_url = ""
        if aircraft:
            photo_url = (
                _clean_text(aircraft.photo_manual_url, limit=1000)
                or _clean_text(aircraft.photo_api_url, limit=1000)
            )

        points.append(
            {
                "event_id": row.id,
                "aircraft_id": row.aircraft_id,
                "event_key": row.event_key,
                "external_flight_id": row.external_flight_id,
                "call_sign": row.call_sign,
                "model": row.model,
                "registration": row.registration,
                "status": row.status,
                "origin_airport_name": row.origin_airport_name,
                "origin_airport_icao": row.origin_airport_icao,
                "origin_airport_iata": row.origin_airport_iata,
                "origin_city": _clean_text(origin_ref.get("city"), limit=120),
                "origin_country": _clean_text(row.origin_country, limit=120)
                or _clean_text(origin_ref.get("country"), limit=120),
                "destination_airport_name": destination_name,
                "destination_airport_icao": row.destination_airport_icao,
                "destination_airport_iata": row.destination_airport_iata,
                "destination_city": (
                    _clean_text(row.destination_airport.city, limit=120)
                    if row.destination_airport
                    else _clean_text(destination_ref.get("city"), limit=120)
                ),
                "destination_country": (
                    _clean_text(row.destination_country, limit=120)
                    or (
                        _clean_text(row.destination_airport.country_name, limit=120)
                        if row.destination_airport
                        else ""
                    )
                    or _clean_text(destination_ref.get("country"), limit=120)
                    or "Cuba"
                ),
                "latitude": lat,
                "longitude": lng,
                "altitude": _safe_float(row.latest_altitude),
                "speed": _safe_float(row.latest_speed),
                "heading": _safe_float(row.latest_heading),
                "observed_at_utc": serialize_flight_time(row.last_seen_at_utc),
                "photo_url": photo_url,
            }
        )

    summary = {
        "window_hours": int(window_hours),
        "window_start_utc": serialize_flight_time(window_start),
        "window_end_utc": serialize_flight_time(now),
        "total_flights": len(points),
        "destination_airports": len(by_destination),
        "by_destination_airport": [
            {"airport": airport, "count": int(count)}
            for airport, count in by_destination.most_common(20)
        ],
    }

    return points, summary


def refresh_flight_layer_snapshots(
    ingestion_run: FlightIngestionRun | None = None,
    now_utc: datetime | None = None,
) -> dict[int, FlightLayerSnapshot]:
    now = _normalize_utc_datetime(now_utc) or _utc_now_naive()
    snapshots: dict[int, FlightLayerSnapshot] = {}

    for hours in _windows():
        points, summary = _build_snapshot_payload(hours, now_utc=now)
        row = FlightLayerSnapshot.query.filter_by(window_hours=hours).first()
        if row is None:
            row = FlightLayerSnapshot(window_hours=hours)
            db.session.add(row)

        row.generated_at_utc = now
        row.stale_after_seconds = get_flights_snapshot_stale_after_seconds()
        row.points_count = len(points)
        row.summary_json = json.dumps(summary, ensure_ascii=False)
        row.points_json = json.dumps(points, ensure_ascii=False)
        row.ingestion_run = ingestion_run
        snapshots[hours] = row

    return snapshots


def ingest_flights_cuba(
    scheduled_for: datetime | None = None,
    raise_on_error: bool = False,
    force_backfill: bool = False,
) -> dict[str, Any]:
    if not get_flights_enabled():
        return {
            "status": "skipped",
            "reason": "flights_disabled",
        }

    fr24_available = bool(get_flights_api_key())
    opensky_available = bool(get_flights_opensky_enabled() and _opensky_credentials_ready())
    if not fr24_available and not opensky_available:
        return {
            "status": "skipped",
            "reason": "missing_flights_api_key_and_opensky_credentials",
        }

    now_utc = _utc_now_naive()
    month_used_before = get_monthly_credit_usage(now_utc)
    monthly_budget = get_flights_monthly_credit_budget()
    safe_mode = _safe_mode_active(month_used_before, monthly_budget)

    request_cap = get_flights_safe_request_cap_per_run() if safe_mode else get_flights_request_cap_per_run()
    request_ctx = RequestContext(
        request_cap=request_cap,
        rate_limit_per_second=get_flights_request_rate_limit(),
    )

    scheduled_for_utc = _normalize_utc_datetime(scheduled_for) or now_utc

    run = FlightIngestionRun(
        scheduled_for_utc=scheduled_for_utc,
        started_at_utc=now_utc,
        status="running",
        safe_mode=safe_mode,
    )
    db.session.add(run)
    db.session.flush()

    errors: list[str] = []
    airports_synced = 0
    events_seen = 0
    events_stored = 0
    positions_stored = 0
    fr24_rate_limited = False
    opensky_rate_limited = False
    opensky_used = False
    opensky_request_count = 0
    opensky_events_seen = 0
    opensky_fallback_reason = "not_evaluated"

    try:
        if fr24_available and _needs_airport_sync(now_utc, safe_mode):
            synced, airport_errors, airports_budget_exhausted = _sync_cuba_airports(request_ctx)
            airports_synced = synced
            errors.extend(airport_errors)
            if airports_budget_exhausted:
                request_ctx.budget_exhausted = True

        known_codes = _known_cuba_airport_codes() or set(get_flights_cuba_airport_codes())

        has_events = db.session.query(FlightEvent.id).limit(1).first() is not None
        run_full_backfill = bool(force_backfill)
        if not run_full_backfill and get_flights_backfill_on_empty_db() and not has_events:
            run_full_backfill = True

        historic_hours = 0
        if run_full_backfill:
            historic_hours = max(0, int(get_flights_backfill_days()) * 24)
        else:
            historic_hours = get_flights_polling_historic_hours()
        if run_full_backfill:
            run.is_backfill = True
            run.backfill_days = get_flights_backfill_days()

        all_records: list[dict[str, Any]] = []
        fr24_records_count = 0

        if fr24_available:
            if historic_hours > 0:
                if not (safe_mode and get_flights_safe_mode_skip_backfill()):
                    backfill_batch = _collect_backfill_records(
                        request_ctx,
                        known_codes,
                        hours=historic_hours,
                    )
                    all_records.extend(backfill_batch.records)
                    events_seen += backfill_batch.seen
                    errors.extend(backfill_batch.errors)
                    if getattr(backfill_batch, "rate_limited", False):
                        fr24_rate_limited = True
                    if backfill_batch.budget_exhausted:
                        request_ctx.budget_exhausted = True

            if not fr24_rate_limited:
                live_batch = _collect_live_records(request_ctx, known_codes, safe_mode=safe_mode)
                all_records.extend(live_batch.records)
                events_seen += live_batch.seen
                errors.extend(live_batch.errors)
                if getattr(live_batch, "rate_limited", False):
                    fr24_rate_limited = True
                if live_batch.budget_exhausted:
                    request_ctx.budget_exhausted = True
            fr24_records_count = len(all_records)
        else:
            errors.append("FLIGHTS_API_KEY no configurada: ejecutando fallback OpenSky.")

        use_opensky_fallback, opensky_fallback_reason = _should_use_opensky_fallback(
            fr24_available=fr24_available,
            fr24_records_count=fr24_records_count,
            fr24_rate_limited=fr24_rate_limited,
            fr24_budget_exhausted=bool(request_ctx.budget_exhausted),
        )
        if use_opensky_fallback:
            opensky_ctx = RequestContext(
                request_cap=get_flights_opensky_request_cap_per_run(),
                rate_limit_per_second=get_flights_opensky_request_rate_limit(),
            )
            opensky_batch = _collect_opensky_fallback_records(
                opensky_ctx,
                known_codes,
                historic_hours=historic_hours,
            )
            all_records.extend(opensky_batch.records)
            events_seen += opensky_batch.seen
            opensky_events_seen = int(opensky_batch.seen)
            opensky_request_count = int(opensky_ctx.request_count)
            errors.extend(opensky_batch.errors)
            opensky_rate_limited = bool(getattr(opensky_batch, "rate_limited", False))
            opensky_used = bool(opensky_batch.records)
            if opensky_batch.budget_exhausted:
                errors.append("OpenSky request cap agotado en esta corrida.")

        if all_records:
            events_stored, positions_stored = _persist_records(all_records, run)

        snapshots = refresh_flight_layer_snapshots(ingestion_run=run, now_utc=_utc_now_naive())

        rate_limited = bool(fr24_rate_limited or opensky_rate_limited)
        run.status = "success"
        if errors or request_ctx.budget_exhausted:
            run.status = "partial"

        run.airports_synced = int(airports_synced)
        run.events_seen = int(events_seen)
        run.events_stored = int(events_stored)
        run.positions_stored = int(positions_stored)
        run.request_count = int(request_ctx.request_count)
        run.estimated_credits = int(request_ctx.estimated_credits)

        month_used_after = get_monthly_credit_usage(_utc_now_naive()) + int(request_ctx.estimated_credits)

        payload = {
            "window_snapshots": {
                str(hours): {
                    "points_count": int(snapshot.points_count or 0),
                    "generated_at_utc": serialize_flight_time(snapshot.generated_at_utc),
                }
                for hours, snapshot in snapshots.items()
            },
            "safe_mode": bool(safe_mode),
            "budget": {
                "monthly_used_before": int(month_used_before),
                "monthly_used_after": int(month_used_after),
                "monthly_budget": int(monthly_budget),
                "guardrail_percent": float(get_flights_guardrail_percent()),
                "guardrail_reached": bool(_safe_mode_active(month_used_after, monthly_budget)),
            },
            "opensky": {
                "enabled": bool(get_flights_opensky_enabled()),
                "used": bool(opensky_used),
                "fallback_reason": opensky_fallback_reason,
                "request_count": int(opensky_request_count),
                "events_seen": int(opensky_events_seen),
                "rate_limited": bool(opensky_rate_limited),
            },
            "warnings": errors,
            "rate_limited": bool(rate_limited),
            "budget_exhausted": bool(request_ctx.budget_exhausted),
        }
        run.payload_json = json.dumps(payload, ensure_ascii=False)
        run.error_message = "; ".join(errors)[:900] if errors else None

        run.finished_at_utc = _utc_now_naive()
        db.session.commit()

        return {
            "status": run.status,
            "run_id": run.id,
            "safe_mode": bool(run.safe_mode),
            "request_count": int(run.request_count or 0),
            "estimated_credits": int(run.estimated_credits or 0),
            "events_seen": int(run.events_seen or 0),
            "events_stored": int(run.events_stored or 0),
            "positions_stored": int(run.positions_stored or 0),
            "rate_limited": bool(rate_limited),
            "budget_exhausted": bool(request_ctx.budget_exhausted),
            "opensky_used": bool(opensky_used),
            "opensky_request_count": int(opensky_request_count),
            "opensky_events_seen": int(opensky_events_seen),
            "opensky_fallback_reason": opensky_fallback_reason,
            "warnings": errors,
        }
    except Exception as exc:
        db.session.rollback()
        logger.exception("Error ingestando capa de vuelos a Cuba")

        fail_run = FlightIngestionRun(
            scheduled_for_utc=scheduled_for_utc,
            started_at_utc=now_utc,
            finished_at_utc=_utc_now_naive(),
            status="error",
            safe_mode=safe_mode,
            request_count=int(request_ctx.request_count),
            estimated_credits=int(request_ctx.estimated_credits),
            error_message=str(exc)[:900],
        )
        db.session.add(fail_run)
        db.session.commit()

        if raise_on_error:
            raise

        return {
            "status": "error",
            "error": str(exc),
            "request_count": int(request_ctx.request_count),
            "estimated_credits": int(request_ctx.estimated_credits),
        }


def decode_snapshot_json(raw: str | None, default: Any):
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


def _needs_summary_enrichment(aircraft: FlightAircraft, event: FlightEvent | None) -> bool:
    aircraft_missing = not (
        _clean_text(aircraft.model, limit=120)
        and _clean_text(aircraft.registration, limit=64)
        and _clean_text(aircraft.operator_name, limit=255)
    )
    if event is None:
        return aircraft_missing

    origin_missing = not (
        _clean_text(event.origin_airport_icao, upper=True, limit=8)
        or _clean_text(event.origin_airport_iata, upper=True, limit=8)
        or _clean_text(event.origin_airport_name, limit=255)
    )
    destination_code_missing = not (
        _clean_text(event.destination_airport_icao, upper=True, limit=8)
        or _clean_text(event.destination_airport_iata, upper=True, limit=8)
    )
    destination_name = _clean_text(event.destination_airport_name, limit=255)
    destination_missing = destination_code_missing or (not destination_name or destination_name == "Aeropuerto Cuba")
    timing_missing = event.departure_at_utc is None and event.arrival_at_utc is None

    return aircraft_missing or origin_missing or destination_missing or timing_missing


def _summary_selector_attempts(
    aircraft: FlightAircraft,
    event: FlightEvent | None,
) -> list[dict[str, Any]]:
    now_utc = _utc_now_naive()
    center = (
        (event.last_seen_at_utc if event else None)
        or (event.departure_at_utc if event else None)
        or (event.arrival_at_utc if event else None)
        or aircraft.last_seen_at_utc
        or now_utc
    )
    lookback_hours = get_flights_summary_on_demand_hours()
    range_from = center - timedelta(hours=lookback_hours)
    range_to = center + timedelta(hours=6)

    base: dict[str, Any] = {
        "flight_datetime_from": serialize_flight_time(range_from),
        "flight_datetime_to": serialize_flight_time(range_to),
        "limit": get_flights_summary_on_demand_limit(),
        "sort": "desc",
    }

    call_sign = _clean_text(
        (event.call_sign if event else "") or aircraft.call_sign,
        upper=True,
        limit=64,
    )
    registration = _clean_text(
        (event.registration if event else "") or aircraft.registration,
        upper=True,
        limit=64,
    )

    attempts: list[dict[str, Any]] = []
    seen: set[tuple[tuple[str, str], ...]] = set()

    def _push(extra: dict[str, Any]) -> None:
        params = dict(base)
        params.update(extra)
        signature = tuple(sorted((str(k), str(v)) for k, v in params.items()))
        if signature in seen:
            return
        seen.add(signature)
        attempts.append(params)

    if call_sign:
        _push({"callsigns": call_sign})
        _push({"flights": call_sign})
    if registration:
        _push({"registrations": registration})
    if call_sign and registration:
        _push({"callsigns": call_sign, "registrations": registration})

    return attempts


def _fetch_summary_rows_on_demand(
    aircraft: FlightAircraft,
    event: FlightEvent | None,
) -> tuple[list[dict[str, Any]], list[str], bool, int]:
    warnings: list[str] = []
    attempts = _summary_selector_attempts(aircraft, event)
    if not attempts:
        return [], warnings, False, 0

    request_ctx = RequestContext(
        request_cap=max(1, len(attempts)),
        rate_limit_per_second=get_flights_request_rate_limit(),
    )
    for params in attempts:
        try:
            payload = _api_get(get_flights_summary_light_path(), params, request_ctx)
        except FlightsApiRateLimited as exc:
            warnings.append(str(exc))
            return [], warnings, True, int(request_ctx.request_count)
        except Exception as exc:
            warnings.append(str(exc))
            continue

        rows = _extract_items(payload, ("data", "items", "results"))
        if rows:
            return rows, warnings, False, int(request_ctx.request_count)

    return [], warnings, False, int(request_ctx.request_count)


def _score_summary_row(
    row: dict[str, Any],
    aircraft: FlightAircraft,
    event: FlightEvent | None,
    known_cuba_codes: set[str],
) -> float:
    score = 0.0

    row_id = _normalize_token(_pick(row, "fr24_id", "id", "flight_id"))
    event_id = _normalize_token(event.external_flight_id if event else "")
    if row_id and event_id and row_id == event_id:
        score += 200.0

    row_callsign = _clean_text(_pick(row, "callsign", "flight"), upper=True, limit=64)
    target_callsign = _clean_text(
        (event.call_sign if event else "") or aircraft.call_sign,
        upper=True,
        limit=64,
    )
    if row_callsign and target_callsign and row_callsign == target_callsign:
        score += 80.0

    row_reg = _clean_text(_pick(row, "reg", "registration"), upper=True, limit=64)
    target_reg = _clean_text(
        (event.registration if event else "") or aircraft.registration,
        upper=True,
        limit=64,
    )
    if row_reg and target_reg and row_reg == target_reg:
        score += 60.0

    dest_icao = _clean_text(
        _pick(
            row,
            "destination_icao_actual",
            "dest_icao_actual",
            "destination_icao",
            "dest_icao",
        ),
        upper=True,
        limit=8,
    )
    if dest_icao and dest_icao in known_cuba_codes:
        score += 40.0

    reference_time = (
        (event.last_seen_at_utc if event else None)
        or (event.departure_at_utc if event else None)
        or aircraft.last_seen_at_utc
    )
    row_time = _parse_datetime(_pick(row, "last_seen", "datetime_landed", "datetime_takeoff"))
    if reference_time and row_time:
        delta_hours = abs((reference_time - row_time).total_seconds()) / 3600.0
        score += max(0.0, 30.0 - min(delta_hours, 30.0))

    return score


def _best_summary_row(
    rows: list[dict[str, Any]],
    aircraft: FlightAircraft,
    event: FlightEvent | None,
    known_cuba_codes: set[str],
) -> dict[str, Any] | None:
    if not rows:
        return None
    ranked = sorted(
        rows,
        key=lambda row: _score_summary_row(row, aircraft, event, known_cuba_codes),
        reverse=True,
    )
    best = ranked[0]
    if _score_summary_row(best, aircraft, event, known_cuba_codes) <= 0:
        return None
    return best


def _apply_summary_row_cache(
    row: dict[str, Any],
    aircraft: FlightAircraft,
    event: FlightEvent | None,
    known_cuba_codes: set[str],
) -> bool:
    changed = False

    call_sign = _clean_text(_pick(row, "callsign", "flight"), limit=64)
    model = _clean_text(_pick(row, "type", "model"), limit=120)
    registration = _clean_text(_pick(row, "reg", "registration"), limit=64)
    operator_name = _clean_text(_pick(row, "operated_as", "painted_as"), limit=255)
    hex_code = _clean_text(_pick(row, "hex"), upper=True, limit=32)
    first_seen = _parse_datetime(_pick(row, "first_seen"))
    last_seen = _parse_datetime(_pick(row, "last_seen"))

    if call_sign and not _clean_text(aircraft.call_sign, limit=64):
        aircraft.call_sign = call_sign
        changed = True
    if model and not _clean_text(aircraft.model, limit=120):
        aircraft.model = model
        changed = True
    if registration and not _clean_text(aircraft.registration, limit=64):
        aircraft.registration = registration
        changed = True
    if operator_name and not _clean_text(aircraft.operator_name, limit=255):
        aircraft.operator_name = operator_name
        changed = True
    if hex_code and not _clean_text(aircraft.hex_code, upper=True, limit=32):
        aircraft.hex_code = hex_code
        changed = True
    if first_seen and (aircraft.first_seen_at_utc is None or first_seen < aircraft.first_seen_at_utc):
        aircraft.first_seen_at_utc = first_seen
        changed = True
    if last_seen and (aircraft.last_seen_at_utc is None or last_seen > aircraft.last_seen_at_utc):
        aircraft.last_seen_at_utc = last_seen
        changed = True

    if event is None:
        return changed

    fr24_id = _clean_text(_pick(row, "fr24_id", "id", "flight_id"), limit=128)
    if fr24_id and not _clean_text(event.external_flight_id, limit=128):
        event.external_flight_id = fr24_id
        changed = True

    if call_sign and not _clean_text(event.call_sign, limit=64):
        event.call_sign = call_sign
        changed = True
    if model and not _clean_text(event.model, limit=120):
        event.model = model
        changed = True
    if registration and not _clean_text(event.registration, limit=64):
        event.registration = registration
        changed = True

    origin_icao = _clean_text(_pick(row, "origin_icao", "orig_icao"), upper=True, limit=8)
    origin_iata = _clean_text(_pick(row, "origin_iata", "orig_iata"), upper=True, limit=8)
    if origin_icao and not _clean_text(event.origin_airport_icao, upper=True, limit=8):
        event.origin_airport_icao = origin_icao
        changed = True
    if origin_iata and not _clean_text(event.origin_airport_iata, upper=True, limit=8):
        event.origin_airport_iata = origin_iata
        changed = True
    if (
        not _clean_text(event.origin_airport_name, limit=255)
        and (origin_icao or origin_iata)
    ):
        event.origin_airport_name = origin_icao or origin_iata
        changed = True

    dest_icao = _clean_text(
        _pick(
            row,
            "destination_icao_actual",
            "dest_icao_actual",
            "destination_icao",
            "dest_icao",
        ),
        upper=True,
        limit=8,
    )
    dest_iata = _clean_text(
        _pick(
            row,
            "destination_iata_actual",
            "dest_iata_actual",
            "destination_iata",
            "dest_iata",
        ),
        upper=True,
        limit=8,
    )
    if dest_icao and not _clean_text(event.destination_airport_icao, upper=True, limit=8):
        event.destination_airport_icao = dest_icao
        changed = True
    if dest_iata and not _clean_text(event.destination_airport_iata, upper=True, limit=8):
        event.destination_airport_iata = dest_iata
        changed = True
    current_dest_name = _clean_text(event.destination_airport_name, limit=255)
    if (not current_dest_name or current_dest_name == "Aeropuerto Cuba") and (dest_icao or dest_iata):
        event.destination_airport_name = dest_icao or dest_iata
        changed = True

    if (dest_icao and dest_icao in known_cuba_codes) or (dest_iata and dest_iata in known_cuba_codes):
        if _clean_text(event.destination_country, limit=120) != "Cuba":
            event.destination_country = "Cuba"
            changed = True

    departure_at = _parse_datetime(_pick(row, "datetime_takeoff"))
    arrival_at = _parse_datetime(_pick(row, "datetime_landed"))
    if departure_at and event.departure_at_utc is None:
        event.departure_at_utc = departure_at
        changed = True
    if arrival_at and event.arrival_at_utc is None:
        event.arrival_at_utc = arrival_at
        changed = True

    if first_seen and (event.first_seen_at_utc is None or first_seen < event.first_seen_at_utc):
        event.first_seen_at_utc = first_seen
        changed = True
    if last_seen and (event.last_seen_at_utc is None or last_seen > event.last_seen_at_utc):
        event.last_seen_at_utc = last_seen
        changed = True

    flight_ended = _pick(row, "flight_ended")
    if not _clean_text(event.status, limit=64):
        if isinstance(flight_ended, bool):
            event.status = "landed" if flight_ended else "live"
            changed = True
        else:
            ended_text = _clean_text(flight_ended, upper=True, limit=16)
            if ended_text in {"TRUE", "1"}:
                event.status = "landed"
                changed = True
            elif ended_text in {"FALSE", "0"}:
                event.status = "live"
                changed = True

    if changed:
        event.last_source_kind = _clean_text(event.last_source_kind, limit=64) or "summary_light_on_demand"

    return changed


def enrich_aircraft_detail_from_summary_light(
    aircraft: FlightAircraft,
    event: FlightEvent | None = None,
) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "status": "skipped",
        "enabled": bool(get_flights_summary_on_demand_enabled()),
        "event_id": int(event.id) if event else None,
        "requests": 0,
        "warnings": [],
        "updated": False,
    }

    if not get_flights_summary_on_demand_enabled():
        meta["reason"] = "summary_on_demand_disabled"
        return meta
    if not get_flights_api_key():
        meta["reason"] = "missing_flights_api_key"
        return meta
    if not _needs_summary_enrichment(aircraft, event):
        meta["status"] = "cached"
        meta["reason"] = "already_enriched"
        return meta

    known_cuba_codes = _known_cuba_airport_codes()
    rows, warnings, rate_limited, request_count = _fetch_summary_rows_on_demand(aircraft, event)
    meta["warnings"] = warnings
    meta["requests"] = int(request_count)
    if rate_limited:
        meta["status"] = "rate_limited"
        return meta
    if not rows:
        meta["status"] = "no_match"
        return meta

    best_row = _best_summary_row(rows, aircraft, event, known_cuba_codes)
    if best_row is None:
        meta["status"] = "no_match"
        return meta

    changed = _apply_summary_row_cache(best_row, aircraft, event, known_cuba_codes)
    meta["updated"] = bool(changed)
    if not changed:
        meta["status"] = "cached"
        return meta

    try:
        db.session.commit()
        meta["status"] = "enriched"
        return meta
    except Exception as exc:
        db.session.rollback()
        logger.exception("Error guardando enriquecimiento on-demand de Flight summary light")
        meta["status"] = "error"
        meta["warnings"] = list(meta.get("warnings") or []) + [str(exc)]
        return meta


def _effective_photo_payload(aircraft: FlightAircraft | None) -> tuple[str, str]:
    if not aircraft:
        return "", "none"
    manual = _clean_text(aircraft.photo_manual_url, limit=1000)
    if manual:
        return manual, "manual"
    api_url = _clean_text(aircraft.photo_api_url, limit=1000)
    if api_url:
        return api_url, "api"
    return "", "none"


def build_aircraft_detail_payload(aircraft: FlightAircraft, now_utc: datetime | None = None) -> dict[str, Any]:
    now = _normalize_utc_datetime(now_utc) or _utc_now_naive()
    window_start = now - timedelta(days=30)

    event_rows = (
        FlightEvent.query.options(selectinload(FlightEvent.destination_airport))
        .filter(
            FlightEvent.aircraft_id == aircraft.id,
            FlightEvent.last_seen_at_utc.isnot(None),
            FlightEvent.last_seen_at_utc >= window_start,
            or_(
                FlightEvent.destination_airport_id.isnot(None),
                func.lower(func.coalesce(FlightEvent.destination_country, "")).contains("cuba"),
                FlightEvent.destination_country == "CU",
            ),
        )
        .order_by(FlightEvent.last_seen_at_utc.desc(), FlightEvent.id.desc())
        .all()
    )

    origin_counter: Counter[str] = Counter()
    destination_counter: Counter[str] = Counter()
    history: list[dict[str, Any]] = []
    airport_lookup_cache: dict[tuple[str, str], dict[str, Any]] = {}

    for event in event_rows:
        origin_ref = _find_airport_point(
            event.origin_airport_icao,
            event.origin_airport_iata,
            cache=airport_lookup_cache,
        )
        destination_ref = _find_airport_point(
            event.destination_airport_icao,
            event.destination_airport_iata,
            cache=airport_lookup_cache,
        )
        origin_name = (
            _clean_text(event.origin_airport_name, limit=255)
            or _clean_text(origin_ref.get("name"), limit=255)
            or "Origen no disponible"
        )
        destination_name = (
            _clean_text(event.destination_airport_name, limit=255)
            or (event.destination_airport.name if event.destination_airport else "")
            or _clean_text(destination_ref.get("name"), limit=255)
            or "Aeropuerto Cuba"
        )

        origin_counter[origin_name] += 1
        destination_counter[destination_name] += 1

        history.append(
            {
                "event_id": event.id,
                "event_key": event.event_key,
                "external_flight_id": event.external_flight_id,
                "status": event.status,
                "origin_airport_name": origin_name,
                "origin_city": _clean_text(origin_ref.get("city"), limit=120),
                "origin_country": _clean_text(event.origin_country, limit=120)
                or _clean_text(origin_ref.get("country"), limit=120),
                "destination_airport_name": destination_name,
                "destination_city": (
                    _clean_text(event.destination_airport.city, limit=120)
                    if event.destination_airport
                    else _clean_text(destination_ref.get("city"), limit=120)
                ),
                "destination_country": (
                    _clean_text(event.destination_country, limit=120)
                    or (
                        _clean_text(event.destination_airport.country_name, limit=120)
                        if event.destination_airport
                        else ""
                    )
                    or _clean_text(destination_ref.get("country"), limit=120)
                    or "Cuba"
                ),
                "departure_at_utc": serialize_flight_time(event.departure_at_utc),
                "arrival_at_utc": serialize_flight_time(event.arrival_at_utc),
                "last_seen_at_utc": serialize_flight_time(event.last_seen_at_utc),
                "latest_position": {
                    "latitude": _safe_float(event.latest_latitude),
                    "longitude": _safe_float(event.latest_longitude),
                    "altitude": _safe_float(event.latest_altitude),
                    "speed": _safe_float(event.latest_speed),
                    "heading": _safe_float(event.latest_heading),
                },
            }
        )

    photo_url, photo_source = _effective_photo_payload(aircraft)
    photo_gallery_rows = (
        FlightAircraftPhotoRevision.query.filter_by(aircraft_id=aircraft.id)
        .order_by(FlightAircraftPhotoRevision.created_at.desc(), FlightAircraftPhotoRevision.id.desc())
        .limit(30)
        .all()
    )
    photo_gallery: list[dict[str, Any]] = []
    seen_gallery_urls: set[str] = set()
    for row in photo_gallery_rows:
        revision_url = _clean_text(row.photo_url, limit=1000)
        if not revision_url or revision_url in seen_gallery_urls:
            continue
        seen_gallery_urls.add(revision_url)
        photo_gallery.append(
            {
                "id": int(row.id),
                "photo_url": revision_url,
                "source": _clean_text(row.photo_source, limit=32) or "manual",
                "uploader_anon": _clean_text(row.uploader_anon_label, limit=80) or "Anon",
                "uploaded_at_utc": serialize_flight_time(row.created_at),
                "is_current": bool(
                    revision_url
                    and revision_url == _clean_text(aircraft.photo_manual_url, limit=1000)
                ),
            }
        )

    return {
        "aircraft": {
            "id": aircraft.id,
            "identity_key": aircraft.identity_key,
            "call_sign": aircraft.call_sign,
            "model": aircraft.model,
            "registration": aircraft.registration,
            "operator_name": aircraft.operator_name,
            "manufacturer": aircraft.manufacturer,
            "first_seen_at_utc": serialize_flight_time(aircraft.first_seen_at_utc),
            "last_seen_at_utc": serialize_flight_time(aircraft.last_seen_at_utc),
            "photo_url": photo_url,
            "photo_source": photo_source,
            "photo_api_url": _clean_text(aircraft.photo_api_url, limit=1000),
            "photo_manual_url": _clean_text(aircraft.photo_manual_url, limit=1000),
        },
        "photo_gallery": photo_gallery,
        "summary_30d": {
            "window_days": 30,
            "window_start_utc": serialize_flight_time(window_start),
            "window_end_utc": serialize_flight_time(now),
            "trips_to_cuba": len(history),
            "origins": [
                {"origin": origin, "count": int(count)}
                for origin, count in origin_counter.most_common(20)
            ],
            "destinations": [
                {"destination": destination, "count": int(count)}
                for destination, count in destination_counter.most_common(20)
            ],
        },
        "history": history,
    }


def _find_airport_point(
    icao_code: str | None,
    iata_code: str | None,
    *,
    cache: dict[tuple[str, str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    icao = _clean_text(icao_code, upper=True, limit=8)
    iata = _clean_text(iata_code, upper=True, limit=8)
    cache_key = (icao, iata)
    if cache is not None and cache_key in cache:
        return cache[cache_key]

    airport = None
    reference: dict[str, Any] = {
        "name": "",
        "city": "",
        "country": "",
        "latitude": None,
        "longitude": None,
        "code": iata or icao,
    }

    if icao:
        airport = FlightAirport.query.filter_by(airport_code_icao=icao).first()
    if airport is None and iata:
        airport = FlightAirport.query.filter_by(airport_code_iata=iata).first()
    if airport is not None:
        reference.update(
            {
                "name": _clean_text(airport.name, limit=255),
                "city": _clean_text(airport.city, limit=120),
                "country": _clean_text(airport.country_name, limit=120),
                "latitude": _safe_float(airport.latitude),
                "longitude": _safe_float(airport.longitude),
                "code": iata or icao,
            }
        )

    world_match = _lookup_world_airport(icao, iata)
    if world_match:
        if reference.get("latitude") is None:
            reference["latitude"] = _safe_float(world_match.get("latitude"))
        if reference.get("longitude") is None:
            reference["longitude"] = _safe_float(world_match.get("longitude"))
        if not reference.get("city"):
            reference["city"] = _clean_text(world_match.get("city"), limit=120)
        if not reference.get("country"):
            reference["country"] = _clean_text(world_match.get("country"), limit=120)
        if not reference.get("name"):
            reference["name"] = (
                _clean_text(world_match.get("code"), upper=True, limit=8)
                or iata
                or icao
                or ""
            )

    if not reference.get("name"):
        reference["name"] = iata or icao or ""

    if cache is not None:
        cache[cache_key] = reference
    return reference


def backfill_flights_airport_metadata_from_static_catalog(
    *,
    limit: int | None = None,
    dry_run: bool = False,
    only_missing: bool = True,
    commit_every: int = 300,
) -> dict[str, Any]:
    commit_every = max(50, int(commit_every or 300))
    max_rows = int(limit) if limit is not None else None
    if max_rows is not None and max_rows <= 0:
        max_rows = None

    static_index = _load_world_airports_index()
    airport_cache: dict[str, FlightAirport] = {}
    lookup_cache: dict[tuple[str, str], dict[str, Any]] = {}

    airports_scanned = 0
    airports_updated = 0
    events_scanned = 0
    events_updated = 0
    origin_code_inferred = 0
    destination_code_inferred = 0
    destination_linked = 0
    pending_changes = 0

    def _mark_dirty(changed: bool) -> None:
        nonlocal pending_changes
        if changed:
            pending_changes += 1

    def _maybe_commit() -> None:
        nonlocal pending_changes
        if dry_run:
            return
        if pending_changes < commit_every:
            return
        db.session.commit()
        pending_changes = 0

    try:
        airport_rows = FlightAirport.query.order_by(FlightAirport.id.asc()).all()
        for airport in airport_rows:
            airports_scanned += 1
            ref = _lookup_world_airport(airport.airport_code_icao, airport.airport_code_iata)
            if not ref:
                continue

            changed = False
            city = _clean_text(ref.get("city"), limit=120)
            country = _clean_text(ref.get("country"), upper=True, limit=120)
            latitude = _safe_float(ref.get("latitude"))
            longitude = _safe_float(ref.get("longitude"))

            if city and (not only_missing or not _clean_text(airport.city, limit=120)):
                if _clean_text(airport.city, limit=120) != city:
                    airport.city = city
                    changed = True
            if country and (not only_missing or not _clean_text(airport.country_name, limit=120)):
                if _clean_text(airport.country_name, upper=True, limit=120) != country:
                    airport.country_name = country
                    changed = True
            if country and (not only_missing or not _clean_text(airport.country_code, upper=True, limit=8)):
                if _clean_text(airport.country_code, upper=True, limit=8) != country:
                    airport.country_code = country
                    changed = True
            if latitude is not None and (
                not only_missing or _safe_float(airport.latitude) is None
            ):
                if _safe_float(airport.latitude) != latitude:
                    airport.latitude = latitude
                    changed = True
            if longitude is not None and (
                not only_missing or _safe_float(airport.longitude) is None
            ):
                if _safe_float(airport.longitude) != longitude:
                    airport.longitude = longitude
                    changed = True

            if _country_is_cuba(airport.country_name, airport.country_code) and not airport.is_cuba:
                airport.is_cuba = True
                changed = True

            if changed:
                airports_updated += 1
                _mark_dirty(True)
                _maybe_commit()

        last_id = 0
        batch_size = 500
        while True:
            remaining = None
            if max_rows is not None:
                remaining = max_rows - events_scanned
                if remaining <= 0:
                    break

            query = (
                FlightEvent.query.options(selectinload(FlightEvent.destination_airport))
                .filter(FlightEvent.id > last_id)
                .order_by(FlightEvent.id.asc())
                .limit(min(batch_size, remaining) if remaining is not None else batch_size)
            )
            batch = query.all()
            if not batch:
                break

            for event in batch:
                last_id = event.id
                events_scanned += 1
                changed = False

                origin_icao = _clean_text(event.origin_airport_icao, upper=True, limit=8)
                origin_iata = _clean_text(event.origin_airport_iata, upper=True, limit=8)
                if not origin_icao or not origin_iata:
                    inferred_icao, inferred_iata = _infer_airport_codes_from_text(
                        event.origin_airport_name
                    )
                    if inferred_icao and not origin_icao:
                        event.origin_airport_icao = inferred_icao
                        origin_icao = inferred_icao
                        changed = True
                        origin_code_inferred += 1
                    if inferred_iata and not origin_iata:
                        event.origin_airport_iata = inferred_iata
                        origin_iata = inferred_iata
                        changed = True
                        origin_code_inferred += 1
                if origin_icao and not origin_iata:
                    alias = _clean_text(_CUBA_CODE_ALIASES.get(origin_icao), upper=True, limit=8)
                    if alias and len(alias) == 3:
                        event.origin_airport_iata = alias
                        origin_iata = alias
                        changed = True
                        origin_code_inferred += 1
                if origin_iata and not origin_icao:
                    alias = _clean_text(_CUBA_CODE_ALIASES.get(origin_iata), upper=True, limit=8)
                    if alias and len(alias) == 4:
                        event.origin_airport_icao = alias
                        origin_icao = alias
                        changed = True
                        origin_code_inferred += 1

                dest_icao = _clean_text(event.destination_airport_icao, upper=True, limit=8)
                dest_iata = _clean_text(event.destination_airport_iata, upper=True, limit=8)
                if not dest_icao or not dest_iata:
                    inferred_icao, inferred_iata = _infer_airport_codes_from_text(
                        event.destination_airport_name
                    )
                    if inferred_icao and not dest_icao:
                        event.destination_airport_icao = inferred_icao
                        dest_icao = inferred_icao
                        changed = True
                        destination_code_inferred += 1
                    if inferred_iata and not dest_iata:
                        event.destination_airport_iata = inferred_iata
                        dest_iata = inferred_iata
                        changed = True
                        destination_code_inferred += 1
                if dest_icao and not dest_iata:
                    alias = _clean_text(_CUBA_CODE_ALIASES.get(dest_icao), upper=True, limit=8)
                    if alias and len(alias) == 3:
                        event.destination_airport_iata = alias
                        dest_iata = alias
                        changed = True
                        destination_code_inferred += 1
                if dest_iata and not dest_icao:
                    alias = _clean_text(_CUBA_CODE_ALIASES.get(dest_iata), upper=True, limit=8)
                    if alias and len(alias) == 4:
                        event.destination_airport_icao = alias
                        dest_icao = alias
                        changed = True
                        destination_code_inferred += 1

                origin_ref = _find_airport_point(origin_icao, origin_iata, cache=lookup_cache)
                destination_ref = _find_airport_point(dest_icao, dest_iata, cache=lookup_cache)

                if _clean_text(origin_ref.get("name"), limit=255) and (
                    not only_missing or not _clean_text(event.origin_airport_name, limit=255)
                ):
                    next_value = _clean_text(origin_ref.get("name"), limit=255)
                    if _clean_text(event.origin_airport_name, limit=255) != next_value:
                        event.origin_airport_name = next_value
                        changed = True

                if _clean_text(origin_ref.get("country"), limit=120) and (
                    not only_missing or not _clean_text(event.origin_country, limit=120)
                ):
                    next_value = _clean_text(origin_ref.get("country"), limit=120)
                    if _clean_text(event.origin_country, limit=120) != next_value:
                        event.origin_country = next_value
                        changed = True

                if _clean_text(destination_ref.get("name"), limit=255) and (
                    not only_missing or not _clean_text(event.destination_airport_name, limit=255)
                ):
                    next_value = _clean_text(destination_ref.get("name"), limit=255)
                    if _clean_text(event.destination_airport_name, limit=255) != next_value:
                        event.destination_airport_name = next_value
                        changed = True

                if _clean_text(destination_ref.get("country"), limit=120) and (
                    not only_missing or not _clean_text(event.destination_country, limit=120)
                ):
                    next_value = _clean_text(destination_ref.get("country"), limit=120)
                    if _clean_text(event.destination_country, limit=120) != next_value:
                        event.destination_country = next_value
                        changed = True

                destination_airport = event.destination_airport
                linked_icao = (
                    _clean_text(destination_airport.airport_code_icao, upper=True, limit=8)
                    if destination_airport
                    else ""
                )
                linked_iata = (
                    _clean_text(destination_airport.airport_code_iata, upper=True, limit=8)
                    if destination_airport
                    else ""
                )
                codes_available = bool(dest_icao or dest_iata)
                destination_link_mismatch = bool(
                    destination_airport is not None
                    and codes_available
                    and not (
                        (not dest_icao or linked_icao == dest_icao)
                        and (not dest_iata or linked_iata == dest_iata)
                    )
                )
                if (destination_airport is None or destination_link_mismatch) and (
                    dest_icao
                    or dest_iata
                    or _clean_text(event.destination_airport_name, limit=255)
                    or _clean_text(destination_ref.get("name"), limit=255)
                ):
                    resolved_name = (
                        _clean_text(event.destination_airport_name, limit=255)
                        or _clean_text(destination_ref.get("name"), limit=255)
                        or "Aeropuerto Cuba"
                    )
                    resolved_country = (
                        _clean_text(event.destination_country, limit=120)
                        or _clean_text(destination_ref.get("country"), limit=120)
                        or "Cuba"
                    )
                    resolved_country_code = _clean_text(destination_ref.get("country"), upper=True, limit=8)
                    if not resolved_country_code and _country_is_cuba(resolved_country, resolved_country_code):
                        resolved_country_code = "CU"
                    parsed = {
                        "code_key": _airport_code_key(dest_icao, dest_iata, "", resolved_name),
                        "fr_airport_id": "",
                        "airport_code_icao": dest_icao,
                        "airport_code_iata": dest_iata,
                        "name": resolved_name,
                        "city": _clean_text(destination_ref.get("city"), limit=120),
                        "province": "",
                        "country_code": resolved_country_code,
                        "country_name": resolved_country,
                        "latitude": _safe_float(destination_ref.get("latitude")),
                        "longitude": _safe_float(destination_ref.get("longitude")),
                        "is_cuba": _country_is_cuba(resolved_country, resolved_country_code),
                    }
                    resolved_airport = _upsert_airport(parsed, airport_cache)
                    if event.destination_airport_id != resolved_airport.id:
                        destination_linked += 1
                    if event.destination_airport is not resolved_airport:
                        event.destination_airport = resolved_airport
                        changed = True
                    destination_airport = resolved_airport

                if destination_airport is not None and destination_ref:
                    airport_changed = False
                    ref_city = _clean_text(destination_ref.get("city"), limit=120)
                    ref_country_code = _clean_text(destination_ref.get("country"), upper=True, limit=8)
                    ref_country_name = "Cuba" if ref_country_code == "CU" else ref_country_code
                    ref_lat = _safe_float(destination_ref.get("latitude"))
                    ref_lng = _safe_float(destination_ref.get("longitude"))

                    if ref_city and (not only_missing or not _clean_text(destination_airport.city, limit=120)):
                        if _clean_text(destination_airport.city, limit=120) != ref_city:
                            destination_airport.city = ref_city
                            airport_changed = True
                    if ref_country_name and (
                        not only_missing or not _clean_text(destination_airport.country_name, limit=120)
                    ):
                        if _clean_text(destination_airport.country_name, upper=True, limit=120) != _clean_text(
                            ref_country_name, upper=True, limit=120
                        ):
                            destination_airport.country_name = ref_country_name
                            airport_changed = True
                    if ref_country_code and (
                        not only_missing or not _clean_text(destination_airport.country_code, upper=True, limit=8)
                    ):
                        if _clean_text(destination_airport.country_code, upper=True, limit=8) != ref_country_code:
                            destination_airport.country_code = ref_country_code
                            airport_changed = True
                    if ref_lat is not None and (
                        not only_missing or _safe_float(destination_airport.latitude) is None
                    ):
                        if _safe_float(destination_airport.latitude) != ref_lat:
                            destination_airport.latitude = ref_lat
                            airport_changed = True
                    if ref_lng is not None and (
                        not only_missing or _safe_float(destination_airport.longitude) is None
                    ):
                        if _safe_float(destination_airport.longitude) != ref_lng:
                            destination_airport.longitude = ref_lng
                            airport_changed = True
                    if _country_is_cuba(destination_airport.country_name, destination_airport.country_code) and not destination_airport.is_cuba:
                        destination_airport.is_cuba = True
                        airport_changed = True

                    if airport_changed:
                        airports_updated += 1
                        changed = True

                if changed:
                    events_updated += 1
                    _mark_dirty(True)
                    _maybe_commit()

        if dry_run:
            db.session.rollback()
        else:
            db.session.commit()

        return {
            "status": "success",
            "dry_run": bool(dry_run),
            "only_missing": bool(only_missing),
            "catalog_rows": len(static_index),
            "airports_scanned": airports_scanned,
            "airports_updated": airports_updated,
            "events_scanned": events_scanned,
            "events_updated": events_updated,
            "origin_code_inferred": origin_code_inferred,
            "destination_code_inferred": destination_code_inferred,
            "destination_linked": destination_linked,
        }
    except Exception:
        db.session.rollback()
        raise


def build_event_track_payload(event: FlightEvent) -> dict[str, Any]:
    point_limit = get_flights_track_point_limit()
    rows = (
        FlightPosition.query.filter_by(event_id=event.id)
        .order_by(FlightPosition.observed_at_utc.asc(), FlightPosition.id.asc())
        .limit(point_limit)
        .all()
    )

    points = [
        {
            "id": row.id,
            "observed_at_utc": serialize_flight_time(row.observed_at_utc),
            "latitude": _safe_float(row.latitude),
            "longitude": _safe_float(row.longitude),
            "altitude": _safe_float(row.altitude),
            "speed": _safe_float(row.speed),
            "heading": _safe_float(row.heading),
            "source_kind": row.source_kind,
        }
        for row in rows
    ]

    if not points and event.latest_latitude is not None and event.latest_longitude is not None:
        points.append(
            {
                "id": None,
                "observed_at_utc": serialize_flight_time(event.last_seen_at_utc),
                "latitude": _safe_float(event.latest_latitude),
                "longitude": _safe_float(event.latest_longitude),
                "altitude": _safe_float(event.latest_altitude),
                "speed": _safe_float(event.latest_speed),
                "heading": _safe_float(event.latest_heading),
                "source_kind": event.last_source_kind or "live",
            }
        )

    origin_ref = _find_airport_point(
        event.origin_airport_icao,
        event.origin_airport_iata,
    )
    destination_ref = _find_airport_point(
        event.destination_airport_icao,
        event.destination_airport_iata,
    )
    origin_lat = _safe_float(origin_ref.get("latitude"))
    origin_lng = _safe_float(origin_ref.get("longitude"))
    destination_lat = _safe_float(event.destination_airport.latitude) if event.destination_airport else None
    destination_lng = _safe_float(event.destination_airport.longitude) if event.destination_airport else None
    if destination_lat is None:
        destination_lat = _safe_float(destination_ref.get("latitude"))
    if destination_lng is None:
        destination_lng = _safe_float(destination_ref.get("longitude"))

    origin_name = (
        _clean_text(event.origin_airport_name, limit=255)
        or _clean_text(origin_ref.get("name"), limit=255)
        or "Origen N/D"
    )
    origin_city_name = _clean_text(origin_ref.get("city"), limit=120)
    origin_country_name = (
        _clean_text(event.origin_country, limit=120)
        or _clean_text(origin_ref.get("country"), limit=120)
    )
    destination_name = (
        _clean_text(event.destination_airport_name, limit=255)
        or (
            _clean_text(event.destination_airport.name, limit=255)
            if event.destination_airport
            else ""
        )
        or _clean_text(destination_ref.get("name"), limit=255)
        or "Aeropuerto Cuba"
    )
    destination_country_name = (
        _clean_text(event.destination_country, limit=120)
        or (
            _clean_text(event.destination_airport.country_name, limit=120)
            if event.destination_airport
            else ""
        )
        or _clean_text(destination_ref.get("country"), limit=120)
        or "Cuba"
    )
    destination_city_name = (
        _clean_text(event.destination_airport.city, limit=120)
        if event.destination_airport
        else _clean_text(destination_ref.get("city"), limit=120)
    )

    return {
        "event": {
            "id": event.id,
            "event_key": event.event_key,
            "external_flight_id": event.external_flight_id,
            "call_sign": event.call_sign,
            "model": event.model,
            "registration": event.registration,
            "status": event.status,
            "origin_airport_name": origin_name,
            "origin_country": origin_country_name,
            "destination_airport_name": destination_name,
            "destination_country": destination_country_name,
            "last_seen_at_utc": serialize_flight_time(event.last_seen_at_utc),
        },
        "track": {
            "point_count": len(points),
            "points": points,
        },
        "route": {
            "origin": {
                "airport_name": origin_name,
                "airport_icao": _clean_text(event.origin_airport_icao, upper=True, limit=8),
                "airport_iata": _clean_text(event.origin_airport_iata, upper=True, limit=8),
                "city": origin_city_name,
                "country": origin_country_name,
                "latitude": origin_lat,
                "longitude": origin_lng,
            },
            "destination": {
                "airport_name": destination_name,
                "airport_icao": _clean_text(event.destination_airport_icao, upper=True, limit=8),
                "airport_iata": _clean_text(event.destination_airport_iata, upper=True, limit=8),
                "city": destination_city_name,
                "country": destination_country_name,
                "latitude": destination_lat,
                "longitude": destination_lng,
            },
        },
    }
