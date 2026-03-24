#!/usr/bin/env python3
"""Extrae datos de represorescubanos.com y los guarda en JSON."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_API_URL = "https://data.represorescubanos.com"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Descarga represores por ID y exporta un JSON con campos "
            "basicos, delitos y tipo de represor."
        )
    )
    parser.add_argument(
        "--start-id",
        type=int,
        default=1,
        help="ID inicial (incluyente). Por defecto: 1",
    )
    parser.add_argument(
        "--end-id",
        type=int,
        default=3000,
        help="ID final (incluyente). Por defecto: 3000",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("represores_1_3000.json"),
        help="Ruta del archivo JSON de salida.",
    )
    parser.add_argument(
        "--errors-output",
        type=Path,
        default=None,
        help="Si se define, guarda errores por ID en este archivo JSON.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=20.0,
        help="Timeout por request en segundos. Por defecto: 20",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="Cantidad de reintentos HTTP por request. Por defecto: 3",
    )
    parser.add_argument(
        "--pause-seconds",
        type=float,
        default=0.0,
        help="Pausa entre IDs para no saturar el servidor. Por defecto: 0",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=50,
        help="Muestra progreso cada N IDs procesados. Por defecto: 50",
    )
    return parser.parse_args()


def build_session(retries: int) -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=retries,
        connect=retries,
        read=retries,
        status=retries,
        backoff_factor=0.35,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(
        {
            "Accept": "application/json",
            "User-Agent": "soscubamap-represores-scraper/1.0",
        }
    )
    return session


def request_json(session: requests.Session, url: str, timeout: float) -> dict[str, Any]:
    response = session.get(url, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, dict):
        return payload
    raise ValueError(f"Respuesta JSON inesperada en {url}")


def clean_text(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    cleaned = value.strip()
    return cleaned or None


def build_image_url(image_value: Any) -> str | None:
    image_text = clean_text(image_value)
    if not image_text:
        return None
    if isinstance(image_text, str) and image_text.startswith(("http://", "https://")):
        return image_text
    return f"{BASE_API_URL}/uploads/{quote(str(image_text), safe='/%')}"


def fetch_repressor(
    session: requests.Session,
    repressor_id: int,
    timeout: float,
) -> dict[str, Any] | None:
    url = f"{BASE_API_URL}/repressor/{repressor_id}"
    payload = request_json(session, url, timeout)
    data = payload.get("data", {})
    if not isinstance(data, dict):
        return None
    rows = data.get("repressor", [])
    if not isinstance(rows, list) or not rows:
        return None
    row = rows[0]
    if not isinstance(row, dict):
        return None
    return row


def extract_name_list(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    names: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = clean_text(item.get("name"))
        if isinstance(name, str):
            names.append(name)
    return names


def fetch_repressor_crimes(
    session: requests.Session,
    repressor_id: int,
    timeout: float,
) -> list[str]:
    url = f"{BASE_API_URL}/repressor/crimes/list/{repressor_id}"
    payload = request_json(session, url, timeout)
    return extract_name_list(payload.get("data", []))


def fetch_repressor_types(
    session: requests.Session,
    repressor_id: int,
    timeout: float,
) -> list[str]:
    url = f"{BASE_API_URL}/repressor/type/{repressor_id}"
    payload = request_json(session, url, timeout)
    data = payload.get("data", {})
    if not isinstance(data, dict):
        return []
    return extract_name_list(data.get("crimes", []))


def build_output_row(
    repressor_id: int,
    row: dict[str, Any],
    crimes: list[str],
    repressor_types: list[str],
) -> dict[str, Any]:
    return {
        "ID": row.get("id", repressor_id),
        "Nombre": clean_text(row.get("name")),
        "Apellido": clean_text(row.get("lastname")),
        "Seudónimo": clean_text(row.get("nickname")),
        "Institución": clean_text(row.get("institution_name")),
        "Centro Laboral": clean_text(row.get("campus_name")),
        "Provincia": clean_text(row.get("province_name")),
        "Municipio": clean_text(row.get("municipality_name")),
        "Delitos del represor": crimes,
        "tipo de represor": repressor_types,
        "url de la imagen": build_image_url(row.get("image")),
    }


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file_obj:
        json.dump(payload, file_obj, ensure_ascii=False, indent=2)


def main() -> None:
    args = parse_args()
    if args.start_id < 1:
        raise SystemExit("--start-id debe ser >= 1")
    if args.end_id < args.start_id:
        raise SystemExit("--end-id no puede ser menor que --start-id")
    if args.progress_every < 1:
        raise SystemExit("--progress-every debe ser >= 1")

    session = build_session(args.retries)
    exported_rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    missing = 0
    start_ts = time.time()
    total = args.end_id - args.start_id + 1

    for idx, repressor_id in enumerate(range(args.start_id, args.end_id + 1), start=1):
        try:
            base_row = fetch_repressor(session, repressor_id, args.timeout)
            if base_row is None:
                missing += 1
            else:
                crimes = fetch_repressor_crimes(session, repressor_id, args.timeout)
                repressor_types = fetch_repressor_types(
                    session, repressor_id, args.timeout
                )
                exported_rows.append(
                    build_output_row(repressor_id, base_row, crimes, repressor_types)
                )
        except (requests.RequestException, ValueError, json.JSONDecodeError) as exc:
            errors.append({"id": repressor_id, "error": str(exc)})

        if args.pause_seconds > 0:
            time.sleep(args.pause_seconds)

        if idx % args.progress_every == 0 or idx == total:
            elapsed = time.time() - start_ts
            print(
                f"[{idx}/{total}] encontrados={len(exported_rows)} "
                f"vacios={missing} errores={len(errors)} "
                f"tiempo={elapsed:.1f}s"
            )

    save_json(args.output, exported_rows)
    print(f"\nJSON guardado en: {args.output}")
    print(f"Registros exportados: {len(exported_rows)}")
    print(f"IDs sin represor: {missing}")
    print(f"Errores: {len(errors)}")

    if args.errors_output:
        save_json(args.errors_output, errors)
        print(f"Errores guardados en: {args.errors_output}")


if __name__ == "__main__":
    main()
