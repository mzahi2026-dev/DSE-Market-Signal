import numpy as np
import pandas as pd
from backend.indicators import (
    compute_sma,
    compute_ema,
    compute_rsi,
    compute_macd,
    compute_bollinger_bands,
    compute_atr,
    compute_adx,
    calculate_all_indicators
)


def test_sma_calculation():
    s = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0])
    sma = compute_sma(s, 3)
    assert len(sma) == 5
    assert sma.iloc[-1] == 40.0  # (30 + 40 + 50) / 3


def test_ema_calculation():
    s = pd.Series([10.0, 11.0, 12.0, 13.0, 14.0])
    ema = compute_ema(s, 3)
    assert len(ema) == 5
    assert ema.iloc[-1] > ema.iloc[0]


def test_rsi_bounds_and_values():
    # Constant series -> neutral RSI ~50
    s = pd.Series([100.0] * 30)
    rsi = compute_rsi(s, 14)
    assert 40.0 <= rsi.iloc[-1] <= 60.0

    # Strictly increasing -> high RSI > 70
    s_up = pd.Series([float(i) for i in range(1, 40)])
    rsi_up = compute_rsi(s_up, 14)
    assert rsi_up.iloc[-1] > 70.0

    # Strictly decreasing -> low RSI < 30
    s_down = pd.Series([float(100 - i) for i in range(1, 40)])
    rsi_down = compute_rsi(s_down, 14)
    assert rsi_down.iloc[-1] < 30.0


def test_macd_calculation():
    s = pd.Series([float(i) for i in range(1, 60)])
    macd, signal, hist = compute_macd(s)
    assert len(macd) == len(s)
    assert len(signal) == len(s)
    assert len(hist) == len(s)
    assert np.allclose(hist, macd - signal)


def test_bollinger_bands():
    s = pd.Series([10.0, 12.0, 11.0, 13.0, 15.0, 14.0, 16.0, 15.0, 17.0, 16.0] * 3)
    upper, mid, lower = compute_bollinger_bands(s, period=10)
    assert len(upper) == len(s)
    assert (upper >= mid).all()
    assert (mid >= lower).all()


def test_atr_and_adx():
    high = pd.Series([15.0, 16.0, 17.0, 18.0, 19.0, 20.0, 21.0, 22.0] * 3)
    low = pd.Series([10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0] * 3)
    close = pd.Series([12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0] * 3)

    atr = compute_atr(high, low, close, 14)
    assert (atr > 0).all()

    adx, plus_di, minus_di = compute_adx(high, low, close, 14)
    assert len(adx) == len(high)
    assert (adx >= 0).all()


def test_calculate_all_indicators_df():
    data = {
        "date": [f"2026-01-{i:02d}" for i in range(1, 31)],
        "open": [100.0 + i for i in range(30)],
        "high": [105.0 + i for i in range(30)],
        "low": [95.0 + i for i in range(30)],
        "close": [102.0 + i for i in range(30)],
        "volume": [1000.0 * (i + 1) for i in range(30)]
    }
    df = pd.DataFrame(data)
    res = calculate_all_indicators(df)
    for col in [
        "sma_9", "sma_20", "sma_50", "ema_9", "ema_21", "ema_50",
        "rsi_14", "macd_line", "macd_signal", "macd_histogram",
        "bb_upper", "bb_middle", "bb_lower", "atr_14", "adx_14",
        "volume_sma_20", "volume_surge"
    ]:
        assert col in res.columns

