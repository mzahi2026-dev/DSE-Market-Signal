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


def scan_full_dse_market_and_rank(top_n: int = 10, min_trades: int = 30, min_value_mn: float = 0.5) -> List[Dict[str, Any]]:
    """Scan all 390+ live trade stocks from DSE, calculate momentum/turnover scores,
    and rank the best market opportunities."""
    import bdshare
    try:
        df = bdshare.get_current_trade_data()
    except Exception as exc:
        return []

    if df is None or df.empty:
        return []

    # Clean and filter active trade stocks
    df = df.dropna(subset=["symbol", "close", "ltp"])
    df["symbol"] = df["symbol"].astype(str).str.strip().str.upper()
    df = df[df["symbol"] != ""]

    # Filter out illiquid / zero-activity stocks
    filtered = df[(df["trade"] >= min_trades) & (df["value"] >= min_value_mn) & (df["change"] > 0)].copy()
    if filtered.empty:
        # Fallback to any positive change if market is slow
        filtered = df[df["change"] > 0].copy()

    if filtered.empty:
        filtered = df.copy()

    filtered["pct_change"] = (filtered["change"] / filtered["ycp"].replace(0, 1.0)) * 100
    # Composite Score: Value (Turnover) 40% + Trades Count 2% + Percentage Gain 300%
    filtered["rank_score"] = (filtered["value"] * 0.4) + (filtered["trade"] * 0.02) + (filtered["pct_change"] * 3.0)
    
    ranked = filtered.sort_values(by="rank_score", ascending=False).head(top_n)

    results = []
    for _, row in ranked.iterrows():
        results.append({
            "symbol": row["symbol"],
            "ltp": float(row["ltp"]),
            "change": float(row["change"]),
            "pct_change": round(float(row["pct_change"]), 2),
            "trade": int(row["trade"]),
            "value_mn": round(float(row["value"]), 2),
            "volume": int(row["volume"]),
            "rank_score": round(float(row["rank_score"]), 2)
        })
    return results


def auto_scan_and_sync_watchlist(top_n: int = 5, backfill_months: int = 6) -> Dict[str, Any]:
    """Scan the entire DSE market, pick the top momentum breakout stocks,
    backfill their historical candle data into the database, generate signals,
    and automatically add the best BUY candidates to the user watchlist."""
    from datetime import date, timedelta
    from bdshare import get_basic_historical_data
    from backend.db import save_prices
    import logging
    logger = logging.getLogger("dse.screener")

    candidates = scan_full_dse_market_and_rank(top_n=top_n)
    if not candidates:
        return {"status": "no_candidates_found", "added_count": 0, "stocks": []}

    today = date.today()
    start_date = (today - timedelta(days=backfill_months * 31)).strftime("%Y-%m-%d")
    end_date = today.strftime("%Y-%m-%d")

    added_stocks = []
    for item in candidates:
        sym = item["symbol"]
        try:
            # 1. Fetch historical OHLCV data to enable full technical analysis & chart display
            df_hist = get_basic_historical_data(start_date, end_date, sym, "legacy")
            if df_hist is not None and not df_hist.empty:
                rows = [
                    (sym, str(r["date"])[:10], float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"]), float(r["volume"]))
                    for _, r in df_hist.iterrows()
                ]
                save_prices(rows, upsert=True)

            # 2. Generate signal & analysis
            sig = generate_signal(sym)
            signal_type = sig.get("signal", "HOLD")
            conf = sig.get("confidence", 50)

            # 3. Add to user watchlist with breakout metadata
            note = f"Auto-Scanned Breakout: Chg +{item['pct_change']}% | Vol {item['volume']:,} | Val ৳{item['value_mn']}M"
            add_to_watchlist(symbol=sym, note=note)

            added_stocks.append({
                "symbol": sym,
                "ltp": item["ltp"],
                "pct_change": item["pct_change"],
                "value_mn": item["value_mn"],
                "signal": signal_type,
                "confidence": conf,
                "target": sig.get("target"),
                "stop_loss": sig.get("stop_loss"),
                "status": "added_to_watchlist"
            })
            logger.info("Auto-scanned and added %s to watchlist (Signal: %s)", sym, signal_type)
        except Exception as e:
            logger.warning("Failed processing scanned stock %s: %s", sym, e)

    return {
        "status": "success",
        "scanned_market_stocks": len(candidates),
        "added_count": len(added_stocks),
        "watchlist_stocks": added_stocks
    }


