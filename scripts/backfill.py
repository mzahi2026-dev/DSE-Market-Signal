import argparse
import calendar
import json
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.collector import collect, get_configured_symbols
LOG = ROOT / "logs" / "backfill.jsonl"

def subtract_months(day, months=6):
    year = day.year
    month = day.month - months
    while month <= 0:
        month += 12
        year -= 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(day.day, last_day))

def make_batches(start, end):
    batches = []
    current = start
    while current <= end:
        batch_end = min(current + timedelta(days=6), end)
        batches.append((current, batch_end))
        current = batch_end + timedelta(days=1)
    return batches

def completed_batches(symbol):
    done = set()
    if not LOG.exists():
        return done
    for line in LOG.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
            if (r.get("symbol") == symbol
                and r.get("status") == "success"
                and r.get("fetched", 0) > 0):
                done.add((r["start"], r["end"]))
        except (ValueError, KeyError, TypeError):
            pass
    return done

def write_log(record):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    record["timestamp"] = datetime.now().isoformat()
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

def backfill_symbol(symbol: str, execute: bool = False, max_batches: int = 2):
    symbol = symbol.upper().strip()
    end = date.today() - timedelta(days=1)
    start = subtract_months(end, 6)

    batches = make_batches(start, end)
    done = completed_batches(symbol)
    pending = [
        (a, b) for a, b in batches
        if (str(a), str(b)) not in done
    ]

    print(f"\n=== DSE 6-MONTH BACKFILL: {symbol} ===")
    print("Range:", start, "to", end)
    print("Total batches:", len(batches))
    print("Pending batches:", len(pending))
    print("Mode:", "EXECUTE" if execute else "DRY RUN")

    selected = pending[:max_batches]

    for i, (a, b) in enumerate(selected, 1):
        print(f"\nBatch {i}/{len(selected)}: {a} to {b}")

        if not execute:
            print("DRY RUN - no request")
            continue

        try:
            result = collect(symbol, str(a), str(b))
            status = (
                "success" if result["fetched"] > 0
                else "empty_unverified"
            )
            write_log({
                "symbol": symbol,
                "start": str(a),
                "end": str(b),
                "status": status,
                "fetched": result["fetched"],
                "inserted": result["inserted"]
            })
            print("Result:", result)

            if status != "success":
                print("WARNING: Empty batch encountered")

        except Exception as exc:
            write_log({
                "symbol": symbol,
                "start": str(a),
                "end": str(b),
                "status": "failed",
                "error": str(exc)
            })
            print("FAILED:", exc)

        if i < len(selected):
            time.sleep(2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="GP")
    parser.add_argument("--all-symbols", action="store_true", help="Backfill all configured symbols")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--max-batches", type=int, default=2)
    args = parser.parse_args()

    if args.max_batches < 1:
        parser.error("max-batches must be positive")

    if args.all_symbols:
        symbols = get_configured_symbols()
    else:
        if not args.symbol.isalnum() or len(args.symbol) > 20:
            parser.error("Invalid symbol")
        symbols = [args.symbol]

    for sym in symbols:
        backfill_symbol(sym, execute=args.execute, max_batches=args.max_batches)

    print("\nBACKFILL RUN COMPLETE")

if __name__ == "__main__":
    main()
