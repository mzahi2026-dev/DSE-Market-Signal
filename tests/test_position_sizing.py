import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.position_sizing import (
    calculate_position_size,
    get_position_recommendation_for_symbol
)


def test_position_sizing_risk_constraint():
    # Capital: 100,000, Risk: 2% = 2,000 max loss
    # Entry: 200, Stop Loss: 190 -> Risk per share: 10
    # Quantity by risk = 2000 / 10 = 200 shares
    # Allocation: 200 * 200 = 40,000 (40% of capital, exceeds 20% max allocation limit of 20,000)
    # Quantity by allocation = 20,000 / 200 = 100 shares
    # Therefore, allocation constraint limits to 100 shares!
    res = calculate_position_size(
        total_capital=100000.0,
        entry_price=200.0,
        stop_loss=190.0,
        risk_pct=2.0,
        max_allocation_pct=20.0
    )
    assert res["recommended_quantity"] == 100
    assert res["limiting_factor"] == "max_capital_allocation"
    assert res["investment_required"] == 20000.0
    assert res["portfolio_weight_pct"] == 20.0
    assert res["potential_loss"] == 1000.0  # 100 shares * 10 loss = 1000 <= 2000 limit


def test_position_sizing_risk_limited():
    # Capital: 100,000, Risk: 1% = 1,000 max loss
    # Entry: 100, Stop Loss: 80 -> Risk per share: 20
    # Shares by risk = 1,000 / 20 = 50 shares (Cost = 5,000 = 5% of portfolio, below 20% cap)
    res = calculate_position_size(
        total_capital=100000.0,
        entry_price=100.0,
        stop_loss=80.0,
        risk_pct=1.0,
        max_allocation_pct=20.0
    )
    assert res["recommended_quantity"] == 50
    assert res["limiting_factor"] == "risk_per_trade"
    assert res["investment_required"] == 5000.0
    assert res["potential_loss"] == 1000.0


def test_position_sizing_invalid_inputs():
    with pytest.raises(ValueError, match="Total capital must be greater than zero"):
        calculate_position_size(0, 100, 90)

    with pytest.raises(ValueError, match="cannot be identical"):
        calculate_position_size(100000, 100, 100)


def test_api_position_sizing():
    with TestClient(app) as client:
        # Calculate endpoint
        calc_res = client.post(
            "/position/calculate?total_capital=100000&entry_price=250&stop_loss=240&risk_pct=2&max_allocation_pct=20"
        )
        assert calc_res.status_code == 200
        data = calc_res.json()
        assert data["recommended_quantity"] > 0
        assert data["investment_required"] <= 20000.0

        # Recommendation endpoint for GP
        rec_res = client.get("/position/recommendation/GP")
        assert rec_res.status_code == 200
        rec_data = rec_res.json()
        assert rec_data["symbol"] == "GP"
        assert "sizing" in rec_data
        assert "recommended_quantity" in rec_data["sizing"]

