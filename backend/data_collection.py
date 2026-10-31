"""DSE Market Signal — Autonomous Data Collection & Catch-Up Engine.

Capabilities:
1. Hourly Intraday Collection:
   Runs every 1 hour during active DSE market hours (Sun-Thu, 10:00 - 14:30 Asia/Dhaka)
   to capture real-time LTP, High, Low, and Volume.
2. Daily EOD Collection:
   Runs once daily after market close (16:30 Asia/Dhaka) to record official EOD daily candles.
3. Offline Catch-Up & Gap Filling on Startup:
   If the backend is turned off/restarted, the engine checks for missing trading days
   since the last collected record and automatically fills all gaps via historical backfill batches.
"""

import json
import logging
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from backend.db import connect, save_prices
from backend.calendar import DHAKA_TZ, is_trading_day, get_trading_days, is_dse_holiday
from backend.collector import (
    collect,
    collect_daily,
    collect_intraday,
    get_configured_symbols
)
from scripts.backfill import make_batches

logger = logging.getLogger("dse.data_collection")

STATE_FILE = Path(__file__).resolve().parent.parent / "data" / "collection_state.json"
LOG_DIR = Path(__file__).resolve().parent.parent / "logs"


def load_collection_state() -> Dict:
    """Load latest collection engine execution state from disk."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Could not parse collection state: %s", exc)
    return {
        "engine_version": "2.0.0",
        "last_startup_catchup": None,
        "last_hourly_run": None,
        "last_eod_run": None,
        "total_gap_recovered_records": 0,
        "last_gap_audit": {},
        "status": "ready"
    }


def save_collection_state(state: Dict) -> None:
    """Persist collection engine state atomically."""
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        temp_file = STATE_FILE.with_suffix(".tmp")
        temp_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
        temp_file.replace(STATE_FILE)
    except Exception as exc:
        logger.error("Failed to save collection state: %s", exc)


def is_dse_market_hour(dt: Optional[datetime] = None) -> bool:
    """Return True if current time is within active DSE trading hours (Sun-Thu 10:00 - 14:30 Asia/Dhaka)."""
    now = dt or datetime.now(DHAKA_TZ)
    if not is_trading_day(now.date()):
        return False
    market_open = now.replace(hour=10, minute=0, second=0, microsecond=0)
    market_close = now.replace(hour=14, minute=30, second=0, microsecond=0)
    return market_open <= now <= market_close


def audit_symbol_gaps(symbol: str, today: Optional[date] = None, max_lookback_days: int = 180) -> Dict:
    """Inspect stored database records for a symbol and identify missing trading dates."""
    symbol = symbol.upper().strip()
    today = today or datetime.now(DHAKA_TZ).date()

    with connect() as con:
        row = con.execute(
            "SELECT MIN(date), MAX(date), COUNT(DISTINCT date) FROM prices WHERE symbol=?",
            (symbol,)
        ).fetchone()

    min_date_str, max_date_str, total_count = row if row else (None, None, 0)

    if not max_date_str:
        # No data at all: gap is from max_lookback_days ago until yesterday
        start_date = today - timedelta(days=max_lookback_days)
        end_date = today - timedelta(days=1)
        expected_days = get_trading_days(start_date, end_date)
        return {
            "symbol": symbol,
            "has_data": False,
            "min_date": None,
            "max_date": None,
            "total_stored_days": 0,
            "missing_trading_days": [d.isoformat() for d in expected_days],
            "gap_start": start_date.isoformat(),
            "gap_end": end_date.isoformat()
        }

    last_collected = date.fromisoformat(max_date_str)
    # Check if there are days between last_collected and today - 1
    start_date = last_collected + timedelta(days=1)
    end_date = today - timedelta(days=1)

    if start_date > end_date:
        # Already fully up to date up to yesterday
        return {
            "symbol": symbol,
            "has_data": True,
            "min_date": min_date_str,
            "max_date": max_date_str,
            "total_stored_days": total_count,
            "missing_trading_days": [],
            "gap_start": None,
            "gap_end": None
        }

    expected_missing = get_trading_days(start_date, end_date)
    return {
        "symbol": symbol,
        "has_data": True,
        "min_date": min_date_str,
        "max_date": max_date_str,
        "total_stored_days": total_count,
        "missing_trading_days": [d.isoformat() for d in expected_missing],
        "gap_start": start_date.isoformat() if expected_missing else None,
        "gap_end": end_date.isoformat() if expected_missing else None
    }


def run_gap_filling_catchup(symbols: Optional[List[str]] = None, max_lookback_days: int = 180) -> Dict:
    """Automatic offline gap filling engine executed on backend startup.

    If the backend server was off, this function scans each configured symbol, detects
    all missing trading days up to yesterday, and automatically executes batch backfills
    to restore historical continuity.
    """
    target_symbols = symbols or get_configured_symbols()
    target_symbols = [s.upper().strip() for s in target_symbols]
    now = datetime.now(DHAKA_TZ)
    today = now.date()

    logger.info("⚡ [DataCollectionEngine] Starting offline gap detection for symbols: %s", target_symbols)
    state = load_collection_state()

    recovery_summary = {
        "timestamp": now.isoformat(),
        "symbols_checked": target_symbols,
        "gaps_detected": {},
        "recovered_batches": 0,
        "total_records_inserted": 0,
        "status": "success",
        "intraday_triggered": False
    }

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    recovery_log = LOG_DIR / "recovery.jsonl"

    for sym in target_symbols:
        gap_info = audit_symbol_gaps(sym, today=today, max_lookback_days=max_lookback_days)
        missing_days = gap_info.get("missing_trading_days", [])

        if not missing_days:
            logger.info("✓ [DataCollectionEngine] %s is fully up-to-date (Latest: %s)", sym, gap_info.get("max_date"))
            recovery_summary["gaps_detected"][sym] = {
                "status": "up_to_date",
                "latest_date": gap_info.get("max_date"),
                "missing_days": 0
            }
            continue

        gap_start = date.fromisoformat(missing_days[0])
        gap_end = date.fromisoformat(missing_days[-1])
        logger.warning(
            "⚠️ [DataCollectionEngine] Detected gap for %s: %d missing trading days (%s to %s)",
            sym, len(missing_days), gap_start, gap_end
        )

        recovery_summary["gaps_detected"][sym] = {
            "status": "recovering",
            "missing_days_count": len(missing_days),
            "missing_dates": missing_days,
            "gap_start": str(gap_start),
            "gap_end": str(gap_end),
            "inserted": 0
        }

        # Break the missing date span into safe 7-day batches for the scraper
        batches = make_batches(gap_start, gap_end)
        for b_start, b_end in batches:
            try:
                logger.info("🔄 [DataCollectionEngine] Backfilling %s: %s to %s", sym, b_start, b_end)
                result = collect(sym, str(b_start), str(b_end))
                inserted = result.get("inserted", 0)
                recovery_summary["total_records_inserted"] += inserted
                recovery_summary["recovered_batches"] += 1
                recovery_summary["gaps_detected"][sym]["inserted"] += inserted

                # Log to recovery audit file
                log_entry = {
                    "timestamp": datetime.now(DHAKA_TZ).isoformat(),
                    "symbol": sym,
                    "batch_start": str(b_start),
                    "batch_end": str(b_end),
                    "status": "success",
                    "inserted": inserted
                }
                with recovery_log.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(log_entry) + "\n")

                # Respectful rate limiting for DSE scraper
                time.sleep(0.5)
            except Exception as exc:
                logger.error("❌ [DataCollectionEngine] Failed backfill batch %s [%s-%s]: %s", sym, b_start, b_end, exc)
                recovery_summary["status"] = "partial_error"
                log_entry = {
                    "timestamp": datetime.now(DHAKA_TZ).isoformat(),
                    "symbol": sym,
                    "batch_start": str(b_start),
                    "batch_end": str(b_end),
                    "status": "failed",
                    "error": str(exc)
                }
                with recovery_log.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(log_entry) + "\n")

    # If backend turned on during active market hours, immediately run intraday collection
    if is_dse_market_hour(now):
        logger.info("📈 [DataCollectionEngine] Backend started during active DSE Market Hours (10:00-14:30). Triggering immediate intraday collection.")
        try:
            intraday_res = collect_hourly_intraday(symbols=target_symbols)
            recovery_summary["intraday_triggered"] = True
            recovery_summary["intraday_result"] = intraday_res
        except Exception as exc:
            logger.warning("Intraday collection on startup warning: %s", exc)

    # Persist engine state
    state["last_startup_catchup"] = recovery_summary
    state["total_gap_recovered_records"] += recovery_summary["total_records_inserted"]
    state["status"] = "ready"
    save_collection_state(state)

    logger.info(
        "✅ [DataCollectionEngine] Startup catch-up complete. Recovered %d batches, inserted %d records.",
        recovery_summary["recovered_batches"], recovery_summary["total_records_inserted"]
    )
    return recovery_summary


def collect_hourly_intraday(symbols: Optional[List[str]] = None) -> Dict:
    """Execute hourly intraday collection during active DSE market hours."""
    target_symbols = symbols or get_configured_symbols()
    logger.info("⏰ [DataCollectionEngine] Running hourly intraday collection for: %s", target_symbols)

    summary = collect_intraday(symbols=target_symbols)

    # Update state
    state = load_collection_state()
    state["last_hourly_run"] = {
        "timestamp": datetime.now(DHAKA_TZ).isoformat(),
        "status": summary.get("status"),
        "updated_symbols": summary.get("updated_symbols", 0)
    }
    save_collection_state(state)
    return summary


def collect_daily_eod(symbols: Optional[List[str]] = None) -> Dict:
    """Execute daily End-of-Day (EOD) collection after market close."""
    target_symbols = symbols or get_configured_symbols()
    logger.info("🌙 [DataCollectionEngine] Running official daily EOD collection for: %s", target_symbols)

    summary = collect_daily(symbols=target_symbols)

    # Update state
    state = load_collection_state()
    state["last_eod_run"] = {
        "timestamp": datetime.now(DHAKA_TZ).isoformat(),
        "status": summary.get("status"),
        "total_inserted": summary.get("total_inserted", 0)
    }
    save_collection_state(state)
    return summary


def get_collection_engine_status() -> Dict:
    """Return comprehensive diagnostics of the data collection engine."""
    now = datetime.now(DHAKA_TZ)
    state = load_collection_state()
    configured_symbols = get_configured_symbols()

    # Query latest records per symbol
    symbol_status = {}
    with connect() as con:
        for sym in configured_symbols:
            row = con.execute(
                "SELECT COUNT(*), MIN(date), MAX(date) FROM prices WHERE symbol=?",
                (sym,)
            ).fetchone()
            count, min_d, max_d = row if row else (0, None, None)
            symbol_status[sym] = {
                "records_count": count,
                "first_date": min_d,
                "latest_date": max_d,
                "is_up_to_date": max_d == (now.date() - timedelta(days=1)).isoformat() or max_d == now.date().isoformat()
            }

    return {
        "engine": "DSE Data Collection Engine v2.0",
        "current_time_bst": now.isoformat(),
        "market_hour_active": is_dse_market_hour(now),
        "is_trading_day": is_trading_day(now.date()),
        "configured_symbols": configured_symbols,
        "symbol_data_status": symbol_status,
        "last_startup_catchup": state.get("last_startup_catchup"),
        "last_hourly_run": state.get("last_hourly_run"),
        "last_eod_run": state.get("last_eod_run"),
        "total_gap_recovered_records": state.get("total_gap_recovered_records", 0)
    }
