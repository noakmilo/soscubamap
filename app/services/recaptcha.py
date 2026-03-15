import json
import urllib.parse
import urllib.request

from flask import current_app


def recaptcha_enabled() -> bool:
    return bool(current_app.config.get("RECAPTCHA_V2_SECRET_KEY"))


def verify_recaptcha(token: str, remote_ip: str | None = None) -> bool:
    secret = current_app.config.get("RECAPTCHA_V2_SECRET_KEY")
    if not secret:
        return True
    if not token:
        return False

    payload = {"secret": secret, "response": token}
    if remote_ip:
        payload["remoteip"] = remote_ip

    data = urllib.parse.urlencode(payload).encode("utf-8")
    try:
        req = urllib.request.Request(
            "https://www.google.com/recaptcha/api/siteverify",
            data=data,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            body = resp.read().decode("utf-8")
            result = json.loads(body)
            return bool(result.get("success"))
    except Exception:
        return False
