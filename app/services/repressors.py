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
from sqlalchemy import func
from sqlalchemy.orm import selectinload
from urllib3.util.retry import Retry

from app.extensions import db
from app.models.repressor import (
    Repressor,
    RepressorCrime,
    RepressorIngestionRun,
    REPRESSOR_VERIFY_LOCK_COUNT,
    RepressorType,
)
from app.services.location_names import canonicalize_location_names


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


def _request_json_or_none_on_404(
    session: requests.Session,
    url: str,
    timeout_seconds: float,
) -> dict[str, Any] | None:
    response = session.get(url, timeout=timeout_seconds)
    if response.status_code == 404:
        return None
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


def _fetch_repressor_row(
    session: requests.Session,
    api_base: str,
    external_id: int,
    timeout_seconds: float,
) -> dict[str, Any] | None:
    payload = _request_json_or_none_on_404(
        session,
        f"{api_base}/repressor/{external_id}",
        timeout_seconds,
    )
    if payload is None:
        return None
    return _extract_repressor_row(payload)


def _discover_latest_external_id(
    session: requests.Session,
    api_base: str,
    timeout_seconds: float,
    first_probe_id: int,
) -> int:
    start_probe = max(int(first_probe_id), 1)
    existence_cache: dict[int, bool] = {}

    def _exists(external_id: int) -> bool:
        cached = existence_cache.get(external_id)
        if cached is not None:
            return cached
        row = _fetch_repressor_row(session, api_base, external_id, timeout_seconds)
        ok = row is not None
        existence_cache[external_id] = ok
        return ok

    if not _exists(start_probe):
        return start_probe - 1

    max_probe = 1_000_000
    lo = start_probe
    hi = max(start_probe + 1, start_probe * 2)
    hi = min(hi, max_probe)

    while _exists(hi):
        lo = hi
        if hi >= max_probe:
            current_app.logger.warning(
                "Se alcanzó el techo de detección de IDs (%s).",
                max_probe,
            )
            return hi
        hi = min(hi * 2, max_probe)

    while lo + 1 < hi:
        mid = (lo + hi) // 2
        if _exists(mid):
            lo = mid
        else:
            hi = mid

    return lo


def _latest_stored_external_id() -> int | None:
    value = db.session.query(func.max(Repressor.external_id)).scalar()
    if value is None:
        return None
    try:
        parsed = int(value)
    except Exception:
        return None
    return parsed if parsed >= 1 else None


def _resolve_scan_start_id(start_id: int | None) -> tuple[int, str]:
    if start_id is not None:
        return max(int(start_id), 1), "explicit"

    latest_stored_id = _latest_stored_external_id()
    if latest_stored_id is not None:
        return latest_stored_id + 1, "incremental_from_last"

    return get_scan_start_id(), "bootstrap_from_config"


def _auto_stop_missing_streak(
    scan_start_strategy: str,
    scan_start: int,
    latest_stored_external_id: int | None,
) -> int:
    if scan_start <= 1:
        return 500
    if scan_start_strategy == "bootstrap_from_config":
        return 500
    if scan_start_strategy == "incremental_from_last":
        if latest_stored_external_id is None or latest_stored_external_id < 1000:
            return 500
    return 25


