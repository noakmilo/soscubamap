from flask import jsonify, request, make_response, session, current_app
import math
import json
import os
import secrets
from decimal import Decimal
from datetime import datetime, timedelta, date, timezone
from sqlalchemy.exc import IntegrityError
from flask_login import current_user
import requests

from app.extensions import db, limiter
from app.services.input_safety import has_malicious_input
from app.services.recaptcha import verify_recaptcha, recaptcha_enabled
from app.services.text_sanitize import sanitize_text
from app.models.comment import Comment
from app.models.user import User
from app.models.role import Role
from app.models.media import Media
from app.models.post_revision import PostRevision
from app.models.post_edit_request import PostEditRequest
from app.models.site_setting import SiteSetting
from app.services.media_upload import (
    validate_files,
    upload_files,
    media_json_from_post,
    get_media_payload,
)
from app.models.chat_message import ChatMessage
from app.models.chat_presence import ChatPresence
from app.models.discussion_post import DiscussionPost
from app.models.discussion_comment import DiscussionComment
from app.models.push_subscription import PushSubscription
from app.models.vote_record import VoteRecord
from app.services.vote_identity import get_voter_hash
from app.models.connectivity_snapshot import ConnectivitySnapshot
from app.models.connectivity_ingestion_run import ConnectivityIngestionRun
from app.models.connectivity_province_status import ConnectivityProvinceStatus
from app.models.ais_ingestion_run import AISIngestionRun
from app.models.ais_cuba_target_vessel import AISCubaTargetVessel
from app.models.protest_event import ProtestEvent
from app.models.protest_ingestion_run import ProtestIngestionRun
from app.models.repressor import (
    REPRESSOR_VERIFY_LOCK_COUNT,
    Repressor,
    RepressorIngestionRun,
    RepressorResidenceReport,
)
from app.models.prisoner import Prisoner
from app.services.connectivity import (
    STATUS_CRITICAL,
    STATUS_COLORS,
    STATUS_LABELS,
    STATUS_UNKNOWN,
    extract_series_points,
    get_latest_hourly_point,
    score_to_status,
    serialize_snapshot_time,
    to_float,
)
from app.services.connectivity_geo import (
    diagnose_province_geojson,
    enrich_geojson_with_status,
    load_province_geojson,
    province_names_from_geojson,
)
from app.services.geo_lookup import is_within_cuba_bounds, list_provinces, lookup_location
from app.services.cuba_locations import PROVINCES, PROVINCE_CENTER_FALLBACKS
from app.services.location_names import (
    canonicalize_location_names,
    canonicalize_province_name,
    normalize_location_key,
)
from app.services.protests import (
    _gazetteer as protest_gazetteer,
    display_source_name as protest_display_source_name,
    get_fetch_interval_seconds as protest_fetch_interval_seconds,
    get_fetch_timeout_seconds as protest_fetch_timeout_seconds,
    get_rss_feed_urls as protest_rss_feed_urls,
    get_frontend_refresh_seconds as protest_frontend_refresh_seconds,
    get_min_confidence_to_show as protest_min_confidence_to_show,
    require_source_url_for_map as protest_require_source_url,
    allow_unresolved_location_on_map as protest_allow_unresolved_location_on_map,
)
from app.services.repressors import (
    build_residence_post_description,
    build_residence_post_title,
    serialize_repressor,
)
from app.services.prisoners import serialize_prisoner
from app.services.aisstream import (
    get_ais_frontend_refresh_seconds,
    get_ais_max_target_vessels,
    get_ais_stale_after_hours,
)

from app.models.post import Post
from sqlalchemy.orm import selectinload
from app.models.category import Category
from sqlalchemy import func, or_
from . import api_bp


def _is_admin_user():
    return current_user.is_authenticated and current_user.has_role("administrador")


def _get_or_create_anon_user():
    if current_user.is_authenticated:
        return current_user

    anon_user = User(email=f"anon+{secrets.token_hex(6)}@local")
    anon_user.set_password(secrets.token_urlsafe(16))
    anon_user.ensure_anon_code()
    default_role = Role.query.filter_by(name="colaborador").first()
    if default_role:
        anon_user.roles.append(default_role)
    db.session.add(anon_user)
    db.session.flush()
    return anon_user


def _residence_category():
    return Category.query.filter_by(slug="residencia-represor").first()


def _get_chat_nick():
    nick = session.get("chat_nick")
    if nick and (nick.lower() != "admin" or _is_admin_user()):
        return nick
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    code = "".join(secrets.choice(alphabet) for _ in range(6))
    nick = f"Anon-{code}"
    session["chat_nick"] = nick
    return nick


def _sanitize_nick(nickname: str, fallback: str) -> str:
    value = (nickname or "").strip()
    if not value:
        return fallback
    if value.lower() == "admin" and not _is_admin_user():
        return fallback
    return value[:80]


def _push_enabled() -> bool:
    return bool(
        current_app.config.get("VAPID_PUBLIC_KEY")
        and current_app.config.get("VAPID_PRIVATE_KEY")
    )


def _truthy_param(raw):
    return str(raw or "").strip().lower() in {"1", "true", "yes", "on"}


def _mask_secret(value):
    text = (value or "").strip()
    if not text:
        return ""
    if len(text) <= 10:
        return "*" * len(text)
    return f"{text[:4]}...{text[-4:]}"


def _canonical_province_name(value):
    return canonicalize_province_name(value) or str(value or "").strip()


def _matching_stored_province_values(model_column, selected_province):
    canonical = _canonical_province_name(selected_province)
    if not canonical:
        return []
    target_key = normalize_location_key(canonical)
    if not target_key:
        return []

    rows = (
        db.session.query(model_column)
        .filter(
            model_column.isnot(None),
            model_column != "",
        )
        .distinct()
        .all()
    )

    values = []
    seen = set()
    for row in rows:
        raw_value = row[0]
        raw_text = str(raw_value or "").strip()
        if not raw_text:
            continue
        if normalize_location_key(raw_text) != target_key:
            continue
        if raw_text in seen:
            continue
        seen.add(raw_text)
        values.append(raw_text)

    if canonical not in seen:
        values.append(canonical)
    return values


def _safe_float(value):
    try:
        numeric = float(value)
    except Exception:
        return None
    if math.isfinite(numeric):
        return numeric
    return None


def _resolve_territory_centroid(province_name=None, municipality_name=None):
    raw_province_text = str(province_name or "").strip()
    province_text = canonicalize_province_name(province_name) or raw_province_text
    municipality_text = (
        canonicalize_location_names(province_name, municipality_name)[1]
        if municipality_name
        else None
    )
    province_keys: list[str] = []
    for value in (province_text, raw_province_text):
        key = normalize_location_key(value)
        if key and key not in province_keys:
            province_keys.append(key)
    if province_text == "La Habana":
        # Algunos geojson históricos etiquetan la ciudad como "Ciudad de La Habana"
        # y otros como "La Habana". Priorizamos la variante de ciudad para no caer
        # en centroides de la antigua provincia Habana.
        prioritized_keys: list[str] = ["ciudaddelahabana", "lahabana"]
        for key in province_keys:
            if key not in prioritized_keys:
                prioritized_keys.append(key)
        province_keys = prioritized_keys

    municipality_key = normalize_location_key(municipality_text)

    gazetteer = {}
    try:
        gazetteer = protest_gazetteer() or {}
    except Exception:
        gazetteer = {}
    gazetteer_all = gazetteer.get("all") if isinstance(gazetteer, dict) else {}
    if not isinstance(gazetteer_all, dict):
        gazetteer_all = {}

    def _pick_lat_lng(entry):
        if not isinstance(entry, dict):
            return None, None
        lat = _safe_float(entry.get("lat"))
        lng = _safe_float(entry.get("lng"))
        if lat is None or lng is None:
            return None, None
        return lat, lng

    if municipality_key:
        entries = gazetteer_all.get(municipality_key) or []
        for entry in entries:
            if str(entry.get("type") or "").strip() != "municipality":
                continue
            entry_province_key = normalize_location_key(entry.get("province"))
            if province_keys and entry_province_key and entry_province_key not in province_keys:
                continue
            lat, lng = _pick_lat_lng(entry)
            if lat is not None and lng is not None:
                return lat, lng

    for candidate_key in province_keys:
        entries = gazetteer_all.get(candidate_key) or []
        for entry in entries:
            if str(entry.get("type") or "").strip() != "province":
                continue
            lat, lng = _pick_lat_lng(entry)
            if lat is not None and lng is not None:
                return lat, lng

    fallback_candidates = []
    for value in (province_text, raw_province_text):
        text = str(value or "").strip()
        if text and text not in fallback_candidates:
            fallback_candidates.append(text)
    if province_text == "La Habana":
        fallback_candidates.append("Ciudad de La Habana")

    for candidate in fallback_candidates:
        fallback = PROVINCE_CENTER_FALLBACKS.get(candidate)
        if isinstance(fallback, (list, tuple)) and len(fallback) >= 2:
            lat = _safe_float(fallback[0])
            lng = _safe_float(fallback[1])
            if lat is not None and lng is not None:
                return lat, lng

    return None, None


def _cf_api_token():
    return (current_app.config.get("CF_API_TOKEN") or os.getenv("CF_API_TOKEN") or "").strip()


def _connectivity_payload_summary(payload):
    if not isinstance(payload, dict):
        return {
            "parse_ok": False,
            "main_points": 0,
            "previous_points": 0,
            "latest_main": None,
            "latest_previous": None,
            "latest_main_hourly": None,
        }

    provinces = payload.get("provinces")
    if isinstance(provinces, dict):
        province_summaries = {}
        ok_count = 0
        latest_points = []
        for province, details in provinces.items():
            province_payload = (details or {}).get("payload")
            summary = _connectivity_payload_summary(province_payload)
            province_summaries[province] = {
                "main_points": summary.get("main_points", 0),
                "latest_main_hourly": summary.get("latest_main_hourly"),
            }
            if summary.get("main_points"):
                ok_count += 1
            latest_main_hourly = summary.get("latest_main_hourly")
            if latest_main_hourly and latest_main_hourly.get("timestamp_utc"):
                latest_points.append(latest_main_hourly.get("timestamp_utc"))
        return {
            "parse_ok": True,
            "mode": payload.get("mode") or "province_geoid_v1",
            "province_count": len(provinces),
            "provinces_with_data": ok_count,
            "latest_hourly_timestamp_utc": max(latest_points) if latest_points else None,
            "provinces": province_summaries,
        }

    main_points = extract_series_points(payload, "main")
    previous_points = extract_series_points(payload, "previous")
    latest_main = main_points[-1] if main_points else None
    latest_previous = previous_points[-1] if previous_points else None
    latest_main_hourly = get_latest_hourly_point(payload, "main")

    def _serialize_point(point):
        if not point:
            return None
        return {
            "timestamp_utc": serialize_snapshot_time(point.get("timestamp")),
            "value": point.get("value"),
        }

    return {
        "parse_ok": True,
        "main_points": len(main_points),
        "previous_points": len(previous_points),
        "latest_main": _serialize_point(latest_main),
        "latest_previous": _serialize_point(latest_previous),
        "latest_main_hourly": _serialize_point(latest_main_hourly),
    }


def _serialize_timeseries_point(point):
    if not point:
        return None
    return {
        "timestamp_utc": serialize_snapshot_time(point.get("timestamp")),
        "value": to_float(point.get("value")),
    }


def _latest_successful_connectivity_run():
    return (
        ConnectivityIngestionRun.query.filter(
            ConnectivityIngestionRun.status == "success",
            ConnectivityIngestionRun.payload_json.isnot(None),
            ConnectivityIngestionRun.payload_json != "",
        )
        .order_by(
            ConnectivityIngestionRun.started_at_utc.desc(),
            ConnectivityIngestionRun.id.desc(),
        )
        .first()
    )


def _compute_window_summary_from_payload(payload, hours):
    main_points_all = extract_series_points(payload, "main")
    previous_points_all = extract_series_points(payload, "previous")
    if not main_points_all:
        return {
            "available": False,
            "reason": "La serie main no contiene puntos.",
            "window_hours": hours,
            "series_main": [],
            "series_previous_aligned": [],
        }

    latest_ts = main_points_all[-1].get("timestamp")
    window_start = latest_ts - timedelta(hours=hours) if latest_ts else None
    main_points = [
        item
        for item in main_points_all
        if item.get("timestamp") is not None and (window_start is None or item.get("timestamp") >= window_start)
    ]
    if not main_points:
        main_points = main_points_all[-hours:]

    previous_aligned = []
    if previous_points_all and main_points:
        align_count = min(len(previous_points_all), len(main_points))
        prev_tail = previous_points_all[-align_count:]
        main_tail = main_points[-align_count:]
        for main_item, prev_item in zip(main_tail, prev_tail):
            previous_aligned.append(
                {
                    "timestamp": main_item.get("timestamp"),
                    "value": to_float(prev_item.get("value")),
                }
            )

    main_values = [to_float(item.get("value")) for item in main_points]
    main_values = [value for value in main_values if value is not None]

    latest_main_value = to_float(main_points[-1].get("value")) if main_points else None
    latest_previous_value = (
        to_float(previous_aligned[-1].get("value")) if previous_aligned else None
    )

    delta_pct = None
    if (
        latest_main_value is not None
        and latest_previous_value is not None
        and latest_previous_value > 0
    ):
        delta_pct = ((latest_main_value - latest_previous_value) / latest_previous_value) * 100.0

    peak_main_value = max(main_values) if main_values else None
    min_main_value = min(main_values) if main_values else None
    avg_main_value = (sum(main_values) / len(main_values)) if main_values else None

    score_method = "blended_latest_avg_worst_from_main_peak_ratio_pct_v1"
    max_drop_from_peak_pct = None
    if (
        peak_main_value is not None
        and min_main_value is not None
        and peak_main_value > 0
    ):
        max_drop_from_peak_pct = ((peak_main_value - min_main_value) / peak_main_value) * 100.0

    score_latest_pct = None
    score_avg_pct = None
    score_worst_pct = None
    score_window_pct = None
    if min_main_value is not None and peak_main_value is not None:
        if peak_main_value > 0:
            if latest_main_value is not None:
                score_latest_pct = (latest_main_value / peak_main_value) * 100.0
                score_latest_pct = max(0.0, min(score_latest_pct, 100.0))
            if avg_main_value is not None:
                score_avg_pct = (avg_main_value / peak_main_value) * 100.0
                score_avg_pct = max(0.0, min(score_avg_pct, 100.0))
            score_worst_pct = (min_main_value / peak_main_value) * 100.0
            score_worst_pct = max(0.0, min(score_worst_pct, 100.0))
        elif peak_main_value == 0 and min_main_value == 0:
            score_latest_pct = 0.0
            score_avg_pct = 0.0
            score_worst_pct = 0.0

    weighted_parts = []
    if score_latest_pct is not None:
        weighted_parts.append((score_latest_pct, 0.55))
    if score_avg_pct is not None:
        weighted_parts.append((score_avg_pct, 0.30))
    if score_worst_pct is not None:
        weighted_parts.append((score_worst_pct, 0.15))
    if weighted_parts:
        total_weight = sum(weight for _, weight in weighted_parts)
        score_window_pct = sum(value * weight for value, weight in weighted_parts) / total_weight
        score_window_pct = max(0.0, min(score_window_pct, 100.0))

    return {
        "available": bool(main_points),
        "window_hours": hours,
        "score_method": score_method,
        "latest_timestamp_utc": serialize_snapshot_time(main_points[-1].get("timestamp")) if main_points else None,
        "latest_main_value": latest_main_value,
        "latest_previous_value": latest_previous_value,
        "delta_pct": delta_pct,
        "peak_main_value": peak_main_value,
        "min_main_value": min_main_value,
        "avg_main_value": avg_main_value,
        "max_drop_from_peak_pct": max_drop_from_peak_pct,
        "score_latest_pct": score_latest_pct,
        "score_avg_pct": score_avg_pct,
        "score_worst_pct": score_worst_pct,
        "score_window_pct": score_window_pct,
        "series_main": [
            point for point in (_serialize_timeseries_point(item) for item in main_points) if point
        ],
        "series_previous_aligned": [
            point
            for point in (_serialize_timeseries_point(item) for item in previous_aligned)
            if point
        ],
    }


def _average_serialized_series(series_groups):
    buckets = {}
    for series in series_groups or []:
        for point in series or []:
            timestamp = point.get("timestamp_utc")
            value = to_float(point.get("value"))
            if not timestamp or value is None:
                continue
            buckets.setdefault(timestamp, []).append(value)
    points = []
    for timestamp in sorted(buckets.keys()):
        values = buckets[timestamp]
        points.append({"timestamp_utc": timestamp, "value": sum(values) / len(values)})
    return points


