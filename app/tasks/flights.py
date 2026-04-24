from datetime import datetime, timezone

from app.celery_app import celery
from app.services.flights import (
    get_flights_detail_preload_daily_lookback_hours,
    get_flights_detail_preload_daily_max_events,
    get_flights_detail_preload_delay_seconds,
    get_flights_detail_preload_enabled,
    get_flights_detail_preload_max_events_per_run,
    ingest_flights_cuba,
    preload_missing_flight_details,
)


def _flights_queue_name() -> str:
    queue_name = (celery.flask_app.config.get("CELERY_FLIGHTS_QUEUE") or "ingestion").strip()
    return queue_name or "ingestion"


def _schedule_detail_preload_for_run(run_id: int) -> bool:
    if run_id <= 0:
        return False
    if not get_flights_detail_preload_enabled():
        return False

    delay_seconds = get_flights_detail_preload_delay_seconds()
    preload_flights_detail_after_ingestion_task.apply_async(
        kwargs={
            "run_id": int(run_id),
            "max_events": int(get_flights_detail_preload_max_events_per_run()),
        },
        countdown=int(max(0, delay_seconds)),
        queue=_flights_queue_name(),
    )
    return True


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
    result = ingest_flights_cuba(scheduled_for=scheduled_for, raise_on_error=True)
    if not isinstance(result, dict):
        return result

    run_id = result.get("run_id")
    try:
        safe_run_id = int(run_id)
    except Exception:
        safe_run_id = 0

    try:
        queued = _schedule_detail_preload_for_run(safe_run_id)
        result["detail_preload_queued"] = bool(queued)
        if queued:
            result["detail_preload_delay_seconds"] = int(get_flights_detail_preload_delay_seconds())
    except Exception as exc:
        result["detail_preload_queued"] = False
        warnings = list(result.get("warnings") or [])
        warnings.append(f"No se pudo encolar precarga de detalle: {exc}")
        result["warnings"] = warnings

    return result


@celery.task(
    name="app.tasks.flights.preload_flights_detail_after_ingestion",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=120,
    retry_backoff_max=900,
    retry_jitter=True,
    retry_kwargs={"max_retries": 2},
)
def preload_flights_detail_after_ingestion_task(self, run_id=None, max_events=None):
    try:
        safe_run_id = int(run_id)
    except Exception:
        safe_run_id = 0
    if safe_run_id <= 0:
        return {
            "status": "skipped",
            "reason": "invalid_run_id",
        }

    safe_max_events = get_flights_detail_preload_max_events_per_run()
    if max_events is not None:
        try:
            safe_max_events = int(max_events)
        except Exception:
            safe_max_events = get_flights_detail_preload_max_events_per_run()

    return preload_missing_flight_details(
        run_id=safe_run_id,
        max_events=safe_max_events,
    )


@celery.task(
    name="app.tasks.flights.preload_flights_detail_daily",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=300,
    retry_backoff_max=1800,
    retry_jitter=True,
    retry_kwargs={"max_retries": 2},
)
def preload_flights_detail_daily_task(self):
    return preload_missing_flight_details(
        max_events=get_flights_detail_preload_daily_max_events(),
        lookback_hours=get_flights_detail_preload_daily_lookback_hours(),
    )
