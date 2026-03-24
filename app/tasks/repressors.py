from app.celery_app import celery
from app.services.repressors import ingest_repressors_range


@celery.task(
    name="app.tasks.repressors.ingest_repressors_catalog",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 3},
)
def ingest_repressors_catalog(self, start_id=None, end_id=None):
    summary = ingest_repressors_range(start_id=start_id, end_id=end_id)
    return {
        "status": summary.get("status") or "ok",
        "run_id": summary.get("run_id"),
        "scan_start_id": summary.get("scan_start_id"),
        "scan_end_id": summary.get("scan_end_id"),
        "stored_items": summary.get("stored_items", 0),
        "updated_items": summary.get("updated_items", 0),
        "errors_count": summary.get("errors_count", 0),
    }
