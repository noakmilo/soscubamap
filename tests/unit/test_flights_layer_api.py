from datetime import datetime, timedelta
from io import BytesIO
import json

from app.extensions import db
from app.models.flight_aircraft import FlightAircraft
from app.models.flight_airport import FlightAirport
from app.models.flight_event import FlightEvent
from app.models.flight_ingestion_run import FlightIngestionRun
from app.models.flight_layer_snapshot import FlightLayerSnapshot
from app.models.flight_position import FlightPosition
from app.models.role import Role
from app.models.user import User


def _login_admin(client, user_id: int) -> None:
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True


def _seed_flights_data(app):
    with app.app_context():
        admin_role = Role(name="administrador")
        admin_user = User(email="admin-flights-api@example.com")
        admin_user.set_password("test")
        admin_user.roles.append(admin_role)

        now = datetime.utcnow()
        run = FlightIngestionRun(
            started_at_utc=now - timedelta(minutes=20),
            finished_at_utc=now - timedelta(minutes=5),
            status="success",
            safe_mode=False,
            request_count=12,
            estimated_credits=12,
            events_seen=4,
            events_stored=1,
            positions_stored=3,
        )
        db.session.add_all([admin_role, admin_user, run])
        db.session.flush()

        airport = FlightAirport(
            code_key="icao:MUHA",
            airport_code_icao="MUHA",
            airport_code_iata="HAV",
            name="Jose Marti",
            city="La Habana",
            country_code="CU",
            country_name="Cuba",
            latitude=22.9892,
            longitude=-82.4091,
            is_cuba=True,
        )
        aircraft = FlightAircraft(
            identity_key="abc123|a320",
            call_sign="ABC123",
            model="A320",
            registration="N123AB",
        )
        db.session.add_all([airport, aircraft])
        db.session.flush()

        event = FlightEvent(
            event_key="fr24|abc123",
            external_flight_id="abc123",
            aircraft_id=aircraft.id,
            destination_airport_id=airport.id,
            ingestion_run_id=run.id,
            identity_key=aircraft.identity_key,
            call_sign="ABC123",
            model="A320",
            registration="N123AB",
            origin_airport_name="Miami Intl",
            origin_airport_icao="KMIA",
            origin_airport_iata="MIA",
            origin_country="USA",
            destination_airport_name="Jose Marti",
            destination_airport_icao="MUHA",
            destination_airport_iata="HAV",
            destination_country="Cuba",
            status="en_route",
            departure_at_utc=now - timedelta(hours=2),
            last_seen_at_utc=now - timedelta(minutes=2),
            latest_latitude=22.9,
            latest_longitude=-82.6,
            latest_speed=420,
            latest_heading=160,
            last_source_kind="live",
        )
        db.session.add(event)
        db.session.flush()

        position = FlightPosition(
            event_id=event.id,
            observed_at_utc=now - timedelta(minutes=2),
            latitude=22.9,
            longitude=-82.6,
            speed=420,
            heading=160,
            source_kind="live",
        )
        db.session.add(position)

        summary = {
            "window_hours": 24,
            "total_flights": 1,
            "destination_airports": 1,
            "origin_countries": 1,
            "origin_airports": 1,
            "by_destination_airport": [{"airport": "Jose Marti", "count": 1}],
            "by_origin_country": [{"country": "USA", "count": 1}],
            "by_origin_airport": [{"airport": "Miami Intl", "count": 1}],
        }
        points = [
            {
                "event_id": event.id,
                "aircraft_id": aircraft.id,
                "call_sign": "ABC123",
                "model": "A320",
                "destination_airport_name": "Jose Marti",
                "origin_airport_icao": "KMIA",
                "origin_airport_iata": "MIA",
                "destination_airport_icao": "MUHA",
                "destination_airport_iata": "HAV",
                "origin_latitude": 25.7959,
                "origin_longitude": -80.287,
                "destination_latitude": 22.9892,
                "destination_longitude": -82.4091,
                "latitude": 22.9,
                "longitude": -82.6,
                "observed_at_utc": (now - timedelta(minutes=2)).isoformat() + "Z",
            }
        ]
        snapshot = FlightLayerSnapshot(
            window_hours=24,
            generated_at_utc=now - timedelta(minutes=1),
            stale_after_seconds=1800,
            points_count=1,
            summary_json=json.dumps(summary),
            points_json=json.dumps(points),
            ingestion_run_id=run.id,
        )
        db.session.add(snapshot)
        db.session.commit()

        return {
            "admin_id": admin_user.id,
            "aircraft_id": aircraft.id,
            "event_id": event.id,
        }


def test_flights_layer_api_is_public(client):
    response = client.get("/api/v1/flights/cuba-layer")
    assert response.status_code == 200


def test_flights_layer_api_returns_snapshot_for_admin(app, client):
    seeded = _seed_flights_data(app)
    _login_admin(client, seeded["admin_id"])

    response = client.get("/api/v1/flights/cuba-layer?window_hours=24")
    assert response.status_code == 200

    payload = response.get_json()
    assert payload is not None
    assert payload["window_hours"] == 24
    assert isinstance(payload.get("points"), list)
    assert len(payload["points"]) == 1
    assert payload["summary"]["total_flights"] == 1
    assert payload["summary"]["origin_countries"] == 1
    assert payload["summary"]["origin_airports"] == 1
    assert payload["summary"]["by_origin_country"][0]["country"] == "USA"
    assert payload["summary"]["by_origin_airport"][0]["airport"] == "Miami Intl"
    assert payload["latest_run"]["status"] == "success"
    assert payload["points"][0]["origin_latitude"] == 25.7959
    assert payload["points"][0]["destination_latitude"] == 22.9892


