import argparse
import json
import sys
from datetime import datetime, timezone

from app import create_app
from app.services.flights import ingest_flights_cuba


def _parse_datetime_utc(raw_value: str):
    text = str(raw_value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except Exception:
        return None
    if parsed.tzinfo is None:
        return parsed
    return parsed.astimezone(timezone.utc).replace(tzinfo=None)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Ingesta de capa de vuelos hacia Cuba (FlightRadar API Explorer)."
    )
    parser.add_argument(
        "--scheduled-for",
        default="",
        help="Timestamp UTC para trazabilidad (ISO8601).",
    )
    parser.add_argument(
        "--force-backfill",
        action="store_true",
        help="Fuerza backfill inicial por la ventana FLIGHTS_BACKFILL_DAYS.",
    )
    parser.add_argument(
        "--raise-on-error",
        action="store_true",
        help="Propaga excepciones en caso de fallo.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    scheduled_for = _parse_datetime_utc(args.scheduled_for)

    app = create_app()
    with app.app_context():
        result = ingest_flights_cuba(
            scheduled_for=scheduled_for,
            force_backfill=bool(args.force_backfill),
            raise_on_error=bool(args.raise_on_error),
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))

        status = str(result.get("status") or "").strip().lower()
        if status in {"error"}:
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
