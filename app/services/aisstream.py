from __future__ import annotations

import asyncio
import json
import math
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from flask import current_app, has_app_context
from sqlalchemy import or_

from app.extensions import db
from app.models.ais_cuba_target_vessel import AISCubaTargetVessel
from app.models.ais_ingestion_run import AISIngestionRun


POSITION_MESSAGE_TYPES = {
    "PositionReport",
    "StandardClassBPositionReport",
    "ExtendedClassBPositionReport",
    "LongRangeAisBroadcastMessage",
}
STATIC_MESSAGE_TYPES = {
    "ShipStaticData",
    "StaticDataReport",
}
AIS_MESSAGE_TYPES = sorted(POSITION_MESSAGE_TYPES | STATIC_MESSAGE_TYPES)


_CLEAN_RE = re.compile(r"[^A-Z0-9]+")


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
    normalized = normalized.replace(" UTC", "")
    normalized = normalized.replace("+0000", "+00:00")
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

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
    ]
    for pattern in patterns:
        try:
            parsed = datetime.strptime(text, pattern)
            return _normalize_utc_datetime(parsed)
        except Exception:
            continue
    return None


def normalize_destination_text(value: Any) -> str:
    text = str(value or "").strip().upper()
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    ascii_text = _CLEAN_RE.sub(" ", ascii_text)
    return " ".join(ascii_text.split())


