from __future__ import annotations

import secrets
import unicodedata
from datetime import datetime

from sqlalchemy.orm import selectinload

from app.celery_app import celery
from app.extensions import db
from app.models.category import Category
from app.models.connectivity_snapshot import ConnectivitySnapshot
from app.models.post import Post
from app.models.role import Role
from app.models.user import User
from app.services.connectivity import (
    STATUS_CRITICAL,
    STATUS_LABELS,
    STATUS_SEVERE,
)
from app.services.connectivity_geo import load_province_geojson
from app.services.cuba_locations import PROVINCE_CENTER_FALLBACKS
from app.services.location_names import canonicalize_province_name, normalize_location_key
from scripts.fetch_connectivity import run_ingestion


ALERT_STATUS_SET = {STATUS_SEVERE, STATUS_CRITICAL}
AUTO_CONNECTIVITY_REPORT_TITLE_PREFIX = "Alerta automatica Cloudflare:"
AUTO_CONNECTIVITY_REPORT_DESCRIPTION_PREFIX = (
    "Reporte automatico generado con Cloudflare Radar y SOSCubaMap."
)
AUTO_CONNECTIVITY_REPORT_MARKER = "auto_connectivity_cloudflare"


def _normalize_text(value):
    text = str(value or "").strip().lower()
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _canonical_province_name(value):
    canonical = canonicalize_province_name(value)
    if canonical:
        return canonical
    return str(value or "").strip()


def _extract_polygon_points(geometry):
    if not isinstance(geometry, dict):
        return []
    gtype = geometry.get("type")
    if gtype == "Polygon":
        polygons = [geometry.get("coordinates") or []]
    elif gtype == "MultiPolygon":
        polygons = geometry.get("coordinates") or []
    else:
        return []

    points = []
    for polygon in polygons:
        if not isinstance(polygon, list) or not polygon:
            continue
        outer_ring = polygon[0] if isinstance(polygon[0], list) else polygon
        if not isinstance(outer_ring, list):
            continue
        for pair in outer_ring:
            if not isinstance(pair, (list, tuple)) or len(pair) < 2:
                continue
            try:
                lon = float(pair[0])
                lat = float(pair[1])
            except Exception:
                continue
            points.append((lat, lon))
    return points


def _geometry_center(geometry):
    points = _extract_polygon_points(geometry)
    if not points:
        return None, None
    lats = [point[0] for point in points]
    lons = [point[1] for point in points]
    if not lats or not lons:
        return None, None
    return (min(lats) + max(lats)) / 2.0, (min(lons) + max(lons)) / 2.0


def _province_centers_from_geojson():
    centers = {}
    geojson = load_province_geojson()
    for feature in geojson.get("features") or []:
        props = feature.get("properties") or {}
        province = _canonical_province_name(props.get("province"))
        if not province:
            continue
        lat, lng = _geometry_center(feature.get("geometry"))
        if lat is None or lng is None:
            continue
        centers[_normalize_text(province)] = (lat, lng)
    return centers


def _fallback_centers():
    payload = {}
    for province, center in (PROVINCE_CENTER_FALLBACKS or {}).items():
        if not center:
            continue
        try:
            lat, lng = center
            payload[_normalize_text(province)] = (float(lat), float(lng))
        except Exception:
            continue
    return payload


FALLBACK_CENTERS = _fallback_centers()


def _resolve_province_center(province, geojson_centers):
    key = _normalize_text(_canonical_province_name(province))
    if not key:
        return None, None

    if key in geojson_centers:
        return geojson_centers[key]
    if key in FALLBACK_CENTERS:
        return FALLBACK_CENTERS[key]
    return None, None


def _status_by_province(snapshot):
    if not snapshot:
        return {}
    payload = {}
    for row in snapshot.provinces or []:
        province = _canonical_province_name(row.province)
        if not province:
            continue
        existing = payload.get(province)
        candidate = {
            "status": str(row.status or "").strip().lower(),
            "score": row.score,
        }
        if existing is None:
            payload[province] = candidate
            continue

        existing_score = existing.get("score")
        candidate_score = candidate.get("score")
        if candidate_score is None:
            continue
        if existing_score is None or candidate_score < existing_score:
            payload[province] = candidate
    return payload


def _should_create_alert(current_status):
    status = str(current_status or "").strip().lower()
    return status in ALERT_STATUS_SET


def _ensure_system_user(email):
    normalized_email = str(email or "").strip().lower() or "radar-bot@soscuba.local"
    user = User.query.filter_by(email=normalized_email).first()
    if user:
        if not user.anon_code:
            user.ensure_anon_code()
            db.session.flush()
        return user

    user = User(email=normalized_email)
    user.set_password(secrets.token_urlsafe(24))
    user.ensure_anon_code()
    default_role = Role.query.filter_by(name="colaborador").first()
    if default_role:
        user.roles.append(default_role)
    db.session.add(user)
    db.session.flush()
    return user


def _already_reported(category_id, province, movement_at_utc, title):
    return (
        Post.query.filter(
            Post.category_id == category_id,
            Post.province == province,
            Post.movement_at == movement_at_utc,
            Post.title == title,
        )
        .order_by(Post.id.desc())
        .first()
        is not None
    )


