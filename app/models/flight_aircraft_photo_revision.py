from datetime import datetime

from app.extensions import db


class FlightAircraftPhotoRevision(db.Model):
    __tablename__ = "flight_aircraft_photo_revisions"

    id = db.Column(db.Integer, primary_key=True)
    aircraft_id = db.Column(
        db.Integer,
        db.ForeignKey("flight_aircraft.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    uploader_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )
    photo_url = db.Column(db.String(1000), nullable=False)
    photo_source = db.Column(db.String(32), nullable=False, default="manual", index=True)
    uploader_anon_label = db.Column(db.String(80), nullable=False, default="Anon")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    aircraft = db.relationship("FlightAircraft", back_populates="photo_revisions")
    uploader = db.relationship("User", foreign_keys=[uploader_user_id])

    def __repr__(self):
        return f"<FlightAircraftPhotoRevision aircraft={self.aircraft_id} id={self.id}>"