def _normalize_mmsi(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    if text.endswith(".0"):
        text = text[:-2]
    try:
        numeric = int(float(text))
    except Exception:
        return ""
    if numeric <= 0:
        return ""
    return str(numeric)


CUBA_PORTS = [
    {
        "key": "cuhav",
        "name": "La Habana",
        "unlocode": "CUHAV",
        "lat": 23.1136,
        "lon": -82.3666,
        "aliases": [
            "CUHAV",
            "HAVANA",
            "HABANA",
            "LA HABANA",
            "HAV",
            "CUBA HAVANA",
            "HAVANA CUBA",
        ],
    },
    {
        "key": "cumar",
        "name": "Mariel",
        "unlocode": "CUMAR",
        "lat": 22.9952,
        "lon": -82.7534,
        "aliases": [
            "CUMAR",
            "MARIEL",
            "PORT MARIEL",
            "CUBA MARIEL",
            "MARIEL CUBA",
        ],
    },
    {
        "key": "cuqma",
        "name": "Matanzas",
        "unlocode": "CUQMA",
        "lat": 23.0494,
        "lon": -81.5775,
        "aliases": [
            "CUQMA",
            "MATANZAS",
            "MATANZAS BAY",
            "MTZ",
            "CUBA MATANZAS",
        ],
    },
    {
        "key": "cucfg",
        "name": "Cienfuegos",
        "unlocode": "CUCFG",
        "lat": 22.1429,
        "lon": -80.4568,
        "aliases": [
            "CUCFG",
            "CIENFUEGOS",
            "CF",
            "CIENFUEGOS CUBA",
        ],
    },
    {
        "key": "cuscu",
        "name": "Santiago de Cuba",
        "unlocode": "CUSCU",
        "lat": 19.9698,
        "lon": -75.8588,
        "aliases": [
            "CUSCU",
            "SANTIAGO",
            "SANTIAGO DE CUBA",
            "SCU",
            "SANTIAGO CUBA",
        ],
    },
    {
        "key": "cunvt",
        "name": "Nuevitas",
        "unlocode": "CUNVT",
        "lat": 21.5459,
        "lon": -77.2649,
        "aliases": [
            "CUNVT",
            "NUEVITAS",
            "NUEVITAS CUBA",
        ],
    },
    {
        "key": "cumoa",
        "name": "Moa",
        "unlocode": "CUMOA",
        "lat": 20.6569,
        "lon": -74.9418,
        "aliases": [
            "CUMOA",
            "MOA",
            "MOA CUBA",
        ],
    },
    {
        "key": "cugtn",
        "name": "Guantanamo",
        "unlocode": "CUGTN",
        "lat": 20.1386,
        "lon": -75.2092,
        "aliases": [
            "CUGTN",
            "GUANTANAMO",
            "GTMO",
            "GUANTANAMO BAY",
        ],
    },
    {
        "key": "cungr",
        "name": "Nueva Gerona",
        "unlocode": "CUNGR",
        "lat": 21.8866,
        "lon": -82.8045,
        "aliases": [
            "CUNGR",
            "NUEVA GERONA",
            "ISLA DE LA JUVENTUD",
        ],
    },
]


GENERIC_CUBA_ALIASES = [
    "CUBA",
    "CUB",
    "CU",
    "ANTILLA",
    "CARIBBEAN",
]


def _build_port_aliases() -> dict[str, dict[str, Any]]:
    payload: dict[str, dict[str, Any]] = {}
    for port in CUBA_PORTS:
        for alias in port.get("aliases") or []:
            normalized_alias = normalize_destination_text(alias)
            if not normalized_alias:
                continue
            payload[normalized_alias] = port
    return payload


PORT_ALIAS_MAP = _build_port_aliases()
SORTED_PORT_ALIASES = sorted(PORT_ALIAS_MAP.keys(), key=len, reverse=True)
GENERIC_ALIASES_NORMALIZED = {
    normalize_destination_text(alias)
    for alias in GENERIC_CUBA_ALIASES
    if normalize_destination_text(alias)
}


def get_ais_enabled() -> bool:
    return bool(_config_value("AISSTREAM_ENABLED", False))


def get_ais_api_key() -> str:
    return str(_config_value("AISSTREAM_API_KEY", "") or "").strip()


def get_ais_ws_url() -> str:
    return str(
        _config_value("AISSTREAM_WS_URL", "wss://stream.aisstream.io/v0/stream") or ""
    ).strip()


def get_ais_capture_minutes() -> int:
    return max(_safe_int(_config_value("AISSTREAM_CAPTURE_MINUTES", 30), 30), 1)


def get_ais_max_messages_per_run() -> int:
    return max(_safe_int(_config_value("AISSTREAM_MAX_MESSAGES_PER_RUN", 120000), 120000), 1000)


def get_ais_ingestion_interval_seconds() -> int:
    raw = _safe_int(_config_value("AISSTREAM_INGESTION_INTERVAL_SECONDS", 86400), 86400)
    return max(raw, 3600)


def get_ais_frontend_refresh_seconds() -> int:
    raw = _safe_int(_config_value("AISSTREAM_FRONTEND_REFRESH_SECONDS", 1800), 1800)
    return max(raw, 60)


def get_ais_stale_after_hours() -> int:
    raw = _safe_int(_config_value("AISSTREAM_STALE_AFTER_HOURS", 48), 48)
    return max(raw, 1)


def get_ais_vessel_stale_hours() -> int:
    raw = _safe_int(_config_value("AISSTREAM_VESSEL_STALE_HOURS", 168), 168)
    return max(raw, 24)


def get_ais_max_target_vessels() -> int:
    raw = _safe_int(_config_value("AISSTREAM_MAX_TARGET_VESSELS", 1500), 1500)
    return max(raw, 50)


def get_min_sog_for_direction_knots() -> float:
    raw = _safe_float(_config_value("AISSTREAM_MIN_SOG_FOR_DIRECTION_KNOTS", 1.0), 1.0)
    return max(raw or 1.0, 0.0)


def get_max_direction_delta_deg() -> float:
    raw = _safe_float(_config_value("AISSTREAM_MAX_DIRECTION_DELTA_DEG", 70.0), 70.0)
    return max(raw or 70.0, 1.0)


def get_max_direction_distance_nm() -> float:
    raw = _safe_float(_config_value("AISSTREAM_MAX_DIRECTION_DISTANCE_NM", 1200.0), 1200.0)
    return max(raw or 1200.0, 10.0)


def get_ais_subscription_bounding_boxes() -> list[list[list[float]]]:
    raw = str(
        _config_value(
            "AISSTREAM_SUBSCRIPTION_BBOXES_JSON",
            "[[[17.5, -88.5], [25.8, -73.0]]]",
        )
        or ""
    ).strip()
    if not raw:
        return [[[17.5, -88.5], [25.8, -73.0]]]

    try:
        payload = json.loads(raw)
    except Exception:
        return [[[17.5, -88.5], [25.8, -73.0]]]

    valid_boxes: list[list[list[float]]] = []
    if not isinstance(payload, list):
        return [[[17.5, -88.5], [25.8, -73.0]]]

    for box in payload:
        if not isinstance(box, list) or len(box) != 2:
            continue
        p1, p2 = box[0], box[1]
        if not isinstance(p1, (list, tuple)) or not isinstance(p2, (list, tuple)):
            continue
        if len(p1) < 2 or len(p2) < 2:
            continue
        lat1 = _safe_float(p1[0])
        lon1 = _safe_float(p1[1])
        lat2 = _safe_float(p2[0])
        lon2 = _safe_float(p2[1])
        if None in {lat1, lon1, lat2, lon2}:
            continue
        valid_boxes.append([[float(lat1), float(lon1)], [float(lat2), float(lon2)]])

    return valid_boxes or [[[17.5, -88.5], [25.8, -73.0]]]


def _angle_delta_deg(a_deg: float, b_deg: float) -> float:
    diff = abs((a_deg - b_deg + 180.0) % 360.0 - 180.0)
    return float(diff)


def _bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_lon = math.radians(lon2 - lon1)
    x = math.sin(delta_lon) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(delta_lon)
    if x == 0 and y == 0:
        return 0.0
    bearing = (math.degrees(math.atan2(x, y)) + 360.0) % 360.0
    return float(bearing)


def _distance_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0088
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(1.0 - a, 0.0)))
    km = radius_km * c
    return float(km * 0.539956803)


