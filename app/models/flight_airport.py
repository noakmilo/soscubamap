from datetime import datetime

from app.extensions import db


class FlightAirport(db.Model):
    __tablename__ = "flight_airports"

    id = db.Column(db.Integer, primary_key=True)
    code_key = db.Column(db.String(32), nullable=False, unique=True, index=True)
    fr_airport_id = db.Column(db.String(64), index=True)
    airport_code_icao = db.Column(db.String(8), index=True)
    airport_code_iata = db.Column(db.String(8), index=True)
    name = db.Column(db.String(255), nullable=False)
    city = db.Column(db.String(120))
    province = db.Column(db.String(120))
    country_code = db.Column(db.String(8), index=True)
    country_name = db.Column(db.String(120))
    latitude = db.Column(db.Float, index=True)
    longitude = db.Column(db.Float, index=True)
    is_cuba = db.Column(db.Boolean, nullable=False, default=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        index=True,
    )

    destination_events = db.relationship(
        "FlightEvent",
        back_populates="destination_airport",
        foreign_keys="FlightEvent.destination_airport_id",
    )

    def __repr__(self):
        return f"<FlightAirport {self.code_key} {self.name}>"
