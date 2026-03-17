"""seed protest settings and feeds

Revision ID: f6e1a4b9c2d3
Revises: c4f8a9d1e2b3
Create Date: 2026-03-17 18:20:00.000000

"""

from datetime import datetime
import json
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f6e1a4b9c2d3"
down_revision = "c4f8a9d1e2b3"
branch_labels = None
depends_on = None


PROTEST_SETTING_DEFAULTS = {
    "PROTEST_FETCH_INTERVAL_SECONDS": "300",
    "PROTEST_FETCH_TIMEOUT_SECONDS": "20",
    "PROTEST_FRONTEND_REFRESH_SECONDS": "300",
    "PROTEST_MAX_POST_AGE_DAYS": "7",
    "PROTEST_MAX_ITEMS_PER_FEED": "120",
    "PROTEST_REQUIRE_SOURCE_URL": "1",
    "PROTEST_ALLOW_UNRESOLVED_TO_MAP": "0",
    "PROTEST_MIN_CONFIDENCE_TO_SHOW": "10",
    "PROTEST_KEYWORDS_STRONG": (
        "protesta,protestas,protestantes,manifestantes,cacerolazo,"
        "a la calle,cacerolas,calderos,trancar calles,gritar libertad"
    ),
    "PROTEST_KEYWORDS_CONTEXT": (
        "detenidos,fuente,represion,descontento social,"
        "indignacion popular,enfrentamiento,sin orden judicial"
    ),
    "PROTEST_KEYWORDS_WEAK": "situacion,tension,incidente",
}


def _normalize_feed_url(raw_url):
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


def _load_seed_feed_urls():
    project_root = Path(__file__).resolve().parents[2]
    feeds_path = project_root / "app" / "static" / "data" / "protest_feeds.json"
    if not feeds_path.exists():
        return []

    try:
        payload = json.loads(feeds_path.read_text(encoding="utf-8"))
    except Exception:
        return []

    items = payload.get("feeds") if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        return []

    cleaned = []
    seen = set()
    for raw_url in items:
        normalized = _normalize_feed_url(raw_url)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(normalized)
    return cleaned


def upgrade():
    connection = op.get_bind()
    now = datetime.utcnow()

    site_settings = sa.table(
        "site_settings",
        sa.column("id", sa.Integer()),
        sa.column("key", sa.String()),
        sa.column("value", sa.String()),
    )
    protest_feed_sources = sa.table(
        "protest_feed_sources",
        sa.column("id", sa.Integer()),
        sa.column("feed_url", sa.String()),
        sa.column("sort_order", sa.Integer()),
        sa.column("created_at", sa.DateTime()),
        sa.column("updated_at", sa.DateTime()),
    )

    setting_keys = list(PROTEST_SETTING_DEFAULTS.keys())
    existing_keys = {
        row[0]
        for row in connection.execute(
            sa.select(site_settings.c.key).where(site_settings.c.key.in_(setting_keys))
        ).fetchall()
    }

    new_settings = []
    for key, value in PROTEST_SETTING_DEFAULTS.items():
        if key in existing_keys:
            continue
        new_settings.append({"key": key, "value": str(value)})

    if new_settings:
        op.bulk_insert(site_settings, new_settings)

    existing_feed_count = (
        connection.execute(sa.select(sa.func.count()).select_from(protest_feed_sources)).scalar()
        or 0
    )
    if existing_feed_count:
        return

    feeds = _load_seed_feed_urls()
    if not feeds:
        return

    op.bulk_insert(
        protest_feed_sources,
        [
            {
                "feed_url": feed_url,
                "sort_order": idx,
                "created_at": now,
                "updated_at": now,
            }
            for idx, feed_url in enumerate(feeds)
        ],
    )


def downgrade():
    # No se borran datos de configuración/feeds para evitar pérdida de cambios del admin.
    pass
