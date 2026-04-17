from datetime import datetime

from app.extensions import db


class FlightIngestionRun(db.Model):
    __tablename__ = "flight_ingestion_runs"

    id = db.Column(db.Integer, primary_key=True)
    scheduled_for_utc = db.Column(db.DateTime, index=True)
    started_at_utc = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    finished_at_utc = db.Column(db.DateTime, index=True)
    status = db.Column(db.String(24), nullable=False, default="running", index=True)

    is_backfill = db.Column(db.Boolean, nullable=False, default=False)
    backfill_days = db.Column(db.Integer, nullable=False, default=0)
    safe_mode = db.Column(db.Boolean, nullable=False, default=False)

    request_count = db.Column(db.Integer, nullable=False, default=0)
    estimated_credits = db.Column(db.Integer, nullable=False, default=0)
    airports_synced = db.Column(db.Integer, nullable=False, default=0)
    events_seen = db.Column(db.Integer, nullable=False, default=0)
    events_stored = db.Column(db.Integer, nullable=False, default=0)
    positions_stored = db.Column(db.Integer, nullable=False, default=0)

    error_message = db.Column(db.Text)
    payload_json = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    events = db.relationship(
        "FlightEvent",
        back_populates="ingestion_run",
        cascade="all, delete-orphan",
    )
    snapshots = db.relationship(
        "FlightLayerSnapshot",
        back_populates="ingestion_run",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<FlightIngestionRun {self.id} {self.status}>"
