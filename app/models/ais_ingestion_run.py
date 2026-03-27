from datetime import datetime

from app.extensions import db


class AISIngestionRun(db.Model):
    __tablename__ = "ais_ingestion_runs"

    id = db.Column(db.Integer, primary_key=True)
    scheduled_for_utc = db.Column(db.DateTime, index=True)
    started_at_utc = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    finished_at_utc = db.Column(db.DateTime, index=True)
    status = db.Column(db.String(24), nullable=False, default="running", index=True)
    total_messages = db.Column(db.Integer, nullable=False, default=0)
    position_messages = db.Column(db.Integer, nullable=False, default=0)
    static_messages = db.Column(db.Integer, nullable=False, default=0)
    matched_messages = db.Column(db.Integer, nullable=False, default=0)
    matched_vessels = db.Column(db.Integer, nullable=False, default=0)
    stale_removed = db.Column(db.Integer, nullable=False, default=0)
    error_message = db.Column(db.Text)
    payload_json = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    vessels = db.relationship(
        "AISCubaTargetVessel",
        back_populates="ingestion_run",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<AISIngestionRun {self.id} {self.status}>"
