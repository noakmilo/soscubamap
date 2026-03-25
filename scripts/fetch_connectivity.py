import argparse
import json
import os
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests

from app import create_app
from app.extensions import db
from app.models.connectivity_ingestion_run import ConnectivityIngestionRun
from app.models.connectivity_province_status import ConnectivityProvinceStatus
from app.models.connectivity_snapshot import ConnectivitySnapshot
from app.services.connectivity import (
    compute_connectivity_score,
    extract_series_points,
    get_latest_common_point,
    get_latest_hourly_point,
    median_baseline,
    score_to_status,
    serialize_snapshot_time,
    to_float,
)
from app.services.cuba_locations import PROVINCES, PROVINCE_RADAR_GEOIDS
from app.services.geo_lookup import list_provinces
from app.services.location_names import canonicalize_province_name, normalize_location_key


def parse_args():
    parser = argparse.ArgumentParser(description="Ingesta de conectividad desde Cloudflare Radar")
    parser.add_argument(
        "--single-call",
        action="store_true",
        help="Realiza una sola llamada a Radar (sin segunda consulta con delay)",
    )
    parser.add_argument(
        "--scheduled-for",
        default="",
        help="Timestamp UTC programado para trazabilidad (ISO8601)",
    )
    return parser.parse_args()


def _parse_scheduled_for(raw):
    text = (raw or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except Exception:
        return None
    if dt.tzinfo:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _province_geoids():
    env_raw = (os.getenv("CF_RADAR_PROVINCE_GEOIDS_JSON") or "").strip()
    base = dict(PROVINCE_RADAR_GEOIDS)
    if not env_raw:
        return base

    try:
        payload = json.loads(env_raw)
    except Exception:
        return base
    if not isinstance(payload, dict):
        return base

    merged = dict(base)
    for raw_name, raw_id in payload.items():
        name = canonicalize_province_name(raw_name) or str(raw_name or "").strip()
        try:
            geo_id = int(str(raw_id).strip())
        except Exception:
            continue
        if name:
            merged[name] = geo_id
    return merged


def _url_with_geoid(base_url, geo_id):
    text = (base_url or "").strip()
    if not text:
        return text
    parsed = urlparse(text)
    query_pairs = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True) if key != "geoId"]
    query_pairs.append(("geoId", str(geo_id)))
    query_pairs.append(("geoId", str(geo_id)))
    new_query = urlencode(query_pairs, doseq=True)
    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            parsed.fragment,
        )
    )


def _utcnow():
    # Keep naive UTC datetimes for existing DB schema, without using deprecated utcnow().
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _truncate_text(value, limit=400):
    text = str(value or "").strip()
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return f"{text[: max(0, limit - 3)]}..."


def _format_cloudflare_entries(raw):
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw.strip()
    if isinstance(raw, dict):
        code = raw.get("code")
        message = (
            raw.get("message")
            or raw.get("error")
            or raw.get("description")
        )
        if code is not None and message:
            return f"{code}: {message}"
        if message:
            return str(message)
        return json.dumps(raw, ensure_ascii=False)
    if isinstance(raw, list):
        items = []
        for entry in raw[:5]:
            item_text = _format_cloudflare_entries(entry)
            if item_text:
                items.append(item_text)
        return " | ".join(items)
    return str(raw)


def _build_radar_error_message(payload, text, status_code):
    parts = []
    if isinstance(payload, dict):
        errors_text = _format_cloudflare_entries(payload.get("errors"))
        messages_text = _format_cloudflare_entries(payload.get("messages"))
        if errors_text:
            parts.append(f"errors={errors_text}")
        if messages_text:
            parts.append(f"messages={messages_text}")
    if parts:
        return _truncate_text("; ".join(parts), limit=500)
    if text:
        return _truncate_text(text, limit=500)
    if status_code is not None:
        return f"HTTP {status_code}"
    return "respuesta invalida"


def _fetch_once(url, token, timeout_seconds):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    started = _utcnow()
    try:
        response = requests.get(url, headers=headers, timeout=timeout_seconds)
        text = response.text or ""
        payload = None
        try:
            payload = response.json()
        except Exception:
            payload = None

        success_flag = True
        if isinstance(payload, dict) and "success" in payload:
            success_flag = bool(payload.get("success"))

        ok = response.ok and success_flag and isinstance(payload, dict)
        error_message = None
        if not ok:
            error_message = _build_radar_error_message(payload, text, response.status_code)

        return {
            "ok": ok,
            "status_code": response.status_code,
            "payload": payload,
            "error": error_message,
            "started_at": started,
            "finished_at": _utcnow(),
        }
    except Exception as exc:
        return {
            "ok": False,
            "status_code": None,
            "payload": None,
            "error": str(exc),
            "started_at": started,
            "finished_at": _utcnow(),
        }


