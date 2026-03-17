from celery import Celery, Task

from app import create_app


PROTEST_INGESTION_TASK = "app.tasks.protests.ingest_protests_feeds"


def _build_beat_schedule(flask_app):
    enabled = bool(flask_app.config.get("CELERY_PROTEST_INGESTION_ENABLED", True))
    if not enabled:
        return {}

    interval_seconds = 300
    try:
        with flask_app.app_context():
            from app.services.protests import get_fetch_interval_seconds

            interval_seconds = get_fetch_interval_seconds()
    except Exception:
        interval_raw = flask_app.config.get("PROTEST_FETCH_INTERVAL_SECONDS", 300)
        try:
            interval_seconds = int(interval_raw)
        except Exception:
            interval_seconds = 300
        interval_seconds = max(60, interval_seconds)

    queue_name = (flask_app.config.get("CELERY_PROTEST_QUEUE") or "ingestion").strip()
    if not queue_name:
        queue_name = "ingestion"

    return {
        "protest-feed-ingestion": {
            "task": PROTEST_INGESTION_TASK,
            "schedule": interval_seconds,
            "options": {"queue": queue_name},
        }
    }


def create_celery(config_object="config.settings.Config"):
    flask_app = create_app(config_object)
    celery = Celery(flask_app.import_name)

    broker_url = (flask_app.config.get("CELERY_BROKER_URL") or "redis://localhost:6379/1").strip()
    result_backend = (
        flask_app.config.get("CELERY_RESULT_BACKEND") or broker_url or "redis://localhost:6379/1"
    ).strip()
    queue_name = (flask_app.config.get("CELERY_PROTEST_QUEUE") or "ingestion").strip()
    timezone = (flask_app.config.get("CELERY_TIMEZONE") or "UTC").strip() or "UTC"

    celery.conf.update(
        broker_url=broker_url,
        result_backend=result_backend,
        task_default_queue=queue_name or "ingestion",
        task_ignore_result=True,
        task_track_started=True,
        accept_content=["json"],
        task_serializer="json",
        result_serializer="json",
        enable_utc=True,
        timezone=timezone,
        beat_schedule=_build_beat_schedule(flask_app),
    )

    class FlaskTask(Task):
        abstract = True

        def __call__(self, *args, **kwargs):
            with flask_app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = FlaskTask
    celery.flask_app = flask_app
    return celery


celery = create_celery()

# Importa tasks para registrar decoradores @celery.task.
import app.tasks.protests  # noqa: E402,F401
