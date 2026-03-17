from urllib.parse import urlparse, urlunparse

from app.extensions import db
from app.models.protest_feed_source import ProtestFeedSource


def normalize_feed_url(raw_url):
    text = str(raw_url or "").strip()
    if not text:
        return ""
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"}:
        return ""
    if not parsed.netloc:
        return ""
    normalized = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower(),
        fragment="",
    )
    return urlunparse(normalized)


def get_protest_feed_urls_from_db():
    rows = (
        ProtestFeedSource.query.order_by(
            ProtestFeedSource.sort_order.asc(),
            ProtestFeedSource.id.asc(),
        ).all()
    )
    return [row.feed_url for row in rows if row.feed_url]


def validate_protest_feed_urls(raw_urls):
    cleaned = []
    errors = []
    seen = set()

    for idx, raw in enumerate(raw_urls or [], start=1):
        text = str(raw or "").strip()
        if not text:
            continue
        normalized = normalize_feed_url(text)
        if not normalized:
            errors.append(f"Feed #{idx}: URL inválida. Usa http:// o https://.")
            continue
        if normalized in seen:
            errors.append(f"Feed #{idx}: URL duplicada.")
            continue
        seen.add(normalized)
        cleaned.append(normalized)

    if not cleaned:
        errors.append("Debes agregar al menos un feed.")

    return cleaned, errors


def save_protest_feed_urls(urls):
    ProtestFeedSource.query.delete()
    for idx, feed_url in enumerate(urls or []):
        db.session.add(
            ProtestFeedSource(
                feed_url=str(feed_url),
                sort_order=idx,
            )
        )
    db.session.commit()
