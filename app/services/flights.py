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
from typing import Any

import requests
from flask import current_app, has_app_context
from sqlalchemy import func, or_
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models.flight_aircraft import FlightAircraft
from app.models.flight_airport import FlightAirport
from app.models.flight_event import FlightEvent
from app.models.flight_ingestion_run import FlightIngestionRun
from app.models.flight_layer_snapshot import FlightLayerSnapshot
from app.models.flight_position import FlightPosition


logger = logging.getLogger(__name__)


WINDOW_HOURS_SUPPORTED = (24, 6, 2)
_CLEAN_TOKEN_RE = re.compile(r"[^a-z0-9]+")


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


class RequestBudgetExhausted(RuntimeError):
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


def _extract_items(payload: Any, preferred_paths: tuple[str, ...]) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if not isinstance(payload, dict):
        return []

    for path in preferred_paths:
        candidate = _get_nested(payload, path)
        if isinstance(candidate, list):
            return [item for item in candidate if isinstance(item, dict)]

    fallback = _walk_for_list(payload)
    if not isinstance(fallback, list):
        return []
    return [item for item in fallback if isinstance(item, dict)]


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


def get_flights_backfill_on_empty_db() -> bool:
    return _safe_bool(_config_value("FLIGHTS_BACKFILL_ON_EMPTY_DB", True), True)


def get_flights_safe_mode_skip_backfill() -> bool:
    return _safe_bool(_config_value("FLIGHTS_SAFE_MODE_SKIP_BACKFILL", True), True)


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
        _config_value("FLIGHTS_API_AIRPORTS_LIGHT_PATH", "/static/airports/light")
        or "/static/airports/light"
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


def get_flights_tracks_path() -> str:
    return str(_config_value("FLIGHTS_API_TRACKS_PATH", "/flights/tracks") or "/flights/tracks").strip()


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
    if request_ctx.request_count >= request_ctx.request_cap:
        request_ctx.budget_exhausted = True
        raise RequestBudgetExhausted("FLIGHTS request cap reached for this run")

    api_key = get_flights_api_key()
    if not api_key:
        raise RuntimeError("FLIGHTS_API_KEY no configurada")

    url = _build_api_url(path)
    if not url:
        raise RuntimeError("FLIGHTS_API_BASE_URL no configurada")

    _apply_rate_limit(request_ctx)

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

    response = requests.get(
        url,
        params=params,
        headers=headers,
        timeout=get_flights_api_timeout_seconds(),
    )
    request_ctx.request_count += 1
    request_ctx.estimated_credits += get_flights_credit_per_request()

    if not response.ok:
        snippet = (response.text or "").strip()
        if len(snippet) > 240:
            snippet = snippet[:237] + "..."
        raise RuntimeError(f"HTTP {response.status_code} from flights API: {snippet or 'sin detalle'}")

    try:
        return response.json()
    except Exception as exc:
        raise RuntimeError(f"Respuesta no JSON desde flights API: {exc}") from exc


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
    codes: set[str] = set()
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