def _is_auto_connectivity_report(post):
    if not post:
        return False

    marker = str(post.other_type or "").strip().lower()
    if marker == AUTO_CONNECTIVITY_REPORT_MARKER:
        return True

    title = str(post.title or "").strip()
    if title.startswith(AUTO_CONNECTIVITY_REPORT_TITLE_PREFIX):
        return True

    description = str(post.description or "").strip()
    if description.startswith(AUTO_CONNECTIVITY_REPORT_DESCRIPTION_PREFIX):
        return True

    return False


def _retire_recovered_auto_reports(category_id, active_alert_provinces, system_user_id=None):
    active_keys = {
        normalize_location_key(_canonical_province_name(name))
        for name in (active_alert_provinces or [])
        if normalize_location_key(_canonical_province_name(name))
    }
    query = Post.query.filter(
        Post.category_id == category_id,
        Post.status == "approved",
    )
    if system_user_id:
        query = query.filter(Post.author_id == system_user_id)

    retired = []
    for post in query.all():
        if not _is_auto_connectivity_report(post):
            continue
        province_key = normalize_location_key(_canonical_province_name(post.province))
        if province_key and province_key in active_keys:
            continue
        post.status = "deleted"
        retired.append(post)
    return retired


@celery.task(
    name="app.tasks.connectivity.poll_connectivity_and_create_reports",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 2},
)
def poll_connectivity_and_create_reports(self):
    scheduled_for = datetime.utcnow()
    run_ingestion(single_call=False, scheduled_for=scheduled_for)

    if not bool(celery.flask_app.config.get("AUTO_CONNECTIVITY_REPORTS_ENABLED", True)):
        return {
            "status": "ok",
            "reports_created": 0,
            "reason": "auto_reports_disabled",
        }

    category = Category.query.filter_by(slug="desconexion-internet").first()
    if not category:
        return {
            "status": "ok",
            "reports_created": 0,
            "reason": "missing_category_desconexion_internet",
        }

    latest_snapshot = (
        ConnectivitySnapshot.query.options(selectinload(ConnectivitySnapshot.provinces))
        .order_by(ConnectivitySnapshot.observed_at_utc.desc(), ConnectivitySnapshot.id.desc())
        .first()
    )
    if not latest_snapshot:
        return {
            "status": "ok",
            "reports_created": 0,
            "reason": "no_connectivity_snapshots",
        }

    current_state = _status_by_province(latest_snapshot)
    centers = _province_centers_from_geojson()

    system_user = None
    user_email = celery.flask_app.config.get("AUTO_CONNECTIVITY_REPORT_USER_EMAIL", "")
    normalized_user_email = str(user_email or "").strip().lower() or "radar-bot@soscuba.local"
    system_user = User.query.filter_by(email=normalized_user_email).first()
    active_alert_provinces = [
        province
        for province in sorted(current_state.keys())
        if _should_create_alert((current_state.get(province) or {}).get("status"))
    ]
    created_provinces = []
    deleted_provinces = []
    deleted_report_ids = []

    try:
        retired_reports = _retire_recovered_auto_reports(
            category.id,
            active_alert_provinces,
            system_user_id=system_user.id if system_user else None,
        )
        deleted_report_ids = [post.id for post in retired_reports]
        deleted_provinces = sorted(
            {
                post.province
                for post in retired_reports
                if str(post.province or "").strip()
            }
        )

        for province in sorted(current_state.keys()):
            state = current_state.get(province) or {}
            current_status = state.get("status")
            if not _should_create_alert(current_status):
                continue

            status_label = STATUS_LABELS.get(current_status, "Conectividad afectada")
            canonical_province = _canonical_province_name(province)
            title = f"Alerta automatica Cloudflare: {status_label} en {canonical_province}"
            if _already_reported(
                category.id,
                canonical_province,
                latest_snapshot.observed_at_utc,
                title,
            ):
                continue

            lat, lng = _resolve_province_center(canonical_province, centers)
            if lat is None or lng is None:
                continue

            if system_user is None:
                system_user = _ensure_system_user(normalized_user_email)

            description = (
                "Reporte automatico generado con Cloudflare Radar y SOSCubaMap. "
                "En parte de este territorio la conectividad se esta viendo afectada, "
                "pero se desconocen los motivos."
            )
            score_value = state.get("score")
            score_text = f"{float(score_value):.1f}" if score_value is not None else "N/D"

            post = Post(
                title=title[:200],
                description=f"{description} Estado detectado: {status_label}. Score estimado: {score_text}.",
                latitude=lat,
                longitude=lng,
                address=f"Centro aproximado de {canonical_province}",
                province=canonical_province,
                municipality=None,
                movement_at=latest_snapshot.observed_at_utc,
                author_id=system_user.id,
                category_id=category.id,
                status="approved",
                is_anonymous=True,
                other_type=AUTO_CONNECTIVITY_REPORT_MARKER,
            )
            db.session.add(post)
            created_provinces.append(canonical_province)

        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return {
        "status": "ok",
        "snapshot_id": latest_snapshot.id,
        "observed_at_utc": latest_snapshot.observed_at_utc.isoformat()
        if latest_snapshot.observed_at_utc
        else None,
        "reports_created": len(created_provinces),
        "provinces": created_provinces,
        "reports_deleted": len(deleted_report_ids),
        "deleted_report_ids": deleted_report_ids,
        "deleted_provinces": deleted_provinces,
    }
