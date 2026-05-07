import json
import secrets

from flask import current_app, flash, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from app.extensions import db, limiter
from app.models.news_comment import NewsComment
from app.models.news_post import NewsPost
from app.services.ai_text import generate_news_summary
from app.services.authz import role_required
from app.services.input_safety import has_malicious_input
from app.services.markdown_utils import render_markdown
from app.services.media_upload import parse_media_json, upload_files, validate_files
from app.services.news_posts import (
    clean_image_alts,
    fallback_news_summary,
    replace_news_image_tokens,
    standalone_news_images,
    unique_news_slug,
)
from app.services.recaptcha import recaptcha_enabled, verify_recaptcha
from . import news_bp


def _get_news_nick():
    allow_admin = current_user.is_authenticated and current_user.has_role("administrador")
    nick = session.get("news_nick")
    if nick and (nick.lower() != "admin" or allow_admin):
        return nick
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    code = "".join(secrets.choice(alphabet) for _ in range(4))
    nick = f"Anon-{code}"
    session["news_nick"] = nick
    return nick


def _resolve_news_nick(nickname: str) -> str:
    allow_admin = current_user.is_authenticated and current_user.has_role("administrador")
    value = (nickname or "").strip()
    if not value:
        value = _get_news_nick()
    if value.lower() == "admin" and not allow_admin:
        value = _get_news_nick()
    value = value[:80]
    session["news_nick"] = value
    return value


def _comment_tree(post_id: int):
    comments = NewsComment.query.filter_by(post_id=post_id).order_by(NewsComment.created_at.asc()).all()
    comment_map = {comment.id: comment for comment in comments}
    roots = []
    for comment in comments:
        comment.thread_children = []
        comment.rendered_body_html = comment.body_html or render_markdown(comment.body)
    for comment in comments:
        if comment.parent_id and comment.parent_id in comment_map:
            comment_map[comment.parent_id].thread_children.append(comment)
        else:
            roots.append(comment)
    return roots


def _uploaded_news_items_from_form():
    raw = (request.form.get("uploaded_images_json") or "").strip()
    if not raw:
        return []
    try:
        data = json.loads(raw) or []
    except Exception:
        return []
    items = []
    for item in data:
        if not isinstance(item, dict):
            continue
        url = (item.get("url") or "").strip()
        if not url:
            continue
        items.append({"url": url, "alt": (item.get("alt") or "").strip()[:255]})
    return items


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
        if recaptcha_enabled():
            token = request.form.get("g-recaptcha-response", "")
            if not verify_recaptcha(token, request.remote_addr):
                flash("Verificación reCAPTCHA falló. Intenta nuevamente.", "error")
                return redirect(url_for("news.new_post"))

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
        uploaded_items = _uploaded_news_items_from_form()

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

        if images:
            media_urls = upload_files(images)
            alts = clean_image_alts(image_alts, len(media_urls))
            posted_items = [
                {"url": url, "alt": alts[idx] if idx < len(alts) else ""}
                for idx, url in enumerate(media_urls)
            ]
            body = replace_news_image_tokens(body, posted_items)
            uploaded_items.extend(posted_items)

        if not summary:
            summary = fallback_news_summary(body)
        summary = summary[:500]

        post = NewsPost(
            title=title[:220],
            slug=unique_news_slug(title),
            author_name=author_name[:120],
            summary=summary,
            body=body,
            body_html=render_markdown(body, allow_images=True),
            images_json=json.dumps(uploaded_items) if uploaded_items else None,
            created_by_id=current_user.id if current_user.is_authenticated else None,
        )
        db.session.add(post)
        db.session.commit()
        flash("Noticia publicada.", "success")
        return redirect(url_for("news.detail", slug=post.slug))

    return render_template(
        "news/new.html",
        post=None,
        images=[],
        recaptcha_site_key=current_app.config.get("RECAPTCHA_V2_SITE_KEY"),
    )


@news_bp.route("/noticias/imagen", methods=["POST"])
@login_required
@role_required("administrador")
@limiter.limit("12/minute; 120/hour", methods=["POST"])
def upload_image():
    images = [
        file
        for file in request.files.getlist("images")
        if file and (file.filename or "").strip()
    ]
    image_alts = request.form.getlist("image_alts[]")
    if has_malicious_input(image_alts):
        return jsonify({"ok": False, "error": "Se detectó contenido sospechoso."}), 400
    if not images:
        return jsonify({"ok": False, "error": "Selecciona al menos una imagen."}), 400
    ok, error = validate_files(images)
    if not ok:
        return jsonify({"ok": False, "error": error}), 400

    media_urls = upload_files(images)
    alts = clean_image_alts(image_alts, len(media_urls))
    items = [
        {"url": url, "alt": alts[idx] if idx < len(alts) else ""}
        for idx, url in enumerate(media_urls)
    ]
    markdown = "\n".join(f"![{item.get('alt') or 'Imagen'}]({item['url']})" for item in items)
    return jsonify({"ok": True, "items": items, "markdown": markdown})


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


@news_bp.route("/noticias/comentarios/<int:comment_id>/eliminar", methods=["POST"])
@login_required
@role_required("administrador")
def delete_comment(comment_id):
    comment = NewsComment.query.get_or_404(comment_id)
    slug = comment.post.slug
    db.session.delete(comment)
    db.session.commit()
    flash("Comentario eliminado.", "success")
    return redirect(url_for("news.detail", slug=slug))


@news_bp.route("/noticias/<slug>", methods=["GET", "POST"])
@limiter.limit("6/minute; 120/day", methods=["POST"])
def detail(slug):
    post = NewsPost.query.filter_by(slug=slug).first_or_404()

    if request.method == "POST":
        if recaptcha_enabled():
            token = request.form.get("g-recaptcha-response", "")
            if not verify_recaptcha(token, request.remote_addr):
                flash("Verificación reCAPTCHA falló. Intenta nuevamente.", "error")
                return redirect(url_for("news.detail", slug=post.slug))
        body = request.form.get("comment_body", "").strip()
        nickname = request.form.get("comment_nickname", "").strip()
        parent_id = request.form.get("parent_id", "").strip()
        if has_malicious_input([body, nickname]):
            flash("Se detectó contenido sospechoso. Revisa y vuelve a intentar.", "error")
            return redirect(url_for("news.detail", slug=post.slug))
        if not body:
            flash("El comentario no puede estar vacío.", "error")
            return redirect(url_for("news.detail", slug=post.slug))

        parent = None
        if parent_id:
            try:
                parent_id_int = int(parent_id)
                parent = NewsComment.query.filter_by(id=parent_id_int, post_id=post.id).first()
            except Exception:
                parent = None

        comment = NewsComment(
            post_id=post.id,
            parent_id=parent.id if parent else None,
            body=body,
            body_html=render_markdown(body),
            author_label=_resolve_news_nick(nickname),
        )
        db.session.add(comment)
        db.session.commit()
        flash("Comentario agregado.", "success")
        return redirect(url_for("news.detail", slug=post.slug))

    images = parse_media_json(post.images_json)
    standalone_images = standalone_news_images(images, post.body)
    primary_image = images[0] if images else None
    return render_template(
        "news/detail.html",
        post=post,
        body_html=render_markdown(post.body, allow_images=True),
        images=standalone_images,
        primary_image=primary_image,
        comments=_comment_tree(post.id),
        nick=_get_news_nick(),
        recaptcha_site_key=current_app.config.get("RECAPTCHA_V2_SITE_KEY"),
        canonical_url=url_for("news.detail", slug=post.slug, _external=True),
    )
