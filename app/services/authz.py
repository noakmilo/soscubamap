from functools import wraps

from flask import abort
from flask_login import current_user


def role_required(*roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if not any(current_user.has_role(role) for role in roles):
                abort(403)
            return fn(*args, **kwargs)

        return wrapper

    return decorator
