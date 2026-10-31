import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.paper_trading import (
    reset_account,
    get_or_create_account,
    place_order,
    get_portfolio,
    get_trade_history
)


@pytest.fixture(autouse=True)
def clean_test_account():
    # Use dedicated test account to avoid interfering with any default data
    reset_account("test_user", initial_capital=100000.0)
    yield
    reset_account("test_user", initial_capital=100000.0)


def test_account_creation_and_balance():
    acc = get_or_create_account("test_user", initial_capital=100000.0)
    assert acc["account_id"] == "test_user"
    assert acc["cash_balance"] == 100000.0
    assert acc["initial_capital"] == 100000.0
    assert acc["realized_pnl"] == 0.0


def test_buy_and_sell_order_execution():
    # Place BUY order: 10 GP shares @ 240.0 = 2400.0 cost (within circuit limits)
    buy_res = place_order(
        account_id="test_user",
        symbol="GP",
        side="BUY",
        quantity=10,
        price=240.0
    )
    assert buy_res["status"] == "FILLED"
    assert buy_res["side"] == "BUY"
    assert buy_res["total_value"] == 2400.0

    port_after_buy = get_portfolio("test_user")
    assert port_after_buy["cash_balance"] == 100000.0 - 2400.0
    assert len(port_after_buy["positions"]) == 1
    assert port_after_buy["positions"][0]["symbol"] == "GP"
    assert port_after_buy["positions"][0]["quantity"] == 10
    assert port_after_buy["positions"][0]["avg_entry_price"] == 240.0

    # Place SELL order: 10 GP shares @ 250.0 = 2500.0 revenue (Profit = +100.0, within circuit limits)
    sell_res = place_order(
        account_id="test_user",
        symbol="GP",
        side="SELL",
        quantity=10,
        price=250.0
    )
    assert sell_res["status"] == "FILLED"
    assert sell_res["realized_pnl"] == 100.0

    port_after_sell = get_portfolio("test_user")
    assert port_after_sell["cash_balance"] == 100100.0
    assert port_after_sell["realized_pnl"] == 100.0
    assert len(port_after_sell["positions"]) == 0

    trades = get_trade_history("test_user")
    assert len(trades) == 2
    assert trades[0]["side"] == "SELL"
    assert trades[1]["side"] == "BUY"


def test_insufficient_funds_rejected():
    with pytest.raises(ValueError, match="Insufficient cash balance"):
        place_order(
            account_id="test_user",
            symbol="GP",
            side="BUY",
            quantity=10000,
            price=250.0,  # 2,500,000 exceeds 100,000 balance
            enforce_risk_limits=False
        )


def test_insufficient_shares_rejected():
    with pytest.raises(ValueError, match="Insufficient shares"):
        place_order(
            account_id="test_user",
            symbol="GP",
            side="SELL",
            quantity=5,
            price=240.0
        )


def test_dse_circuit_limit_enforced():
    """Verify that orders violating DSE circuit band are rejected."""
    with pytest.raises(ValueError, match="exceeds upper circuit limit"):
        place_order(
            account_id="test_user",
            symbol="GP",
            side="BUY",
            quantity=10,
            price=280.0  # Exceeds +8.75% circuit limit
        )


def test_dse_tick_size_enforced():
    """Verify that orders violating 0.10 BDT tick size are rejected."""
    with pytest.raises(ValueError, match="violates DSE tick size"):
        place_order(
            account_id="test_user",
            symbol="GP",
            side="BUY",
            quantity=10,
            price=240.05
        )


def test_dse_invalid_category_and_side_enforced():
    """Verify invalid side or unknown category are rejected."""
    with pytest.raises(ValueError, match="Side must be BUY or SELL"):
        place_order(account_id="test_user", symbol="GP", side="HOLD", quantity=10, price=240.0)

    with pytest.raises(ValueError, match="Invalid stock category"):
        place_order(account_id="test_user", symbol="GP", side="BUY", quantity=10, price=240.0, category="INVALID")


def test_risk_limits_enforced():
    """Verify that orders violating risk limits (e.g. single stock allocation limit) are rejected."""
    with pytest.raises(ValueError, match="Concentration limit exceeded"):
        place_order(
            account_id="test_user",
            symbol="GP",
            side="BUY",
            quantity=200,
            price=240.0  # 48,000 = 48% > 25% max allocation
        )


def test_low_risk_reward_rejected():
    """Verify that BUY orders with R:R < 1.5 are rejected."""
    with pytest.raises(ValueError, match="Low Risk/Reward Ratio"):
        place_order(
            account_id="test_user",
            symbol="GP",
            side="BUY",
            quantity=5,
            price=240.0,
            stop_loss=235.0,  # risk = 5.0
            target=244.0       # reward = 4.0, RRR = 0.8 < 1.5
        )


def test_limit_order_pending_behavior():
    """Verify that BUY limit orders below market price remain PENDING."""
    order_res = place_order(
        account_id="test_user",
        symbol="GP",
        side="BUY",
        quantity=5,
        price=220.0,  # Below market price (237.3)
        order_type="LIMIT"
    )
    assert order_res["status"] == "PENDING"
    # Cash not deducted
    port = get_portfolio("test_user")
    assert port["cash_balance"] == 100000.0


def test_api_paper_trading():
    with TestClient(app) as client:
        # Check initial portfolio
        res = client.get("/paper/portfolio?account_id=test_user")
        assert res.status_code == 200
        data = res.json()
        assert data["cash_balance"] == 100000.0

        # Execute order via API
        order_res = client.post(
            "/paper/order?account_id=test_user&symbol=GP&side=BUY&quantity=5&price=250"
        )
        assert order_res.status_code == 200
        assert order_res.json()["status"] == "FILLED"

        # Check trades list via API
        trades_res = client.get("/paper/trades?account_id=test_user")
        assert trades_res.status_code == 200
        assert len(trades_res.json()["trades"]) == 1

        # Reset account via API
        reset_res = client.post("/paper/reset?account_id=test_user&initial_capital=50000")
        assert reset_res.status_code == 200
        assert reset_res.json()["cash_balance"] == 50000.0

