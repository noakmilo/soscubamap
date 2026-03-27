from __future__ import annotations

from typing import Any


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def split_offense_types(raw_value: Any) -> list[str]:
    text = _clean_text(raw_value)
    if not text:
        return []

    normalized = (
        text.replace("\r", "\n")
        .replace(";", "\n")
        .replace("|", "\n")
        .replace("·", "\n")
        .replace(",", "\n")
    )
    items: list[str] = []
    seen = set()
    for line in normalized.split("\n"):
        value = _clean_text(line)
        if not value:
            continue
        lowered = value.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        items.append(value)
    return items


def serialize_prisoner(prisoner, include_source: bool = False) -> dict[str, Any]:
    offense_types = split_offense_types(prisoner.offense_types)
    payload = {
        "id": prisoner.id,
        "external_id": prisoner.external_id,
        "name": prisoner.name,
        "lastname": prisoner.lastname,
        "full_name": prisoner.full_name,
        "gender_label": prisoner.gender_label,
        "detention_typology": prisoner.detention_typology,
        "age_detention_label": prisoner.age_detention_label,
        "age_current_label": prisoner.age_current_label,
        "province_name": prisoner.province_name,
        "municipality_name": prisoner.municipality_name,
        "prison_name": prisoner.prison_name,
        "prison_latitude": float(prisoner.prison_latitude)
        if prisoner.prison_latitude is not None
        else None,
        "prison_longitude": float(prisoner.prison_longitude)
        if prisoner.prison_longitude is not None
        else None,
        "prison_address": prisoner.prison_address,
        "detention_date": prisoner.detention_date,
        "offense_types": prisoner.offense_types,
        "offense_types_list": offense_types,
        "sentence_text": prisoner.sentence_text,
        "medical_status": prisoner.medical_status,
        "penal_status": prisoner.penal_status,
        "observations": prisoner.observations,
        "image_url": prisoner.image_url,
        "image_source_url": prisoner.image_source_url,
        "image_cached_url": prisoner.image_cached_url,
        "source_detail_url": prisoner.source_detail_url,
        "source_created_at": prisoner.source_created_at.isoformat()
        if prisoner.source_created_at
        else None,
        "source_updated_at": prisoner.source_updated_at.isoformat()
        if prisoner.source_updated_at
        else None,
        "first_seen_at": prisoner.first_seen_at.isoformat() if prisoner.first_seen_at else None,
        "last_synced_at": prisoner.last_synced_at.isoformat()
        if prisoner.last_synced_at
        else None,
        "created_at": prisoner.created_at.isoformat() if prisoner.created_at else None,
        "updated_at": prisoner.updated_at.isoformat() if prisoner.updated_at else None,
    }
    if include_source:
        payload["source_payload_json"] = prisoner.source_payload_json
    return payload
