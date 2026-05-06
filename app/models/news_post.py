from datetime import datetime

from app.extensions import db


class NewsPost(db.Model):
    __tablename__ = "news_posts"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(220), nullable=False)
    slug = db.Column(db.String(240), nullable=False, unique=True, index=True)
    author_name = db.Column(db.String(120), nullable=False)
    summary = db.Column(db.String(500), nullable=False)
    body = db.Column(db.Text, nullable=False)
    body_html = db.Column(db.Text, nullable=False)
    images_json = db.Column(db.Text)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    created_by = db.relationship("User")
    comments = db.relationship(
        "NewsComment",
        back_populates="post",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<NewsPost {self.id} {self.slug}>"
