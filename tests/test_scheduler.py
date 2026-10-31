import json
from fastapi.testclient import TestClient
from backend import collector
from backend.main import app, scheduler

def test_scheduler_registration():
    with TestClient(app):
        daily_job = scheduler.get_job("daily_dse")
        assert daily_job is not None
        assert str(daily_job.trigger.timezone) == "Asia/Dhaka"

        intraday_job = scheduler.get_job("hourly_intraday_dse")
        assert intraday_job is not None
        assert str(intraday_job.trigger.timezone) == "Asia/Dhaka"

def test_daily_collection(monkeypatch, tmp_path):
    calls = []

    def fake_collect(symbol, start, end):
        calls.append((symbol, start, end))
        return {
            "symbol": symbol,
            "fetched": 5,
            "inserted": 0
        }

    monkeypatch.setattr(
        collector, "collect", fake_collect
    )

    log = tmp_path / "daily.jsonl"
    result = collector.collect_daily(log_path=log)

    assert result["status"] == "success"
    assert len(calls) == 1
    assert calls[0][0] == "GP"
    assert log.exists()

    saved = json.loads(
        log.read_text(encoding="utf-8").strip()
    )
    assert saved["status"] == "success"

def test_empty_daily_result(monkeypatch, tmp_path):
    monkeypatch.setattr(
        collector,
        "collect",
        lambda *args: {
            "symbol": "GP",
            "fetched": 0,
            "inserted": 0
        }
    )

    log = tmp_path / "empty.jsonl"
    result = collector.collect_daily(log_path=log)

    assert result["status"] == "empty_unverified"

def test_failed_collection(monkeypatch, tmp_path):
    def fail(*args):
        raise RuntimeError("Source unavailable")

    monkeypatch.setattr(collector, "collect", fail)

    log = tmp_path / "failed.jsonl"

    try:
        collector.collect_daily(log_path=log)
    except RuntimeError:
        pass
    else:
        raise AssertionError("Failure not raised")

    saved = json.loads(
        log.read_text(encoding="utf-8").strip()
    )
    assert saved["status"] == "failed"


def test_daily_collection_multi_symbol(monkeypatch, tmp_path):
    collected = []
    monkeypatch.setattr(
        collector,
        "collect",
        lambda sym, s, e: collected.append(sym) or {"symbol": sym, "fetched": 5, "inserted": 5}
    )
    log = tmp_path / "multi.jsonl"
    res = collector.collect_daily(symbols=["GP", "BATBC", "SQURPHARMA"], log_path=log)
    assert res["status"] == "success"
    assert len(collected) == 3
    assert set(collected) == {"GP", "BATBC", "SQURPHARMA"}
    assert res["total_inserted"] == 15


def test_collect_intraday_execution(monkeypatch, tmp_path):
    import pandas as pd
    fake_df = pd.DataFrame([
        {"symbol": "GP", "ltp": 240.0, "high": 242.0, "low": 238.0, "close": 240.0, "ycp": 239.0, "volume": 10000},
        {"symbol": "BATBC", "ltp": 210.0, "high": 212.0, "low": 208.0, "close": 210.0, "ycp": 211.0, "volume": 5000}
    ])
    monkeypatch.setattr("bdshare.get_current_trade_data", lambda: fake_df)

    log = tmp_path / "intraday.jsonl"
    res = collector.collect_intraday(symbols=["GP", "BATBC"], log_path=log)
    assert res["status"] == "success"
    assert res["updated_symbols"] == 2
    assert "GP" in res["results"]
    assert res["results"]["GP"]["data"]["ltp"] == 240.0


def test_collect_intraday_manual_mode_skips():
    from backend.automation import set_automation_mode
    set_automation_mode("MANUAL")
    res = collector.collect_intraday(symbols=["GP"])
    assert res["status"] == "skipped"
    assert "MANUAL mode" in res["reason"]
    set_automation_mode("AUTO")
