from datetime import date
from backend.calendar import is_dse_weekend, is_trading_day
from scripts.gap_audit import audit


def test_gap_audit_structure():
    result = audit(today=date(2026, 10, 31))

    assert result["symbol"] == "GP"
    assert result["start"] == "2026-04-30"
    assert result["end"] == "2026-10-30"
    assert result["expected_batches"] == 27
    assert isinstance(result["weekday_gap_candidates"], list)
    assert isinstance(result["verified_holidays"], list)
    assert result["calendar_verified"] is True


def test_sunday_thursday_trading_calendar():
    # Friday & Saturday are weekends in Bangladesh
    friday = date(2026, 5, 1)
    saturday = date(2026, 5, 2)
    sunday = date(2026, 5, 3)
    thursday = date(2026, 5, 7)

    assert is_dse_weekend(friday) is True
    assert is_dse_weekend(saturday) is True
    assert is_dse_weekend(sunday) is False
    assert is_dse_weekend(thursday) is False

    # Sunday is an active trading day unless holiday
    assert is_trading_day(sunday) is True
    assert is_trading_day(thursday) is True
    assert is_trading_day(friday) is False


def test_gap_audit_calendar_verified_false_on_missing_days(monkeypatch):
    import scripts.gap_audit as gap
    monkeypatch.setattr(gap, "audit_trading_days", lambda stored, start, end: (["2026-05-03"], []))
    res = gap.audit(symbol="GP")
    assert res["missing_trading_days"] == ["2026-05-03"]
    assert res["calendar_verified"] is False
