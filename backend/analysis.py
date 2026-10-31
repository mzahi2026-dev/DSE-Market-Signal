"""Stock technical analysis and trend evaluation module."""

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from backend.db import connect
from backend.indicators import calculate_all_indicators


def get_stock_price_history(symbol: str, limit: int = 250) -> pd.DataFrame:
    """Fetch stored price history from database for a symbol, sorted ascending by date."""
    symbol = symbol.upper().strip()
    with connect() as con:
        rows = con.execute(
            """SELECT date, open, high, low, close, volume
               FROM prices
               WHERE symbol = ?
               ORDER BY date ASC""",
            (symbol,)
        ).fetchall()

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"])
    # Defensive data hygiene: sanitize zero or corrupted open/high/low values
    df["open"] = np.where(df["open"] <= 0, df["close"], df["open"])
    df["high"] = np.where(df["high"] <= 0, np.maximum(df["open"], df["close"]), df["high"])
    df["low"] = np.where(df["low"] <= 0, np.minimum(df["open"], df["close"]), df["low"])
    df["high"] = np.maximum(df["high"], np.maximum(df["open"], df["close"]))
    df["low"] = np.minimum(df["low"], np.minimum(df["open"], df["close"]))
    if limit and len(df) > limit:
        df = df.iloc[-limit:].reset_index(drop=True)
    return df


def calculate_support_resistance(df: pd.DataFrame, window: int = 20) -> Dict[str, float]:
    """Calculate key support, resistance, and pivot levels from price history with DSE volatility protection."""
    if df.empty:
        return {
            "pivot": 0.0,
            "support_1": 0.0,
            "support_2": 0.0,
            "resistance_1": 0.0,
            "resistance_2": 0.0,
            "swing_high": 0.0,
            "swing_low": 0.0,
            "atr": 0.0
        }

    # Ensure chronological order
    df = df.sort_values("date").reset_index(drop=True)
    latest = df.iloc[-1]
    close = float(latest["close"])

    # Calculate ATR(14)
    tr = np.maximum(
        df["high"] - df["low"],
        np.maximum(
            (df["high"] - df["close"].shift(1)).abs(),
            (df["low"] - df["close"].shift(1)).abs()
        )
    )
    atr_series = tr.tail(14).dropna()
    atr_val = float(atr_series.mean()) if not atr_series.empty and atr_series.mean() > 0 else float(latest["high"] - latest["low"])
    if atr_val <= 0 or np.isnan(atr_val):
        atr_val = max(0.5, close * 0.01)

    # Reference candle for Classic Pivots:
    # Use previous completed bar if available, else latest
    ref = df.iloc[-2] if len(df) > 1 else latest
    ref_h = float(ref["high"])
    ref_l = float(ref["low"])
    ref_c = float(ref["close"])

    # If reference bar is flat (H == L) as often occurs in DSE floor/circuit limits, look back for a bar with spread
    if ref_h == ref_l:
        non_flat = df[df["high"] > df["low"]]
        if not non_flat.empty:
            ref = non_flat.iloc[-1]
            ref_h = float(ref["high"])
            ref_l = float(ref["low"])
            ref_c = float(ref["close"])
        else:
            ref_h = close + atr_val
            ref_l = max(0.1, close - atr_val)
            ref_c = close

    # Standard Classic Pivot Points formula
    pivot = (ref_h + ref_l + ref_c) / 3.0
    r1 = (2.0 * pivot) - ref_l
    s1 = (2.0 * pivot) - ref_h
    r2 = pivot + (ref_h - ref_l)
    s2 = pivot - (ref_h - ref_l)

    # Find swing highs and lows in the lookback window
    window_df = df.tail(window).reset_index(drop=True)
    swing_high = float(window_df["high"].max())
    swing_low = float(window_df["low"].min())

    # Detect local swing points (fractals k=2)
    k = 2
    sw_highs, sw_lows = [], []
    hi_vals = window_df["high"].values
    lo_vals = window_df["low"].values
    for i in range(k, len(window_df) - k):
        if hi_vals[i] == hi_vals[i - k:i + k + 1].max():
            sw_highs.append(float(hi_vals[i]))
        if lo_vals[i] == lo_vals[i - k:i + k + 1].min():
            sw_lows.append(float(lo_vals[i]))

    min_buffer = atr_val * 0.1
    above_swings = [h for h in sw_highs if h > (close + min_buffer)]
    below_swings = [l for l in sw_lows if l < (close - min_buffer)]

    # Guarantee resistance is strictly above current price
    if r1 <= close + min_buffer:
        r1 = min(above_swings) if above_swings else (close + 1.0 * atr_val)
    if r2 <= r1:
        r2 = r1 + atr_val

    # Guarantee support is strictly below current price
    if s1 >= close - min_buffer:
        s1 = max(below_swings) if below_swings else max(0.1, close - 1.0 * atr_val)
    if s2 >= s1:
        s2 = max(0.1, s1 - atr_val)

    # Ensure pivot stays realistically between s1 and r1
    if pivot <= s1 or pivot >= r1:
        pivot = (r1 + s1) / 2.0

    return {
        "pivot": round(float(pivot), 2),
        "support_1": round(float(s1), 2),
        "support_2": round(float(s2), 2),
        "resistance_1": round(float(r1), 2),
        "resistance_2": round(float(r2), 2),
        "swing_high": round(float(swing_high), 2),
        "swing_low": round(float(swing_low), 2),
        "atr": round(float(atr_val), 2)
    }


