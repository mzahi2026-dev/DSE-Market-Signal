import json
from datetime import date, datetime
from zoneinfo import ZoneInfo
from fastapi.testclient import TestClient

from backend.main import app
from backend import data_collection


def test_is_dse_market_hour_logic():
    dhaka_tz = ZoneInfo("Asia/Dhaka")

    # Sunday (trading day) at 11:30 BST -> inside market hours (10:00 - 14:30)
    sun_market = datetime(2026, 11, 1, 11, 30, tzinfo=dhaka_tz)
    assert data_collection.is_dse_market_hour(sun_market) is True

    # Friday (weekend) at 11:30 BST -> closed
    fri_time = datetime(2026, 10, 30, 11, 30, tzinfo=dhaka_tz)
    assert data_collection.is_dse_market_hour(fri_time) is False

    # Sunday after market close at 15:00 BST -> closed
    sun_after = datetime(2026, 11, 1, 15, 0, tzinfo=dhaka_tz)
    assert data_collection.is_dse_market_hour(sun_after) is False

    # Sunday before market open at 09:00 BST -> closed
    sun_before = datetime(2026, 11, 1, 9, 0, tzinfo=dhaka_tz)
    assert data_collection.is_dse_market_hour(sun_before) is False


def test_audit_symbol_gaps():
    # Audit for GP with a known date
    audit_res = data_collection.audit_symbol_gaps("GP", today=date(2026, 11, 2))
    assert audit_res["symbol"] == "GP"
    assert "has_data" in audit_res
    assert isinstance(audit_res["missing_trading_days"], list)


def test_gap_filling_catchup_execution(monkeypatch, tmp_path):
    collected_calls = []

    def fake_collect(symbol, start, end):
        collected_calls.append((symbol, start, end))
        return {"symbol": symbol, "fetched": 3, "inserted": 3}

    monkeypatch.setattr(data_collection, "collect", fake_collect)

    # Temporary state file
    temp_state = tmp_path / "collection_state.json"
    monkeypatch.setattr(data_collection, "STATE_FILE", temp_state)

    result = data_collection.run_gap_filling_catchup(symbols=["GP"])
    assert result["status"] in ("success", "partial_error")
    assert "symbols_checked" in result
    assert "gaps_detected" in result

    # Check state file persisted
    assert temp_state.exists()
    state = json.loads(temp_state.read_text(encoding="utf-8"))
    assert "last_startup_catchup" in state


def test_hourly_and_eod_collection_wrappers(monkeypatch, tmp_path):
    monkeypatch.setattr(
        data_collection,
        "collect_intraday",
        lambda symbols: {"status": "success", "updated_symbols": len(symbols)}
    )
    monkeypatch.setattr(
        data_collection,
        "collect_daily",
        lambda symbols: {"status": "success", "total_inserted": 5}
    )

    temp_state = tmp_path / "collection_state.json"
    monkeypatch.setattr(data_collection, "STATE_FILE", temp_state)

    # 1. Hourly intraday
    h_res = data_collection.collect_hourly_intraday(symbols=["GP"])
    assert h_res["status"] == "success"
    assert h_res["updated_symbols"] == 1

    # 2. Daily EOD
    e_res = data_collection.collect_daily_eod(symbols=["GP"])
    assert e_res["status"] == "success"
    assert e_res["total_inserted"] == 5

    # Check state recorded both
    state = json.loads(temp_state.read_text(encoding="utf-8"))
    assert state["last_hourly_run"]["status"] == "success"
    assert state["last_eod_run"]["status"] == "success"


def test_collection_api_endpoints(monkeypatch):
    monkeypatch.setattr(
        data_collection,
        "collect",
        lambda sym, a, b: {"symbol": sym, "fetched": 1, "inserted": 1}
    )
    monkeypatch.setattr(
        data_collection,
        "collect_intraday",
        lambda symbols: {"status": "success", "updated_symbols": len(symbols)}
    )
    monkeypatch.setattr(
        data_collection,
        "collect_daily",
        lambda symbols: {"status": "success", "total_inserted": 1}
    )
    with TestClient(app) as client:
        # GET /collection/status
        res = client.get("/collection/status")
        assert res.status_code == 200
        data = res.json()
        assert "engine" in data
        assert "configured_symbols" in data
        assert "GP" in data["configured_symbols"]
        assert "symbol_data_status" in data

        # POST /collection/run-hourly
        h_res = client.post("/collection/run-hourly?symbols=GP")
        assert h_res.status_code == 200

        # POST /collection/run-eod
        e_res = client.post("/collection/run-eod?symbols=GP")
        assert e_res.status_code == 200

        # POST /collection/run-gap-fill
        g_res = client.post("/collection/run-gap-fill?symbols=GP")
        assert g_res.status_code == 200
