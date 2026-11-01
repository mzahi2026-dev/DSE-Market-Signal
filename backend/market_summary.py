"""Market Summary and Breadth calculation for DSE."""

from typing import Any, Dict, List
import pandas as pd
from backend.db import connect
from backend.analysis import analyze_stock


def get_all_symbols() -> List[str]:
    """Return distinct stock symbols in the database."""
    with connect() as con:
        rows = con.execute("SELECT DISTINCT symbol FROM prices ORDER BY symbol").fetchall()
    return [r[0] for r in rows]


def get_market_summary() -> Dict[str, Any]:
    """Aggregate market breadth, gainers/losers, and sentiment across tracked stocks."""
    symbols = get_all_symbols()
    if not symbols:
        return {
            "status": "empty",
            "message": "No stocks found in database",
            "advancers": 0,
            "decliners": 0,
            "unchanged": 0,
            "total_stocks": 0
        }

    stocks_data = []
    advancers = 0
    decliners = 0
    unchanged = 0
    total_volume = 0.0

    for sym in symbols:
        analysis = analyze_stock(sym)
        if analysis.get("status") == "no_data":
            continue

        p = analysis["price"]
        chg_pct = p["change_pct"]
        vol = p["volume"]
        total_volume += vol

        if chg_pct > 0:
            advancers += 1
        elif chg_pct < 0:
            decliners += 1
        else:
            unchanged += 1

        stocks_data.append({
            "symbol": sym,
            "close": p["close"],
            "change": p["change"],
            "change_pct": chg_pct,
            "volume": vol,
            "trend": analysis["trend"],
            "rsi": analysis["indicators"]["rsi_14"]
        })

    total_stocks = len(stocks_data)
    adv_dec_ratio = round(advancers / decliners, 2) if decliners > 0 else float(advancers)

    # Sort gainers and losers
    gainers = sorted(stocks_data, key=lambda x: x["change_pct"], reverse=True)[:5]
    losers = sorted(stocks_data, key=lambda x: x["change_pct"])[:5]
    most_active = sorted(stocks_data, key=lambda x: x["volume"], reverse=True)[:5]

    # Market Sentiment
    bullish_stocks = sum(1 for s in stocks_data if s["trend"] == "Bullish")
    bearish_stocks = sum(1 for s in stocks_data if s["trend"] == "Bearish")

    if bullish_stocks > bearish_stocks:
        sentiment = "Bullish"
    elif bearish_stocks > bullish_stocks:
        sentiment = "Bearish"
    else:
        sentiment = "Neutral"

    return {
        "status": "ok",
        "total_stocks": total_stocks,
        "advancers": advancers,
        "decliners": decliners,
        "unchanged": unchanged,
        "advance_decline_ratio": adv_dec_ratio,
        "total_volume": round(total_volume, 2),
        "sentiment": sentiment,
        "all_stocks": sorted(stocks_data, key=lambda x: x["change_pct"], reverse=True),
        "top_gainers": gainers,
        "top_losers": losers,
        "most_active": most_active
    }