def _contains_alias_phrase(text: str, alias: str) -> bool:
    return f" {alias} " in f" {text} "


def _best_directional_port(lat: float, lon: float, cog: float):
    best_port = None
    best_delta = None
    best_distance = None
    for port in CUBA_PORTS:
        bearing = _bearing_deg(lat, lon, port["lat"], port["lon"])
        delta = _angle_delta_deg(cog, bearing)
        distance_nm = _distance_nm(lat, lon, port["lat"], port["lon"])
        if (
            best_port is None
            or delta < (best_delta or 9999)
            or (abs(delta - (best_delta or 9999)) < 1e-9 and distance_nm < (best_distance or 999999))
        ):
            best_port = port
            best_delta = delta
            best_distance = distance_nm
    if best_port is None:
        return None
    return {
        "port": best_port,
        "delta_deg": float(best_delta or 0.0),
        "distance_nm": float(best_distance or 0.0),
    }


def _directional_port_match(
    latitude: float | None,
    longitude: float | None,
    cog: float | None,
    sog: float | None,
):
    if latitude is None or longitude is None or cog is None or sog is None:
        return None
    if sog < get_min_sog_for_direction_knots():
        return None

    directional = _best_directional_port(latitude, longitude, cog)
    if not directional:
        return None

    max_delta = get_max_direction_delta_deg()
    max_distance = get_max_direction_distance_nm()
    if directional["delta_deg"] > max_delta:
        return None
    if directional["distance_nm"] > max_distance:
        return None

    confidence = 0.45
    confidence += max(0.0, (max_delta - directional["delta_deg"]) / max_delta) * 0.3
    confidence += max(0.0, (max_distance - directional["distance_nm"]) / max_distance) * 0.15
    confidence = min(max(confidence, 0.45), 0.9)
    directional["confidence"] = confidence
    return directional


