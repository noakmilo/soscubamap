import json
from datetime import datetime

from app.extensions import db


class Repressor(db.Model):
    __tablename__ = "repressors"

    id = db.Column(db.Integer, primary_key=True)
    external_id = db.Column(db.Integer, nullable=False, unique=True, index=True)

    name = db.Column(db.String(160), nullable=False, default="")
    lastname = db.Column(db.String(200), nullable=False, default="")
    nickname = db.Column(db.String(160))

    institution_name = db.Column(db.String(200))
    campus_name = db.Column(db.String(200))
    province_name = db.Column(db.String(120), index=True)
    municipality_name = db.Column(db.String(120), index=True)
    country_name = db.Column(db.String(120))

    image_source_url = db.Column(db.String(1000))
    image_cached_url = db.Column(db.String(1000))
    source_detail_url = db.Column(db.String(500))

    source_created_at = db.Column(db.DateTime)
    source_updated_at = db.Column(db.DateTime)
    source_status = db.Column(db.Integer)
    source_is_identifies = db.Column(db.String(60))
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

    crimes = db.relationship(
        "RepressorCrime",
        back_populates="repressor",
        cascade="all, delete-orphan",
        order_by="RepressorCrime.name.asc()",
    )
    types = db.relationship(
        "RepressorType",
        back_populates="repressor",
        cascade="all, delete-orphan",
        order_by="RepressorType.name.asc()",
    )
    residence_reports = db.relationship(
        "RepressorResidenceReport",
        back_populates="repressor",
        cascade="all, delete-orphan",
        order_by="RepressorResidenceReport.created_at.desc()",
    )
    submissions = db.relationship(
        "RepressorSubmission",
        back_populates="repressor",
        order_by="RepressorSubmission.created_at.desc()",
    )
    posts = db.relationship("Post", back_populates="repressor")

    @property
    def full_name(self):
        value = f"{self.name or ''} {self.lastname or ''}".strip()
        return value or f"Represor #{self.external_id}"

    @property
    def image_url(self):
        return (self.image_cached_url or self.image_source_url or "").strip() or None

    def __repr__(self):
        return f"<Repressor {self.id} ext={self.external_id} {self.full_name}>"


class RepressorCrime(db.Model):
    __tablename__ = "repressor_crimes"

    id = db.Column(db.Integer, primary_key=True)
    repressor_id = db.Column(
        db.Integer,
        db.ForeignKey("repressors.id"),
        nullable=False,
        index=True,
    )
    source_crime_id = db.Column(db.Integer, index=True)
    name = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    repressor = db.relationship("Repressor", back_populates="crimes")

    __table_args__ = (
        db.UniqueConstraint("repressor_id", "name", name="uq_repressor_crime_name"),
    )

    def __repr__(self):
        return f"<RepressorCrime {self.id} repressor={self.repressor_id}>"


class RepressorType(db.Model):
    __tablename__ = "repressor_types"

    id = db.Column(db.Integer, primary_key=True)
    repressor_id = db.Column(
        db.Integer,
        db.ForeignKey("repressors.id"),
        nullable=False,
        index=True,
    )
    source_type_id = db.Column(db.Integer, index=True)
    name = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    repressor = db.relationship("Repressor", back_populates="types")

    __table_args__ = (
        db.UniqueConstraint("repressor_id", "name", name="uq_repressor_type_name"),
    )

    def __repr__(self):
        return f"<RepressorType {self.id} repressor={self.repressor_id}>"


