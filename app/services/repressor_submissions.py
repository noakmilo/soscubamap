import json
from datetime import datetime
from typing import Iterable

from sqlalchemy import func

from app.extensions import db
from app.models.repressor import (
    Repressor,
    RepressorCrime,
    RepressorSubmission,
    RepressorType,
)
from app.services.location_names import canonicalize_location_names

REPRESSOR_TYPE_OPTIONS = [
    {
        "name": "Bata Blanca",
        "description": (
            "Funcionarios que coordinan desde Cuba o en el exterior el tráfico "
            "internacional de médicos cubanos. Incluye quienes organizan, controlan, "
            "vigilan y reprimen al personal de misiones y brigadas médicas para imponer "
            "condiciones de trabajo forzado."
        ),
    },
    {
        "name": "Exportación",
        "description": (
            "Represores enviados al extranjero para organizar, asesorar o participar en "
            "la represión en países aliados del gobierno de Cuba. También diplomáticos u "
            "otros representantes que difunden propaganda oficial y tergiversan la "
            "realidad cubana."
        ),
    },
    {
        "name": "Económico",
        "description": (
            "Inspectores, policías, investigadores, jueces y funcionarios de supervisión "
            "que persiguen al pequeño sector privado urbano/agrario y a actores del "
            "mercado informal en la isla."
        ),
    },
    {
        "name": "Cuello Blanco",
        "description": (
            "Funcionarios que usan su autoridad para implementar medidas represivas por "
            "razones políticas u otras intolerancias, incluyendo expulsiones de centros "
            "de trabajo y estudio."
        ),
    },
    {
        "name": "Violento",
        "description": (
            "Personas que protagonizan actos de violencia política por iniciativa propia "
            "o por órdenes superiores, incitan a la violencia desde cargos públicos, o "
            "participan en la organización y ejecución de turbas."
        ),
    },
]


def get_repressor_type_options() -> list[dict[str, str]]:
    return [dict(item) for item in REPRESSOR_TYPE_OPTIONS]


def get_repressor_type_names() -> set[str]:
    return {item["name"] for item in REPRESSOR_TYPE_OPTIONS}


def list_existing_repressor_crime_names() -> list[str]:
    rows = (
        db.session.query(RepressorCrime.name)
        .filter(
            RepressorCrime.name.isnot(None),
            RepressorCrime.name != "",
        )
        .distinct()
        .order_by(RepressorCrime.name.asc())
        .all()
    )
    names: list[str] = []
    for row in rows:
        value = str(row[0] or "").strip()
        if value:
            names.append(value)
    return names


def normalize_list_items(values: Iterable[str]) -> list[str]:
    items: list[str] = []
    seen = set()
    for raw in values:
        value = str(raw or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        items.append(value)
    return items


def parse_custom_crimes(custom_crimes_text: str) -> list[str]:
    raw_items = custom_crimes_text.replace("\r", "\n").replace(";", "\n").replace(",", "\n")
    return normalize_list_items(raw_items.split("\n"))


def _next_manual_external_id() -> int:
    min_value = db.session.query(func.min(Repressor.external_id)).scalar()
    try:
        min_id = int(min_value)
    except Exception:
        min_id = 0
    if min_id >= 0:
        return -1
    return min_id - 1


def _sync_repressor_crimes(repressor: Repressor, crime_names: list[str]) -> None:
    current = {item.name: item for item in repressor.crimes}
    incoming = set(crime_names)
    for name in crime_names:
        if name in current:
            continue
        repressor.crimes.append(RepressorCrime(name=name))
    for name, item in current.items():
        if name not in incoming:
            db.session.delete(item)


def _sync_repressor_types(repressor: Repressor, type_names: list[str]) -> None:
    current = {item.name: item for item in repressor.types}
    incoming = set(type_names)
    for name in type_names:
        if name in current:
            continue
        repressor.types.append(RepressorType(name=name))
    for name, item in current.items():
        if name not in incoming:
            db.session.delete(item)


def materialize_repressor_submission(
    submission: RepressorSubmission,
    reviewer_id: int | None = None,
) -> Repressor:
    now = datetime.utcnow()
    repressor = None
    if submission.repressor_id:
        repressor = Repressor.query.get(submission.repressor_id)
    if repressor is None:
        repressor = Repressor(
            external_id=_next_manual_external_id(),
            first_seen_at=now,
        )
        db.session.add(repressor)

    province_name, municipality_name = canonicalize_location_names(
        submission.province_name,
        submission.municipality_name,
    )

    repressor.name = submission.name or ""
    repressor.lastname = submission.lastname or ""
    repressor.nickname = submission.nickname or None
    repressor.institution_name = submission.institution_name or None
    repressor.campus_name = submission.campus_name or None
    repressor.province_name = province_name
    repressor.municipality_name = municipality_name
    repressor.testimony = submission.testimony or None
    repressor.image_source_url = submission.photo_url
    repressor.image_cached_url = submission.photo_url
    repressor.source_detail_url = None
    repressor.source_created_at = submission.created_at
    repressor.source_updated_at = now
    repressor.source_status = 1
    repressor.source_is_identifies = "manual_submission"
    repressor.source_payload_json = json.dumps(
        {
            "submission_id": submission.id,
            "note": submission.note,
            "testimony": submission.testimony,
            "payload_json": submission.payload_json,
            "submitted_by_user_id": submission.submitter_id,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    repressor.last_synced_at = now

    _sync_repressor_crimes(repressor, submission.crimes_list)
    _sync_repressor_types(repressor, submission.types_list)

    submission.repressor = repressor
    submission.status = "approved"
    submission.reviewed_at = now
    submission.reviewer_id = reviewer_id
    submission.rejection_reason = None

    return repressor
