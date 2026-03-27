from datetime import datetime, timedelta

from app.extensions import db
from app.models.ais_cuba_target_vessel import AISCubaTargetVessel
from app.models.ais_ingestion_run import AISIngestionRun
from app.models.role import Role
from app.models.user import User


def _login_admin(client, user_id: int) -> None:
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True


def test_ais_layer_api_requires_admin(client):
    response = client.get("/api/v1/ais/cuba-targets")
    assert response.status_code == 403


def test_ais_layer_api_returns_points_for_admin(app, client):
    with app.app_context():
        admin_role = Role(name="administrador")
        admin_user = User(email="admin-ais-api@example.com")
        admin_user.set_password("test")
        admin_user.roles.append(admin_role)

        now = datetime.utcnow()
        run = AISIngestionRun(
            started_at_utc=now - timedelta(minutes=30),
            finished_at_utc=now - timedelta(minutes=5),
            status="success",
            total_messages=100,
            position_messages=70,
            static_messages=30,
            matched_messages=20,
            matched_vessels=3,
        )
        db.session.add_all([admin_role, admin_user, run])
        db.session.flush()

        vessel = AISCubaTargetVessel(
            mmsi="372003000",
            ship_name="TEST VESSEL",
            destination_raw="HAVANA",
            destination_normalized="HAVANA",
            matched_port_key="cuhav",
            matched_port_name="La Habana",
            match_confidence=0.91,
            match_reason="port_alias_exact",
            latitude=23.11,
            longitude=-82.35,
            sog=12.4,
            cog=102.2,
            last_seen_at_utc=now - timedelta(minutes=1),
            ingestion_run_id=run.id,
        )
        db.session.add(vessel)
        db.session.commit()

        admin_id = admin_user.id

    _login_admin(client, admin_id)
    response = client.get("/api/v1/ais/cuba-targets")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload is not None
    assert isinstance(payload.get("points"), list)
    assert len(payload["points"]) == 1
    assert payload["points"][0]["mmsi"] == "372003000"
    assert payload["points"][0]["matched_port_key"] == "cuhav"
    assert payload["latest_run"]["status"] == "success"
    assert payload["stale"] is False
