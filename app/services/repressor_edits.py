import json
from datetime import datetime
from typing import Any

from app.extensions import db
from app.models.repressor import (
    REPRESSOR_VERIFY_LOCK_COUNT,
    Repressor,
    RepressorCrime,
    RepressorEditRequest,
    RepressorRevision,
    RepressorType,
)
from app.services.location_names import canonicalize_location_names


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def normalize_list_items(values: list[str]) -> list[str]:
    items: list[str] = []
    seen = set()
    for raw in values:
        value = str(raw or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        items.append(value)
    return items


def sync_repressor_crimes(repressor: Repressor, crime_names: list[str]) -> None:
    current = {item.name: item for item in repressor.crimes}
    incoming = set(crime_names)
    for name in crime_names:
        if name in current:
            continue
        repressor.crimes.append(RepressorCrime(name=name))
    for name, item in current.items():
        if name not in incoming:
            db.session.delete(item)


def sync_repressor_types(repressor: Repressor, type_names: list[str]) -> None:
    current = {item.name: item for item in repressor.types}
    incoming = set(type_names)
    for name in type_names:
        if name in current:
            continue
        repressor.types.append(RepressorType(name=name))
    for name, item in current.items():
        if name not in incoming:
            db.session.delete(item)


def snapshot_repressor(
    repressor: Repressor,
    reason: str,
    *,
    editor_id: int | None = None,
    editor_label: str | None = None,
    payload: dict[str, Any] | None = None,
) -> RepressorRevision:
    revision = RepressorRevision(
        repressor_id=repressor.id,
        editor_id=editor_id,
        editor_label=editor_label,
        reason=reason,
        name=repressor.name or "",
        lastname=repressor.lastname or "",
        nickname=repressor.nickname or None,
        institution_name=repressor.institution_name or None,
        campus_name=repressor.campus_name or None,
        province_name=repressor.province_name or None,
        municipality_name=repressor.municipality_name or None,
        testimony=repressor.testimony or None,
        image_url=repressor.image_url,
        crimes_json=json.dumps(
            [item.name for item in repressor.crimes],
            ensure_ascii=False,
        ),
        types_json=json.dumps(
            [item.name for item in repressor.types],
            ensure_ascii=False,
        ),
        payload_json=json.dumps(payload, ensure_ascii=False, sort_keys=True) if payload else None,
    )
    db.session.add(revision)
    return revision


def _apply_payload(
    repressor: Repressor,
    *,
    name: str,
    lastname: str | None,
    nickname: str | None,
    institution_name: str | None,
    campus_name: str | None,
    province_name: str | None,
    municipality_name: str | None,
    testimony: str | None,
    image_url: str | None,
    crimes: list[str],
    types: list[str],
) -> None:
    canonical_province, canonical_municipality = canonicalize_location_names(
        province_name,
        municipality_name,
    )

    repressor.name = clean_text(name) or ""
    repressor.lastname = clean_text(lastname) or ""
    repressor.nickname = clean_text(nickname)
    repressor.institution_name = clean_text(institution_name)
    repressor.campus_name = clean_text(campus_name)
    repressor.province_name = canonical_province
    repressor.municipality_name = canonical_municipality
    repressor.testimony = clean_text(testimony)

    normalized_image_url = clean_text(image_url)
    if normalized_image_url:
        repressor.image_source_url = normalized_image_url
        repressor.image_cached_url = normalized_image_url

    sync_repressor_crimes(repressor, normalize_list_items(crimes))
    sync_repressor_types(repressor, normalize_list_items(types))

    now = datetime.utcnow()
    repressor.source_updated_at = now
    repressor.last_synced_at = now


def apply_repressor_edit_request(
    repressor: Repressor,
    edit_request: RepressorEditRequest,
) -> None:
    if (repressor.verify_count or 0) >= REPRESSOR_VERIFY_LOCK_COUNT:
        raise ValueError(
            "La ficha alcanzó 10 verificaciones y ya no puede editarse en la plataforma."
        )
    _apply_payload(
        repressor,
        name=edit_request.name or "",
        lastname=edit_request.lastname,
        nickname=edit_request.nickname,
        institution_name=edit_request.institution_name,
        campus_name=edit_request.campus_name,
        province_name=edit_request.province_name,
        municipality_name=edit_request.municipality_name,
        testimony=edit_request.testimony,
        image_url=edit_request.image_url,
        crimes=edit_request.crimes_list,
        types=edit_request.types_list,
    )


def apply_repressor_revision(
    repressor: Repressor,
    revision: RepressorRevision,
) -> None:
    if (repressor.verify_count or 0) >= REPRESSOR_VERIFY_LOCK_COUNT:
        raise ValueError(
            "La ficha alcanzó 10 verificaciones y ya no puede editarse en la plataforma."
        )
    _apply_payload(
        repressor,
        name=revision.name or "",
        lastname=revision.lastname,
        nickname=revision.nickname,
        institution_name=revision.institution_name,
        campus_name=revision.campus_name,
        province_name=revision.province_name,
        municipality_name=revision.municipality_name,
        testimony=revision.testimony,
        image_url=revision.image_url,
        crimes=revision.crimes_list,
        types=revision.types_list,
    )
