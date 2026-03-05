from flask import Blueprint

panic_bp = Blueprint("panic", __name__, template_folder="templates")

from . import routes  # noqa: E402,F401
