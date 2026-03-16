import threading
from datetime import datetime, timedelta

_SCHEDULER_THREAD = None
_SCHEDULER_THREAD_LOCK = threading.Lock()
_SCHEDULER_STOP_EVENT = threading.Event()
_POSTGRES_LOCK_KEY = 74201931


def _log(app, level, message):
    logger = getattr(app, "logger", None)
    if not logger:
        return
    fn = getattr(logger, level, None)
    if callable(fn):
        fn(message)


def _run_with_postgres_lock(app, callback):
    from app.extensions import db

    driver = str(getattr(db.engine.url, "drivername", "") or "")
    if not driver.startswith("postgresql"):
        callback()
        return True

    raw = None
    cur = None
    acquired = False
    try:
        raw = db.engine.raw_connection()
        cur = raw.cursor()
        cur.execute("SELECT pg_try_advisory_lock(%s)", (_POSTGRES_LOCK_KEY,))
        row = cur.fetchone()
        acquired = bool(row and row[0])
        if not acquired:
            return False
        callback()
        return True
    finally:
        if acquired and cur is not None:
            try:
                cur.execute("SELECT pg_advisory_unlock(%s)", (_POSTGRES_LOCK_KEY,))
            except Exception:
                pass
        if cur is not None:
            try:
                cur.close()
            except Exception:
                pass
        if raw is not None:
            try:
                raw.close()
            except Exception:
                pass


def _should_skip_recent_run(app, interval_seconds):
    from app.models.protest_ingestion_run import ProtestIngestionRun

    last_run = (
        ProtestIngestionRun.query.order_by(
            ProtestIngestionRun.started_at_utc.desc(),
            ProtestIngestionRun.id.desc(),
        )
        .limit(1)
        .first()
    )
    if not last_run or not last_run.started_at_utc:
        return False

    now = datetime.utcnow()
    window = max(30, int(interval_seconds))
    return last_run.started_at_utc >= (now - timedelta(seconds=window))


def _get_interval_seconds():
    from app.services.protests import get_frontend_refresh_seconds

    try:
        return max(30, int(get_frontend_refresh_seconds()))
    except Exception:
        return 300


def _run_ingestion_once(app):
    from app.services.protests import get_rss_feed_urls
    from scripts.fetch_protests import run_ingestion

    feeds = get_rss_feed_urls()
    if not feeds:
        _log(app, "debug", "Protest scheduler skipped: no RSS feeds configured")
        return

    interval_seconds = _get_interval_seconds()
    if _should_skip_recent_run(app, interval_seconds):
        _log(app, "debug", "Protest scheduler skipped: recent run already executed")
        return

    def _run():
        run_ingestion(feeds)

    executed = _run_with_postgres_lock(app, _run)
    if not executed:
        _log(app, "debug", "Protest scheduler skipped: lock held by another worker")


def _scheduler_loop(app):
    _log(app, "info", "Protest scheduler thread started")

    # Initial small delay to let app boot cleanly.
    if _SCHEDULER_STOP_EVENT.wait(timeout=10):
        return

    while not _SCHEDULER_STOP_EVENT.is_set():
        interval_seconds = 300
        try:
            with app.app_context():
                interval_seconds = _get_interval_seconds()
                _run_ingestion_once(app)
        except Exception as exc:
            _log(app, "exception", f"Protest scheduler error: {exc}")

        if _SCHEDULER_STOP_EVENT.wait(timeout=max(30, int(interval_seconds))):
            break

    _log(app, "info", "Protest scheduler thread stopped")


def stop_protest_scheduler():
    _SCHEDULER_STOP_EVENT.set()


def run_protest_scheduler_forever(app):
    if app.config.get("TESTING"):
        return
    if not app.config.get("PROTEST_SCHEDULER_ENABLED", True):
        _log(app, "info", "Protest scheduler is disabled by configuration")
        return

    _SCHEDULER_STOP_EVENT.clear()
    _scheduler_loop(app)


def start_protest_scheduler(app):
    global _SCHEDULER_THREAD

    if app.config.get("TESTING"):
        return
    if not app.config.get("PROTEST_SCHEDULER_ENABLED", True):
        return

    with _SCHEDULER_THREAD_LOCK:
        if _SCHEDULER_THREAD and _SCHEDULER_THREAD.is_alive():
            return

        _SCHEDULER_STOP_EVENT.clear()
        _SCHEDULER_THREAD = threading.Thread(
            target=_scheduler_loop,
            args=(app,),
            name="protest-scheduler",
            daemon=True,
        )
        _SCHEDULER_THREAD.start()
