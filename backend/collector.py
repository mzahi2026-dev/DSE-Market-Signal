import json
import logging
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import pandas as pd
from bdshare import get_basic_historical_data
from backend.db import save_prices

logger = logging.getLogger("dse.collector")

CONFIG_FILE = Path(__file__).resolve().parent / "scraping_config.json"


def load_config():
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "api_key_required": False,
        "symbols": ["GP", "BATBC", "SQURPHARMA", "BEXIMCO", "ROBI"],
        "schedule_timezone": "Asia/Dhaka",
        "retry_failed": True
    }


def get_configured_symbols():
    """Retrieve list of configured stock symbols from settings.json or config."""
    settings_file = Path(__file__).resolve().parent.parent / "config" / "settings.json"
    if settings_file.exists():
        try:
            cfg = json.loads(settings_file.read_text(encoding="utf-8"))
            syms = cfg.get("market", {}).get("symbols")
            if syms and isinstance(syms, list):
                return syms
        except Exception:
            pass
    cfg2 = load_config()
    return cfg2.get("symbols", ["GP", "BATBC", "SQURPHARMA", "BEXIMCO", "ROBI"])


def is_permission_blocked(exc: Exception) -> bool:
    """Return True if exception indicates HTTP 403, 401, 429, or permission denied.
    NEVER attempt to bypass or retry permission errors."""
    msg = str(exc).lower()
    return any(term in msg for term in ("403", "401", "429", "forbidden", "unauthorized", "permission denied"))


def collect(symbol, start, end, max_retries=1, retry_delay=3):
    """Collect DSE historical prices for a symbol between start and end date (max 7 days).
    Uses legacy scraping without any API key.
    Aborts immediately on 403/permission errors.
    """
    symbol = symbol.upper().strip()
    a, b = date.fromisoformat(start), date.fromisoformat(end)

    if not symbol.isalnum() or len(symbol) > 20:
        raise ValueError("Invalid stock symbol")
    if a > b or b > date.today():
        raise ValueError("Invalid date range")
    if (b - a).days > 7:
        raise ValueError("Maximum 7 days per batch")

    df = None
    last_err = None

    for attempt in range(max_retries + 1):
        try:
            df = get_basic_historical_data(start, end, symbol)
            break
        except Exception as exc:
            last_err = exc
            if is_permission_blocked(exc):
                logger.error("HTTP 403 / Access restricted for %s: %s", symbol, exc)
                raise
            if attempt < max_retries:
                backoff_delay = retry_delay * (2 ** attempt)
                logger.warning("Retryable error fetching %s (attempt %d, backoff %ds): %s", symbol, attempt + 1, backoff_delay, exc)
                time.sleep(backoff_delay)
            else:
                raise

    if df is None or df.empty:
        return {"symbol": symbol, "fetched": 0, "inserted": 0}

    df = df.reset_index()
    df.columns = [str(c).lower().strip() for c in df.columns]

    required = ["date", "open", "high", "low", "close", "volume"]
    if not all(c in df.columns for c in required):
        raise ValueError(f"Unexpected columns: {list(df.columns)}")

    rows = []
    for _, r in df.iterrows():
        if any(pd.isna(r[c]) for c in required):
            continue
        rows.append((
            symbol,
            str(pd.to_datetime(r["date"]).date()),
            float(r["open"]),
            float(r["high"]),
            float(r["low"]),
            float(r["close"]),
            float(r["volume"])
        ))

    inserted = save_prices(rows)
    return {
        "symbol": symbol,
        "fetched": len(rows),
        "inserted": inserted
    }


