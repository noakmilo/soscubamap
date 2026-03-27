from datetime import datetime, timezone

from app.celery_app import celery
from app.services.aisstream import ingest_aisstream_cuba_targets as run_ais_ingestion


@celery.task(
    name="app.tasks.ais.ingest_aisstream_cuba_targets",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=300,
    retry_backoff_max=3600,
    retry_jitter=True,
    retry_kwargs={"max_retries": 2},
)
def ingest_aisstream_cuba_targets(self):
    scheduled_for = datetime.now(timezone.utc).replace(tzinfo=None)
    return run_ais_ingestion(scheduled_for=scheduled_for, raise_on_error=True)
