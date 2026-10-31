from fastapi.testclient import TestClient
from backend.main import app
from backend.signals import generate_signal, SignalType
from backend.telegram import format_signal_message, send_telegram_alert


def test_generate_signal_gp():
    sig = generate_signal("GP")
    assert sig["symbol"] == "GP"
    assert "signal" in sig
    assert sig["signal"] in [s.value for s in SignalType]
    assert 0 <= sig["confidence"] <= 100
    assert "reasons" in sig
    assert isinstance(sig["reasons"], list)
    assert "target" in sig
    assert "stop_loss" in sig
    assert "risk_reward_ratio" in sig


def test_telegram_format_message():
    sample_signal = {
        "symbol": "GP",
        "date": "2026-10-29",
        "close": 245.5,
        "signal": "BUY",
        "confidence": 75,
        "target": 260.0,
        "stop_loss": 235.0,
        "risk_reward_ratio": 1.45,
        "reasons": ["Bullish Golden Cross", "MACD histogram positive"]
    }
    msg = format_signal_message(sample_signal)
    assert "DSE MARKET SIGNAL: GP" in msg
    assert "BUY" in msg
    assert "BDT 245.50" in msg
    assert "Bullish Golden Cross" in msg


def test_telegram_fallback_simulation():
    sample_signal = {
        "symbol": "GP",
        "date": "2026-10-29",
        "close": 245.5,
        "signal": "BUY",
        "confidence": 75,
        "target": 260.0,
        "stop_loss": 235.0,
        "risk_reward_ratio": 1.45,
        "reasons": ["Bullish Golden Cross"]
    }
    # With empty bot token, should simulate gracefully
    res = send_telegram_alert(sample_signal, config={"bot_token": "", "chat_id": ""})
    assert res["status"] == "simulated"
    assert res["delivered"] is False
    assert "preview" in res


def test_api_signals_endpoint():
    with TestClient(app) as client:
        res = client.get("/signals/GP")
        assert res.status_code == 200
        data = res.json()
        assert data["symbol"] == "GP"
        assert "signal" in data

        res_all = client.get("/signals")
        assert res_all.status_code == 200
        data_all = res_all.json()
        assert data_all["count"] >= 1


def test_api_signal_notify_endpoint():
    with TestClient(app) as client:
        res = client.post("/signals/notify/GP")
        assert res.status_code == 200
        data = res.json()
        assert "signal" in data
        assert "notification" in data
        assert data["notification"]["status"] in ("simulated", "delivered")

