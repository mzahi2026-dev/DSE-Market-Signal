"""DSE Buy/Sell/Hold Signal Engine with Confluence and Filtering."""

from enum import Enum
from typing import Any, Dict, List, Optional
import pandas as pd
from backend.analysis import analyze_stock, get_stock_price_history
from backend.indicators import calculate_all_indicators


class SignalType(str, Enum):
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"


def generate_signal(symbol: str) -> Dict[str, Any]:
    """Evaluate multi-indicator confluence and generate a filtered trading signal."""
    df = get_stock_price_history(symbol)
    if df.empty or len(df) < 15:
        return {
            "symbol": symbol.upper(),
            "signal": SignalType.HOLD.value,
            "confidence": 0,
            "reasons": ["Insufficient historical data for confluence analysis"],
            "actionable": False
        }

    df_ind = calculate_all_indicators(df)
    latest = df_ind.iloc[-1]
    prev = df_ind.iloc[-2]

    close = float(latest["close"])
    prev_close = float(prev["close"])
    rsi = float(latest.get("rsi_14", 50.0))
    prev_rsi = float(prev.get("rsi_14", 50.0))
    macd_hist = float(latest.get("macd_histogram", 0.0))
    prev_macd_hist = float(prev.get("macd_histogram", 0.0))
    ema_9 = float(latest.get("ema_9", close))
    ema_21 = float(latest.get("ema_21", close))
    ema_50 = float(latest.get("ema_50", close))
    prev_ema_9 = float(prev.get("ema_9", prev_close))
    prev_ema_21 = float(prev.get("ema_21", prev_close))
    atr = float(latest.get("atr_14", close * 0.02))
    vol_surge = bool(latest.get("volume_surge", False))

    reasons = []
    bullish_points = 0
    bearish_points = 0
    total_checks = 6

    # 1. EMA Alignment and Cross
    if prev_ema_9 <= prev_ema_21 and ema_9 > ema_21:
        bullish_points += 2
        reasons.append("Bullish Golden Cross: EMA 9 crossed above EMA 21")
    elif ema_9 > ema_21 and close > ema_21:
        bullish_points += 1
        reasons.append("Price holding above EMA 9 and EMA 21")
    elif prev_ema_9 >= prev_ema_21 and ema_9 < ema_21:
        bearish_points += 2
        reasons.append("Bearish Death Cross: EMA 9 crossed below EMA 21")
    elif ema_9 < ema_21 and close < ema_21:
        bearish_points += 1
        reasons.append("Price trading below EMA 9 and EMA 21")

    # 2. MACD Momentum
    if prev_macd_hist <= 0 and macd_hist > 0:
        bullish_points += 2
        reasons.append("Bullish MACD crossover above signal line")
    elif macd_hist > 0 and macd_hist > prev_macd_hist:
        bullish_points += 1
        reasons.append("MACD histogram expanding positively")
    elif prev_macd_hist >= 0 and macd_hist < 0:
        bearish_points += 2
        reasons.append("Bearish MACD crossover below signal line")
    elif macd_hist < 0 and macd_hist < prev_macd_hist:
        bearish_points += 1
        reasons.append("MACD histogram expanding negatively")

    # 3. RSI Momentum & Overbought/Oversold
    if prev_rsi < 30 and rsi >= 30:
        bullish_points += 2
        reasons.append(f"RSI recovering from oversold territory ({rsi:.1f})")
    elif 50 <= rsi <= 68:
        bullish_points += 1
        reasons.append(f"RSI in healthy bullish momentum zone ({rsi:.1f})")
    elif rsi > 70:
        bearish_points += 2
        reasons.append(f"RSI in overbought zone ({rsi:.1f}) - risk of pullback")
    elif prev_rsi > 70 and rsi <= 70:
        bearish_points += 2
        reasons.append(f"RSI rolling over from overbought level ({rsi:.1f})")
    elif rsi < 40:
        bearish_points += 1
        reasons.append(f"RSI in weak bearish momentum zone ({rsi:.1f})")

    # 4. Long-term Trend (EMA 50)
    if close > ema_50:
        bullish_points += 1
        reasons.append("Price above 50 EMA baseline")
    else:
        bearish_points += 1
        reasons.append("Price below 50 EMA baseline")

    # 5. Volume Confirmation
    if vol_surge and close > prev_close:
        bullish_points += 1
        reasons.append("Above-average volume supporting price advance")
    elif vol_surge and close < prev_close:
        bearish_points += 1
        reasons.append("Heavy distribution volume on price decline")

    # Signal Classification and Confidence Scoring
    net_score = bullish_points - bearish_points
    max_possible = total_checks * 1.5

    if net_score >= 4:
        raw_signal = SignalType.STRONG_BUY
        confidence = min(95, int(60 + (net_score / max_possible) * 35))
    elif net_score >= 2:
        raw_signal = SignalType.BUY
        confidence = min(85, int(50 + (net_score / max_possible) * 35))
    elif net_score <= -4:
        raw_signal = SignalType.STRONG_SELL
        confidence = min(95, int(60 + (abs(net_score) / max_possible) * 35))
    elif net_score <= -2:
        raw_signal = SignalType.SELL
        confidence = min(85, int(50 + (abs(net_score) / max_possible) * 35))
    else:
        raw_signal = SignalType.HOLD
        confidence = 50

    # Signal Filtering: require confidence >= 60% and at least 2 reasons to be actionable
    actionable = (raw_signal in (SignalType.BUY, SignalType.STRONG_BUY, SignalType.SELL, SignalType.STRONG_SELL)) and (confidence >= 60)

    # Dynamic targets and stop loss based on ATR
    if raw_signal in (SignalType.BUY, SignalType.STRONG_BUY):
        stop_loss = round(close - (1.5 * atr), 2)
        target = round(close + (2.5 * atr), 2)
    elif raw_signal in (SignalType.SELL, SignalType.STRONG_SELL):
        stop_loss = round(close + (1.5 * atr), 2)
        target = round(close - (2.5 * atr), 2)
    else:
        stop_loss = round(close - (1.5 * atr), 2)
        target = round(close + (1.5 * atr), 2)

    risk_reward = round(abs(target - close) / max(0.01, abs(close - stop_loss)), 2)

    return {
        "symbol": symbol.upper(),
        "date": str(latest["date"]),
        "close": close,
        "signal": raw_signal.value,
        "confidence": confidence,
        "actionable": actionable,
        "target": target,
        "stop_loss": stop_loss,
        "risk_reward_ratio": risk_reward,
        "reasons": reasons,
        "scores": {
            "bullish_points": bullish_points,
            "bearish_points": bearish_points,
            "net_score": net_score
        }
    }

