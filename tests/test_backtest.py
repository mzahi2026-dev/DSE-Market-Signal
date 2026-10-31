from fastapi.testclient import TestClient
from backend.main import app
from backend.backtesting import run_backtest


def test_backtest_execution():
    res = run_backtest(
        symbol="GP",
        initial_capital=100000.0,
        risk_per_trade_pct=2.0,
        max_allocation_pct=25.0
    )
    assert res["symbol"] == "GP"
    assert res["initial_capital"] == 100000.0
    assert "final_equity" in res
    assert "total_pnl" in res
    assert "total_return_pct" in res
    assert "max_drawdown_pct" in res
    assert "total_trades" in res
    assert "win_rate_pct" in res
    assert "profit_factor" in res
    assert "trades" in res
    assert isinstance(res["trades"], list)


def test_api_backtest_endpoint():
    with TestClient(app) as client:
        res = client.post("/backtest/run?symbol=GP&initial_capital=100000")
        assert res.status_code == 200
        data = res.json()
        assert data["symbol"] == "GP"
        assert "final_equity" in data

