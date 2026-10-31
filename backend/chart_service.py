"""Dedicated Chart Service for Candlestick, RSI, MACD, and Technical Indicators."""

from typing import Any, Dict, List
import pandas as pd
from backend.analysis import get_stock_price_history, calculate_support_resistance
from backend.indicators import calculate_all_indicators


def get_full_chart_data(symbol: str, limit: int = 100) -> Dict[str, Any]:
    """Generate structured multi-panel chart data for TradingView/Canvas charts."""
    symbol = symbol.upper().strip()
    df = get_stock_price_history(symbol, limit=limit)
    if df.empty:
        return {"symbol": symbol, "status": "no_data", "candlesticks": [], "rsi": [], "macd": []}

    df_ind = calculate_all_indicators(df)

    candlesticks = []
    volume_series = []
    ema_9_series = []
    ema_21_series = []
    ema_50_series = []
    bb_upper_series = []
    bb_lower_series = []
    rsi_series = []
    macd_series = []

    for _, r in df_ind.iterrows():
        d_str = str(r["date"])
        c = float(r["close"])
        o = float(r["open"])
        h = float(r["high"])
        l = float(r["low"])
        v = float(r["volume"])

        candlesticks.append({
            "time": d_str,
            "open": o,
            "high": h,
            "low": l,
            "close": c,
            "is_bullish": c >= o
        })

        volume_series.append({
            "time": d_str,
            "value": v,
            "color": "#089981" if c >= o else "#f23645"
        })

        if pd.notna(r.get("ema_9")):
            ema_9_series.append({"time": d_str, "value": round(float(r["ema_9"]), 2)})
        if pd.notna(r.get("ema_21")):
            ema_21_series.append({"time": d_str, "value": round(float(r["ema_21"]), 2)})
        if pd.notna(r.get("ema_50")):
            ema_50_series.append({"time": d_str, "value": round(float(r["ema_50"]), 2)})

        if pd.notna(r.get("bb_upper")):
            bb_upper_series.append({"time": d_str, "value": round(float(r["bb_upper"]), 2)})
        if pd.notna(r.get("bb_lower")):
            bb_lower_series.append({"time": d_str, "value": round(float(r["bb_lower"]), 2)})

        if pd.notna(r.get("rsi_14")):
            rsi_series.append({"time": d_str, "value": round(float(r["rsi_14"]), 2)})

        if pd.notna(r.get("macd_line")) and pd.notna(r.get("macd_signal")):
            hist = round(float(r["macd_histogram"]), 4)
            macd_series.append({
                "time": d_str,
                "macd": round(float(r["macd_line"]), 4),
                "signal": round(float(r["macd_signal"]), 4),
                "histogram": hist,
                "histogram_color": "#089981" if hist >= 0 else "#f23645"
            })

    sr_levels = calculate_support_resistance(df_ind)

    return {
        "symbol": symbol,
        "count": len(candlesticks),
        "candlesticks": candlesticks,
        "volume": volume_series,
        "levels": sr_levels,
        "overlays": {
            "ema_9": ema_9_series,
            "ema_21": ema_21_series,
            "ema_50": ema_50_series,
            "bb_upper": bb_upper_series,
            "bb_lower": bb_lower_series
        },
        "indicators": {
            "rsi": rsi_series,
            "macd": macd_series
        }
    }

