import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.paper_trading import reset_account
from backend.risk_management import (
    calculate_stop_loss_levels,
    calculate_targets_and_rrr,
    update_trailing_stop,
    evaluate_order_risk,
    DEFAULT_RISK_CONFIG
)


def test_stop_loss_level_calculation():
    levels = calculate_stop_loss_levels(
        entry_price=200.0,
        atr=5.0,
        swing_low=191.0,
        fixed_pct=5.0
    )
    assert levels["fixed_percent_stop"] == 190.0   # 200 * 0.95
    assert levels["atr_volatility_stop"] == 192.5  # 200 - 1.5*5
    assert levels["market_structure_stop"] == round(191.0 * 0.99, 2)
    assert levels["recommended_stop_loss"] < 200.0


def test_risk_reward_ratio_calculation():
    rrr_valid = calculate_targets_and_rrr(
        entry_price=100.0,
        stop_loss=90.0,   # Risk = 10
        resistance_level=125.0  # Reward = 25 -> RRR = 2.5
    )
    assert rrr_valid["risk_amount"] == 10.0
    assert rrr_valid["risk_reward_ratio"] == 2.5
    assert rrr_valid["is_acceptable_rrr"] is True

    rrr_invalid = calculate_targets_and_rrr(
        entry_price=100.0,
        stop_loss=90.0,
        resistance_level=110.0  # Reward = 10 -> RRR = 1.0 < 1.5
    )
    assert rrr_invalid["risk_reward_ratio"] == 1.0
    assert rrr_invalid["is_acceptable_rrr"] is False


def test_trailing_stop_movement():
    # If price moves higher (entry 100, high 120, stop 95)
    res1 = update_trailing_stop(
        entry_price=100.0,
        highest_price=120.0,
        current_price=120.0,
        current_stop_loss=95.0,
        trailing_pct=5.0
    )
    # 5% from 120 = 114.0, which is > 95.0, so stop should move up to 114.0
    assert res1["new_stop_loss"] == 114.0
    assert res1["stop_updated"] is True

    # If price pulls back (from 120 to 116), stop loss must NEVER decrease!
    res2 = update_trailing_stop(
        entry_price=100.0,
        highest_price=120.0,
        current_price=116.0,
        current_stop_loss=114.0,
        trailing_pct=5.0
    )
    assert res2["new_stop_loss"] == 114.0
    assert res2["stop_updated"] is False


def test_evaluate_order_risk_circuit_breaker():
    reset_account("risk_test_user", initial_capital=100000.0)

    # Normal order approval
    ok_eval = evaluate_order_risk(
        account_id="risk_test_user",
        symbol="GP",
        side="BUY",
        quantity=10,
        price=200.0,
        stop_loss=190.0,
        target=220.0
    )
    assert ok_eval["is_approved"] is True

    # Low R:R rejection
    low_rrr_eval = evaluate_order_risk(
        account_id="risk_test_user",
        symbol="GP",
        side="BUY",
        quantity=10,
        price=200.0,
        stop_loss=195.0,  # risk = 5.0
        target=204.0       # reward = 4.0, RRR = 0.8 < 1.5
    )
    assert low_rrr_eval["is_approved"] is False
    assert any("Low Risk/Reward Ratio" in r for r in low_rrr_eval["reasons"])


def test_drawdown_calculated_from_peak_equity():
    """Verify drawdown is calculated from peak equity, not just initial capital."""
    from backend.db import connect
    from backend.paper_trading import get_portfolio

    reset_account("peak_user", initial_capital=100000.0)

    # Set peak equity to 200,000, and current equity to 170,000 (15% drawdown from peak)
    with connect() as con:
        con.execute(
            "UPDATE virtual_accounts SET peak_equity=200000.0, cash_balance=170000.0 WHERE account_id='peak_user'"
        )
        con.commit()

    port = get_portfolio("peak_user")
    assert port["peak_equity"] == 200000.0
    assert port["total_equity"] == 170000.0

    eval_res = evaluate_order_risk(
        account_id="peak_user",
        symbol="GP",
        side="BUY",
        quantity=5,
        price=200.0
    )
    # Drawdown is 15.0% > 10.0% max limit -> must be rejected
    assert eval_res["is_approved"] is False
    assert any("Drawdown Circuit Breaker active" in r for r in eval_res["reasons"])
    assert any("15.0%" in r for r in eval_res["reasons"])


def test_api_risk_endpoints():
    with TestClient(app) as client:
        # Evaluate order
        res = client.post(
            "/risk/evaluate?account_id=risk_test_user&symbol=GP&side=BUY&quantity=5&price=200&stop_loss=190&target=225"
        )
        assert res.status_code == 200
        assert res.json()["is_approved"] is True

        # Account risk status
        acc_res = client.get("/risk/account/risk_test_user")
        assert acc_res.status_code == 200
        assert acc_res.json()["circuit_breaker_active"] is False

        # Trailing stop endpoint
        trail_res = client.post(
            "/risk/trailing-stop?entry_price=100&highest_price=120&current_price=120&current_stop_loss=95&trailing_pct=5"
        )
        assert trail_res.status_code == 200
        assert trail_res.json()["new_stop_loss"] == 114.0