def collect_daily(symbol="GP", symbols=None, log_path=None):
    """Automated daily collection scheduled for DSE market close (16:30 Asia/Dhaka).
    Collects past 7 calendar days to ensure complete week capture for configured symbols.
    """
    from backend.automation import load_automation_state
    state = load_automation_state()
    if state.get("mode") == "MANUAL":
        logger.info("Daily collection skipped: System is in MANUAL automation mode")
        return {"status": "skipped", "reason": "MANUAL mode active"}

    if symbols is not None:
        target_symbols = list(symbols) if not isinstance(symbols, str) else [symbols]
    else:
        target_symbols = [symbol]

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

    summary = {
        "timestamp": now.isoformat(),
        "symbols": target_symbols,
        "start": str(start),
        "end": str(end),
        "results": {},
        "status": "success",
        "total_inserted": 0
    }

    single_record = None

    for sym in target_symbols:
        sym = sym.upper().strip()
        record = {
            "timestamp": now.isoformat(),
            "symbol": sym,
            "start": str(start),
            "end": str(end)
        }
        try:
            result = collect(sym, str(start), str(end))
            record["result"] = result
            record["status"] = (
                "success" if result["fetched"] > 0
                else "empty_unverified"
            )
            summary["results"][sym] = record
            summary["total_inserted"] += result.get("inserted", 0)
        except Exception as exc:
            record["status"] = "failed"
            record["error"] = str(exc)
            summary["results"][sym] = record
            summary["status"] = "failed"

        with log_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record) + "\n")

        single_record = record

    if len(target_symbols) == 1 and single_record is not None:
        if single_record["status"] == "failed":
            raise RuntimeError(single_record["error"])
        return single_record

    return summary


def collect_intraday(symbols=None, log_path=None):
    """Hourly intraday data collection engine scheduled during DSE market hours (10:00 - 14:00 Asia/Dhaka).
    Fetches real-time price, high, low, volume, and last trade price (LTP) and updates today's session record.
    """
    from backend.automation import load_automation_state
    state = load_automation_state()
    if state.get("mode") == "MANUAL":
        logger.info("Intraday collection skipped: System is in MANUAL automation mode")
        return {"status": "skipped", "reason": "MANUAL mode active"}

    from backend.calendar import is_trading_day
    now = datetime.now(ZoneInfo("Asia/Dhaka"))
    today = now.date()

    if not is_trading_day(today):
        logger.info("Intraday collection skipped: %s is not an active DSE trading day", today)
        return {"status": "skipped", "reason": "Not an active DSE trading day"}

    if symbols is None:
        target_symbols = get_configured_symbols()
    elif isinstance(symbols, str):
        target_symbols = [symbols]
    else:
        target_symbols = list(symbols)

    target_symbols = [s.upper().strip() for s in target_symbols]

    if log_path is None:
        log_path = (
            Path(__file__).resolve().parent.parent
            / "logs" / "intraday_collection.jsonl"
        )
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    summary = {
        "timestamp": now.isoformat(),
        "date": str(today),
        "symbols": target_symbols,
        "results": {},
        "status": "success",
        "updated_symbols": 0
    }

    live_df = None
    try:
        import bdshare
        live_df = bdshare.get_current_trade_data()
        if live_df is not None and not live_df.empty:
            live_df.columns = [str(c).lower().strip() for c in live_df.columns]
    except Exception as exc:
        logger.warning("Could not fetch bulk live trade data: %s", exc)

    rows_to_save = []

    for sym in target_symbols:
        record = {
            "timestamp": now.isoformat(),
            "symbol": sym,
            "date": str(today)
        }
        sym_data = None
        if live_df is not None and not live_df.empty and "symbol" in live_df.columns:
            matches = live_df[live_df["symbol"] == sym]
            if not matches.empty:
                sym_data = matches.iloc[0].to_dict()

        if sym_data:
            try:
                ltp = float(sym_data.get("ltp", 0.0) or 0.0)
                high = float(sym_data.get("high", ltp) or ltp)
                low = float(sym_data.get("low", ltp) or ltp)
                close = float(sym_data.get("close", ltp) or ltp)
                ycp = float(sym_data.get("ycp", close) or close)
                open_p = float(sym_data.get("open", ycp) or ycp)
                vol = float(sym_data.get("volume", 0.0) or 0.0)

                if ltp > 0:
                    rows_to_save.append((sym, str(today), open_p, high, low, ltp, vol))
                    record["status"] = "success"
                    record["data"] = {
                        "ltp": ltp,
                        "high": high,
                        "low": low,
                        "open": open_p,
                        "volume": vol
                    }
                    summary["results"][sym] = record
                    summary["updated_symbols"] += 1
                else:
                    record["status"] = "empty_or_zero"
                    summary["results"][sym] = record
            except Exception as exc:
                record["status"] = "failed"
                record["error"] = str(exc)
                summary["results"][sym] = record
        else:
            record["status"] = "no_live_data"
            summary["results"][sym] = record

        with log_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record) + "\n")

    if rows_to_save:
        save_prices(rows_to_save, upsert=True)

    if summary["updated_symbols"] == 0 and target_symbols:
        summary["status"] = "no_data_collected"

    return summary
