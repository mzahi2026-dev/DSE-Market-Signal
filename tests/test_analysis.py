from fastapi.testclient import TestClient
from backend.main import app
from backend.analysis import analyze_stock, calculate_support_resistance
from backend.market_summary import get_market_summary


def test_analyze_stock_gp():
    result = analyze_stock("GP")
    assert result["symbol"] == "GP"
    assert "price" in result
    assert "close" in result["price"]
    assert "trend" in result
    assert result["trend"] in ("Bullish", "Bearish", "Neutral")
    assert "indicators" in result
    assert "rsi_14" in result["indicators"]
    assert "macd" in result["indicators"]
    assert "levels" in result
    assert "pivot" in result["levels"]
    assert "support_1" in result["levels"]
    assert "resistance_1" in result["levels"]


def test_market_summary_calculation():
    summary = get_market_summary()
    assert summary["status"] == "ok"
    assert summary["total_stocks"] >= 1
    assert "advancers" in summary
    assert "decliners" in summary
    assert "unchanged" in summary
    assert "sentiment" in summary
    assert "top_gainers" in summary
    assert "top_losers" in summary


def test_api_stock_analysis():
    with TestClient(app) as client:
        res = client.get("/analysis/GP")
        assert res.status_code == 200
        data = res.json()
        assert data["symbol"] == "GP"
        assert "price" in data
        assert "indicators" in data


def test_api_stock_indicators():
    with TestClient(app) as client:
        res = client.get("/indicators/GP?limit=20")
        assert res.status_code == 200
        data = res.json()
        assert data["symbol"] == "GP"
        assert len(data["data"]) <= 20
        assert "rsi_14" in data["data"][-1]
        assert "ema_21" in data["data"][-1]


def test_api_market_summary():
    with TestClient(app) as client:
        res = client.get("/market/summary")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert "sentiment" in data


def test_support_resistance_strict_ordering():
    from backend.analysis import get_stock_price_history, calculate_support_resistance
    for sym in ["GP", "BATBC", "SQURPHARMA"]:
        df = get_stock_price_history(sym, limit=30)
        if not df.empty and len(df) >= 5:
            levels = calculate_support_resistance(df)
            close = float(df.iloc[-1]["close"])
            assert levels["support_1"] < close, f"{sym}: support_1 {levels['support_1']} must be < close {close}"
            assert levels["resistance_1"] > close, f"{sym}: resistance_1 {levels['resistance_1']} must be > close {close}"
            assert levels["support_2"] <= levels["support_1"]
            assert levels["resistance_2"] >= levels["resistance_1"]
            assert levels["support_1"] <= levels["pivot"] <= levels["resistance_1"]


def test_support_resistance_flat_bar_fallback():
    import pandas as pd
    from backend.analysis import calculate_support_resistance
    # Simulate completely flat DSE floor price days where high == low == close
    flat_data = [
        {"date": f"2026-10-{i:02d}", "open": 200.0, "high": 200.0, "low": 200.0, "close": 200.0, "volume": 1000}
        for i in range(1, 15)
    ]
    df = pd.DataFrame(flat_data)
    levels = calculate_support_resistance(df)
    assert levels["support_1"] < 200.0, "Support 1 must be below close even on flat bars"
    assert levels["resistance_1"] > 200.0, "Resistance 1 must be above close even on flat bars"
    assert levels["support_1"] < levels["resistance_1"], "S1 and R1 must not collapse into identical value"


def test_support_resistance_empty_df():
    import pandas as pd
    from backend.analysis import calculate_support_resistance
    levels = calculate_support_resistance(pd.DataFrame())
    assert levels["support_1"] == 0.0
    assert levels["resistance_1"] == 0.0
    assert levels["pivot"] == 0.0