def _build_http_requests_window_summary(window_hours=24):
    try:
        hours = int(window_hours)
    except Exception:
        hours = 24
    hours = max(1, min(hours, 48))

    run = _latest_successful_connectivity_run()
    if not run or not run.payload_json:
        return {
            "available": False,
            "reason": "No hay ingestas exitosas con payload.",
            "window_hours": hours,
            "series_main": [],
            "series_previous_aligned": [],
        }

    try:
        payload = json.loads(run.payload_json)
    except Exception as exc:
        return {
            "available": False,
            "reason": f"Payload de ingesta invalido: {exc}",
            "window_hours": hours,
            "source_run_id": run.id,
            "source_started_at_utc": serialize_snapshot_time(run.started_at_utc),
            "source_finished_at_utc": serialize_snapshot_time(run.finished_at_utc),
            "series_main": [],
            "series_previous_aligned": [],
        }

    provinces = payload.get("provinces")
    if isinstance(provinces, dict):
        by_province = {}
        for raw_province, details in provinces.items():
            province_name = _canonical_province_name(raw_province)
            province_payload = (details or {}).get("payload")
            summary = _compute_window_summary_from_payload(province_payload, hours)
            summary["geo_id"] = (details or {}).get("geo_id")
            by_province[province_name] = summary

        available_province_items = [
            item for item in by_province.values() if item.get("available")
        ]
        if not available_province_items:
            return {
                "available": False,
                "reason": "No hay series provinciales con datos.",
                "window_hours": hours,
                "source_run_id": run.id,
                "source_started_at_utc": serialize_snapshot_time(run.started_at_utc),
                "source_finished_at_utc": serialize_snapshot_time(run.finished_at_utc),
                "series_main": [],
                "series_previous_aligned": [],
                "by_province": by_province,
            }

        main_series_avg = _average_serialized_series(
            [item.get("series_main") for item in available_province_items]
        )
        prev_series_avg = _average_serialized_series(
            [item.get("series_previous_aligned") for item in available_province_items]
        )
        main_values = [to_float(point.get("value")) for point in main_series_avg]
        main_values = [value for value in main_values if value is not None]

        latest_main_value = (
            to_float(main_series_avg[-1].get("value")) if main_series_avg else None
        )
        latest_previous_value = (
            to_float(prev_series_avg[-1].get("value")) if prev_series_avg else None
        )
        delta_pct = None
        if (
            latest_main_value is not None
            and latest_previous_value is not None
            and latest_previous_value > 0
        ):
            delta_pct = (
                (latest_main_value - latest_previous_value) / latest_previous_value
            ) * 100.0

        peak_main_value = max(main_values) if main_values else None
        min_main_value = min(main_values) if main_values else None
        avg_main_value = (sum(main_values) / len(main_values)) if main_values else None

        score_latest_pct = None
        score_avg_pct = None
        score_worst_pct = None
        if min_main_value is not None and peak_main_value is not None:
            if peak_main_value > 0:
                if latest_main_value is not None:
                    score_latest_pct = (latest_main_value / peak_main_value) * 100.0
                if avg_main_value is not None:
                    score_avg_pct = (avg_main_value / peak_main_value) * 100.0
                score_worst_pct = (min_main_value / peak_main_value) * 100.0
            elif peak_main_value == 0 and min_main_value == 0:
                score_latest_pct = 0.0
                score_avg_pct = 0.0
                score_worst_pct = 0.0

        score_latest_pct = (
            max(0.0, min(score_latest_pct, 100.0))
            if score_latest_pct is not None
            else None
        )
        score_avg_pct = (
            max(0.0, min(score_avg_pct, 100.0))
            if score_avg_pct is not None
            else None
        )
        score_worst_pct = (
            max(0.0, min(score_worst_pct, 100.0))
            if score_worst_pct is not None
            else None
        )
        score_window_pct = _average_numeric(
            [item.get("score_window_pct") for item in available_province_items]
        )
        if score_window_pct is None:
            score_window_pct = _average_numeric(
                [item.get("score_worst_pct") for item in available_province_items]
            )

        max_drop_from_peak_pct = None
        if (
            peak_main_value is not None
            and min_main_value is not None
            and peak_main_value > 0
        ):
            max_drop_from_peak_pct = (
                (peak_main_value - min_main_value) / peak_main_value
            ) * 100.0

        latest_candidates = [
            item.get("latest_timestamp_utc")
            for item in available_province_items
            if item.get("latest_timestamp_utc")
        ]

        return {
            "available": bool(main_series_avg),
            "window_hours": hours,
            "score_method": "blended_latest_avg_worst_from_main_peak_ratio_pct_v1",
            "source_run_id": run.id,
            "source_started_at_utc": serialize_snapshot_time(run.started_at_utc),
            "source_finished_at_utc": serialize_snapshot_time(run.finished_at_utc),
            "latest_timestamp_utc": (
                main_series_avg[-1].get("timestamp_utc")
                if main_series_avg
                else (max(latest_candidates) if latest_candidates else None)
            ),
            "latest_main_value": latest_main_value,
            "latest_previous_value": latest_previous_value,
            "delta_pct": delta_pct,
            "peak_main_value": peak_main_value,
            "min_main_value": min_main_value,
            "avg_main_value": avg_main_value,
            "max_drop_from_peak_pct": max_drop_from_peak_pct,
            "score_latest_pct": score_latest_pct,
            "score_avg_pct": score_avg_pct,
            "score_worst_pct": score_worst_pct,
            "score_window_pct": score_window_pct,
            "series_main": main_series_avg,
            "series_previous_aligned": prev_series_avg,
            "by_province": by_province,
            "province_count": len(by_province),
            "provinces_with_data": len(available_province_items),
        }

    summary = _compute_window_summary_from_payload(payload, hours)
    summary.update(
        {
            "source_run_id": run.id,
            "source_started_at_utc": serialize_snapshot_time(run.started_at_utc),
            "source_finished_at_utc": serialize_snapshot_time(run.finished_at_utc),
        }
    )
    return summary


def _build_http_requests_24h_summary():
    return _build_http_requests_window_summary(24)


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


def _normalize_percentage(value):
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


def _coerce_alert_type(value, event_type=""):
    text = str(value or "").strip().lower()
    if text in {"outage", "anomaly"}:
        return text
    event = str(event_type or "").strip().lower()
    if "outage" in event:
        return "outage"
    return "anomaly"


def _normalize_cloudflare_alerts(raw_alerts):
    items = []
    for item in raw_alerts or []:
        if not isinstance(item, dict):
            continue
        start_date = str(
            item.get("start_date")
            or item.get("startDate")
            or ""
        ).strip() or None
        end_date = str(
            item.get("end_date")
            or item.get("endDate")
            or ""
        ).strip() or None
        event_type = str(item.get("event_type") or item.get("eventType") or "").strip() or None
        alert_type = _coerce_alert_type(item.get("alert_type"), event_type)
        normalized = {
            "source": str(item.get("source") or "").strip() or None,
            "alert_type": alert_type,
            "event_type": event_type,
            "status": str(item.get("status") or "").strip() or None,
            "description": str(item.get("description") or "").strip() or None,
            "outage_cause": str(item.get("outage_cause") or "").strip() or None,
            "outage_type": str(item.get("outage_type") or "").strip() or None,
            "magnitude": to_float(item.get("magnitude")),
            "asn": str(item.get("asn") or "").strip() or None,
            "asn_name": str(item.get("asn_name") or "").strip() or None,
            "start_date": start_date,
            "end_date": end_date,
            "linked_url": str(item.get("linked_url") or item.get("linkedUrl") or "").strip() or None,
            "is_instantaneous": bool(item.get("is_instantaneous")),
        }
        if not normalized["start_date"]:
            continue
        items.append(normalized)

    deduped = {}
    for item in items:
        key = (
            item.get("source"),
            item.get("alert_type"),
            item.get("event_type"),
            item.get("start_date"),
        )
        existing = deduped.get(key)
        if existing is None:
            deduped[key] = item
            continue
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


def _is_alert_active(alert, now_utc, max_age_hours):
    end_dt = _parse_radar_datetime(alert.get("end_date"))
    if end_dt and end_dt <= now_utc:
        return False
    start_dt = _parse_radar_datetime(alert.get("start_date"))
    if start_dt is None:
        return False
    if end_dt is None:
        max_age = timedelta(hours=max(int(max_age_hours or 24), 1))
        if now_utc - start_dt > max_age:
            return False
    return True


def _extract_radar_payload_from_run(run):
    if not run or not run.payload_json:
        return None
    try:
        payload = json.loads(run.payload_json)
    except Exception:
        return None
    radar = payload.get("cloudflare_radar") if isinstance(payload, dict) else None
    return radar if isinstance(radar, dict) else None


def _build_windowed_audience_summary(now_utc, window_hours):
    try:
        hours = int(window_hours)
    except Exception:
        hours = 24
    hours = max(1, hours)
    window_start = now_utc - timedelta(hours=hours)
    runs = (
        ConnectivityIngestionRun.query.filter(
            ConnectivityIngestionRun.status == "success",
            ConnectivityIngestionRun.started_at_utc >= window_start,
        )
        .order_by(ConnectivityIngestionRun.id.desc())
        .limit(120)
        .all()
    )

    mobile_values = []
    desktop_values = []
    human_values = []
    bot_values = []
    latest_sample_at = None
    sample_count = 0

    for run in runs:
        radar = _extract_radar_payload_from_run(run)
        if not isinstance(radar, dict):
            continue
        audience_raw = radar.get("audience") if isinstance(radar.get("audience"), dict) else {}
        mobile = _normalize_percentage(audience_raw.get("device_mobile_pct"))
        desktop = _normalize_percentage(audience_raw.get("device_desktop_pct"))
        human = _normalize_percentage(audience_raw.get("human_pct"))
        bot = _normalize_percentage(audience_raw.get("bot_pct"))
        if all(value is None for value in (mobile, desktop, human, bot)):
            continue

        sample_count += 1
        if mobile is not None:
            mobile_values.append(mobile)
        if desktop is not None:
            desktop_values.append(desktop)
        if human is not None:
            human_values.append(human)
        if bot is not None:
            bot_values.append(bot)

        sample_at = _parse_radar_datetime(radar.get("fetched_at_utc")) or run.finished_at_utc or run.started_at_utc
        if sample_at and (latest_sample_at is None or sample_at > latest_sample_at):
            latest_sample_at = sample_at

    mobile_avg = _normalize_percentage(_average_numeric(mobile_values))
    desktop_avg = _normalize_percentage(_average_numeric(desktop_values))
    human_avg = _normalize_percentage(_average_numeric(human_values))
    bot_avg = _normalize_percentage(_average_numeric(bot_values))

    return {
        "available": any(value is not None for value in (mobile_avg, desktop_avg, human_avg, bot_avg)),
        "device_mobile_pct": mobile_avg,
        "device_desktop_pct": desktop_avg,
        "human_pct": human_avg,
        "bot_pct": bot_avg,
        "window_hours": hours,
        "sample_count": sample_count,
        "window_start_utc": serialize_snapshot_time(window_start),
        "window_end_utc": serialize_snapshot_time(now_utc),
        "latest_sample_at_utc": serialize_snapshot_time(latest_sample_at),
    }


def _build_cloudflare_radar_summary(window_hours=24):
    now_utc = datetime.utcnow()
    run = _latest_successful_connectivity_run()
    if not run or not run.payload_json:
        return {
            "available": False,
            "source_run_id": None,
            "source_started_at_utc": None,
            "source_finished_at_utc": None,
            "updated_at_utc": None,
            "parse_error": None,
            "errors": [],
            "audience": {"available": False},
            "speed": {"available": False},
            "alerts": {
                "available": False,
                "active_count": 0,
                "active_outages": 0,
                "active_anomalies": 0,
                "latest": None,
                "active": [],
                "items_count": 0,
            },
        }

    parse_error = None
    payload = None
    try:
        payload = json.loads(run.payload_json)
    except Exception as exc:
        parse_error = str(exc)

    radar = payload.get("cloudflare_radar") if isinstance(payload, dict) else None
    if not isinstance(radar, dict):
        return {
            "available": False,
            "source_run_id": run.id,
            "source_started_at_utc": serialize_snapshot_time(run.started_at_utc),
            "source_finished_at_utc": serialize_snapshot_time(run.finished_at_utc),
            "updated_at_utc": None,
            "parse_error": parse_error,
            "errors": [],
            "audience": {"available": False},
            "speed": {"available": False},
            "alerts": {
                "available": False,
                "active_count": 0,
                "active_outages": 0,
                "active_anomalies": 0,
                "latest": None,
                "active": [],
                "items_count": 0,
            },
        }

    errors = radar.get("errors") if isinstance(radar.get("errors"), list) else []
    audience_raw = radar.get("audience") if isinstance(radar.get("audience"), dict) else {}
    mobile_pct = _normalize_percentage(audience_raw.get("device_mobile_pct"))
    desktop_pct = _normalize_percentage(audience_raw.get("device_desktop_pct"))
    human_pct = _normalize_percentage(audience_raw.get("human_pct"))
    bot_pct = _normalize_percentage(audience_raw.get("bot_pct"))
    try:
        audience_window_hours = int(window_hours)
    except Exception:
        audience_window_hours = 24
    audience_window_hours = max(1, audience_window_hours)
    audience_window_start = now_utc - timedelta(hours=audience_window_hours)
    audience = {
        "available": any(value is not None for value in (mobile_pct, desktop_pct, human_pct, bot_pct)),
        "device_mobile_pct": mobile_pct,
        "device_desktop_pct": desktop_pct,
        "human_pct": human_pct,
        "bot_pct": bot_pct,
        "window_hours": audience_window_hours,
        "sample_count": 1 if any(value is not None for value in (mobile_pct, desktop_pct, human_pct, bot_pct)) else 0,
        "window_start_utc": serialize_snapshot_time(audience_window_start),
        "window_end_utc": serialize_snapshot_time(now_utc),
        "latest_sample_at_utc": str(radar.get("fetched_at_utc") or "").strip() or None,
        "is_window_fallback": True,
    }
    windowed_audience = _build_windowed_audience_summary(now_utc, window_hours)
    if windowed_audience.get("sample_count", 0) > 0:
        windowed_audience["is_window_fallback"] = False
        audience = windowed_audience

    speed_raw = radar.get("speed") if isinstance(radar.get("speed"), dict) else {}
    latest_speed_raw = speed_raw.get("latest") if isinstance(speed_raw.get("latest"), dict) else {}
    averages_raw = speed_raw.get("averages_7d") if isinstance(speed_raw.get("averages_7d"), dict) else {}
    speed_latest = {
        "download_mbps": to_float(latest_speed_raw.get("download_mbps")),
        "global_download_mbps": to_float(latest_speed_raw.get("global_download_mbps")),
        "download_delta_pct": to_float(latest_speed_raw.get("download_delta_pct")),
        "upload_mbps": to_float(latest_speed_raw.get("upload_mbps")),
        "latency_ms": to_float(latest_speed_raw.get("latency_ms")),
        "global_latency_ms": to_float(latest_speed_raw.get("global_latency_ms")),
        "latency_delta_pct": to_float(latest_speed_raw.get("latency_delta_pct")),
        "jitter_ms": to_float(latest_speed_raw.get("jitter_ms")),
        "packet_loss_pct": to_float(latest_speed_raw.get("packet_loss_pct")),
    }
    speed_averages = {
        "download_mbps": to_float(averages_raw.get("download_mbps")),
        "global_download_mbps": to_float(averages_raw.get("global_download_mbps")),
        "latency_ms": to_float(averages_raw.get("latency_ms")),
        "global_latency_ms": to_float(averages_raw.get("global_latency_ms")),
        "jitter_ms": to_float(averages_raw.get("jitter_ms")),
        "packet_loss_pct": to_float(averages_raw.get("packet_loss_pct")),
    }
    speed = {
        "available": bool(speed_raw.get("available"))
        or any(value is not None for value in speed_latest.values())
        or any(value is not None for value in speed_averages.values()),
        "latest": speed_latest,
        "averages_7d": speed_averages,
    }

    alerts_raw = radar.get("alerts") if isinstance(radar.get("alerts"), dict) else {}
    alert_items = []
    if isinstance(alerts_raw.get("items"), list):
        alert_items.extend(alerts_raw.get("items") or [])
    if isinstance(alerts_raw.get("annotations"), list):
        alert_items.extend(alerts_raw.get("annotations") or [])
    if isinstance(alerts_raw.get("anomalies"), list):
        alert_items.extend(alerts_raw.get("anomalies") or [])
    normalized_alerts = _normalize_cloudflare_alerts(alert_items)

    max_age_hours = int(current_app.config.get("CONNECTIVITY_ALERT_ACTIVE_MAX_AGE_HOURS", 24))
    active_alerts = []
    for item in normalized_alerts:
        item_payload = dict(item)
        item_payload["is_active"] = _is_alert_active(item_payload, now_utc, max_age_hours)
        if item_payload["is_active"]:
            active_alerts.append(item_payload)

    latest_alert = active_alerts[0] if active_alerts else (normalized_alerts[0] if normalized_alerts else None)
    alerts = {
        "available": bool(normalized_alerts),
        "active_count": len(active_alerts),
        "active_outages": len(
            [item for item in active_alerts if item.get("alert_type") == "outage"]
        ),
        "active_anomalies": len(
            [item for item in active_alerts if item.get("alert_type") == "anomaly"]
        ),
        "latest": latest_alert,
        "active": active_alerts[:20],
        "items_count": len(normalized_alerts),
    }

    available = audience.get("available") or speed.get("available") or alerts.get("available")
    return {
        "available": bool(available),
        "source_run_id": run.id,
        "source_started_at_utc": serialize_snapshot_time(run.started_at_utc),
        "source_finished_at_utc": serialize_snapshot_time(run.finished_at_utc),
        "updated_at_utc": str(radar.get("fetched_at_utc") or "").strip() or None,
        "parse_error": parse_error,
        "errors": errors,
        "audience": audience,
        "speed": speed,
        "alerts": alerts,
    }


