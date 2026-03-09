"""
Blueprint: /panic  — Botón de pánico

Rutas:
  GET  /panic          → sirve la página del botón
  POST /api/panic      → recibe lat/lng y crea el reporte directamente
"""

import secrets
from decimal import Decimal

from flask import current_app, jsonify, request

from app.extensions import db, limiter
from app.models.category import Category
from app.models.post import Post
from app.models.role import Role
from app.models.user import User
from app.services.geo_lookup import lookup_location
from app.services.push_notifications import push_enabled, send_alert_notification

from . import panic_bp


@panic_bp.route("/api/panic", methods=["POST"])
@limiter.limit("1/hour; 3/day")
def panic_report():
    data = request.get_json(silent=True) or {}

    try:
        lat = Decimal(str(data["latitude"]))
        lng = Decimal(str(data["longitude"]))
    except (KeyError, Exception):
        return jsonify({"ok": False, "error": "Coordenadas inválidas."}), 400

    if not (-90 <= float(lat) <= 90 and -180 <= float(lng) <= 180):
        return jsonify({"ok": False, "error": "Coordenadas fuera de rango."}), 400

    category = Category.query.filter_by(slug="accion-represiva").first()
    if not category:
        category = Category.query.first()
    if not category:
        return jsonify({"ok": False, "error": "Sin categorías configuradas."}), 500

    province, municipality = None, None
    try:
        province, municipality = lookup_location(float(lat), float(lng))
    except Exception:
        pass

    anon_user = User(email=f"panic+{secrets.token_hex(6)}@local")
    anon_user.set_password(secrets.token_urlsafe(16))
    anon_user.ensure_anon_code()
    default_role = Role.query.filter_by(name="colaborador").first()
    if default_role:
        anon_user.roles.append(default_role)
    db.session.add(anon_user)
    db.session.flush()

    description = (
        data.get("description")
        or f"Alerta enviada desde botón de pánico. "
        f"Coordenadas: {lat}, {lng}. "
        f"Verificar y ampliar descripción si es posible."
    )

    post = Post(
        title="🚨 Alerta SOS — Acción represiva",
        description=description[:2000],
        latitude=lat,
        longitude=lng,
        province=province or "",
        municipality=municipality or "",
        category_id=category.id,
        author_id=anon_user.id,
        status="approved",
    )
    db.session.add(post)
    db.session.commit()

    if push_enabled():
        try:
            send_alert_notification(post)
        except Exception:
            current_app.logger.exception("Push falló en panic report.")

    return jsonify({"ok": True, "id": post.id}), 201


@panic_bp.route("/panic")
def panic_page():
    return current_app.send_static_file("panic.html")
