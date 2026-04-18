import csv
import html
import io
import json
import re
import secrets
import textwrap
import unicodedata
from datetime import datetime
from decimal import Decimal
from typing import Any

from flask import (
    abort,
    current_app,
    flash,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user
from sqlalchemy import func, or_
from sqlalchemy.orm import selectinload

from app.extensions import db, limiter
from app.models.category import Category
from app.models.donation_log import DonationLog
from app.models.location_report import LocationReport
from app.models.media import Media
from app.models.post import Post
from app.models.post_edit_request import PostEditRequest
from app.models.post_revision import PostRevision
from app.models.repressor import (
    REPRESSOR_VERIFY_LOCK_COUNT,
    Repressor,
    RepressorEditRequest,
    RepressorResidenceReport,
    RepressorRevision,
    RepressorSubmission,
)
from app.models.prisoner import Prisoner, PrisonerRevision
from app.models.role import Role
from app.models.site_setting import SiteSetting
from app.models.user import User
from app.models.vote_record import VoteRecord
from app.services.category_rules import is_other_type_allowed
from app.services.category_sort import sort_categories_for_forms
from app.services.ai_text import optimize_report_text
from app.services.content_quality import validate_description, validate_title
from app.services.geo_lookup import (
    is_within_cuba_bounds,
    list_municipalities,
    list_provinces,
    lookup_location,
    municipalities_map,
)
from app.services.location_names import (
    canonicalize_location_names,
    canonicalize_province_name,
    normalize_location_key,
)
from app.services.cuba_locations import PROVINCE_CENTER_FALLBACKS
from app.services.input_safety import has_malicious_input
from app.services.media_upload import (
    get_media_payload,
    media_json_from_post,
    parse_media_json,
    upload_files,
    validate_files,
)
from app.services.push_notifications import push_enabled, send_alert_notification
from app.services.recaptcha import recaptcha_enabled, verify_recaptcha
from app.services.repressors import (
    build_residence_post_description,
    build_residence_post_title,
    serialize_repressor,
)
from app.services.prisoners import serialize_prisoner
from app.services.repressor_submissions import (
    get_repressor_type_names,
    get_repressor_type_options,
    list_existing_repressor_crime_names,
    materialize_repressor_submission,
    normalize_list_items,
    parse_custom_crimes,
)
from app.services.repressor_edits import (
    apply_repressor_edit_request,
    snapshot_repressor,
)
from app.services.prisoner_edits import apply_prisoner_payload, snapshot_prisoner
from app.services.vote_identity import get_voter_hash
from app.services.map_providers import get_map_provider_forms, get_map_provider_main

from . import map_bp

URGENT_CATEGORY_SLUGS = {
    "accion-represiva",
    "accion-represiva-del-gobierno",
    "movimiento-tropas",
    "movimiento-militar",
    "desconexion-internet",
}

_REPRESSOR_VIEWER_STACK_KEY = "repressors_viewer_stack"
_REPRESSOR_VIEWER_INDEX_KEY = "repressors_viewer_index"
_AUTO_CONNECTIVITY_REPORT_MARKER = "auto_connectivity_cloudflare"
_TOKEN_SANITIZE_RE = re.compile(r"[^a-z0-9]+")
_MAP_LAYER_ALIASES = {
    "map": "map",
    "mapa": "map",
    "satellite": "satellite",
    "satelite": "satellite",
    "connectivity": "connectivity",
    "conectividad": "connectivity",
    "repressors": "repressors",
    "represores": "repressors",
    "prisoners": "prisoners",
    "prisioneros": "prisoners",
    "protests": "protests",
    "protestas": "protests",
    "ais": "ais",
    "buques": "ais",
    "buques-cuba": "ais",
    "ships": "ais",
    "vessels": "ais",
    "flights": "flights",
    "vuelos": "flights",
    "vuelos-cuba": "flights",
    "flights-cuba": "flights",
}
_REPRESSOR_TYPE_PALETTES = {
    "batablanca": {
        "bg": "linear-gradient(145deg, #d8f0ff 0%, #b8dfff 100%)",
        "border": "#75b7ef",
        "text": "#11314a",
    },
    "exportacion": {
        "bg": "linear-gradient(145deg, #ffe2a8 0%, #ffc969 100%)",
        "border": "#da9f36",
        "text": "#4a2b00",
    },
    "economico": {
        "bg": "linear-gradient(145deg, #c9f5c7 0%, #8de08a 100%)",
        "border": "#4faa55",
        "text": "#133f16",
    },
    "cuelloblanco": {
        "bg": "linear-gradient(145deg, #f2f4f7 0%, #dce3ea 100%)",
        "border": "#9eb2c7",
        "text": "#1f2b38",
    },
    "violento": {
        "bg": "linear-gradient(145deg, #ffc0b5 0%, #ff8f77 100%)",
        "border": "#d85a47",
        "text": "#4a1109",
    },
    "default": {
        "bg": "linear-gradient(145deg, #d5dcff 0%, #aeb9ff 100%)",
        "border": "#7787e2",
        "text": "#1a2150",
    },
}


def _google_maps_api_key():
    return (current_app.config.get("GOOGLE_MAPS_API_KEY") or "").strip()


def _get_chat_nick():
    allow_admin = current_user.is_authenticated and current_user.has_role(
        "administrador"
    )
    if current_user.is_authenticated and current_user.anon_code:
        return f"Anon-{current_user.anon_code}"
    nick = session.get("chat_nick")
    if nick and (nick.lower() != "admin" or allow_admin):
        return nick
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    code = "".join(secrets.choice(alphabet) for _ in range(6))
    nick = f"Anon-{code}"
    session["chat_nick"] = nick
    return nick


def _get_chat_session_id():
    sid = session.get("chat_sid")
    if sid:
        return sid
    sid = secrets.token_hex(16)
    session["chat_sid"] = sid
    return sid


def _get_verified_post_ids(post_ids):
    if not post_ids:
        return set()
    voter_hash = get_voter_hash(
        current_user, request, current_app.config.get("SECRET_KEY", "")
    )
    if not voter_hash:
        return set()
    rows = (
        VoteRecord.query.filter_by(target_type="post_verify", voter_hash=voter_hash)
        .filter(VoteRecord.target_id.in_(post_ids))
        .all()
    )
    return {row.target_id for row in rows}


def _get_verified_repressor_ids(repressor_ids):
    if not repressor_ids:
        return set()
    voter_hash = get_voter_hash(
        current_user, request, current_app.config.get("SECRET_KEY", "")
    )
    if not voter_hash:
        return set()
    rows = (
        VoteRecord.query.filter_by(
            target_type="repressor_verify",
            voter_hash=voter_hash,
        )
        .filter(VoteRecord.target_id.in_(repressor_ids))
        .all()
    )
    return {row.target_id for row in rows}


def _resolve_geo_location(lat, lng, province, municipality):
    try:
        auto_prov, auto_mun = lookup_location(lat, lng)
    except Exception:
        return province, municipality
    if auto_prov:
        province = auto_prov
    if auto_mun:
        municipality = auto_mun
    return province, municipality


def _matching_post_province_values(selected_province):
    canonical = canonicalize_province_name(selected_province)
    if not canonical:
        return []
    target_key = normalize_location_key(canonical)
    if not target_key:
        return []

    rows = (
        db.session.query(Post.province)
        .filter(
            Post.province.isnot(None),
            Post.province != "",
        )
        .distinct()
        .all()
    )

    values = []
    seen = set()
    for row in rows:
        raw_text = str(row[0] or "").strip()
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


def _clean_captions(raw, count):
    captions = []
    for idx in range(count):
        value = ""
        if raw and idx < len(raw):
            value = (raw[idx] or "").strip()
        if value:
            value = value[:255]
        captions.append(value)
    return captions


def _residence_category():
    return Category.query.filter_by(slug="residencia-represor").first()


def _latest_approved_repressor_residence_report(
    repressor_id: int,
    *,
    include_post: bool = False,
) -> RepressorResidenceReport | None:
    query = RepressorResidenceReport.query.filter_by(
        repressor_id=repressor_id,
        status="approved",
    )
    if include_post:
        query = query.options(selectinload(RepressorResidenceReport.created_post))
    return query.order_by(
        RepressorResidenceReport.created_at.desc(),
        RepressorResidenceReport.id.desc(),
    ).first()


def _repressor_confirmed_residence_url(repressor: Repressor) -> str | None:
    latest_report = _latest_approved_repressor_residence_report(
        repressor.id,
        include_post=True,
    )
    if latest_report is None:
        return None

    created_post = latest_report.created_post
    if created_post is not None and created_post.status == "approved":
        return url_for("map.report_detail", post_id=created_post.id)

    try:
        lat = float(latest_report.latitude)
        lng = float(latest_report.longitude)
    except Exception:
        return None
    if not is_within_cuba_bounds(lat, lng):
        return None
    return url_for("map.dashboard", lat=f"{lat:.6f}", lng=f"{lng:.6f}")


def _initial_repressor_residence_coords(repressor: Repressor) -> tuple[float, float]:
    latest_report = _latest_approved_repressor_residence_report(repressor.id)
    if latest_report is not None:
        try:
            lat = float(latest_report.latitude)
            lng = float(latest_report.longitude)
            if is_within_cuba_bounds(lat, lng):
                return lat, lng
        except Exception:
            pass

    canonical_province = canonicalize_province_name(repressor.province_name)
    fallback = PROVINCE_CENTER_FALLBACKS.get(canonical_province or "")
    if isinstance(fallback, (list, tuple)) and len(fallback) >= 2:
        try:
            lat = float(fallback[0])
            lng = float(fallback[1])
            if is_within_cuba_bounds(lat, lng):
                return lat, lng
        except Exception:
            pass

    return 23.1136, -82.3666


def _is_moderation_enabled() -> bool:
    moderation_setting = SiteSetting.query.filter_by(key="moderation_enabled").first()
    if moderation_setting is None:
        return True
    return moderation_setting.value == "true"


def _normalize_token(value: str) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return _TOKEN_SANITIZE_RE.sub("", text)


def _palette_for_type_name(type_name: str) -> dict[str, str]:
    key = _normalize_token(type_name)
    return _REPRESSOR_TYPE_PALETTES.get(key) or _REPRESSOR_TYPE_PALETTES["default"]


def _build_repressor_type_legend():
    legend: list[dict[str, str]] = []
    for item in get_repressor_type_options():
        name = (item.get("name") or "").strip()
        if not name:
            continue
        palette = _palette_for_type_name(name)
        legend.append(
            {
                "name": name,
                "description": (item.get("description") or "").strip(),
                "bg": palette["bg"],
                "border": palette["border"],
                "text": palette["text"],
            }
        )
    return legend


def _build_repressor_type_badges(repressor: Repressor):
    options_by_key = {
        _normalize_token(item.get("name")): (item.get("description") or "").strip()
        for item in get_repressor_type_options()
        if (item.get("name") or "").strip()
    }
    badges: list[dict[str, str]] = []
    for item in repressor.types:
        name = (item.name or "").strip()
        if not name:
            continue
        palette = _palette_for_type_name(name)
        description = options_by_key.get(_normalize_token(name)) or "Sin descripción disponible."
        badges.append(
            {
                "name": name,
                "bg": palette["bg"],
                "border": palette["border"],
                "text": palette["text"],
                "description": description,
            }
        )
    return badges


def _load_viewer_history_state() -> tuple[list[int], int]:
    raw_stack = session.get(_REPRESSOR_VIEWER_STACK_KEY, [])
    stack: list[int] = []
    if isinstance(raw_stack, list):
        for raw in raw_stack:
            try:
                value = int(raw)
            except Exception:
                continue
            if value > 0:
                stack.append(value)
    if len(stack) > 300:
        stack = stack[-300:]

    try:
        index = int(session.get(_REPRESSOR_VIEWER_INDEX_KEY, len(stack) - 1))
    except Exception:
        index = len(stack) - 1
    if not stack:
        index = -1
    if index < 0:
        index = 0
    if stack and index >= len(stack):
        index = len(stack) - 1
    return stack, index


def _save_viewer_history_state(stack: list[int], index: int) -> None:
    if len(stack) > 300:
        stack = stack[-300:]
        index = min(index, len(stack) - 1)
    session[_REPRESSOR_VIEWER_STACK_KEY] = stack
    session[_REPRESSOR_VIEWER_INDEX_KEY] = index


def _pick_random_repressor_id(exclude_id: int | None = None) -> int | None:
    query = db.session.query(Repressor.id)
    if exclude_id is not None:
        query = query.filter(Repressor.id != exclude_id)
    row = query.order_by(func.random()).first()
    if not row:
        return None
    try:
        return int(row[0])
    except Exception:
        return None


def _serialize_residence_report(report: RepressorResidenceReport):
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
        "created_at": report.created_at.isoformat() if report.created_at else None,
    }


