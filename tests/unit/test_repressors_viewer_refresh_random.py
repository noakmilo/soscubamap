import re

from app.extensions import db
from app.models.repressor import Repressor


def _extract_repressor_id(html: str) -> int | None:
    match = re.search(r'data-repressor-id="(\d+)"', html or "")
    if not match:
        return None
    return int(match.group(1))


def test_repressors_viewer_refresh_shows_different_repressor_when_possible(app, client):
    with app.app_context():
        db.session.add_all(
            [
                Repressor(external_id=99101, name="A", lastname="Uno"),
                Repressor(external_id=99102, name="B", lastname="Dos"),
            ]
        )
        db.session.commit()

    first = client.get("/represores/visor")
    assert first.status_code == 200
    first_id = _extract_repressor_id(first.get_data(as_text=True))
    assert first_id is not None

    refreshed = client.get("/represores/visor")
    assert refreshed.status_code == 200
    refreshed_id = _extract_repressor_id(refreshed.get_data(as_text=True))
    assert refreshed_id is not None
    assert refreshed_id != first_id
