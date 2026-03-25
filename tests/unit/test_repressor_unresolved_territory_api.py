from app.extensions import db
from app.models.repressor import Repressor, RepressorResidenceReport, RepressorType


def test_unresolved_territory_api_returns_only_unresolved_for_municipality(app, client):
    with app.app_context():
        unresolved = Repressor(
            external_id=91001,
            name="Carlos",
            lastname="Pendiente",
            province_name="La Habana",
            municipality_name="Playa",
        )
        unresolved.types.append(RepressorType(name="Violento"))

        resolved = Repressor(
            external_id=91002,
            name="Pedro",
            lastname="Resuelto",
            province_name="La Habana",
            municipality_name="Playa",
        )
        province_only = Repressor(
            external_id=91003,
            name="Marcos",
            lastname="Provincia",
            province_name="Matanzas",
            municipality_name=None,
        )
        db.session.add_all([unresolved, resolved, province_only])
        db.session.flush()

        report = RepressorResidenceReport(
            repressor_id=resolved.id,
            status="approved",
            latitude=23.1136,
            longitude=-82.3666,
            message="Reporte aprobado para excluirlo de no localizados.",
        )
        db.session.add(report)
        db.session.commit()

        unresolved_id = unresolved.id

    response = client.get(
        "/api/v1/repressors/unresolved-territory?scope=municipality&province=La%20Habana&municipality=Playa"
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload is not None
    assert payload["ok"] is True
    assert payload["scope"] == "municipality"
    assert payload["territory_label"] == "La Habana · Playa"
    assert payload["count"] == 1
    assert len(payload["items"]) == 1
    assert payload["items"][0]["id"] == unresolved_id
    assert payload["items"][0]["type_names"] == ["Violento"]


def test_unresolved_territory_api_province_scope_requires_missing_municipality(app, client):
    with app.app_context():
        province_only = Repressor(
            external_id=92001,
            name="Raul",
            lastname="SinMunicipio",
            province_name="Matanzas",
            municipality_name=None,
        )
        with_municipality = Repressor(
            external_id=92002,
            name="Ernesto",
            lastname="ConMunicipio",
            province_name="Matanzas",
            municipality_name="Cardenas",
        )
        db.session.add_all([province_only, with_municipality])
        db.session.commit()
        province_only_id = province_only.id

    response = client.get(
        "/api/v1/repressors/unresolved-territory?scope=province&province=Matanzas"
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload is not None
    assert payload["count"] == 1
    assert payload["items"][0]["id"] == province_only_id


def test_unresolved_territory_api_rejects_invalid_scope(client):
    response = client.get(
        "/api/v1/repressors/unresolved-territory?scope=country&province=La%20Habana"
    )
    assert response.status_code == 400
    payload = response.get_json()
    assert payload is not None
    assert payload["ok"] is False
