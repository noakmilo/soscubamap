from datetime import datetime

from app.extensions import db


class LocationReport(db.Model):
    __tablename__ = "location_reports"

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("posts.id"), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    post = db.relationship("Post", backref="location_reports")

    def __repr__(self):
        return f"<LocationReport {self.id} post={self.post_id}>"
