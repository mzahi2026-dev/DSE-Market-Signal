from fastapi.testclient import TestClient
from backend.main import app
from backend.chart_service import get_full_chart_data


def test_full_chart_data_structure():
    data = get_full_chart_data("GP", limit=50)
    assert data["symbol"] == "GP"
    assert "candlesticks" in data
    assert len(data["candlesticks"]) <= 50

    c0 = data["candlesticks"][0]
    assert "time" in c0
    assert "open" in c0
    assert "high" in c0
    assert "low" in c0
    assert "close" in c0
    assert "is_bullish" in c0
    assert c0["high"] >= c0["low"]

    assert "overlays" in data
    assert "ema_9" in data["overlays"]
    assert "indicators" in data
    assert "rsi" in data["indicators"]
    assert "macd" in data["indicators"]
    assert "levels" in data
    assert "support_1" in data["levels"]
    assert "resistance_1" in data["levels"]


def test_api_chart_endpoints():
    with TestClient(app) as client:
        # Full chart
        full_res = client.get("/charts/full/GP?limit=30")
        assert full_res.status_code == 200
        assert full_res.json()["symbol"] == "GP"

        # Candlestick endpoint
        candle_res = client.get("/charts/candlestick/GP")
        assert candle_res.status_code == 200
        assert "candlesticks" in candle_res.json()

        # RSI endpoint
        rsi_res = client.get("/charts/rsi/GP")
        assert rsi_res.status_code == 200
        assert "rsi" in rsi_res.json()

        # MACD endpoint
        macd_res = client.get("/charts/macd/GP")
        assert macd_res.status_code == 200
        assert "macd" in macd_res.json()

