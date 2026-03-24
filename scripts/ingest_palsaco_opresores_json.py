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

import cloudinary
import cloudinary.uploader
from flask import current_app
from sqlalchemy import func

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
        default=Path("data/palsaco_opresores_catalog_ready.json"),
        help="Archivo JSON final del catálogo listo para ingesta.",
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
    parser.add_argument(
        "--no-cloudinary",
        action="store_true",
        help="No espeja imágenes en Cloudinary (solo guarda URL origen).",
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


def _cloudinary_is_configured() -> bool:
    return bool(
        clean_text(current_app.config.get("CLOUDINARY_CLOUD_NAME"))
        and clean_text(current_app.config.get("CLOUDINARY_API_KEY"))
        and clean_text(current_app.config.get("CLOUDINARY_API_SECRET"))
    )


def _ensure_cloudinary_configured() -> bool:
    if not _cloudinary_is_configured():
        return False
    cloudinary.config(
        cloud_name=current_app.config.get("CLOUDINARY_CLOUD_NAME"),
        api_key=current_app.config.get("CLOUDINARY_API_KEY"),
        api_secret=current_app.config.get("CLOUDINARY_API_SECRET"),
        secure=True,
    )
    return True


def _is_cloudinary_url(url: str | None) -> bool:
    value = clean_text(url)
    if not value:
        return False
    return "res.cloudinary.com" in value


def _cloudinary_public_id_for_repressor(repressor: Repressor) -> str:
    base = clean_text(repressor.source_detail_url) or f"external-{repressor.external_id}"
    digest = hashlib.sha1(base.encode("utf-8")).hexdigest()[:14]
    return f"repressor-palsaco-{abs(int(repressor.external_id))}-{digest}"


def mirror_image_to_cloudinary(repressor: Repressor, source_url: str | None) -> str | None:
    image_source_url = clean_text(source_url)
    if not image_source_url:
        return None
    if not _ensure_cloudinary_configured():
        return image_source_url

    try:
        result = cloudinary.uploader.upload(
            image_source_url,
            folder="soscubamap/repressors",
            public_id=_cloudinary_public_id_for_repressor(repressor),
            overwrite=True,
            resource_type="image",
        )
        return (
            clean_text(result.get("secure_url"))
            or clean_text(result.get("url"))
            or image_source_url
        )
    except Exception:
        current_app.logger.exception(
            "No se pudo espejar imagen a Cloudinary para repressor external_id=%s",
            repressor.external_id,
        )
        return image_source_url


def get_or_create_repressor(
    source_url: str,
    canonical_name: str,
    canonical_lastname: str,
    canonical_province: str | None,
) -> tuple[str, Repressor]:
    item = Repressor.query.filter_by(source_detail_url=source_url).first()
    if item is not None:
        return "updated", item

    external_id = stable_external_id(source_url)
    item = Repressor.query.filter_by(external_id=external_id).first()
    if item is not None:
        return "updated", item

    if canonical_name and canonical_lastname and canonical_province:
        item = (
            Repressor.query.filter(
                func.lower(Repressor.name) == canonical_name.lower(),
                func.lower(Repressor.lastname) == canonical_lastname.lower(),
                func.lower(func.coalesce(Repressor.province_name, "")) == canonical_province.lower(),
            )
            .order_by(Repressor.id.asc())
            .first()
        )
        if item is not None:
            return "updated", item

    item = Repressor(
        external_id=external_id,
        first_seen_at=datetime.utcnow(),
        source_detail_url=source_url,
    )
    db.session.add(item)
    return "stored", item


def ingest_item(item: dict[str, Any], mirror_cloudinary: bool = True) -> str:
    source_url = (
        clean_text(item.get("canonical_url"))
        or clean_text(item.get("source_url"))
        or clean_text(item.get("source_detail_url"))
    )
    if not source_url:
        raise ValueError("item sin source_url/canonical_url")

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
    canonical_name = name or (clean_text(display_name) or clean_text(item.get("name")) or "N/D")
    canonical_lastname = lastname or (clean_text(item.get("lastname")) or "")

    action, repressor = get_or_create_repressor(
        source_url=source_url,
        canonical_name=canonical_name,
        canonical_lastname=canonical_lastname,
        canonical_province=canonical_province,
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

    repressor.name = canonical_name
    repressor.lastname = canonical_lastname
    repressor.nickname = alias
    repressor.institution_name = institution
    repressor.campus_name = campus
    repressor.province_name = canonical_province
    repressor.municipality_name = canonical_municipality
    repressor.testimony = testimony
    repressor.image_source_url = image_url
    if mirror_cloudinary:
        repressor.image_cached_url = mirror_image_to_cloudinary(repressor, image_url)
    else:
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

        mirror_cloudinary = not args.no_cloudinary
        if mirror_cloudinary and not _cloudinary_is_configured():
            print(
                "Aviso: Cloudinary no configurado; se guardará URL original en image_cached_url."
            )
        for idx, row in enumerate(rows, start=1):
            try:
                action = ingest_item(row, mirror_cloudinary=mirror_cloudinary)
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