def _pick_best_attempt(attempts):
    best = None
    for attempt in attempts:
        if not attempt.get("ok"):
            continue
        payload = attempt.get("payload")
        latest = get_latest_hourly_point(payload, "main")
        if not latest:
            continue
        candidate = {
            "attempt": attempt,
            "latest": latest,
        }
        if best is None or latest["timestamp"] > best["latest"]["timestamp"]:
            best = candidate
    return best


def _radar_base_url(value):
    text = str(value or "").strip().rstrip("/")
    if text:
        return text
    return "https://api.cloudflare.com/client/v4/radar"


def _radar_url(base_url, path, params=None):
    base = _radar_base_url(base_url)
    path_text = f"/{str(path or '').lstrip('/')}"
    query = urlencode(params or {}, doseq=True)
    if query:
        return f"{base}{path_text}?{query}"
    return f"{base}{path_text}"


def _fetch_radar_json(url, token, timeout_seconds):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    try:
        response = requests.get(url, headers=headers, timeout=timeout_seconds)
        payload = None
        try:
            payload = response.json()
        except Exception:
            payload = None

        success_flag = True
        if isinstance(payload, dict) and "success" in payload:
            success_flag = bool(payload.get("success"))

        ok = response.ok and success_flag and isinstance(payload, dict)
        error_message = None
        if not ok:
            error_message = _build_radar_error_message(
                payload,
                response.text or "",
                response.status_code,
            )

        return {
            "ok": ok,
            "status_code": response.status_code,
            "payload": payload if isinstance(payload, dict) else None,
            "error": error_message,
        }
    except Exception as exc:
        return {
            "ok": False,
            "status_code": None,
            "payload": None,
            "error": str(exc),
        }


def _to_percent(value):
    numeric = to_float(value)
    if numeric is None:
        return None
    if 0 <= numeric <= 1.000001:
        numeric *= 100.0
    if numeric < 0:
        numeric = 0.0
    if numeric > 100:
        numeric = 100.0
    return round(numeric, 3)


