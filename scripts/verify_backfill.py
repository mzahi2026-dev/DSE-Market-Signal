import json
from pathlib import Path
from backend.db import connect

log = Path("logs/backfill.jsonl")
records = []

if log.exists():
    for line in log.read_text(encoding="utf-8").splitlines():
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            pass

success = [
    r for r in records
    if r.get("symbol") == "GP"
    and r.get("status") == "success"
]

failed = [
    r for r in records
    if r.get("symbol") == "GP"
    and r.get("status") != "success"
]

with connect() as con:
    count, first, last = con.execute("""
        SELECT COUNT(*), MIN(date), MAX(date)
        FROM prices WHERE symbol = ?
    """, ("GP",)).fetchone()

    duplicates = con.execute("""
        SELECT COUNT(*) FROM (
            SELECT symbol, date, COUNT(*) AS n
            FROM prices
            WHERE symbol = ?
            GROUP BY symbol, date
            HAVING n > 1
        )
    """, ("GP",)).fetchone()[0]

print("\n=== BACKFILL VERIFICATION ===")
print("Successful log entries:", len(success))
print("Failed/empty log entries:", len(failed))
print("Database GP rows:", count)
print("First stored date:", first)
print("Last stored date:", last)
print("Duplicate records:", duplicates)

if duplicates == 0 and len(failed) == 0:
    print("PASS: Database integrity and log status")
else:
    print("REVIEW REQUIRED: Inspect failed batches")
