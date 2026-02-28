from flask import render_template, redirect, url_for, request, flash, current_app
from flask_login import login_user, logout_user, login_required

from app.extensions import db
from app.models.user import User
from app.models.role import Role
from . import auth_bp


def _get_or_create_role(name):
    role = Role.query.filter_by(name=name).first()
    if not role:
        role = Role(name=name)
        db.session.add(role)
        db.session.commit()
    return role


@auth_bp.route("/registro", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Email y contraseña son obligatorios.", "error")
            return redirect(url_for("auth.register"))

        if User.query.filter_by(email=email).first():
            flash("Ese email ya está registrado.", "error")
            return redirect(url_for("auth.register"))

        user = User(email=email)
        user.set_password(password)
        user.ensure_anon_code()
        default_role = Role.query.filter_by(name="colaborador").first()
        if default_role:
            user.roles.append(default_role)
        db.session.add(user)
        db.session.commit()

        login_user(user)
        return redirect(url_for("map.dashboard"))

    return render_template("auth/register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()

        admin_email = current_app.config.get("ADMIN_EMAIL", "").strip().lower()
        admin_password = current_app.config.get("ADMIN_PASSWORD", "")
        if admin_email and admin_password and email == admin_email:
            if not user:
                user = User(email=email)
                user.set_password(admin_password)
                user.ensure_anon_code()
                admin_role = _get_or_create_role("administrador")
                user.roles.append(admin_role)
                db.session.add(user)
                db.session.commit()
            elif not user.has_role("administrador"):
                admin_role = _get_or_create_role("administrador")
                user.roles.append(admin_role)
                db.session.commit()

        if user and not user.anon_code:
            user.ensure_anon_code()
            db.session.commit()

        if not user or not user.check_password(password):
            flash("Credenciales inválidas.", "error")
            return redirect(url_for("auth.login"))

        login_user(user)
        return redirect(url_for("map.dashboard"))

    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("map.dashboard"))