def match_destination_to_cuba_ports(
    destination: Any,
    latitude: float | None = None,
    longitude: float | None = None,
    cog: float | None = None,
    sog: float | None = None,
) -> dict[str, Any]:
    destination_raw = str(destination or "").strip()
    destination_normalized = normalize_destination_text(destination_raw)
    payload: dict[str, Any] = {
        "destination_raw": destination_raw,
        "destination_normalized": destination_normalized,
        "is_match": False,
        "port_key": None,
        "port_name": None,
        "confidence": 0.0,
        "reason": "empty_destination",
    }

    if not destination_normalized:
        return payload

    payload["reason"] = "destination_not_matched"

    exact_port = PORT_ALIAS_MAP.get(destination_normalized)
    if exact_port:
        payload.update(
            {
                "is_match": True,
                "port_key": exact_port["key"],
                "port_name": exact_port["name"],
                "confidence": 0.92,
                "reason": "port_alias_exact",
            }
        )
        directional = _directional_port_match(latitude, longitude, cog, sog)
        if directional and directional["port"]["key"] == exact_port["key"]:
            payload["confidence"] = min(1.0, payload["confidence"] + 0.06)
            payload["reason"] = "port_alias_exact_directional"
        return payload

    for alias in SORTED_PORT_ALIASES:
        if len(alias) < 3:
            continue
        if not _contains_alias_phrase(destination_normalized, alias):
            continue
        matched_port = PORT_ALIAS_MAP.get(alias)
        if not matched_port:
            continue
        payload.update(
            {
                "is_match": True,
                "port_key": matched_port["key"],
                "port_name": matched_port["name"],
                "confidence": 0.84,
                "reason": "port_alias_contains",
            }
        )
        directional = _directional_port_match(latitude, longitude, cog, sog)
        if directional and directional["port"]["key"] == matched_port["key"]:
            payload["confidence"] = min(0.98, payload["confidence"] + 0.08)
            payload["reason"] = "port_alias_contains_directional"
        return payload

    generic_hits = [
        alias for alias in GENERIC_ALIASES_NORMALIZED if _contains_alias_phrase(destination_normalized, alias)
    ]
    if generic_hits:
        directional = _directional_port_match(latitude, longitude, cog, sog)
        if directional:
            matched_port = directional["port"]
            payload.update(
                {
                    "is_match": True,
                    "port_key": matched_port["key"],
                    "port_name": matched_port["name"],
                    "confidence": directional["confidence"],
                    "reason": "generic_cuba_directional",
                }
            )
            return payload

        payload.update(
            {
                "is_match": False,
                "confidence": 0.0,
                "reason": "generic_cuba_without_direction",
            }
        )
        return payload

    return payload


@dataclass
class VesselState:
    mmsi: str
    ship_name: str = ""
    imo: str = ""
    call_sign: str = ""
    vessel_type: str = ""
    destination_raw: str = ""
    destination_normalized: str = ""
    matched_port_key: str | None = None
    matched_port_name: str | None = None
    match_confidence: float = 0.0
    match_reason: str = ""
    latitude: float | None = None
    longitude: float | None = None
    sog: float | None = None
    cog: float | None = None
    heading: float | None = None
    navigational_status: str | None = None
    source_message_type: str = ""
    last_seen_at_utc: datetime | None = None
    last_position_at_utc: datetime | None = None
    last_static_at_utc: datetime | None = None
    touched_in_run: bool = False

    @property
    def is_mappable_match(self) -> bool:
        return (
            self.match_confidence > 0
            and self.latitude is not None
            and self.longitude is not None
            and math.isfinite(self.latitude)
            and math.isfinite(self.longitude)
        )


def _load_state_cache() -> dict[str, VesselState]:
    cache: dict[str, VesselState] = {}
    rows = AISCubaTargetVessel.query.all()
    for row in rows:
        mmsi = _normalize_mmsi(row.mmsi)
        if not mmsi:
            continue
        cache[mmsi] = VesselState(
            mmsi=mmsi,
            ship_name=str(row.ship_name or "").strip(),
            imo=str(row.imo or "").strip(),
            call_sign=str(row.call_sign or "").strip(),
            vessel_type=str(row.vessel_type or "").strip(),
            destination_raw=str(row.destination_raw or "").strip(),
            destination_normalized=str(row.destination_normalized or "").strip(),
            matched_port_key=str(row.matched_port_key or "").strip() or None,
            matched_port_name=str(row.matched_port_name or "").strip() or None,
            match_confidence=float(row.match_confidence or 0.0),
            match_reason=str(row.match_reason or "").strip(),
            latitude=_safe_float(row.latitude),
            longitude=_safe_float(row.longitude),
            sog=_safe_float(row.sog),
            cog=_safe_float(row.cog),
            heading=_safe_float(row.heading),
            navigational_status=str(row.navigational_status or "").strip() or None,
            source_message_type=str(row.source_message_type or "").strip(),
            last_seen_at_utc=_normalize_utc_datetime(row.last_seen_at_utc),
            last_position_at_utc=_normalize_utc_datetime(row.last_position_at_utc),
            last_static_at_utc=_normalize_utc_datetime(row.last_static_at_utc),
        )
    return cache