def _normalize_map_layer(value: str | None, *, allow_admin_layers: bool = False) -> str:
    raw = (value or "").strip().lower()
    normalized = _MAP_LAYER_ALIASES.get(raw, "map")
    if normalized == "ais" and not allow_admin_layers:
        return "map"
    return normalized


@map_bp.route("/")
@map_bp.route("/map=<string:layer_slug>")
def dashboard(layer_slug: str | None = None):
    categories = Category.query.order_by(Category.id.asc()).all()
    posts = Post.query.filter_by(status="approved").all()
    map_provider_main = get_map_provider_main()
    allow_admin_layers = current_user.is_authenticated and current_user.has_role(
        "administrador"
    )
    initial_base_mode = _normalize_map_layer(
        layer_slug, allow_admin_layers=allow_admin_layers
    )
    return render_template(
        "map/dashboard.html",
        categories=categories,
        posts=posts,
        vapid_public_key=current_app.config.get("VAPID_PUBLIC_KEY"),
        push_alerts_enabled=push_enabled(),
        chat_nick=_get_chat_nick(),
        chat_sid=_get_chat_session_id(),
        irc_nick=_get_chat_nick(),
        provinces=list_provinces(),
        municipalities_map=municipalities_map(),
        connectivity_refresh_seconds=current_app.config.get(
            "CONNECTIVITY_FRONTEND_REFRESH_SECONDS", 300
        ),
        protest_refresh_seconds=current_app.config.get(
            "PROTEST_FRONTEND_REFRESH_SECONDS", 300
        ),
        ais_refresh_seconds=current_app.config.get(
            "AISSTREAM_FRONTEND_REFRESH_SECONDS", 1800
        ),
        flights_refresh_seconds=current_app.config.get(
            "FLIGHTS_FRONTEND_REFRESH_SECONDS", 300
        ),
        map_provider_main=map_provider_main,
        google_maps_api_key=_google_maps_api_key(),
        initial_base_mode=initial_base_mode,
        map_layer_route_template=url_for("map.dashboard", layer_slug="__layer__"),
    )


@map_bp.route("/push-sw.js")
def push_service_worker():
    response = current_app.send_static_file("push-sw.js")
    response.headers["Cache-Control"] = "no-cache"
    return response


def _export_columns():
    return [
        ("id", "ID"),
        ("title", "Título"),
        ("description", "Descripción"),
        ("category", "Categoría"),
        ("province", "Provincia"),
        ("municipality", "Municipio"),
        ("latitude", "Latitud"),
        ("longitude", "Longitud"),
        ("address", "Dirección"),
        ("repressor_name", "Represor"),
        ("other_type", "Tipo (Otros)"),
        ("verify_count", "Verificaciones"),
        ("links", "Enlaces"),
        ("created_at", "Creado"),
        ("updated_at", "Actualizado"),
    ]


def _serialize_export_row(post):
    links = []
    if post.links_json:
        try:
            links = json.loads(post.links_json) or []
        except Exception:
            links = []
    return {
        "id": post.id,
        "title": post.title,
        "description": post.description,
        "category": post.category.name if post.category else "",
        "province": post.province or "",
        "municipality": post.municipality or "",
        "latitude": str(post.latitude) if post.latitude is not None else "",
        "longitude": str(post.longitude) if post.longitude is not None else "",
        "address": post.address or "",
        "repressor_name": post.repressor_name or "",
        "other_type": post.other_type or "",
        "verify_count": post.verify_count or 0,
        "links": ", ".join(links),
        "created_at": post.created_at.isoformat() if post.created_at else "",
        "updated_at": post.updated_at.isoformat() if post.updated_at else "",
    }


def _load_export_posts():
    return (
        Post.query.options(selectinload(Post.category))
        .filter_by(status="approved")
        .order_by(Post.created_at.desc())
        .all()
    )


@map_bp.route("/exportar")
def export_data():
    return render_template("map/export.html")


@map_bp.route("/exportar/descargar")
def export_download():
    fmt = (request.args.get("format") or "csv").lower()
    if fmt not in {"csv", "xls", "txt", "pdf"}:
        abort(400)

    columns = _export_columns()
    posts = _load_export_posts()
    rows = [_serialize_export_row(post) for post in posts]
    filename = f"soscubamap_reportes_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.{fmt}"

    if fmt in {"csv", "txt"}:
        output = io.StringIO()
        delimiter = "," if fmt == "csv" else "\t"
        writer = csv.writer(output, delimiter=delimiter)
        writer.writerow([label for _, label in columns])
        for row in rows:
            writer.writerow([row[key] for key, _ in columns])
        resp = make_response(output.getvalue())
        mime = "text/csv" if fmt == "csv" else "text/plain"
        resp.headers["Content-Type"] = f"{mime}; charset=utf-8"
        resp.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        return resp

    if fmt == "xls":
        header_cells = "".join(f"<th>{html.escape(label)}</th>" for _, label in columns)
        body_rows = []
        for row in rows:
            cells = "".join(
                f"<td>{html.escape(str(row[key] if row[key] is not None else ''))}</td>"
                for key, _ in columns
            )
            body_rows.append(f"<tr>{cells}</tr>")
        table_html = (
            '<table border="1">'
            f"<thead><tr>{header_cells}</tr></thead>"
            f"<tbody>{''.join(body_rows)}</tbody>"
            "</table>"
        )
        html_doc = (
            '<!doctype html><html><head><meta charset="utf-8"></head>'
            f"<body>{table_html}</body></html>"
        )
        resp = make_response(html_doc)
        resp.headers["Content-Type"] = "application/vnd.ms-excel; charset=utf-8"
        resp.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        return resp

    # PDF (solo texto)
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
    except Exception:
        resp = make_response("PDF no disponible en el servidor.", 501)
        resp.headers["Content-Type"] = "text/plain; charset=utf-8"
        return resp

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    margin = 36
    y = height - margin
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(margin, y, "SOSCuba Map · Exportación de reportes (solo texto)")
    y -= 18
    pdf.setFont("Helvetica", 9)
    pdf.drawString(margin, y, f"Generado: {datetime.utcnow().isoformat()} UTC")
    y -= 18

    def write_line(text):
        nonlocal y
        if y < margin:
            pdf.showPage()
            y = height - margin
            pdf.setFont("Helvetica", 9)
        pdf.drawString(margin, y, text)
        y -= 12

    wrap_width = 110
    for row in rows:
        write_line(f"Reporte #{row['id']}")
        for key, label in columns:
            value = row.get(key, "")
            if value is None:
                value = ""
            text = f"{label}: {value}"
            for line in textwrap.wrap(text, width=wrap_width) or [""]:
                write_line(line)
        write_line("-" * 80)
        y -= 6

    pdf.showPage()
    pdf.save()
    pdf_bytes = buffer.getvalue()
    buffer.close()
    resp = make_response(pdf_bytes)
    resp.headers["Content-Type"] = "application/pdf"
    resp.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp


@map_bp.route("/api-docs")
def api_docs():
    base_url = request.host_url.rstrip("/")
    return render_template("map/api_docs.html", base_url=base_url)


@map_bp.route("/analiticas")
def analytics():
    categories = Category.query.order_by(Category.id.asc()).all()
    return render_template(
        "map/analytics.html",
        categories=categories,
        provinces=list_provinces(),
    )


@map_bp.route("/nuevo", methods=["GET", "POST"])
@limiter.limit("3/minute; 30/day", methods=["POST"])
def new_post():
    categories = sort_categories_for_forms(
        Category.query.order_by(Category.id.asc()).all()
    )
    if request.method == "POST":
        form_data = {
            "title": request.form.get("title", "").strip(),
            "description": request.form.get("description", "").strip(),
            "category_id": request.form.get("category_id", "").strip(),
            "latitude": request.form.get("latitude", "").strip(),
            "longitude": request.form.get("longitude", "").strip(),
            "address": request.form.get("address", "").strip(),
            "province": request.form.get("province", "").strip(),
            "municipality": request.form.get("municipality", "").strip(),
            "movement_date": request.form.get("movement_date", "").strip(),
            "movement_time": request.form.get("movement_time", "").strip(),
            "repressor_name": request.form.get("repressor_name", "").strip(),
            "other_type": request.form.get("other_type", "").strip(),
            "polygon_geojson": request.form.get("polygon_geojson", "").strip(),
        }
        images = [
            file
            for file in request.files.getlist("images")
            if file and (file.filename or "").strip()
        ]
        image_captions = request.form.getlist("image_captions[]")
        links = request.form.getlist("links[]")
        links = [link.strip() for link in links if link.strip()]
        errors = {}

        if recaptcha_enabled():
            token = request.form.get("g-recaptcha-response", "")
            if not verify_recaptcha(token, request.remote_addr):
                errors["recaptcha"] = (
                    "Verificación reCAPTCHA falló. Intenta nuevamente."
                )

        if has_malicious_input(
            [
                form_data["title"],
                form_data["description"],
                form_data["address"],
                form_data["province"],
                form_data["municipality"],
                form_data["movement_date"],
                form_data["movement_time"],
                form_data["repressor_name"],
                form_data["other_type"],
            ]
            + links
        ):
            errors["form"] = (
                "Se detectó contenido sospechoso. Revisa y vuelve a intentar."
            )

        if not form_data["title"]:
            errors["title"] = "El título es obligatorio."
        if not form_data["description"]:
            errors["description"] = "La descripción es obligatoria."
        if not form_data["category_id"]:
            errors["category_id"] = "Selecciona una categoría."
        if not form_data["latitude"]:
            errors["latitude"] = "La latitud es obligatoria."
        if not form_data["longitude"]:
            errors["longitude"] = "La longitud es obligatoria."

        if form_data["title"] and "title" not in errors:
            ok_title, msg_title = validate_title(form_data["title"])
            if not ok_title:
                errors["title"] = msg_title
        if form_data["description"] and "description" not in errors:
            if len(form_data["description"]) < 50:
                errors["description"] = (
                    "La descripción debe tener al menos 50 caracteres."
                )
            else:
                ok_desc, msg_desc = validate_description(form_data["description"])
                if not ok_desc:
                    errors["description"] = msg_desc

        category = None
        if form_data["category_id"]:
            try:
                category = Category.query.get(int(form_data["category_id"]))
            except Exception:
                errors["category_id"] = "Selecciona una categoría válida."
        slug = category.slug if category else ""
        is_urgent = slug in URGENT_CATEGORY_SLUGS
        movement_at = None
        if slug == "residencia-represor":
            if not form_data["repressor_name"]:
                errors["repressor_name"] = (
                    "Debes indicar el nombre o apodo del represor."
                )
            if not images:
                errors["images"] = "Debes subir al menos una imagen del represor."
        if slug in URGENT_CATEGORY_SLUGS:
            if not form_data["movement_date"]:
                errors["movement_date"] = "Debes indicar la fecha del evento."
            if not form_data["movement_time"]:
                errors["movement_time"] = "Debes indicar la hora del evento."
            if not errors.get("movement_date") and not errors.get("movement_time"):
                try:
                    movement_at = datetime.fromisoformat(
                        f"{form_data['movement_date']}T{form_data['movement_time']}"
                    )
                except Exception:
                    errors["movement_date"] = "Fecha u hora inválida."
        if slug == "otros":
            if not form_data["other_type"]:
                errors["other_type"] = (
                    "Debes especificar el tipo en la categoría Otros."
                )
            elif not is_other_type_allowed(form_data["other_type"]):
                errors["other_type"] = (
                    "El tipo en “Otros” no puede referirse a represores. Usa la categoría correspondiente."
                )
        if images and "images" not in errors:
            ok, error = validate_files(images)
            if not ok:
                errors["images"] = error

        lat = None
        lng = None
        if "latitude" not in errors and "longitude" not in errors:
            try:
                lat = Decimal(form_data["latitude"])
                lng = Decimal(form_data["longitude"])
            except Exception:
                errors["latitude"] = "Latitud inválida."
                errors["longitude"] = "Longitud inválida."

        if lat is not None and lng is not None and not is_within_cuba_bounds(lat, lng):
            errors["latitude"] = "La ubicación debe estar dentro del territorio cubano."
            errors["longitude"] = "La ubicación debe estar dentro del territorio cubano."

        if lat is not None and lng is not None:
            province, municipality = _resolve_geo_location(
                lat, lng, form_data["province"], form_data["municipality"]
            )
            form_data["province"] = province or ""
            form_data["municipality"] = municipality or ""

        if not form_data["province"]:
            errors["province"] = "Provincia obligatoria."
        if not form_data["municipality"]:
            errors["municipality"] = "Municipio obligatorio."

        if errors:
            moderation_setting = SiteSetting.query.filter_by(
                key="moderation_enabled"
            ).first()
            moderation_enabled = True
            if moderation_setting:
                moderation_enabled = moderation_setting.value == "true"
            return render_template(
                "map/new_post.html",
                categories=categories,
                preset_lat=form_data["latitude"],
                preset_lng=form_data["longitude"],
                preset_zoom=request.args.get("zoom", ""),
                moderation_enabled=moderation_enabled,
                provinces=list_provinces(),
                municipalities_map=municipalities_map(),
                recaptcha_site_key=current_app.config.get("RECAPTCHA_V2_SITE_KEY"),
                map_provider_forms=get_map_provider_forms(),
                google_maps_api_key=_google_maps_api_key(),
                form_data=form_data,
                errors=errors,
                form_links=links,
            )

        try:
            lat = Decimal(form_data["latitude"])
            lng = Decimal(form_data["longitude"])
        except Exception:
            flash("Latitud/longitud inválidas.", "error")
            return redirect(url_for("map.new_post"))

        if not is_within_cuba_bounds(lat, lng):
            flash("La ubicación debe estar dentro del territorio cubano.", "error")
            return redirect(url_for("map.new_post"))

        province, municipality = _resolve_geo_location(
            lat, lng, form_data["province"], form_data["municipality"]
        )
        if not province or not municipality:
            flash("Provincia y municipio son obligatorios.", "error")
            return redirect(url_for("map.new_post"))

        author_id = None
        if current_user.is_authenticated:
            author_id = current_user.id
        else:
            # Create a one-off anonymous user for this report
            anon_user = User(email=f"anon+{secrets.token_hex(6)}@local")
            anon_user.set_password(secrets.token_urlsafe(16))
            anon_user.ensure_anon_code()
            default_role = Role.query.filter_by(name="colaborador").first()
            if default_role:
                anon_user.roles.append(default_role)
            db.session.add(anon_user)
            db.session.flush()
            author_id = anon_user.id

        moderation_setting = SiteSetting.query.filter_by(
            key="moderation_enabled"
        ).first()
        moderation_enabled = True
        if moderation_setting:
            moderation_enabled = moderation_setting.value == "true"

        post = Post(
            title=form_data["title"],
            description=form_data["description"],
            category_id=int(form_data["category_id"]),
            latitude=lat,
            longitude=lng,
            address=form_data["address"] or None,
            province=province or None,
            municipality=municipality or None,
            movement_at=movement_at,
            repressor_name=form_data["repressor_name"] or None,
            other_type=form_data["other_type"] or None,
            polygon_geojson=form_data["polygon_geojson"] or None,
            links_json=json.dumps(links) if links else None,
            author_id=author_id,
        )
        post.status = "approved" if is_urgent or not moderation_enabled else "pending"
        db.session.add(post)
        db.session.commit()

        if images:
            media_urls = upload_files(images)
            captions = _clean_captions(image_captions, len(media_urls))
            for idx, url in enumerate(media_urls):
                caption = captions[idx] if idx < len(captions) else ""
                db.session.add(
                    Media(post_id=post.id, file_url=url, caption=caption or None)
                )
            db.session.commit()

        if is_urgent and post.status == "approved":
            try:
                send_alert_notification(post)
            except Exception:
                current_app.logger.exception("No se pudo enviar notificación push.")

        payload = {
            "id": post.id,
            "status": post.status,
            "title": post.title,
            "description": post.description,
            "latitude": float(post.latitude),
            "longitude": float(post.longitude),
            "address": post.address,
            "category": {"name": post.category.name, "slug": post.category.slug},
            "verify_count": post.verify_count or 0,
            "created_at": post.created_at.isoformat(),
            "movement_at": post.movement_at.isoformat() if post.movement_at else None,
        }

        # If submitted from iframe modal, return a script that closes the modal and refreshes map
        if request.args.get("modal") == "1":
            return render_template("map/report_success.html", payload=payload)

        if post.status == "pending":
            flash("Reporte enviado a moderación.", "success")
        else:
            flash("Reporte publicado.", "success")
        return redirect(url_for("map.dashboard"))

    preset_lat = request.args.get("lat", "")
    preset_lng = request.args.get("lng", "")
    preset_zoom = request.args.get("zoom", "")
    preset_province = ""
    preset_municipality = ""
    if preset_lat and preset_lng:
        try:
            lat = Decimal(preset_lat)
            lng = Decimal(preset_lng)
            preset_province, preset_municipality = _resolve_geo_location(
                lat, lng, "", ""
            )
        except Exception:
            preset_province = ""
            preset_municipality = ""
    moderation_setting = SiteSetting.query.filter_by(key="moderation_enabled").first()
    moderation_enabled = True
    if moderation_setting:
        moderation_enabled = moderation_setting.value == "true"

    return render_template(
        "map/new_post.html",
        categories=categories,
        preset_lat=preset_lat,
        preset_lng=preset_lng,
        preset_zoom=preset_zoom,
        preset_province=preset_province,
        preset_municipality=preset_municipality,
        moderation_enabled=moderation_enabled,
        provinces=list_provinces(),
        municipalities_map=municipalities_map(),
        recaptcha_site_key=current_app.config.get("RECAPTCHA_V2_SITE_KEY"),
        map_provider_forms=get_map_provider_forms(),
        google_maps_api_key=_google_maps_api_key(),
        form_data=None,
        errors={},
        form_links=[],
    )


