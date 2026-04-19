from datetime import datetime, timedelta

from app.extensions import db
from app.models.flight_aircraft import FlightAircraft
from app.models.flight_airport import FlightAirport
from app.models.flight_event import FlightEvent


def test_analytics_includes_flights_origin_distribution(app, client):
    now = datetime.utcnow()
    with app.app_context():
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
        aircraft_a = FlightAircraft(
            identity_key="flight-analytics-a",
            call_sign="AAA001",
            model="A320",
        )
        aircraft_b = FlightAircraft(
            identity_key="flight-analytics-b",
            call_sign="BBB002",
            model="B738",
        )
        db.session.add_all([airport, aircraft_a, aircraft_b])
        db.session.flush()

        event_a = FlightEvent(
            event_key="analytics-flight-a",
            external_flight_id="analytics-flight-a",
            aircraft_id=aircraft_a.id,
            destination_airport_id=airport.id,
            identity_key=aircraft_a.identity_key,
            call_sign=aircraft_a.call_sign,
            model=aircraft_a.model,
            origin_airport_name="Miami Intl",
            origin_airport_icao="KMIA",
            origin_airport_iata="MIA",
            origin_country="USA",
            destination_airport_name="Jose Marti",
            destination_airport_icao="MUHA",
            destination_airport_iata="HAV",
            destination_country="Cuba",
            status="en_route",
            last_seen_at_utc=now - timedelta(days=1),
            latest_latitude=22.8,
            latest_longitude=-82.5,
            last_source_kind="historic",
        )
        event_b = FlightEvent(
            event_key="analytics-flight-b",
            external_flight_id="analytics-flight-b",
            aircraft_id=aircraft_b.id,
            destination_airport_id=airport.id,
            identity_key=aircraft_b.identity_key,
            call_sign=aircraft_b.call_sign,
            model=aircraft_b.model,
            origin_airport_name="Cancun Intl",
            origin_airport_icao="MMUN",
            origin_airport_iata="CUN",
            origin_country="Mexico",
            destination_airport_name="Jose Marti",
            destination_airport_icao="MUHA",
            destination_airport_iata="HAV",
            destination_country="Cuba",
            status="en_route",
            last_seen_at_utc=now - timedelta(days=2),
            latest_latitude=22.7,
            latest_longitude=-82.4,
            last_source_kind="historic",
        )
        event_old = FlightEvent(
            event_key="analytics-flight-old",
            external_flight_id="analytics-flight-old",
            aircraft_id=aircraft_a.id,
            destination_airport_id=airport.id,
            identity_key=aircraft_a.identity_key,
            call_sign=aircraft_a.call_sign,
            model=aircraft_a.model,
            origin_airport_name="Santo Domingo",
            origin_airport_icao="MDSD",
            origin_airport_iata="SDQ",
            origin_country="Republica Dominicana",
            destination_airport_name="Jose Marti",
            destination_airport_icao="MUHA",
            destination_airport_iata="HAV",
            destination_country="Cuba",
            status="landed",
            last_seen_at_utc=now - timedelta(days=190),
            latest_latitude=22.6,
            latest_longitude=-82.3,
            last_source_kind="historic",
        )
        db.session.add_all([event_a, event_b, event_old])
        db.session.commit()

    start = (now - timedelta(days=7)).date().isoformat()
    end = now.date().isoformat()
    response = client.get(f"/api/v1/analytics?start={start}&end={end}")
    assert response.status_code == 200

    payload = response.get_json()
    assert payload is not None
    flights = payload["flights_origin_summary"]
    assert flights["total_flights"] == 2

    by_country = {item["country"]: item["count"] for item in flights["by_origin_country"]}
    assert by_country["USA"] == 1
    assert by_country["Mexico"] == 1
    assert "Republica Dominicana" not in by_country

    by_airport = {item["airport"]: item["count"] for item in flights["by_origin_airport"]}
    assert by_airport["Miami Intl"] == 1
    assert by_airport["Cancun Intl"] == 1
    assert "Santo Domingo" not in by_airport
