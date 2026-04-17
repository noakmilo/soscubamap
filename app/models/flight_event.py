from datetime import datetime

from app.extensions import db


class FlightEvent(db.Model):
    __tablename__ = "flight_events"

    id = db.Column(db.Integer, primary_key=True)
    event_key = db.Column(db.String(255), nullable=False, unique=True, index=True)
    external_flight_id = db.Column(db.String(128), index=True)

    aircraft_id = db.Column(
        db.Integer,
        db.ForeignKey("flight_aircraft.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    destination_airport_id = db.Column(
        db.Integer,
        db.ForeignKey("flight_airports.id", ondelete="SET NULL"),
        index=True,
    )
    ingestion_run_id = db.Column(
        db.Integer,
        db.ForeignKey("flight_ingestion_runs.id", ondelete="SET NULL"),
        index=True,
    )

    identity_key = db.Column(db.String(255), index=True)
    call_sign = db.Column(db.String(64), index=True)
    model = db.Column(db.String(120), index=True)
    registration = db.Column(db.String(64), index=True)

    origin_airport_icao = db.Column(db.String(8), index=True)
    origin_airport_iata = db.Column(db.String(8), index=True)
    origin_airport_name = db.Column(db.String(255))
    origin_country = db.Column(db.String(120))

    destination_airport_icao = db.Column(db.String(8), index=True)
    destination_airport_iata = db.Column(db.String(8), index=True)
    destination_airport_name = db.Column(db.String(255), index=True)
    destination_country = db.Column(db.String(120), index=True)

    status = db.Column(db.String(64), index=True)
    departure_at_utc = db.Column(db.DateTime, index=True)
    arrival_at_utc = db.Column(db.DateTime, index=True)
    first_seen_at_utc = db.Column(db.DateTime, index=True)
    last_seen_at_utc = db.Column(db.DateTime, index=True)

    latest_latitude = db.Column(db.Float, index=True)
    latest_longitude = db.Column(db.Float, index=True)
    latest_altitude = db.Column(db.Float)
    latest_speed = db.Column(db.Float)
    latest_heading = db.Column(db.Float)
    last_source_kind = db.Column(db.String(64), index=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        index=True,
    )

    aircraft = db.relationship("FlightAircraft", back_populates="events")
    destination_airport = db.relationship(
        "FlightAirport",
        back_populates="destination_events",
        foreign_keys=[destination_airport_id],
    )
    ingestion_run = db.relationship("FlightIngestionRun", back_populates="events")
    positions = db.relationship(
        "FlightPosition",
        back_populates="event",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<FlightEvent {self.event_key}>"
