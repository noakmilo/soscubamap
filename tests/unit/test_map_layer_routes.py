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
