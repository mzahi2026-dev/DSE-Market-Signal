from fastapi.testclient import TestClient
from backend.main import app
from backend.dse_rules import (
    get_circuit_percentage,
    calculate_circuit_limits,
    is_valid_tick_size,
    validate_dse_order,
    get_dse_session_status
)


def test_circuit_percentage_brackets():
    # <= 200 -> 10%
    assert get_circuit_percentage(150.0) == 10.0
    # 201 to 500 -> 8.75%
    assert get_circuit_percentage(250.0) == 8.75
    # 501 to 1000 -> 7.5%
    assert get_circuit_percentage(750.0) == 7.5
    # 1001 to 2000 -> 6.25%
    assert get_circuit_percentage(1500.0) == 6.25
    # 2001 to 5000 -> 5.0%
    assert get_circuit_percentage(3000.0) == 5.0
    # > 5000 -> 3.75%
    assert get_circuit_percentage(6000.0) == 3.75


def test_circuit_limits_calculation():
    # Price 250.0 -> 8.75% = delta 21.875
    # Upper = 271.9, Lower = 228.1
    limits = calculate_circuit_limits(250.0)
    assert limits["circuit_percentage"] == 8.75
    assert limits["upper_limit"] == 271.9
    assert limits["lower_limit"] == 228.1


def test_tick_size_validation():
    # 0.10 multiples valid
    assert is_valid_tick_size(245.50) is True
    assert is_valid_tick_size(245.10) is True
    assert is_valid_tick_size(245.00) is True
    # Non-0.10 invalid
    assert is_valid_tick_size(245.55) is False
    assert is_valid_tick_size(245.123) is False


def test_validate_dse_order_policies():
    # Valid order: 250 close, order at 255.0, Category A
    res_valid = validate_dse_order(
        symbol="GP",
        side="BUY",
        quantity=10,
        price=255.0,
        prev_close=250.0,
        category="A"
    )
    assert res_valid["is_valid"] is True
    assert res_valid["settlement_cycle"] == "T+2"
    assert res_valid["margin_eligible"] is True

    # Category Z order: T+3 settlement, non-marginable
    res_z = validate_dse_order(
        symbol="GP",
        side="BUY",
        quantity=10,
        price=255.0,
        prev_close=250.0,
        category="Z"
    )
    assert res_z["settlement_cycle"] == "T+3"
    assert res_z["margin_eligible"] is False

    # Circuit limit breach (e.g. price 280 > upper limit 271.9)
    res_breach = validate_dse_order(
        symbol="GP",
        side="BUY",
        quantity=10,
        price=280.0,
        prev_close=250.0
    )
    assert res_breach["is_valid"] is False
    assert any("exceeds upper circuit limit" in err for err in res_breach["errors"])


def test_api_dse_rules_endpoints():
    with TestClient(app) as client:
        # Circuit limits endpoint
        circ_res = client.get("/dse/circuit-limits/GP")
        assert circ_res.status_code == 200
        assert "upper_limit" in circ_res.json()
        assert "lower_limit" in circ_res.json()

        # Market status endpoint
        status_res = client.get("/dse/market-status")
        assert status_res.status_code == 200
        assert "session" in status_res.json()

        # Validate order endpoint
        val_res = client.post(
            "/dse/validate-order?symbol=GP&side=BUY&quantity=10&price=250&prev_close=250&category=A"
        )
        assert val_res.status_code == 200
        assert val_res.json()["is_valid"] is True

