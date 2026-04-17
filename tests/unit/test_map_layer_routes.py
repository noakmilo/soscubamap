from app.extensions import db
from app.models.role import Role
from app.models.user import User


def _login_admin(client, user_id: int) -> None:
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True


def test_dashboard_default_layer_mode(client):
    response = client.get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'data-initial-base-mode="map"' in html
    assert 'data-layer-route-template="/map=__layer__"' in html


def test_dashboard_repressors_layer_mode(client):
    response = client.get("/map=represores")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'data-initial-base-mode="repressors"' in html


def test_dashboard_connectivity_layer_mode(client):
    response = client.get("/map=conectividad")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'data-initial-base-mode="connectivity"' in html


def test_dashboard_satellite_layer_mode(client):
    response = client.get("/map=satelite")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'data-initial-base-mode="satellite"' in html


def test_dashboard_invalid_layer_falls_back_to_map(client):
    response = client.get("/map=loquesea")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'data-initial-base-mode="map"' in html


def test_dashboard_ais_layer_requires_admin(client):
    response = client.get("/map=buques")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'data-initial-base-mode="map"' in html


def test_dashboard_ais_layer_mode_for_admin(app, client):
    with app.app_context():
        admin_role = Role(name="administrador")
        admin_user = User(email="admin-ais@example.com")
        admin_user.set_password("test")
        admin_user.roles.append(admin_role)
        db.session.add_all([admin_role, admin_user])
        db.session.commit()
        admin_id = admin_user.id

    _login_admin(client, admin_id)
    response = client.get("/map=buques")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'data-initial-base-mode="ais"' in html


def test_dashboard_flights_layer_requires_admin(client):
    response = client.get("/map=vuelos")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'data-initial-base-mode="map"' in html


def test_dashboard_flights_layer_mode_for_admin(app, client):
    with app.app_context():
        admin_role = Role(name="administrador")
        admin_user = User(email="admin-flights@example.com")
        admin_user.set_password("test")
        admin_user.roles.append(admin_role)
        db.session.add_all([admin_role, admin_user])
        db.session.commit()
        admin_id = admin_user.id

    _login_admin(client, admin_id)
    response = client.get("/map=vuelos")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'data-initial-base-mode="flights"' in html
