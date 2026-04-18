import argparse
import json
import sys

from app import create_app
from app.extensions import db
from app.services.flights import (
    backfill_flights_airport_metadata_from_static_catalog,
    refresh_flight_layer_snapshots,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Backfill manual de metadatos de aeropuertos para vuelos ya guardados, "
            "usando app/static/data/aeropuertos.json."
        )
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limita la cantidad de eventos FlightEvent a procesar (0 = sin limite).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula cambios sin persistir en base de datos.",
    )
    parser.add_argument(
        "--include-complete",
        action="store_true",
        help="Tambien actualiza registros que ya tienen datos (por defecto: solo faltantes).",
    )
    parser.add_argument(
        "--commit-every",
        type=int,
        default=300,
        help="Cantidad de cambios entre commits parciales.",
    )
    parser.add_argument(
        "--no-refresh-snapshots",
        action="store_true",
        help="No recalcula snapshots 7d/24h/6h/2h al terminar.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    app = create_app()

    with app.app_context():
        result = backfill_flights_airport_metadata_from_static_catalog(
            limit=(args.limit or None),
            dry_run=bool(args.dry_run),
            only_missing=not bool(args.include_complete),
            commit_every=args.commit_every,
        )
        if (not args.dry_run) and (not args.no_refresh_snapshots):
            snapshots = refresh_flight_layer_snapshots()
            db.session.commit()
            result["snapshots_refreshed"] = {
                str(hours): int(snapshot.points_count or 0)
                for hours, snapshot in snapshots.items()
            }
        print(json.dumps(result, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
