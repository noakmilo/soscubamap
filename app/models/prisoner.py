import json
from datetime import datetime

from app.extensions import db


class Prisoner(db.Model):
    __tablename__ = "prisoners"

    id = db.Column(db.Integer, primary_key=True)
    external_id = db.Column(db.Integer, nullable=False, unique=True, index=True)

    name = db.Column(db.String(160), nullable=False, default="")
    lastname = db.Column(db.String(200), nullable=False, default="")
    gender_label = db.Column(db.String(120))
    detention_typology = db.Column(db.String(200))
    age_detention_label = db.Column(db.String(120))
    age_current_label = db.Column(db.String(120))

    province_name = db.Column(db.String(120), index=True)
    municipality_name = db.Column(db.String(120), index=True)
    prison_name = db.Column(db.String(200), index=True)
    prison_latitude = db.Column(db.Numeric(9, 6))
    prison_longitude = db.Column(db.Numeric(9, 6))
    prison_address = db.Column(db.String(255))

    detention_date = db.Column(db.String(50))
    offense_types = db.Column(db.Text)
    sentence_text = db.Column(db.String(300))
    medical_status = db.Column(db.String(300))
    penal_status = db.Column(db.String(300))
    observations = db.Column(db.Text)

    image_source_url = db.Column(db.String(1000))
    image_cached_url = db.Column(db.String(1000))
    source_detail_url = db.Column(db.String(500))

    source_created_at = db.Column(db.DateTime)
    source_updated_at = db.Column(db.DateTime)
    source_payload_json = db.Column(db.Text, nullable=False, default="{}")

    first_seen_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_synced_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
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

    revisions = db.relationship(
        "PrisonerRevision",
        back_populates="prisoner",
        cascade="all, delete-orphan",
        order_by="PrisonerRevision.created_at.desc()",
    )

    @property
    def full_name(self):
        value = f"{self.name or ''} {self.lastname or ''}".strip()
        return value or f"Prisionero #{self.external_id}"

    @property
    def image_url(self):
        return (self.image_cached_url or self.image_source_url or "").strip() or None

    def __repr__(self):
        return f"<Prisoner {self.id} ext={self.external_id} {self.full_name}>"


class PrisonerRevision(db.Model):
    __tablename__ = "prisoner_revisions"

    id = db.Column(db.Integer, primary_key=True)
    prisoner_id = db.Column(
        db.Integer,
        db.ForeignKey("prisoners.id"),
        nullable=False,
        index=True,
    )
    editor_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    editor_label = db.Column(db.String(120))
    reason = db.Column(db.Text)

    name = db.Column(db.String(160), nullable=False, default="")
    lastname = db.Column(db.String(200))
    gender_label = db.Column(db.String(120))
    detention_typology = db.Column(db.String(200))
    age_detention_label = db.Column(db.String(120))
    age_current_label = db.Column(db.String(120))
    province_name = db.Column(db.String(120), index=True)
    municipality_name = db.Column(db.String(120), index=True)
    prison_name = db.Column(db.String(200), index=True)
    prison_latitude = db.Column(db.Numeric(9, 6))
    prison_longitude = db.Column(db.Numeric(9, 6))
    prison_address = db.Column(db.String(255))
    detention_date = db.Column(db.String(50))
    offense_types = db.Column(db.Text)
    sentence_text = db.Column(db.String(300))
    medical_status = db.Column(db.String(300))
    penal_status = db.Column(db.String(300))
    observations = db.Column(db.Text)
    image_url = db.Column(db.String(1000))
    payload_json = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    prisoner = db.relationship("Prisoner", back_populates="revisions")
    editor = db.relationship("User", foreign_keys=[editor_id])

    @property
    def full_name(self):
        value = f"{self.name or ''} {self.lastname or ''}".strip()
        return value or "Prisionero sin nombre"

    def payload(self):
        raw = self.payload_json
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def __repr__(self):
        return f"<PrisonerRevision {self.id} prisoner={self.prisoner_id}>"
