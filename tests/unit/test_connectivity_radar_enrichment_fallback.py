from datetime import timedelta

from scripts import fetch_connectivity as fc


def _sample_previous_payload():
    return {
        "fetched_at_utc": "2026-03-25T10:00:00Z",
        "api_base_url": "https://api.cloudflare.com/client/v4/radar",
        "audience": {
            "available": True,
            "device_mobile_pct": 72.0,
            "device_desktop_pct": 28.0,
            "human_pct": 88.0,
            "bot_pct": 12.0,
        },
        "alerts": {
            "available": True,
            "items": [],
            "count_annotations": 0,
            "count_anomalies": 0,
        },
        "speed": {
            "available": True,
            "days": [],
            "latest": {"download_mbps": 6.5, "latency_ms": 150.0},
            "averages_7d": {"download_mbps": 6.2, "latency_ms": 160.0},
        },
        "errors": [],
    }


def test_radar_enrichment_reuses_previous_during_cooldown(monkeypatch):
    called = {"count": 0}

    def _fake_fetch(*args, **kwargs):
        called["count"] += 1
        return {}

    monkeypatch.setattr(fc, "_fetch_radar_enrichment", _fake_fetch)

    now = fc._utcnow()
    previous = {
        "run_id": 123,
        "fetched_at_utc": now - timedelta(minutes=30),
        "payload": _sample_previous_payload(),
    }
    resolved = fc._resolve_radar_enrichment_with_fallback(
        "https://api.cloudflare.com/client/v4/radar",
        "token",
        30,
        cooldown_seconds=21600,
        previous_record=previous,
    )

    assert called["count"] == 0
    assert resolved.get("reused_from_run_id") == 123
    assert resolved.get("reused_reason") == "cooldown_active"
    assert resolved.get("audience", {}).get("available") is True
    assert resolved.get("speed", {}).get("available") is True


def test_radar_enrichment_reuses_previous_when_rate_limited(monkeypatch):
    def _fake_fetch(*args, **kwargs):
        return {
            "fetched_at_utc": "2026-03-25T16:00:00Z",
            "api_base_url": "https://api.cloudflare.com/client/v4/radar",
            "audience": {"available": False},
            "alerts": {"available": False, "items": []},
            "speed": {"available": False, "latest": None, "averages_7d": {}},
            "errors": [
                {"endpoint": "device_type", "status_code": 429, "error": "HTTP 429"},
            ],
        }

    monkeypatch.setattr(fc, "_fetch_radar_enrichment", _fake_fetch)

    previous = {
        "run_id": 77,
        "fetched_at_utc": fc._utcnow() - timedelta(hours=12),
        "payload": _sample_previous_payload(),
    }
    resolved = fc._resolve_radar_enrichment_with_fallback(
        "https://api.cloudflare.com/client/v4/radar",
        "token",
        30,
        cooldown_seconds=0,
        previous_record=previous,
    )

    assert resolved.get("reused_from_run_id") == 77
    assert resolved.get("reused_reason") == "upstream_rate_limited"
    assert resolved.get("audience", {}).get("available") is True
    assert resolved.get("speed", {}).get("available") is True
    errors = resolved.get("errors") or []
    assert any(item.get("status_code") == 429 for item in errors if isinstance(item, dict))
