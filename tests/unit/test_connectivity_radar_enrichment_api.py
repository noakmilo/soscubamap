import json
from datetime import datetime, timedelta

from app.extensions import db
from app.models.connectivity_ingestion_run import ConnectivityIngestionRun


def _iso_utc(dt):
    return dt.replace(microsecond=0).isoformat() + "Z"


def test_connectivity_latest_exposes_cloudflare_radar_enrichment(client, app):
    with app.app_context():
        now = datetime.utcnow()
        run = ConnectivityIngestionRun(
            status="success",
            started_at_utc=now - timedelta(minutes=2),
            finished_at_utc=now - timedelta(minutes=1),
            payload_json=json.dumps(
                {
                    "mode": "province_geoid_v1",
                    "provinces": {},
                    "cloudflare_radar": {
                        "fetched_at_utc": _iso_utc(now - timedelta(minutes=1)),
                        "audience": {
                            "available": True,
                            "device_mobile_pct": 72.4,
                            "device_desktop_pct": 27.6,
                            "human_pct": 86.2,
                            "bot_pct": 13.8,
                        },
                        "speed": {
                            "available": True,
                            "latest": {
                                "download_mbps": 7.52,
                                "global_download_mbps": 21.84,
                                "download_delta_pct": -65.57,
                                "latency_ms": 142.5,
                                "global_latency_ms": 61.2,
                                "latency_delta_pct": 132.84,
                            },
                            "averages_7d": {
                                "download_mbps": 6.91,
                                "latency_ms": 151.1,
                            },
                        },
                        "alerts": {
                            "items": [
                                {
                                    "source": "annotation",
                                    "alert_type": "outage",
                                    "event_type": "OUTAGE",
                                    "start_date": _iso_utc(now - timedelta(hours=1)),
                                    "end_date": None,
                                    "description": "Interrupción en curso",
                                },
                                {
                                    "source": "traffic_anomaly",
                                    "alert_type": "anomaly",
                                    "event_type": "traffic_anomaly",
                                    "start_date": _iso_utc(now - timedelta(hours=3)),
                                    "end_date": _iso_utc(now + timedelta(hours=1)),
                                    "description": "Anomalía de tráfico",
                                },
                            ],
                        },
                        "errors": [],
                    },
                },
                ensure_ascii=False,
            ),
        )
        db.session.add(run)
        db.session.commit()

    response = client.get("/api/connectivity/latest")
    assert response.status_code == 200
    payload = response.get_json()
    radar = payload.get("cloudflare_radar") or {}

    assert radar.get("available") is True
    assert radar.get("alerts", {}).get("active_count") == 2
    assert radar.get("alerts", {}).get("active_outages") == 1
    assert radar.get("alerts", {}).get("active_anomalies") == 1
    assert radar.get("speed", {}).get("latest", {}).get("download_mbps") == 7.52
    assert radar.get("audience", {}).get("device_mobile_pct") == 72.4


def test_connectivity_latest_handles_missing_radar_enrichment(client, app):
    with app.app_context():
        run = ConnectivityIngestionRun(
            status="success",
            payload_json=json.dumps(
                {
                    "mode": "province_geoid_v1",
                    "provinces": {},
                },
                ensure_ascii=False,
            ),
        )
        db.session.add(run)
        db.session.commit()

    response = client.get("/api/connectivity/latest")
    assert response.status_code == 200
    payload = response.get_json()
    radar = payload.get("cloudflare_radar") or {}

    assert radar.get("available") is False
    assert radar.get("alerts", {}).get("active_count") == 0


def test_connectivity_latest_audience_changes_with_window_hours(client, app):
    with app.app_context():
        now = datetime.utcnow()
        recent_run = ConnectivityIngestionRun(
            status="success",
            started_at_utc=now - timedelta(hours=1),
            finished_at_utc=now - timedelta(minutes=50),
            payload_json=json.dumps(
                {
                    "mode": "province_geoid_v1",
                    "provinces": {},
                    "cloudflare_radar": {
                        "fetched_at_utc": _iso_utc(now - timedelta(minutes=50)),
                        "audience": {
                            "available": True,
                            "device_mobile_pct": 80.0,
                            "device_desktop_pct": 20.0,
                            "human_pct": 90.0,
                            "bot_pct": 10.0,
                        },
                        "speed": {"available": False},
                        "alerts": {"items": []},
                        "errors": [],
                    },
                },
                ensure_ascii=False,
            ),
        )
        older_run = ConnectivityIngestionRun(
            status="success",
            started_at_utc=now - timedelta(hours=5),
            finished_at_utc=now - timedelta(hours=4, minutes=45),
            payload_json=json.dumps(
                {
                    "mode": "province_geoid_v1",
                    "provinces": {},
                    "cloudflare_radar": {
                        "fetched_at_utc": _iso_utc(now - timedelta(hours=4, minutes=45)),
                        "audience": {
                            "available": True,
                            "device_mobile_pct": 60.0,
                            "device_desktop_pct": 40.0,
                            "human_pct": 70.0,
                            "bot_pct": 30.0,
                        },
                        "speed": {"available": False},
                        "alerts": {"items": []},
                        "errors": [],
                    },
                },
                ensure_ascii=False,
            ),
        )
        db.session.add(recent_run)
        db.session.add(older_run)
        db.session.commit()

    payload_2h = client.get("/api/connectivity/latest?window_hours=2").get_json()
    payload_6h = client.get("/api/connectivity/latest?window_hours=6").get_json()

    audience_2h = payload_2h.get("cloudflare_radar", {}).get("audience", {})
    audience_6h = payload_6h.get("cloudflare_radar", {}).get("audience", {})

    assert audience_2h.get("window_hours") == 2
    assert audience_2h.get("sample_count") == 1
    assert audience_2h.get("device_mobile_pct") == 80.0
    assert audience_2h.get("human_pct") == 90.0

    assert audience_6h.get("window_hours") == 6
    assert audience_6h.get("sample_count") == 2
    assert audience_6h.get("device_mobile_pct") == 70.0
    assert audience_6h.get("human_pct") == 80.0
