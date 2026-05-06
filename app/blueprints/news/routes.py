import json
import re
import unicodedata

from flask import current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from app.extensions import db, limiter
from app.models.news_post import NewsPost
from app.services.authz import role_required
from app.services.input_safety import has_malicious_input
from app.services.markdown_utils import render_markdown
from app.services.media_upload import parse_media_json, upload_files, validate_files
from app.services.ai_text import generate_news_summary
from . import news_bp


def _slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value).strip("-").lower()
    return slug[:180] or "noticia"


def _unique_slug(title: str) -> str:
    base = _slugify(title)
    slug = base
    counter = 2
    while NewsPost.query.filter(func.lower(NewsPost.slug) == slug.lower()).first():
        suffix = f"-{counter}"
        slug = f"{base[: 240 - len(suffix)]}{suffix}"
        counter += 1
    return slug


def _fallback_summary(body: str) -> str:
    compact = re.sub(r"\s+", " ", re.sub(r"[\*_#>`\[\]\(\)]", "", body or "")).strip()
    if len(compact) <= 300:
        return compact
    return compact[:297].rstrip() + "..."


def _clean_image_alts(raw, count):
    alts = []
    for idx in range(count):
        value = ""
        if raw and idx < len(raw):
            value = (raw[idx] or "").strip()
        alts.append(value[:255])
    return alts


@news_bp.route("/noticias")
def index():
    posts = NewsPost.query.order_by(NewsPost.created_at.desc()).all()
    for post in posts:
        images = parse_media_json(post.images_json)
        post.thumbnail = images[0] if images else None
    return render_template("news/index.html", posts=posts)


@news_bp.route("/noticias/new", methods=["GET", "POST"])
@login_required
@role_required("administrador")
@limiter.limit("3/minute; 40/day", methods=["POST"])
def new_post():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        author_name = request.form.get("author_name", "").strip()
        summary = request.form.get("summary", "").strip()
        body = request.form.get("body", "").strip()
        images = [
            file
            for file in request.files.getlist("images")
            if file and (file.filename or "").strip()
        ]
        image_alts = request.form.getlist("image_alts[]")

        if has_malicious_input([title, author_name, summary, body] + image_alts):
            flash("Se detectó contenido sospechoso. Revisa y vuelve a intentar.", "error")
            return redirect(url_for("news.new_post"))

        if not title or not author_name or not body:
            flash("Título, autor y cuerpo son obligatorios.", "error")
            return redirect(url_for("news.new_post"))

        if images:
            ok, error = validate_files(images)
            if not ok:
                flash(error, "error")
                return redirect(url_for("news.new_post"))

        if not summary:
            summary = _fallback_summary(body)
        summary = summary[:500]

        images_json = None
        if images:
            media_urls = upload_files(images)
            alts = _clean_image_alts(image_alts, len(media_urls))
            items = [
                {"url": url, "alt": alts[idx] if idx < len(alts) else ""}
                for idx, url in enumerate(media_urls)
            ]
            images_json = json.dumps(items)

        post = NewsPost(
            title=title[:220],
            slug=_unique_slug(title),
            author_name=author_name[:120],
            summary=summary,
            body=body,
            body_html=render_markdown(body),
            images_json=images_json,
            created_by_id=current_user.id if current_user.is_authenticated else None,
        )
        db.session.add(post)
        db.session.commit()
        flash("Noticia publicada.", "success")
        return redirect(url_for("news.detail", slug=post.slug))

    return render_template("news/new.html")


@news_bp.route("/noticias/resumen", methods=["POST"])
@login_required
@role_required("administrador")
@limiter.limit("6/minute; 60/hour", methods=["POST"])
def summarize():
    payload = request.get_json(silent=True) or {}
    title = (payload.get("title") or "").strip()
    body = (payload.get("body") or "").strip()
    if not body:
        return jsonify({"ok": False, "error": "Escribe el cuerpo de la noticia primero."}), 400
    if has_malicious_input([title, body]):
        return jsonify({"ok": False, "error": "Se detectó contenido sospechoso."}), 400
    try:
        summary = generate_news_summary(title=title, body=body)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 503
    except Exception:
        current_app.logger.exception("Error al generar resumen de noticia")
        return jsonify({"ok": False, "error": "No se pudo generar el resumen."}), 502
    return jsonify({"ok": True, "summary": summary})


@news_bp.route("/noticias/<slug>")
def detail(slug):
    post = NewsPost.query.filter_by(slug=slug).first_or_404()
    images = parse_media_json(post.images_json)
    return render_template("news/detail.html", post=post, images=images)
