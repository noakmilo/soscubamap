import argparse
import json
import logging
import sys

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
        help=(
            "ID inicial. Si se omite: usa último ID local + 1 "
            "(o REPRESSOR_SCAN_START_ID en primera ingesta)."
        ),
    )
    parser.add_argument(
        "--end-id",
        type=int,
        default=None,
        help=(
            "ID final. Si se omite: la ingesta avanza hasta que se alcanza "
            "una racha de IDs inexistentes (modo automático incremental)."
        ),
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


def configure_console_logging() -> None:
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
            stream=sys.stdout,
        )
    root.setLevel(logging.INFO)


def main():
    args = parse_args()
    configure_console_logging()
    app = create_app()
    app.logger.setLevel(logging.INFO)
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
