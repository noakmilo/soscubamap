from datetime import datetime

from app.extensions import db


class NewsComment(db.Model):
    __tablename__ = "news_comments"

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("news_posts.id"), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("news_comments.id", ondelete="CASCADE"))
    body = db.Column(db.Text, nullable=False)
    body_html = db.Column(db.Text, nullable=False)
    author_label = db.Column(db.String(80), nullable=False)
    upvotes = db.Column(db.Integer, default=0)
    downvotes = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    post = db.relationship("NewsPost", back_populates="comments")
    children = db.relationship(
        "NewsComment",
        cascade="all, delete-orphan",
        single_parent=True,
        passive_deletes=True,
        backref=db.backref("parent", remote_side=[id]),
    )

    @property
    def score(self):
        return (self.upvotes or 0) - (self.downvotes or 0)

    def __repr__(self):
        return f"<NewsComment {self.id}>"
