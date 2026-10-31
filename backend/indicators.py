"""Technical Indicators calculation module for DSE market data."""

from typing import Dict, List, Optional
import numpy as np
import pandas as pd


def compute_sma(series: pd.Series, period: int) -> pd.Series:
    """Simple Moving Average."""
    return series.rolling(window=period, min_periods=1).mean()


def compute_ema(series: pd.Series, period: int) -> pd.Series:
    """Exponential Moving Average."""
    return series.ewm(span=period, adjust=False).mean()


def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index (Wilder's RSI)."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    # Wilder's smoothing
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()

    rsi = pd.Series(50.0, index=close.index)

    # Where both are zero (flat price), RSI is 50.0
    zero_both = (avg_gain == 0) & (avg_loss == 0)
    # Where loss is zero and gain > 0, RSI is 100.0
    zero_loss = (avg_loss == 0) & (avg_gain > 0)
    # Where gain is zero and loss > 0, RSI is 0.0
    zero_gain = (avg_gain == 0) & (avg_loss > 0)

    normal = (~zero_both) & (~zero_loss) & (~zero_gain) & avg_loss.notna() & avg_gain.notna()

    rs = avg_gain[normal] / avg_loss[normal]
    rsi[normal] = 100.0 - (100.0 / (1.0 + rs))
    rsi[zero_loss] = 100.0
    rsi[zero_gain] = 0.0
    rsi[zero_both] = 50.0

    return rsi.fillna(50.0)


def compute_macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """Moving Average Convergence Divergence."""
    ema_fast = compute_ema(close, fast)
    ema_slow = compute_ema(close, slow)
    macd_line = ema_fast - ema_slow
    signal_line = compute_ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def compute_bollinger_bands(close: pd.Series, period: int = 20, num_std: float = 2.0):
    """Bollinger Bands."""
    middle = compute_sma(close, period)
    std = close.rolling(window=period, min_periods=1).std().fillna(0)
    upper = middle + (std * num_std)
    lower = middle - (std * num_std)
    return upper, middle, lower


def compute_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Average True Range (ATR)."""
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = true_range.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    return atr.fillna(true_range)


def compute_adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14):
    """Average Directional Index (ADX), +DI, -DI."""
    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    atr = compute_atr(high, low, close, period)
    plus_di = 100 * (pd.Series(plus_dm, index=high.index).ewm(alpha=1/period, adjust=False).mean() / atr.replace(0, np.nan))
    minus_di = 100 * (pd.Series(minus_dm, index=low.index).ewm(alpha=1/period, adjust=False).mean() / atr.replace(0, np.nan))

    dx = (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan) * 100
    adx = dx.ewm(alpha=1/period, adjust=False).mean().fillna(20.0)
    return adx, plus_di.fillna(0.0), minus_di.fillna(0.0)


def calculate_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Take a DataFrame with columns ['date', 'open', 'high', 'low', 'close', 'volume']
    sorted ascending by date, and compute all technical indicators.
    """
    if df.empty or len(df) < 2:
        return df

    out = df.copy()
    out = out.sort_values("date").reset_index(drop=True)

    close = out["close"]
    high = out["high"]
    low = out["low"]
    volume = out["volume"]

    # Moving averages
    out["sma_9"] = compute_sma(close, 9)
    out["sma_20"] = compute_sma(close, 20)
    out["sma_50"] = compute_sma(close, 50)
    out["ema_9"] = compute_ema(close, 9)
    out["ema_21"] = compute_ema(close, 21)
    out["ema_50"] = compute_ema(close, 50)

    # Momentum
    out["rsi_14"] = compute_rsi(close, 14)
    macd_line, macd_sig, macd_hist = compute_macd(close)
    out["macd_line"] = macd_line
    out["macd_signal"] = macd_sig
    out["macd_histogram"] = macd_hist

    # Volatility
    bb_upper, bb_mid, bb_lower = compute_bollinger_bands(close, 20, 2.0)
    out["bb_upper"] = bb_upper
    out["bb_middle"] = bb_mid
    out["bb_lower"] = bb_lower
    out["atr_14"] = compute_atr(high, low, close, 14)

    # Trend Strength
    adx, pdi, mdi = compute_adx(high, low, close, 14)
    out["adx_14"] = adx
    out["plus_di"] = pdi
    out["minus_di"] = mdi

    # Volume Indicators
    out["volume_sma_20"] = compute_sma(volume, 20)
    out["volume_surge"] = out["volume"] > (out["volume_sma_20"] * 1.5)

    return out
