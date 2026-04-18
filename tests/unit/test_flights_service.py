from datetime import datetime

from app.services.flights import (
    DEFAULT_CUBA_LIVE_BOUNDS,
    RequestContext,
    _collect_backfill_records,
    _collect_live_records,
    _extract_items,
    _parse_event_row,
)


def test_collect_live_records_adds_bounds_selector_when_missing(monkeypatch):
    captured: dict[str, object] = {}

    def fake_query(
        path,
        base_params,
        preferred_paths,
        known_cuba_codes,
        source_kind,
        request_ctx,
        max_pages,
        force_destination_cuba=False,
    ):
        captured["path"] = path
        captured["base_params"] = dict(base_params)
        captured["source_kind"] = source_kind
        captured["max_pages"] = max_pages
        captured["force_destination_cuba"] = bool(force_destination_cuba)
        return type("Batch", (), {"records": [], "seen": 0, "errors": [], "budget_exhausted": False})()

    monkeypatch.setattr("app.services.flights.get_flights_live_filter_airports", lambda: "")
    monkeypatch.setattr("app.services.flights.get_flights_live_filter_bounds", lambda: "")
    monkeypatch.setattr("app.services.flights.get_flights_events_max_pages", lambda: 5)
    monkeypatch.setattr("app.services.flights.get_flights_safe_mode_events_max_pages", lambda: 2)
    monkeypatch.setattr("app.services.flights._query_events_from_endpoint", fake_query)

    request_ctx = RequestContext(request_cap=10, rate_limit_per_second=10)
    _collect_live_records(request_ctx, known_cuba_codes=set(), safe_mode=False)

    assert captured["source_kind"] == "live"
    assert captured["max_pages"] == 5
    assert captured["force_destination_cuba"] is False
    assert captured["base_params"] == {"light": 1, "bounds": DEFAULT_CUBA_LIVE_BOUNDS}


def test_collect_live_records_forces_destination_for_inbound_cuba_filter(monkeypatch):
    calls: list[dict[str, object]] = []

    def fake_query(
        path,
        base_params,
        preferred_paths,
        known_cuba_codes,
        source_kind,
        request_ctx,
        max_pages,
        force_destination_cuba=False,
    ):
        calls.append(
            {
                "base_params": dict(base_params),
                "force_destination_cuba": bool(force_destination_cuba),
            }
        )
        return type("Batch", (), {"records": [], "seen": 1, "errors": [], "budget_exhausted": False})()

    monkeypatch.setattr("app.services.flights.get_flights_live_filter_airports", lambda: "inbound:CU")
    monkeypatch.setattr("app.services.flights.get_flights_live_filter_bounds", lambda: "")
    monkeypatch.setattr("app.services.flights.get_flights_events_max_pages", lambda: 5)
    monkeypatch.setattr("app.services.flights.get_flights_safe_mode_events_max_pages", lambda: 2)
    monkeypatch.setattr("app.services.flights._query_events_from_endpoint", fake_query)

    request_ctx = RequestContext(request_cap=10, rate_limit_per_second=10)
    _collect_live_records(request_ctx, known_cuba_codes={"MUHA"}, safe_mode=False)

    assert len(calls) == 1
    assert calls[0]["force_destination_cuba"] is True
    assert calls[0]["base_params"] == {"light": 1, "airports": "inbound:CU"}


def test_collect_live_records_expands_country_filter_when_empty(monkeypatch):
    calls: list[dict[str, object]] = []

    def fake_query(
        path,
        base_params,
        preferred_paths,
        known_cuba_codes,
        source_kind,
        request_ctx,
        max_pages,
        force_destination_cuba=False,
    ):
        calls.append(
            {
                "base_params": dict(base_params),
                "force_destination_cuba": bool(force_destination_cuba),
            }
        )
        seen = 0 if len(calls) == 1 else 3
        return type("Batch", (), {"records": [], "seen": seen, "errors": [], "budget_exhausted": False})()

    monkeypatch.setattr("app.services.flights.get_flights_live_filter_airports", lambda: "inbound:CU")
    monkeypatch.setattr("app.services.flights.get_flights_live_filter_bounds", lambda: "")
    monkeypatch.setattr("app.services.flights.get_flights_events_max_pages", lambda: 5)
    monkeypatch.setattr("app.services.flights.get_flights_safe_mode_events_max_pages", lambda: 2)
    monkeypatch.setattr("app.services.flights._query_events_from_endpoint", fake_query)

    request_ctx = RequestContext(request_cap=10, rate_limit_per_second=10)
    _collect_live_records(request_ctx, known_cuba_codes={"MUHA", "MUVR"}, safe_mode=False)

    assert len(calls) == 2
    assert calls[0]["base_params"] == {"light": 1, "airports": "inbound:CU"}
    assert calls[0]["force_destination_cuba"] is True
    assert calls[1]["base_params"] == {"light": 1, "airports": "inbound:MUHA,inbound:MUVR"}
    assert calls[1]["force_destination_cuba"] is True


