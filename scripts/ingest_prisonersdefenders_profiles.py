#!/usr/bin/env python3
"""Ingesta de fichas scrapeadas de Prisoners Defenders a la tabla prisoners."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import unicodedata
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
from app.models.prisoner import Prisoner
from app.services.geo_lookup import list_provinces
from app.services.location_names import canonicalize_location_names, canonicalize_province_name
from app.services.prisoner_edits import apply_prisoner_payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingesta de JSON scrapeado de prisonersdefenders.org a tabla prisoners."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/prisonersdefenders_profiles.json"),
        help="Archivo JSON de entrada (salida de scrape_prisonersdefenders_profiles.py).",
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
        help="No espeja imágenes en Cloudinary.",
    )
    return parser.parse_args()


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def normalize_key(value: str | None) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text


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
    return parts[0], " ".join(parts[1:])


def _first_value(values: Any) -> str | None:
    if isinstance(values, list):
        for value in values:
            text = clean_text(value)
            if text:
                return text
        return None
    return clean_text(values)


def _all_values(values: Any) -> list[str]:
    if isinstance(values, list):
        out: list[str] = []
        seen = set()
        for value in values:
            text = clean_text(value)
            if not text:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(text)
        return out
    text = clean_text(values)
    return [text] if text else []


def field_first(fields: dict[str, Any], keywords: tuple[str, ...]) -> str | None:
    for key, value in fields.items():
        normalized_key = normalize_key(key)
        if any(keyword in normalized_key for keyword in keywords):
            result = _first_value(value)
            if result:
                return result
    return None


def field_all(fields: dict[str, Any], keywords: tuple[str, ...]) -> list[str]:
    collected: list[str] = []
    seen = set()
    for key, value in fields.items():
        normalized_key = normalize_key(key)
        if not any(keyword in normalized_key for keyword in keywords):
            continue
        for item in _all_values(value):
            lower = item.lower()
            if lower in seen:
                continue
            seen.add(lower)
            collected.append(item)
    return collected


def parse_prison_from_penal_status(penal_status: str | None) -> str | None:
    text = clean_text(penal_status)
    if not text:
        return None
    normalized = normalize_key(text)
    markers = ("prision:", "prision ", "prisión:", "prisión ")
    for marker in markers:
        idx = normalized.find(marker)
        if idx == -1:
            continue
        start = idx + len(marker)
        raw = text[start:].strip(" :")
        return clean_text(raw)
    return None


def parse_location_from_profile_lines(profile_lines: list[str]) -> tuple[str | None, str | None]:
    if not isinstance(profile_lines, list):
        return None, None

    province_candidates = {item.lower(): item for item in list_provinces()}
    last_line = clean_text(profile_lines[-1] if profile_lines else None)
    if not last_line:
        return None, None

    if "," in last_line:
        left, right = [clean_text(part) for part in last_line.split(",", 1)]
        province = canonicalize_province_name(right)
        if province:
            return province, left

    province = canonicalize_province_name(last_line)
    if province:
        return province, None

    lowered = last_line.lower()
    if lowered in province_candidates:
        return province_candidates[lowered], None
    return None, None


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


def _cloudinary_public_id_for_prisoner(prisoner: Prisoner) -> str:
    base = clean_text(prisoner.source_detail_url) or f"external-{prisoner.external_id}"
    digest = hashlib.sha1(base.encode("utf-8")).hexdigest()[:14]
    return f"prisoner-pd-{abs(int(prisoner.external_id))}-{digest}"


def mirror_image_to_cloudinary(prisoner: Prisoner, source_url: str | None) -> str | None:
    image_source_url = clean_text(source_url)
    if not image_source_url:
        return None
    if not _ensure_cloudinary_configured():
        return image_source_url

    try:
        result = cloudinary.uploader.upload(
            image_source_url,
            folder="soscubamap/prisoners",
            public_id=_cloudinary_public_id_for_prisoner(prisoner),
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
            "No se pudo espejar imagen a Cloudinary para prisoner external_id=%s",
            prisoner.external_id,
        )
        return image_source_url


def get_or_create_prisoner(source_url: str, external_id: int, full_name: str) -> tuple[str, Prisoner]:
    item = Prisoner.query.filter_by(source_detail_url=source_url).first()
    if item is not None:
        return "updated", item

    item = Prisoner.query.filter_by(external_id=external_id).first()
    if item is not None:
        return "updated", item

    name, lastname = split_person_name(full_name)
    if name:
        item = (
            Prisoner.query.filter(
                func.lower(Prisoner.name) == name.lower(),
                func.lower(func.coalesce(Prisoner.lastname, "")) == lastname.lower(),
            )
            .order_by(Prisoner.id.asc())
            .first()
        )
        if item is not None:
            return "updated", item

    item = Prisoner(
        external_id=external_id,
        source_detail_url=source_url,
        source_payload_json="{}",
        first_seen_at=datetime.utcnow(),
        last_synced_at=datetime.utcnow(),
    )
    db.session.add(item)
    return "stored", item


def ingest_item(item: dict[str, Any], mirror_cloudinary: bool = True) -> str:
    source_url = clean_text(item.get("source_url"))
    if not source_url:
        raise ValueError("item sin source_url")

    external_id = stable_external_id(source_url)
    full_name = clean_text(item.get("full_name")) or "Prisionero sin nombre"
    name, lastname = split_person_name(full_name)

    fields = item.get("fields") if isinstance(item.get("fields"), dict) else {}
    profile_lines = item.get("profile_lines") if isinstance(item.get("profile_lines"), list) else []
    listing_card = item.get("listing_card") if isinstance(item.get("listing_card"), dict) else {}

    gender_label = field_first(fields, ("tipologia de detencion", "tipología de detención"))
    detention_typology = gender_label or clean_text(profile_lines[1] if len(profile_lines) > 1 else None)
    age_detention_label = field_first(fields, ("edad en la detencion", "edad en la detención"))
    age_current_label = field_first(fields, ("edad actual",))
    if not age_detention_label:
        age_detention_label = clean_text(listing_card.get("age_detention_label"))

    detention_date = field_first(fields, ("fecha de detencion", "fecha de detención"))
    offense_types_list = field_all(fields, ("tipo de delito", "delito", "delitos"))
    offense_types = ", ".join(offense_types_list) if offense_types_list else None
    sentence_text = field_first(fields, ("condena",))
    medical_status = field_first(fields, ("estado medico", "estado médico"))
    penal_status = (
        field_first(fields, ("estado penal", "prision", "prisión"))
        or clean_text(listing_card.get("penal_status_label"))
    )
    observations = "\n\n".join(
        [text for text in (item.get("observations") or []) if clean_text(text)]
    ) or None

    prison_name = field_first(fields, ("prision", "prisión"))
    if not prison_name:
        prison_name = parse_prison_from_penal_status(penal_status)

    province_name = field_first(fields, ("provincia",))
    municipality_name = field_first(fields, ("municipio",))
    if not province_name and not municipality_name:
        guessed_province, guessed_municipality = parse_location_from_profile_lines(profile_lines)
        province_name = province_name or guessed_province
        municipality_name = municipality_name or guessed_municipality
    province_name, municipality_name = canonicalize_location_names(province_name, municipality_name)

    photo_url = clean_text(item.get("photo_url"))
    if not photo_url and isinstance(item.get("photo_urls"), list):
        for candidate in item.get("photo_urls"):
            value = clean_text(candidate)
            if value:
                photo_url = value
                break

    action, prisoner = get_or_create_prisoner(
        source_url=source_url,
        external_id=external_id,
        full_name=full_name,
    )

    image_url = photo_url
    if mirror_cloudinary:
        image_url = mirror_image_to_cloudinary(prisoner, image_url)

    apply_prisoner_payload(
        prisoner,
        name=name or full_name,
        lastname=lastname,
        gender_label=clean_text(listing_card.get("gender_hint")) or None,
        detention_typology=detention_typology,
        age_detention_label=age_detention_label,
        age_current_label=age_current_label,
        province_name=province_name,
        municipality_name=municipality_name,
        prison_name=prison_name,
        prison_latitude=None,
        prison_longitude=None,
        prison_address=None,
        detention_date=detention_date,
        offense_types=offense_types,
        sentence_text=sentence_text,
        medical_status=medical_status,
        penal_status=penal_status,
        observations=observations,
        image_url=image_url,
        source_detail_url=source_url,
    )

    payload = {
        "source": "prisonersdefenders_scrape",
        "full_name": full_name,
        "profile_lines": profile_lines,
        "fields": fields,
        "documents": item.get("documents") or [],
        "access_all_documents_url": item.get("access_all_documents_url"),
        "listing_card": listing_card,
        "raw": item,
    }
    prisoner.source_payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    now = datetime.utcnow()
    if prisoner.source_created_at is None:
        prisoner.source_created_at = now
    prisoner.source_updated_at = now
    prisoner.last_synced_at = now

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
    raise ValueError("JSON inválido: usa lista o {'items': [...]}")


def main() -> None:
    args = parse_args()
    if not args.input.exists():
        raise SystemExit(f"No existe archivo de entrada: {args.input}")

    app = create_app()
    with app.app_context():
        items = load_items(args.input)
        total = len(items)
        if total == 0:
            print("No hay items para ingestar.")
            return

        stored = 0
        updated = 0
        failed = 0

        for idx, item in enumerate(items, start=1):
            try:
                action = ingest_item(item, mirror_cloudinary=not args.no_cloudinary)
            except Exception as exc:
                failed += 1
                db.session.rollback()
                current_app.logger.exception("Error ingestando item %s", idx)
                print(f"[{idx}/{total}] ERROR: {exc}")
                continue

            if action == "stored":
                stored += 1
            else:
                updated += 1

            if args.progress_every > 0 and idx % args.progress_every == 0:
                print(
                    f"[{idx}/{total}] stored={stored} updated={updated} failed={failed}"
                )

        if args.dry_run:
            db.session.rollback()
            print("Dry-run: rollback aplicado, sin cambios persistidos.")
        else:
            db.session.commit()
            print("Commit aplicado.")

        print(
            f"Finalizado: total={total} stored={stored} updated={updated} failed={failed}"
        )


if __name__ == "__main__":
    main()
