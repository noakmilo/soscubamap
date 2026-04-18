import argparse
import json
import sys
from pathlib import Path

import requests


DEFAULT_AIRPORTS_URL = "https://cdn.jsdelivr.net/npm/airports-json@1.0.0/data/airports.json"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Descarga y actualiza el catalogo local de aeropuertos desde un JSON remoto."
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_AIRPORTS_URL,
        help="URL del JSON de aeropuertos.",
    )
    parser.add_argument(
        "--output",
        default="app/static/data/aeropuertos.json",
        help="Ruta destino del archivo JSON local.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Timeout HTTP en segundos.",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=0,
        help="Indentacion JSON (0 = minificado).",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    response = requests.get(
        args.url,
        timeout=max(5, int(args.timeout or 30)),
        headers={"User-Agent": "soscubamap-airports-sync/1.0"},
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        raise RuntimeError("El JSON descargado no es una lista.")

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=(args.indent if args.indent > 0 else None)),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "status": "success",
                "url": args.url,
                "output": str(output),
                "rows": len(payload),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