def _resolve_message_payload(message_obj: dict[str, Any], message_type: str) -> dict[str, Any]:
    container = message_obj.get("Message")
    if isinstance(container, dict):
        payload = container.get(message_type)
        if isinstance(payload, dict):
            return payload
        if len(container) == 1:
            only_value = next(iter(container.values()))
            if isinstance(only_value, dict):
                return only_value
    return {}


def _resolve_metadata(message_obj: dict[str, Any]) -> dict[str, Any]:
    metadata = message_obj.get("MetaData")
    if isinstance(metadata, dict):
        return metadata
    metadata = message_obj.get("Metadata")
    if isinstance(metadata, dict):
        return metadata
    return {}


def _extract_static_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}

    part_a = payload.get("PartA")
    if not isinstance(part_a, dict):
        part_a = payload.get("ReportA") if isinstance(payload.get("ReportA"), dict) else {}

    part_b = payload.get("PartB")
    if not isinstance(part_b, dict):
        part_b = payload.get("ReportB") if isinstance(payload.get("ReportB"), dict) else {}

    destination = str(
        payload.get("Destination")
        or part_b.get("Destination")
        or ""
    ).strip()

    ship_name = str(
        payload.get("Name")
        or part_a.get("Name")
        or part_b.get("Name")
        or ""
    ).strip()

    call_sign = str(payload.get("CallSign") or part_b.get("CallSign") or "").strip()
    imo = str(payload.get("IMO") or part_b.get("IMO") or "").strip()
    vessel_type = payload.get("Type")
    if vessel_type is None:
        vessel_type = part_b.get("Type")
    vessel_type_text = str(vessel_type or "").strip()

    return {
        "destination": destination,
        "ship_name": ship_name,
        "call_sign": call_sign,
        "imo": imo,
        "vessel_type": vessel_type_text,
    }


def _apply_destination_match(state: VesselState) -> None:
    if not state.destination_raw:
        return
    match = match_destination_to_cuba_ports(
        state.destination_raw,
        latitude=state.latitude,
        longitude=state.longitude,
        cog=state.cog,
        sog=state.sog,
    )
    state.destination_normalized = match.get("destination_normalized") or ""
    if match.get("is_match"):
        state.matched_port_key = match.get("port_key")
        state.matched_port_name = match.get("port_name")
        state.match_confidence = float(match.get("confidence") or 0.0)
        state.match_reason = str(match.get("reason") or "")
        return
    state.matched_port_key = None
    state.matched_port_name = None
    state.match_confidence = 0.0
    state.match_reason = str(match.get("reason") or "")


def _apply_position_fields(
    state: VesselState,
    payload: dict[str, Any],
    metadata: dict[str, Any],
    observed_at: datetime,
) -> None:
    lat = _safe_float(payload.get("Latitude"))
    if lat is None:
        lat = _safe_float(metadata.get("Latitude"))
    if lat is None:
        lat = _safe_float(metadata.get("latitude"))

    lon = _safe_float(payload.get("Longitude"))
    if lon is None:
        lon = _safe_float(metadata.get("Longitude"))
    if lon is None:
        lon = _safe_float(metadata.get("longitude"))

    if lat is not None:
        state.latitude = lat
    if lon is not None:
        state.longitude = lon

    sog = _safe_float(payload.get("Sog"))
    if sog is None:
        sog = _safe_float(payload.get("SOG"))
    if sog is not None:
        state.sog = sog

    cog = _safe_float(payload.get("Cog"))
    if cog is None:
        cog = _safe_float(payload.get("COG"))
    if cog is not None:
        state.cog = cog % 360.0

    heading = _safe_float(payload.get("TrueHeading"))
    if heading is not None:
        state.heading = heading % 360.0

    nav_status = payload.get("NavigationalStatus")
    if nav_status is not None:
        state.navigational_status = str(nav_status)

    state.last_position_at_utc = observed_at


