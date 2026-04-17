from datetime import datetime

from app.extensions import db


class FlightLayerSnapshot(db.Model):
    __tablename__ = "flight_layer_snapshots"

    id = db.Column(db.Integer, primary_key=True)
    window_hours = db.Column(db.Integer, nullable=False, unique=True, index=True)
    generated_at_utc = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    stale_after_seconds = db.Column(db.Integer, nullable=False, default=3600)
    points_count = db.Column(db.Integer, nullable=False, default=0)
    summary_json = db.Column(db.Text)
    points_json = db.Column(db.Text)

    ingestion_run_id = db.Column(
        db.Integer,
        db.ForeignKey("flight_ingestion_runs.id", ondelete="SET NULL"),
        index=True,
    )

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        index=True,
    )

    ingestion_run = db.relationship("FlightIngestionRun", back_populates="snapshots")

    def __repr__(self):
        return f"<FlightLayerSnapshot {self.window_hours}h>"
