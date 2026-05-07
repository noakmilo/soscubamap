import json
import re
import unicodedata

from sqlalchemy import func

from app.models.news_post import NewsPost


def slugify_news_title(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value).strip("-").lower()
    return slug[:180] or "noticia"


def unique_news_slug(title: str, current_post_id: int | None = None) -> str:
    base = slugify_news_title(title)
    slug = base
    counter = 2
    while True:
        query = NewsPost.query.filter(func.lower(NewsPost.slug) == slug.lower())
        if current_post_id:
            query = query.filter(NewsPost.id != current_post_id)
        if not query.first():
            return slug
        suffix = f"-{counter}"
        slug = f"{base[: 240 - len(suffix)]}{suffix}"
        counter += 1


def fallback_news_summary(body: str) -> str:
    compact = re.sub(r"\s+", " ", re.sub(r"[\*_#>`\[\]\(\)]", "", body or "")).strip()
    if len(compact) <= 300:
        return compact
    return compact[:297].rstrip() + "..."


def clean_image_alts(raw, count):
    alts = []
    for idx in range(count):
        value = ""
        if raw and idx < len(raw):
            value = (raw[idx] or "").strip()
        alts.append(value[:255])
    return alts


def build_news_images_json(urls, alts, existing=None) -> str | None:
    items = list(existing or [])
    for idx, url in enumerate(urls or []):
        items.append({"url": url, "alt": alts[idx] if idx < len(alts) else ""})
    return json.dumps(items) if items else None


def replace_news_image_tokens(body: str, uploaded_items) -> str:
    value = body or ""
    for idx, item in enumerate(uploaded_items or []):
        url = item.get("url") if isinstance(item, dict) else ""
        if not url:
            continue
        value = value.replace(f"news-image:{idx}", url)
    return value


def standalone_news_images(images, body: str):
    source = body or ""
    standalone = []
    for image in images or []:
        url = image.get("url") if isinstance(image, dict) else ""
        if not url or url in source:
            continue
        standalone.append(image)
    return standalone
