from urllib.parse import urlparse

from flask import Flask, g, redirect, request, session, url_for
from flask_babel import gettext as _
from werkzeug.middleware.proxy_fix import ProxyFix

from .extensions import babel, db, limiter, login_manager, migrate
from .blueprints.auth import auth_bp
from .blueprints.map import map_bp
from .blueprints.admin import admin_bp
from .blueprints.moderation import moderation_bp
from .blueprints.api import api_bp
from .blueprints.discussions import discussions_bp
from .blueprints.panic import panic_bp


def create_app(config_object="config.settings.Config"):
    app = Flask(__name__)
    app.config.from_object(config_object)

    # ── Locale selector (defined before babel.init_app) ──────────────────
    def get_locale():
        # getattr fallback guards against AttributeError if called before
        # set_locale runs (e.g., in error handlers triggered early in the
        # request cycle)
        return getattr(g, "locale", "es")

    # ── Extensions ────────────────────────────────────────────────────────
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    limiter.init_app(app)
    babel.init_app(app, locale_selector=get_locale)

    if app.config.get("TRUST_PROXY_HEADERS", True):
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

    # ── Locale injection ──────────────────────────────────────────────────
    @app.before_request
    def set_locale():
        g.locale = (
            session.get("lang")
            or request.accept_languages.best_match(["es", "en"])
            or "es"
        )

    # ── Language switcher route ───────────────────────────────────────────
    @app.route("/set-lang/<lang>")
    @limiter.limit("30 per minute")
    def set_language(lang):
        if lang in ("es", "en"):
            session["lang"] = lang
        referrer = request.referrer
        if referrer:
            parsed = urlparse(referrer)
            # parsed.netloc is empty for relative URLs — those are safe to
            # follow since they cannot point outside the current host
            if parsed.netloc and parsed.netloc != request.host:
                referrer = None
        return redirect(referrer or url_for("map.dashboard"))

    # ── Blueprints ────────────────────────────────────────────────────────
    app.register_blueprint(auth_bp)
    app.register_blueprint(map_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(moderation_bp, url_prefix="/moderacion")
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(discussions_bp)
    app.register_blueprint(panic_bp)

    return app