class RepressorIngestionRun(db.Model):
    __tablename__ = "repressor_ingestion_runs"

    id = db.Column(db.Integer, primary_key=True)
    started_at_utc = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    finished_at_utc = db.Column(db.DateTime, index=True)
    status = db.Column(db.String(24), nullable=False, default="running", index=True)

    scan_start_id = db.Column(db.Integer, nullable=False, default=1)
    scan_end_id = db.Column(db.Integer, nullable=False, default=3000)
    scanned_ids = db.Column(db.Integer, nullable=False, default=0)

    stored_items = db.Column(db.Integer, nullable=False, default=0)
    updated_items = db.Column(db.Integer, nullable=False, default=0)
    unchanged_items = db.Column(db.Integer, nullable=False, default=0)
    missing_items = db.Column(db.Integer, nullable=False, default=0)
    errors_count = db.Column(db.Integer, nullable=False, default=0)

    error_message = db.Column(db.Text)
    payload_json = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<RepressorIngestionRun {self.id} {self.status}>"


class RepressorResidenceReport(db.Model):
    __tablename__ = "repressor_residence_reports"

    id = db.Column(db.Integer, primary_key=True)
    repressor_id = db.Column(
        db.Integer,
        db.ForeignKey("repressors.id"),
        nullable=False,
        index=True,
    )
    status = db.Column(db.String(20), nullable=False, default="pending", index=True)

    reporter_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    reviewer_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)

    latitude = db.Column(db.Numeric(9, 6), nullable=False)
    longitude = db.Column(db.Numeric(9, 6), nullable=False)
    address = db.Column(db.String(255))
    province = db.Column(db.String(120), index=True)
    municipality = db.Column(db.String(120), index=True)
    message = db.Column(db.Text, nullable=False)
    evidence_links_json = db.Column(db.Text)
    source_image_url = db.Column(db.String(1000))

    created_post_id = db.Column(db.Integer, db.ForeignKey("posts.id"), index=True)

    rejection_reason = db.Column(db.Text)
    reviewed_at = db.Column(db.DateTime, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        index=True,
    )

    repressor = db.relationship("Repressor", back_populates="residence_reports")
    reporter = db.relationship("User", foreign_keys=[reporter_id])
    reviewer = db.relationship("User", foreign_keys=[reviewer_id])
    created_post = db.relationship("Post", foreign_keys=[created_post_id])

    def __repr__(self):
        return f"<RepressorResidenceReport {self.id} repressor={self.repressor_id} {self.status}>"


class RepressorSubmission(db.Model):
    __tablename__ = "repressor_submissions"

    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(20), nullable=False, default="pending", index=True)

    submitter_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    reviewer_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    repressor_id = db.Column(db.Integer, db.ForeignKey("repressors.id"), index=True)

    photo_url = db.Column(db.String(1000), nullable=False)
    name = db.Column(db.String(160), nullable=False, default="")
    lastname = db.Column(db.String(200))
    nickname = db.Column(db.String(160))
    institution_name = db.Column(db.String(200))
    campus_name = db.Column(db.String(200))
    province_name = db.Column(db.String(120), index=True)
    municipality_name = db.Column(db.String(120), index=True)

    crimes_json = db.Column(db.Text, nullable=False, default="[]")
    types_json = db.Column(db.Text, nullable=False, default="[]")
    note = db.Column(db.Text)
    payload_json = db.Column(db.Text)

    rejection_reason = db.Column(db.Text)
    reviewed_at = db.Column(db.DateTime, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        index=True,
    )

    submitter = db.relationship("User", foreign_keys=[submitter_id])
    reviewer = db.relationship("User", foreign_keys=[reviewer_id])
    repressor = db.relationship("Repressor", back_populates="submissions")

    @staticmethod
    def _parse_json_items(raw_value):
        if not raw_value:
            return []
        try:
            parsed = json.loads(raw_value)
        except Exception:
            return []
        if not isinstance(parsed, list):
            return []
        items = []
        seen = set()
        for item in parsed:
            text = str(item or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            items.append(text)
        return items

    @property
    def crimes_list(self):
        return self._parse_json_items(self.crimes_json)

    @property
    def types_list(self):
        return self._parse_json_items(self.types_json)

    @property
    def full_name(self):
        value = f"{self.name or ''} {self.lastname or ''}".strip()
        return value or "Represor sin nombre"

    def __repr__(self):
        return f"<RepressorSubmission {self.id} {self.status}>"
