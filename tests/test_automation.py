import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.automation import (
    load_automation_state,
    set_automation_mode,
    get_automation_monitoring_status,
    execute_automation_cycle
)


def test_automation_mode_toggle():
    res_manual = set_automation_mode("MANUAL")
    assert res_manual["mode"] == "MANUAL"

    res_auto = set_automation_mode("AUTO")
    assert res_auto["mode"] == "AUTO"

    with pytest.raises(ValueError, match="Mode must be AUTO or MANUAL"):
        set_automation_mode("INVALID_MODE")


def test_automation_monitoring_status():
    status = get_automation_monitoring_status()
    assert "mode" in status
    assert "total_runs" in status
    assert "success_rate_pct" in status
    assert "retry_policy" in status


def test_api_automation_endpoints():
    with TestClient(app) as client:
        # Get status
        status_res = client.get("/automation/status")
        assert status_res.status_code == 200
        assert "mode" in status_res.json()

        # Set mode
        mode_res = client.post("/automation/mode?mode=MANUAL")
        assert mode_res.status_code == 200
        assert mode_res.json()["mode"] == "MANUAL"

        # Reset back to AUTO
        mode_auto = client.post("/automation/mode?mode=AUTO")
        assert mode_auto.status_code == 200
        assert mode_auto.json()["mode"] == "AUTO"

        # Logs endpoint with valid json record
        from backend.automation import RUNS_LOG, log_automation_run
        log_automation_run({"test_run": True, "status": "SUCCESS"})
        logs_res = client.get("/automation/logs")
        assert logs_res.status_code == 200
        assert "runs" in logs_res.json()
        assert any(r.get("test_run") is True for r in logs_res.json()["runs"])


def test_manual_mode_skips_scheduled_collection():
    from backend.collector import collect_daily
    set_automation_mode("MANUAL")
    res = collect_daily()
    assert res.get("status") == "skipped"
    assert "MANUAL mode" in res.get("reason", "")
    set_automation_mode("AUTO")


def test_automation_cycle_recovery_failure_marks_failed(monkeypatch):
    import backend.automation as auto

    def fake_collect(sym, s, e):
        return {"symbol": sym, "fetched": 5, "inserted": 0}

    def fake_audit(sym):
        return {"missing_trading_days": ["2026-10-28"]}

    def fake_recovery(symbol, execute, max_batches):
        return {"status": "failed", "failed_batches": 1}

    monkeypatch.setattr(auto, "collect", fake_collect)
    monkeypatch.setattr(auto, "audit", fake_audit)
    monkeypatch.setattr(auto, "run_recovery", fake_recovery)

    report = auto.execute_automation_cycle(symbols=["GP"])
    assert report["status"] == "FAILED"
    assert report["recoveries"]["GP"]["status"] == "failed"

