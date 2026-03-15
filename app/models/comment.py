from datetime import datetime

from app.extensions import db


class Comment(db.Model):
    __tablename__ = "comments"

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("posts.id"), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    author_label = db.Column(db.String(60))
    body = db.Column(db.Text, nullable=False)

    upvotes = db.Column(db.Integer, default=0)
    downvotes = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    post = db.relationship("Post", backref="comments")
    author = db.relationship("User")

    def score(self):
        return (self.upvotes or 0) - (self.downvotes or 0)

    def __repr__(self):
        return f"<Comment {self.id} post={self.post_id}>"
