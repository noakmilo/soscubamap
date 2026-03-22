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
from scripts.fetch_connectivity import run_ingestion


ALERT_STATUS_SET = {STATUS_SEVERE, STATUS_CRITICAL}


def _normalize_text(value):
    text = str(value or "").strip().lower()
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


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
        province = str(props.get("province") or "").strip()
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
    key = _normalize_text(province)
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
        province = str(row.province or "").strip()
        if not province:
            continue
        payload[province] = {
            "status": str(row.status or "").strip().lower(),
            "score": row.score,
        }
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
    created_provinces = []

    try:
        for province in sorted(current_state.keys()):
            state = current_state.get(province) or {}
            current_status = state.get("status")
            if not _should_create_alert(current_status):
                continue

            status_label = STATUS_LABELS.get(current_status, "Conectividad afectada")
            title = f"Alerta automatica Cloudflare: {status_label} en {province}"
            if _already_reported(
                category.id,
                province,
                latest_snapshot.observed_at_utc,
                title,
            ):
                continue

            lat, lng = _resolve_province_center(province, centers)
            if lat is None or lng is None:
                continue

            if system_user is None:
                system_user = _ensure_system_user(user_email)

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
                address=f"Centro aproximado de {province}",
                province=province,
                municipality=None,
                movement_at=latest_snapshot.observed_at_utc,
                author_id=system_user.id,
                category_id=category.id,
                status="approved",
                is_anonymous=True,
            )
            db.session.add(post)
            created_provinces.append(province)

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
    }
