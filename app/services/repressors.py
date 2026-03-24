import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import cloudinary
import cloudinary.uploader
import requests
from flask import current_app
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.extensions import db
from app.models.repressor import (
    Repressor,
    RepressorCrime,
    RepressorIngestionRun,
    RepressorType,
)


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_source_datetime(raw_value: Any) -> datetime | None:
    text = _clean_text(raw_value)
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except Exception:
        return None


def _safe_int(raw_value: Any, default: int) -> int:
    try:
        return int(raw_value)
    except Exception:
        return default


def _safe_float(raw_value: Any, default: float) -> float:
    try:
        return float(raw_value)
    except Exception:
        return default


def get_api_base_url() -> str:
    value = _clean_text(current_app.config.get("REPRESSOR_API_BASE_URL"))
    return value or "https://data.represorescubanos.com"


def get_public_base_url() -> str:
    value = _clean_text(current_app.config.get("REPRESSOR_PUBLIC_BASE_URL"))
    return value or "https://represorescubanos.com/repressor-detail"


def get_fetch_timeout_seconds() -> float:
    return max(_safe_float(current_app.config.get("REPRESSOR_FETCH_TIMEOUT_SECONDS"), 20.0), 5.0)


def get_fetch_retries() -> int:
    return max(_safe_int(current_app.config.get("REPRESSOR_FETCH_RETRIES"), 3), 0)


def get_fetch_pause_seconds() -> float:
    return max(_safe_float(current_app.config.get("REPRESSOR_FETCH_PAUSE_SECONDS"), 0.0), 0.0)


def get_scan_start_id() -> int:
    return max(_safe_int(current_app.config.get("REPRESSOR_SCAN_START_ID"), 1), 1)


def get_scan_end_id() -> int:
    end_id = _safe_int(current_app.config.get("REPRESSOR_SCAN_END_ID"), 3000)
    return max(end_id, get_scan_start_id())


def get_ingestion_interval_seconds() -> int:
    raw = _safe_int(current_app.config.get("REPRESSOR_INGESTION_INTERVAL_SECONDS"), 86400)
    return max(raw, 3600)


def get_backup_json_path() -> str:
    value = _clean_text(current_app.config.get("REPRESSOR_BACKUP_JSON_PATH"))
    return value or "data/repressors_backup_latest.json"


def _build_http_session() -> requests.Session:
    retries = get_fetch_retries()
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
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(
        {
            "Accept": "application/json",
            "User-Agent": "soscubamap-repressor-ingestor/1.0",
        }
    )
    return session


def _request_json(session: requests.Session, url: str, timeout_seconds: float) -> dict[str, Any]:
    response = session.get(url, timeout=timeout_seconds)
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, dict):
        return payload
    raise ValueError(f"Respuesta JSON inesperada: {url}")


def _extract_repressor_row(payload: dict[str, Any]) -> dict[str, Any] | None:
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