def test_flights_layer_api_defaults_to_2h_window_for_admin(app, client):
    seeded = _seed_flights_data(app)
    _login_admin(client, seeded["admin_id"])

    response = client.get("/api/v1/flights/cuba-layer")
    assert response.status_code == 200

    payload = response.get_json()
    assert payload is not None
    assert payload["window_hours"] == 2


def test_flights_layer_api_accepts_7d_window_for_admin(app, client):
    seeded = _seed_flights_data(app)
    _login_admin(client, seeded["admin_id"])

    response = client.get("/api/v1/flights/cuba-layer?window_hours=168")
    assert response.status_code == 200

    payload = response.get_json()
    assert payload is not None
    assert payload["window_hours"] == 168
    assert isinstance(payload.get("points"), list)


def test_flights_layer_api_enriches_route_coordinates_when_missing_in_snapshot(app, client):
    seeded = _seed_flights_data(app)
    _login_admin(client, seeded["admin_id"])

    with app.app_context():
        snapshot = FlightLayerSnapshot.query.filter_by(window_hours=24).first()
        points = json.loads(snapshot.points_json or "[]")
        points[0].pop("origin_latitude", None)
        points[0].pop("origin_longitude", None)
        points[0].pop("destination_latitude", None)
        points[0].pop("destination_longitude", None)
        snapshot.points_json = json.dumps(points)
        db.session.commit()

    response = client.get("/api/v1/flights/cuba-layer?window_hours=24")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload is not None
    point = payload["points"][0]
    assert point["destination_latitude"] == 22.9892
    assert point["destination_longitude"] == -82.4091


def test_flights_detail_track_and_photo_upload(app, client, monkeypatch):
    seeded = _seed_flights_data(app)
    _login_admin(client, seeded["admin_id"])

    detail_response = client.get(f"/api/v1/flights/aircraft/{seeded['aircraft_id']}/detail")
    assert detail_response.status_code == 200
    detail_payload = detail_response.get_json()
    assert detail_payload["aircraft"]["call_sign"] == "ABC123"
    assert detail_payload["summary_30d"]["trips_to_cuba"] >= 1

    track_response = client.get(f"/api/v1/flights/events/{seeded['event_id']}/track")
    assert track_response.status_code == 200
    track_payload = track_response.get_json()
    assert track_payload["event"]["id"] == seeded["event_id"]
    assert track_payload["track"]["point_count"] >= 1

    monkeypatch.setattr("app.blueprints.api.routes.validate_files", lambda _files: (True, ""))
    monkeypatch.setattr(
        "app.blueprints.api.routes.upload_files",
        lambda _files: ["https://cdn.example.com/plane-photo.jpg"],
    )

    with app.app_context():
        app.config["CLOUDINARY_CLOUD_NAME"] = "cloud"
        app.config["CLOUDINARY_API_KEY"] = "key"
        app.config["CLOUDINARY_API_SECRET"] = "secret"

    upload_response = client.post(
        f"/api/v1/flights/aircraft/{seeded['aircraft_id']}/photo",
        data={"photo": (BytesIO(b"img-bytes"), "plane.jpg")},
        content_type="multipart/form-data",
    )
    assert upload_response.status_code == 200
    upload_payload = upload_response.get_json()
    assert upload_payload["ok"] is True
    assert upload_payload["photo_source"] == "manual"
    assert upload_payload["photo_url"] == "https://cdn.example.com/plane-photo.jpg"


def test_flights_detail_uses_event_id_for_summary_enrichment(app, client, monkeypatch):
    seeded = _seed_flights_data(app)
    _login_admin(client, seeded["admin_id"])

    captured = {"aircraft_id": None, "event_id": None}

    def fake_enrich(aircraft, event=None):
        captured["aircraft_id"] = aircraft.id
        captured["event_id"] = event.id if event is not None else None
        return {"status": "cached", "event_id": captured["event_id"], "requests": 0, "warnings": []}

    monkeypatch.setattr("app.blueprints.api.routes.enrich_aircraft_detail_from_summary_light", fake_enrich)

    response = client.get(
        f"/api/v1/flights/aircraft/{seeded['aircraft_id']}/detail?event_id={seeded['event_id']}"
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload is not None
    assert payload["summary_light_cache"]["status"] == "cached"
    assert payload["summary_light_cache"]["event_id"] == seeded["event_id"]
    assert captured["aircraft_id"] == seeded["aircraft_id"]
    assert captured["event_id"] == seeded["event_id"]


def test_flights_detail_uses_latest_event_when_event_id_missing(app, client, monkeypatch):
    seeded = _seed_flights_data(app)
    _login_admin(client, seeded["admin_id"])

    captured = {"opensky_event_id": None, "summary_event_id": None}

    def fake_opensky_enrich(aircraft, event=None):
        captured["opensky_event_id"] = event.id if event is not None else None
        return {"status": "cached", "event_id": captured["opensky_event_id"], "requests": 0, "warnings": []}

    def fake_summary_enrich(aircraft, event=None):
        captured["summary_event_id"] = event.id if event is not None else None
        return {"status": "cached", "event_id": captured["summary_event_id"], "requests": 0, "warnings": []}

    monkeypatch.setattr("app.blueprints.api.routes.enrich_aircraft_detail_from_opensky", fake_opensky_enrich)
    monkeypatch.setattr("app.blueprints.api.routes.enrich_aircraft_detail_from_summary_light", fake_summary_enrich)

    response = client.get(f"/api/v1/flights/aircraft/{seeded['aircraft_id']}/detail")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload is not None
    assert payload["opensky_cache"]["event_id"] == seeded["event_id"]
    assert payload["summary_light_cache"]["event_id"] == seeded["event_id"]
    assert captured["opensky_event_id"] == seeded["event_id"]
    assert captured["summary_event_id"] == seeded["event_id"]