@map_bp.route("/donar")
def donate():
    logs = DonationLog.query.order_by(DonationLog.donated_at.desc()).all()
    return render_template("map/donate.html", donation_logs=logs)


@map_bp.route("/acerca")
def about():
    return render_template("map/about.html")


@map_bp.route("/reportar-ubicacion/<int:post_id>", methods=["GET", "POST"])
@limiter.limit("5/minute; 50/day", methods=["POST"])
def report_location(post_id):
    post = Post.query.get_or_404(post_id)
    submitted = False
    if request.method == "POST":
        message = request.form.get("message", "").strip()
        if has_malicious_input([message]):
            flash(
                "Se detectó contenido sospechoso. Revisa y vuelve a intentar.", "error"
            )
        elif not message:
            flash("Describe por qué la ubicación es incorrecta.", "error")
        else:
            db.session.add(LocationReport(post_id=post.id, message=message))
            db.session.commit()
            submitted = True
    return render_template("map/report_location.html", post=post, submitted=submitted)


def _get_or_create_anon_editor():
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


def _is_admin_user():
    return current_user.is_authenticated and current_user.has_role("administrador")


def _is_edit_locked(post: Post) -> bool:
    return (post.verify_count or 0) >= 10 and not _is_admin_user()


def _is_repressor_profile_locked(repressor: Repressor) -> bool:
    return (repressor.verify_count or 0) >= REPRESSOR_VERIFY_LOCK_COUNT


def _get_editor_identity():
    editor = _get_or_create_anon_editor()
    if editor and editor.anon_code:
        return editor, f"Anon-{editor.anon_code}"
    if editor and editor.email:
        return editor, editor.email
    return editor, "Anon"


@map_bp.route("/reporte/<int:post_id>/ia/optimizar", methods=["POST"])
@limiter.limit("5/minute; 40/hour", methods=["POST"])
def optimize_report_text_ai(post_id):
    if not _is_admin_user():
        return jsonify({"ok": False, "error": "No autorizado."}), 403

    post = Post.query.get_or_404(post_id)
    payload = request.get_json(silent=True) or {}

    field = (payload.get("field") or "").strip().lower()
    text = payload.get("text") or ""
    title_context = (payload.get("title_context") or "").strip() or post.title
    description_context = (payload.get("description_context") or "").strip() or post.description

    try:
        optimized = optimize_report_text(
            field,
            text,
            title_context=title_context,
            description_context=description_context,
        )
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 503
    except Exception:
        current_app.logger.exception("Error al optimizar texto con IA")
        return (
            jsonify({"ok": False, "error": "No se pudo optimizar el texto en este momento."}),
            502,
        )

    if field == "title":
        ok, error = validate_title(optimized)
    else:
        ok, error = validate_description(optimized)

    if not ok:
        return (
            jsonify(
                {
                    "ok": False,
                    "error": f"La IA devolvio un texto invalido: {error}",
                }
            ),
            422,
        )

    return jsonify({"ok": True, "field": field, "optimized_text": optimized})


