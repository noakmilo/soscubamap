from datetime import datetime

from app.extensions import db
from app.models.category import Category
from app.models.post import Post
from app.models.user import User
from app.services.connectivity import STATUS_CRITICAL, STATUS_SEVERE
from app.tasks.connectivity import (
    AUTO_CONNECTIVITY_REPORT_DESCRIPTION_PREFIX,
    AUTO_CONNECTIVITY_REPORT_MARKER,
    AUTO_CONNECTIVITY_REPORT_TITLE_PREFIX,
    _geometry_center,
    _is_auto_connectivity_report,
    _resolve_province_center,
    _retire_recovered_auto_reports,
    _should_create_alert,
)


class TestShouldCreateAlert:
    def test_creates_for_severe(self):
        assert _should_create_alert(STATUS_SEVERE) is True

    def test_creates_for_critical(self):
        assert _should_create_alert(STATUS_CRITICAL) is True

    def test_does_not_create_for_non_alert_states(self):
        assert _should_create_alert("normal") is False


class TestGeometryCenter:
    def test_polygon_center(self):
        geometry = {
            "type": "Polygon",
            "coordinates": [[[-82.0, 22.0], [-80.0, 22.0], [-80.0, 24.0], [-82.0, 24.0], [-82.0, 22.0]]],
        }
        lat, lng = _geometry_center(geometry)
        assert round(lat, 4) == 23.0
        assert round(lng, 4) == -81.0

    def test_returns_none_for_invalid_geometry(self):
        lat, lng = _geometry_center({"type": "Point", "coordinates": [-82.0, 23.0]})
        assert lat is None
        assert lng is None


class TestResolveProvinceCenter:
    def test_prefers_geojson_center(self):
        center = _resolve_province_center("La Habana", {"la habana": (23.2, -82.2)})
        assert center == (23.2, -82.2)

    def test_fallback_when_geojson_missing(self):
        lat, lng = _resolve_province_center("La Habana", {})
        assert lat is not None
        assert lng is not None


class TestAutoConnectivityCleanup:
    def test_detects_auto_connectivity_report_by_marker(self, app):
        with app.app_context():
            post = Post(
                title="Cualquiera",
                description="Texto",
                latitude=23.1,
                longitude=-82.3,
                province="La Habana",
                movement_at=datetime.utcnow(),
                author_id=1,
                category_id=1,
                status="approved",
                is_anonymous=True,
                other_type=AUTO_CONNECTIVITY_REPORT_MARKER,
            )
            assert _is_auto_connectivity_report(post) is True

    def test_retires_only_recovered_auto_reports(self, app):
        with app.app_context():
            category = Category(
                name="Desconexion internet",
                slug="desconexion-internet",
            )
            bot_user = User(email="radar-bot@soscuba.local")
            bot_user.set_password("x")
            bot_user.ensure_anon_code()
            manual_user = User(email="manual@soscuba.local")
            manual_user.set_password("x")
            manual_user.ensure_anon_code()

            db.session.add_all([category, bot_user, manual_user])
            db.session.flush()

            active_auto = Post(
                title=f"{AUTO_CONNECTIVITY_REPORT_TITLE_PREFIX} Problemas severos en La Habana",
                description=f"{AUTO_CONNECTIVITY_REPORT_DESCRIPTION_PREFIX} Estado detectado: Problemas severos.",
                latitude=23.1,
                longitude=-82.3,
                province="La Habana",
                movement_at=datetime.utcnow(),
                author_id=bot_user.id,
                category_id=category.id,
                status="approved",
                is_anonymous=True,
                other_type=AUTO_CONNECTIVITY_REPORT_MARKER,
            )
            recovered_auto = Post(
                title=f"{AUTO_CONNECTIVITY_REPORT_TITLE_PREFIX} Apagon o conectividad critica en Matanzas",
                description=f"{AUTO_CONNECTIVITY_REPORT_DESCRIPTION_PREFIX} Estado detectado: Apagon o conectividad critica.",
                latitude=23.0,
                longitude=-81.6,
                province="Matanzas",
                movement_at=datetime.utcnow(),
                author_id=bot_user.id,
                category_id=category.id,
                status="approved",
                is_anonymous=True,
            )
            manual_report = Post(
                title="Desconexion reportada por usuario",
                description="Vecinos reportan inestabilidad intermitente.",
                latitude=23.0,
                longitude=-81.6,
                province="Matanzas",
                movement_at=datetime.utcnow(),
                author_id=manual_user.id,
                category_id=category.id,
                status="approved",
                is_anonymous=True,
            )
            db.session.add_all([active_auto, recovered_auto, manual_report])
            db.session.commit()

            retired = _retire_recovered_auto_reports(
                category.id,
                active_alert_provinces=["La Habana"],
                system_user_id=bot_user.id,
            )
            db.session.commit()

            assert len(retired) == 1
            assert retired[0].id == recovered_auto.id
            assert Post.query.get(active_auto.id).status == "approved"
            assert Post.query.get(recovered_auto.id).status == "deleted"
            assert Post.query.get(manual_report.id).status == "approved"
