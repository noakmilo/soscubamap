import json
import logging
import sys

from app import create_app
from app.services.aisstream import ingest_aisstream_cuba_targets


def configure_console_logging() -> None:
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
            stream=sys.stdout,
        )
    root.setLevel(logging.INFO)


def main() -> None:
    configure_console_logging()
    app = create_app()
    app.logger.setLevel(logging.INFO)
    with app.app_context():
        summary = ingest_aisstream_cuba_targets(raise_on_error=False)
        print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