def _cloudflare_probe():
    api_url = (current_app.config.get("CLOUDFLARE_RADAR_HTTP_TIMESERIES_URL") or "").strip()
    timeout_seconds = int(current_app.config.get("CONNECTIVITY_FETCH_TIMEOUT_SECONDS", 30))
    token = _cf_api_token()

    result = {
        "requested_at_utc": serialize_snapshot_time(datetime.utcnow()),
        "api_url": api_url,
        "timeout_seconds": timeout_seconds,
        "token_configured": bool(token),
        "token_preview": _mask_secret(token),
        "http_status": None,
        "request_ok": False,
        "cloudflare_success": None,
        "errors": None,
        "payload_summary": None,
        "error": None,
    }

    if not api_url:
        result["error"] = "CLOUDFLARE_RADAR_HTTP_TIMESERIES_URL no configurado"
        return result
    if not token:
        result["error"] = "CF_API_TOKEN no configurado"
        return result

    try:
        response = requests.get(
            api_url,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=timeout_seconds,
        )
        result["http_status"] = response.status_code
        result["request_ok"] = bool(response.ok)

        payload = None
        try:
            payload = response.json()
        except Exception:
            payload = None

        if isinstance(payload, dict):
            result["cloudflare_success"] = payload.get("success")
            result["errors"] = payload.get("errors")
            result["payload_summary"] = _connectivity_payload_summary(payload)
            if not response.ok and not result["errors"]:
                result["error"] = (response.text or "").strip()[:400]
        else:
            result["error"] = "Respuesta no JSON o invalida"
    except Exception as exc:
        result["error"] = str(exc)

    return result


def _apply_vote(record, value):
    if value == 1:
        record.upvotes = (record.upvotes or 0) + 1
    else:
        record.downvotes = (record.downvotes or 0) + 1


def _remove_vote(record, value):
    if value == 1:
        record.upvotes = max((record.upvotes or 0) - 1, 0)
    else:
        record.downvotes = max((record.downvotes or 0) - 1, 0)


def _get_verified_post_ids(post_ids):
    if not post_ids:
        return set()
    voter_hash = get_voter_hash(current_user, request, current_app.config.get("SECRET_KEY", ""))
    if not voter_hash:
        return set()
    rows = (
        VoteRecord.query.filter_by(target_type="post_verify", voter_hash=voter_hash)
        .filter(VoteRecord.target_id.in_(post_ids))
        .all()
    )
    return {row.target_id for row in rows}


def _average_numeric(values):
    numeric = [to_float(value) for value in (values or [])]
    numeric = [value for value in numeric if value is not None]
    if not numeric:
        return None
    return sum(numeric) / len(numeric)


def _minimum_numeric(values):
    numeric = [to_float(value) for value in (values or [])]
    numeric = [value for value in numeric if value is not None]
    if not numeric:
        return None
    return min(numeric)


def _parse_connectivity_window_hours():
    raw = (request.args.get("window_hours") or "").strip()
    if not raw:
        return 24
    try:
        value = int(raw)
    except Exception:
        return 24
    if value in (2, 6, 24):
        return value
    return 24


def _parse_iso_day(raw_value):
    text = str(raw_value or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except Exception:
        return None


def _day_to_str(value):
    if isinstance(value, date):
        return value.isoformat()
    return None


def _parse_protest_filters():
    today_utc = datetime.utcnow().date()
    mode = "day"

    day_param = _parse_iso_day(request.args.get("day"))
    start_param = _parse_iso_day(request.args.get("start"))
    end_param = _parse_iso_day(request.args.get("end"))

    if start_param and end_param:
        if end_param < start_param:
            start_param, end_param = end_param, start_param
        mode = "range"
        return {
            "mode": mode,
            "day": None,
            "start": start_param,
            "end": end_param,
        }

    return {
        "mode": mode,
        "day": day_param or today_utc,
        "start": None,
        "end": None,
    }


def _protest_event_color(event_type, confidence):
    event_key = str(event_type or "").strip().lower()
    score = to_float(confidence)
    if event_key == "confirmed_protest":
        return "#c62828"
    if event_key == "probable_protest":
        return "#ef6c00"
    if event_key == "related_unrest":
        return "#f9a825"
    if event_key == "unresolved_location":
        return "#d97706"
    if score is not None and score >= 70:
        return "#c62828"
    if score is not None and score >= 50:
        return "#ef6c00"
    if score is not None and score >= 35:
        return "#f9a825"
    return "#64748b"


def _safe_keywords_json(raw_json):
    if not raw_json:
        return {}
    try:
        parsed = json.loads(raw_json)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _build_protest_feature(row):
    if row.latitude is None or row.longitude is None:
        return None
    published_at_utc = row.source_published_at_utc.isoformat() + "Z" if row.source_published_at_utc else None
    confidence = to_float(row.confidence_score)
    source_name = protest_display_source_name(
        source_feed=row.source_feed or "",
        source_url=row.source_url or "",
        fallback_name=row.source_name or "",
    )
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [float(row.longitude), float(row.latitude)],
        },
        "properties": {
            "id": row.id,
            "title": row.raw_title,
            "event_type": row.event_type,
            "confidence_score": confidence,
            "color": _protest_event_color(row.event_type, confidence),
            "source_feed": row.source_feed,
            "source_name": source_name,
            "source_name_raw": row.source_name,
            "source_platform": row.source_platform,
            "source_url": row.source_url,
            "source_published_at_utc": published_at_utc,
            "transparency_note": row.transparency_note,
            "matched_place_text": row.matched_place_text,
            "matched_feature_type": row.matched_feature_type,
            "matched_feature_name": row.matched_feature_name,
            "matched_province": row.matched_province,
            "matched_municipality": row.matched_municipality,
            "matched_locality": row.matched_locality,
            "location_precision": row.location_precision,
            "detected_keywords": _safe_keywords_json(row.detected_keywords_json),
            "review_status": row.review_status,
            "can_admin_delete": _is_admin_user(),
        },
    }


@api_bp.route("/health")
def health():
    return jsonify({"status": "ok"})


@api_bp.route("/connectivity/latest")
@limiter.limit("120/minute")
def connectivity_latest():
    now = datetime.utcnow()
    stale_after_hours = int(current_app.config.get("CONNECTIVITY_STALE_AFTER_HOURS", 8))
    stale_threshold = timedelta(hours=max(stale_after_hours, 1))
    window_hours = _parse_connectivity_window_hours()
    window_start = now - timedelta(hours=window_hours)
    window_aggregation = "worst"
    http_requests_window = _build_http_requests_window_summary(window_hours)

    snapshot = (
        ConnectivitySnapshot.query.options(selectinload(ConnectivitySnapshot.provinces))
        .order_by(ConnectivitySnapshot.observed_at_utc.desc(), ConnectivitySnapshot.id.desc())
        .first()
    )
    window_snapshots = (
        ConnectivitySnapshot.query.options(selectinload(ConnectivitySnapshot.provinces))
        .filter(
            ConnectivitySnapshot.observed_at_utc >= window_start,
            ConnectivitySnapshot.observed_at_utc <= now,
        )
        .order_by(ConnectivitySnapshot.observed_at_utc.asc(), ConnectivitySnapshot.id.asc())
        .all()
    )

    geojson = load_province_geojson()
    try:
        province_names = {
            _canonical_province_name(name)
            for name in (list_provinces() or [])
            if _canonical_province_name(name)
        }
    except Exception:
        province_names = set(PROVINCES)
    if not province_names:
        province_names = set(PROVINCES)
    province_names.update(
        _canonical_province_name(name)
        for name in province_names_from_geojson(geojson)
        if _canonical_province_name(name)
    )

    national_score = None
    national_status = STATUS_UNKNOWN
    national_confidence = "unknown"
    stale = True
    partial = True
    snapshot_payload = None
    status_by_province = {}
    window_payload = {
        "hours": window_hours,
        "aggregation": window_aggregation,
        "start_utc": serialize_snapshot_time(window_start),
        "end_utc": serialize_snapshot_time(now),
        "snapshot_count": 0,
        "national_score": None,
        "national_status": STATUS_UNKNOWN,
        "national_status_label": STATUS_LABELS.get(STATUS_UNKNOWN, "Sin datos"),
    }

    if snapshot:
        stale = not snapshot.fetched_at_utc or (now - snapshot.fetched_at_utc) > stale_threshold
        snapshot_payload = {
            "id": snapshot.id,
            "observed_at_utc": serialize_snapshot_time(snapshot.observed_at_utc),
            "fetched_at_utc": serialize_snapshot_time(snapshot.fetched_at_utc),
            "traffic_value": snapshot.traffic_value,
            "baseline_value": snapshot.baseline_value,
            "score": snapshot.score,
            "status": score_to_status(snapshot.score),
            "status_label": STATUS_LABELS.get(
                score_to_status(snapshot.score), STATUS_LABELS[STATUS_UNKNOWN]
            ),
            "is_partial": bool(snapshot.is_partial),
            "stale": stale,
            "confidence": snapshot.confidence or "country_level",
        }

    window_score = None
    if isinstance(http_requests_window, dict) and http_requests_window.get("available"):
        window_score = to_float(http_requests_window.get("score_window_pct"))
        if window_score is None:
            window_score = to_float(http_requests_window.get("score_worst_pct"))
    window_by_province = {}
    if isinstance(http_requests_window, dict):
        raw_by_province = http_requests_window.get("by_province") or {}
        if isinstance(raw_by_province, dict):
            for raw_name, summary in raw_by_province.items():
                canonical_name = _canonical_province_name(raw_name)
                if canonical_name:
                    window_by_province[canonical_name] = summary
    window_series_main = (
        (http_requests_window.get("series_main") or [])
        if isinstance(http_requests_window, dict)
        else []
    )
    window_latest_utc = (
        (window_series_main[-1].get("timestamp_utc") if window_series_main else None)
        or (
            http_requests_window.get("latest_timestamp_utc")
            if isinstance(http_requests_window, dict)
            else None
        )
    )
    window_start_utc = (
        window_series_main[0].get("timestamp_utc")
        if window_series_main
        else serialize_snapshot_time(window_start)
    )
    window_end_utc = window_latest_utc or serialize_snapshot_time(now)

    if window_by_province:
        province_scores = []
        province_available_count = 0
        for province, summary in window_by_province.items():
            province_names.add(province)
            province_score = to_float(summary.get("score_window_pct"))
            if province_score is None:
                province_score = to_float(summary.get("score_worst_pct"))
            if province_score is None:
                continue
            province_available_count += 1
            province_scores.append(province_score)
            status_key = score_to_status(province_score)
            status_by_province[province] = {
                "province": province,
                "score": province_score,
                "status": status_key,
                "status_label": STATUS_LABELS.get(status_key, STATUS_LABELS[STATUS_UNKNOWN]),
                "status_color": STATUS_COLORS.get(status_key, STATUS_COLORS[STATUS_UNKNOWN]),
                "confidence": "province_level_radar_estimated",
                "is_estimated": False,
            }

        national_score = window_score if window_score is not None else _average_numeric(province_scores)
        national_status = score_to_status(national_score)
        national_confidence = "province_level_radar_aggregate"
        partial = province_available_count < len(window_by_province)

        window_payload.update(
            {
                "aggregation": "blended_http_series",
                "score_method": http_requests_window.get("score_method")
                or "blended_latest_avg_worst_from_main_peak_ratio_pct_v1",
                "snapshot_count": len(window_snapshots),
                "national_score": national_score,
                "national_status": national_status,
                "national_status_label": STATUS_LABELS.get(
                    national_status, STATUS_LABELS[STATUS_UNKNOWN]
                ),
                "start_utc": window_start_utc,
                "end_utc": window_end_utc,
                "latest_observed_at_utc": window_latest_utc,
                "http_series_points": len(window_series_main),
                "max_drop_from_peak_pct": http_requests_window.get(
                    "max_drop_from_peak_pct"
                ),
                "province_count": len(window_by_province),
                "provinces_with_data": province_available_count,
                "province_data_source": "radar_geoid",
            }
        )
    elif window_snapshots:
        national_window_scores = [item.score for item in window_snapshots]
        if window_aggregation == "worst":
            national_score = _minimum_numeric(national_window_scores)
        else:
            national_score = _average_numeric(national_window_scores)

        national_status = score_to_status(national_score)
        national_confidence = "window_worst_country_level"
        partial = bool(any(item.is_partial for item in window_snapshots))

        province_score_map = {}
        for snap in window_snapshots:
            for row in snap.provinces:
                province_name = _canonical_province_name(row.province)
                if not province_name:
                    continue
                province_score_map.setdefault(province_name, []).append(row.score)
                province_names.add(province_name)

        for province, scores in province_score_map.items():
            if window_aggregation == "worst":
                province_score = _minimum_numeric(scores)
            else:
                province_score = _average_numeric(scores)
            status_key = score_to_status(province_score)
            status_by_province[province] = {
                "province": province,
                "score": province_score,
                "status": status_key,
                "status_label": STATUS_LABELS.get(status_key, STATUS_LABELS[STATUS_UNKNOWN]),
                "status_color": STATUS_COLORS.get(status_key, STATUS_COLORS[STATUS_UNKNOWN]),
                "confidence": "window_worst_estimated_country_level",
                "is_estimated": True,
            }

        window_payload.update(
            {
                "snapshot_count": len(window_snapshots),
                "national_score": national_score,
                "national_status": national_status,
                "national_status_label": STATUS_LABELS.get(
                    national_status, STATUS_LABELS[STATUS_UNKNOWN]
                ),
                "latest_observed_at_utc": serialize_snapshot_time(
                    window_snapshots[-1].observed_at_utc
                ),
                "start_utc": serialize_snapshot_time(window_start),
                "end_utc": serialize_snapshot_time(now),
            }
        )
    elif window_score is not None:
        national_score = window_score
        national_status = score_to_status(window_score)
        national_confidence = "window_blended_http_series_country_level"
        partial = bool(snapshot.is_partial) if snapshot else False

        window_payload.update(
            {
                "aggregation": "blended_http_series",
                "score_method": http_requests_window.get("score_method")
                or "blended_latest_avg_worst_from_main_peak_ratio_pct_v1",
                "snapshot_count": len(window_snapshots),
                "national_score": national_score,
                "national_status": national_status,
                "national_status_label": STATUS_LABELS.get(
                    national_status, STATUS_LABELS[STATUS_UNKNOWN]
                ),
                "start_utc": window_start_utc,
                "end_utc": window_end_utc,
                "latest_observed_at_utc": window_latest_utc,
                "http_series_points": len(window_series_main),
                "max_drop_from_peak_pct": http_requests_window.get(
                    "max_drop_from_peak_pct"
                ),
            }
        )
    elif snapshot:
        national_score = snapshot.score
        national_status = score_to_status(snapshot.score)
        national_confidence = snapshot.confidence or "country_level"
        partial = bool(snapshot.is_partial)

        for row in snapshot.provinces:
            province_name = _canonical_province_name(row.province)
            if not province_name:
                continue
            status_key = score_to_status(row.score)
            status_by_province[province_name] = {
                "province": province_name,
                "score": row.score,
                "status": status_key,
                "status_label": STATUS_LABELS.get(status_key, STATUS_LABELS[STATUS_UNKNOWN]),
                "status_color": STATUS_COLORS.get(status_key, STATUS_COLORS[STATUS_UNKNOWN]),
                "confidence": row.confidence or "estimated_country_level",
                "is_estimated": True,
            }
            province_names.add(province_name)

        window_payload.update(
            {
                "snapshot_count": 1,
                "national_score": national_score,
                "national_status": national_status,
                "national_status_label": STATUS_LABELS.get(
                    national_status, STATUS_LABELS[STATUS_UNKNOWN]
                ),
                "latest_observed_at_utc": serialize_snapshot_time(snapshot.observed_at_utc),
                "start_utc": serialize_snapshot_time(window_start),
                "end_utc": serialize_snapshot_time(now),
            }
        )

    province_items = []
    for province in sorted(province_names):
        state = status_by_province.get(province)
        if not state:
            status_key = national_status if national_score is not None else STATUS_UNKNOWN
            state = {
                "province": province,
                "score": national_score,
                "status": status_key,
                "status_label": STATUS_LABELS.get(status_key, STATUS_LABELS[STATUS_UNKNOWN]),
                "status_color": STATUS_COLORS.get(status_key, STATUS_COLORS[STATUS_UNKNOWN]),
                "confidence": national_confidence,
                "is_estimated": True,
            }
            status_by_province[province] = state
        province_items.append(state)

    enriched_geojson = enrich_geojson_with_status(geojson, status_by_province)
    http_requests_24h = (
        http_requests_window
        if window_hours == 24
        else _build_http_requests_24h_summary()
    )
    cloudflare_radar = _build_cloudflare_radar_summary(window_hours=window_hours)

    return jsonify(
        {
            "snapshot": snapshot_payload,
            "stale": stale,
            "is_partial": partial,
            "has_geojson": bool((enriched_geojson.get("features") or [])),
            "provinces": province_items,
            "geojson": enriched_geojson,
            "window": window_payload,
            "http_requests_window": http_requests_window,
            "http_requests_window_by_province": window_by_province,
            "http_requests_24h": http_requests_24h,
            "cloudflare_radar": cloudflare_radar,
            "source": {
                "name": "Cloudflare Radar",
                "url": "https://radar.cloudflare.com/",
                "label": "Hecho con tecnologia de Cloudflare Radar",
            },
            "refresh_seconds": int(current_app.config.get("CONNECTIVITY_FRONTEND_REFRESH_SECONDS", 300)),
        }
    )


