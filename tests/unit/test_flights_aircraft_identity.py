from datetime import datetime, timedelta

from sqlalchemy import func

from app.extensions import db
from app.models.flight_aircraft import FlightAircraft
from app.models.flight_event import FlightEvent
from app.models.flight_ingestion_run import FlightIngestionRun
from app.services.flights import _normalize_identity_key, _persist_records


def _build_record(*, event_key: str, identity_key: str, call_sign: str, registration: str, observed_at_utc: datetime):
    return {
        "event_key": event_key,
        "external_flight_id": event_key,
        "identity_key": identity_key,
        "call_sign": call_sign,
        "model": "B38M",
        "registration": registration,
        "origin_airport_icao": "KMIA",
        "origin_airport_iata": "MIA",
        "origin_airport_name": "Miami Intl",
        "origin_country": "USA",
        "destination_airport_icao": "MUHA",
        "destination_airport_iata": "HAV",
        "destination_airport_name": "Jose Marti",
        "destination_country": "Cuba",
        "destination_country_code": "CU",
        "destination_fr_airport_id": "airport-muha",
        "status": "live",
        "departure_at_utc": observed_at_utc - timedelta(hours=2),
        "arrival_at_utc": None,
        "observed_at_utc": observed_at_utc,
        "latitude": 23.0,
        "longitude": -82.0,
        "altitude": 12000,
        "speed": 430,
        "heading": 150,
        "source_kind": "live",
    }


def test_identity_key_prioritizes_registration_over_callsign_and_model():
    key = _normalize_identity_key("SWA3952", "B38M", "N8884Q", "fr24-123")
    assert key == "reg|n8884q"



def test_persist_records_merges_aircraft_rows_by_registration(app):
    with app.app_context():
        now = datetime.utcnow()
        run = FlightIngestionRun(started_at_utc=now - timedelta(minutes=10), status="running")
        db.session.add(run)
        db.session.flush()

        legacy_aircraft = FlightAircraft(
            identity_key="swa3952|b38m",
            call_sign="SWA3952",
            model="B38M",
            registration="N8884Q",
            first_seen_at_utc=now - timedelta(days=2),
            last_seen_at_utc=now - timedelta(days=1),
        )
        db.session.add(legacy_aircraft)
        db.session.flush()

        legacy_event = FlightEvent(
            event_key="legacy-event-1",
            external_flight_id="legacy-event-1",
            aircraft_id=legacy_aircraft.id,
            ingestion_run_id=run.id,
            identity_key=legacy_aircraft.identity_key,
            call_sign="SWA3952",
            model="B38M",
            registration="N8884Q",
            destination_airport_name="Jose Marti",
            destination_country="Cuba",
            last_seen_at_utc=now - timedelta(days=1),
            latest_latitude=22.9,
            latest_longitude=-82.4,
            last_source_kind="historic",
        )
        db.session.add(legacy_event)
        db.session.commit()

        new_record = _build_record(
            event_key="fr24|new-event-2",
            identity_key="reg|n8884q",
            call_sign="SWA4012",
            registration="N8884Q",
            observed_at_utc=now,
        )

        events_stored, _positions_stored = _persist_records([new_record], run)
        db.session.commit()

        assert events_stored == 1

        aircraft_rows = FlightAircraft.query.filter(
            func.upper(func.coalesce(FlightAircraft.registration, "")) == "N8884Q"
        ).all()
        assert len(aircraft_rows) == 1

        canonical = aircraft_rows[0]
        assert canonical.identity_key == "reg|n8884q"

        reloaded_legacy_event = FlightEvent.query.filter_by(event_key="legacy-event-1").first()
        new_event = FlightEvent.query.filter_by(event_key="fr24|new-event-2").first()
        assert reloaded_legacy_event is not None
        assert new_event is not None
        assert reloaded_legacy_event.aircraft_id == canonical.id
        assert new_event.aircraft_id == canonical.id