def _apply_static_fields(
    state: VesselState,
    payload: dict[str, Any],
    metadata: dict[str, Any],
    observed_at: datetime,
) -> None:
    static_payload = _extract_static_payload(payload)

    ship_name = static_payload.get("ship_name") or metadata.get("ShipName") or metadata.get("ship_name")
    if ship_name:
        state.ship_name = str(ship_name).strip()

    call_sign = static_payload.get("call_sign")
    if call_sign:
        state.call_sign = str(call_sign).strip()

    imo = static_payload.get("imo")
    if imo:
        state.imo = str(imo).strip()

    vessel_type = static_payload.get("vessel_type")
    if vessel_type:
        state.vessel_type = str(vessel_type).strip()

    destination = str(static_payload.get("destination") or "").strip()
    if destination:
        state.destination_raw = destination

    state.last_static_at_utc = observed_at


def _update_state_from_message(
    state_cache: dict[str, VesselState],
    message_obj: dict[str, Any],
    counters: dict[str, int],
) -> None:
    if not isinstance(message_obj, dict):
        counters["parse_errors"] += 1
        return

    message_type = str(message_obj.get("MessageType") or "").strip()
    if not message_type:
        counters["parse_errors"] += 1
        return

    if message_type not in POSITION_MESSAGE_TYPES and message_type not in STATIC_MESSAGE_TYPES:
        return

    payload = _resolve_message_payload(message_obj, message_type)
    metadata = _resolve_metadata(message_obj)

    mmsi = _normalize_mmsi(
        metadata.get("MMSI")
        or payload.get("UserID")
        or payload.get("MMSI")
    )
    if not mmsi:
        counters["parse_errors"] += 1
        return

    observed_at = _parse_datetime(
        metadata.get("time_utc")
        or metadata.get("Time_UTC")
        or metadata.get("timestamp_utc")
        or metadata.get("TimestampUTC")
        or metadata.get("received_at")
    ) or _utc_now_naive()

    state = state_cache.get(mmsi)
    if state is None:
        state = VesselState(mmsi=mmsi)
        state_cache[mmsi] = state

    ship_name = metadata.get("ShipName") or metadata.get("ship_name")
    if ship_name:
        state.ship_name = str(ship_name).strip()

    if message_type in POSITION_MESSAGE_TYPES:
        counters["position_messages"] += 1
        _apply_position_fields(state, payload, metadata, observed_at)
    elif message_type in STATIC_MESSAGE_TYPES:
        counters["static_messages"] += 1
        _apply_static_fields(state, payload, metadata, observed_at)

    if state.destination_raw:
        _apply_destination_match(state)

    if state.is_mappable_match:
        counters["matched_messages"] += 1

    state.last_seen_at_utc = observed_at
    state.source_message_type = message_type
    state.touched_in_run = True


def _upsert_target_vessel(state: VesselState, ingestion_run_id: int) -> None:
    row = AISCubaTargetVessel.query.filter_by(mmsi=state.mmsi).first()
    if row is None:
        row = AISCubaTargetVessel(mmsi=state.mmsi)
        db.session.add(row)

    row.ship_name = state.ship_name or None
    row.imo = state.imo or None
    row.call_sign = state.call_sign or None
    row.vessel_type = state.vessel_type or None

    row.destination_raw = state.destination_raw or None
    row.destination_normalized = state.destination_normalized or None
    row.matched_port_key = state.matched_port_key
    row.matched_port_name = state.matched_port_name
    row.match_confidence = float(state.match_confidence or 0.0)
    row.match_reason = state.match_reason or None

    row.latitude = _safe_float(state.latitude)
    row.longitude = _safe_float(state.longitude)
    row.sog = _safe_float(state.sog)
    row.cog = _safe_float(state.cog)
    row.heading = _safe_float(state.heading)
    row.navigational_status = state.navigational_status
    row.source_message_type = state.source_message_type or None

    row.last_seen_at_utc = state.last_seen_at_utc
    row.last_position_at_utc = state.last_position_at_utc
    row.last_static_at_utc = state.last_static_at_utc
    row.ingestion_run_id = ingestion_run_id


