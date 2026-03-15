from app import create_app
from app.extensions import db
from app.models.role import Role
from app.models.user import User

DEFAULT_ROLES = ["colaborador", "moderador", "administrador"]


def main():
    app = create_app()
    with app.app_context():
        for role_name in DEFAULT_ROLES:
            if not Role.query.filter_by(name=role_name).first():
                db.session.add(Role(name=role_name))
        db.session.commit()

        admin_email = input("Email para admin (enter para omitir): ").strip().lower()
        if admin_email:
            user = User.query.filter_by(email=admin_email).first()
            if not user:
                print("Usuario no existe.")
                return
            admin_role = Role.query.filter_by(name="administrador").first()
            if admin_role and admin_role not in user.roles:
                user.roles.append(admin_role)
                db.session.commit()
                print("Rol admin asignado.")

        print("Roles cargados.")


if __name__ == "__main__":
    main()
