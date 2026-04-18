from datetime import datetime

from app.extensions import db


class FlightAircraft(db.Model):
    __tablename__ = "flight_aircraft"

    id = db.Column(db.Integer, primary_key=True)
    identity_key = db.Column(db.String(255), nullable=False, unique=True, index=True)
    call_sign = db.Column(db.String(64), index=True)
    model = db.Column(db.String(120), index=True)
    registration = db.Column(db.String(64), index=True)
    hex_code = db.Column(db.String(32), index=True)
    operator_name = db.Column(db.String(255))
    manufacturer = db.Column(db.String(120))

    photo_api_url = db.Column(db.String(1000))
    photo_manual_url = db.Column(db.String(1000))
    photo_updated_at_utc = db.Column(db.DateTime)

    first_seen_at_utc = db.Column(db.DateTime, index=True)
    last_seen_at_utc = db.Column(db.DateTime, index=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        index=True,
    )

    events = db.relationship(
        "FlightEvent",
        back_populates="aircraft",
        cascade="all, delete-orphan",
    )
    photo_revisions = db.relationship(
        "FlightAircraftPhotoRevision",
        back_populates="aircraft",
        cascade="all, delete-orphan",
        order_by="FlightAircraftPhotoRevision.created_at.desc(), FlightAircraftPhotoRevision.id.desc()",
    )

    def __repr__(self):
        return f"<FlightAircraft {self.identity_key}>"