def _parse_event_row(item: dict[str, Any], known_cuba_codes: set[str], source_kind: str) -> dict[str, Any] | None:
    external_flight_id = _clean_text(
        _pick(
            item,
            "flight_id",
            "id",
            "fr24_id",
            "identifier",
        ),
        limit=128,
    )

    call_sign = _clean_text(_pick(item, "callsign", "call_sign", "identification.callsign"), limit=64)
    model = _clean_text(
        _pick(
            item,
            "model",
            "aircraft.model",
            "aircraft_model",
            "aircraft.type",
        ),
        limit=120,
    )
    registration = _clean_text(
        _pick(item, "registration", "aircraft.registration", "tail_number"),
        limit=64,
    )

    origin_icao = _clean_text(
        _pick(
            item,
            "origin.icao",
            "origin_airport_icao",
            "departure.airport.icao",
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
    altitude = _safe_float(_pick(item, "altitude", "position.altitude", "position.alt"))
    speed = _safe_float(_pick(item, "speed", "ground_speed", "position.speed", "position.gs"))
    heading = _safe_float(_pick(item, "heading", "course", "position.heading", "position.track"))
    status = _clean_text(_pick(item, "status", "state", "flight_status"), limit=64)

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
        except Exception as exc:
            batch.errors.append(str(exc))
            break

        rows = _extract_items(payload, preferred_paths)
        if not rows:
            break

        for row in rows:
            batch.seen += 1
            parsed = _parse_event_row(row, known_cuba_codes, source_kind)
            if parsed is None:
                continue
            batch.records.append(parsed)

        if len(rows) < limit:
            break

    return batch


def _sync_cuba_airports(request_ctx: RequestContext) -> tuple[int, list[str], bool]:
    stored = 0
    errors: list[str] = []
    budget_exhausted = False
    limit = get_flights_response_limit()
    max_pages = get_flights_airports_max_pages()

    airport_cache: dict[str, FlightAirport] = {}

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
    days: int,
) -> FetchBatch:
    batch = FetchBatch()
    if days <= 0:
        return batch

    now_utc = _utc_now_naive()
    start_utc = now_utc - timedelta(days=days)
    cursor = start_utc
    chunk_hours = get_flights_backfill_chunk_hours()
    max_pages = get_flights_events_max_pages()

    while cursor < now_utc:
        chunk_end = min(cursor + timedelta(hours=chunk_hours), now_utc)
        params = {
            "destination_country": "CU",
            "from": serialize_flight_time(cursor),
            "to": serialize_flight_time(chunk_end),
            "light": 1,
        }
        chunk = _query_events_from_endpoint(
            get_flights_historic_events_light_path(),
            params,
            ("events", "data.events", "data.items", "items", "results", "data"),
            known_cuba_codes,
            "historic",
            request_ctx,
            max_pages=max_pages,
        )
        batch.records.extend(chunk.records)
        batch.seen += chunk.seen
        batch.errors.extend(chunk.errors)
        if chunk.budget_exhausted:
            batch.budget_exhausted = True
            break
        cursor = chunk_end

    return batch


def _collect_live_records(
    request_ctx: RequestContext,
    known_cuba_codes: set[str],
    safe_mode: bool,
) -> FetchBatch:
    max_pages = get_flights_safe_mode_events_max_pages() if safe_mode else get_flights_events_max_pages()
    params = {
        "destination_country": "CU",
        "light": 1,
    }
    return _query_events_from_endpoint(
        get_flights_live_positions_light_path(),
        params,
        ("positions", "flights", "data.positions", "data.flights", "data.items", "items", "data"),
        known_cuba_codes,
        "live",
        request_ctx,
        max_pages=max_pages,
    )


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

    for row in rows:
        lat = _safe_float(row.latest_latitude)
        lng = _safe_float(row.latest_longitude)
        if lat is None or lng is None:
            continue

        aircraft = row.aircraft
        destination_name = (
            (row.destination_airport.name if row.destination_airport else "")
            or row.destination_airport_name
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
                "origin_country": row.origin_country,
                "destination_airport_name": destination_name,
                "destination_airport_icao": row.destination_airport_icao,
                "destination_airport_iata": row.destination_airport_iata,
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

    if not get_flights_api_key():
        return {
            "status": "skipped",
            "reason": "missing_flights_api_key",
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

    try:
        if _needs_airport_sync(now_utc, safe_mode):
            synced, airport_errors, airports_budget_exhausted = _sync_cuba_airports(request_ctx)
            airports_synced = synced
            errors.extend(airport_errors)
            if airports_budget_exhausted:
                request_ctx.budget_exhausted = True

        known_codes = _known_cuba_airport_codes()

        has_events = db.session.query(FlightEvent.id).limit(1).first() is not None
        do_backfill = bool(force_backfill)
        if not do_backfill and get_flights_backfill_on_empty_db() and not has_events:
            do_backfill = True

        all_records: list[dict[str, Any]] = []

        if do_backfill and get_flights_backfill_days() > 0:
            run.is_backfill = True
            run.backfill_days = get_flights_backfill_days()
            if not (safe_mode and get_flights_safe_mode_skip_backfill()):
                backfill_batch = _collect_backfill_records(
                    request_ctx,
                    known_codes,
                    days=get_flights_backfill_days(),
                )
                all_records.extend(backfill_batch.records)
                events_seen += backfill_batch.seen
                errors.extend(backfill_batch.errors)
                if backfill_batch.budget_exhausted:
                    request_ctx.budget_exhausted = True

        live_batch = _collect_live_records(request_ctx, known_codes, safe_mode=safe_mode)
        all_records.extend(live_batch.records)
        events_seen += live_batch.seen
        errors.extend(live_batch.errors)
        if live_batch.budget_exhausted:
            request_ctx.budget_exhausted = True

        if all_records:
            events_stored, positions_stored = _persist_records(all_records, run)

        snapshots = refresh_flight_layer_snapshots(ingestion_run=run, now_utc=_utc_now_naive())

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
            "warnings": errors,
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
            "budget_exhausted": bool(request_ctx.budget_exhausted),
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

    for event in event_rows:
        origin_name = _clean_text(event.origin_airport_name, limit=255) or "Origen no disponible"
        destination_name = (
            _clean_text(event.destination_airport_name, limit=255)
            or (event.destination_airport.name if event.destination_airport else "")
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
                "origin_country": event.origin_country,
                "destination_airport_name": destination_name,
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

    return {
        "event": {
            "id": event.id,
            "event_key": event.event_key,
            "external_flight_id": event.external_flight_id,
            "call_sign": event.call_sign,
            "model": event.model,
            "registration": event.registration,
            "status": event.status,
            "origin_airport_name": event.origin_airport_name,
            "destination_airport_name": event.destination_airport_name,
            "last_seen_at_utc": serialize_flight_time(event.last_seen_at_utc),
        },
        "track": {
            "point_count": len(points),
            "points": points,
        },
    }