def _extract_named_items(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    dedup_by_name: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        name = _clean_text(item.get("name"))
        if not name:
            continue
        item_id = _safe_int(item.get("id"), 0) or None
        existing = dedup_by_name.get(name)
        if existing is None:
            dedup_by_name[name] = {"id": item_id, "name": name}
            continue
        if existing.get("id") is None and item_id is not None:
            existing["id"] = item_id
    return list(dedup_by_name.values())


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
            obj = RepressorCrime(
                name=item["name"],
                source_crime_id=item.get("id"),
            )
            repressor.crimes.append(obj)
            current_crimes[item["name"]] = obj
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
            obj = RepressorType(
                name=item["name"],
                source_type_id=item.get("id"),
            )
            repressor.types.append(obj)
            current_types[item["name"]] = obj
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
        if (repressor.verify_count or 0) >= REPRESSOR_VERIFY_LOCK_COUNT:
            return "unchanged", repressor

    source_image_url = _build_source_image_url(base_row.get("image"))
    image_changed = source_image_url != repressor.image_source_url
    desired_cached_image = repressor.image_cached_url
    if image_changed or not desired_cached_image:
        desired_cached_image = _cache_image_url(source_image_url, external_id)

    province_name, municipality_name = canonicalize_location_names(
        _clean_text(base_row.get("province_name")),
        _clean_text(base_row.get("municipality_name")),
    )

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
    changed |= _set_field(repressor, "province_name", province_name)
    changed |= _set_field(
        repressor,
        "municipality_name",
        municipality_name,
    )
    changed |= _set_field(repressor, "testimony", _clean_text(base_row.get("testimony")))
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
    province_name, municipality_name = canonicalize_location_names(
        repressor.province_name,
        repressor.municipality_name,
    )
    payload = {
        "id": repressor.id,
        "external_id": repressor.external_id,
        "verify_count": repressor.verify_count or 0,
        "name": repressor.name,
        "lastname": repressor.lastname,
        "full_name": repressor.full_name,
        "nickname": repressor.nickname,
        "institution_name": repressor.institution_name,
        "campus_name": repressor.campus_name,
        "province_name": province_name,
        "municipality_name": municipality_name,
        "country_name": repressor.country_name,
        "testimony": repressor.testimony,
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


def _serialize_all_repressors_for_backup() -> list[dict[str, Any]]:
    rows = (
        Repressor.query.options(
            selectinload(Repressor.crimes),
            selectinload(Repressor.types),
        )
        .order_by(Repressor.external_id.asc(), Repressor.id.asc())
        .all()
    )
    return [serialize_repressor(item, include_relationships=True) for item in rows]


def ingest_repressors_range(
    start_id: int | None = None,
    end_id: int | None = None,
    backup_json_path: str | None = None,
    progress_every: int = 100,
) -> dict[str, Any]:
    timeout_seconds = get_fetch_timeout_seconds()
    pause_seconds = get_fetch_pause_seconds()
    session = _build_http_session()
    api_base = get_api_base_url().rstrip("/")

    latest_stored_before_scan = _latest_stored_external_id()
    scan_start, scan_start_strategy = _resolve_scan_start_id(start_id)
    auto_stop_missing = _auto_stop_missing_streak(
        scan_start_strategy=scan_start_strategy,
        scan_start=scan_start,
        latest_stored_external_id=latest_stored_before_scan,
    )
    if end_id is not None:
        scan_end = max(int(end_id), 1)
        scan_end_strategy = "explicit"
    else:
        scan_end = scan_start
        scan_end_strategy = "auto_until_missing_streak"

    run = RepressorIngestionRun(
        started_at_utc=datetime.utcnow(),
        status="running",
        scan_start_id=scan_start,
        scan_end_id=scan_end,
    )
    db.session.add(run)
    db.session.commit()
    if scan_end_strategy == "explicit":
        current_app.logger.info(
            "Ingesta represores iniciada. start=%s (%s) end=%s (%s)",
            scan_start,
            scan_start_strategy,
            scan_end,
            scan_end_strategy,
        )
    else:
        current_app.logger.info(
            "Ingesta represores iniciada. start=%s (%s) end=auto (%s, missing_streak_stop=%s)",
            scan_start,
            scan_start_strategy,
            scan_end_strategy,
            auto_stop_missing,
        )

    counters = {
        "scanned_ids": 0,
        "stored_items": 0,
        "updated_items": 0,
        "unchanged_items": 0,
        "missing_items": 0,
        "errors_count": 0,
    }
    errors: list[dict[str, Any]] = []
    last_existing_external_id = scan_start - 1

    try:
        if scan_end_strategy == "explicit":
            total = max(scan_end - scan_start + 1, 0)
            if total == 0:
                current_app.logger.info(
                    "No hay IDs nuevos para ingerir. start=%s end=%s.",
                    scan_start,
                    scan_end,
                )
        else:
            total = None

        processed = 0
        missing_streak = 0
        external_id = scan_start
        while True:
            if scan_end_strategy == "explicit":
                if external_id > scan_end:
                    break
            else:
                if missing_streak >= auto_stop_missing:
                    break

            processed += 1
            counters["scanned_ids"] += 1
            try:
                base_row = _fetch_repressor_row(
                    session=session,
                    api_base=api_base,
                    external_id=external_id,
                    timeout_seconds=timeout_seconds,
                )
                if base_row is None:
                    counters["missing_items"] += 1
                    missing_streak += 1
                else:
                    missing_streak = 0
                    if external_id > last_existing_external_id:
                        last_existing_external_id = external_id
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
                    db.session.commit()
            except Exception as exc:
                db.session.rollback()
                counters["errors_count"] += 1
                errors.append({"external_id": external_id, "error": str(exc)})
                current_app.logger.exception(
                    "Error en ingesta de represor external_id=%s",
                    external_id,
                )

            if pause_seconds > 0:
                time.sleep(pause_seconds)

            if progress_every > 0 and (
                processed % progress_every == 0
                or (total is not None and processed == total)
            ):
                if total is not None:
                    current_app.logger.info(
                        "Ingesta represores [%s/%s] stored=%s updated=%s unchanged=%s missing=%s errors=%s",
                        processed,
                        total,
                        counters["stored_items"],
                        counters["updated_items"],
                        counters["unchanged_items"],
                        counters["missing_items"],
                        counters["errors_count"],
                    )
                else:
                    current_app.logger.info(
                        "Ingesta represores [%s] stored=%s updated=%s unchanged=%s missing=%s errors=%s missing_streak=%s/%s",
                        processed,
                        counters["stored_items"],
                        counters["updated_items"],
                        counters["unchanged_items"],
                        counters["missing_items"],
                        counters["errors_count"],
                        missing_streak,
                        auto_stop_missing,
                    )

            external_id += 1

        if scan_end_strategy != "explicit":
            scan_end = max(last_existing_external_id, scan_start - 1)
            if counters["stored_items"] == 0 and counters["updated_items"] == 0 and counters["unchanged_items"] == 0:
                current_app.logger.info(
                    "No se encontraron nuevos represores en modo incremental. start=%s.",
                    scan_start,
                )
            else:
                current_app.logger.info(
                    "Ingesta represores auto-finalizada en external_id=%s tras missing_streak=%s.",
                    scan_end,
                    auto_stop_missing,
                )

        backup_target = backup_json_path or get_backup_json_path()
        if backup_target:
            _write_backup_json(backup_target, _serialize_all_repressors_for_backup())

        run.status = "success"
        run.finished_at_utc = datetime.utcnow()
        run.scanned_ids = counters["scanned_ids"]
        run.stored_items = counters["stored_items"]
        run.updated_items = counters["updated_items"]
        run.unchanged_items = counters["unchanged_items"]
        run.missing_items = counters["missing_items"]
        run.errors_count = counters["errors_count"]
        run.scan_end_id = scan_end
        run.error_message = errors[0]["error"] if errors else None
        run.payload_json = json.dumps(
            {
                "scan_start_id": scan_start,
                "scan_end_id": scan_end,
                "scan_start_strategy": scan_start_strategy,
                "scan_end_strategy": scan_end_strategy,
                "auto_stop_missing_streak": auto_stop_missing if scan_end_strategy != "explicit" else None,
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
                "scan_start_strategy": scan_start_strategy,
                "scan_end_strategy": scan_end_strategy,
                "auto_stop_missing_streak": auto_stop_missing if scan_end_strategy != "explicit" else None,
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
        "scan_start_strategy": scan_start_strategy,
        "scan_end_strategy": scan_end_strategy,
        "auto_stop_missing_streak": auto_stop_missing if scan_end_strategy != "explicit" else None,
        "next_suggested_start_id": (scan_end + 1) if scan_end >= 1 else 1,
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