@map_bp.route("/reporte/<int:post_id>/editar", methods=["GET", "POST"])
@limiter.limit("3/minute; 30/day", methods=["POST"])
def edit_report_public(post_id):
    post = Post.query.get_or_404(post_id)
    if _is_edit_locked(post):
        message = (
            "Este reporte ya tiene 10 verificaciones y solo el admin puede editarlo. "
            "Aun puedes comentar notas y reportar ubicacion si detectas un dato erroneo."
        )
        if request.args.get("modal") == "1":
            return render_template(
                "map/edit_locked.html", message=message, post_id=post.id
            )
        flash(message, "error")
        return redirect(url_for("map.report_detail", post_id=post.id))
    categories = sort_categories_for_forms(
        Category.query.order_by(Category.id.asc()).all()
    )
    links = []
    if post.links_json:
        try:
            links = json.loads(post.links_json)
        except Exception:
            links = []

    if request.method == "POST":
        form_data = {
            "title": request.form.get("title", "").strip(),
            "description": request.form.get("description", "").strip(),
            "edit_reason": request.form.get("edit_reason", "").strip(),
            "category_id": request.form.get("category_id", "").strip(),
            "latitude": request.form.get("latitude", "").strip(),
            "longitude": request.form.get("longitude", "").strip(),
            "address": request.form.get("address", "").strip(),
            "province": request.form.get("province", "").strip(),
            "municipality": request.form.get("municipality", "").strip(),
            "movement_date": request.form.get("movement_date", "").strip(),
            "movement_time": request.form.get("movement_time", "").strip(),
            "repressor_name": request.form.get("repressor_name", "").strip(),
            "other_type": request.form.get("other_type", "").strip(),
            "polygon_geojson": request.form.get("polygon_geojson", "").strip(),
        }
        images = [
            file
            for file in request.files.getlist("images")
            if file and (file.filename or "").strip()
        ]
        image_captions = request.form.getlist("image_captions[]")
        links_list = request.form.getlist("links[]")
        links_list = [link.strip() for link in links_list if link.strip()]
        errors = {}

        if recaptcha_enabled():
            token = request.form.get("g-recaptcha-response", "")
            if not verify_recaptcha(token, request.remote_addr):
                errors["recaptcha"] = (
                    "Verificación reCAPTCHA falló. Intenta nuevamente."
                )

        if has_malicious_input(
            [
                form_data["title"],
                form_data["description"],
                form_data["edit_reason"],
                form_data["address"],
                form_data["province"],
                form_data["municipality"],
                form_data["movement_date"],
                form_data["movement_time"],
                form_data["repressor_name"],
                form_data["other_type"],
            ]
            + links_list
        ):
            errors["form"] = (
                "Se detectó contenido sospechoso. Revisa y vuelve a intentar."
            )

        if not form_data["title"]:
            errors["title"] = "El título es obligatorio."
        if not form_data["description"]:
            errors["description"] = "La descripción es obligatoria."
        if not form_data["edit_reason"]:
            errors["edit_reason"] = "El motivo de edición es obligatorio."
        if not form_data["category_id"]:
            errors["category_id"] = "Selecciona una categoría."
        if not form_data["latitude"]:
            errors["latitude"] = "La latitud es obligatoria."
        if not form_data["longitude"]:
            errors["longitude"] = "La longitud es obligatoria."

        if form_data["title"] and "title" not in errors:
            ok_title, msg_title = validate_title(form_data["title"])
            if not ok_title:
                errors["title"] = msg_title
        if form_data["description"] and "description" not in errors:
            if len(form_data["description"]) < 50:
                errors["description"] = (
                    "La descripción debe tener al menos 50 caracteres."
                )
            else:
                ok_desc, msg_desc = validate_description(form_data["description"])
                if not ok_desc:
                    errors["description"] = msg_desc

        category = None
        if form_data["category_id"]:
            try:
                category = Category.query.get(int(form_data["category_id"]))
            except Exception:
                errors["category_id"] = "Selecciona una categoría válida."
        slug = category.slug if category else ""
        is_urgent = slug in URGENT_CATEGORY_SLUGS
        existing_media_count = len(get_media_payload(post))
        movement_at = None
        if slug == "residencia-represor":
            if not form_data["repressor_name"]:
                errors["repressor_name"] = (
                    "Debes indicar el nombre o apodo del represor."
                )
            if existing_media_count + len(images) < 1:
                errors["images"] = "Debes subir al menos una imagen del represor."
        if slug in URGENT_CATEGORY_SLUGS:
            if not form_data["movement_date"]:
                errors["movement_date"] = "Debes indicar la fecha del evento."
            if not form_data["movement_time"]:
                errors["movement_time"] = "Debes indicar la hora del evento."
            if not errors.get("movement_date") and not errors.get("movement_time"):
                try:
                    movement_at = datetime.fromisoformat(
                        f"{form_data['movement_date']}T{form_data['movement_time']}"
                    )
                except Exception:
                    errors["movement_date"] = "Fecha u hora inválida."
        if slug == "otros":
            if not form_data["other_type"]:
                errors["other_type"] = (
                    "Debes especificar el tipo en la categoría Otros."
                )
            elif not is_other_type_allowed(form_data["other_type"]):
                errors["other_type"] = (
                    "El tipo en “Otros” no puede referirse a represores. Usa la categoría correspondiente."
                )
        if images and "images" not in errors:
            ok, error = validate_files(images)
            if not ok:
                errors["images"] = error

        lat = None
        lng = None
        if "latitude" not in errors and "longitude" not in errors:
            try:
                lat = Decimal(form_data["latitude"])
                lng = Decimal(form_data["longitude"])
            except Exception:
                errors["latitude"] = "Latitud inválida."
                errors["longitude"] = "Longitud inválida."

        if lat is not None and lng is not None:
            province, municipality = _resolve_geo_location(
                lat, lng, form_data["province"], form_data["municipality"]
            )
            form_data["province"] = province or ""
            form_data["municipality"] = municipality or ""

        if not form_data["province"]:
            errors["province"] = "Provincia obligatoria."
        if not form_data["municipality"]:
            errors["municipality"] = "Municipio obligatorio."

        if errors:
            moderation_setting = SiteSetting.query.filter_by(
                key="moderation_enabled"
            ).first()
            moderation_enabled = True
            if moderation_setting:
                moderation_enabled = moderation_setting.value == "true"
            return render_template(
                "map/edit_report.html",
                post=post,
                categories=categories,
                links=links,
                form_links=links_list,
                form_data=form_data,
                errors=errors,
                media_items=get_media_payload(post),
                moderation_enabled=moderation_enabled,
                provinces=list_provinces(),
                municipalities_map=municipalities_map(),
                recaptcha_site_key=current_app.config.get("RECAPTCHA_V2_SITE_KEY"),
                map_provider_forms=get_map_provider_forms(),
                google_maps_api_key=_google_maps_api_key(),
            )

        try:
            lat = Decimal(form_data["latitude"])
            lng = Decimal(form_data["longitude"])
        except Exception:
            flash("Latitud/longitud inválidas.", "error")
            return redirect(url_for("map.edit_report_public", post_id=post.id))

        province, municipality = _resolve_geo_location(
            lat, lng, form_data["province"], form_data["municipality"]
        )
        if not province or not municipality:
            flash("Provincia y municipio son obligatorios.", "error")
            return redirect(url_for("map.edit_report_public", post_id=post.id))

        moderation_setting = SiteSetting.query.filter_by(
            key="moderation_enabled"
        ).first()
        moderation_enabled = True
        if moderation_setting:
            moderation_enabled = moderation_setting.value == "true"

        editor = _get_or_create_anon_editor()
        editor_label = (
            f"Anon-{editor.anon_code}" if editor and editor.anon_code else "Anon"
        )
        media_urls = []
        media_items = []
        if images:
            media_urls = upload_files(images)
            if not media_urls:
                flash("No se pudo subir la imagen.", "error")
                return redirect(url_for("map.edit_report_public", post_id=post.id))
            captions = _clean_captions(image_captions, len(media_urls))
            media_items = [
                {"url": url, "caption": (captions[idx] if idx < len(captions) else "")}
                for idx, url in enumerate(media_urls)
            ]

        if moderation_enabled and not is_urgent:
            combined_media = None
            if media_items:
                combined_media = get_media_payload(post) + media_items
            edit_req = PostEditRequest(
                post_id=post.id,
                editor_id=editor.id if editor else None,
                editor_label=editor_label,
                reason=form_data["edit_reason"],
                title=form_data["title"],
                description=form_data["description"],
                latitude=lat,
                longitude=lng,
                address=form_data["address"] or None,
                province=province or None,
                municipality=municipality or None,
                movement_at=movement_at,
                repressor_name=form_data["repressor_name"] or None,
                other_type=form_data["other_type"] or None,
                category_id=int(form_data["category_id"]),
                polygon_geojson=form_data["polygon_geojson"] or None,
                links_json=json.dumps(links_list) if links_list else None,
                media_json=(
                    json.dumps(combined_media) if combined_media is not None else None
                ),
            )
            db.session.add(edit_req)
            db.session.commit()
            payload = {"status": "pending"}
            if request.args.get("modal") == "1":
                return render_template("map/edit_success.html", payload=payload)
            flash("Edición enviada a moderación.", "success")
            return redirect(url_for("map.dashboard"))

        # Sin moderación: aplicar directo y guardar revisión
        revision = PostRevision(
            post_id=post.id,
            editor_id=editor.id if editor else None,
            editor_label=editor_label,
            reason=form_data["edit_reason"],
            title=post.title,
            description=post.description,
            latitude=post.latitude,
            longitude=post.longitude,
            address=post.address,
            province=post.province,
            municipality=post.municipality,
            movement_at=post.movement_at,
            repressor_name=post.repressor_name,
            other_type=post.other_type,
            category_id=post.category_id,
            polygon_geojson=post.polygon_geojson,
            links_json=post.links_json,
            media_json=media_json_from_post(post),
        )
        db.session.add(revision)

        post.title = form_data["title"]
        post.description = form_data["description"]
        post.category_id = int(form_data["category_id"])
        post.latitude = lat
        post.longitude = lng
        post.address = form_data["address"] or None
        post.province = province or None
        post.municipality = municipality or None
        post.movement_at = movement_at
        post.repressor_name = form_data["repressor_name"] or None
        post.other_type = form_data["other_type"] or None
        post.polygon_geojson = form_data["polygon_geojson"] or None
        post.links_json = json.dumps(links_list) if links_list else None
        if media_items:
            for item in media_items:
                db.session.add(
                    Media(
                        post_id=post.id,
                        file_url=item.get("url"),
                        caption=(item.get("caption") or None),
                    )
                )
        db.session.commit()

        payload = {"status": "approved"}
        if request.args.get("modal") == "1":
            return render_template("map/edit_success.html", payload=payload)
        flash("Edición aplicada.", "success")
        return redirect(url_for("map.dashboard"))

    moderation_setting = SiteSetting.query.filter_by(key="moderation_enabled").first()
    moderation_enabled = True
    if moderation_setting:
        moderation_enabled = moderation_setting.value == "true"

    return render_template(
        "map/edit_report.html",
        post=post,
        categories=categories,
        links=links,
        media_items=get_media_payload(post),
        moderation_enabled=moderation_enabled,
        provinces=list_provinces(),
        municipalities_map=municipalities_map(),
        recaptcha_site_key=current_app.config.get("RECAPTCHA_V2_SITE_KEY"),
        map_provider_forms=get_map_provider_forms(),
        google_maps_api_key=_google_maps_api_key(),
        form_data=None,
        errors={},
        form_links=links,
    )


@map_bp.route("/reporte/<int:post_id>")
def report_detail(post_id):
    post = (
        Post.query.options(
            selectinload(Post.repressor).selectinload(Repressor.crimes),
            selectinload(Post.repressor).selectinload(Repressor.types),
        )
        .filter_by(id=post_id)
        .first_or_404()
    )
    if post.status != "approved":
        allowed = current_user.is_authenticated and (
            current_user.has_role("moderador") or current_user.has_role("administrador")
        )
        if not allowed:
            abort(404)

    links = []
    if post.links_json:
        try:
            links = json.loads(post.links_json)
        except Exception:
            links = []

    anon_label = (
        f"Anon-{post.author.anon_code}"
        if post.author and post.author.anon_code
        else "Anon"
    )
    moderation_setting = SiteSetting.query.filter_by(key="moderation_enabled").first()
    moderation_enabled = True
    if moderation_setting:
        moderation_enabled = moderation_setting.value == "true"
    verified_by_me = post.id in _get_verified_post_ids([post.id])
    return render_template(
        "map/report_detail.html",
        post=post,
        links=links,
        anon_label=anon_label,
        media_items=get_media_payload(post),
        moderation_enabled=moderation_enabled,
        edit_locked=_is_edit_locked(post),
        recaptcha_site_key=current_app.config.get("RECAPTCHA_V2_SITE_KEY"),
        verified_by_me=verified_by_me,
    )


@map_bp.route("/reporte/<int:post_id>/historial")
def post_history(post_id):
    post = Post.query.get_or_404(post_id)
    revisions = (
        PostRevision.query.filter_by(post_id=post.id)
        .order_by(PostRevision.created_at.desc())
        .all()
    )
    rejected_edits = (
        PostEditRequest.query.filter_by(post_id=post.id, status="rejected")
        .order_by(PostEditRequest.created_at.desc())
        .all()
    )
    latest_reason = None
    if revisions:
        latest_reason = revisions[0].reason
    links = []
    if post.links_json:
        try:
            links = json.loads(post.links_json)
        except Exception:
            links = []
    rev_links = {}
    rev_media = {}
    for rev in revisions:
        if rev.links_json:
            try:
                rev_links[rev.id] = json.loads(rev.links_json)
            except Exception:
                rev_links[rev.id] = []
        else:
            rev_links[rev.id] = []
        if rev.media_json:
            rev_media[rev.id] = parse_media_json(rev.media_json)
        else:
            rev_media[rev.id] = []

    rejected_links = {}
    rejected_media = {}
    for edit in rejected_edits:
        if edit.links_json:
            try:
                rejected_links[edit.id] = json.loads(edit.links_json)
            except Exception:
                rejected_links[edit.id] = []
        else:
            rejected_links[edit.id] = []
        if edit.media_json:
            rejected_media[edit.id] = parse_media_json(edit.media_json)
        else:
            rejected_media[edit.id] = []

    return render_template(
        "map/post_history.html",
        post=post,
        revisions=revisions,
        links=links,
        rev_links=rev_links,
        latest_reason=latest_reason,
        media_items=get_media_payload(post),
        rev_media=rev_media,
        rejected_edits=rejected_edits,
        rejected_links=rejected_links,
        rejected_media=rejected_media,
    )


@map_bp.route("/reportes")
def reports():
    selected_province = canonicalize_province_name(request.args.get("provincia", "").strip()) or ""
    selected_municipality = request.args.get("municipio", "").strip()
    province_filter_values = _matching_post_province_values(selected_province) if selected_province else []
    if selected_province and not province_filter_values:
        province_filter_values = [selected_province]

    query = Post.query.filter_by(status="approved")
    query = query.filter(
        func.coalesce(func.lower(Post.other_type), "") != _AUTO_CONNECTIVITY_REPORT_MARKER
    )
    if province_filter_values:
        query = query.filter(Post.province.in_(province_filter_values))
    if selected_municipality:
        query = query.filter_by(municipality=selected_municipality)

    posts = query.order_by(Post.created_at.desc()).all()
    verified_ids = _get_verified_post_ids([post.id for post in posts])

    provinces = list_provinces()
    if selected_province:
        municipalities = list_municipalities(selected_province)
    else:
        municipalities = list_municipalities()

    return render_template(
        "map/reports.html",
        posts=posts,
        verified_ids=verified_ids,
        provinces=provinces,
        municipalities=municipalities,
        selected_province=selected_province,
        selected_municipality=selected_municipality,
        municipalities_map=municipalities_map(),
    )


