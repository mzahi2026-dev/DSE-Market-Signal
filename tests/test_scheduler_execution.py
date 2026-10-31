import json
import threading
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from backend import collector


def test_automatic_scheduler_execution(monkeypatch, tmp_path):
    finished = threading.Event()
    calls = []

    def fake_collect(symbol, start, end):
        calls.append((symbol, start, end))
        return {
            "symbol": symbol,
            "fetched": 5,
            "inserted": 0,
            "source": "mock"
        }

    monkeypatch.setattr(collector, "collect", fake_collect)

    log_path = tmp_path / "scheduled_execution.jsonl"

    scheduler = BackgroundScheduler(
        timezone=ZoneInfo("Asia/Dhaka")
    )

    def scheduled_job():
        try:
            collector.collect_daily(log_path=log_path)
        finally:
            finished.set()

    scheduler.add_job(
        scheduled_job,
        trigger="date",
        run_date=datetime.now(ZoneInfo("Asia/Dhaka")),
        id="execution_test"
    )

    try:
        scheduler.start()

        assert finished.wait(timeout=8), (
            "Scheduler did not execute within 8 seconds"
        )

        assert len(calls) == 1
        assert log_path.exists()

        records = [
            json.loads(line)
            for line in log_path.read_text(
                encoding="utf-8"
            ).splitlines()
        ]

        assert len(records) == 1
        assert records[0]["status"] == "success"
        assert records[0]["result"]["fetched"] == 5

        print("PASS: Scheduler executed automatically")
        print("PASS: Collection function called")
        print("PASS: Execution log created")

    finally:
        scheduler.shutdown(wait=True)
