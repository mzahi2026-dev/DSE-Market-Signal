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

