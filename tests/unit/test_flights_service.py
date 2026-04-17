from app.services.flights import (
    DEFAULT_CUBA_LIVE_BOUNDS,
    RequestContext,
    _collect_backfill_records,
    _collect_live_records,
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
    ):
        captured["path"] = path
        captured["base_params"] = dict(base_params)
        captured["source_kind"] = source_kind
        captured["max_pages"] = max_pages
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
    assert captured["base_params"] == {"light": 1, "bounds": DEFAULT_CUBA_LIVE_BOUNDS}


def test_collect_backfill_records_warns_when_historic_disabled(monkeypatch):
    monkeypatch.setattr("app.services.flights.get_flights_backfill_historic_enabled", lambda: False)
    request_ctx = RequestContext(request_cap=10, rate_limit_per_second=10)
    batch = _collect_backfill_records(request_ctx, known_cuba_codes=set(), days=7)

    assert batch.seen == 0
    assert batch.records == []
    assert batch.budget_exhausted is False
    assert batch.errors
    assert "Backfill historico desactivado" in batch.errors[0]


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
