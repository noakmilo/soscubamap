import json
from datetime import datetime

from flask import current_app, url_for

try:
    from pywebpush import WebPushException, webpush
except Exception:  # pragma: no cover - optional dependency at runtime
    webpush = None
    WebPushException = Exception

from app.extensions import db
from app.models.push_subscription import PushSubscription
from app.services.text_sanitize import sanitize_text

ALERT_ICON_PATH = "/static/img/favico.png"


def push_enabled() -> bool:
    if webpush is None:
        return False
    return bool(
        current_app.config.get("VAPID_PUBLIC_KEY")
        and current_app.config.get("VAPID_PRIVATE_KEY")
    )


def _format_alert_payload(post):
    category_name = post.category.name if post.category else "Alerta"
    title = sanitize_text(f"Alerta: {category_name}", max_len=64) or "Alerta SOSCuba"
    location = " · ".join(
        [part for part in [post.province or "", post.municipality or ""] if part]
    )
    timestamp = post.movement_at or post.created_at
    timestamp_label = ""
    if timestamp:
        timestamp_label = timestamp.strftime("%Y-%m-%d %H:%M")
    body_parts = [sanitize_text(post.title, max_len=90)]
    if location:
        body_parts.append(location)
    if timestamp_label:
        body_parts.append(timestamp_label)
    body = " · ".join([part for part in body_parts if part])
    url = url_for("map.report_detail", post_id=post.id, _external=True)
    return {
        "title": title,
        "body": sanitize_text(body, max_len=160),
        "url": url,
        "tag": f"alert-{post.id}",
        "icon": ALERT_ICON_PATH,
        "badge": ALERT_ICON_PATH,
    }


def send_alert_notification(post) -> int:
    if not push_enabled():
        return 0

    subscriptions = PushSubscription.query.filter_by(active=True).all()
    if not subscriptions:
        return 0

    vapid_private_key = current_app.config.get("VAPID_PRIVATE_KEY")
    vapid_subject = current_app.config.get(
        "VAPID_SUBJECT", "mailto:soscubamap@proton.me"
    )
    payload = json.dumps(_format_alert_payload(post))

    delivered = 0
    stale = []
    for subscription in subscriptions:
        try:
            webpush(
                subscription_info={
                    "endpoint": subscription.endpoint,
                    "keys": {
                        "p256dh": subscription.p256dh,
                        "auth": subscription.auth,
                    },
                },
                data=payload,
                vapid_private_key=vapid_private_key,
                vapid_claims={"sub": vapid_subject},
            )
            delivered += 1
        except WebPushException as exc:
            response = getattr(exc, "response", None)
            status = getattr(response, "status_code", None)
            if status in (404, 410):
                stale.append(subscription)

    if stale:
        for subscription in stale:
            subscription.active = False
            subscription.updated_at = datetime.utcnow()
        db.session.commit()

    return delivered
