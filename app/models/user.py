import secrets
import string
from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db, login_manager

from .role import user_roles


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    anon_code = db.Column(db.String(6), unique=True, nullable=True, index=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    roles = db.relationship("Role", secondary=user_roles, backref="users")
    posts = db.relationship("Post", back_populates="author")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def has_role(self, name):
        return any(role.name == name for role in self.roles)

    def ensure_anon_code(self):
        if self.anon_code:
            return
        alphabet = string.ascii_uppercase + string.digits
        for _ in range(10):
            candidate = "".join(secrets.choice(alphabet) for _ in range(6))
            if not User.query.filter_by(anon_code=candidate).first():
                self.anon_code = candidate
                return
        self.anon_code = "".join(secrets.choice(alphabet) for _ in range(6))

    def __repr__(self):
        return f"<User {self.email}>"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))
