from app.services.connectivity import STATUS_CRITICAL, STATUS_SEVERE
from app.tasks.connectivity import (
    _geometry_center,
    _resolve_province_center,
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
