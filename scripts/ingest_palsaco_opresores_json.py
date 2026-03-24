#!/usr/bin/env python3
"""Ingest palsaco scraped JSON into local Repressor tables."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import create_app
from app.extensions import db
from app.models.repressor import Repressor, RepressorCrime, RepressorType
from app.services.location_names import canonicalize_location_names


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingesta de JSON scrapeado de palsaco.com a tabla repressors."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("palsaco_opresores_scrape.json"),
        help="Archivo JSON generado por scrape_palsaco_opresores.py",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=50,
        help="Log de progreso cada N items.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="No hace commit en base de datos.",
    )
    return parser.parse_args()


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def stable_external_id(source_url: str) -> int:
    digest = hashlib.sha1(source_url.encode("utf-8")).hexdigest()
    numeric = int(digest[:12], 16)
    return -((numeric % 2_000_000_000) + 1)


def split_person_name(full_name: str | None) -> tuple[str, str]:
    text = clean_text(full_name)
    if not text:
        return "", ""
    parts = text.split()
    if len(parts) == 1:
        return parts[0], ""
    return " ".join(parts[:-1]), parts[-1]


def normalize_display_name(text: str | None) -> str | None:
    value = clean_text(text)
    if not value:
        return None
    if ":" in value:
        left, right = value.split(":", 1)
        if "opresor" in left.lower() and clean_text(right):
            return clean_text(right)
    return value


def normalize_list(values: list[str]) -> list[str]:
    out: list[str] = []
    seen = set()
    for raw in values:
        value = clean_text(raw)
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def split_multi_values(raw: str | None) -> list[str]:
    text = clean_text(raw)
    if not text:
        return []
    chunk = (
        text.replace("\r", "\n")
        .replace(";", "\n")
        .replace(",", "\n")
        .replace(" / ", "\n")
        .replace("|", "\n")
    )
    return normalize_list(chunk.split("\n"))


def extract_field_value(fields: dict[str, str], keywords: tuple[str, ...]) -> str | None:
    for key, value in fields.items():
        lowered = key.lower()
        if any(keyword in lowered for keyword in keywords):
            return clean_text(value)
    return None


def extract_field_values(fields: dict[str, str], keywords: tuple[str, ...]) -> list[str]:
    collected: list[str] = []
    for key, value in fields.items():
        lowered = key.lower()
        if any(keyword in lowered for keyword in keywords):
            collected.extend(split_multi_values(value))
    return normalize_list(collected)


def sync_crimes(repressor: Repressor, crime_names: list[str]) -> None:
    if not crime_names:
        return
    current = {item.name: item for item in repressor.crimes}
    incoming = set(crime_names)
    for name in crime_names:
        if name in current:
            continue
        repressor.crimes.append(RepressorCrime(name=name))
    for name, obj in current.items():
        if name not in incoming:
            db.session.delete(obj)


def sync_types(repressor: Repressor, type_names: list[str]) -> None:
    if not type_names:
        return
    current = {item.name: item for item in repressor.types}
    incoming = set(type_names)
    for name in type_names:
        if name in current:
            continue
        repressor.types.append(RepressorType(name=name))
    for name, obj in current.items():
        if name not in incoming:
            db.session.delete(obj)


def get_or_create_repressor(source_url: str) -> tuple[str, Repressor]:
    item = Repressor.query.filter_by(source_detail_url=source_url).first()
    if item is not None:
        return "updated", item

    external_id = stable_external_id(source_url)
    item = Repressor.query.filter_by(external_id=external_id).first()
    if item is not None:
        return "updated", item

    item = Repressor(
        external_id=external_id,
        first_seen_at=datetime.utcnow(),
        source_detail_url=source_url,
    )
    db.session.add(item)
    return "stored", item


def ingest_item(item: dict[str, Any]) -> str:
    source_url = (
        clean_text(item.get("canonical_url"))
        or clean_text(item.get("source_url"))
        or clean_text(item.get("source_detail_url"))
    )
    if not source_url:
        raise ValueError("item sin source_url/canonical_url")

    action, repressor = get_or_create_repressor(source_url)
    source_payload = item.get("source_payload") if isinstance(item.get("source_payload"), dict) else {}
    fields_raw = item.get("fields") if isinstance(item.get("fields"), dict) else {}
    if not fields_raw and isinstance(source_payload.get("fields"), dict):
        fields_raw = source_payload.get("fields")
    fields = {str(k): str(v) for k, v in fields_raw.items()}

    display_name = normalize_display_name(item.get("name")) or extract_field_value(
        fields,
        ("nombre", "name"),
    )
    name, lastname = split_person_name(display_name)
    alias = clean_text(item.get("nickname")) or extract_field_value(
        fields,
        ("alias", "seudonimo", "apodo", "nick"),
    )
    institution = extract_field_value(
        fields,
        ("institucion", "ministerio", "organizacion", "entidad"),
    ) or clean_text(item.get("institution_name"))
    campus = extract_field_value(fields, ("centro laboral", "unidad", "laboral")) or clean_text(
        item.get("campus_name")
    )
    province = extract_field_value(fields, ("provincia",)) or clean_text(item.get("province_name"))
    municipality = extract_field_value(fields, ("municipio",)) or clean_text(
        item.get("municipality_name")
    )
    canonical_province, canonical_municipality = canonicalize_location_names(
        province,
        municipality,
    )

    crimes = extract_field_values(fields, ("delito", "cargo", "acusacion", "acusación"))
    if not crimes and isinstance(item.get("crimes"), list):
        crimes = normalize_list([str(value) for value in item.get("crimes", [])])
    types = extract_field_values(fields, ("tipo", "clasificacion", "categoria", "categoría"))
    if not types and isinstance(item.get("types"), list):
        types = normalize_list([str(value) for value in item.get("types", [])])

    image_url = (
        clean_text(item.get("image_url"))
        or clean_text(item.get("image_source_url"))
        or clean_text(item.get("image_cached_url"))
    )
    summary = clean_text(item.get("summary")) or clean_text(source_payload.get("summary"))
    testimony = (
        clean_text(item.get("testimony"))
        or clean_text(source_payload.get("testimony"))
        or extract_field_value(fields, ("testimonio",))
    )

    repressor.name = name or (clean_text(display_name) or clean_text(item.get("name")) or "N/D")
    repressor.lastname = lastname or (clean_text(item.get("lastname")) or "")
    repressor.nickname = alias
    repressor.institution_name = institution
    repressor.campus_name = campus
    repressor.province_name = canonical_province
    repressor.municipality_name = canonical_municipality
    repressor.testimony = testimony
    repressor.image_source_url = image_url
    repressor.image_cached_url = image_url
    repressor.source_detail_url = source_url
    repressor.source_status = 1
    repressor.source_is_identifies = "palsaco_scrape"
    repressor.source_payload_json = json.dumps(
        {
            "source": "palsaco_scrape",
            "summary": summary,
            "testimony": testimony,
            "fields": fields,
            "image_urls": item.get("image_urls") or [],
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    repressor.source_updated_at = datetime.utcnow()
    repressor.last_synced_at = datetime.utcnow()

    sync_crimes(repressor, crimes)
    sync_types(repressor, types)
    return action


def load_items(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as file_obj:
        payload = json.load(file_obj)
    if isinstance(payload, dict):
        items = payload.get("items")
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    raise ValueError("JSON no tiene formato valido (lista o {'items': [...]})")


def main() -> None:
    args = parse_args()
    if not args.input.exists():
        raise SystemExit(f"No existe archivo de entrada: {args.input}")

    app = create_app()
    with app.app_context():
        rows = load_items(args.input)
        counters = {"stored": 0, "updated": 0, "errors": 0}
        errors: list[dict[str, Any]] = []

        for idx, row in enumerate(rows, start=1):
            try:
                action = ingest_item(row)
                counters[action] += 1
            except Exception as exc:
                db.session.rollback()
                counters["errors"] += 1
                errors.append(
                    {
                        "index": idx,
                        "source_url": row.get("source_url"),
                        "error": str(exc),
                    }
                )

            if idx % args.progress_every == 0 or idx == len(rows):
                print(
                    f"[{idx}/{len(rows)}] stored={counters['stored']} "
                    f"updated={counters['updated']} errors={counters['errors']}"
                )

        if args.dry_run:
            db.session.rollback()
            print("Dry-run: cambios revertidos (rollback).")
        else:
            db.session.commit()

        summary = {
            "input": str(args.input),
            "total_rows": len(rows),
            "stored": counters["stored"],
            "updated": counters["updated"],
            "errors": counters["errors"],
            "errors_sample": errors[:50],
            "dry_run": bool(args.dry_run),
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
