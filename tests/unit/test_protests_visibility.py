import json
from datetime import datetime

import pytest

import app.services.protests as protests
from app.extensions import db
from app.models.protest_event import ProtestEvent


@pytest.fixture(autouse=True)
def _reset_protests_cache(monkeypatch):
    protests._GAZETTEER_CACHE["signature"] = None
    protests._GAZETTEER_CACHE["data"] = None
    monkeypatch.delenv("GEOJSON_PROVINCES_PATH", raising=False)
    monkeypatch.delenv("GEOJSON_MUNICIPALITIES_PATH", raising=False)
    monkeypatch.delenv("GEOJSON_LOCALITIES_PATH", raising=False)
    yield
    protests._GAZETTEER_CACHE["signature"] = None
    protests._GAZETTEER_CACHE["data"] = None


def test_resolve_place_uses_province_center_fallback():
    result = protests.resolve_place("Protesta reportada en La Habana")
    assert result["feature_type"] == "province"
    assert result["province"] == "La Habana"
    assert result["latitude"] is not None
    assert result["longitude"] is not None
    assert result["location_precision"] == "exact_province"


def test_should_show_on_map_allows_low_score_if_keywords_match(monkeypatch):
    monkeypatch.setenv("PROTEST_MIN_CONFIDENCE_TO_SHOW", "80")
    payload = {
        "source_url": "https://x.com/soscuba/status/123",
        "confidence_score": 8.0,
        "event_type": "context_only",
        "latitude": 23.1136,
        "longitude": -82.3666,
    }
    keyword_hits = {"strong": [], "context": ["represion"], "weak": []}
    assert protests.should_show_on_map(payload, keyword_hits=keyword_hits) is True


def test_should_show_on_map_blocks_low_score_without_keywords(monkeypatch):
    monkeypatch.setenv("PROTEST_MIN_CONFIDENCE_TO_SHOW", "80")
    payload = {
        "source_url": "https://x.com/soscuba/status/456",
        "confidence_score": 8.0,
        "event_type": "context_only",
        "latitude": 23.1136,
        "longitude": -82.3666,
    }
    assert protests.should_show_on_map(payload, keyword_hits={"strong": [], "context": [], "weak": []}) is False


def test_protests_geojson_keeps_visible_low_confidence_without_min_conf_filter(app, client):
    now = datetime.utcnow().replace(microsecond=0)
    low_score = ProtestEvent(
        source_feed="https://feed.example/1.xml",
        source_name="feed-a",
        source_guid="guid-a",
        source_url="https://x.com/soscuba/status/a",
        source_platform="x",
        source_published_at_utc=now,
        published_day_utc=now.date(),
        raw_title="Evento A",
        raw_description="desc",
        clean_text="texto",
        detected_keywords_json=json.dumps({"context": ["represion"]}, ensure_ascii=False),
        latitude=23.11,
        longitude=-82.36,
        confidence_score=8.0,
        event_type="context_only",
        review_status="auto",
        visible_on_map=True,
        dedupe_hash="a" * 64,
        transparency_note="Fuente enlazada al post original.",
    )
    high_score = ProtestEvent(
        source_feed="https://feed.example/2.xml",
        source_name="feed-b",
        source_guid="guid-b",
        source_url="https://x.com/soscuba/status/b",
        source_platform="x",
        source_published_at_utc=now,
        published_day_utc=now.date(),
        raw_title="Evento B",
        raw_description="desc",
        clean_text="texto",
        detected_keywords_json=json.dumps({"strong": ["protesta"]}, ensure_ascii=False),
        latitude=23.12,
        longitude=-82.37,
        confidence_score=70.0,
        event_type="confirmed_protest",
        review_status="auto",
        visible_on_map=True,
        dedupe_hash="b" * 64,
        transparency_note="Fuente enlazada al post original.",
    )

    with app.app_context():
        db.session.add(low_score)
        db.session.add(high_score)
        db.session.commit()

    day = now.date().isoformat()
    response = client.get(f"/api/protests/geojson?day={day}")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload is not None
    assert payload["features_total"] == 2

    filtered = client.get(f"/api/protests/geojson?day={day}&min_confidence=50")
    assert filtered.status_code == 200
    filtered_payload = filtered.get_json()
    assert filtered_payload is not None
    assert filtered_payload["features_total"] == 1
