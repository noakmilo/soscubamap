from datetime import datetime, timedelta

from app.extensions import db
from app.models.flight_aircraft import FlightAircraft
from app.models.flight_event import FlightEvent


def _seed_aircraft_with_event(*, registration: str, call_sign: str, minutes_offset: int = 0):
    now = datetime.utcnow() + timedelta(minutes=minutes_offset)
    aircraft = FlightAircraft(
        identity_key=f"{registration.lower()}|{call_sign.lower()}|{minutes_offset}",
        call_sign=call_sign,
        model="A320",
        registration=registration,
        operator_name="Test Operator",
        last_seen_at_utc=now,
        first_seen_at_utc=now - timedelta(days=2),
    )
    db.session.add(aircraft)
    db.session.flush()

    event = FlightEvent(
        event_key=f"evt|{registration}|{call_sign}|{minutes_offset}",
        aircraft_id=aircraft.id,
        identity_key=aircraft.identity_key,
        call_sign=call_sign,
        model="A320",
        registration=registration,
        origin_airport_name="Miami Intl",
        origin_country="USA",
        destination_airport_name="Jose Marti",
        destination_country="Cuba",
        status="landed",
        departure_at_utc=now - timedelta(hours=2),
        arrival_at_utc=now - timedelta(hours=1),
        last_seen_at_utc=now - timedelta(minutes=5),
        latest_latitude=22.9,
        latest_longitude=-82.4,
    )
    db.session.add(event)
    db.session.commit()
    return {
        "aircraft_id": aircraft.id,
        "event_id": event.id,
        "registration": aircraft.registration,
        "call_sign": aircraft.call_sign,
    }


def test_flight_profile_route_renders_by_registration(app, client):
    with app.app_context():
        seeded = _seed_aircraft_with_event(
            registration="N123AB",
            call_sign="ABC123",
            minutes_offset=0,
        )

    response = client.get(f"/vuelos/matricula/{seeded['registration']}")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Ficha de avión" in html
    assert "ABC123" in html
    assert "Miami Intl" in html
    assert "Jose Marti" in html


def test_flight_profile_route_uses_aircraft_id_when_provided(app, client):
    with app.app_context():
        older = _seed_aircraft_with_event(
            registration="N777ZZ",
            call_sign="OLD111",
            minutes_offset=-1440,
        )
        _newer = _seed_aircraft_with_event(
            registration="N777ZZ",
            call_sign="NEW222",
            minutes_offset=0,
        )

    response = client.get(f"/vuelos/matricula/N777ZZ?aircraft_id={older['aircraft_id']}")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "OLD111" in html
    assert "NEW222" not in html


def test_flight_profile_route_returns_404_when_registration_not_found(client):
    response = client.get("/vuelos/matricula/NOEXISTE")
    assert response.status_code == 404