@api_bp.route("/connectivity/debug")
@limiter.limit("30/minute")
def connectivity_debug():
    if not _is_admin_user():
        return jsonify({"error": "Acceso denegado"}), 403

    now = datetime.utcnow()
    debug_window_hours = _parse_connectivity_window_hours()
    stale_after_hours = int(current_app.config.get("CONNECTIVITY_STALE_AFTER_HOURS", 8))
    stale_threshold = timedelta(hours=max(stale_after_hours, 1))

    snapshot = (
        ConnectivitySnapshot.query.options(selectinload(ConnectivitySnapshot.provinces))
        .order_by(ConnectivitySnapshot.observed_at_utc.desc(), ConnectivitySnapshot.id.desc())
        .first()
    )
    latest_runs = (
        ConnectivityIngestionRun.query.order_by(
            ConnectivityIngestionRun.started_at_utc.desc(),
            ConnectivityIngestionRun.id.desc(),
        )
        .limit(10)
        .all()
    )

    geojson = load_province_geojson()
    geojson_names = set(province_names_from_geojson(geojson))
    geo_diagnostic = diagnose_province_geojson()

    snapshot_payload = None
    snapshot_stale = True
    province_rows = []
    if snapshot:
        snapshot_stale = not snapshot.fetched_at_utc or (now - snapshot.fetched_at_utc) > stale_threshold
        province_rows = list(snapshot.provinces or [])
        snapshot_payload = {
            "id": snapshot.id,
            "observed_at_utc": serialize_snapshot_time(snapshot.observed_at_utc),
            "fetched_at_utc": serialize_snapshot_time(snapshot.fetched_at_utc),
            "traffic_value": snapshot.traffic_value,
            "baseline_value": snapshot.baseline_value,
            "score": snapshot.score,
            "status": snapshot.status,
            "is_partial": bool(snapshot.is_partial),
            "confidence": snapshot.confidence,
            "method": snapshot.method,
            "stale": snapshot_stale,
            "province_rows_count": len(province_rows),
        }

    province_status_names = {row.province for row in province_rows if row.province}
    missing_geo_for_status = sorted(province_status_names - geojson_names)
    missing_status_for_geo = sorted(geojson_names - province_status_names)

    runs_payload = []
    for run in latest_runs:
        payload_summary = None
        payload_parse_error = None
        if run.payload_json:
            try:
                payload_obj = json.loads(run.payload_json)
                payload_summary = _connectivity_payload_summary(payload_obj)
            except Exception as exc:
                payload_parse_error = str(exc)

        runs_payload.append(
            {
                "id": run.id,
                "status": run.status,
                "attempt_count": run.attempt_count,
                "scheduled_for_utc": serialize_snapshot_time(run.scheduled_for_utc),
                "started_at_utc": serialize_snapshot_time(run.started_at_utc),
                "finished_at_utc": serialize_snapshot_time(run.finished_at_utc),
                "error_message": (run.error_message or "")[:500] or None,
                "payload_parse_error": payload_parse_error,
                "payload_summary": payload_summary,
            }
        )

    diagnostics = {
        "generated_at_utc": serialize_snapshot_time(now),
        "config": {
            "api_url": current_app.config.get("CLOUDFLARE_RADAR_HTTP_TIMESERIES_URL"),
            "radar_api_base_url": current_app.config.get("CLOUDFLARE_RADAR_API_BASE_URL"),
            "cf_api_token_configured": bool(_cf_api_token()),
            "cf_api_token_preview": _mask_secret(_cf_api_token()),
            "connectivity_fetch_delay_seconds": int(current_app.config.get("CONNECTIVITY_FETCH_DELAY_SECONDS", 120)),
            "connectivity_fetch_timeout_seconds": int(current_app.config.get("CONNECTIVITY_FETCH_TIMEOUT_SECONDS", 30)),
            "connectivity_alert_active_max_age_hours": int(
                current_app.config.get("CONNECTIVITY_ALERT_ACTIVE_MAX_AGE_HOURS", 24)
            ),
            "connectivity_stale_after_hours": stale_after_hours,
            "connectivity_frontend_refresh_seconds": int(
                current_app.config.get("CONNECTIVITY_FRONTEND_REFRESH_SECONDS", 300)
            ),
        },
        "geojson": {
            "has_geojson_features": bool((geojson.get("features") or [])),
            "geojson_feature_count": len(geojson.get("features") or []),
            "geojson_province_name_count": len(geojson_names),
            "diagnostic": geo_diagnostic,
        },
        "window_probe": {
            "hours": debug_window_hours,
            "http_requests_window": _build_http_requests_window_summary(debug_window_hours),
            "cloudflare_radar": _build_cloudflare_radar_summary(window_hours=debug_window_hours),
        },
        "snapshot": snapshot_payload,
        "ingestion_runs": runs_payload,
        "consistency": {
            "status_provinces_without_geometry": missing_geo_for_status,
            "geometry_provinces_without_status": missing_status_for_geo,
            "status_geometry_overlap_count": len(province_status_names & geojson_names),
            "likely_reasons_if_not_drawn": [
                "No existe snapshot en BD" if not snapshot else None,
                "Snapshot existe pero esta stale (sin datos recientes)" if snapshot_stale else None,
                "GeoJSON provincial vacio o ruta incorrecta"
                if not (geojson.get("features") or [])
                else None,
                "Nombres de provincias no coinciden entre BD y GeoJSON"
                if province_rows and not (province_status_names & geojson_names)
                else None,
            ],
        },
    }
    diagnostics["consistency"]["likely_reasons_if_not_drawn"] = [
        item for item in diagnostics["consistency"]["likely_reasons_if_not_drawn"] if item
    ]

    if _truthy_param(request.args.get("probe")):
        diagnostics["cloudflare_probe"] = _cloudflare_probe()

    return jsonify(diagnostics)


@api_bp.route("/protests/geojson")
@limiter.limit("120/minute")
def protests_geojson():
    now = datetime.utcnow()
    today_utc = now.date()
    filters = _parse_protest_filters()
    mode = filters["mode"]

    province = (request.args.get("province") or "").strip()
    municipality = (request.args.get("municipality") or "").strip()
    source_name = (request.args.get("source") or "").strip()

    min_conf_raw = (request.args.get("min_confidence") or "").strip()
    min_conf_default = protest_min_confidence_to_show()
    confidence_filter_applied = bool(min_conf_raw)
    try:
        min_confidence = max(0.0, min(100.0, float(min_conf_raw))) if min_conf_raw else min_conf_default
    except Exception:
        min_confidence = min_conf_default
        confidence_filter_applied = False

    include_hidden = _is_admin_user() and _truthy_param(request.args.get("include_hidden"))

    base_query = ProtestEvent.query
    base_query = base_query.filter(ProtestEvent.review_status != "deleted_manual")
    if not include_hidden:
        base_query = base_query.filter(ProtestEvent.visible_on_map.is_(True))
    base_query = base_query.filter(
        ProtestEvent.source_url.isnot(None),
        ProtestEvent.source_url != "",
    )
    if confidence_filter_applied:
        base_query = base_query.filter(
            or_(
                ProtestEvent.review_status == "approved_manual",
                ProtestEvent.confidence_score >= min_confidence,
            )
        )

    if province:
        base_query = base_query.filter(ProtestEvent.matched_province == province)
    if municipality:
        base_query = base_query.filter(ProtestEvent.matched_municipality == municipality)
    if source_name:
        base_query = base_query.filter(ProtestEvent.source_name == source_name)

    timeline_start_day = db.session.query(func.min(ProtestEvent.published_day_utc)).scalar()
    if timeline_start_day is None:
        first_run_started = db.session.query(func.min(ProtestIngestionRun.started_at_utc)).scalar()
        if first_run_started:
            timeline_start_day = first_run_started.date()
    timeline_end_day = today_utc
    if timeline_start_day is None:
        timeline_start_day = today_utc

    if mode == "range":
        start_day = filters["start"]
        end_day = filters["end"]
        start_dt = datetime.combine(start_day, datetime.min.time())
        end_dt = datetime.combine(end_day + timedelta(days=1), datetime.min.time())
        scoped_query = base_query.filter(
            ProtestEvent.source_published_at_utc >= start_dt,
            ProtestEvent.source_published_at_utc < end_dt,
        )
    else:
        selected_day = filters["day"]
        start_dt = datetime.combine(selected_day, datetime.min.time())
        end_dt = datetime.combine(selected_day + timedelta(days=1), datetime.min.time())
        scoped_query = base_query.filter(
            ProtestEvent.source_published_at_utc >= start_dt,
            ProtestEvent.source_published_at_utc < end_dt,
        )

    rows = (
        scoped_query.order_by(ProtestEvent.source_published_at_utc.asc(), ProtestEvent.id.asc())
        .limit(5000)
        .all()
    )

    feature_rows = []
    for row in rows:
        feature = _build_protest_feature(row)
        if feature:
            feature_rows.append(feature)

    day_counts_rows = (
        base_query.with_entities(
            ProtestEvent.published_day_utc.label("day"),
            func.count(ProtestEvent.id).label("count"),
        )
        .group_by(ProtestEvent.published_day_utc)
        .order_by(ProtestEvent.published_day_utc.asc())
        .all()
    )
    day_counts = [
        {
            "day": _day_to_str(item.day),
            "count": int(item.count or 0),
        }
        for item in day_counts_rows
        if item.day is not None
    ]

    latest_run = (
        ProtestIngestionRun.query.order_by(
            ProtestIngestionRun.started_at_utc.desc(),
            ProtestIngestionRun.id.desc(),
        )
        .limit(1)
        .first()
    )

    payload = {
        "type": "FeatureCollection",
        "features": feature_rows,
        "events_total": len(rows),
        "features_total": len(feature_rows),
        "filters": {
            "mode": mode,
            "min_confidence": min_confidence,
            "min_confidence_applied": confidence_filter_applied,
            "province": province or None,
            "municipality": municipality or None,
            "source": source_name or None,
            "include_hidden": include_hidden,
        },
        "timeline": {
            "start_day_utc": _day_to_str(timeline_start_day),
            "end_day_utc": _day_to_str(timeline_end_day),
            "selected_day_utc": _day_to_str(filters.get("day")),
            "selected_start_day_utc": _day_to_str(filters.get("start")),
            "selected_end_day_utc": _day_to_str(filters.get("end")),
            "day_counts": day_counts,
        },
        "range": {
            "start_utc": start_dt.isoformat() + "Z",
            "end_utc": end_dt.isoformat() + "Z",
        },
        "source": {
            "name": "RSS configurados",
            "label": "Eventos con enlace a publicacion original",
        },
        "refresh_seconds": protest_frontend_refresh_seconds(),
        "latest_ingestion": {
            "id": latest_run.id if latest_run else None,
            "status": latest_run.status if latest_run else None,
            "started_at_utc": serialize_snapshot_time(latest_run.started_at_utc) if latest_run else None,
            "finished_at_utc": serialize_snapshot_time(latest_run.finished_at_utc) if latest_run else None,
        },
    }
    return jsonify(payload)


@api_bp.route("/protests/debug")
@limiter.limit("30/minute")
def protests_debug():
    if not _is_admin_user():
        return jsonify({"error": "Acceso denegado"}), 403

    total_events = db.session.query(func.count(ProtestEvent.id)).scalar() or 0
    visible_events = (
        db.session.query(func.count(ProtestEvent.id))
        .filter(ProtestEvent.visible_on_map.is_(True))
        .scalar()
        or 0
    )
    with_coords = (
        db.session.query(func.count(ProtestEvent.id))
        .filter(
            ProtestEvent.latitude.isnot(None),
            ProtestEvent.longitude.isnot(None),
        )
        .scalar()
        or 0
    )
    without_source = (
        db.session.query(func.count(ProtestEvent.id))
        .filter((ProtestEvent.source_url.is_(None)) | (ProtestEvent.source_url == ""))
        .scalar()
        or 0
    )

    latest_runs = (
        ProtestIngestionRun.query.order_by(
            ProtestIngestionRun.started_at_utc.desc(),
            ProtestIngestionRun.id.desc(),
        )
        .limit(10)
        .all()
    )

    runs_payload = []
    for run in latest_runs:
        payload_preview = None
        if run.payload_json:
            try:
                payload_obj = json.loads(run.payload_json)
                payload_preview = {
                    "feeds": list((payload_obj.get("feeds") or {}).keys())[:6],
                    "errors": (payload_obj.get("errors") or [])[:6],
                }
            except Exception:
                payload_preview = {"error": "payload_json invalido"}
        runs_payload.append(
            {
                "id": run.id,
                "status": run.status,
                "started_at_utc": serialize_snapshot_time(run.started_at_utc),
                "finished_at_utc": serialize_snapshot_time(run.finished_at_utc),
                "feed_count": run.feed_count,
                "fetched_items": run.fetched_items,
                "parsed_items": run.parsed_items,
                "stored_items": run.stored_items,
                "updated_items": run.updated_items,
                "deduped_items": run.deduped_items,
                "hidden_items": run.hidden_items,
                "error_message": (run.error_message or "")[:500] or None,
                "payload_preview": payload_preview,
            }
        )

    return jsonify(
        {
            "generated_at_utc": serialize_snapshot_time(datetime.utcnow()),
            "config": {
                "protest_rss_feeds": protest_rss_feed_urls(),
                "protest_rss_feeds_mode": "db_first_with_json_fallback",
                "protest_fetch_timeout_seconds": protest_fetch_timeout_seconds(),
                "protest_fetch_interval_seconds": protest_fetch_interval_seconds(),
                "protest_frontend_refresh_seconds": protest_frontend_refresh_seconds(),
                "protest_min_confidence_to_show": protest_min_confidence_to_show(),
                "protest_require_source_url": protest_require_source_url(),
                "protest_allow_unresolved_to_map": protest_allow_unresolved_location_on_map(),
                "geojson_provinces_path": current_app.config.get("GEOJSON_PROVINCES_PATH"),
                "geojson_municipalities_path": current_app.config.get("GEOJSON_MUNICIPALITIES_PATH"),
                "geojson_localities_path": current_app.config.get("GEOJSON_LOCALITIES_PATH"),
            },
            "counts": {
                "total_events": int(total_events),
                "visible_events": int(visible_events),
                "events_with_coords": int(with_coords),
                "events_without_source": int(without_source),
            },
            "runs": runs_payload,
        }
    )


@api_bp.route("/protests/<int:event_id>", methods=["DELETE"])
@limiter.limit("20/minute; 120/day")
def delete_protest_event(event_id):
    if not _is_admin_user():
        return jsonify({"ok": False, "error": "No autorizado."}), 403

    event = ProtestEvent.query.get(event_id)
    if not event:
        return jsonify({"ok": False, "error": "Evento no encontrado."}), 404

    db.session.delete(event)
    db.session.commit()
    return jsonify({"ok": True, "id": event_id, "status": "deleted"})


@api_bp.route("/push/subscribe", methods=["POST"])
@limiter.limit("5/minute; 60/day")
def push_subscribe():
    if not _push_enabled():
        return jsonify({"error": "Push deshabilitado"}), 503

    payload = request.get_json(silent=True) or {}
    endpoint = (payload.get("endpoint") or "").strip()
    keys = payload.get("keys") or {}
    p256dh = (keys.get("p256dh") or "").strip()
    auth = (keys.get("auth") or "").strip()

    if not endpoint or not p256dh or not auth:
        return jsonify({"error": "Suscripción inválida"}), 400
    if len(endpoint) > 2000 or len(p256dh) > 255 or len(auth) > 255:
        return jsonify({"error": "Suscripción inválida"}), 400

    user_agent = (request.headers.get("User-Agent") or "")[:255]
    subscription = PushSubscription.query.filter_by(endpoint=endpoint).first()
    if subscription:
        subscription.p256dh = p256dh
        subscription.auth = auth
        subscription.active = True
        subscription.user_agent = user_agent
    else:
        subscription = PushSubscription(
            endpoint=endpoint,
            p256dh=p256dh,
            auth=auth,
            user_agent=user_agent,
            active=True,
        )
        db.session.add(subscription)

    db.session.commit()
    return jsonify({"status": "ok"})


@api_bp.route("/push/unsubscribe", methods=["POST"])
@limiter.limit("10/minute; 120/day")
def push_unsubscribe():
    payload = request.get_json(silent=True) or {}
    endpoint = (payload.get("endpoint") or "").strip()
    if not endpoint:
        return jsonify({"error": "Suscripción inválida"}), 400

    subscription = PushSubscription.query.filter_by(endpoint=endpoint).first()
    if subscription:
        subscription.active = False
        subscription.updated_at = datetime.utcnow()
        db.session.commit()
    return jsonify({"status": "ok"})


