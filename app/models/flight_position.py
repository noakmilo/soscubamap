from datetime import datetime

from app.extensions import db


class FlightPosition(db.Model):
    __tablename__ = "flight_positions"

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(
        db.Integer,
        db.ForeignKey("flight_events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    observed_at_utc = db.Column(db.DateTime, nullable=False, index=True)
    latitude = db.Column(db.Float, nullable=False, index=True)
    longitude = db.Column(db.Float, nullable=False, index=True)
    altitude = db.Column(db.Float)
    speed = db.Column(db.Float)
    heading = db.Column(db.Float)
    source_kind = db.Column(db.String(64), nullable=False, default="live", index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    event = db.relationship("FlightEvent", back_populates="positions")

    __table_args__ = (
        db.UniqueConstraint(
            "event_id",
            "observed_at_utc",
            "source_kind",
            name="uq_flight_positions_event_observed_source",
        ),
    )

    def __repr__(self):
        return f"<FlightPosition event={self.event_id} at={self.observed_at_utc}>"
