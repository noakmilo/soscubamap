from celery import Celery, Task

from app import create_app


PROTEST_INGESTION_TASK = "app.tasks.protests.ingest_protests_feeds"
CONNECTIVITY_POLL_TASK = "app.tasks.connectivity.poll_connectivity_and_create_reports"
AIS_INGESTION_TASK = "app.tasks.ais.ingest_aisstream_cuba_targets"
FLIGHTS_INGESTION_TASK = "app.tasks.flights.ingest_flights_cuba"
FLIGHTS_DETAIL_PRELOAD_DAILY_TASK = "app.tasks.flights.preload_flights_detail_daily"
REPRESSOR_INGESTION_TASK = "app.tasks.repressors.ingest_repressors_catalog"
POST_EXPIRATION_TASK = "app.tasks.posts.expire_map_alert_posts"


def _build_beat_schedule(flask_app):
    schedule = {}

    protest_enabled = bool(flask_app.config.get("CELERY_PROTEST_INGESTION_ENABLED", True))
    if protest_enabled:
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

        schedule["protest-feed-ingestion"] = {
            "task": PROTEST_INGESTION_TASK,
            "schedule": interval_seconds,
            "options": {"queue": queue_name},
        }

    connectivity_enabled = bool(flask_app.config.get("CELERY_CONNECTIVITY_POLLING_ENABLED", True))
    if connectivity_enabled:
        interval_raw = flask_app.config.get("CELERY_CONNECTIVITY_POLLING_INTERVAL_SECONDS", 7200)
        try:
            interval_seconds = int(interval_raw)
        except Exception:
            interval_seconds = 7200
        interval_seconds = max(300, interval_seconds)

        queue_name = (flask_app.config.get("CELERY_CONNECTIVITY_QUEUE") or "ingestion").strip()
        if not queue_name:
            queue_name = "ingestion"

        schedule["connectivity-polling-auto-reports"] = {
            "task": CONNECTIVITY_POLL_TASK,
            "schedule": interval_seconds,
            "options": {"queue": queue_name},
        }

    ais_enabled = bool(flask_app.config.get("AISSTREAM_ENABLED", False)) and bool(
        flask_app.config.get("CELERY_AIS_INGESTION_ENABLED", True)
    )
    if ais_enabled:
        interval_seconds = 86400
        try:
            with flask_app.app_context():
                from app.services.aisstream import get_ais_ingestion_interval_seconds

                interval_seconds = get_ais_ingestion_interval_seconds()
        except Exception:
            interval_raw = flask_app.config.get("AISSTREAM_INGESTION_INTERVAL_SECONDS", 86400)
            try:
                interval_seconds = int(interval_raw)
            except Exception:
                interval_seconds = 86400
            interval_seconds = max(3600, interval_seconds)

        queue_name = (flask_app.config.get("CELERY_AIS_QUEUE") or "ingestion").strip()
        if not queue_name:
            queue_name = "ingestion"

        schedule["aisstream-cuba-target-ingestion"] = {
            "task": AIS_INGESTION_TASK,
            "schedule": interval_seconds,
            "options": {"queue": queue_name},
        }

    flights_enabled = bool(flask_app.config.get("FLIGHTS_ENABLED", False)) and bool(
        flask_app.config.get("CELERY_FLIGHTS_INGESTION_ENABLED", True)
    )
    if flights_enabled:
        interval_seconds = 900
        try:
            with flask_app.app_context():
                from app.services.flights import get_flights_ingestion_interval_seconds

                interval_seconds = get_flights_ingestion_interval_seconds()
        except Exception:
            interval_raw = flask_app.config.get("FLIGHTS_INGESTION_INTERVAL_SECONDS", 900)
            try:
                interval_seconds = int(interval_raw)
            except Exception:
                interval_seconds = 900
            interval_seconds = max(60, interval_seconds)

        queue_name = (flask_app.config.get("CELERY_FLIGHTS_QUEUE") or "ingestion").strip()
        if not queue_name:
            queue_name = "ingestion"

        schedule["flights-cuba-ingestion"] = {
            "task": FLIGHTS_INGESTION_TASK,
            "schedule": interval_seconds,
            "options": {"queue": queue_name},
        }

        detail_preload_daily_enabled = bool(
            flask_app.config.get("FLIGHTS_DETAIL_PRELOAD_ENABLED", True)
        ) and bool(flask_app.config.get("FLIGHTS_DETAIL_PRELOAD_DAILY_ENABLED", True))
        if detail_preload_daily_enabled:
            preload_interval_seconds = 86400
            try:
                with flask_app.app_context():
                    from app.services.flights import (
                        get_flights_detail_preload_daily_interval_seconds,
                    )

                    preload_interval_seconds = get_flights_detail_preload_daily_interval_seconds()
            except Exception:
                interval_raw = flask_app.config.get(
                    "FLIGHTS_DETAIL_PRELOAD_DAILY_INTERVAL_SECONDS",
                    86400,
                )
                try:
                    preload_interval_seconds = int(interval_raw)
                except Exception:
                    preload_interval_seconds = 86400
                preload_interval_seconds = max(3600, preload_interval_seconds)

            schedule["flights-detail-preload-daily"] = {
                "task": FLIGHTS_DETAIL_PRELOAD_DAILY_TASK,
                "schedule": preload_interval_seconds,
                "options": {"queue": queue_name},
            }

    repressor_enabled = bool(
        flask_app.config.get("CELERY_REPRESSOR_INGESTION_ENABLED", True)
    )
    if repressor_enabled:
        interval_seconds = 86400
        try:
            with flask_app.app_context():
                from app.services.repressors import get_ingestion_interval_seconds

                interval_seconds = get_ingestion_interval_seconds()
        except Exception:
            interval_raw = flask_app.config.get("REPRESSOR_INGESTION_INTERVAL_SECONDS", 86400)
            try:
                interval_seconds = int(interval_raw)
            except Exception:
                interval_seconds = 86400
            interval_seconds = max(3600, interval_seconds)

        queue_name = (flask_app.config.get("CELERY_REPRESSOR_QUEUE") or "ingestion").strip()
        if not queue_name:
            queue_name = "ingestion"

        schedule["repressor-catalog-ingestion"] = {
            "task": REPRESSOR_INGESTION_TASK,
            "schedule": interval_seconds,
            "options": {"queue": queue_name},
        }

    post_expiration_enabled = bool(
        flask_app.config.get("CELERY_POST_EXPIRATION_ENABLED", True)
    )
    if post_expiration_enabled:
        interval_raw = flask_app.config.get("CELERY_POST_EXPIRATION_INTERVAL_SECONDS", 86400)
        try:
            interval_seconds = int(interval_raw)
        except Exception:
            interval_seconds = 86400
        interval_seconds = max(3600, interval_seconds)

        queue_name = (flask_app.config.get("CELERY_POST_EXPIRATION_QUEUE") or "ingestion").strip()
        if not queue_name:
            queue_name = "ingestion"

        schedule["post-map-expiration"] = {
            "task": POST_EXPIRATION_TASK,
            "schedule": interval_seconds,
            "options": {"queue": queue_name},
        }

    return schedule


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
import app.tasks.connectivity  # noqa: E402,F401
import app.tasks.ais  # noqa: E402,F401
import app.tasks.flights  # noqa: E402,F401
import app.tasks.repressors  # noqa: E402,F401
import app.tasks.posts  # noqa: E402,F401
