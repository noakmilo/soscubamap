from datetime import datetime, timezone

from app.celery_app import celery
from app.services.flights import ingest_flights_cuba


@celery.task(
    name="app.tasks.flights.ingest_flights_cuba",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=300,
    retry_backoff_max=1800,
    retry_jitter=True,
    retry_kwargs={"max_retries": 2},
)
def ingest_flights_cuba_task(self):
    scheduled_for = datetime.now(timezone.utc).replace(tzinfo=None)
    return ingest_flights_cuba(scheduled_for=scheduled_for, raise_on_error=True)
