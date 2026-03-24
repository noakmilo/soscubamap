from __future__ import annotations

from datetime import datetime, timedelta

from flask import current_app
from sqlalchemy import func
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models.category import Category
from app.models.post import Post


def _normalize_slugs(raw_value) -> list[str]:
    if isinstance(raw_value, (list, tuple, set)):
        values = raw_value
    else:
        values = str(raw_value or "").split(",")
    out: list[str] = []
    seen = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def expire_old_map_alert_posts() -> dict:
    category_slugs = _normalize_slugs(
        current_app.config.get(
            "POST_EXPIRATION_CATEGORY_SLUGS",
            "accion-represiva,movimiento-tropas",
        )
    )
    if not category_slugs:
        return {
            "status": "ok",
            "expired_count": 0,
            "reason": "no_category_slugs_configured",
        }

    days_raw = current_app.config.get("POST_EXPIRATION_DAYS", 7)
    try:
        days = int(days_raw)
    except Exception:
        days = 7
    days = max(1, days)

    now = datetime.utcnow()
    threshold = now - timedelta(days=days)

    matched_categories = Category.query.filter(Category.slug.in_(category_slugs)).all()
    if not matched_categories:
        return {
            "status": "ok",
            "expired_count": 0,
            "threshold_utc": threshold.isoformat(),
            "days": days,
            "reason": "no_matching_categories",
        }

    category_ids = [item.id for item in matched_categories]
    category_by_id = {item.id: item.slug for item in matched_categories}

    reference_time = func.coalesce(Post.movement_at, Post.created_at)
    rows = (
        Post.query.options(selectinload(Post.category))
        .filter(
            Post.status == "approved",
            Post.category_id.in_(category_ids),
            reference_time <= threshold,
        )
        .all()
    )
    if not rows:
        return {
            "status": "ok",
            "expired_count": 0,
            "threshold_utc": threshold.isoformat(),
            "days": days,
            "categories": category_slugs,
        }

    expired_by_slug: dict[str, int] = {}
    expired_ids: list[int] = []
    for post in rows:
        post.status = "hidden"
        slug = category_by_id.get(post.category_id) or ""
        if not slug and post.category:
            slug = (post.category.slug or "").strip()
        slug = slug or "unknown"
        expired_by_slug[slug] = expired_by_slug.get(slug, 0) + 1
        expired_ids.append(post.id)

    db.session.commit()
    return {
        "status": "ok",
        "expired_count": len(expired_ids),
        "expired_ids": expired_ids[:200],
        "expired_by_category": expired_by_slug,
        "threshold_utc": threshold.isoformat(),
        "days": days,
        "categories": category_slugs,
    }
