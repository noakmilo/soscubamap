from app.celery_app import celery
from scripts.fetch_protests import run_ingestion


def _normalize_feeds(feeds):
    if not isinstance(feeds, (list, tuple)):
        return []
    normalized = []
    for value in feeds:
        text = str(value or "").strip()
        if text:
            normalized.append(text)
    return normalized


@celery.task(
    name="app.tasks.protests.ingest_protests_feeds",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 3},
)
def ingest_protests_feeds(self, feeds=None):
    feed_urls = _normalize_feeds(feeds)
    run_ingestion(feed_urls)
    return {
        "status": "ok",
        "feeds": len(feed_urls),
    }
