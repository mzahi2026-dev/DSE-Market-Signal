from fastapi.testclient import TestClient
from backend.main import app
from backend.ai_engine import (
    get_ai_config,
    analyze_stock_with_ai,
    review_signal_with_ai,
    get_ai_market_outlook
)


def test_ai_fallback_when_no_api_key(monkeypatch):
    # Ensure no API key in environment
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    res = analyze_stock_with_ai("GP")
    assert res["symbol"] == "GP"
    assert res["mode"] == "rule_based_fallback"
    assert "verdict" in res
    assert "summary" in res
    assert "key_catalysts" in res
    assert isinstance(res["key_catalysts"], list)
    assert "risks" in res
    assert "action_plan" in res


def test_ai_signal_review():
    review = review_signal_with_ai("GP")
    assert review["symbol"] == "GP"
    assert "algorithmic_signal" in review
    assert "ai_verdict" in review
    assert "consensus" in review
    assert review["consensus"] in ("ALIGNED", "DIVERGENT")


def test_ai_market_outlook():
    outlook = get_ai_market_outlook()
    assert outlook["status"] == "ok"
    assert "market_sentiment" in outlook
    assert "ai_commentary" in outlook


def test_api_ai_endpoints():
    with TestClient(app) as client:
        # AI Status
        status_res = client.get("/ai/status")
        assert status_res.status_code == 200
        data = status_res.json()
        assert data["status"] == "ok"
        assert "active_mode" in data

        # AI Analyze GP
        ana_res = client.get("/ai/analyze/GP")
        assert ana_res.status_code == 200
        ana_data = ana_res.json()
        assert ana_data["symbol"] == "GP"
        assert "summary" in ana_data

        # AI Signal Review
        rev_res = client.get("/ai/review-signal/GP")
        assert rev_res.status_code == 200
        assert "consensus" in rev_res.json()

        # AI Market Outlook
        out_res = client.get("/ai/market-outlook")
        assert out_res.status_code == 200
        assert "market_sentiment" in out_res.json()

