import argparse
import json
import logging
import sys
import time
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.collector import collect, get_configured_symbols
from scripts.backfill import make_batches, subtract_months
BACKFILL_LOG = ROOT / "logs" / "backfill.jsonl"
RECOVERY_LOG = ROOT / "logs" / "recovery.jsonl"

logger = logging.getLogger("dse.recovery")


def load_records(path):
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def pending_batches(symbol, start, end, log_path=BACKFILL_LOG):
    expected = make_batches(start, end)
    completed = set()

    for r in load_records(log_path):
        if (
            r.get("symbol") == symbol
            and r.get("status") == "success"
            and r.get("fetched", 0) > 0
        ):
            completed.add((r.get("start"), r.get("end")))

    return [
        (a, b) for a, b in expected
        if (str(a), str(b)) not in completed
    ]


def retryable(exc):
    message = str(exc).lower()

    # Do not retry authorization/access errors
    if any(code in message for code in (
        "403", "401", "429", "forbidden",
        "unauthorized", "permission denied"
    )):
        return False

    return isinstance(exc, (
        TimeoutError,
        ConnectionError
    ))


def collect_with_retry(symbol, start, end,
                       max_attempts=2, delay=5,
                       fetcher=None, sleeper=None):
    if fetcher is None:
        fetcher = collect
    if sleeper is None:
        sleeper = time.sleep

    for attempt in range(1, max_attempts + 1):
        try:
            return fetcher(symbol, start, end)
        except Exception as exc:
            if attempt >= max_attempts or not retryable(exc):
                raise
            print(f"Temporary error; retry {attempt}/{max_attempts}")
            sleeper(delay)


def append_log(record, path=RECOVERY_LOG):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def run_recovery(symbol="GP", execute=False, max_batches=2, log_path=RECOVERY_LOG, backfill_log=BACKFILL_LOG, fetcher=None):
    """Controlled missing-data recovery."""
    symbol = symbol.upper().strip()
    end = date.today() - timedelta(days=1)
    start = subtract_months(end, 6)
    pending = pending_batches(symbol, start, end, log_path=backfill_log)

    report = {
        "symbol": symbol,
        "pending_batches": [(str(a), str(b)) for a, b in pending],
        "executed": execute,
        "processed": []
    }

    if not pending or not execute:
        return report

    selected = pending[:max_batches]
    for a, b in selected:
        try:
            result = collect_with_retry(symbol, str(a), str(b), fetcher=fetcher)
            status = "success" if result["fetched"] > 0 else "empty_unverified"
            record = {
                "symbol": symbol,
                "start": str(a),
                "end": str(b),
                "status": status,
                "fetched": result["fetched"],
                "inserted": result["inserted"]
            }
            append_log(record, path=log_path)
            report["processed"].append(record)

            if status == "success":
                append_log(record, path=backfill_log)
        except Exception as exc:
            err_record = {
                "symbol": symbol,
                "start": str(a),
                "end": str(b),
                "status": "failed",
                "error": str(exc)
            }
            append_log(err_record, path=log_path)
            report["processed"].append(err_record)
            break

    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="GP")
    parser.add_argument("--all-symbols", action="store_true", help="Run recovery for all configured symbols")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--max-batches", type=int, default=2)
    args = parser.parse_args()

    if args.max_batches < 1:
        parser.error("max-batches must be positive")

    symbols = get_configured_symbols() if args.all_symbols else [args.symbol.upper().strip()]

    for symbol in symbols:
        if not symbol.isalnum() or len(symbol) > 20:
            print(f"Skipping invalid symbol: {symbol}")
            continue

        end = date.today() - timedelta(days=1)
        start = subtract_months(end, 6)
        pending = pending_batches(symbol, start, end)

        print(f"\n=== DSE RECOVERY CHECK: {symbol} ===")
        print("Unverified batch ranges:", len(pending))
        print("Mode:", "EXECUTE" if args.execute else "DRY RUN")

        if not pending:
            print("PASS: No incomplete logged batches")
            print("NOTE: Trading-day completeness verified")
            continue

        if not args.execute:
            for a, b in pending:
                print("Needs review:", a, "to", b)
            continue

        res = run_recovery(symbol=symbol, execute=True, max_batches=args.max_batches)
        print("Recovery result:", res)


if __name__ == "__main__":
    main()