@map_bp.route("/represores")
def repressors():
    q = request.args.get("q", "").strip()
    selected_province = canonicalize_province_name(request.args.get("provincia", "").strip()) or ""
    selected_municipality = request.args.get("municipio", "").strip()
    per_page_options = [20, 50, 100, 500]
    try:
        page = max(int(request.args.get("page", "1")), 1)
    except Exception:
        page = 1
    try:
        requested_per_page = int(request.args.get("per_page", "20"))
    except Exception:
        requested_per_page = 20

    per_page = requested_per_page if requested_per_page in per_page_options else 20
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

    if selected_province:
        query = query.filter(Repressor.province_name == selected_province)
    if selected_municipality:
        query = query.filter(Repressor.municipality_name == selected_municipality)

    total = query.count()
    pages = max((total + per_page - 1) // per_page, 1)
    page = min(page, pages)
    rows = (
        query.order_by(Repressor.updated_at.desc(), Repressor.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    page_window = 2
    first_page_in_window = max(1, page - page_window)
    last_page_in_window = min(pages, page + page_window)
    page_numbers = list(range(first_page_in_window, last_page_in_window + 1))

    provinces = list_provinces()
    if selected_province:
        municipalities = list_municipalities(selected_province)
    else:
        municipalities = list_municipalities()

    return render_template(
        "map/repressors.html",
        repressors=rows,
        total=total,
        page=page,
        pages=pages,
        page_numbers=page_numbers,
        per_page=per_page,
        per_page_options=per_page_options,
        q=q,
        provinces=provinces,
        municipalities=municipalities,
        selected_province=selected_province,
        selected_municipality=selected_municipality,
        municipalities_map=municipalities_map(),
        canonicalize_location_names=canonicalize_location_names,
    )


@map_bp.route("/represores/agregar", methods=["GET", "POST"])
@limiter.limit("3/minute; 20/day", methods=["POST"])
def add_repressor():
    moderation_enabled = _is_moderation_enabled()
    type_options = get_repressor_type_options()
    allowed_type_names = get_repressor_type_names()
    existing_crime_names = list_existing_repressor_crime_names()
    existing_crime_name_set = set(existing_crime_names)
    cloudinary_enabled = bool(
        (current_app.config.get("CLOUDINARY_CLOUD_NAME") or "").strip()
        and (current_app.config.get("CLOUDINARY_API_KEY") or "").strip()
        and (current_app.config.get("CLOUDINARY_API_SECRET") or "").strip()
    )

    errors = {}
    form_data = {
        "name": "",
        "lastname": "",
        "nickname": "",
        "institution_name": "",
        "campus_name": "",
        "province_name": "",
        "municipality_name": "",
        "testimony": "",
        "note": "",
        "custom_crimes": "",
        "selected_crime_names": [],
        "selected_type_names": [],
    }

    if request.method == "POST":
        selected_crime_names = normalize_list_items(request.form.getlist("crime_names[]"))
        selected_type_names = normalize_list_items(request.form.getlist("type_names[]"))
        custom_crimes_text = request.form.get("custom_crimes", "").strip()
        form_data = {
            "name": request.form.get("name", "").strip(),
            "lastname": request.form.get("lastname", "").strip(),
            "nickname": request.form.get("nickname", "").strip(),
            "institution_name": request.form.get("institution_name", "").strip(),
            "campus_name": request.form.get("campus_name", "").strip(),
            "province_name": request.form.get("province_name", "").strip(),
            "municipality_name": request.form.get("municipality_name", "").strip(),
            "testimony": request.form.get("testimony", "").strip(),
            "note": request.form.get("note", "").strip(),
            "custom_crimes": custom_crimes_text,
            "selected_crime_names": selected_crime_names,
            "selected_type_names": selected_type_names,
        }
        photo_files = [
            file
            for file in request.files.getlist("photo")
            if file and (file.filename or "").strip()
        ]
        filtered_selected_crimes = [
            value for value in selected_crime_names if value in existing_crime_name_set
        ]
        filtered_selected_types = [
            value for value in selected_type_names if value in allowed_type_names
        ]
        all_crime_names = normalize_list_items(
            filtered_selected_crimes + parse_custom_crimes(custom_crimes_text)
        )

        province_name, municipality_name = canonicalize_location_names(
            form_data["province_name"],
            form_data["municipality_name"],
        )
        form_data["province_name"] = province_name or ""
        form_data["municipality_name"] = municipality_name or ""
        form_data["selected_crime_names"] = filtered_selected_crimes
        form_data["selected_type_names"] = filtered_selected_types

        if recaptcha_enabled():
            token = request.form.get("g-recaptcha-response", "")
            if not verify_recaptcha(token, request.remote_addr):
                errors["recaptcha"] = "Verificación reCAPTCHA falló."

        if not photo_files:
            errors["photo"] = "La foto es obligatoria."
        elif len(photo_files) > 1:
            errors["photo"] = "Solo puedes subir una foto por envío."
        elif not cloudinary_enabled:
            errors["photo"] = "Subida de imagen no disponible: falta configuración del servicio de imágenes."
        else:
            ok, error = validate_files(photo_files)
            if not ok:
                errors["photo"] = error

        if not form_data["name"]:
            errors["name"] = "El nombre es obligatorio."

        if not filtered_selected_types:
            errors["types"] = "Selecciona al menos un tipo de represor."

        if not all_crime_names:
            errors["crimes"] = "Selecciona al menos un delito o agrega uno nuevo."

        if len(all_crime_names) > 100:
            errors["crimes"] = "Máximo 100 delitos por envío."

        if len(form_data["note"]) > 4000:
            errors["note"] = "La nota no puede exceder 4000 caracteres."
        if len(form_data["testimony"]) > 12000:
            errors["testimony"] = "El testimonio no puede exceder 12000 caracteres."

        malicious_values = [
            form_data["name"],
            form_data["lastname"],
            form_data["nickname"],
            form_data["institution_name"],
            form_data["campus_name"],
            form_data["province_name"],
            form_data["municipality_name"],
            form_data["testimony"],
            form_data["note"],
            form_data["custom_crimes"],
        ] + filtered_selected_types + all_crime_names
        if has_malicious_input(malicious_values):
            errors["form"] = "Se detectó contenido sospechoso en el formulario."

        photo_url = None
        if not errors:
            try:
                uploaded_urls = upload_files(photo_files)
                photo_url = uploaded_urls[0] if uploaded_urls else None
            except Exception:
                current_app.logger.exception("Error al subir foto de represor")
                errors["photo"] = "No se pudo subir la foto."
            if not photo_url and "photo" not in errors:
                errors["photo"] = "No se pudo subir la foto."

        if not errors:
            try:
                submitter = _get_or_create_anon_editor()
                reviewer_id = current_user.id if current_user.is_authenticated else None
                status = "pending" if moderation_enabled else "approved"
                submission = RepressorSubmission(
                    status=status,
                    submitter_id=submitter.id if submitter else None,
                    reviewer_id=reviewer_id if not moderation_enabled else None,
                    photo_url=photo_url,
                    name=form_data["name"],
                    lastname=form_data["lastname"] or None,
                    nickname=form_data["nickname"] or None,
                    institution_name=form_data["institution_name"] or None,
                    campus_name=form_data["campus_name"] or None,
                    province_name=form_data["province_name"] or None,
                    municipality_name=form_data["municipality_name"] or None,
                    testimony=form_data["testimony"] or None,
                    crimes_json=json.dumps(all_crime_names, ensure_ascii=False),
                    types_json=json.dumps(filtered_selected_types, ensure_ascii=False),
                    note=form_data["note"] or None,
                    payload_json=json.dumps(
                        {
                            "custom_crimes_raw": custom_crimes_text,
                            "selected_crimes": filtered_selected_crimes,
                            "selected_types": filtered_selected_types,
                        },
                        ensure_ascii=False,
                    ),
                    reviewed_at=datetime.utcnow() if not moderation_enabled else None,
                )
                db.session.add(submission)
                db.session.flush()

                repressor = None
                if not moderation_enabled:
                    repressor = materialize_repressor_submission(
                        submission,
                        reviewer_id=reviewer_id,
                    )

                db.session.commit()

                if moderation_enabled:
                    flash("Propuesta enviada a moderación.", "success")
                    return redirect(url_for("map.add_repressor"))

                flash("Represor agregado al catálogo.", "success")
                return redirect(url_for("map.repressor_detail", repressor_id=repressor.id))
            except Exception:
                db.session.rollback()
                current_app.logger.exception("Error al guardar propuesta de represor")
                errors["form"] = "No se pudo guardar la propuesta. Inténtalo nuevamente."

    return render_template(
        "map/repressor_new.html",
        form_data=form_data,
        errors=errors,
        moderation_enabled=moderation_enabled,
        type_options=type_options,
        existing_crime_names=existing_crime_names,
        provinces=list_provinces(),
        municipalities_map=municipalities_map(),
        recaptcha_site_key=current_app.config.get("RECAPTCHA_V2_SITE_KEY"),
    )


@map_bp.route("/represores/<int:repressor_id>")
def repressor_detail(repressor_id):
    repressor = (
        Repressor.query.options(
            selectinload(Repressor.crimes),
            selectinload(Repressor.types),
        )
        .filter_by(id=repressor_id)
        .first_or_404()
    )
    repressor_verified_by_me = repressor.id in _get_verified_repressor_ids([repressor.id])
    repressor_edit_locked = _is_repressor_profile_locked(repressor)
    confirmed_residence_url = _repressor_confirmed_residence_url(repressor)

    return render_template(
        "map/repressor_detail.html",
        repressor=repressor,
        repressor_payload=serialize_repressor(repressor, include_relationships=True),
        type_badges=_build_repressor_type_badges(repressor),
        type_legend=_build_repressor_type_legend(),
        show_profile_actions=True,
        repressor_verified_by_me=repressor_verified_by_me,
        repressor_edit_locked=repressor_edit_locked,
        confirmed_residence_url=confirmed_residence_url,
    )


@map_bp.route("/represores/<int:repressor_id>/eliminar", methods=["POST"])
def delete_repressor(repressor_id):
    if not _is_admin_user():
        abort(403)

    repressor = Repressor.query.get_or_404(repressor_id)
    if _is_repressor_profile_locked(repressor):
        flash(
            "Esta ficha alcanzó 10 verificaciones y no puede eliminarse.",
            "error",
        )
        return redirect(url_for("map.repressor_detail", repressor_id=repressor.id))
    full_name = repressor.full_name
    try:
        Post.query.filter_by(repressor_id=repressor.id).update(
            {Post.repressor_id: None},
            synchronize_session=False,
        )
        RepressorSubmission.query.filter_by(repressor_id=repressor.id).update(
            {RepressorSubmission.repressor_id: None},
            synchronize_session=False,
        )
        db.session.delete(repressor)
        db.session.commit()
        flash(f"Ficha eliminada: {full_name}.", "success")
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Error eliminando represor id=%s", repressor_id)
        flash("No se pudo eliminar la ficha del represor.", "error")

    return redirect(url_for("map.repressors"))


def _repressor_form_defaults(repressor: Repressor) -> dict[str, Any]:
    return {
        "name": repressor.name or "",
        "lastname": repressor.lastname or "",
        "nickname": repressor.nickname or "",
        "institution_name": repressor.institution_name or "",
        "campus_name": repressor.campus_name or "",
        "province_name": repressor.province_name or "",
        "municipality_name": repressor.municipality_name or "",
        "testimony": repressor.testimony or "",
        "note": "",
        "reason": "",
        "custom_crimes": "",
        "selected_crime_names": [item.name for item in repressor.crimes if item.name],
        "selected_type_names": [item.name for item in repressor.types if item.name],
    }


def _has_repressor_changes(
    repressor: Repressor,
    form_data: dict[str, Any],
    crimes: list[str],
    types: list[str],
    *,
    new_photo_selected: bool = False,
) -> bool:
    current_province, current_municipality = canonicalize_location_names(
        repressor.province_name,
        repressor.municipality_name,
    )
    candidate_province, candidate_municipality = canonicalize_location_names(
        form_data.get("province_name"),
        form_data.get("municipality_name"),
    )

    if (repressor.name or "") != (form_data.get("name") or ""):
        return True
    if (repressor.lastname or "") != (form_data.get("lastname") or ""):
        return True
    if (repressor.nickname or "") != (form_data.get("nickname") or ""):
        return True
    if (repressor.institution_name or "") != (form_data.get("institution_name") or ""):
        return True
    if (repressor.campus_name or "") != (form_data.get("campus_name") or ""):
        return True
    if (current_province or "") != (candidate_province or ""):
        return True
    if (current_municipality or "") != (candidate_municipality or ""):
        return True
    if (repressor.testimony or "") != (form_data.get("testimony") or ""):
        return True
    if new_photo_selected:
        return True

    current_crimes = sorted([item.name for item in repressor.crimes if item.name])
    current_types = sorted([item.name for item in repressor.types if item.name])
    if current_crimes != sorted(crimes):
        return True
    if current_types != sorted(types):
        return True
    return False


def _handle_repressor_edit_form(repressor_id: int, edit_kind: str):
    repressor = (
        Repressor.query.options(
            selectinload(Repressor.crimes),
            selectinload(Repressor.types),
        )
        .filter_by(id=repressor_id)
        .first_or_404()
    )
    if _is_repressor_profile_locked(repressor):
        flash(
            "Esta ficha alcanzó 10 verificaciones y ya no puede editarse ni reportarse.",
            "error",
        )
        return redirect(url_for("map.repressor_detail", repressor_id=repressor.id))
    moderation_enabled = _is_moderation_enabled()
    type_options = get_repressor_type_options()
    allowed_type_names = get_repressor_type_names()
    existing_crime_names = list_existing_repressor_crime_names()
    existing_crime_name_set = set(existing_crime_names)
    cloudinary_enabled = bool(
        (current_app.config.get("CLOUDINARY_CLOUD_NAME") or "").strip()
        and (current_app.config.get("CLOUDINARY_API_KEY") or "").strip()
        and (current_app.config.get("CLOUDINARY_API_SECRET") or "").strip()
    )
    errors = {}
    form_data = _repressor_form_defaults(repressor)
    is_report_mode = edit_kind == "report"

    if request.method == "POST":
        selected_crime_names = normalize_list_items(request.form.getlist("crime_names[]"))
        selected_type_names = normalize_list_items(request.form.getlist("type_names[]"))
        photo_files = [
            file
            for file in request.files.getlist("photo")
            if file and (file.filename or "").strip()
        ]
        custom_crimes_text = request.form.get("custom_crimes", "").strip()
        form_data = {
            "name": request.form.get("name", "").strip(),
            "lastname": request.form.get("lastname", "").strip(),
            "nickname": request.form.get("nickname", "").strip(),
            "institution_name": request.form.get("institution_name", "").strip(),
            "campus_name": request.form.get("campus_name", "").strip(),
            "province_name": request.form.get("province_name", "").strip(),
            "municipality_name": request.form.get("municipality_name", "").strip(),
            "testimony": request.form.get("testimony", "").strip(),
            "note": request.form.get("note", "").strip(),
            "reason": request.form.get("reason", "").strip(),
            "custom_crimes": custom_crimes_text,
            "selected_crime_names": selected_crime_names,
            "selected_type_names": selected_type_names,
        }

        filtered_selected_crimes = [
            value for value in selected_crime_names if value in existing_crime_name_set
        ]
        filtered_selected_types = [
            value for value in selected_type_names if value in allowed_type_names
        ]
        all_crime_names = normalize_list_items(
            filtered_selected_crimes + parse_custom_crimes(custom_crimes_text)
        )

        province_name, municipality_name = canonicalize_location_names(
            form_data["province_name"],
            form_data["municipality_name"],
        )
        form_data["province_name"] = province_name or ""
        form_data["municipality_name"] = municipality_name or ""
        form_data["selected_crime_names"] = filtered_selected_crimes
        form_data["selected_type_names"] = filtered_selected_types

        if recaptcha_enabled():
            token = request.form.get("g-recaptcha-response", "")
            if not verify_recaptcha(token, request.remote_addr):
                errors["recaptcha"] = "Verificación reCAPTCHA falló."

        if not form_data["reason"]:
            errors["reason"] = "Debes explicar el motivo de la edición/reporte."
        if len(form_data["reason"]) > 2000:
            errors["reason"] = "El motivo no puede exceder 2000 caracteres."
        if len(form_data["note"]) > 4000:
            errors["note"] = "La nota no puede exceder 4000 caracteres."
        if len(form_data["testimony"]) > 12000:
            errors["testimony"] = "El testimonio no puede exceder 12000 caracteres."
        if len(photo_files) > 1:
            errors["photo"] = "Solo puedes subir una foto por envío."
        elif photo_files and not cloudinary_enabled:
            errors["photo"] = "Subida de imagen no disponible: falta configuración del servicio de imágenes."
        elif photo_files:
            ok, error = validate_files(photo_files)
            if not ok:
                errors["photo"] = error

        if not form_data["name"]:
            errors["name"] = "El nombre es obligatorio."
        if not filtered_selected_types:
            errors["types"] = "Selecciona al menos un tipo de represor."
        if not all_crime_names:
            errors["crimes"] = "Selecciona al menos un delito o agrega uno nuevo."
        if len(all_crime_names) > 100:
            errors["crimes"] = "Máximo 100 delitos por edición."

        malicious_values = [
            form_data["name"],
            form_data["lastname"],
            form_data["nickname"],
            form_data["institution_name"],
            form_data["campus_name"],
            form_data["province_name"],
            form_data["municipality_name"],
            form_data["testimony"],
            form_data["note"],
            form_data["reason"],
            form_data["custom_crimes"],
        ] + filtered_selected_types + all_crime_names
        if has_malicious_input(malicious_values):
            errors["form"] = "Se detectó contenido sospechoso en el formulario."

        has_changes = _has_repressor_changes(
            repressor,
            form_data=form_data,
            crimes=all_crime_names,
            types=filtered_selected_types,
            new_photo_selected=bool(photo_files),
        )
        if not has_changes and not is_report_mode:
            errors["form"] = "No se detectaron cambios en la ficha."

        uploaded_photo_url = None
        if not errors and photo_files:
            try:
                uploaded_urls = upload_files(photo_files)
                uploaded_photo_url = uploaded_urls[0] if uploaded_urls else None
            except Exception:
                current_app.logger.exception("Error al subir foto de edición de represor")
                errors["photo"] = "No se pudo subir la foto."
            if not uploaded_photo_url and "photo" not in errors:
                errors["photo"] = "No se pudo subir la foto."

        if not errors:
            try:
                editor, editor_label = _get_editor_identity()
                reviewer_id = current_user.id if current_user.is_authenticated else None
                status = "pending" if moderation_enabled else "approved"

                edit_request = RepressorEditRequest(
                    repressor_id=repressor.id,
                    status=status,
                    edit_kind="report" if is_report_mode else "edit",
                    editor_id=editor.id if editor else None,
                    reviewer_id=reviewer_id if not moderation_enabled else None,
                    editor_label=editor_label,
                    reason=form_data["reason"],
                    note=form_data["note"] or None,
                    name=form_data["name"],
                    lastname=form_data["lastname"] or None,
                    nickname=form_data["nickname"] or None,
                    institution_name=form_data["institution_name"] or None,
                    campus_name=form_data["campus_name"] or None,
                    province_name=form_data["province_name"] or None,
                    municipality_name=form_data["municipality_name"] or None,
                    testimony=form_data["testimony"] or None,
                    image_url=uploaded_photo_url or repressor.image_url,
                    crimes_json=json.dumps(all_crime_names, ensure_ascii=False),
                    types_json=json.dumps(filtered_selected_types, ensure_ascii=False),
                    payload_json=json.dumps(
                        {
                            "custom_crimes_raw": custom_crimes_text,
                            "selected_crimes": filtered_selected_crimes,
                            "selected_types": filtered_selected_types,
                            "source": "community_repressor_edit",
                            "photo_replaced": bool(uploaded_photo_url),
                        },
                        ensure_ascii=False,
                    ),
                    reviewed_at=datetime.utcnow() if not moderation_enabled else None,
                )
                db.session.add(edit_request)
                db.session.flush()

                if not moderation_enabled and has_changes:
                    snapshot_repressor(
                        repressor,
                        reason=form_data["reason"],
                        editor_id=editor.id if editor else None,
                        editor_label=editor_label,
                        payload={
                            "edit_request_id": edit_request.id,
                            "edit_kind": edit_request.edit_kind,
                            "mode": "direct_apply_without_moderation",
                        },
                    )
                    apply_repressor_edit_request(repressor, edit_request)

                db.session.commit()
                if moderation_enabled:
                    flash("Propuesta de ficha enviada a moderación.", "success")
                elif has_changes:
                    flash("Ficha de represor actualizada.", "success")
                else:
                    flash("Reporte de ficha registrado.", "success")
                return redirect(url_for("map.repressor_detail", repressor_id=repressor.id))
            except Exception:
                db.session.rollback()
                current_app.logger.exception("Error al guardar edición de represor")
                errors["form"] = "No se pudo guardar la edición/reporte. Inténtalo nuevamente."

    return render_template(
        "map/edit_repressor.html",
        repressor=repressor,
        form_data=form_data,
        errors=errors,
        moderation_enabled=moderation_enabled,
        type_options=type_options,
        existing_crime_names=existing_crime_names,
        provinces=list_provinces(),
        municipalities_map=municipalities_map(),
        recaptcha_site_key=current_app.config.get("RECAPTCHA_V2_SITE_KEY"),
        is_report_mode=is_report_mode,
    )


@map_bp.route("/represores/<int:repressor_id>/editar", methods=["GET", "POST"])
@limiter.limit("3/minute; 20/day", methods=["POST"])
def edit_repressor_public(repressor_id):
    return _handle_repressor_edit_form(repressor_id, edit_kind="edit")


@map_bp.route("/represores/<int:repressor_id>/reportar", methods=["GET", "POST"])
@limiter.limit("3/minute; 20/day", methods=["POST"])
def report_repressor_profile(repressor_id):
    return _handle_repressor_edit_form(repressor_id, edit_kind="report")


@map_bp.route("/represores/<int:repressor_id>/historial")
def repressor_history(repressor_id):
    repressor = (
        Repressor.query.options(
            selectinload(Repressor.crimes),
            selectinload(Repressor.types),
        )
        .filter_by(id=repressor_id)
        .first_or_404()
    )

    revisions = (
        RepressorRevision.query.filter_by(repressor_id=repressor.id)
        .order_by(RepressorRevision.created_at.desc())
        .all()
    )
    rejected_edits = (
        RepressorEditRequest.query.filter_by(repressor_id=repressor.id, status="rejected")
        .order_by(RepressorEditRequest.created_at.desc())
        .all()
    )
    latest_reason = revisions[0].reason if revisions else None

    return render_template(
        "map/repressor_history.html",
        repressor=repressor,
        repressor_payload=serialize_repressor(repressor, include_relationships=True),
        type_badges=_build_repressor_type_badges(repressor),
        revisions=revisions,
        rejected_edits=rejected_edits,
        latest_reason=latest_reason,
    )


@map_bp.route("/represores/visor")
def repressors_viewer():
    total_repressors = int(db.session.query(func.count(Repressor.id)).scalar() or 0)
    nav_action = (request.args.get("nav") or "").strip().lower()
    stack, index = _load_viewer_history_state()
    had_existing_stack = bool(stack)

    if total_repressors <= 0:
        stack = []
        index = -1
        _save_viewer_history_state(stack, index)
        return render_template(
            "map/repressor_random_viewer.html",
            repressor=None,
            repressor_payload=None,
            type_badges=[],
            type_legend=_build_repressor_type_legend(),
            has_prev=False,
            has_next=False,
            viewer_total_seen=0,
            viewer_position=0,
            total_repressors=0,
            repressor_verified_by_me=False,
            repressor_edit_locked=False,
        )

    if not stack:
        random_id = _pick_random_repressor_id()
        if random_id is not None:
            stack = [random_id]
            index = 0

    if nav_action == "prev" and stack:
        index = max(0, index - 1)
    elif nav_action == "next" and stack:
        current_id = stack[index]
        next_id = _pick_random_repressor_id(
            exclude_id=current_id if total_repressors > 1 else None
        )
        if next_id is not None:
            stack = stack[: index + 1]
            stack.append(next_id)
            index += 1
    elif not nav_action and had_existing_stack and stack:
        current_id = stack[index]
        next_id = _pick_random_repressor_id(
            exclude_id=current_id if total_repressors > 1 else None
        )
        if next_id is not None:
            stack = stack[: index + 1]
            stack.append(next_id)
            index += 1

    selected_id = stack[index] if stack else None
    repressor = None
    if selected_id is not None:
        repressor = (
            Repressor.query.options(
                selectinload(Repressor.crimes),
                selectinload(Repressor.types),
            )
            .filter_by(id=selected_id)
            .first()
        )

    if repressor is None:
        random_id = _pick_random_repressor_id()
        if random_id is not None:
            stack = [random_id]
            index = 0
            repressor = (
                Repressor.query.options(
                    selectinload(Repressor.crimes),
                    selectinload(Repressor.types),
                )
                .filter_by(id=random_id)
                .first()
            )

    _save_viewer_history_state(stack, index)
    repressor_verified_by_me = (
        repressor.id in _get_verified_repressor_ids([repressor.id]) if repressor else False
    )
    repressor_edit_locked = _is_repressor_profile_locked(repressor) if repressor else False
    confirmed_residence_url = (
        _repressor_confirmed_residence_url(repressor) if repressor else None
    )

    return render_template(
        "map/repressor_random_viewer.html",
        repressor=repressor,
        repressor_payload=serialize_repressor(repressor, include_relationships=True)
        if repressor
        else None,
        type_badges=_build_repressor_type_badges(repressor) if repressor else [],
        type_legend=_build_repressor_type_legend(),
        show_profile_actions=False,
        has_prev=index > 0,
        has_next=total_repressors > 1,
        viewer_total_seen=len(stack),
        viewer_position=(index + 1) if index >= 0 else 0,
        total_repressors=total_repressors,
        repressor_verified_by_me=repressor_verified_by_me,
        repressor_edit_locked=repressor_edit_locked,
        confirmed_residence_url=confirmed_residence_url,
    )


@map_bp.route("/represores/<int:repressor_id>/reportar-residencia", methods=["GET", "POST"])
@limiter.limit("3/minute; 30/day", methods=["POST"])
def report_repressor_residence(repressor_id):
    repressor = Repressor.query.filter_by(id=repressor_id).first_or_404()
    category = _residence_category()
    if not category:
        abort(500, "No existe la categoría residencia-represor")

    errors = {}
    submitted = False
    default_lat, default_lng = _initial_repressor_residence_coords(repressor)
    form_data = {
        "message": "",
        "address": "",
        "province": repressor.province_name or "",
        "municipality": repressor.municipality_name or "",
        "latitude": f"{default_lat:.6f}",
        "longitude": f"{default_lng:.6f}",
        "links": [""],
    }

    if request.method == "POST":
        links = request.form.getlist("links[]")
        links = [item.strip() for item in links if item.strip()]
        form_data = {
            "message": request.form.get("message", "").strip(),
            "address": request.form.get("address", "").strip(),
            "province": request.form.get("province", "").strip(),
            "municipality": request.form.get("municipality", "").strip(),
            "latitude": request.form.get("latitude", "").strip(),
            "longitude": request.form.get("longitude", "").strip(),
            "links": links if links else [""],
        }

        if recaptcha_enabled():
            token = request.form.get("g-recaptcha-response", "")
            if not verify_recaptcha(token, request.remote_addr):
                errors["recaptcha"] = "Verificación reCAPTCHA falló."

        if not form_data["message"]:
            errors["message"] = "El mensaje es obligatorio."
        elif len(form_data["message"]) < 30:
            errors["message"] = "El mensaje debe tener al menos 30 caracteres."

        if has_malicious_input(
            [
                form_data["message"],
                form_data["address"],
                form_data["province"],
                form_data["municipality"],
            ]
            + links
        ):
            errors["form"] = "Se detectó contenido sospechoso."

        lat = None
        lng = None
        if not form_data["latitude"]:
            errors["latitude"] = "La latitud es obligatoria."
        if not form_data["longitude"]:
            errors["longitude"] = "La longitud es obligatoria."

        if "latitude" not in errors and "longitude" not in errors:
            try:
                lat = Decimal(form_data["latitude"])
                lng = Decimal(form_data["longitude"])
            except Exception:
                errors["latitude"] = "Latitud inválida."
                errors["longitude"] = "Longitud inválida."

        if lat is not None and lng is not None:
            if not is_within_cuba_bounds(lat, lng):
                errors["latitude"] = "La ubicación debe estar dentro de Cuba."
                errors["longitude"] = "La ubicación debe estar dentro de Cuba."
            else:
                auto_prov, auto_mun = _resolve_geo_location(
                    lat,
                    lng,
                    form_data["province"],
                    form_data["municipality"],
                )
                form_data["province"] = auto_prov or ""
                form_data["municipality"] = auto_mun or ""

        if not form_data["province"]:
            errors["province"] = "Provincia obligatoria."
        if not form_data["municipality"]:
            errors["municipality"] = "Municipio obligatorio."

        if not errors:
            reporter = _get_or_create_anon_editor()
            auto_approve = bool(current_app.config.get("REPRESSOR_RESIDENCE_AUTO_APPROVE", False))
            post_status = "approved" if auto_approve else "pending"
            report_status = "approved" if auto_approve else "pending"

            post = Post(
                title=build_residence_post_title(repressor),
                description=build_residence_post_description(repressor, form_data["message"]),
                category_id=category.id,
                latitude=lat,
                longitude=lng,
                address=form_data["address"] or None,
                province=form_data["province"] or None,
                municipality=form_data["municipality"] or None,
                repressor_name=repressor.full_name,
                repressor_id=repressor.id,
                links_json=json.dumps(links, ensure_ascii=False) if links else None,
                status=post_status,
                author_id=reporter.id,
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
                address=form_data["address"] or None,
                province=form_data["province"] or None,
                municipality=form_data["municipality"] or None,
                message=form_data["message"],
                evidence_links_json=json.dumps(links, ensure_ascii=False) if links else None,
                source_image_url=repressor.image_url,
                created_post_id=post.id,
                reviewed_at=datetime.utcnow() if auto_approve else None,
            )
            db.session.add(residence_report)
            db.session.commit()
            submitted = True

            if request.args.get("modal") != "1":
                if post.status == "approved":
                    flash("Reporte de residencia publicado.", "success")
                else:
                    flash("Reporte de residencia enviado a moderación.", "success")

            if request.args.get("modal") == "1":
                return render_template(
                    "map/report_success.html",
                    payload={
                        "id": post.id,
                        "status": post.status,
                        "title": post.title,
                        "description": post.description,
                        "latitude": float(post.latitude),
                        "longitude": float(post.longitude),
                        "address": post.address,
                        "category": {"name": category.name, "slug": category.slug},
                        "verify_count": post.verify_count or 0,
                        "created_at": post.created_at.isoformat() if post.created_at else None,
                        "movement_at": None,
                    },
                )

    return render_template(
        "map/repressor_report_residence.html",
        repressor=repressor,
        repressor_payload=serialize_repressor(repressor, include_relationships=True),
        form_data=form_data,
        errors=errors,
        submitted=submitted,
        provinces=list_provinces(),
        municipalities_map=municipalities_map(),
        map_provider_forms=get_map_provider_forms(),
        google_maps_api_key=_google_maps_api_key(),
        recaptcha_site_key=current_app.config.get("RECAPTCHA_V2_SITE_KEY"),
    )


def _next_local_prisoner_external_id() -> int:
    current_min = (
        db.session.query(func.min(Prisoner.external_id))
        .filter(Prisoner.external_id < 0)
        .scalar()
    )
    if current_min is None:
        return -1
    try:
        return int(current_min) - 1
    except Exception:
        return -1


def _available_prison_names(
    selected_province: str = "",
    selected_municipality: str = "",
) -> list[str]:
    query = db.session.query(Prisoner.prison_name).filter(
        Prisoner.prison_name.isnot(None),
        Prisoner.prison_name != "",
    )
    if selected_province:
        query = query.filter(Prisoner.province_name == selected_province)
    if selected_municipality:
        query = query.filter(Prisoner.municipality_name == selected_municipality)
    rows = query.distinct().order_by(Prisoner.prison_name.asc()).all()
    return [str(row[0]).strip() for row in rows if str(row[0] or "").strip()]


def _prisoner_form_defaults(prisoner: Prisoner | None = None) -> dict[str, Any]:
    if prisoner is None:
        return {
            "name": "",
            "lastname": "",
            "gender_label": "",
            "detention_typology": "",
            "age_detention_label": "",
            "age_current_label": "",
            "province_name": "",
            "municipality_name": "",
            "prison_name": "",
            "prison_latitude": "",
            "prison_longitude": "",
            "prison_address": "",
            "detention_date": "",
            "offense_types": "",
            "sentence_text": "",
            "medical_status": "",
            "penal_status": "",
            "observations": "",
            "image_url": "",
            "source_detail_url": "",
            "reason": "",
        }

    return {
        "name": prisoner.name or "",
        "lastname": prisoner.lastname or "",
        "gender_label": prisoner.gender_label or "",
        "detention_typology": prisoner.detention_typology or "",
        "age_detention_label": prisoner.age_detention_label or "",
        "age_current_label": prisoner.age_current_label or "",
        "province_name": prisoner.province_name or "",
        "municipality_name": prisoner.municipality_name or "",
        "prison_name": prisoner.prison_name or "",
        "prison_latitude": str(prisoner.prison_latitude) if prisoner.prison_latitude is not None else "",
        "prison_longitude": str(prisoner.prison_longitude) if prisoner.prison_longitude is not None else "",
        "prison_address": prisoner.prison_address or "",
        "detention_date": prisoner.detention_date or "",
        "offense_types": prisoner.offense_types or "",
        "sentence_text": prisoner.sentence_text or "",
        "medical_status": prisoner.medical_status or "",
        "penal_status": prisoner.penal_status or "",
        "observations": prisoner.observations or "",
        "image_url": prisoner.image_url or "",
        "source_detail_url": prisoner.source_detail_url or "",
        "reason": "",
    }


def _normalize_prisoner_form_data() -> dict[str, Any]:
    return {
        "name": request.form.get("name", "").strip(),
        "lastname": request.form.get("lastname", "").strip(),
        "gender_label": request.form.get("gender_label", "").strip(),
        "detention_typology": request.form.get("detention_typology", "").strip(),
        "age_detention_label": request.form.get("age_detention_label", "").strip(),
        "age_current_label": request.form.get("age_current_label", "").strip(),
        "province_name": request.form.get("province_name", "").strip(),
        "municipality_name": request.form.get("municipality_name", "").strip(),
        "prison_name": request.form.get("prison_name", "").strip(),
        "prison_latitude": request.form.get("prison_latitude", "").strip(),
        "prison_longitude": request.form.get("prison_longitude", "").strip(),
        "prison_address": request.form.get("prison_address", "").strip(),
        "detention_date": request.form.get("detention_date", "").strip(),
        "offense_types": request.form.get("offense_types", "").strip(),
        "sentence_text": request.form.get("sentence_text", "").strip(),
        "medical_status": request.form.get("medical_status", "").strip(),
        "penal_status": request.form.get("penal_status", "").strip(),
        "observations": request.form.get("observations", "").strip(),
        "image_url": request.form.get("image_url", "").strip(),
        "source_detail_url": request.form.get("source_detail_url", "").strip(),
        "reason": request.form.get("reason", "").strip(),
    }


def _validate_prisoner_form_data(
    form_data: dict[str, Any],
    *,
    require_reason: bool = False,
) -> dict[str, str]:
    errors: dict[str, str] = {}

    province_name, municipality_name = canonicalize_location_names(
        form_data.get("province_name"),
        form_data.get("municipality_name"),
    )
    form_data["province_name"] = province_name or ""
    form_data["municipality_name"] = municipality_name or ""

    if not form_data.get("name"):
        errors["name"] = "El nombre es obligatorio."

    if require_reason and not form_data.get("reason"):
        errors["reason"] = "Debes explicar el motivo de la edición."
    if len(form_data.get("reason") or "") > 2000:
        errors["reason"] = "El motivo no puede exceder 2000 caracteres."

    for field_key, max_len in (
        ("lastname", 200),
        ("gender_label", 120),
        ("detention_typology", 200),
        ("age_detention_label", 120),
        ("age_current_label", 120),
        ("province_name", 120),
        ("municipality_name", 120),
        ("prison_name", 200),
        ("prison_address", 255),
        ("detention_date", 50),
        ("sentence_text", 300),
        ("medical_status", 300),
        ("penal_status", 300),
        ("image_url", 1000),
        ("source_detail_url", 500),
    ):
        value = str(form_data.get(field_key) or "")
        if len(value) > max_len:
            errors[field_key] = f"El campo excede {max_len} caracteres."

    if len(str(form_data.get("offense_types") or "")) > 6000:
        errors["offense_types"] = "Los delitos no pueden exceder 6000 caracteres."
    if len(str(form_data.get("observations") or "")) > 24000:
        errors["observations"] = "Las observaciones no pueden exceder 24000 caracteres."

    lat_raw = form_data.get("prison_latitude")
    lng_raw = form_data.get("prison_longitude")
    has_lat = bool(str(lat_raw or "").strip())
    has_lng = bool(str(lng_raw or "").strip())
    if has_lat != has_lng:
        errors["prison_latitude"] = "Debes indicar latitud y longitud juntas."
        errors["prison_longitude"] = "Debes indicar latitud y longitud juntas."
    elif has_lat and has_lng:
        try:
            lat = Decimal(str(lat_raw))
            lng = Decimal(str(lng_raw))
        except Exception:
            errors["prison_latitude"] = "Latitud inválida."
            errors["prison_longitude"] = "Longitud inválida."
        else:
            if not is_within_cuba_bounds(lat, lng):
                errors["prison_latitude"] = "La prisión debe ubicarse dentro de Cuba."
                errors["prison_longitude"] = "La prisión debe ubicarse dentro de Cuba."

    malicious_values = [
        form_data.get("name"),
        form_data.get("lastname"),
        form_data.get("gender_label"),
        form_data.get("detention_typology"),
        form_data.get("age_detention_label"),
        form_data.get("age_current_label"),
        form_data.get("province_name"),
        form_data.get("municipality_name"),
        form_data.get("prison_name"),
        form_data.get("prison_address"),
        form_data.get("detention_date"),
        form_data.get("offense_types"),
        form_data.get("sentence_text"),
        form_data.get("medical_status"),
        form_data.get("penal_status"),
        form_data.get("observations"),
        form_data.get("image_url"),
        form_data.get("source_detail_url"),
        form_data.get("reason"),
    ]
    if has_malicious_input(malicious_values):
        errors["form"] = "Se detectó contenido sospechoso en el formulario."

    return errors


def _has_prisoner_changes(
    prisoner: Prisoner,
    form_data: dict[str, Any],
    *,
    image_url: str | None,
) -> bool:
    current_province, current_municipality = canonicalize_location_names(
        prisoner.province_name,
        prisoner.municipality_name,
    )
    candidate_province, candidate_municipality = canonicalize_location_names(
        form_data.get("province_name"),
        form_data.get("municipality_name"),
    )

    comparisons = (
        ((prisoner.name or ""), (form_data.get("name") or "")),
        ((prisoner.lastname or ""), (form_data.get("lastname") or "")),
        ((prisoner.gender_label or ""), (form_data.get("gender_label") or "")),
        ((prisoner.detention_typology or ""), (form_data.get("detention_typology") or "")),
        ((prisoner.age_detention_label or ""), (form_data.get("age_detention_label") or "")),
        ((prisoner.age_current_label or ""), (form_data.get("age_current_label") or "")),
        ((current_province or ""), (candidate_province or "")),
        ((current_municipality or ""), (candidate_municipality or "")),
        ((prisoner.prison_name or ""), (form_data.get("prison_name") or "")),
        ((str(prisoner.prison_latitude or "")), (form_data.get("prison_latitude") or "")),
        ((str(prisoner.prison_longitude or "")), (form_data.get("prison_longitude") or "")),
        ((prisoner.prison_address or ""), (form_data.get("prison_address") or "")),
        ((prisoner.detention_date or ""), (form_data.get("detention_date") or "")),
        ((prisoner.offense_types or ""), (form_data.get("offense_types") or "")),
        ((prisoner.sentence_text or ""), (form_data.get("sentence_text") or "")),
        ((prisoner.medical_status or ""), (form_data.get("medical_status") or "")),
        ((prisoner.penal_status or ""), (form_data.get("penal_status") or "")),
        ((prisoner.observations or ""), (form_data.get("observations") or "")),
        ((prisoner.source_detail_url or ""), (form_data.get("source_detail_url") or "")),
    )
    for current_value, incoming_value in comparisons:
        if str(current_value or "") != str(incoming_value or ""):
            return True

    if (prisoner.image_url or "") != (image_url or ""):
        return True
    return False


@map_bp.route("/prisioneros")
def prisoners():
    q = request.args.get("q", "").strip()
    selected_province = canonicalize_province_name(request.args.get("provincia", "").strip()) or ""
    selected_municipality = request.args.get("municipio", "").strip()
    selected_prison = request.args.get("prision", "").strip()

    per_page_options = [20, 50, 100, 500]
    try:
        page = max(int(request.args.get("page", "1")), 1)
    except Exception:
        page = 1
    try:
        requested_per_page = int(request.args.get("per_page", "20"))
    except Exception:
        requested_per_page = 20
    per_page = requested_per_page if requested_per_page in per_page_options else 20

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

    if selected_province:
        query = query.filter(Prisoner.province_name == selected_province)
    if selected_municipality:
        query = query.filter(Prisoner.municipality_name == selected_municipality)
    if selected_prison:
        query = query.filter(Prisoner.prison_name == selected_prison)

    total = query.count()
    pages = max((total + per_page - 1) // per_page, 1)
    page = min(page, pages)
    rows = (
        query.order_by(Prisoner.updated_at.desc(), Prisoner.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    page_window = 2
    first_page_in_window = max(1, page - page_window)
    last_page_in_window = min(pages, page + page_window)
    page_numbers = list(range(first_page_in_window, last_page_in_window + 1))

    provinces = list_provinces()
    municipalities = (
        list_municipalities(selected_province) if selected_province else list_municipalities()
    )
    prisons = _available_prison_names(selected_province, selected_municipality)

    return render_template(
        "map/prisoners.html",
        prisoners=rows,
        total=total,
        page=page,
        pages=pages,
        page_numbers=page_numbers,
        per_page=per_page,
        per_page_options=per_page_options,
        q=q,
        provinces=provinces,
        municipalities=municipalities,
        prisons=prisons,
        selected_province=selected_province,
        selected_municipality=selected_municipality,
        selected_prison=selected_prison,
        municipalities_map=municipalities_map(),
    )


@map_bp.route("/prisioneros/agregar", methods=["GET", "POST"])
@limiter.limit("3/minute; 20/day", methods=["POST"])
def add_prisoner():
    cloudinary_enabled = bool(
        (current_app.config.get("CLOUDINARY_CLOUD_NAME") or "").strip()
        and (current_app.config.get("CLOUDINARY_API_KEY") or "").strip()
        and (current_app.config.get("CLOUDINARY_API_SECRET") or "").strip()
    )
    errors: dict[str, str] = {}
    form_data = _prisoner_form_defaults()

    if request.method == "POST":
        form_data = _normalize_prisoner_form_data()
        photo_files = [
            file
            for file in request.files.getlist("photo")
            if file and (file.filename or "").strip()
        ]

        if recaptcha_enabled():
            token = request.form.get("g-recaptcha-response", "")
            if not verify_recaptcha(token, request.remote_addr):
                errors["recaptcha"] = "Verificación reCAPTCHA falló."

        errors.update(_validate_prisoner_form_data(form_data, require_reason=False))

        if len(photo_files) > 1:
            errors["photo"] = "Solo puedes subir una foto."
        elif photo_files and not cloudinary_enabled:
            errors["photo"] = "Subida no disponible: falta configuración del servicio de imágenes."
        elif photo_files:
            ok, error = validate_files(photo_files)
            if not ok:
                errors["photo"] = error

        uploaded_photo_url = None
        if not errors and photo_files:
            try:
                uploaded_urls = upload_files(photo_files)
                uploaded_photo_url = uploaded_urls[0] if uploaded_urls else None
            except Exception:
                current_app.logger.exception("Error al subir foto de prisionero")
                errors["photo"] = "No se pudo subir la foto."
            if not uploaded_photo_url and "photo" not in errors:
                errors["photo"] = "No se pudo subir la foto."

        if not errors:
            try:
                prisoner = Prisoner(
                    external_id=_next_local_prisoner_external_id(),
                    source_payload_json=json.dumps(
                        {
                            "source": "community_manual",
                            "created_via": "prisoner_add_form",
                        },
                        ensure_ascii=False,
                    ),
                    source_created_at=datetime.utcnow(),
                    source_updated_at=datetime.utcnow(),
                    first_seen_at=datetime.utcnow(),
                    last_synced_at=datetime.utcnow(),
                )
                apply_prisoner_payload(
                    prisoner,
                    name=form_data.get("name") or "",
                    lastname=form_data.get("lastname"),
                    gender_label=form_data.get("gender_label"),
                    detention_typology=form_data.get("detention_typology"),
                    age_detention_label=form_data.get("age_detention_label"),
                    age_current_label=form_data.get("age_current_label"),
                    province_name=form_data.get("province_name"),
                    municipality_name=form_data.get("municipality_name"),
                    prison_name=form_data.get("prison_name"),
                    prison_latitude=form_data.get("prison_latitude"),
                    prison_longitude=form_data.get("prison_longitude"),
                    prison_address=form_data.get("prison_address"),
                    detention_date=form_data.get("detention_date"),
                    offense_types=form_data.get("offense_types"),
                    sentence_text=form_data.get("sentence_text"),
                    medical_status=form_data.get("medical_status"),
                    penal_status=form_data.get("penal_status"),
                    observations=form_data.get("observations"),
                    image_url=uploaded_photo_url or form_data.get("image_url"),
                    source_detail_url=form_data.get("source_detail_url"),
                )
                db.session.add(prisoner)
                db.session.commit()
                flash("Prisionero agregado al catálogo.", "success")
                return redirect(url_for("map.prisoner_detail", prisoner_id=prisoner.id))
            except Exception:
                db.session.rollback()
                current_app.logger.exception("Error guardando prisionero")
                errors["form"] = "No se pudo guardar la ficha. Inténtalo nuevamente."

    return render_template(
        "map/prisoner_new.html",
        form_data=form_data,
        errors=errors,
        provinces=list_provinces(),
        municipalities_map=municipalities_map(),
        recaptcha_site_key=current_app.config.get("RECAPTCHA_V2_SITE_KEY"),
    )


@map_bp.route("/prisioneros/<int:prisoner_id>")
def prisoner_detail(prisoner_id):
    prisoner = Prisoner.query.filter_by(id=prisoner_id).first_or_404()
    return render_template(
        "map/prisoner_detail.html",
        prisoner=prisoner,
        prisoner_payload=serialize_prisoner(prisoner, include_source=True),
        show_profile_actions=True,
    )


@map_bp.route("/prisioneros/<int:prisoner_id>/editar", methods=["GET", "POST"])
@limiter.limit("3/minute; 20/day", methods=["POST"])
def edit_prisoner_public(prisoner_id):
    prisoner = Prisoner.query.filter_by(id=prisoner_id).first_or_404()
    cloudinary_enabled = bool(
        (current_app.config.get("CLOUDINARY_CLOUD_NAME") or "").strip()
        and (current_app.config.get("CLOUDINARY_API_KEY") or "").strip()
        and (current_app.config.get("CLOUDINARY_API_SECRET") or "").strip()
    )
    errors: dict[str, str] = {}
    form_data = _prisoner_form_defaults(prisoner)

    if request.method == "POST":
        form_data = _normalize_prisoner_form_data()
        photo_files = [
            file
            for file in request.files.getlist("photo")
            if file and (file.filename or "").strip()
        ]

        if recaptcha_enabled():
            token = request.form.get("g-recaptcha-response", "")
            if not verify_recaptcha(token, request.remote_addr):
                errors["recaptcha"] = "Verificación reCAPTCHA falló."

        errors.update(_validate_prisoner_form_data(form_data, require_reason=True))

        if len(photo_files) > 1:
            errors["photo"] = "Solo puedes subir una foto."
        elif photo_files and not cloudinary_enabled:
            errors["photo"] = "Subida no disponible: falta configuración del servicio de imágenes."
        elif photo_files:
            ok, error = validate_files(photo_files)
            if not ok:
                errors["photo"] = error

        uploaded_photo_url = None
        if not errors and photo_files:
            try:
                uploaded_urls = upload_files(photo_files)
                uploaded_photo_url = uploaded_urls[0] if uploaded_urls else None
            except Exception:
                current_app.logger.exception("Error al subir foto de edición de prisionero")
                errors["photo"] = "No se pudo subir la foto."
            if not uploaded_photo_url and "photo" not in errors:
                errors["photo"] = "No se pudo subir la foto."

        final_image_url = uploaded_photo_url or form_data.get("image_url") or prisoner.image_url
        if not errors and not _has_prisoner_changes(
            prisoner,
            form_data,
            image_url=final_image_url,
        ):
            errors["form"] = "No se detectaron cambios en la ficha."

        if not errors:
            try:
                editor, editor_label = _get_editor_identity()
                snapshot_prisoner(
                    prisoner,
                    reason=form_data.get("reason") or "",
                    editor_id=editor.id if editor else None,
                    editor_label=editor_label,
                    payload={
                        "source": "community_prisoner_edit",
                        "photo_replaced": bool(uploaded_photo_url),
                    },
                )
                apply_prisoner_payload(
                    prisoner,
                    name=form_data.get("name") or "",
                    lastname=form_data.get("lastname"),
                    gender_label=form_data.get("gender_label"),
                    detention_typology=form_data.get("detention_typology"),
                    age_detention_label=form_data.get("age_detention_label"),
                    age_current_label=form_data.get("age_current_label"),
                    province_name=form_data.get("province_name"),
                    municipality_name=form_data.get("municipality_name"),
                    prison_name=form_data.get("prison_name"),
                    prison_latitude=form_data.get("prison_latitude"),
                    prison_longitude=form_data.get("prison_longitude"),
                    prison_address=form_data.get("prison_address"),
                    detention_date=form_data.get("detention_date"),
                    offense_types=form_data.get("offense_types"),
                    sentence_text=form_data.get("sentence_text"),
                    medical_status=form_data.get("medical_status"),
                    penal_status=form_data.get("penal_status"),
                    observations=form_data.get("observations"),
                    image_url=final_image_url,
                    source_detail_url=form_data.get("source_detail_url"),
                )
                db.session.commit()
                flash("Ficha de prisionero actualizada.", "success")
                return redirect(url_for("map.prisoner_detail", prisoner_id=prisoner.id))
            except Exception:
                db.session.rollback()
                current_app.logger.exception("Error guardando edición de prisionero")
                errors["form"] = "No se pudo guardar la edición. Inténtalo nuevamente."

    return render_template(
        "map/edit_prisoner.html",
        prisoner=prisoner,
        form_data=form_data,
        errors=errors,
        provinces=list_provinces(),
        municipalities_map=municipalities_map(),
        recaptcha_site_key=current_app.config.get("RECAPTCHA_V2_SITE_KEY"),
    )


@map_bp.route("/prisioneros/<int:prisoner_id>/historial")
def prisoner_history(prisoner_id):
    prisoner = Prisoner.query.filter_by(id=prisoner_id).first_or_404()
    revisions = (
        PrisonerRevision.query.filter_by(prisoner_id=prisoner.id)
        .order_by(PrisonerRevision.created_at.desc())
        .all()
    )
    latest_reason = revisions[0].reason if revisions else None
    return render_template(
        "map/prisoner_history.html",
        prisoner=prisoner,
        prisoner_payload=serialize_prisoner(prisoner, include_source=True),
        revisions=revisions,
        latest_reason=latest_reason,
    )


@map_bp.route("/prisioneros/<int:prisoner_id>/eliminar", methods=["POST"])
def delete_prisoner(prisoner_id):
    if not _is_admin_user():
        abort(403)

    prisoner = Prisoner.query.get_or_404(prisoner_id)
    full_name = prisoner.full_name
    try:
        db.session.delete(prisoner)
        db.session.commit()
        flash(f"Ficha eliminada: {full_name}.", "success")
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Error eliminando prisionero id=%s", prisoner_id)
        flash("No se pudo eliminar la ficha del prisionero.", "error")

    return redirect(url_for("map.prisoners"))
