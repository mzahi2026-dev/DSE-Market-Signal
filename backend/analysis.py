"""Stock technical analysis and trend evaluation module."""

from typing import Any, Dict, List, Optional
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
    if limit and len(df) > limit:
        df = df.iloc[-limit:].reset_index(drop=True)
    return df


def calculate_support_resistance(df: pd.DataFrame, window: int = 20) -> Dict[str, float]:
    """Calculate key support, resistance, and pivot levels from price history."""
    if df.empty:
        return {"support_1": 0.0, "support_2": 0.0, "resistance_1": 0.0, "resistance_2": 0.0, "pivot": 0.0}

    latest = df.iloc[-1]
    high = float(df["high"].tail(window).max())
    low = float(df["low"].tail(window).min())
    close = float(latest["close"])

    # Standard Classic Pivot Points
    pivot = (latest["high"] + latest["low"] + latest["close"]) / 3.0
    r1 = (2 * pivot) - latest["low"]
    s1 = (2 * pivot) - latest["high"]
    r2 = pivot + (latest["high"] - latest["low"])
    s2 = pivot - (latest["high"] - latest["low"])

    return {
        "pivot": round(pivot, 2),
        "support_1": round(s1, 2),
        "support_2": round(s2, 2),
        "resistance_1": round(r1, 2),
        "resistance_2": round(r2, 2),
        "swing_high": round(high, 2),
        "swing_low": round(low, 2)
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

