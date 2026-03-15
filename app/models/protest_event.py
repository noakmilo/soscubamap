from datetime import datetime

from app.extensions import db


class ProtestEvent(db.Model):
    __tablename__ = "protest_events"

    id = db.Column(db.Integer, primary_key=True)
    source_feed = db.Column(db.String(1000), nullable=False, default="", index=True)
    source_name = db.Column(db.String(255), nullable=False, default="", index=True)
    source_guid = db.Column(db.String(1000), index=True)
    source_url = db.Column(db.String(2000), nullable=False, default="", index=True)
    source_platform = db.Column(db.String(64), nullable=False, default="web", index=True)
    source_author = db.Column(db.String(255))
    source_published_at_utc = db.Column(db.DateTime, nullable=False, index=True)
    published_day_utc = db.Column(db.Date, nullable=False, index=True)

    raw_title = db.Column(db.Text, nullable=False, default="")
    raw_description = db.Column(db.Text, nullable=False, default="")
    clean_text = db.Column(db.Text, nullable=False, default="")
    detected_keywords_json = db.Column(db.Text, nullable=False, default="{}")

    matched_place_text = db.Column(db.String(255))
    matched_feature_type = db.Column(db.String(32), index=True)
    matched_feature_name = db.Column(db.String(255))
    matched_province = db.Column(db.String(120), index=True)
    matched_municipality = db.Column(db.String(120), index=True)
    matched_locality = db.Column(db.String(160), index=True)

    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    location_precision = db.Column(db.String(64), nullable=False, default="unresolved")

    confidence_score = db.Column(db.Float, nullable=False, default=0.0, index=True)
    event_type = db.Column(db.String(32), nullable=False, default="context_only", index=True)
    review_status = db.Column(db.String(32), nullable=False, default="auto", index=True)
    visible_on_map = db.Column(db.Boolean, nullable=False, default=False, index=True)

    dedupe_hash = db.Column(db.String(64), nullable=False, default="", index=True)
    related_group_hash = db.Column(db.String(64))
    transparency_note = db.Column(db.String(255), nullable=False, default="")

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        index=True,
    )

    __table_args__ = (
        db.UniqueConstraint("source_feed", "source_guid", name="uq_protest_feed_guid"),
    )

    def __repr__(self):
        return f"<ProtestEvent {self.id} {self.event_type} {self.source_published_at_utc.isoformat()}>"
