from flask import Flask
from dotenv import load_dotenv
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_login import current_user
from .extensions import db, migrate, login_manager, limiter
from .blueprints.auth import auth_bp
from .blueprints.map import map_bp
from .blueprints.admin import admin_bp
from .blueprints.moderation import moderation_bp
from .blueprints.api import api_bp
from .blueprints.discussions import discussions_bp
from .blueprints.panic import panic_bp
from .blueprints.news import news_bp


def create_app(config_object="config.settings.Config"):
    load_dotenv()
    app = Flask(__name__)
    app.config.from_object(config_object)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    limiter.init_app(app)

    if app.config.get("TRUST_PROXY_HEADERS", True):
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

    app.register_blueprint(auth_bp)
    app.register_blueprint(map_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(moderation_bp, url_prefix="/moderacion")
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(discussions_bp)
    app.register_blueprint(panic_bp)
    app.register_blueprint(news_bp)

    @app.context_processor
    def inject_moderation_pending_count():
        pending_count = 0
        try:
            if current_user.is_authenticated and current_user.has_role("administrador"):
                from app.models.post import Post
                from app.models.post_edit_request import PostEditRequest
                from app.models.repressor import RepressorEditRequest, RepressorSubmission

                pending_posts = Post.query.filter_by(status="pending").count()
                pending_edits = PostEditRequest.query.filter_by(status="pending").count()
                pending_repressors = RepressorSubmission.query.filter_by(status="pending").count()
                pending_repressor_edits = RepressorEditRequest.query.filter_by(
                    status="pending"
                ).count()
                pending_count = (
                    int(pending_posts or 0)
                    + int(pending_edits or 0)
                    + int(pending_repressors or 0)
                    + int(pending_repressor_edits or 0)
                )
        except Exception:
            pending_count = 0
        return {"moderation_pending_count": pending_count}

    return app
