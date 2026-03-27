from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.extensions import db
from app.models.prisoner import Prisoner, PrisonerRevision
from app.services.location_names import canonicalize_location_names


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def clean_decimal(value: Any) -> Decimal | None:
    text = clean_text(value)
    if not text:
        return None
    try:
        return Decimal(text)
    except Exception:
        return None


def snapshot_prisoner(
    prisoner: Prisoner,
    reason: str,
    *,
    editor_id: int | None = None,
    editor_label: str | None = None,
    payload: dict[str, Any] | None = None,
) -> PrisonerRevision:
    revision = PrisonerRevision(
        prisoner_id=prisoner.id,
        editor_id=editor_id,
        editor_label=editor_label,
        reason=reason,
        name=prisoner.name or "",
        lastname=prisoner.lastname or "",
        gender_label=prisoner.gender_label,
        detention_typology=prisoner.detention_typology,
        age_detention_label=prisoner.age_detention_label,
        age_current_label=prisoner.age_current_label,
        province_name=prisoner.province_name,
        municipality_name=prisoner.municipality_name,
        prison_name=prisoner.prison_name,
        prison_latitude=prisoner.prison_latitude,
        prison_longitude=prisoner.prison_longitude,
        prison_address=prisoner.prison_address,
        detention_date=prisoner.detention_date,
        offense_types=prisoner.offense_types,
        sentence_text=prisoner.sentence_text,
        medical_status=prisoner.medical_status,
        penal_status=prisoner.penal_status,
        observations=prisoner.observations,
        image_url=prisoner.image_url,
        payload_json=json.dumps(payload, ensure_ascii=False, sort_keys=True) if payload else None,
    )
    db.session.add(revision)
    return revision


def apply_prisoner_payload(
    prisoner: Prisoner,
    *,
    name: str,
    lastname: str | None,
    gender_label: str | None,
    detention_typology: str | None,
    age_detention_label: str | None,
    age_current_label: str | None,
    province_name: str | None,
    municipality_name: str | None,
    prison_name: str | None,
    prison_latitude: Any,
    prison_longitude: Any,
    prison_address: str | None,
    detention_date: str | None,
    offense_types: str | None,
    sentence_text: str | None,
    medical_status: str | None,
    penal_status: str | None,
    observations: str | None,
    image_url: str | None,
    source_detail_url: str | None = None,
) -> None:
    canonical_province, canonical_municipality = canonicalize_location_names(
        province_name,
        municipality_name,
    )

    prisoner.name = clean_text(name) or ""
    prisoner.lastname = clean_text(lastname) or ""
    prisoner.gender_label = clean_text(gender_label)
    prisoner.detention_typology = clean_text(detention_typology)
    prisoner.age_detention_label = clean_text(age_detention_label)
    prisoner.age_current_label = clean_text(age_current_label)
    prisoner.province_name = canonical_province
    prisoner.municipality_name = canonical_municipality
    prisoner.prison_name = clean_text(prison_name)
    prisoner.prison_latitude = clean_decimal(prison_latitude)
    prisoner.prison_longitude = clean_decimal(prison_longitude)
    prisoner.prison_address = clean_text(prison_address)
    prisoner.detention_date = clean_text(detention_date)
    prisoner.offense_types = clean_text(offense_types)
    prisoner.sentence_text = clean_text(sentence_text)
    prisoner.medical_status = clean_text(medical_status)
    prisoner.penal_status = clean_text(penal_status)
    prisoner.observations = clean_text(observations)

    normalized_image_url = clean_text(image_url)
    if normalized_image_url:
        prisoner.image_source_url = normalized_image_url
        prisoner.image_cached_url = normalized_image_url

    normalized_source_detail = clean_text(source_detail_url)
    if normalized_source_detail:
        prisoner.source_detail_url = normalized_source_detail

    now = datetime.utcnow()
    prisoner.source_updated_at = now
    prisoner.last_synced_at = now


def apply_prisoner_revision(prisoner: Prisoner, revision: PrisonerRevision) -> None:
    apply_prisoner_payload(
        prisoner,
        name=revision.name or "",
        lastname=revision.lastname,
        gender_label=revision.gender_label,
        detention_typology=revision.detention_typology,
        age_detention_label=revision.age_detention_label,
        age_current_label=revision.age_current_label,
        province_name=revision.province_name,
        municipality_name=revision.municipality_name,
        prison_name=revision.prison_name,
        prison_latitude=revision.prison_latitude,
        prison_longitude=revision.prison_longitude,
        prison_address=revision.prison_address,
        detention_date=revision.detention_date,
        offense_types=revision.offense_types,
        sentence_text=revision.sentence_text,
        medical_status=revision.medical_status,
        penal_status=revision.penal_status,
        observations=revision.observations,
        image_url=revision.image_url,
    )
