from datetime import datetime

from app.extensions import db


discussion_post_tags = db.Table(
    "discussion_post_tags",
    db.Column("post_id", db.Integer, db.ForeignKey("discussion_posts.id", ondelete="CASCADE"), primary_key=True),
    db.Column("tag_id", db.Integer, db.ForeignKey("discussion_tags.id", ondelete="CASCADE"), primary_key=True),
)


class DiscussionTag(db.Model):
    __tablename__ = "discussion_tags"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    slug = db.Column(db.String(80), nullable=False, unique=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    posts = db.relationship(
        "DiscussionPost",
        secondary=discussion_post_tags,
        back_populates="tags",
    )

    def __repr__(self):
        return f"<DiscussionTag {self.slug}>"
