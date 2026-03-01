from datetime import datetime

from app.extensions import db


class ChatPresence(db.Model):
    __tablename__ = "chat_presences"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(64), unique=True, nullable=False, index=True)
    nickname = db.Column(db.String(80), nullable=False)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow, index=True)