@api_bp.route("/categories")
def categories():
    items = Category.query.order_by(Category.id.asc()).all()
    return jsonify(
        [
            {"id": c.id, "name": c.name, "slug": c.slug, "description": c.description}
            for c in items
        ]
    )


def _serialize_post_repressor(post: Post, include_relationships: bool = False):
    if not getattr(post, "repressor", None):
        return None
    return serialize_repressor(post.repressor, include_relationships=include_relationships)


def _coerce_link_value(raw_link):
    if isinstance(raw_link, str):
        value = raw_link.strip()
        return value or None

    if isinstance(raw_link, dict):
        for key in ("url", "href", "link", "value"):
            candidate = raw_link.get(key)
            if not isinstance(candidate, str):
                continue
            value = candidate.strip()
            if value:
                return value

    return None


def _deserialize_links_json(links_json):
    if not links_json:
        return []

    try:
        parsed = json.loads(links_json)
    except (TypeError, ValueError):
        return []

    if isinstance(parsed, list):
        return [value for value in (_coerce_link_value(item) for item in parsed) if value]

    single = _coerce_link_value(parsed)
    return [single] if single else []


@api_bp.route("/posts")
def posts():
    category_id = request.args.get("category_id")
    limit = request.args.get("limit")
    query = Post.query.options(
        selectinload(Post.media),
        selectinload(Post.repressor),
    ).filter_by(status="approved")
    if category_id:
        query = query.filter_by(category_id=int(category_id))

    query = query.order_by(Post.created_at.desc())
    if limit:
        try:
            query = query.limit(int(limit))
        except ValueError:
            pass

    items = query.all()
    verified_ids = _get_verified_post_ids([p.id for p in items])
    return jsonify(
        [
            {
                "id": p.id,
                "title": p.title,
                "description": p.description,
                "latitude": float(p.latitude),
                "longitude": float(p.longitude),
                "address": p.address,
                "province": p.province,
                "municipality": p.municipality,
                "movement_at": p.movement_at.isoformat() if p.movement_at else None,
                "repressor_name": p.repressor_name,
                "repressor_id": p.repressor_id,
                "other_type": p.other_type,
                "created_at": p.created_at.isoformat(),
                "anon": f"Anon-{p.author.anon_code}" if p.author and p.author.anon_code else "Anon",
                "polygon_geojson": p.polygon_geojson,
                "links": _deserialize_links_json(p.links_json),
                "media": get_media_payload(p)[:4],
                "verify_count": p.verify_count or 0,
                "verified_by_me": p.id in verified_ids,
                "repressor": _serialize_post_repressor(p, include_relationships=False),
                "category": {
                    "id": p.category.id,
                    "name": p.category.name,
                    "slug": p.category.slug,
                },
            }
            for p in items
        ]
    )


def _serialize_post(post: Post):
    return {
        "id": post.id,
        "title": post.title,
        "description": post.description,
        "latitude": float(post.latitude),
        "longitude": float(post.longitude),
        "address": post.address,
        "province": post.province,
        "municipality": post.municipality,
        "movement_at": post.movement_at.isoformat() if post.movement_at else None,
        "repressor_name": post.repressor_name,
        "repressor_id": post.repressor_id,
        "other_type": post.other_type,
        "status": post.status,
        "polygon_geojson": post.polygon_geojson,
        "links": _deserialize_links_json(post.links_json),
        "media": get_media_payload(post),
        "verify_count": post.verify_count or 0,
        "repressor": _serialize_post_repressor(post, include_relationships=True),
        "created_at": post.created_at.isoformat() if post.created_at else None,
        "updated_at": post.updated_at.isoformat() if post.updated_at else None,
        "anon": f"Anon-{post.author.anon_code}" if post.author and post.author.anon_code else "Anon",
        "category": {
            "id": post.category.id,
            "name": post.category.name,
            "slug": post.category.slug,
        }
        if post.category
        else None,
    }


