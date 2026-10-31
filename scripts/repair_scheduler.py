import ast
from pathlib import Path

file = Path("backend/collector.py")
source = file.read_text(encoding="utf-8-sig")

tree = ast.parse(source)

functions = [
    node for node in tree.body
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    and node.name == "collect_daily"
]

if len(functions) != 1:
    raise SystemExit(
        "Expected exactly one collect_daily function. No changes made."
    )

node = functions[0]
lines = source.splitlines(keepends=True)

replacement = '''def collect_daily(log_path=None):
    import json
    from datetime import datetime
    from pathlib import Path
    from zoneinfo import ZoneInfo

    now = datetime.now(ZoneInfo("Asia/Dhaka"))
    end = now.date()
    start = end - timedelta(days=6)

    if log_path is None:
        log_path = (
            Path(__file__).resolve().parent.parent
            / "logs" / "daily_collection.jsonl"
        )

    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

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

    with log_path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record) + chr(10))

    if record["status"] == "failed":
        raise RuntimeError(record["error"])

    return record
'''

updated = (
    "".join(lines[:node.lineno - 1])
    + replacement
    + "".join(lines[node.end_lineno:])
)

ast.parse(updated)
file.write_text(updated, encoding="utf-8")

print("Scheduler function repaired successfully")
