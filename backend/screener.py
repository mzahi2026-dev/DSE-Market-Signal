"""Stock Screener and Watchlist Management Subsystem for DSE."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from backend.db import connect
from backend.analysis import analyze_stock
from backend.signals import generate_signal
from backend.ai_engine import review_signal_with_ai
from backend.market_summary import get_all_symbols
from backend.calendar import DHAKA_TZ


def init_watchlist_table():
    """Ensure watchlist database table exists."""
    with connect() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS user_watchlist (
                symbol TEXT PRIMARY KEY,
                note TEXT,
                added_at TEXT NOT NULL
            )
        """)
        con.commit()


def add_to_watchlist(symbol: str, note: str = "") -> Dict[str, Any]:
    init_watchlist_table()
    symbol = symbol.upper().strip()
    now_iso = datetime.now(DHAKA_TZ).isoformat()
    with connect() as con:
        con.execute(
            "INSERT OR REPLACE INTO user_watchlist (symbol, note, added_at) VALUES (?, ?, ?)",
            (symbol, note, now_iso)
        )
        con.commit()
    return {"symbol": symbol, "note": note, "added_at": now_iso, "status": "added"}


def remove_from_watchlist(symbol: str) -> Dict[str, Any]:
    init_watchlist_table()
    symbol = symbol.upper().strip()
    with connect() as con:
        con.execute("DELETE FROM user_watchlist WHERE symbol=?", (symbol,))
        con.commit()
    return {"symbol": symbol, "status": "removed"}


def get_watchlist() -> List[Dict[str, Any]]:
    init_watchlist_table()
    with connect() as con:
        rows = con.execute("SELECT symbol, note, added_at FROM user_watchlist ORDER BY symbol").fetchall()

    watchlist_items = []
    for r in rows:
        sym, note, added = r[0], r[1], r[2]
        analysis = analyze_stock(sym)
        signal = generate_signal(sym)
        ai_rev = review_signal_with_ai(sym)

        price_info = analysis.get("price", {})
        watchlist_items.append({
            "symbol": sym,
            "note": note,
            "added_at": added,
            "price": price_info.get("close", 0.0),
            "change_pct": price_info.get("change_pct", 0.0),
            "trend": analysis.get("trend", "Neutral"),
            "rsi": analysis.get("indicators", {}).get("rsi_14", 50.0),
            "signal": signal.get("signal", "HOLD"),
            "confidence": signal.get("confidence", 50),
            "ai_consensus": ai_rev.get("consensus", "ALIGNED")
        })

    return watchlist_items


def screen_stocks(
    signal_filter: str = "ALL",      # "ALL", "BUY_ONLY", "SELL_ONLY"
    trend_filter: str = "ALL",       # "ALL", "Bullish", "Bearish"
    rsi_filter: str = "ALL",         # "ALL", "OVERSOLD", "OVERBOUGHT", "HEALTHY_BULL"
    volume_surge_only: bool = False,
    min_confidence: int = 50
) -> List[Dict[str, Any]]:
    """Scan all database stocks against quantitative technical criteria."""
    symbols = get_all_symbols()
    matches = []

    for sym in symbols:
        analysis = analyze_stock(sym)
        if analysis.get("status") == "no_data":
            continue

        sig = generate_signal(sym)
        p = analysis["price"]
        ind = analysis["indicators"]
        rsi = ind["rsi_14"]
        trend = analysis["trend"]
        conf = sig["confidence"]

        # Confidence filter
        if conf < min_confidence:
            continue

        # Signal filter
        if signal_filter == "BUY_ONLY" and not ("BUY" in sig["signal"]):
            continue
        elif signal_filter == "SELL_ONLY" and not ("SELL" in sig["signal"]):
            continue

        # Trend filter
        if trend_filter != "ALL" and trend.lower() != trend_filter.lower():
            continue

        # RSI filter
        if rsi_filter == "OVERSOLD" and rsi > 35:
            continue
        elif rsi_filter == "OVERBOUGHT" and rsi < 70:
            continue
        elif rsi_filter == "HEALTHY_BULL" and not (50 <= rsi <= 68):
            continue

        # Volume filter
        if volume_surge_only and not ind["volume_surge"]:
            continue

        ai_review = review_signal_with_ai(sym)

        matches.append({
            "symbol": sym,
            "close": p["close"],
            "change_pct": p["change_pct"],
            "trend": trend,
            "rsi": rsi,
            "signal": sig["signal"],
            "confidence": conf,
            "target": sig["target"],
            "stop_loss": sig["stop_loss"],
            "volume_surge": ind["volume_surge"],
            "ai_verdict": ai_review.get("ai_verdict"),
            "ai_consensus": ai_review.get("consensus")
        })

    return sorted(matches, key=lambda x: x["confidence"], reverse=True)