def _parse_radar_datetime(raw):
    text = str(raw or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except Exception:
        return None
    if parsed.tzinfo:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _speed_window_params(days=7, location=None):
    params = [("format", "json")]
    now_utc = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    def _iso_utc(dt):
        return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    for day_idx in range(max(1, int(days))):
        end_dt = now_utc - timedelta(days=day_idx)
        start_dt = end_dt - timedelta(days=1)
        params.append(("name", f"day{day_idx}"))
        params.append(("dateStart", _iso_utc(start_dt)))
        params.append(("dateEnd", _iso_utc(end_dt)))
        if location:
            params.append(("location", str(location)))
    return params


def _parse_speed_row(row):
    if not isinstance(row, dict):
        return {
            "download_mbps": None,
            "upload_mbps": None,
            "latency_ms": None,
            "jitter_ms": None,
            "packet_loss_pct": None,
        }
    return {
        "download_mbps": to_float(
            row.get("bandwidthDownload")
            or row.get("downloadMbps")
            or row.get("download")
        ),
        "upload_mbps": to_float(
            row.get("bandwidthUpload")
            or row.get("uploadMbps")
            or row.get("upload")
        ),
        "latency_ms": to_float(
            row.get("latencyIdle")
            or row.get("latencyLoaded")
            or row.get("latency")
        ),
        "jitter_ms": to_float(
            row.get("jitterIdle")
            or row.get("jitterLoaded")
            or row.get("jitter")
        ),
        "packet_loss_pct": to_float(
            row.get("packetLoss")
            or row.get("packetLossPct")
            or row.get("packet_loss")
        ),
    }


def _average(values):
    numeric = [to_float(value) for value in (values or [])]
    numeric = [value for value in numeric if value is not None]
    if not numeric:
        return None
    return sum(numeric) / len(numeric)


def _safe_round(value, decimals=3):
    numeric = to_float(value)
    if numeric is None:
        return None
    return round(numeric, decimals)


def _build_speed_summary(cuba_payload, world_payload, days=7):
    cuba_result = cuba_payload.get("result") if isinstance(cuba_payload, dict) else None
    world_result = world_payload.get("result") if isinstance(world_payload, dict) else None
    if not isinstance(cuba_result, dict):
        return {
            "available": False,
            "days": [],
            "latest": None,
            "averages_7d": {},
        }

    rows = []
    for day_idx in range(max(1, int(days))):
        key = f"day{day_idx}"
        cuba_row = _parse_speed_row(cuba_result.get(key))
        world_row = _parse_speed_row(world_result.get(key) if isinstance(world_result, dict) else None)

        if all(
            cuba_row.get(field) is None
            for field in ("download_mbps", "upload_mbps", "latency_ms", "jitter_ms", "packet_loss_pct")
        ):
            continue

        download_delta_pct = None
        if (
            cuba_row.get("download_mbps") is not None
            and world_row.get("download_mbps") is not None
            and world_row["download_mbps"] > 0
        ):
            download_delta_pct = (
                (cuba_row["download_mbps"] - world_row["download_mbps"])
                / world_row["download_mbps"]
            ) * 100.0

        latency_delta_pct = None
        if (
            cuba_row.get("latency_ms") is not None
            and world_row.get("latency_ms") is not None
            and world_row["latency_ms"] > 0
        ):
            latency_delta_pct = (
                (cuba_row["latency_ms"] - world_row["latency_ms"])
                / world_row["latency_ms"]
            ) * 100.0

        rows.append(
            {
                "day_index": day_idx,
                "download_mbps": _safe_round(cuba_row.get("download_mbps"), 3),
                "upload_mbps": _safe_round(cuba_row.get("upload_mbps"), 3),
                "latency_ms": _safe_round(cuba_row.get("latency_ms"), 2),
                "jitter_ms": _safe_round(cuba_row.get("jitter_ms"), 2),
                "packet_loss_pct": _safe_round(cuba_row.get("packet_loss_pct"), 3),
                "global_download_mbps": _safe_round(world_row.get("download_mbps"), 3),
                "global_upload_mbps": _safe_round(world_row.get("upload_mbps"), 3),
                "global_latency_ms": _safe_round(world_row.get("latency_ms"), 2),
                "global_jitter_ms": _safe_round(world_row.get("jitter_ms"), 2),
                "download_delta_pct": _safe_round(download_delta_pct, 2),
                "latency_delta_pct": _safe_round(latency_delta_pct, 2),
            }
        )

    rows.sort(key=lambda item: int(item.get("day_index") or 0))
    latest = rows[0] if rows else None
    averages = {
        "download_mbps": _safe_round(_average([row.get("download_mbps") for row in rows]), 3),
        "upload_mbps": _safe_round(_average([row.get("upload_mbps") for row in rows]), 3),
        "latency_ms": _safe_round(_average([row.get("latency_ms") for row in rows]), 2),
        "jitter_ms": _safe_round(_average([row.get("jitter_ms") for row in rows]), 2),
        "packet_loss_pct": _safe_round(_average([row.get("packet_loss_pct") for row in rows]), 3),
        "global_download_mbps": _safe_round(
            _average([row.get("global_download_mbps") for row in rows]),
            3,
        ),
        "global_latency_ms": _safe_round(
            _average([row.get("global_latency_ms") for row in rows]),
            2,
        ),
    }
    return {
        "available": bool(rows),
        "days": rows,
        "latest": latest,
        "averages_7d": averages,
    }


def _extract_annotation_alerts(payload):
    result = payload.get("result") if isinstance(payload, dict) else None
    annotations = result.get("annotations") if isinstance(result, dict) else None
    if not isinstance(annotations, list):
        return []

    alerts = []
    for item in annotations:
        if not isinstance(item, dict):
            continue
        event_type = str(item.get("eventType") or "").strip().upper()
        alert_type = "outage" if event_type == "OUTAGE" else "anomaly"
        start_date = str(item.get("startDate") or "").strip() or None
        end_date = str(item.get("endDate") or "").strip() or None
        outage = item.get("outage") if isinstance(item.get("outage"), dict) else {}
        locations = item.get("locations") if isinstance(item.get("locations"), list) else []
        asns = item.get("asns") if isinstance(item.get("asns"), list) else []
        alerts.append(
            {
                "source": "annotation",
                "alert_type": alert_type,
                "event_type": event_type or None,
                "description": str(item.get("description") or "").strip() or None,
                "start_date": start_date,
                "end_date": end_date,
                "linked_url": str(item.get("linkedUrl") or "").strip() or None,
                "outage_cause": str(outage.get("outageCause") or "").strip() or None,
                "outage_type": str(outage.get("outageType") or "").strip() or None,
                "data_source": str(item.get("dataSource") or "").strip() or None,
                "is_instantaneous": bool(item.get("isInstantaneous")),
                "locations": [str(loc).strip() for loc in locations if str(loc).strip()],
                "asns": [str(asn).strip() for asn in asns if str(asn).strip()],
            }
        )
    return alerts


def _extract_anomaly_alerts(payload):
    result = payload.get("result") if isinstance(payload, dict) else None
    anomalies = result.get("trafficAnomalies") if isinstance(result, dict) else None
    if not isinstance(anomalies, list):
        return []

    alerts = []
    for item in anomalies:
        if not isinstance(item, dict):
            continue
        asn_details = item.get("asnDetails") if isinstance(item.get("asnDetails"), dict) else {}
        alerts.append(
            {
                "source": "traffic_anomaly",
                "alert_type": "anomaly",
                "event_type": str(item.get("type") or "").strip() or None,
                "status": str(item.get("status") or "").strip() or None,
                "description": str(item.get("description") or "").strip() or None,
                "start_date": str(item.get("startDate") or "").strip() or None,
                "end_date": str(item.get("endDate") or "").strip() or None,
                "magnitude": _safe_round(to_float(item.get("magnitude")), 3),
                "asn": str(asn_details.get("asn") or "").strip() or None,
                "asn_name": str(asn_details.get("name") or "").strip() or None,
            }
        )
    return alerts


def _dedupe_and_sort_alerts(alerts):
    deduped = {}
    for item in alerts or []:
        if not isinstance(item, dict):
            continue
        key = (
            str(item.get("source") or "").strip().lower(),
            str(item.get("alert_type") or "").strip().lower(),
            str(item.get("event_type") or "").strip().lower(),
            str(item.get("start_date") or "").strip(),
        )
        existing = deduped.get(key)
        if existing is None:
            deduped[key] = item
            continue
        # Preserve richer records (description/outage fields).
        existing_richness = sum(
            1 for field in ("description", "outage_cause", "outage_type", "linked_url") if existing.get(field)
        )
        candidate_richness = sum(
            1 for field in ("description", "outage_cause", "outage_type", "linked_url") if item.get(field)
        )
        if candidate_richness > existing_richness:
            deduped[key] = item

    sorted_items = list(deduped.values())
    sorted_items.sort(
        key=lambda row: _parse_radar_datetime(row.get("start_date")) or datetime.min,
        reverse=True,
    )
    return sorted_items


def _fetch_radar_enrichment(base_url, token, timeout_seconds):
    output = {
        "fetched_at_utc": serialize_snapshot_time(_utcnow()),
        "api_base_url": _radar_base_url(base_url),
        "audience": {
            "available": False,
            "device_mobile_pct": None,
            "device_desktop_pct": None,
            "human_pct": None,
            "bot_pct": None,
        },
        "alerts": {
            "available": False,
            "items": [],
            "count_annotations": 0,
            "count_anomalies": 0,
        },
        "speed": {
            "available": False,
            "days": [],
            "latest": None,
            "averages_7d": {},
        },
        "errors": [],
    }

    urls = {
        "device_type": _radar_url(
            base_url,
            "/http/summary/device_type",
            {"dateRange": "1d", "location": "CU", "format": "json"},
        ),
        "bot_class": _radar_url(
            base_url,
            "/http/summary/bot_class",
            {"dateRange": "1d", "location": "CU", "format": "json"},
        ),
        "annotations": _radar_url(
            base_url,
            "/annotations/outages",
            {"dateRange": "2d", "location": "CU", "format": "json"},
        ),
        "traffic_anomalies": _radar_url(
            base_url,
            "/traffic_anomalies",
            {"dateRange": "2d", "location": "CU", "limit": 20, "format": "json"},
        ),
        "speed_cuba": _radar_url(
            base_url,
            "/quality/speed/summary",
            _speed_window_params(days=7, location="CU"),
        ),
        "speed_world": _radar_url(
            base_url,
            "/quality/speed/summary",
            _speed_window_params(days=7, location=None),
        ),
    }

    responses = {}
    for name, url in urls.items():
        response = _fetch_radar_json(url, token, timeout_seconds)
        responses[name] = response
        if not response.get("ok"):
            output["errors"].append(
                {
                    "endpoint": name,
                    "status_code": response.get("status_code"),
                    "error": response.get("error"),
                }
            )

    device_payload = responses.get("device_type", {}).get("payload") or {}
    bot_payload = responses.get("bot_class", {}).get("payload") or {}
    device_summary = (
        device_payload.get("result", {}).get("summary_0")
        if isinstance(device_payload, dict)
        else None
    )
    bot_summary = (
        bot_payload.get("result", {}).get("summary_0")
        if isinstance(bot_payload, dict)
        else None
    )
    mobile_pct = _to_percent((device_summary or {}).get("mobile"))
    desktop_pct = _to_percent((device_summary or {}).get("desktop"))
    human_pct = _to_percent((bot_summary or {}).get("human"))
    bot_pct = _to_percent((bot_summary or {}).get("bot"))
    if mobile_pct is not None and desktop_pct is None:
        desktop_pct = _safe_round(100 - mobile_pct, 3)
    if desktop_pct is not None and mobile_pct is None:
        mobile_pct = _safe_round(100 - desktop_pct, 3)
    if human_pct is not None and bot_pct is None:
        bot_pct = _safe_round(100 - human_pct, 3)
    if bot_pct is not None and human_pct is None:
        human_pct = _safe_round(100 - bot_pct, 3)
    output["audience"] = {
        "available": any(value is not None for value in (mobile_pct, desktop_pct, human_pct, bot_pct)),
        "device_mobile_pct": mobile_pct,
        "device_desktop_pct": desktop_pct,
        "human_pct": human_pct,
        "bot_pct": bot_pct,
    }

    annotation_alerts = _extract_annotation_alerts(
        responses.get("annotations", {}).get("payload")
    )
    anomaly_alerts = _extract_anomaly_alerts(
        responses.get("traffic_anomalies", {}).get("payload")
    )
    merged_alerts = _dedupe_and_sort_alerts(annotation_alerts + anomaly_alerts)
    output["alerts"] = {
        "available": bool(merged_alerts),
        "items": merged_alerts[:40],
        "count_annotations": len(annotation_alerts),
        "count_anomalies": len(anomaly_alerts),
    }

    speed_summary = _build_speed_summary(
        responses.get("speed_cuba", {}).get("payload"),
        responses.get("speed_world", {}).get("payload"),
        days=7,
    )
    output["speed"] = speed_summary
    return output


def _coerce_non_negative_int(value, default):
    try:
        parsed = int(value)
    except Exception:
        parsed = int(default)
    return max(parsed, 0)


def _clone_json_value(value):
    try:
        return json.loads(json.dumps(value, ensure_ascii=False))
    except Exception:
        return value


def _normalize_radar_error_items(items):
    normalized = []
    if not isinstance(items, list):
        return normalized
    for raw in items:
        if not isinstance(raw, dict):
            continue
        endpoint = str(raw.get("endpoint") or "").strip() or "unknown"
        status_code_raw = raw.get("status_code")
        try:
            status_code = int(status_code_raw) if status_code_raw is not None else None
        except Exception:
            status_code = None
        error_text = _truncate_text(raw.get("error"), limit=320)
        key = (endpoint, status_code, error_text)
        if any((row.get("_key") == key) for row in normalized):
            continue
        normalized.append(
            {
                "endpoint": endpoint,
                "status_code": status_code,
                "error": error_text or None,
                "_key": key,
            }
        )
    for row in normalized:
        row.pop("_key", None)
    return normalized


def _merge_radar_errors(*groups):
    merged = []
    seen = set()
    for group in groups:
        for item in _normalize_radar_error_items(group):
            key = (item.get("endpoint"), item.get("status_code"), item.get("error"))
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
            if len(merged) >= 24:
                return merged
    return merged


def _radar_enrichment_has_visible_data(enrichment):
    if not isinstance(enrichment, dict):
        return False
    audience = enrichment.get("audience") if isinstance(enrichment.get("audience"), dict) else {}
    speed = enrichment.get("speed") if isinstance(enrichment.get("speed"), dict) else {}
    alerts = enrichment.get("alerts") if isinstance(enrichment.get("alerts"), dict) else {}
    if bool(audience.get("available")) or bool(speed.get("available")) or bool(alerts.get("available")):
        return True
    metrics = [
        audience.get("device_mobile_pct"),
        audience.get("device_desktop_pct"),
        audience.get("human_pct"),
        audience.get("bot_pct"),
    ]
    if any(to_float(metric) is not None for metric in metrics):
        return True
    latest = speed.get("latest") if isinstance(speed.get("latest"), dict) else {}
    return any(to_float(value) is not None for value in latest.values())


def _radar_enrichment_has_rate_limit_error(enrichment):
    errors = enrichment.get("errors") if isinstance(enrichment, dict) else None
    for row in _normalize_radar_error_items(errors):
        if row.get("status_code") == 429:
            return True
    return False


def _latest_successful_radar_enrichment():
    runs = (
        ConnectivityIngestionRun.query.filter_by(status="success")
        .order_by(ConnectivityIngestionRun.id.desc())
        .limit(30)
        .all()
    )
    for run in runs:
        payload_raw = run.payload_json
        if not payload_raw:
            continue
        try:
            payload = json.loads(payload_raw)
        except Exception:
            continue
        radar = payload.get("cloudflare_radar") if isinstance(payload, dict) else None
        if not isinstance(radar, dict):
            continue
        return {
            "run_id": run.id,
            "fetched_at_utc": _parse_radar_datetime(radar.get("fetched_at_utc")),
            "payload": radar,
        }
    return None


def _resolve_radar_enrichment_with_fallback(
    base_url,
    token,
    timeout_seconds,
    cooldown_seconds,
    previous_record=None,
):
    now = _utcnow()
    previous_payload = (
        previous_record.get("payload")
        if isinstance(previous_record, dict) and isinstance(previous_record.get("payload"), dict)
        else None
    )
    previous_run_id = previous_record.get("run_id") if isinstance(previous_record, dict) else None
    previous_fetched_at = (
        previous_record.get("fetched_at_utc") if isinstance(previous_record, dict) else None
    )

    if previous_payload and cooldown_seconds > 0 and previous_fetched_at:
        age_seconds = max(0, int((now - previous_fetched_at).total_seconds()))
        if age_seconds < cooldown_seconds:
            reused = _clone_json_value(previous_payload)
            reused["reused_from_run_id"] = previous_run_id
            reused["reused_reason"] = "cooldown_active"
            reused["reused_at_utc"] = serialize_snapshot_time(now)
            reused["errors"] = _merge_radar_errors(
                reused.get("errors"),
                [
                    {
                        "endpoint": "cloudflare_radar",
                        "status_code": None,
                        "error": (
                            "Se reutilizo enrichment previo por cooldown para reducir llamadas "
                            "a Cloudflare Radar."
                        ),
                    }
                ],
            )
            return reused

    fresh = _fetch_radar_enrichment(base_url, token, timeout_seconds)
    if not previous_payload:
        return fresh
    if not _radar_enrichment_has_visible_data(previous_payload):
        return fresh
    if _radar_enrichment_has_visible_data(fresh) and not _radar_enrichment_has_rate_limit_error(fresh):
        return fresh

    reused = _clone_json_value(previous_payload)
    reused["reused_from_run_id"] = previous_run_id
    reused["reused_at_utc"] = serialize_snapshot_time(now)
    if _radar_enrichment_has_rate_limit_error(fresh):
        reused["reused_reason"] = "upstream_rate_limited"
    else:
        reused["reused_reason"] = "upstream_unavailable"
    reused["errors"] = _merge_radar_errors(
        fresh.get("errors"),
        [
            {
                "endpoint": "cloudflare_radar",
                "status_code": None,
                "error": "Se reutilizo enrichment previo por error temporal en Cloudflare Radar.",
            }
        ],
    )
    return reused


def _historical_baseline():
    rows = (
        ConnectivitySnapshot.query.order_by(ConnectivitySnapshot.observed_at_utc.desc())
        .limit(12)
        .all()
    )
    return median_baseline([row.traffic_value for row in rows])


def _compute_payload_snapshot(payload):
    main_points = extract_series_points(payload, "main")
    previous_points = extract_series_points(payload, "previous")
    if not main_points:
        return None

    latest_main = main_points[-1]
    latest_pair = get_latest_common_point(main_points, previous_points)

    observed_at = latest_main["timestamp"]
    traffic_value = to_float(latest_main["value"])
    baseline_value = None
    partial = False

    if latest_pair:
        observed_at = latest_pair["timestamp"]
        traffic_value = to_float(latest_pair["main_value"])
        baseline_value = to_float(latest_pair["previous_value"])
    else:
        partial = True
        if previous_points:
            baseline_value = to_float(previous_points[-1]["value"])

    if baseline_value is None or baseline_value <= 0:
        fallback_baseline = _historical_baseline()
        if fallback_baseline is not None and fallback_baseline > 0:
            baseline_value = fallback_baseline
        else:
            baseline_value = traffic_value

    score, status = compute_connectivity_score(traffic_value, baseline_value)
    if score is None:
        return None

    return {
        "observed_at_utc": observed_at,
        "traffic_value": traffic_value,
        "baseline_value": baseline_value,
        "score": score,
        "status": status,
        "is_partial": partial,
    }


def _upsert_snapshot(run, best_payloads_by_province):
    raw_provinces = list(best_payloads_by_province.keys())
    if not raw_provinces:
        try:
            raw_provinces = list_provinces() or list(PROVINCES)
        except Exception:
            raw_provinces = list(PROVINCES)
    if not raw_provinces:
        raw_provinces = list(PROVINCES)

    provinces = []
    seen_province_keys = set()
    for raw_province in raw_provinces:
        province_name = canonicalize_province_name(raw_province) or str(raw_province or "").strip()
        if not province_name:
            continue
        province_key = normalize_location_key(province_name)
        if not province_key or province_key in seen_province_keys:
            continue
        seen_province_keys.add(province_key)
        provinces.append(province_name)
    if not provinces:
        provinces = list(PROVINCES)

    province_rows = {}
    for province in provinces:
        payload = (best_payloads_by_province.get(province) or {}).get("payload")
        row = _compute_payload_snapshot(payload) if payload else None
        if row:
            province_rows[province] = row

    if not province_rows:
        return None, "No se encontraron datapoints en ninguna provincia"

    scores = [row["score"] for row in province_rows.values() if row.get("score") is not None]
    traffic_values = [
        row["traffic_value"] for row in province_rows.values() if row.get("traffic_value") is not None
    ]
    baseline_values = [
        row["baseline_value"] for row in province_rows.values() if row.get("baseline_value") is not None
    ]
    observed_candidates = [
        row["observed_at_utc"] for row in province_rows.values() if row.get("observed_at_utc") is not None
    ]

    if not scores or not observed_candidates:
        return None, "No fue posible calcular el score de conectividad"

    score = sum(scores) / len(scores)
    status = score_to_status(score)
    traffic_value = sum(traffic_values) / len(traffic_values) if traffic_values else 0.0
    baseline_value = sum(baseline_values) / len(baseline_values) if baseline_values else traffic_value
    observed_at = max(observed_candidates)
    partial = bool(len(province_rows) < len(provinces)) or any(
        bool(row.get("is_partial")) for row in province_rows.values()
    )

    previous_snapshot = (
        ConnectivitySnapshot.query.order_by(ConnectivitySnapshot.observed_at_utc.desc()).first()
    )
    if previous_snapshot:
        previous_score = to_float(previous_snapshot.score)
        if previous_score is not None and abs(score - previous_score) < 3:
            score = previous_score
            status = score_to_status(score)

    snapshot = ConnectivitySnapshot(
        ingestion_run_id=run.id,
        observed_at_utc=observed_at,
        fetched_at_utc=_utcnow(),
        traffic_value=traffic_value,
        baseline_value=baseline_value,
        score=score,
        status=status,
        is_partial=partial,
        confidence="country_level",
        method="province_geoid_aggregate_v1",
    )
    db.session.add(snapshot)
    db.session.flush()

    for province in provinces:
        row = province_rows.get(province)
        province_score = row["score"] if row else score
        province_status = row["status"] if row else status
        db.session.add(
            ConnectivityProvinceStatus(
                snapshot_id=snapshot.id,
                province=province,
                score=province_score,
                status=province_status,
                confidence=(
                    "province_level_radar_estimated"
                    if row
                    else "country_level_fallback"
                ),
                method="province_geoid_v1" if row else "country_fallback_v1",
            )
        )

    return snapshot, None


def run_ingestion(single_call=False, scheduled_for=None):
    app = create_app()
    with app.app_context():
        token = (os.getenv("CF_API_TOKEN") or "").strip()
        if not token:
            raise RuntimeError("CF_API_TOKEN no configurado")

        api_url = app.config.get("CLOUDFLARE_RADAR_HTTP_TIMESERIES_URL")
        radar_api_base_url = app.config.get("CLOUDFLARE_RADAR_API_BASE_URL")
        timeout_seconds = int(app.config.get("CONNECTIVITY_FETCH_TIMEOUT_SECONDS", 30))
        delay_seconds = int(app.config.get("CONNECTIVITY_FETCH_DELAY_SECONDS", 120))
        enrichment_cooldown_seconds = _coerce_non_negative_int(
            app.config.get("CONNECTIVITY_RADAR_ENRICHMENT_COOLDOWN_SECONDS", 21600),
            21600,
        )
        province_geoids = _province_geoids()
        if not province_geoids:
            raise RuntimeError("No hay geoIds provinciales configurados para Radar")
        previous_radar_enrichment = _latest_successful_radar_enrichment()

        run = ConnectivityIngestionRun(
            scheduled_for_utc=scheduled_for,
            started_at_utc=_utcnow(),
            status="running",
            attempt_count=0,
            api_url=api_url,
        )
        db.session.add(run)
        db.session.commit()

        attempt_rounds = []
        total_attempts = 0
        max_rounds = 1 if single_call else 2

        for round_index in range(max_rounds):
            round_attempts = {}
            for province, geo_id in province_geoids.items():
                province_url = _url_with_geoid(api_url, geo_id)
                attempt = _fetch_once(province_url, token, timeout_seconds)
                attempt["geo_id"] = geo_id
                attempt["url"] = province_url
                round_attempts[province] = attempt
                total_attempts += 1
            attempt_rounds.append(round_attempts)
            run.attempt_count = total_attempts
            db.session.commit()

            if round_index < max_rounds - 1 and delay_seconds > 0:
                time.sleep(delay_seconds)

        best_payloads_by_province = {}
        for province in province_geoids.keys():
            province_attempts = []
            for round_attempts in attempt_rounds:
                attempt = round_attempts.get(province)
                if attempt:
                    province_attempts.append(attempt)
            best = _pick_best_attempt(province_attempts)
            if best:
                best_attempt = best["attempt"]
                best_payloads_by_province[province] = {
                    "geo_id": best_attempt.get("geo_id"),
                    "url": best_attempt.get("url"),
                    "status_code": best_attempt.get("status_code"),
                    "payload": best_attempt.get("payload"),
                }

        if not best_payloads_by_province:
            run.status = "failed"
            all_errors = []
            for round_attempts in attempt_rounds:
                for province, attempt in round_attempts.items():
                    status_code = attempt.get("status_code")
                    all_errors.append(
                        f"{province}: HTTP {status_code if status_code is not None else '-'} - "
                        f"{attempt.get('error') or 'respuesta invalida'}"
                    )
            run.error_message = "; ".join(all_errors)[:1200]
            run.finished_at_utc = _utcnow()
            run.payload_json = json.dumps(
                {
                    "mode": "province_geoid_v1",
                    "provinces": {
                        province: {
                            "geo_id": attempt.get("geo_id"),
                            "ok": bool(attempt.get("ok")),
                            "status_code": attempt.get("status_code"),
                            "error": attempt.get("error"),
                        }
                        for round_attempts in attempt_rounds
                        for province, attempt in round_attempts.items()
                    },
                },
                ensure_ascii=False,
            )
            db.session.commit()
            raise RuntimeError(run.error_message or "No se pudo obtener datos de Radar")

        radar_enrichment = _resolve_radar_enrichment_with_fallback(
            radar_api_base_url,
            token,
            timeout_seconds,
            cooldown_seconds=enrichment_cooldown_seconds,
            previous_record=previous_radar_enrichment,
        )
        payload_record = {
            "mode": "province_geoid_v1",
            "generated_at_utc": serialize_snapshot_time(_utcnow()),
            "provinces": {
                province: {
                    "geo_id": details.get("geo_id"),
                    "status_code": details.get("status_code"),
                    "url": details.get("url"),
                    "payload": details.get("payload"),
                }
                for province, details in best_payloads_by_province.items()
            },
            "cloudflare_radar": radar_enrichment,
        }

        snapshot, snapshot_error = _upsert_snapshot(run, best_payloads_by_province)
        if snapshot_error:
            run.status = "failed"
            run.error_message = snapshot_error
            run.finished_at_utc = _utcnow()
            run.payload_json = json.dumps(payload_record, ensure_ascii=False)
            db.session.commit()
            raise RuntimeError(snapshot_error)

        run.status = "success"
        run.error_message = None
        run.finished_at_utc = _utcnow()
        run.payload_json = json.dumps(payload_record, ensure_ascii=False)
        db.session.commit()

        print(
            "OK",
            json.dumps(
                {
                    "run_id": run.id,
                    "snapshot_id": snapshot.id,
                    "observed_at_utc": serialize_snapshot_time(snapshot.observed_at_utc),
                    "score": round(snapshot.score or 0, 2),
                    "status": snapshot.status,
                    "attempts": total_attempts,
                    "provinces_ok": len(best_payloads_by_province),
                },
                ensure_ascii=False,
            ),
        )


def main():
    args = parse_args()
    scheduled_for = _parse_scheduled_for(args.scheduled_for)
    run_ingestion(single_call=args.single_call, scheduled_for=scheduled_for)


if __name__ == "__main__":
    main()
