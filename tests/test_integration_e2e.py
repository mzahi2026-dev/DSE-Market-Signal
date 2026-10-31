from fastapi.testclient import TestClient
from backend.main import app
from backend.db import connect


def test_full_project_end_to_end_integration():
    """Verify end-to-end workflow across data, indicators, signals, risk, paper trading, and frontend."""
    with TestClient(app) as client:
        # 1. Health & Scheduler
        h_res = client.get("/health")
        assert h_res.status_code == 200
        assert h_res.json()["status"] == "ok"

        # 2. Database Prices
        p_res = client.get("/prices?symbol=GP&limit=5")
        assert p_res.status_code == 200
        assert len(p_res.json()["rows"]) > 0

        # 3. Market Analysis & Breadth
        m_res = client.get("/market/summary")
        assert m_res.status_code == 200
        assert m_res.json()["total_stocks"] >= 1

        # 4. Technical Indicators
        ind_res = client.get("/indicators/GP?limit=10")
        assert ind_res.status_code == 200
        assert len(ind_res.json()["data"]) > 0

        # 5. Algorithmic Signals
        sig_res = client.get("/signals/GP")
        assert sig_res.status_code == 200
        sig_data = sig_res.json()
        assert sig_data["signal"] in ("STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL")

        # 6. Position Sizing
        pos_res = client.post("/position/calculate?total_capital=100000&entry_price=250&stop_loss=240")
        assert pos_res.status_code == 200
        assert pos_res.json()["recommended_quantity"] > 0

        # 7. Risk Management Evaluation
        risk_res = client.post("/risk/evaluate?symbol=GP&side=BUY&quantity=5&price=250&stop_loss=240&target=270")
        assert risk_res.status_code == 200

        # 8. DSE Rules & Limits
        circ_res = client.get("/dse/circuit-limits/GP")
        assert circ_res.status_code == 200

        # 9. Paper Trading Execution
        client.post("/paper/reset?account_id=e2e_user&initial_capital=100000")
        order_res = client.post("/paper/order?account_id=e2e_user&symbol=GP&side=BUY&quantity=5&price=250")
        assert order_res.status_code == 200

        port_res = client.get("/paper/portfolio?account_id=e2e_user")
        assert port_res.status_code == 200
        assert len(port_res.json()["positions"]) == 1

        # 10. AI Second Opinion
        ai_res = client.get("/ai/analyze/GP")
        assert ai_res.status_code == 200

        # 11. Engine Pipeline
        pipe_res = client.get("/engine/pipeline/GP?account_id=e2e_user")
        assert pipe_res.status_code == 200

        # 12. Automation Subsystem
        auto_res = client.get("/automation/status")
        assert auto_res.status_code == 200

        # 13. Charts
        chart_res = client.get("/charts/full/GP?limit=20")
        assert chart_res.status_code == 200

        # 14. Screener & Watchlist
        screen_res = client.get("/screener/scan")
        assert screen_res.status_code == 200

        client.post("/watchlist/add?symbol=GP&note=e2e_verified")
        wl_res = client.get("/watchlist")
        assert wl_res.status_code == 200

        # 15. Backtest
        bt_res = client.post("/backtest/run?symbol=GP")
        assert bt_res.status_code == 200

        # 16. TradingView Frontend
        front_res = client.get("/")
        assert front_res.status_code == 200
        assert "TradingView Dashboard" in front_res.text