async def _consume_ais_stream(
    state_cache: dict[str, VesselState],
    counters: dict[str, int],
) -> None:
    try:
        import websockets
    except Exception as exc:
        raise RuntimeError("Dependencia faltante: websockets") from exc

    api_key = get_ais_api_key()
    if not api_key:
        raise RuntimeError("AISSTREAM_API_KEY no configurada")

    ws_url = get_ais_ws_url()
    if not ws_url:
        raise RuntimeError("AISSTREAM_WS_URL no configurada")

    capture_minutes = get_ais_capture_minutes()
    max_seconds = max(10, capture_minutes * 60)
    max_messages = get_ais_max_messages_per_run()
    deadline = asyncio.get_running_loop().time() + max_seconds

    subscription_message = {
        "APIKey": api_key,
        "BoundingBoxes": get_ais_subscription_bounding_boxes(),
        "FilterMessageTypes": AIS_MESSAGE_TYPES,
    }

    async with websockets.connect(ws_url, ping_interval=20, ping_timeout=20, close_timeout=6) as websocket:
        await websocket.send(json.dumps(subscription_message))

        while asyncio.get_running_loop().time() < deadline:
            if counters["total_messages"] >= max_messages:
                break
            timeout_seconds = min(5.0, max(0.2, deadline - asyncio.get_running_loop().time()))
            try:
                raw_message = await asyncio.wait_for(websocket.recv(), timeout=timeout_seconds)
            except asyncio.TimeoutError:
                continue

            counters["total_messages"] += 1

            try:
                message_obj = json.loads(raw_message)
            except Exception:
                counters["parse_errors"] += 1
                continue

            if isinstance(message_obj, dict) and message_obj.get("error"):
                raise RuntimeError(f"AISStream error: {message_obj.get('error')}")

            _update_state_from_message(state_cache, message_obj, counters)


def _run_ingestion_sync(
    state_cache: dict[str, VesselState],
    counters: dict[str, int],
) -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        raise RuntimeError("No se puede ejecutar AIS ingestion dentro de un event loop activo")
    asyncio.run(_consume_ais_stream(state_cache, counters))


def _finalize_run_success(run_id: int, counters: dict[str, int], summary_payload: dict[str, Any]) -> None:
    run = db.session.get(AISIngestionRun, run_id)
    if not run:
        return
    run.finished_at_utc = _utc_now_naive()
    run.status = "success"
    run.total_messages = int(counters.get("total_messages") or 0)
    run.position_messages = int(counters.get("position_messages") or 0)
    run.static_messages = int(counters.get("static_messages") or 0)
    run.matched_messages = int(counters.get("matched_messages") or 0)
    run.matched_vessels = int(counters.get("matched_vessels") or 0)
    run.stale_removed = int(counters.get("stale_removed") or 0)
    run.error_message = None
    run.payload_json = json.dumps(summary_payload, ensure_ascii=False)
    db.session.commit()


def _finalize_run_failure(run_id: int, counters: dict[str, int], error_message: str) -> None:
    run = db.session.get(AISIngestionRun, run_id)
    if not run:
        return
    run.finished_at_utc = _utc_now_naive()
    run.status = "failed"
    run.total_messages = int(counters.get("total_messages") or 0)
    run.position_messages = int(counters.get("position_messages") or 0)
    run.static_messages = int(counters.get("static_messages") or 0)
    run.matched_messages = int(counters.get("matched_messages") or 0)
    run.matched_vessels = int(counters.get("matched_vessels") or 0)
    run.stale_removed = int(counters.get("stale_removed") or 0)
    run.error_message = (error_message or "").strip()[:2000] or "Error desconocido"
    run.payload_json = json.dumps(
        {
            "status": "failed",
            "error": run.error_message,
            "totals": {
                "total_messages": run.total_messages,
                "position_messages": run.position_messages,
                "static_messages": run.static_messages,
                "matched_messages": run.matched_messages,
                "matched_vessels": run.matched_vessels,
            },
        },
        ensure_ascii=False,
    )
    db.session.commit()


