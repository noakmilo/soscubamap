import re

from app.extensions import db
from app.models.discussion_tag import DiscussionTag


def normalize_tag(value: str) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value.strip().lower())


def upsert_tags(raw_tags):
    tags = []
    for raw in raw_tags:
        slug = normalize_tag(raw)
        if not slug:
            continue
        existing = DiscussionTag.query.filter_by(slug=slug).first()
        if existing:
            tags.append(existing)
            continue
        tag = DiscussionTag(name=raw.strip()[:80], slug=slug[:80])
        db.session.add(tag)
        db.session.flush()
        tags.append(tag)
    return tags
