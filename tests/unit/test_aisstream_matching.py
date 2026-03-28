from datetime import datetime

from app.services.aisstream import (
    DestinationDiagnostics,
    VesselState,
    _apply_static_fields,
    _update_state_from_message,
    match_destination_to_cuba_ports,
    normalize_destination_text,
)


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


def test_apply_static_fields_reads_destination_from_metadata_fallback():
    state = VesselState(mmsi="372003000")
    destination = _apply_static_fields(
        state=state,
        payload={"PartA": {"Name": "TEST VESSEL"}, "PartB": {}},
        metadata={"Destination": "CUHAV"},
        observed_at=datetime(2026, 3, 27, 23, 18, 25),
    )
    assert destination == "CUHAV"
    assert state.destination_raw == "CUHAV"


def test_destination_diagnostics_collects_static_destinations():
    state_cache = {}
    counters = {
        "total_messages": 0,
        "position_messages": 0,
        "static_messages": 0,
        "matched_messages": 0,
        "matched_vessels": 0,
        "stale_removed": 0,
        "parse_errors": 0,
    }
    diagnostics = DestinationDiagnostics(top_limit=5)
    message_obj = {
        "MessageType": "ShipStaticData",
        "MetaData": {
            "MMSI": "372003000",
            "Destination": "Havana Cuba",
            "time_utc": "2026-03-27T23:18:25Z",
        },
        "Message": {
            "ShipStaticData": {
                "PartA": {"Name": "TEST VESSEL"},
                "PartB": {},
            }
        },
    }

    _update_state_from_message(state_cache, message_obj, counters, diagnostics)
    payload = diagnostics.to_payload()

    assert counters["static_messages"] == 1
    assert payload["static_messages_total"] == 1
    assert payload["static_messages_with_destination"] == 1
    assert payload["static_messages_matched"] == 1
    assert payload["top_normalized_destinations"][0]["destination"] == "HAVANA CUBA"
    assert payload["match_reasons"][0]["reason"] in {"port_alias_exact", "port_alias_contains"}
