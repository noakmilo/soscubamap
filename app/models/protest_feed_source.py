from datetime import datetime

from app.extensions import db


class ProtestFeedSource(db.Model):
    __tablename__ = "protest_feed_sources"

    id = db.Column(db.Integer, primary_key=True)
    feed_url = db.Column(db.String(1000), nullable=False, unique=True, index=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        index=True,
    )

    def __repr__(self):
        return f"<ProtestFeedSource {self.id} {self.feed_url}>"
