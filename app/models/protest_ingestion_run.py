from datetime import datetime

from app.extensions import db


class ProtestIngestionRun(db.Model):
    __tablename__ = "protest_ingestion_runs"

    id = db.Column(db.Integer, primary_key=True)
    started_at_utc = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, index=True
    )
    finished_at_utc = db.Column(db.DateTime, index=True)
    status = db.Column(db.String(24), nullable=False, default="running", index=True)
    feed_count = db.Column(db.Integer, nullable=False, default=0)
    fetched_items = db.Column(db.Integer, nullable=False, default=0)
    parsed_items = db.Column(db.Integer, nullable=False, default=0)
    stored_items = db.Column(db.Integer, nullable=False, default=0)
    updated_items = db.Column(db.Integer, nullable=False, default=0)
    deduped_items = db.Column(db.Integer, nullable=False, default=0)
    hidden_items = db.Column(db.Integer, nullable=False, default=0)
    error_message = db.Column(db.Text)
    payload_json = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<ProtestIngestionRun {self.id} {self.status}>"