def analyze_stock(symbol: str) -> Dict[str, Any]:
    """Perform comprehensive technical analysis on a stock."""
    df = get_stock_price_history(symbol)
    if df.empty:
        return {
            "symbol": symbol.upper(),
            "status": "no_data",
            "message": f"No price data available for {symbol}"
        }

    df_ind = calculate_all_indicators(df)
    latest = df_ind.iloc[-1]
    prev = df_ind.iloc[-2] if len(df_ind) > 1 else latest

    close = float(latest["close"])
    prev_close = float(prev["close"]) if len(df_ind) > 1 else close
    change = close - prev_close
    change_pct = (change / prev_close * 100) if prev_close else 0.0

    rsi = float(latest.get("rsi_14", 50.0))
    macd_line = float(latest.get("macd_line", 0.0))
    macd_signal = float(latest.get("macd_signal", 0.0))
    macd_hist = float(latest.get("macd_histogram", 0.0))
    prev_macd_hist = float(prev.get("macd_histogram", 0.0))

    ema_9 = float(latest.get("ema_9", close))
    ema_21 = float(latest.get("ema_21", close))
    ema_50 = float(latest.get("ema_50", close))

    # Trend Determination
    bullish_signals = 0
    bearish_signals = 0

    # Moving Average Trend
    if close > ema_21:
        bullish_signals += 1
    else:
        bearish_signals += 1

    if ema_9 > ema_21:
        bullish_signals += 1
    else:
        bearish_signals += 1

    if close > ema_50:
        bullish_signals += 1
    else:
        bearish_signals += 1

    # RSI condition
    rsi_state = "neutral"
    if rsi >= 70:
        rsi_state = "overbought"
        bearish_signals += 1
    elif rsi <= 30:
        rsi_state = "oversold"
        bullish_signals += 1
    elif rsi > 50:
        bullish_signals += 1
    else:
        bearish_signals += 1

    # MACD Condition
    macd_crossover = "none"
    if prev_macd_hist <= 0 and macd_hist > 0:
        macd_crossover = "bullish_crossover"
        bullish_signals += 2
    elif prev_macd_hist >= 0 and macd_hist < 0:
        macd_crossover = "bearish_crossover"
        bearish_signals += 2
    elif macd_hist > 0:
        bullish_signals += 1
    else:
        bearish_signals += 1

    # Overall Trend
    if bullish_signals > bearish_signals + 1:
        trend = "Bullish"
    elif bearish_signals > bullish_signals + 1:
        trend = "Bearish"
    else:
        trend = "Neutral"

    sr = calculate_support_resistance(df)

    return {
        "symbol": symbol.upper(),
        "date": str(latest["date"]),
        "price": {
            "open": float(latest["open"]),
            "high": float(latest["high"]),
            "low": float(latest["low"]),
            "close": close,
            "volume": float(latest["volume"]),
            "change": round(change, 2),
            "change_pct": round(change_pct, 2)
        },
        "trend": trend,
        "indicators": {
            "rsi_14": round(rsi, 2),
            "rsi_state": rsi_state,
            "macd": {
                "macd_line": round(macd_line, 4),
                "signal_line": round(macd_signal, 4),
                "histogram": round(macd_hist, 4),
                "crossover": macd_crossover
            },
            "moving_averages": {
                "sma_20": round(float(latest.get("sma_20", close)), 2),
                "sma_50": round(float(latest.get("sma_50", close)), 2),
                "ema_9": round(ema_9, 2),
                "ema_21": round(ema_21, 2),
                "ema_50": round(ema_50, 2)
            },
            "bollinger_bands": {
                "upper": round(float(latest.get("bb_upper", close)), 2),
                "middle": round(float(latest.get("bb_middle", close)), 2),
                "lower": round(float(latest.get("bb_lower", close)), 2)
            },
            "atr_14": round(float(latest.get("atr_14", 0.0)), 2),
            "adx_14": round(float(latest.get("adx_14", 0.0)), 2),
            "volume_surge": bool(latest.get("volume_surge", False))
        },
        "levels": sr,
        "score": {
            "bullish_signals": bullish_signals,
            "bearish_signals": bearish_signals
        }
    }