def _prune_stale_vessels() -> int:
    cutoff = _utc_now_naive() - timedelta(hours=get_ais_vessel_stale_hours())
    deleted = (
        AISCubaTargetVessel.query.filter(
            or_(
                AISCubaTargetVessel.last_seen_at_utc.is_(None),
                AISCubaTargetVessel.last_seen_at_utc < cutoff,
            )
        )
        .delete(synchronize_session=False)
    )
    return int(deleted or 0)


def ingest_aisstream_cuba_targets(
    scheduled_for: datetime | None = None,
    raise_on_error: bool = True,
) -> dict[str, Any]:
    if not get_ais_enabled():
        return {
            "status": "skipped",
            "reason": "aisstream_disabled",
            "stored_vessels": int(AISCubaTargetVessel.query.count() or 0),
        }

    if not get_ais_api_key():
        return {
            "status": "skipped",
            "reason": "missing_api_key",
            "stored_vessels": int(AISCubaTargetVessel.query.count() or 0),
        }

    run = AISIngestionRun(
        scheduled_for_utc=_normalize_utc_datetime(scheduled_for),
        started_at_utc=_utc_now_naive(),
        status="running",
    )
    db.session.add(run)
    db.session.commit()

    run_id = int(run.id)
    counters = {
        "total_messages": 0,
        "position_messages": 0,
        "static_messages": 0,
        "matched_messages": 0,
        "matched_vessels": 0,
        "stale_removed": 0,
        "parse_errors": 0,
    }

    state_cache = _load_state_cache()

    try:
        _run_ingestion_sync(state_cache, counters)

        updated_vessels = 0
        cleared_non_matching = []
        matched_by_port: dict[str, int] = {}
        for state in state_cache.values():
            if not state.touched_in_run:
                continue

            if (state.match_confidence or 0) <= 0:
                cleared_non_matching.append(state.mmsi)
                continue

            if not state.is_mappable_match:
                # Conserva el último punto útil cuando hubo match de destino
                # pero en esta corrida no llegó posición válida.
                continue

            _upsert_target_vessel(state, run_id)
            updated_vessels += 1
            port_label = str(state.matched_port_name or "Sin puerto")
            matched_by_port[port_label] = matched_by_port.get(port_label, 0) + 1

        if cleared_non_matching:
            (
                AISCubaTargetVessel.query.filter(
                    AISCubaTargetVessel.mmsi.in_(cleared_non_matching)
                ).delete(synchronize_session=False)
            )

        counters["matched_vessels"] = updated_vessels
        counters["stale_removed"] = _prune_stale_vessels()

        db.session.commit()

        total_rows = int(AISCubaTargetVessel.query.count() or 0)
        summary_payload = {
            "status": "success",
            "run_id": run_id,
            "capture_minutes": get_ais_capture_minutes(),
            "total_messages": counters["total_messages"],
            "position_messages": counters["position_messages"],
            "static_messages": counters["static_messages"],
            "matched_messages": counters["matched_messages"],
            "matched_vessels": counters["matched_vessels"],
            "parse_errors": counters["parse_errors"],
            "stale_removed": counters["stale_removed"],
            "stored_vessels": total_rows,
            "matched_by_port": [
                {"port": port, "count": count}
                for port, count in sorted(
                    matched_by_port.items(),
                    key=lambda item: (-int(item[1]), str(item[0])),
                )
            ],
        }
        _finalize_run_success(run_id, counters, summary_payload)
        return summary_payload
    except Exception as exc:
        db.session.rollback()
        _finalize_run_failure(run_id, counters, str(exc))
        failure_payload = {
            "status": "failed",
            "run_id": run_id,
            "error": str(exc),
            "total_messages": counters["total_messages"],
            "position_messages": counters["position_messages"],
            "static_messages": counters["static_messages"],
            "matched_messages": counters["matched_messages"],
            "matched_vessels": counters["matched_vessels"],
            "parse_errors": counters["parse_errors"],
        }
        if raise_on_error:
            raise
        return failure_payload
