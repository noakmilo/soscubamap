import argparse
import json

from app import create_app
from app.services.repressors import (
    ingest_repressors_range,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Ingesta del catalogo de represores hacia base de datos local."
    )
    parser.add_argument(
        "--start-id",
        type=int,
        default=None,
        help="ID inicial (si se omite usa configuracion).",
    )
    parser.add_argument(
        "--end-id",
        type=int,
        default=None,
        help="ID final (si se omite usa configuracion).",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=100,
        help="Log de progreso cada N IDs.",
    )
    parser.add_argument(
        "--backup-json",
        type=str,
        default=None,
        help="Ruta del backup JSON final (si se omite usa configuracion).",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    app = create_app()
    with app.app_context():
        summary = ingest_repressors_range(
            start_id=args.start_id,
            end_id=args.end_id,
            backup_json_path=args.backup_json,
            progress_every=args.progress_every,
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
