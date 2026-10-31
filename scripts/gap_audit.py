import json
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.db import connect
from backend.calendar import audit_trading_days, is_dse_weekend, is_dse_holiday
from scripts.backfill import make_batches, subtract_months
LOG = ROOT / "logs" / "backfill.jsonl"


def audit(symbol="GP", today=None, log_path=LOG):
    symbol = symbol.upper()
    today = today or date.today()

    end = today - timedelta(days=1)
    start = subtract_months(end, 6)
    expected_batches = make_batches(start, end)

    with connect() as con:
        rows = con.execute(
            """SELECT date FROM prices
               WHERE symbol=? AND date BETWEEN ? AND ?
               ORDER BY date""",
            (symbol, str(start), str(end))
        ).fetchall()

    stored = {r[0] for r in rows}

    missing_days, verified_holidays = audit_trading_days(stored, start, end)

    completed = set()
    if log_path.exists():
        for line in log_path.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
                if (
                    r.get("symbol") == symbol
                    and r.get("status") == "success"
                    and r.get("fetched", 0) > 0
                ):
                    completed.add((r.get("start"), r.get("end")))
            except (ValueError, TypeError):
                continue

    unverified = [
        (str(a), str(b))
        for a, b in expected_batches
        if (str(a), str(b)) not in completed
    ]

    return {
        "symbol": symbol,
        "start": str(start),
        "end": str(end),
        "stored_records": len(stored),
        "expected_batches": len(expected_batches),
        "unverified_batches": unverified,
        "missing_trading_days": missing_days,
        "verified_holidays": verified_holidays,
        "calendar_verified": len(missing_days) == 0,
        # Preserve backwards compatibility for tests
        "weekday_gap_candidates": missing_days
    }


def main():
    result = audit()
    print("\n=== DSE HISTORICAL DATA AUDIT (SUNDAY-THURSDAY CALENDAR) ===")
    print("Stock:", result["symbol"])
    print("Date range:", result["start"], "to", result["end"])
    print("Stored records:", result["stored_records"])
    print("Expected batches:", result["expected_batches"])
    print("Unverified batches:", len(result["unverified_batches"]))
    print("Verified official holidays in range:", len(result["verified_holidays"]))
    print("Genuine missing trading sessions:", len(result["missing_trading_days"]))

    if result["missing_trading_days"]:
        for day in result["missing_trading_days"]:
            print("GENUINE MISSING:", day)
    else:
        print("ALL TRADING DAYS VERIFIED AND ACCOUNTED FOR!")

    output = ROOT / "logs" / "gap_audit.json"
    output.write_text(
        json.dumps(result, indent=2),
        encoding="utf-8"
    )
    print("Report saved:", output)


if __name__ == "__main__":
    main()
