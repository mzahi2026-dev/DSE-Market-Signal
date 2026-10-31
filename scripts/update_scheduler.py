from pathlib import Path
import re

file = Path("backend/collector.py")
source = file.read_text(encoding="utf-8-sig")

replacement = '''
def collect_daily():
    """Daily GP collection using a 7-day lookback."""
    import json
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from pathlib import Path

    now = datetime.now(ZoneInfo("Asia/Dhaka"))
    end = now.date()
    start = end - timedelta(days=6)

    log = Path(__file__).resolve().parent.parent / "logs" / "daily_collection.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "timestamp": now.isoformat(),
        "symbol": "GP",
        "start": str(start),
        "end": str(end)
    }

    try:
        result = collect("GP", str(start), str(end))
        record["result"] = result
        record["status"] = (
            "success" if result["fetched"] > 0
            else "empty_unverified"
        )
    except Exception as exc:
        record["status"] = "failed"
        record["error"] = str(exc)

    with log.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\\\\n")

    if record["status"] == "failed":
        raise RuntimeError(record["error"])

    return record
'''

# Correct escaped newline in generated Python source
replacement = replacement.replace(
    'json.dumps(record) + "\\\\n"',
    'json.dumps(record) + "\\n"'
)

pattern = r'(?m)^def collect_daily\(\):[\s\S]*$'

if len(re.findall(pattern, source)) != 1:
    raise SystemExit("Existing collect_daily function not found")

updated = re.sub(pattern, lambda match: replacement.strip() + "\n", source)
file.write_text(updated, encoding="utf-8")

print("Daily collection function updated")
