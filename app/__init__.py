from flask import Flask
from dotenv import load_dotenv
from werkzeug.middleware.proxy_fix import ProxyFix
from .extensions import db, migrate, login_manager, limiter
from .blueprints.auth import auth_bp
from .blueprints.map import map_bp
from .blueprints.admin import admin_bp
from .blueprints.moderation import moderation_bp
from .blueprints.api import api_bp
from .blueprints.discussions import discussions_bp
from .blueprints.panic import panic_bp


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

    return app
