import json

from app.services.connectivity_geo import _load_geojson_from_disk


def _feature(name, key="NAME_1"):
    return {
        "type": "Feature",
        "properties": {key: name},
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [-82.5, 23.2],
                    [-82.4, 23.2],
                    [-82.4, 23.1],
                    [-82.5, 23.1],
                    [-82.5, 23.2],
                ]
            ],
        },
    }


def test_load_geojson_maps_historic_city_havana_alias(tmp_path):
    geojson_path = tmp_path / "provinces.geojson"
    payload = {
        "type": "FeatureCollection",
        "features": [
            _feature("CiudadDeLaHabana"),
            _feature("Matanzas"),
        ],
    }
    geojson_path.write_text(json.dumps(payload), encoding="utf-8")

    normalized = _load_geojson_from_disk(str(geojson_path), ["NAME_1"])
    names = [(feature.get("properties") or {}).get("province") for feature in normalized["features"]]

    assert "La Habana" in names
    assert "CiudadDeLaHabana" not in names


def test_load_geojson_maps_legacy_lahabana_to_artemisa_when_needed(tmp_path):
    geojson_path = tmp_path / "legacy_provinces.geojson"
    payload = {
        "type": "FeatureCollection",
        "features": [
            _feature("CiudadDeLaHabana"),
            _feature("LaHabana"),
            _feature("Mayabeque"),
        ],
    }
    geojson_path.write_text(json.dumps(payload), encoding="utf-8")

    normalized = _load_geojson_from_disk(str(geojson_path), ["NAME_1"])
    names = [(feature.get("properties") or {}).get("province") for feature in normalized["features"]]

    assert "La Habana" in names
    assert "Artemisa" in names
    assert "LaHabana" not in names


def test_load_geojson_does_not_remap_lahabana_if_artemisa_already_exists(tmp_path):
    geojson_path = tmp_path / "mixed_provinces.geojson"
    payload = {
        "type": "FeatureCollection",
        "features": [
            _feature("CiudadDeLaHabana"),
            _feature("LaHabana"),
            _feature("Artemisa"),
        ],
    }
    geojson_path.write_text(json.dumps(payload), encoding="utf-8")

    normalized = _load_geojson_from_disk(str(geojson_path), ["NAME_1"])
    names = [(feature.get("properties") or {}).get("province") for feature in normalized["features"]]

    assert names.count("Artemisa") == 1