@api_bp.route("/v1/reports")
@limiter.limit("120/minute")
def reports_v1():
    category_id = request.args.get("category_id")
    province = (request.args.get("province") or "").strip()
    municipality = (request.args.get("municipality") or "").strip()
    status = (request.args.get("status") or "approved").strip().lower()

    allowed_statuses = {"pending", "approved", "rejected", "hidden", "deleted"}
    if status not in allowed_statuses:
        status = "approved"

    if status != "approved" and not _is_admin_user():
        status = "approved"

    query = Post.query.options(
        selectinload(Post.media),
        selectinload(Post.category),
        selectinload(Post.author),
        selectinload(Post.repressor).selectinload(Repressor.crimes),
        selectinload(Post.repressor).selectinload(Repressor.types),
    )
    query = query.filter(Post.status == status)

    if category_id:
        try:
            query = query.filter(Post.category_id == int(category_id))
        except ValueError:
            pass

    if province:
        query = query.filter(Post.province.ilike(province))
    if municipality:
        query = query.filter(Post.municipality.ilike(municipality))

    try:
        page = max(int(request.args.get("page", 1)), 1)
    except ValueError:
        page = 1
    try:
        per_page = max(int(request.args.get("per_page", 50)), 1)
    except ValueError:
        per_page = 50
    per_page = min(per_page, 100)

    total = query.count()
    pages = max(math.ceil(total / per_page), 1) if per_page else 1
    items = (
        query.order_by(Post.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return jsonify(
        {
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": pages,
            "has_next": page < pages,
            "has_prev": page > 1,
            "items": [_serialize_post(p) for p in items],
        }
    )


@api_bp.route("/v1/reports/<int:post_id>")
@limiter.limit("120/minute")
def report_detail_v1(post_id):
    query = Post.query.options(
        selectinload(Post.media),
        selectinload(Post.category),
        selectinload(Post.author),
        selectinload(Post.repressor).selectinload(Repressor.crimes),
        selectinload(Post.repressor).selectinload(Repressor.types),
    )
    post = query.get_or_404(post_id)
    if post.status != "approved" and not _is_admin_user():
        return jsonify({"error": "No autorizado."}), 403
    return jsonify(_serialize_post(post))


@api_bp.route("/v1/categories")
def categories_v1():
    return categories()


def _serialize_repressor_residence_report(report: RepressorResidenceReport):
    return {
        "id": report.id,
        "repressor_id": report.repressor_id,
        "status": report.status,
        "latitude": float(report.latitude) if report.latitude is not None else None,
        "longitude": float(report.longitude) if report.longitude is not None else None,
        "address": report.address,
        "province": report.province,
        "municipality": report.municipality,
        "message": report.message,
        "source_image_url": report.source_image_url,
        "created_post_id": report.created_post_id,
        "rejection_reason": report.rejection_reason,
        "reviewed_at": report.reviewed_at.isoformat() if report.reviewed_at else None,
        "created_at": report.created_at.isoformat() if report.created_at else None,
        "updated_at": report.updated_at.isoformat() if report.updated_at else None,
    }


@api_bp.route("/v1/repressors")
@limiter.limit("120/minute")
def repressors_v1():
    q = (request.args.get("q") or "").strip()
    province = (request.args.get("province") or "").strip()
    municipality = (request.args.get("municipality") or "").strip()

    query = Repressor.query.options(
        selectinload(Repressor.crimes),
        selectinload(Repressor.types),
    )

    if q:
        token = f"%{q}%"
        filters = [
            Repressor.name.ilike(token),
            Repressor.lastname.ilike(token),
            Repressor.nickname.ilike(token),
            Repressor.institution_name.ilike(token),
            Repressor.campus_name.ilike(token),
        ]
        if q.isdigit():
            filters.append(Repressor.external_id == int(q))
        query = query.filter(or_(*filters))

    if province:
        query = query.filter(Repressor.province_name.ilike(province))
    if municipality:
        query = query.filter(Repressor.municipality_name.ilike(municipality))

    try:
        page = max(int(request.args.get("page", 1)), 1)
    except ValueError:
        page = 1
    try:
        per_page = max(int(request.args.get("per_page", 50)), 1)
    except ValueError:
        per_page = 50
    per_page = min(per_page, 100)

    total = query.count()
    pages = max(math.ceil(total / per_page), 1) if per_page else 1
    items = (
        query.order_by(Repressor.updated_at.desc(), Repressor.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return jsonify(
        {
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": pages,
            "has_next": page < pages,
            "has_prev": page > 1,
            "items": [serialize_repressor(item, include_relationships=True) for item in items],
        }
    )


@api_bp.route("/v1/repressors/<int:repressor_id>")
@limiter.limit("120/minute")
def repressor_detail_v1(repressor_id):
    repressor = (
        Repressor.query.options(
            selectinload(Repressor.crimes),
            selectinload(Repressor.types),
        )
        .filter_by(id=repressor_id)
        .first_or_404()
    )
    approved_residence_reports = (
        RepressorResidenceReport.query.filter_by(
            repressor_id=repressor.id,
            status="approved",
        )
        .order_by(RepressorResidenceReport.created_at.desc())
        .limit(50)
        .all()
    )
    payload = serialize_repressor(repressor, include_relationships=True)
    payload["approved_residence_reports"] = [
        _serialize_repressor_residence_report(item)
        for item in approved_residence_reports
    ]
    return jsonify(payload)


@api_bp.route("/v1/prisoners")
@limiter.limit("120/minute")
def prisoners_v1():
    q = (request.args.get("q") or "").strip()
    province = canonicalize_province_name((request.args.get("province") or "").strip()) or ""
    municipality = (request.args.get("municipality") or "").strip()
    prison = (request.args.get("prison") or "").strip()

    query = Prisoner.query
    if q:
        token = f"%{q}%"
        filters = [
            Prisoner.name.ilike(token),
            Prisoner.lastname.ilike(token),
            Prisoner.prison_name.ilike(token),
            Prisoner.penal_status.ilike(token),
            Prisoner.offense_types.ilike(token),
        ]
        if q.lstrip("-").isdigit():
            filters.append(Prisoner.external_id == int(q))
        query = query.filter(or_(*filters))

    if province:
        query = query.filter(Prisoner.province_name == province)
    if municipality:
        query = query.filter(Prisoner.municipality_name == municipality)
    if prison:
        query = query.filter(Prisoner.prison_name == prison)

    try:
        page = max(int(request.args.get("page", 1)), 1)
    except ValueError:
        page = 1
    try:
        per_page = max(int(request.args.get("per_page", 50)), 1)
    except ValueError:
        per_page = 50
    per_page = min(per_page, 100)

    total = query.count()
    pages = max(math.ceil(total / per_page), 1) if per_page else 1
    items = (
        query.order_by(Prisoner.updated_at.desc(), Prisoner.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return jsonify(
        {
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": pages,
            "has_next": page < pages,
            "has_prev": page > 1,
            "items": [serialize_prisoner(item, include_source=False) for item in items],
        }
    )


@api_bp.route("/v1/prisoners/<int:prisoner_id>")
@limiter.limit("120/minute")
def prisoner_detail_v1(prisoner_id):
    prisoner = Prisoner.query.filter_by(id=prisoner_id).first_or_404()
    return jsonify(serialize_prisoner(prisoner, include_source=True))


@api_bp.route("/v1/prisoners/stats")
@limiter.limit("120/minute")
def prisoner_stats_v1():
    requested_province = canonicalize_province_name((request.args.get("province") or "").strip()) or None
    requested_municipality = (request.args.get("municipality") or "").strip() or None
    requested_prison = (request.args.get("prison") or "").strip() or None
    requested_province_values = (
        _matching_stored_province_values(Prisoner.province_name, requested_province)
        if requested_province
        else []
    )

    query = db.session.query(
        Prisoner.province_name,
        Prisoner.municipality_name,
        Prisoner.prison_name,
        func.count(Prisoner.id),
    )
    if requested_province:
        if requested_province_values:
            query = query.filter(Prisoner.province_name.in_(requested_province_values))
        else:
            query = query.filter(Prisoner.province_name == requested_province)
    if requested_municipality:
        query = query.filter(Prisoner.municipality_name == requested_municipality)
    if requested_prison:
        query = query.filter(Prisoner.prison_name == requested_prison)
    raw_rows = query.group_by(
        Prisoner.province_name,
        Prisoner.municipality_name,
        Prisoner.prison_name,
    ).all()

    total = 0
    by_province: dict[str, dict[str, int | str | None]] = {}
    by_province_municipality: dict[str, dict[str, int | str | None]] = {}
    by_prison: dict[str, dict[str, int | str | None]] = {}
    for raw_province, raw_municipality, raw_prison, raw_count in raw_rows:
        count = int(raw_count or 0)
        if count <= 0:
            continue
        province_name, municipality_name = canonicalize_location_names(
            raw_province,
            raw_municipality,
        )
        prison_name = str(raw_prison or "").strip() or None

        total += count
        province_key = normalize_location_key(province_name) or "__nd__"
        province_bucket = by_province.get(province_key)
        if province_bucket is None:
            province_bucket = {"province": province_name, "count": 0}
            by_province[province_key] = province_bucket
        province_bucket["count"] = int(province_bucket["count"] or 0) + count

        municipality_key = normalize_location_key(municipality_name) or "__nd__"
        pair_key = f"{province_key}|{municipality_key}"
        pair_bucket = by_province_municipality.get(pair_key)
        if pair_bucket is None:
            pair_bucket = {
                "province": province_name,
                "municipality": municipality_name,
                "count": 0,
            }
            by_province_municipality[pair_key] = pair_bucket
        pair_bucket["count"] = int(pair_bucket["count"] or 0) + count

        if prison_name:
            prison_key = normalize_location_key(prison_name) or prison_name.lower()
            prison_bucket = by_prison.get(prison_key)
            if prison_bucket is None:
                prison_bucket = {
                    "prison": prison_name,
                    "province": province_name,
                    "municipality": municipality_name,
                    "count": 0,
                }
                by_prison[prison_key] = prison_bucket
            prison_bucket["count"] = int(prison_bucket["count"] or 0) + count

    province_rows = sorted(
        by_province.values(),
        key=lambda item: (-int(item["count"] or 0), str(item["province"] or "")),
    )
    municipality_rows = sorted(
        by_province_municipality.values(),
        key=lambda item: (
            -int(item["count"] or 0),
            str(item["province"] or ""),
            str(item["municipality"] or ""),
        ),
    )
    prison_rows = sorted(
        by_prison.values(),
        key=lambda item: (
            -int(item["count"] or 0),
            str(item["prison"] or ""),
        ),
    )

    return jsonify(
        {
            "total_prisoners": total,
            "by_province": [
                {"province": row["province"], "count": int(row["count"] or 0)}
                for row in province_rows
            ],
            "by_province_municipality": [
                {
                    "province": row["province"],
                    "municipality": row["municipality"],
                    "count": int(row["count"] or 0),
                }
                for row in municipality_rows
            ],
            "by_prison": [
                {
                    "prison": row["prison"],
                    "province": row["province"],
                    "municipality": row["municipality"],
                    "count": int(row["count"] or 0),
                }
                for row in prison_rows
            ],
        }
    )


@api_bp.route("/v1/ais/cuba-targets")
@limiter.limit("120/minute")
def ais_cuba_targets_v1():
    if not _is_admin_user():
        return jsonify({"error": "Acceso denegado"}), 403

    try:
        requested_limit = int(request.args.get("limit", get_ais_max_target_vessels()))
    except Exception:
        requested_limit = get_ais_max_target_vessels()
    limit = max(1, min(requested_limit, 5000))

    try:
        min_confidence = float(request.args.get("min_confidence", "0") or 0)
    except Exception:
        min_confidence = 0.0
    min_confidence = max(0.0, min(min_confidence, 1.0))

    query = AISCubaTargetVessel.query.filter(
        AISCubaTargetVessel.latitude.isnot(None),
        AISCubaTargetVessel.longitude.isnot(None),
        AISCubaTargetVessel.match_confidence >= min_confidence,
    ).order_by(
        AISCubaTargetVessel.match_confidence.desc(),
        AISCubaTargetVessel.last_seen_at_utc.desc().nullslast(),
        AISCubaTargetVessel.updated_at.desc().nullslast(),
    )
    rows = query.limit(limit).all()

    points = []
    by_port: dict[str, int] = {}
    for row in rows:
        lat = _safe_float(row.latitude)
        lng = _safe_float(row.longitude)
        if lat is None or lng is None:
            continue

        port_label = str(row.matched_port_name or "Sin puerto").strip() or "Sin puerto"
        by_port[port_label] = by_port.get(port_label, 0) + 1
        points.append(
            {
                "id": row.id,
                "mmsi": row.mmsi,
                "ship_name": row.ship_name,
                "imo": row.imo,
                "call_sign": row.call_sign,
                "vessel_type": row.vessel_type,
                "destination_raw": row.destination_raw,
                "destination_normalized": row.destination_normalized,
                "matched_port_key": row.matched_port_key,
                "matched_port_name": row.matched_port_name,
                "match_confidence": float(row.match_confidence or 0.0),
                "match_reason": row.match_reason,
                "latitude": lat,
                "longitude": lng,
                "sog": _safe_float(row.sog),
                "cog": _safe_float(row.cog),
                "heading": _safe_float(row.heading),
                "navigational_status": row.navigational_status,
                "source_message_type": row.source_message_type,
                "last_seen_at_utc": serialize_snapshot_time(row.last_seen_at_utc),
                "last_position_at_utc": serialize_snapshot_time(row.last_position_at_utc),
                "last_static_at_utc": serialize_snapshot_time(row.last_static_at_utc),
                "updated_at": serialize_snapshot_time(row.updated_at),
            }
        )

    latest_run = (
        AISIngestionRun.query.order_by(
            AISIngestionRun.started_at_utc.desc(),
            AISIngestionRun.id.desc(),
        )
        .limit(1)
        .first()
    )
    stale_after_hours = get_ais_stale_after_hours()
    stale_threshold = timedelta(hours=max(stale_after_hours, 1))
    now = datetime.utcnow()
    stale = True
    if latest_run and latest_run.finished_at_utc:
        stale = (now - latest_run.finished_at_utc) > stale_threshold

    return jsonify(
        {
            "points": points,
            "summary": {
                "total_points": len(points),
                "min_confidence": min_confidence,
                "by_port": [
                    {"port": port, "count": count}
                    for port, count in sorted(
                        by_port.items(),
                        key=lambda item: (-int(item[1]), str(item[0])),
                    )
                ],
            },
            "latest_run": {
                "id": latest_run.id if latest_run else None,
                "status": latest_run.status if latest_run else None,
                "scheduled_for_utc": serialize_snapshot_time(latest_run.scheduled_for_utc)
                if latest_run
                else None,
                "started_at_utc": serialize_snapshot_time(latest_run.started_at_utc)
                if latest_run
                else None,
                "finished_at_utc": serialize_snapshot_time(latest_run.finished_at_utc)
                if latest_run
                else None,
                "total_messages": int(latest_run.total_messages or 0) if latest_run else 0,
                "position_messages": int(latest_run.position_messages or 0) if latest_run else 0,
                "static_messages": int(latest_run.static_messages or 0) if latest_run else 0,
                "matched_messages": int(latest_run.matched_messages or 0) if latest_run else 0,
                "matched_vessels": int(latest_run.matched_vessels or 0) if latest_run else 0,
                "stale_removed": int(latest_run.stale_removed or 0) if latest_run else 0,
                "error_message": latest_run.error_message if latest_run else None,
            },
            "stale": stale,
            "stale_after_hours": stale_after_hours,
            "source": {
                "name": "AISStream",
                "url": "https://aisstream.io/documentation",
            },
            "refresh_seconds": get_ais_frontend_refresh_seconds(),
        }
    )


@api_bp.route("/v1/prisoners/map-layer")
@limiter.limit("120/minute")
def prisoner_map_layer_v1():
    requested_province = canonicalize_province_name((request.args.get("province") or "").strip()) or ""
    requested_municipality = (request.args.get("municipality") or "").strip()
    requested_prison = (request.args.get("prison") or "").strip()
    requested_province_values = (
        _matching_stored_province_values(Prisoner.province_name, requested_province)
        if requested_province
        else []
    )

    base_query = Prisoner.query
    if requested_province:
        if requested_province_values:
            base_query = base_query.filter(Prisoner.province_name.in_(requested_province_values))
        else:
            base_query = base_query.filter(Prisoner.province_name == requested_province)
    if requested_municipality:
        base_query = base_query.filter(Prisoner.municipality_name == requested_municipality)
    if requested_prison:
        base_query = base_query.filter(Prisoner.prison_name == requested_prison)

    rows_query = db.session.query(
        Prisoner.province_name,
        Prisoner.municipality_name,
        Prisoner.prison_name,
        func.count(Prisoner.id),
    )
    if requested_province:
        if requested_province_values:
            rows_query = rows_query.filter(Prisoner.province_name.in_(requested_province_values))
        else:
            rows_query = rows_query.filter(Prisoner.province_name == requested_province)
    if requested_municipality:
        rows_query = rows_query.filter(Prisoner.municipality_name == requested_municipality)
    if requested_prison:
        rows_query = rows_query.filter(Prisoner.prison_name == requested_prison)
    rows = rows_query.group_by(
        Prisoner.province_name,
        Prisoner.municipality_name,
        Prisoner.prison_name,
    ).all()

    buckets = {}
    without_territory_reference = 0
    for raw_province, raw_municipality, raw_prison, raw_count in rows:
        count = int(raw_count or 0)
        if count <= 0:
            continue

        province_name, municipality_name = canonicalize_location_names(
            raw_province,
            raw_municipality,
        )
        prison_name = str(raw_prison or "").strip() or None
        scope = "municipality" if (province_name and municipality_name) else ("province" if province_name else "")
        if not scope:
            without_territory_reference += count
            continue

        province_key = normalize_location_key(province_name) or "__nd__"
        municipality_key = normalize_location_key(municipality_name) if municipality_name else "__nd__"
        bucket_key = f"{scope}|{province_key}|{municipality_key}"
        bucket = buckets.get(bucket_key)
        if bucket is None:
            bucket = {
                "scope": scope,
                "province": province_name,
                "municipality": municipality_name if scope == "municipality" else None,
                "count": 0,
                "prisons": set(),
            }
            buckets[bucket_key] = bucket
        bucket["count"] = int(bucket["count"] or 0) + count
        if prison_name:
            bucket["prisons"].add(prison_name)

    points = []
    for bucket in buckets.values():
        lat, lng = _resolve_territory_centroid(
            bucket.get("province"),
            bucket.get("municipality"),
        )
        if lat is None or lng is None:
            without_territory_reference += int(bucket.get("count") or 0)
            continue
        points.append(
            {
                "scope": bucket.get("scope"),
                "province": bucket.get("province"),
                "municipality": bucket.get("municipality"),
                "count": int(bucket.get("count") or 0),
                "prisons": sorted(bucket.get("prisons") or []),
                "latitude": lat,
                "longitude": lng,
            }
        )
    points.sort(
        key=lambda item: (
            -int(item.get("count") or 0),
            str(item.get("province") or ""),
            str(item.get("municipality") or ""),
        )
    )

    total_prisoners = int(base_query.count() or 0)
    with_prison_location = int(
        base_query.filter(
            Prisoner.prison_latitude.isnot(None),
            Prisoner.prison_longitude.isnot(None),
        ).count()
        or 0
    )

    province_filter_query = db.session.query(Prisoner.province_name).filter(
        Prisoner.province_name.isnot(None),
        Prisoner.province_name != "",
    )
    province_options = sorted(
        {
            canonicalize_province_name(str(row[0] or "").strip()) or str(row[0] or "").strip()
            for row in province_filter_query.distinct().all()
            if str(row[0] or "").strip()
        }
    )

    municipality_filter_query = db.session.query(Prisoner.municipality_name).filter(
        Prisoner.municipality_name.isnot(None),
        Prisoner.municipality_name != "",
    )
    if requested_province:
        if requested_province_values:
            municipality_filter_query = municipality_filter_query.filter(
                Prisoner.province_name.in_(requested_province_values)
            )
        else:
            municipality_filter_query = municipality_filter_query.filter(
                Prisoner.province_name == requested_province
            )
    municipality_options = sorted(
        {
            str(row[0]).strip()
            for row in municipality_filter_query.distinct().all()
            if str(row[0] or "").strip()
        }
    )

    prison_filter_query = db.session.query(Prisoner.prison_name).filter(
        Prisoner.prison_name.isnot(None),
        Prisoner.prison_name != "",
    )
    if requested_province:
        if requested_province_values:
            prison_filter_query = prison_filter_query.filter(
                Prisoner.province_name.in_(requested_province_values)
            )
        else:
            prison_filter_query = prison_filter_query.filter(
                Prisoner.province_name == requested_province
            )
    if requested_municipality:
        prison_filter_query = prison_filter_query.filter(
            Prisoner.municipality_name == requested_municipality
        )
    prison_options = sorted(
        {
            str(row[0]).strip()
            for row in prison_filter_query.distinct().all()
            if str(row[0] or "").strip()
        }
    )

    return jsonify(
        {
            "points": points,
            "summary": {
                "total_prisoners": total_prisoners,
                "territories_points": len(points),
                "with_prison_location": with_prison_location,
                "without_prison_location": max(total_prisoners - with_prison_location, 0),
                "without_territory_reference": without_territory_reference,
            },
            "filters": {
                "selected_province": requested_province or "",
                "selected_municipality": requested_municipality or "",
                "selected_prison": requested_prison or "",
                "provinces": province_options,
                "municipalities": municipality_options,
                "prisons": prison_options,
            },
        }
    )


@api_bp.route("/v1/prisoners/territory")
@limiter.limit("120/minute")
def prisoners_territory_v1():
    scope = (request.args.get("scope") or "").strip().lower()
    province = (request.args.get("province") or "").strip()
    municipality = (request.args.get("municipality") or "").strip()
    prison = (request.args.get("prison") or "").strip()

    if scope not in {"province", "municipality"}:
        return (
            jsonify({"ok": False, "error": "scope inválido. Usa 'province' o 'municipality'."}),
            400,
        )

    canonical_province, canonical_municipality = canonicalize_location_names(
        province,
        municipality,
    )
    if not canonical_province:
        return jsonify({"ok": False, "error": "province es obligatorio."}), 400
    if scope == "municipality" and not canonical_municipality:
        return jsonify({"ok": False, "error": "municipality es obligatorio para scope=municipality."}), 400

    province_filter_values = _matching_stored_province_values(
        Prisoner.province_name,
        canonical_province,
    )
    if not province_filter_values:
        province_filter_values = [canonical_province]

    query = Prisoner.query
    if scope == "municipality":
        query = query.filter(
            Prisoner.province_name.in_(province_filter_values),
            Prisoner.municipality_name == canonical_municipality,
        )
    else:
        query = query.filter(
            Prisoner.province_name.in_(province_filter_values),
            or_(Prisoner.municipality_name.is_(None), Prisoner.municipality_name == ""),
        )
    if prison:
        query = query.filter(Prisoner.prison_name == prison)

    rows = (
        query.order_by(
            Prisoner.lastname.asc(),
            Prisoner.name.asc(),
            Prisoner.id.asc(),
        )
        .all()
    )
    items = []
    for prisoner in rows:
        items.append(
            {
                "id": prisoner.id,
                "external_id": prisoner.external_id,
                "full_name": prisoner.full_name,
                "province_name": prisoner.province_name,
                "municipality_name": prisoner.municipality_name,
                "prison_name": prisoner.prison_name,
                "prison_latitude": _safe_float(prisoner.prison_latitude),
                "prison_longitude": _safe_float(prisoner.prison_longitude),
                "penal_status": prisoner.penal_status,
                "image_url": prisoner.image_url,
            }
        )

    territory_label = (
        f"{canonical_province} · {canonical_municipality}"
        if scope == "municipality"
        else canonical_province
    )
    return jsonify(
        {
            "ok": True,
            "scope": scope,
            "province": canonical_province,
            "municipality": canonical_municipality if scope == "municipality" else None,
            "territory_label": territory_label,
            "count": len(items),
            "items": items,
        }
    )


@api_bp.route("/v1/repressors/stats")
@limiter.limit("120/minute")
def repressor_stats_v1():
    requested_province = (request.args.get("province") or "").strip()
    requested_province = canonicalize_province_name(requested_province) if requested_province else None

    raw_rows = (
        db.session.query(
            Repressor.province_name,
            Repressor.municipality_name,
            func.count(Repressor.id),
        )
        .group_by(
            Repressor.province_name,
            Repressor.municipality_name,
        )
        .all()
    )

    total = 0
    by_province: dict[str, dict[str, int | str | None]] = {}
    by_province_municipality: dict[str, dict[str, int | str | None]] = {}
    for raw_province, raw_municipality, raw_count in raw_rows:
        count = int(raw_count or 0)
        if count <= 0:
            continue

        province_name, municipality_name = canonicalize_location_names(
            raw_province,
            raw_municipality,
        )
        if requested_province and province_name != requested_province:
            continue

        total += count

        province_key = normalize_location_key(province_name) or "__nd__"
        province_bucket = by_province.get(province_key)
        if province_bucket is None:
            province_bucket = {"province": province_name, "count": 0}
            by_province[province_key] = province_bucket
        province_bucket["count"] = int(province_bucket["count"] or 0) + count

        municipality_key = normalize_location_key(municipality_name) or "__nd__"
        pair_key = f"{province_key}|{municipality_key}"
        pair_bucket = by_province_municipality.get(pair_key)
        if pair_bucket is None:
            pair_bucket = {
                "province": province_name,
                "municipality": municipality_name,
                "count": 0,
            }
            by_province_municipality[pair_key] = pair_bucket
        pair_bucket["count"] = int(pair_bucket["count"] or 0) + count

    province_rows = sorted(
        by_province.values(),
        key=lambda item: (-int(item["count"] or 0), str(item["province"] or "")),
    )
    municipality_rows = sorted(
        by_province_municipality.values(),
        key=lambda item: (
            -int(item["count"] or 0),
            str(item["province"] or ""),
            str(item["municipality"] or ""),
        ),
    )

    return jsonify(
        {
            "total_repressors": total,
            "by_province": [
                {
                    "province": row["province"],
                    "count": int(row["count"] or 0),
                }
                for row in province_rows
            ],
            "by_province_municipality": [
                {
                    "province": row["province"],
                    "municipality": row["municipality"],
                    "count": int(row["count"] or 0),
                }
                for row in municipality_rows
            ],
        }
    )


def _approved_repressor_ids_subquery():
    return (
        db.session.query(
            RepressorResidenceReport.repressor_id.label("repressor_id"),
        )
        .filter(
            RepressorResidenceReport.status == "approved",
            RepressorResidenceReport.repressor_id.isnot(None),
        )
        .distinct()
        .subquery()
    )


@api_bp.route("/v1/repressors/map-layer")
@limiter.limit("120/minute")
def repressor_map_layer_v1():
    approved_reports = (
        RepressorResidenceReport.query.options(
            selectinload(RepressorResidenceReport.repressor).selectinload(Repressor.types)
        )
        .filter(RepressorResidenceReport.status == "approved")
        .order_by(
            RepressorResidenceReport.created_at.desc(),
            RepressorResidenceReport.id.desc(),
        )
        .all()
    )

    confirmed_residences = []
    for report in approved_reports:
        lat = _safe_float(report.latitude)
        lng = _safe_float(report.longitude)
        if lat is None or lng is None:
            continue

        repressor = report.repressor
        report_province, report_municipality = canonicalize_location_names(
            report.province or (repressor.province_name if repressor else None),
            report.municipality or (repressor.municipality_name if repressor else None),
        )
        type_names = []
        if repressor:
            type_names = [
                str(item.name or "").strip()
                for item in (repressor.types or [])
                if str(item.name or "").strip()
            ]

        confirmed_residences.append(
            {
                "report_id": report.id,
                "repressor_id": repressor.id if repressor else None,
                "repressor_name": repressor.full_name if repressor else "",
                "repressor_image_url": repressor.image_url if repressor else None,
                "repressor_type_names": type_names,
                "province": report_province,
                "municipality": report_municipality,
                "address": report.address,
                "message": report.message,
                "latitude": lat,
                "longitude": lng,
                "created_at": report.created_at.isoformat() if report.created_at else None,
            }
        )

    approved_repressor_ids_subquery = _approved_repressor_ids_subquery()

    unresolved_rows = (
        db.session.query(
            Repressor.province_name,
            Repressor.municipality_name,
            func.count(Repressor.id),
        )
        .outerjoin(
            approved_repressor_ids_subquery,
            approved_repressor_ids_subquery.c.repressor_id == Repressor.id,
        )
        .filter(approved_repressor_ids_subquery.c.repressor_id.is_(None))
        .group_by(
            Repressor.province_name,
            Repressor.municipality_name,
        )
        .all()
    )

    buckets = {}
    without_territory_reference = 0
    for raw_province, raw_municipality, raw_count in unresolved_rows:
        count = int(raw_count or 0)
        if count <= 0:
            continue

        province_name, municipality_name = canonicalize_location_names(
            raw_province,
            raw_municipality,
        )

        scope = (
            "municipality"
            if (municipality_name and province_name)
            else ("province" if province_name else "")
        )
        if not scope:
            without_territory_reference += count
            continue

        province_key = normalize_location_key(province_name) or "__nd__"
        municipality_key = normalize_location_key(municipality_name) if municipality_name else "__nd__"
        bucket_key = f"{scope}|{province_key}|{municipality_key}"
        bucket = buckets.get(bucket_key)
        if bucket is None:
            bucket = {
                "scope": scope,
                "province": province_name,
                "municipality": municipality_name if scope == "municipality" else None,
                "count": 0,
            }
            buckets[bucket_key] = bucket
        bucket["count"] = int(bucket["count"] or 0) + count

    unresolved_territories = []
    for bucket in buckets.values():
        lat, lng = _resolve_territory_centroid(
            bucket.get("province"),
            bucket.get("municipality"),
        )
        if lat is None or lng is None:
            without_territory_reference += int(bucket.get("count") or 0)
            continue

        unresolved_territories.append(
            {
                "scope": bucket.get("scope"),
                "province": bucket.get("province"),
                "municipality": bucket.get("municipality"),
                "count": int(bucket.get("count") or 0),
                "latitude": lat,
                "longitude": lng,
            }
        )

    unresolved_territories.sort(
        key=lambda item: (
            -int(item.get("count") or 0),
            str(item.get("province") or ""),
            str(item.get("municipality") or ""),
        )
    )

    total_repressors = int(db.session.query(func.count(Repressor.id)).scalar() or 0)
    with_confirmed_residence = int(
        db.session.query(func.count(func.distinct(RepressorResidenceReport.repressor_id)))
        .filter(
            RepressorResidenceReport.status == "approved",
            RepressorResidenceReport.repressor_id.isnot(None),
        )
        .scalar()
        or 0
    )
    without_confirmed_residence = max(total_repressors - with_confirmed_residence, 0)

    return jsonify(
        {
            "confirmed_residences": confirmed_residences,
            "unresolved_territories": unresolved_territories,
            "summary": {
                "total_repressors": total_repressors,
                "with_confirmed_residence": with_confirmed_residence,
                "without_confirmed_residence": without_confirmed_residence,
                "without_territory_reference": without_territory_reference,
                "confirmed_residences_points": len(confirmed_residences),
                "unresolved_territories_points": len(unresolved_territories),
            },
        }
    )


@api_bp.route("/v1/repressors/unresolved-territory")
@limiter.limit("120/minute")
def unresolved_repressors_territory_v1():
    scope = (request.args.get("scope") or "").strip().lower()
    province = (request.args.get("province") or "").strip()
    municipality = (request.args.get("municipality") or "").strip()

    if scope not in {"province", "municipality"}:
        return (
            jsonify({"ok": False, "error": "scope inválido. Usa 'province' o 'municipality'."}),
            400,
        )

    canonical_province, canonical_municipality = canonicalize_location_names(
        province,
        municipality,
    )
    if not canonical_province:
        return jsonify({"ok": False, "error": "province es obligatorio."}), 400
    if scope == "municipality" and not canonical_municipality:
        return jsonify({"ok": False, "error": "municipality es obligatorio para scope=municipality."}), 400

    approved_repressor_ids_subquery = _approved_repressor_ids_subquery()
    query = (
        Repressor.query.options(
            selectinload(Repressor.types),
        )
        .outerjoin(
            approved_repressor_ids_subquery,
            approved_repressor_ids_subquery.c.repressor_id == Repressor.id,
        )
        .filter(approved_repressor_ids_subquery.c.repressor_id.is_(None))
    )

    if scope == "municipality":
        query = query.filter(
            Repressor.province_name == canonical_province,
            Repressor.municipality_name == canonical_municipality,
        )
    else:
        query = query.filter(
            Repressor.province_name == canonical_province,
            or_(Repressor.municipality_name.is_(None), Repressor.municipality_name == ""),
        )

    rows = (
        query.order_by(
            Repressor.lastname.asc(),
            Repressor.name.asc(),
            Repressor.id.asc(),
        )
        .all()
    )

    items = []
    for repressor in rows:
        type_names = [
            str(item.name or "").strip()
            for item in (repressor.types or [])
            if str(item.name or "").strip()
        ]
        items.append(
            {
                "id": repressor.id,
                "external_id": repressor.external_id,
                "full_name": repressor.full_name,
                "nickname": repressor.nickname,
                "province_name": repressor.province_name,
                "municipality_name": repressor.municipality_name,
                "image_url": repressor.image_url,
                "type_names": type_names,
            }
        )

    territory_label = (
        f"{canonical_province} · {canonical_municipality}"
        if scope == "municipality"
        else canonical_province
    )

    return jsonify(
        {
            "ok": True,
            "scope": scope,
            "province": canonical_province,
            "municipality": canonical_municipality if scope == "municipality" else None,
            "territory_label": territory_label,
            "count": len(items),
            "items": items,
        }
    )


@api_bp.route("/v1/repressors/<int:repressor_id>/residence-reports", methods=["POST"])
@limiter.limit("6/minute; 80/day")
def create_repressor_residence_report_v1(repressor_id):
    repressor = Repressor.query.get_or_404(repressor_id)
    payload = request.get_json(silent=True) or {}

    message = (payload.get("message") or "").strip()
    address = (payload.get("address") or "").strip()
    province = (payload.get("province") or "").strip()
    municipality = (payload.get("municipality") or "").strip()
    links = payload.get("links") if isinstance(payload.get("links"), list) else []
    links = [str(item or "").strip() for item in links if str(item or "").strip()]

    if recaptcha_enabled():
        token = (payload.get("recaptcha") or "").strip()
        if not verify_recaptcha(token, request.remote_addr):
            return jsonify({"ok": False, "error": "Verificación reCAPTCHA falló."}), 400

    if not message:
        return jsonify({"ok": False, "error": "El mensaje es obligatorio."}), 400
    if len(message) < 30:
        return jsonify({"ok": False, "error": "El mensaje debe tener al menos 30 caracteres."}), 400
    if has_malicious_input([message, address, province, municipality] + links):
        return jsonify({"ok": False, "error": "Se detectó contenido sospechoso."}), 400

    try:
        lat = Decimal(str(payload.get("latitude")))
        lng = Decimal(str(payload.get("longitude")))
    except Exception:
        return jsonify({"ok": False, "error": "Latitud/longitud inválidas."}), 400

    if not is_within_cuba_bounds(lat, lng):
        return jsonify({"ok": False, "error": "La ubicación debe estar dentro de Cuba."}), 400

    try:
        auto_province, auto_municipality = lookup_location(lat, lng)
    except Exception:
        auto_province, auto_municipality = None, None
    if auto_province:
        province = auto_province
    if auto_municipality:
        municipality = auto_municipality

    if not province or not municipality:
        return jsonify({"ok": False, "error": "Provincia y municipio son obligatorios."}), 400

    category = _residence_category()
    if not category:
        return jsonify({"ok": False, "error": "Categoría residencia-represor no disponible."}), 500

    reporter = _get_or_create_anon_user()
    auto_approve = bool(current_app.config.get("REPRESSOR_RESIDENCE_AUTO_APPROVE", False))
    post_status = "approved" if auto_approve else "pending"
    report_status = "approved" if auto_approve else "pending"

    post = Post(
        title=build_residence_post_title(repressor),
        description=build_residence_post_description(repressor, message),
        latitude=lat,
        longitude=lng,
        address=address or None,
        province=province or None,
        municipality=municipality or None,
        repressor_name=repressor.full_name,
        repressor_id=repressor.id,
        links_json=json.dumps(links, ensure_ascii=False) if links else None,
        status=post_status,
        author_id=reporter.id,
        category_id=category.id,
    )
    db.session.add(post)
    db.session.flush()

    if repressor.image_url:
        db.session.add(
            Media(
                post_id=post.id,
                file_url=repressor.image_url,
                caption=f"Represor: {repressor.full_name}",
            )
        )

    residence_report = RepressorResidenceReport(
        repressor_id=repressor.id,
        status=report_status,
        reporter_id=reporter.id,
        latitude=lat,
        longitude=lng,
        address=address or None,
        province=province or None,
        municipality=municipality or None,
        message=message,
        evidence_links_json=json.dumps(links, ensure_ascii=False) if links else None,
        source_image_url=repressor.image_url,
        created_post_id=post.id,
        reviewed_at=datetime.utcnow() if auto_approve else None,
    )
    db.session.add(residence_report)
    db.session.commit()

    return (
        jsonify(
            {
                "ok": True,
                "residence_report": _serialize_repressor_residence_report(residence_report),
                "post": _serialize_post(post),
            }
        ),
        201,
    )


def _parse_date(value: str):
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except Exception:
        return None


def _build_connectivity_outage_events(start_dt, end_dt, province=""):
    selected_province = _canonical_province_name((province or "").strip()) or None
    selected_province_values = (
        _matching_stored_province_values(
            ConnectivityProvinceStatus.province,
            selected_province,
        )
        if selected_province
        else []
    )
    if selected_province and not selected_province_values:
        selected_province_values = [selected_province]

    if selected_province:
        base_query = db.session.query(
            ConnectivitySnapshot.id.label("snapshot_id"),
            ConnectivitySnapshot.observed_at_utc.label("observed_at_utc"),
            ConnectivityProvinceStatus.status.label("status"),
            ConnectivityProvinceStatus.score.label("score"),
            ConnectivityProvinceStatus.province.label("province"),
        ).join(
            ConnectivityProvinceStatus,
            ConnectivityProvinceStatus.snapshot_id == ConnectivitySnapshot.id,
        ).filter(
            ConnectivityProvinceStatus.province.in_(selected_province_values),
        )
    else:
        base_query = db.session.query(
            ConnectivitySnapshot.id.label("snapshot_id"),
            ConnectivitySnapshot.observed_at_utc.label("observed_at_utc"),
            ConnectivitySnapshot.status.label("status"),
            ConnectivitySnapshot.score.label("score"),
        )

    previous_point = (
        base_query.filter(ConnectivitySnapshot.observed_at_utc < start_dt)
        .order_by(ConnectivitySnapshot.observed_at_utc.desc(), ConnectivitySnapshot.id.desc())
        .first()
    )
    points_in_range = (
        base_query.filter(
            ConnectivitySnapshot.observed_at_utc >= start_dt,
            ConnectivitySnapshot.observed_at_utc <= end_dt,
        )
        .order_by(ConnectivitySnapshot.observed_at_utc.asc(), ConnectivitySnapshot.id.asc())
        .all()
    )

    points = []
    if previous_point:
        points.append(previous_point)
    points.extend(points_in_range)

    if not points:
        return {"events": [], "total": 0, "ongoing": 0}

    def _is_critical(item):
        return (getattr(item, "status", "") or "").strip().lower() == STATUS_CRITICAL

    def _build_event_start(item):
        start_raw = getattr(item, "observed_at_utc", None)
        event = {
            "started_at_utc": serialize_snapshot_time(start_raw),
            "ended_at_utc": None,
            "duration_minutes": None,
            "ongoing": True,
            "score_at_start": getattr(item, "score", None),
            "score_at_end": None,
            "start_snapshot_id": getattr(item, "snapshot_id", None),
            "end_snapshot_id": None,
            "province": _canonical_province_name(getattr(item, "province", None))
            or selected_province,
            "_start_dt": start_raw,
        }
        return event

    events = []
    open_event = None
    prev = None
    for point in points:
        current_critical = _is_critical(point)
        previous_critical = _is_critical(prev) if prev is not None else False

        if current_critical and not previous_critical:
            open_event = _build_event_start(point)
        elif (not current_critical) and previous_critical and open_event is not None:
            start_raw = open_event.get("_start_dt")
            end_raw = getattr(point, "observed_at_utc", None)
            duration_minutes = None
            if start_raw and end_raw:
                duration_minutes = max(int((end_raw - start_raw).total_seconds() // 60), 0)

            open_event.update(
                {
                    "ended_at_utc": serialize_snapshot_time(end_raw),
                    "duration_minutes": duration_minutes,
                    "ongoing": False,
                    "score_at_end": getattr(point, "score", None),
                    "end_snapshot_id": getattr(point, "snapshot_id", None),
                }
            )
            open_event.pop("_start_dt", None)
            events.append(open_event)
            open_event = None

        prev = point

    if open_event is not None:
        open_event.pop("_start_dt", None)
        events.append(open_event)

    events = [event for event in events if event.get("started_at_utc")]
    events.sort(key=lambda event: event.get("started_at_utc") or "", reverse=True)
    return {
        "events": events[:120],
        "total": len(events),
        "ongoing": len([event for event in events if event.get("ongoing")]),
    }


@api_bp.route("/v1/analytics")
@limiter.limit("60/minute")
def analytics_v1():
    start_raw = (request.args.get("start") or "").strip()
    end_raw = (request.args.get("end") or "").strip()
    category_id = request.args.get("category_id")
    province = _canonical_province_name((request.args.get("province") or "").strip())
    province_filter_values = _matching_stored_province_values(Post.province, province) if province else []
    if province and not province_filter_values:
        province_filter_values = [province]

    end_dt = _parse_date(end_raw) or datetime.utcnow()
    start_dt = _parse_date(start_raw) or (end_dt - timedelta(days=90))
    if start_dt > end_dt:
        start_dt, end_dt = end_dt, start_dt
    end_dt = end_dt.replace(hour=23, minute=59, second=59, microsecond=0)

    active_statuses = ["approved", "pending", "rejected", "hidden"]

    base_query = Post.query.filter(
        Post.created_at >= start_dt,
        Post.created_at <= end_dt,
        Post.status.in_(active_statuses),
    )
    if category_id:
        try:
            base_query = base_query.filter(Post.category_id == int(category_id))
        except ValueError:
            pass
    if province_filter_values:
        base_query = base_query.filter(Post.province.in_(province_filter_values))

    day_expr = func.date(Post.created_at).label("day")
    reports_over_time = (
        db.session.query(
            day_expr,
            func.count(Post.id),
        )
        .filter(
            Post.created_at >= start_dt,
            Post.created_at <= end_dt,
            Post.status.in_(active_statuses),
        )
        .group_by(day_expr)
        .order_by(day_expr)
    )
    if category_id:
        try:
            reports_over_time = reports_over_time.filter(Post.category_id == int(category_id))
        except ValueError:
            pass
    if province_filter_values:
        reports_over_time = reports_over_time.filter(Post.province.in_(province_filter_values))

    reports_series = [
        {"date": row[0].isoformat(), "count": row[1]}
        for row in reports_over_time.all()
    ]

    category_distribution = (
        db.session.query(Category.id, Category.name, func.count(Post.id))
        .join(Post, Post.category_id == Category.id)
        .filter(
            Post.created_at >= start_dt,
            Post.created_at <= end_dt,
            Post.status.in_(active_statuses),
        )
        .group_by(Category.id, Category.name)
        .order_by(func.count(Post.id).desc())
    )
    if category_id:
        try:
            category_distribution = category_distribution.filter(Post.category_id == int(category_id))
        except ValueError:
            pass
    if province_filter_values:
        category_distribution = category_distribution.filter(Post.province.in_(province_filter_values))

    category_items = [
        {"id": row[0], "name": row[1], "count": row[2]}
        for row in category_distribution.all()
    ]

    province_distribution = (
        db.session.query(Post.province, func.count(Post.id))
        .filter(
            Post.created_at >= start_dt,
            Post.created_at <= end_dt,
            Post.status.in_(active_statuses),
            Post.province.isnot(None),
            Post.province != "",
        )
        .group_by(Post.province)
        .order_by(func.count(Post.id).desc())
    )
    if category_id:
        try:
            province_distribution = province_distribution.filter(Post.category_id == int(category_id))
        except ValueError:
            pass
    if province_filter_values:
        province_distribution = province_distribution.filter(Post.province.in_(province_filter_values))

    province_counter = {}
    for row in province_distribution.all():
        canonical_name = _canonical_province_name(row[0])
        if not canonical_name:
            continue
        province_counter[canonical_name] = province_counter.get(canonical_name, 0) + int(row[1] or 0)
    province_items = [
        {"name": name, "count": count}
        for name, count in sorted(
            province_counter.items(),
            key=lambda item: (-int(item[1]), item[0]),
        )[:10]
    ]

    municipality_distribution = (
        db.session.query(Post.municipality, func.count(Post.id))
        .filter(
            Post.created_at >= start_dt,
            Post.created_at <= end_dt,
            Post.status.in_(active_statuses),
            Post.municipality.isnot(None),
            Post.municipality != "",
        )
        .group_by(Post.municipality)
        .order_by(func.count(Post.id).desc())
    )
    if category_id:
        try:
            municipality_distribution = municipality_distribution.filter(Post.category_id == int(category_id))
        except ValueError:
            pass
    if province_filter_values:
        municipality_distribution = municipality_distribution.filter(Post.province.in_(province_filter_values))

    municipality_items = [
        {"name": row[0], "count": row[1]} for row in municipality_distribution.limit(10).all()
    ]

    moderation_status = (
        db.session.query(Post.status, func.count(Post.id))
        .filter(Post.created_at >= start_dt, Post.created_at <= end_dt)
        .group_by(Post.status)
        .all()
    )
    moderation_map = {status: count for status, count in moderation_status}

    top_verified = (
        Post.query.options(selectinload(Post.category))
        .filter(
            Post.created_at >= start_dt,
            Post.created_at <= end_dt,
            Post.status == "approved",
        )
        .order_by(Post.verify_count.desc().nullslast(), Post.created_at.desc())
    )
    if category_id:
        try:
            top_verified = top_verified.filter(Post.category_id == int(category_id))
        except ValueError:
            pass
    if province_filter_values:
        top_verified = top_verified.filter(Post.province.in_(province_filter_values))

    top_verified_items = [
        {"id": p.id, "title": p.title, "verify_count": p.verify_count or 0}
        for p in top_verified.limit(10).all()
    ]

    comment_day = func.date(Comment.created_at).label("day")
    comment_query = (
        db.session.query(
            comment_day,
            func.count(Comment.id),
        )
        .filter(Comment.created_at >= start_dt, Comment.created_at <= end_dt)
        .group_by(comment_day)
        .order_by(comment_day)
    )
    discussion_day = func.date(DiscussionComment.created_at).label("day")
    discussion_comment_query = (
        db.session.query(
            discussion_day,
            func.count(DiscussionComment.id),
        )
        .filter(
            DiscussionComment.created_at >= start_dt,
            DiscussionComment.created_at <= end_dt,
        )
        .group_by(discussion_day)
        .order_by(discussion_day)
    )

    report_comments = {row[0].isoformat(): row[1] for row in comment_query.all()}
    discussion_comments = {
        row[0].isoformat(): row[1] for row in discussion_comment_query.all()
    }
    labels = sorted(set(report_comments.keys()) | set(discussion_comments.keys()))
    report_counts = [report_comments.get(label, 0) for label in labels]
    discussion_counts = [discussion_comments.get(label, 0) for label in labels]

    edit_status_query = (
        db.session.query(PostEditRequest.status, func.count(PostEditRequest.id))
        .filter(PostEditRequest.created_at >= start_dt, PostEditRequest.created_at <= end_dt)
        .group_by(PostEditRequest.status)
        .all()
    )
    edit_status_map = {status: count for status, count in edit_status_query}
    connectivity_outages = _build_connectivity_outage_events(start_dt, end_dt, province=province)
    connectivity_24h = _build_http_requests_24h_summary()

    return jsonify(
        {
            "range": {
                "start": start_dt.date().isoformat(),
                "end": end_dt.date().isoformat(),
            },
            "reports_over_time": reports_series,
            "category_distribution": category_items,
            "province_distribution": province_items,
            "municipality_distribution": municipality_items,
            "moderation_status": {
                "approved": moderation_map.get("approved", 0),
                "pending": moderation_map.get("pending", 0),
                "rejected": moderation_map.get("rejected", 0),
                "hidden": moderation_map.get("hidden", 0),
            },
            "top_verified": top_verified_items,
            "comments_over_time": {
                "labels": labels,
                "report_counts": report_counts,
                "discussion_counts": discussion_counts,
            },
            "edit_status": {
                "pending": edit_status_map.get("pending", 0),
                "approved": edit_status_map.get("approved", 0),
                "rejected": edit_status_map.get("rejected", 0),
            },
            "connectivity_outages": connectivity_outages,
            "connectivity_24h": connectivity_24h,
        }
    )
@api_bp.route("/posts/<int:post_id>/verify", methods=["POST"])
@limiter.limit("10/minute; 200/day")
def verify_post(post_id):
    post = Post.query.get_or_404(post_id)
    cookie_key = f"verified_{post_id}"
    voter_hash = get_voter_hash(current_user, request, current_app.config.get("SECRET_KEY", ""))

    existing = VoteRecord.query.filter_by(
        target_type="post_verify",
        target_id=post.id,
        voter_hash=voter_hash,
    ).first()
    if existing or request.cookies.get(cookie_key):
        return jsonify({"ok": False, "verify_count": post.verify_count or 0})

    record = VoteRecord(
        target_type="post_verify",
        target_id=post.id,
        voter_hash=voter_hash,
        value=1,
    )
    db.session.add(record)
    post.verify_count = (post.verify_count or 0) + 1
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"ok": False, "verify_count": post.verify_count or 0})

    resp = make_response(jsonify({"ok": True, "verify_count": post.verify_count}))
    resp.set_cookie(cookie_key, "1")
    return resp


@api_bp.route("/repressors/<int:repressor_id>/verify", methods=["POST"])
@limiter.limit("10/minute; 200/day")
def verify_repressor(repressor_id):
    repressor = Repressor.query.get_or_404(repressor_id)
    cookie_key = f"verified_repressor_{repressor_id}"
    voter_hash = get_voter_hash(current_user, request, current_app.config.get("SECRET_KEY", ""))

    existing = VoteRecord.query.filter_by(
        target_type="repressor_verify",
        target_id=repressor.id,
        voter_hash=voter_hash,
    ).first()
    if existing or request.cookies.get(cookie_key):
        return jsonify(
            {
                "ok": False,
                "verify_count": repressor.verify_count or 0,
                "locked": (repressor.verify_count or 0) >= REPRESSOR_VERIFY_LOCK_COUNT,
            }
        )

    record = VoteRecord(
        target_type="repressor_verify",
        target_id=repressor.id,
        voter_hash=voter_hash,
        value=1,
    )
    db.session.add(record)
    repressor.verify_count = (repressor.verify_count or 0) + 1
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(
            {
                "ok": False,
                "verify_count": repressor.verify_count or 0,
                "locked": (repressor.verify_count or 0) >= REPRESSOR_VERIFY_LOCK_COUNT,
            }
        )

    resp = make_response(
        jsonify(
            {
                "ok": True,
                "verify_count": repressor.verify_count,
                "locked": (repressor.verify_count or 0) >= REPRESSOR_VERIFY_LOCK_COUNT,
            }
        )
    )
    resp.set_cookie(cookie_key, "1")
    return resp


@api_bp.route("/posts/<int:post_id>/comments", methods=["GET", "POST"])
@limiter.limit("10/minute; 200/day", methods=["POST"])
def comments(post_id):
    post = Post.query.get_or_404(post_id)
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        body = sanitize_text(data.get("body") or "", max_len=4000)
        if recaptcha_enabled():
            token = (data.get("recaptcha") or "").strip()
            if not verify_recaptcha(token, request.remote_addr):
                return jsonify({"ok": False, "error": "Verificación reCAPTCHA falló."}), 400
        if has_malicious_input([body]):
            return jsonify({"ok": False, "error": "Contenido sospechoso."}), 400
        if not body:
            return jsonify({"ok": False, "error": "Comentario vacío."}), 400

        user = _get_or_create_anon_user()
        label = f"Anon-{user.anon_code}" if user and user.anon_code else "Anon"
        comment = Comment(post_id=post.id, author_id=user.id, author_label=label, body=body)
        db.session.add(comment)
        db.session.commit()

    items = (
        Comment.query.filter_by(post_id=post.id)
        .order_by(Comment.created_at.desc())
        .all()
    )
    return jsonify(
        [
            {
                "id": c.id,
                "author": c.author_label or "Anon",
                "body": c.body,
                "created_at": c.created_at.isoformat(),
                "upvotes": c.upvotes or 0,
                "downvotes": c.downvotes or 0,
                "score": (c.upvotes or 0) - (c.downvotes or 0),
            }
            for c in items
        ]
    )


@api_bp.route("/comments/<int:comment_id>/vote", methods=["POST"])
@limiter.limit("10/minute; 200/day")
def vote_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    data = request.get_json(silent=True) or {}
    value = data.get("value")
    if value not in (1, -1):
        return jsonify({"ok": False, "error": "Voto inválido."}), 400

    voter_hash = get_voter_hash(current_user, request, current_app.config.get("SECRET_KEY", ""))
    existing = VoteRecord.query.filter_by(
        target_type="comment",
        target_id=comment.id,
        voter_hash=voter_hash,
    ).first()

    if existing and existing.value == value:
        return jsonify(
            {
                "ok": True,
                "upvotes": comment.upvotes or 0,
                "downvotes": comment.downvotes or 0,
                "score": (comment.upvotes or 0) - (comment.downvotes or 0),
            }
        )

    if existing:
        _remove_vote(comment, existing.value)
        existing.value = value
    else:
        existing = VoteRecord(
            target_type="comment",
            target_id=comment.id,
            voter_hash=voter_hash,
            value=value,
        )
        db.session.add(existing)

    _apply_vote(comment, value)
    db.session.commit()

    return jsonify(
        {
            "ok": True,
            "upvotes": comment.upvotes or 0,
            "downvotes": comment.downvotes or 0,
            "score": (comment.upvotes or 0) - (comment.downvotes or 0),
        }
    )


@api_bp.route("/comments/<int:comment_id>", methods=["DELETE"])
@limiter.limit("10/minute; 100/day")
def delete_comment(comment_id):
    if not (current_user.is_authenticated and current_user.has_role("administrador")):
        return jsonify({"ok": False, "error": "No autorizado."}), 403
    comment = Comment.query.get_or_404(comment_id)
    db.session.delete(comment)
    db.session.commit()
    return jsonify({"ok": True})


@api_bp.route("/posts/<int:post_id>/status", methods=["POST"])
def update_post_status(post_id):
    if not (current_user.is_authenticated and current_user.has_role("administrador")):
        return jsonify({"ok": False, "error": "No autorizado."}), 403
    data = request.get_json(silent=True) or {}
    status = data.get("status")
    if status not in {"approved", "hidden", "deleted", "rejected", "pending"}:
        return jsonify({"ok": False, "error": "Estado inválido."}), 400
    post = Post.query.get_or_404(post_id)
    post.status = status
    db.session.commit()
    return jsonify({"ok": True, "status": post.status})


@api_bp.route("/discusiones/<int:post_id>/vote", methods=["POST"])
@limiter.limit("12/minute; 240/day")
def vote_discussion_post(post_id):
    post = DiscussionPost.query.get_or_404(post_id)
    data = request.get_json(silent=True) or {}
    value = data.get("value")
    if value not in (1, -1):
        return jsonify({"ok": False, "error": "Voto inválido."}), 400

    voter_hash = get_voter_hash(current_user, request, current_app.config.get("SECRET_KEY", ""))
    existing = VoteRecord.query.filter_by(
        target_type="discussion_post",
        target_id=post.id,
        voter_hash=voter_hash,
    ).first()

    if existing and existing.value == value:
        return jsonify(
            {
                "ok": True,
                "upvotes": post.upvotes or 0,
                "downvotes": post.downvotes or 0,
                "score": (post.upvotes or 0) - (post.downvotes or 0),
            }
        )

    if existing:
        _remove_vote(post, existing.value)
        existing.value = value
    else:
        existing = VoteRecord(
            target_type="discussion_post",
            target_id=post.id,
            voter_hash=voter_hash,
            value=value,
        )
        db.session.add(existing)

    _apply_vote(post, value)
    db.session.commit()

    return jsonify(
        {
            "ok": True,
            "upvotes": post.upvotes or 0,
            "downvotes": post.downvotes or 0,
            "score": (post.upvotes or 0) - (post.downvotes or 0),
        }
    )


@api_bp.route("/discusiones/comentarios/<int:comment_id>/vote", methods=["POST"])
@limiter.limit("10/minute; 200/day")
def vote_discussion_comment(comment_id):
    comment = DiscussionComment.query.get_or_404(comment_id)
    data = request.get_json(silent=True) or {}
    value = data.get("value")
    if value not in (1, -1):
        return jsonify({"ok": False, "error": "Voto inválido."}), 400

    voter_hash = get_voter_hash(current_user, request, current_app.config.get("SECRET_KEY", ""))
    existing = VoteRecord.query.filter_by(
        target_type="discussion_comment",
        target_id=comment.id,
        voter_hash=voter_hash,
    ).first()

    if existing and existing.value == value:
        return jsonify(
            {
                "ok": True,
                "upvotes": comment.upvotes or 0,
                "downvotes": comment.downvotes or 0,
                "score": (comment.upvotes or 0) - (comment.downvotes or 0),
            }
        )

    if existing:
        _remove_vote(comment, existing.value)
        existing.value = value
    else:
        existing = VoteRecord(
            target_type="discussion_comment",
            target_id=comment.id,
            voter_hash=voter_hash,
            value=value,
        )
        db.session.add(existing)

    _apply_vote(comment, value)
    db.session.commit()

    return jsonify(
        {
            "ok": True,
            "upvotes": comment.upvotes or 0,
            "downvotes": comment.downvotes or 0,
            "score": (comment.upvotes or 0) - (comment.downvotes or 0),
        }
    )


@api_bp.route("/posts/<int:post_id>/media", methods=["POST"])
@limiter.limit("6/hour; 30/day")
def upload_post_media(post_id):
    post = Post.query.get_or_404(post_id)
    files = [
        file
        for file in request.files.getlist("images")
        if file and (file.filename or "").strip()
    ]
    captions_raw = request.form.getlist("image_captions[]")
    if has_malicious_input(captions_raw):
        return jsonify({"ok": False, "error": "Contenido sospechoso."}), 400
    ok, error = validate_files(files)
    if not ok:
        return jsonify({"ok": False, "error": error}), 400

    moderation_setting = SiteSetting.query.filter_by(key="moderation_enabled").first()
    moderation_enabled = True
    if moderation_setting:
        moderation_enabled = moderation_setting.value == "true"

    urls = upload_files(files)
    if not urls:
        return jsonify({"ok": False, "error": "No se pudo subir la imagen."}), 400

    if moderation_enabled:
        captions = []
        for idx in range(len(urls)):
            value = ""
            if idx < len(captions_raw):
                value = (captions_raw[idx] or "").strip()
            captions.append(value[:255] if value else "")
        new_items = [
            {"url": url, "caption": (captions[idx] if idx < len(captions) else "")}
            for idx, url in enumerate(urls)
        ]
        combined = get_media_payload(post) + new_items
        edit = PostEditRequest(
            post_id=post.id,
            editor_id=current_user.id if current_user.is_authenticated else None,
            editor_label=f"Anon-{current_user.anon_code}" if current_user.is_authenticated and current_user.anon_code else "Anon",
            reason="Imagen añadida",
            title=post.title,
            description=post.description,
            latitude=post.latitude,
            longitude=post.longitude,
            address=post.address,
            province=post.province,
            municipality=post.municipality,
            repressor_name=post.repressor_name,
            other_type=post.other_type,
            category_id=post.category_id,
            polygon_geojson=post.polygon_geojson,
            links_json=post.links_json,
            media_json=json.dumps(combined),
        )
        db.session.add(edit)
        db.session.commit()
        return jsonify({"ok": True, "status": "pending"})

    revision = PostRevision(
        post_id=post.id,
        editor_id=current_user.id if current_user.is_authenticated else None,
        editor_label=f"Anon-{current_user.anon_code}" if current_user.is_authenticated and current_user.anon_code else "Anon",
        reason="Imagen añadida",
        title=post.title,
        description=post.description,
        latitude=post.latitude,
        longitude=post.longitude,
        address=post.address,
        province=post.province,
        municipality=post.municipality,
        repressor_name=post.repressor_name,
        other_type=post.other_type,
        category_id=post.category_id,
        polygon_geojson=post.polygon_geojson,
        links_json=post.links_json,
        media_json=media_json_from_post(post),
    )
    db.session.add(revision)

    captions = []
    for idx in range(len(urls)):
        value = ""
        if idx < len(captions_raw):
            value = (captions_raw[idx] or "").strip()
        captions.append(value[:255] if value else "")

    for idx, url in enumerate(urls):
        caption = captions[idx] if idx < len(captions) else ""
        db.session.add(Media(post_id=post.id, file_url=url, caption=caption or None))
    db.session.commit()

    return jsonify({"ok": True, "status": "approved", "media": get_media_payload(post)})


@api_bp.route("/chat", methods=["GET", "POST"])
@limiter.limit("60/minute", methods=["GET"])
@limiter.limit("6/minute; 120/day", methods=["POST"])
def chat_messages():
    if current_app.config.get("CHAT_DISABLED", True):
        return jsonify({"ok": False, "error": "Chat deshabilitado."}), 403
    now = datetime.utcnow()
    cutoff_keep = now - timedelta(hours=48)
    cutoff_visible = now - timedelta(hours=24)
    cutoff_online = now - timedelta(minutes=10)

    ChatMessage.query.filter(ChatMessage.created_at < cutoff_keep).delete()
    ChatPresence.query.filter(ChatPresence.last_seen < cutoff_online).delete()
    db.session.commit()

    session_id = session.get("chat_sid")
    if not session_id:
        session_id = secrets.token_hex(16)
        session["chat_sid"] = session_id

    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        body = sanitize_text(data.get("body") or "", max_len=1000)
        nickname = sanitize_text(data.get("nickname") or "", max_len=80)

        if has_malicious_input([body, nickname]):
            return jsonify({"ok": False, "error": "Contenido sospechoso."}), 400

        if not body:
            return jsonify({"ok": False, "error": "Mensaje vacío."}), 400

        nickname = _sanitize_nick(nickname, _get_chat_nick())
        session["chat_nick"] = nickname

        presence = ChatPresence.query.filter_by(session_id=session_id).first()
        if not presence:
            presence = ChatPresence(session_id=session_id, nickname=nickname, last_seen=now)
            db.session.add(presence)
        else:
            presence.nickname = nickname
            presence.last_seen = now

        author_id = current_user.id if current_user.is_authenticated else None
        msg = ChatMessage(author_id=author_id, author_label=nickname, body=body)
        db.session.add(msg)
        db.session.commit()
    else:
        nickname = _get_chat_nick()
        presence = ChatPresence.query.filter_by(session_id=session_id).first()
        if not presence:
            presence = ChatPresence(session_id=session_id, nickname=nickname, last_seen=now)
            db.session.add(presence)
        else:
            presence.last_seen = now
        db.session.commit()

    items = (
        ChatMessage.query.filter(ChatMessage.created_at >= cutoff_visible)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    online_count = ChatPresence.query.count()
    return jsonify(
        {
            "items": [
                {
                    "id": m.id,
                    "author": m.author_label,
                    "body": m.body,
                    "created_at": m.created_at.isoformat(),
                }
                for m in items
            ],
            "online_count": online_count,
        }
    )