def _extract_named_items(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    result: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = _clean_text(item.get("name"))
        if not name:
            continue
        result.append(
            {
                "id": _safe_int(item.get("id"), 0) or None,
                "name": name,
            }
        )
    return result


def _build_source_image_url(image_raw: Any) -> str | None:
    image_text = _clean_text(image_raw)
    if not image_text:
        return None
    if image_text.startswith(("http://", "https://")):
        return image_text
    return f"{get_api_base_url()}/uploads/{quote(image_text, safe='/%')}"


def _build_detail_url(external_id: int) -> str:
    return f"{get_public_base_url().rstrip('/')}/{external_id}"


def _cloudinary_is_configured() -> bool:
    return bool(
        _clean_text(current_app.config.get("CLOUDINARY_CLOUD_NAME"))
        and _clean_text(current_app.config.get("CLOUDINARY_API_KEY"))
        and _clean_text(current_app.config.get("CLOUDINARY_API_SECRET"))
    )


def _cache_image_url(source_url: str | None, external_id: int) -> str | None:
    if not source_url:
        return None
    if not _cloudinary_is_configured():
        return source_url

    cloudinary.config(
        cloud_name=current_app.config.get("CLOUDINARY_CLOUD_NAME"),
        api_key=current_app.config.get("CLOUDINARY_API_KEY"),
        api_secret=current_app.config.get("CLOUDINARY_API_SECRET"),
        secure=True,
    )
    public_id = f"repressor-{external_id}"
    try:
        result = cloudinary.uploader.upload(
            source_url,
            folder="soscubamap/repressors",
            public_id=public_id,
            overwrite=True,
            resource_type="image",
        )
        return result.get("secure_url") or result.get("url") or source_url
    except Exception:
        current_app.logger.exception(
            "No se pudo cachear imagen de represor ext_id=%s",
            external_id,
        )
        return source_url


def _sync_repressor_children(
    repressor: Repressor,
    crimes: list[dict[str, Any]],
    types: list[dict[str, Any]],
) -> bool:
    changed = False

    current_crimes = {item.name: item for item in repressor.crimes}
    incoming_crime_names = {item["name"] for item in crimes}
    for item in crimes:
        obj = current_crimes.get(item["name"])
        if obj is None:
            repressor.crimes.append(
                RepressorCrime(
                    name=item["name"],
                    source_crime_id=item.get("id"),
                )
            )
            changed = True
            continue
        if obj.source_crime_id != item.get("id"):
            obj.source_crime_id = item.get("id")
            changed = True
    for name, obj in current_crimes.items():
        if name not in incoming_crime_names:
            db.session.delete(obj)
            changed = True

    current_types = {item.name: item for item in repressor.types}
    incoming_type_names = {item["name"] for item in types}
    for item in types:
        obj = current_types.get(item["name"])
        if obj is None:
            repressor.types.append(
                RepressorType(
                    name=item["name"],
                    source_type_id=item.get("id"),
                )
            )
            changed = True
            continue
        if obj.source_type_id != item.get("id"):
            obj.source_type_id = item.get("id")
            changed = True
    for name, obj in current_types.items():
        if name not in incoming_type_names:
            db.session.delete(obj)
            changed = True

    return changed


def _set_field(model_obj: Any, field_name: str, value: Any) -> bool:
    if getattr(model_obj, field_name) != value:
        setattr(model_obj, field_name, value)
        return True
    return False


def _upsert_repressor(
    external_id: int,
    base_row: dict[str, Any],
    crimes: list[dict[str, Any]],
    types: list[dict[str, Any]],
) -> tuple[str, Repressor]:
    repressor = Repressor.query.filter_by(external_id=external_id).first()
    action = "stored"
    now = datetime.utcnow()

    if repressor is None:
        repressor = Repressor(external_id=external_id, first_seen_at=now)
        db.session.add(repressor)
    else:
        action = "unchanged"

    source_image_url = _build_source_image_url(base_row.get("image"))
    image_changed = source_image_url != repressor.image_source_url
    desired_cached_image = repressor.image_cached_url
    if image_changed or not desired_cached_image:
        desired_cached_image = _cache_image_url(source_image_url, external_id)

    changed = False
    changed |= _set_field(repressor, "name", _clean_text(base_row.get("name")) or "")
    changed |= _set_field(repressor, "lastname", _clean_text(base_row.get("lastname")) or "")
    changed |= _set_field(repressor, "nickname", _clean_text(base_row.get("nickname")))
    changed |= _set_field(
        repressor,
        "institution_name",
        _clean_text(base_row.get("institution_name")),
    )
    changed |= _set_field(repressor, "campus_name", _clean_text(base_row.get("campus_name")))
    changed |= _set_field(repressor, "province_name", _clean_text(base_row.get("province_name")))
    changed |= _set_field(
        repressor,
        "municipality_name",
        _clean_text(base_row.get("municipality_name")),
    )
    changed |= _set_field(repressor, "country_name", _clean_text(base_row.get("country_name")))
    changed |= _set_field(repressor, "image_source_url", source_image_url)
    changed |= _set_field(repressor, "image_cached_url", desired_cached_image)
    changed |= _set_field(repressor, "source_detail_url", _build_detail_url(external_id))
    changed |= _set_field(
        repressor,
        "source_created_at",
        _parse_source_datetime(base_row.get("created_at")),
    )
    changed |= _set_field(
        repressor,
        "source_updated_at",
        _parse_source_datetime(base_row.get("updated_at")),
    )
    changed |= _set_field(repressor, "source_status", _safe_int(base_row.get("status"), 0))
    changed |= _set_field(
        repressor,
        "source_is_identifies",
        _clean_text(base_row.get("is_identifies")),
    )
    changed |= _set_field(
        repressor,
        "source_payload_json",
        json.dumps(base_row, ensure_ascii=False, sort_keys=True),
    )
    changed |= _set_field(repressor, "last_synced_at", now)

    child_changed = _sync_repressor_children(repressor, crimes, types)
    changed = changed or child_changed

    if action == "stored":
        return action, repressor
    if changed:
        return "updated", repressor
    return "unchanged", repressor


def serialize_repressor(repressor: Repressor, include_relationships: bool = True) -> dict[str, Any]:
    payload = {
        "id": repressor.id,
        "external_id": repressor.external_id,
        "name": repressor.name,
        "lastname": repressor.lastname,
        "full_name": repressor.full_name,
        "nickname": repressor.nickname,
        "institution_name": repressor.institution_name,
        "campus_name": repressor.campus_name,
        "province_name": repressor.province_name,
        "municipality_name": repressor.municipality_name,
        "country_name": repressor.country_name,
        "image_url": repressor.image_url,
        "image_source_url": repressor.image_source_url,
        "source_detail_url": repressor.source_detail_url,
        "source_status": repressor.source_status,
        "source_is_identifies": repressor.source_is_identifies,
        "source_created_at": repressor.source_created_at.isoformat()
        if repressor.source_created_at
        else None,
        "source_updated_at": repressor.source_updated_at.isoformat()
        if repressor.source_updated_at
        else None,
        "last_synced_at": repressor.last_synced_at.isoformat()
        if repressor.last_synced_at
        else None,
    }
    if include_relationships:
        payload["types"] = [item.name for item in repressor.types]
        payload["crimes"] = [item.name for item in repressor.crimes]
    return payload


def _write_backup_json(path_text: str, rows: list[dict[str, Any]]) -> None:
    path = Path(path_text)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file_obj:
        json.dump(rows, file_obj, ensure_ascii=False, indent=2)


def ingest_repressors_range(
    start_id: int | None = None,
    end_id: int | None = None,
    backup_json_path: str | None = None,
    progress_every: int = 100,
) -> dict[str, Any]:
    scan_start = max(int(start_id or get_scan_start_id()), 1)
    scan_end = max(int(end_id or get_scan_end_id()), scan_start)
    timeout_seconds = get_fetch_timeout_seconds()
    pause_seconds = get_fetch_pause_seconds()

    run = RepressorIngestionRun(
        started_at_utc=datetime.utcnow(),
        status="running",
        scan_start_id=scan_start,
        scan_end_id=scan_end,
    )
    db.session.add(run)
    db.session.commit()

    session = _build_http_session()
    api_base = get_api_base_url().rstrip("/")

    counters = {
        "scanned_ids": 0,
        "stored_items": 0,
        "updated_items": 0,
        "unchanged_items": 0,
        "missing_items": 0,
        "errors_count": 0,
    }
    errors: list[dict[str, Any]] = []
    exported_rows: list[dict[str, Any]] = []

    try:
        total = scan_end - scan_start + 1
        for index, external_id in enumerate(range(scan_start, scan_end + 1), start=1):
            counters["scanned_ids"] += 1
            try:
                base_payload = _request_json(
                    session,
                    f"{api_base}/repressor/{external_id}",
                    timeout_seconds,
                )
                base_row = _extract_repressor_row(base_payload)
                if base_row is None:
                    counters["missing_items"] += 1
                else:
                    crimes_payload = _request_json(
                        session,
                        f"{api_base}/repressor/crimes/list/{external_id}",
                        timeout_seconds,
                    )
                    types_payload = _request_json(
                        session,
                        f"{api_base}/repressor/type/{external_id}",
                        timeout_seconds,
                    )
                    crimes = _extract_named_items(crimes_payload.get("data", []))
                    data_types = types_payload.get("data", {})
                    type_rows = data_types.get("crimes", []) if isinstance(data_types, dict) else []
                    types = _extract_named_items(type_rows)

                    action, repressor = _upsert_repressor(
                        external_id=external_id,
                        base_row=base_row,
                        crimes=crimes,
                        types=types,
                    )
                    counters[f"{action}_items"] += 1
                    exported_rows.append(serialize_repressor(repressor))
            except Exception as exc:
                counters["errors_count"] += 1
                errors.append({"external_id": external_id, "error": str(exc)})
                current_app.logger.exception(
                    "Error en ingesta de represor external_id=%s",
                    external_id,
                )

            if pause_seconds > 0:
                time.sleep(pause_seconds)

            if progress_every > 0 and (index % progress_every == 0 or index == total):
                current_app.logger.info(
                    "Ingesta represores [%s/%s] stored=%s updated=%s unchanged=%s missing=%s errors=%s",
                    index,
                    total,
                    counters["stored_items"],
                    counters["updated_items"],
                    counters["unchanged_items"],
                    counters["missing_items"],
                    counters["errors_count"],
                )

        db.session.commit()

        backup_target = backup_json_path or get_backup_json_path()
        if backup_target:
            _write_backup_json(backup_target, exported_rows)

        run.status = "success"
        run.finished_at_utc = datetime.utcnow()
        run.scanned_ids = counters["scanned_ids"]
        run.stored_items = counters["stored_items"]
        run.updated_items = counters["updated_items"]
        run.unchanged_items = counters["unchanged_items"]
        run.missing_items = counters["missing_items"]
        run.errors_count = counters["errors_count"]
        run.error_message = errors[0]["error"] if errors else None
        run.payload_json = json.dumps(
            {
                "scan_start_id": scan_start,
                "scan_end_id": scan_end,
                "backup_json_path": backup_target,
                "counters": counters,
                "errors_sample": errors[:50],
            },
            ensure_ascii=False,
        )
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        run.status = "failed"
        run.finished_at_utc = datetime.utcnow()
        run.error_message = str(exc)
        run.payload_json = json.dumps(
            {
                "scan_start_id": scan_start,
                "scan_end_id": scan_end,
                "counters": counters,
                "errors_sample": errors[:50],
            },
            ensure_ascii=False,
        )
        db.session.add(run)
        db.session.commit()
        raise

    return {
        "status": run.status,
        "run_id": run.id,
        "scan_start_id": scan_start,
        "scan_end_id": scan_end,
        "backup_json_path": backup_json_path or get_backup_json_path(),
        **counters,
        "errors_sample": errors[:20],
    }


def build_residence_post_title(repressor: Repressor) -> str:
    return f"Residencia de represor: {repressor.full_name}"


def build_residence_post_description(repressor: Repressor, message: str) -> str:
    lines = [
        "Reporte ciudadano de posible residencia de represor.",
        f"Represor: {repressor.full_name}",
    ]
    if repressor.nickname:
        lines.append(f"Seudonimo: {repressor.nickname}")
    if message:
        lines.append("")
        lines.append("Detalles del reporte:")
        lines.append(message.strip())
    return "\n".join(lines).strip()
