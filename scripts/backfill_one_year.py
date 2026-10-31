"""DSE 1-Year Full Historical Backfill Runner.

Collects continuous daily OHLCV prices from 2025-11-02 to 2026-11-01 (1 full year)
for all configured DSE symbols: GP, BATBC, BEXIMCO, ROBI, SQURPHARMA.
"""

import io
import sys
import time
from datetime import date, timedelta
from pathlib import Path

# Force UTF-8 stdout
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.db import connect
from backend.collector import collect, get_configured_symbols
from scripts.backfill import make_batches, subtract_months


def backfill_one_year():
    symbols = get_configured_symbols()
    today = date(2026, 11, 1)
    # First trading day of November 2025 (Nov 1 2025 was Saturday)
    target_start = date(2025, 11, 2)
    target_end = today

    print(f"=== STARTING 1-YEAR HISTORICAL DSE BACKFILL ===")
    print(f"Target Horizon: {target_start} to {target_end} (1 Full Year)")
    print(f"Target Symbols: {symbols}\n", flush=True)

    total_inserted_all = 0
    total_batches_all = 0

    for sym in symbols:
        with connect() as con:
            row = con.execute("SELECT MIN(date), MAX(date), COUNT(*) FROM prices WHERE symbol=?", (sym,)).fetchone()
        curr_min = date.fromisoformat(row[0]) if row and row[0] else None
        curr_max = date.fromisoformat(row[1]) if row and row[1] else None
        curr_cnt = row[2] if row else 0

        print(f"\n--- Processing {sym} ---", flush=True)
        print(f"Current DB Range: {curr_min} to {curr_max} ({curr_cnt} days)", flush=True)

        if curr_min and curr_min <= target_start:
            print(f"[OK] {sym} already has data back to {curr_min} (>= 1 year). Skipping.", flush=True)
            continue

        # Need backfill from target_start up to (curr_min - 1 day)
        backfill_end = (curr_min - timedelta(days=1)) if curr_min else target_end
        batches = make_batches(target_start, backfill_end)
        print(f"Missing Horizon: {target_start} to {backfill_end} ({len(batches)} batches of 7 days)", flush=True)

        sym_inserted = 0
        for i, (b_start, b_end) in enumerate(batches, 1):
            with connect() as con:
                has_rec = con.execute(
                    "SELECT 1 FROM prices WHERE symbol=? AND date BETWEEN ? AND ? LIMIT 1",
                    (sym, str(b_start), str(b_end))
                ).fetchone()

            if has_rec:
                print(f"  [{i}/{len(batches)}] Batch {b_start} to {b_end} already in DB. Skipping.", flush=True)
                continue

            print(f"  [{i}/{len(batches)}] Fetching {sym}: {b_start} to {b_end} ...", end=" ", flush=True)
            try:
                res = collect(sym, str(b_start), str(b_end))
                ins = res.get("inserted", 0)
                sym_inserted += ins
                total_inserted_all += ins
                total_batches_all += 1
                print(f"DONE (+{ins} records)", flush=True)
            except Exception as exc:
                print(f"SKIPPED/FAILED ({exc})", flush=True)

            time.sleep(0.3)

        print(f"[OK] {sym} complete: inserted {sym_inserted} new historical records.", flush=True)

    # Final Summary
    with connect() as con:
        print("\n=== 1-YEAR BACKFILL FINISHED: FINAL DATABASE VERIFICATION ===", flush=True)
        for sym in symbols:
            row = con.execute("SELECT COUNT(*), MIN(date), MAX(date) FROM prices WHERE symbol=?", (sym,)).fetchone()
            print(f"{sym}: {row[0]} trading days | {row[1]} to {row[2]}", flush=True)
        total = con.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
        print(f"\nTOTAL ALL RECORDS IN DATABASE: {total}", flush=True)
        print(f"Total newly inserted in this run: {total_inserted_all} across {total_batches_all} batches.", flush=True)


if __name__ == "__main__":
    backfill_one_year()
