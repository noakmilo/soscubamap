from datetime import datetime

from app.extensions import db


class AISCubaTargetVessel(db.Model):
    __tablename__ = "ais_cuba_target_vessels"

    id = db.Column(db.Integer, primary_key=True)
    mmsi = db.Column(db.String(32), nullable=False, unique=True, index=True)
    ship_name = db.Column(db.String(255))
    imo = db.Column(db.String(32))
    call_sign = db.Column(db.String(64))
    vessel_type = db.Column(db.String(80))

    destination_raw = db.Column(db.String(255))
    destination_normalized = db.Column(db.String(255), index=True)
    matched_port_key = db.Column(db.String(64), index=True)
    matched_port_name = db.Column(db.String(128))
    match_confidence = db.Column(db.Float, nullable=False, default=0.0)
    match_reason = db.Column(db.String(120))

    latitude = db.Column(db.Float, index=True)
    longitude = db.Column(db.Float, index=True)
    sog = db.Column(db.Float)
    cog = db.Column(db.Float)
    heading = db.Column(db.Float)
    navigational_status = db.Column(db.String(64))
    source_message_type = db.Column(db.String(64))

    last_seen_at_utc = db.Column(db.DateTime, index=True)
    last_position_at_utc = db.Column(db.DateTime)
    last_static_at_utc = db.Column(db.DateTime)

    ingestion_run_id = db.Column(
        db.Integer,
        db.ForeignKey("ais_ingestion_runs.id", ondelete="SET NULL"),
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

    ingestion_run = db.relationship("AISIngestionRun", back_populates="vessels")

    def __repr__(self):
        return f"<AISCubaTargetVessel {self.mmsi} {self.ship_name or ''}>"
