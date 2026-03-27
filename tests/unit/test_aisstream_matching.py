from app.services.aisstream import match_destination_to_cuba_ports, normalize_destination_text


def test_normalize_destination_text_removes_accents_and_symbols():
    assert normalize_destination_text("  La Habaña / Cuba ") == "LA HABANA CUBA"


def test_match_unlocode_exact_port():
    match = match_destination_to_cuba_ports("CUHAV")
    assert match["is_match"] is True
    assert match["port_key"] == "cuhav"
    assert match["port_name"] == "La Habana"


def test_match_alias_contains_port():
    match = match_destination_to_cuba_ports("Havana Cuba")
    assert match["is_match"] is True
    assert match["port_key"] == "cuhav"


def test_generic_cuba_needs_directional_data():
    match = match_destination_to_cuba_ports("CUBA")
    assert match["is_match"] is False
    assert match["reason"] == "generic_cuba_without_direction"


def test_generic_cuba_with_direction_matches_port():
    match = match_destination_to_cuba_ports(
        "CUBA",
        latitude=23.2,
        longitude=-83.5,
        cog=95,
        sog=12,
    )
    assert match["is_match"] is True
    assert match["port_key"] in {"cuhav", "cumar", "cuqma"}
    assert match["confidence"] >= 0.45