def test_collect_backfill_records_warns_when_historic_disabled(monkeypatch):
    monkeypatch.setattr("app.services.flights.get_flights_backfill_historic_enabled", lambda: False)
    request_ctx = RequestContext(request_cap=10, rate_limit_per_second=10)
    batch = _collect_backfill_records(request_ctx, known_cuba_codes=set(), days=7)

    assert batch.seen == 0
    assert batch.records == []
    assert batch.budget_exhausted is False
    assert batch.errors
    assert "Backfill historico desactivado" in batch.errors[0]


def test_collect_backfill_records_uses_historic_positions(monkeypatch):
    calls: list[dict[str, object]] = []

    def fake_query(
        path,
        base_params,
        preferred_paths,
        known_cuba_codes,
        source_kind,
        request_ctx,
        max_pages,
        force_destination_cuba=False,
    ):
        calls.append(
            {
                "path": path,
                "base_params": dict(base_params),
                "source_kind": source_kind,
                "force_destination_cuba": bool(force_destination_cuba),
                "max_pages": max_pages,
            }
        )
        return type(
            "Batch",
            (),
            {"records": [{"event_key": "x1"}], "seen": 2, "errors": [], "budget_exhausted": False},
        )()

    monkeypatch.setattr("app.services.flights.get_flights_backfill_historic_enabled", lambda: True)
    monkeypatch.setattr("app.services.flights.get_flights_backfill_chunk_hours", lambda: 24)
    monkeypatch.setattr("app.services.flights.get_flights_events_max_pages", lambda: 5)
    monkeypatch.setattr("app.services.flights.get_flights_live_filter_airports", lambda: "inbound:CU")
    monkeypatch.setattr("app.services.flights.get_flights_live_filter_bounds", lambda: "")
    monkeypatch.setattr(
        "app.services.flights.get_flights_historic_positions_light_path",
        lambda: "/historic/flight-positions/light",
    )
    monkeypatch.setattr(
        "app.services.flights._utc_now_naive",
        lambda: datetime(2026, 4, 18, 12, 0, 0),
    )
    monkeypatch.setattr("app.services.flights._query_events_from_endpoint", fake_query)

    request_ctx = RequestContext(request_cap=30, rate_limit_per_second=10)
    batch = _collect_backfill_records(request_ctx, known_cuba_codes={"MUHA"}, days=1)

    assert calls
    assert calls[0]["path"] == "/historic/flight-positions/light"
    assert calls[0]["source_kind"] == "historic"
    assert calls[0]["max_pages"] == 5
    assert calls[0]["force_destination_cuba"] is True
    assert calls[0]["base_params"]["airports"] == "inbound:CU"
    assert isinstance(calls[0]["base_params"]["timestamp"], int)
    assert batch.seen == 2


def test_parse_event_row_supports_summary_style_fields():
    row = {
        "fr24_id": "fr123",
        "callsign": "AAL100",
        "type": "A21N",
        "reg": "N100AA",
        "orig_icao": "KMIA",
        "destination_icao": "MUHA",
        "last_seen": "2026-04-17T18:00:00",
        "lat": 22.99,
        "lon": -82.4,
        "flight_ended": False,
    }

    parsed = _parse_event_row(row, known_cuba_codes={"MUHA"}, source_kind="live")
    assert parsed is not None
    assert parsed["external_flight_id"] == "fr123"
    assert parsed["model"] == "A21N"
    assert parsed["registration"] == "N100AA"
    assert parsed["destination_airport_icao"] == "MUHA"
    assert parsed["status"] == "live"


def test_extract_items_accepts_dict_map_payload():
    payload = {
        "data": {
            "abc123": {"fr24_id": "abc123", "callsign": "AAL100", "lat": 22.0, "lon": -82.0},
            "def456": {"fr24_id": "def456", "callsign": "DLH1", "lat": 23.0, "lon": -81.0},
        }
    }

    rows = _extract_items(payload, ("positions", "flights", "data"))
    assert len(rows) == 2
    assert {row.get("fr24_id") for row in rows} == {"abc123", "def456"}
