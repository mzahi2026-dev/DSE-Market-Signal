"""Automation, Retry, Recovery, and Health Monitoring Subsystem for DSE."""

import json
import logging
import time
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo
from backend.collector import collect, is_permission_blocked
from backend.calendar import DHAKA_TZ
from scripts.gap_audit import audit
from scripts.recovery import run_recovery

logger = logging.getLogger("dse.automation")

ROOT_DIR = Path(__file__).resolve().parent.parent
STATE_FILE = ROOT_DIR / "data" / "automation_state.json"
RUNS_LOG = ROOT_DIR / "logs" / "automation_runs.jsonl"


def load_automation_state() -> Dict[str, Any]:
    default_state = {
        "mode": "AUTO",  # "AUTO" or "MANUAL"
        "last_run": None,
        "last_status": "NONE",
        "total_runs": 0,
        "successful_runs": 0,
        "failed_runs": 0
    }
    if STATE_FILE.exists():
        try:
            stored = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            default_state.update(stored)
        except Exception:
            pass
    return default_state


def save_automation_state(state: Dict[str, Any]):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def set_automation_mode(mode: str) -> Dict[str, Any]:
    mode_upper = mode.upper().strip()
    if mode_upper not in ("AUTO", "MANUAL"):
        raise ValueError("Mode must be AUTO or MANUAL")
    state = load_automation_state()
    state["mode"] = mode_upper
    save_automation_state(state)
    return state


def log_automation_run(record: Dict[str, Any]):
    RUNS_LOG.parent.mkdir(parents=True, exist_ok=True)
    with RUNS_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def execute_automation_cycle(symbols: Optional[List[str]] = None, max_retries: int = 1) -> Dict[str, Any]:
    """Execute complete automation cycle:
    1. Collect latest data for symbols with controlled retries
    2. Audit calendar for missing trading sessions
    3. Run recovery if needed
    4. Update metrics
    """
    state = load_automation_state()
    now_iso = datetime.now(DHAKA_TZ).isoformat()
    symbols = symbols or ["GP"]

    cycle_report = {
        "timestamp": now_iso,
        "mode": state["mode"],
        "symbols": symbols,
        "collections": [],
        "recovery": None,
        "status": "SUCCESS"
    }

    # Date range: past 7 days
    end = date.today()
    start = end - timedelta(days=6)

    for sym in symbols:
        sym_res = {"symbol": sym, "status": "PENDING"}
        for attempt in range(max_retries + 1):
            try:
                res = collect(sym, str(start), str(end))
                sym_res["status"] = "SUCCESS"
                sym_res["result"] = res
                break
            except Exception as exc:
                if is_permission_blocked(exc):
                    sym_res["status"] = "FORBIDDEN_ABORT"
                    sym_res["error"] = str(exc)
                    cycle_report["status"] = "FAILED"
                    break
                if attempt < max_retries:
                    backoff = 2 * (2 ** attempt)
                    time.sleep(backoff)
                else:
                    sym_res["status"] = "FAILED"
                    sym_res["error"] = str(exc)
                    cycle_report["status"] = "FAILED"

        cycle_report["collections"].append(sym_res)

    # Missing Data Recovery Check across ALL target symbols
    cycle_report["recoveries"] = {}
    for sym in symbols:
        try:
            gap_audit = audit(sym)
            if gap_audit.get("missing_trading_days"):
                recovery_res = run_recovery(symbol=sym, execute=True, max_batches=1)
                cycle_report["recoveries"][sym] = recovery_res
                if recovery_res.get("status") == "failed" or recovery_res.get("failed_batches", 0) > 0:
                    cycle_report["status"] = "FAILED"
        except Exception as exc:
            cycle_report["recoveries"][sym] = {"status": "failed", "error": str(exc)}
            cycle_report["status"] = "FAILED"

    # Backwards compatibility
    cycle_report["recovery"] = cycle_report["recoveries"].get(symbols[0])

    # Update State
    state["last_run"] = now_iso
    state["last_status"] = cycle_report["status"]
    state["total_runs"] += 1
    if cycle_report["status"] == "SUCCESS":
        state["successful_runs"] += 1
    else:
        state["failed_runs"] += 1
    save_automation_state(state)

    log_automation_run(cycle_report)
    return cycle_report


def get_automation_monitoring_status() -> Dict[str, Any]:
    state = load_automation_state()
    total = state["total_runs"]
    succ = state["successful_runs"]
    success_rate = (succ / total * 100.0) if total > 0 else 100.0

    return {
        "mode": state["mode"],
        "last_run": state["last_run"],
        "last_status": state["last_status"],
        "total_runs": total,
        "success_rate_pct": round(success_rate, 2),
        "scheduler_schedule": "Daily 16:30 Asia/Dhaka",
        "retry_policy": "Exponential backoff for transient, strictly no retry on 403"
    }

