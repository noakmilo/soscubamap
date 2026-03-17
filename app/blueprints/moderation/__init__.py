from flask import Blueprint

moderation_bp = Blueprint(
    "moderation", __name__, template_folder="../../templates/moderation"
)

from . import routes  # noqa: E402,F401
