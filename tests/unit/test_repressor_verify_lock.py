from app.extensions import db
from app.models.repressor import Repressor
from app.models.role import Role
from app.models.user import User


def _create_repressor(external_id: int, verify_count: int = 0) -> Repressor:
    repressor = Repressor(
        external_id=external_id,
        name="Represor",
        lastname=f"#{external_id}",
        verify_count=verify_count,
    )
    db.session.add(repressor)
    db.session.commit()
    return repressor


def _login_admin(client, user_id: int) -> None:
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True


def test_verify_repressor_only_counts_once_per_identity(app, client):
    with app.app_context():
        repressor = _create_repressor(98001)
        repressor_id = repressor.id

    first = client.post(f"/api/repressors/{repressor_id}/verify")
    assert first.status_code == 200
    first_payload = first.get_json()
    assert first_payload is not None
    assert first_payload["ok"] is True
    assert first_payload["verify_count"] == 1
    assert first_payload["locked"] is False

    second = client.post(f"/api/repressors/{repressor_id}/verify")
    assert second.status_code == 200
    second_payload = second.get_json()
    assert second_payload is not None
    assert second_payload["ok"] is False
    assert second_payload["verify_count"] == 1
    assert second_payload["locked"] is False

    with app.app_context():
        refreshed = db.session.get(Repressor, repressor_id)
        assert refreshed is not None
        assert refreshed.verify_count == 1


def test_verify_repressor_marks_locked_when_reaching_threshold(app, client):
    with app.app_context():
        repressor = _create_repressor(98002, verify_count=9)
        repressor_id = repressor.id

    response = client.post(f"/api/repressors/{repressor_id}/verify")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload is not None
    assert payload["ok"] is True
    assert payload["verify_count"] == 10
    assert payload["locked"] is True

    with app.app_context():
        refreshed = db.session.get(Repressor, repressor_id)
        assert refreshed is not None
        assert refreshed.verify_count == 10


def test_locked_repressor_cannot_open_edit_form(app, client):
    with app.app_context():
        repressor = _create_repressor(98003, verify_count=10)
        repressor_id = repressor.id

    response = client.get(f"/represores/{repressor_id}/editar", follow_redirects=True)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "ya no puede editarse ni reportarse" in html


def test_locked_repressor_cannot_be_deleted_even_by_admin(app, client):
    with app.app_context():
        admin_role = Role(name="administrador")
        admin_user = User(email="admin@example.com")
        admin_user.set_password("test")
        admin_user.roles.append(admin_role)
        db.session.add_all([admin_role, admin_user])
        repressor = _create_repressor(98004, verify_count=10)
        db.session.commit()
        repressor_id = repressor.id
        admin_id = admin_user.id

    _login_admin(client, admin_id)

    response = client.post(
        f"/represores/{repressor_id}/eliminar",
        follow_redirects=True,
    )
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "no puede eliminarse" in html

    with app.app_context():
        assert db.session.get(Repressor, repressor_id) is not None
