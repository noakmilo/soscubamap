import argparse
import json
import logging
import sys

from app import create_app
from app.services.aisstream import ingest_aisstream_cuba_targets


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ejecuta manualmente una corrida AISStream con logging de progreso."
    )
    parser.add_argument("--capture-minutes", type=int, default=None)
    parser.add_argument("--max-messages", type=int, default=None)
    parser.add_argument("--progress-every", type=int, default=None)
    parser.add_argument("--idle-log-seconds", type=int, default=None)
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


def configure_console_logging(log_level: str) -> None:
    level = getattr(logging, str(log_level or "INFO").upper(), logging.INFO)
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(
            level=level,
            format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
            stream=sys.stdout,
        )
    root.setLevel(level)


def _apply_runtime_overrides(app, args: argparse.Namespace) -> dict[str, int]:
    overrides: dict[str, int] = {}
    if args.capture_minutes is not None:
        app.config["AISSTREAM_CAPTURE_MINUTES"] = int(args.capture_minutes)
        overrides["AISSTREAM_CAPTURE_MINUTES"] = int(args.capture_minutes)
    if args.max_messages is not None:
        app.config["AISSTREAM_MAX_MESSAGES_PER_RUN"] = int(args.max_messages)
        overrides["AISSTREAM_MAX_MESSAGES_PER_RUN"] = int(args.max_messages)
    if args.progress_every is not None:
        app.config["AISSTREAM_PROGRESS_LOG_EVERY"] = int(args.progress_every)
        overrides["AISSTREAM_PROGRESS_LOG_EVERY"] = int(args.progress_every)
    if args.idle_log_seconds is not None:
        app.config["AISSTREAM_IDLE_LOG_SECONDS"] = int(args.idle_log_seconds)
        overrides["AISSTREAM_IDLE_LOG_SECONDS"] = int(args.idle_log_seconds)
    return overrides


def main() -> None:
    args = parse_args()
    configure_console_logging(args.log_level)
    app = create_app()
    app.logger.setLevel(logging.getLogger().level)
    with app.app_context():
        overrides = _apply_runtime_overrides(app, args)
        if overrides:
            logging.getLogger(__name__).info("AISStream runtime overrides %s", overrides)
        summary = ingest_aisstream_cuba_targets(raise_on_error=False)
        print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
