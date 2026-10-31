from datetime import date
from fastapi.testclient import TestClient
from backend.main import app, scheduler
from backend.calendar import is_dse_weekend, is_dse_holiday, is_trading_day, audit_trading_days
from backend.collector import is_permission_blocked
from backend.db import connect


def test_dse_sunday_thursday_trading_calendar():
    # Friday=4 and Saturday=5 must be weekends in Bangladesh
    assert is_dse_weekend(date(2026, 5, 1)) is True   # Friday
    assert is_dse_weekend(date(2026, 5, 2)) is True   # Saturday
    assert is_dse_weekend(date(2026, 5, 3)) is False  # Sunday (trading day)
    assert is_dse_weekend(date(2026, 5, 7)) is False  # Thursday (trading day)

    # Active trading day verification
    assert is_trading_day(date(2026, 5, 3)) is True
    assert is_trading_day(date(2026, 5, 1)) is False


def test_dse_holidays_verified():
    # Eid-ul-Adha holiday in May 2026
    assert is_dse_holiday(date(2026, 5, 26)) is True
    assert is_trading_day(date(2026, 5, 26)) is False

    # Half-yearly Bank holiday July 1
    assert is_dse_holiday(date(2026, 7, 1)) is True
    assert is_trading_day(date(2026, 7, 1)) is False


def test_recovery_status_endpoint():
    with TestClient(app) as client:
        res = client.get("/recovery/status?symbol=GP")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert "audit" in data
        assert data["audit"]["symbol"] == "GP"
        assert data["audit"]["calendar_verified"] is True
        assert len(data["audit"]["missing_trading_days"]) == 0


def test_scheduler_single_instance_and_timezone():
    with TestClient(app):
        jobs = scheduler.get_jobs()
        job_ids = [j.id for j in jobs]
        assert "daily_dse" in job_ids
        # Single job registration, no duplicate registrations
        assert job_ids.count("daily_dse") == 1
        job = scheduler.get_job("daily_dse")
        assert str(job.trigger.timezone) == "Asia/Dhaka"


def test_permission_error_detection_no_bypass():
    err403 = Exception("HTTP 403 Forbidden")
    assert is_permission_blocked(err403) is True

    err_auth = Exception("401 Unauthorized")
    assert is_permission_blocked(err_auth) is True

    err_normal = Exception("Connection reset by peer")
    assert is_permission_blocked(err_normal) is False


def test_database_integrity_preservation():
    with connect() as con:
        count = con.execute("SELECT COUNT(*) FROM prices WHERE symbol='GP'").fetchone()[0]
        duplicates = con.execute("""
            SELECT COUNT(*) FROM (
                SELECT symbol, date, COUNT(*) AS n
                FROM prices WHERE symbol='GP'
                GROUP BY symbol, date HAVING n > 1
            )
        """).fetchone()[0]

    assert count >= 122, "Original backfilled GP records must be preserved"
    assert duplicates == 0, "No duplicate records allowed"

