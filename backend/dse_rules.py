"""DSE Market Rules and Trading Policy Validation Engine.

Implements official Dhaka Stock Exchange (DSE) market mechanisms:
- Daily Circuit Breakers / Price Limit Bands
- Minimum Tick Size (0.10 BDT)
- Settlement Cycles by Stock Category (A/B/N = T+2, Z = T+3)
- Margin loan restrictions (Category Z prohibited)
- Trading session hours (10:00 - 14:30 Asia/Dhaka)
"""

from datetime import datetime, time
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo
from backend.calendar import is_trading_day, DHAKA_TZ
from backend.paper_trading import get_latest_price


# DSE Circuit Breaker Percentage Brackets (BSEC/DSE standard)
CIRCUIT_BRACKETS = [
    (200.0, 10.0),    # Up to 200 BDT: 10%
    (500.0, 8.75),    # 201 to 500 BDT: 8.75%
    (1000.0, 7.5),    # 501 to 1000 BDT: 7.5%
    (2000.0, 6.25),   # 1001 to 2000 BDT: 6.25%
    (5000.0, 5.0),    # 2001 to 5000 BDT: 5.0%
    (float("inf"), 3.75)  # Above 5000 BDT: 3.75%
]

DSE_TICK_SIZE = 0.10

# Category Settlement Rules
SETTLEMENT_DAYS = {
    "A": 2,  # T+2
    "B": 2,  # T+2
    "N": 2,  # T+2
    "Z": 3   # T+3 (Strict, non-marginable)
}


def get_circuit_percentage(price: float) -> float:
    """Return applicable DSE daily circuit breaker percentage for given price."""
    for ceiling, pct in CIRCUIT_BRACKETS:
        if price <= ceiling:
            return pct
    return 3.75


def calculate_circuit_limits(prev_close: float) -> Dict[str, float]:
    """Calculate maximum allowed Upper Limit and Lower Limit for the session."""
    if prev_close <= 0:
        raise ValueError("Previous close must be positive")

    pct = get_circuit_percentage(prev_close)
    max_delta = prev_close * (pct / 100.0)

    upper = round(prev_close + max_delta, 1)
    lower = max(DSE_TICK_SIZE, round(prev_close - max_delta, 1))

    return {
        "prev_close": prev_close,
        "circuit_percentage": pct,
        "upper_limit": upper,
        "lower_limit": lower,
        "tick_size": DSE_TICK_SIZE
    }


def is_valid_tick_size(price: float) -> bool:
    """Check if price complies with 0.10 BDT tick size."""
    # Round to 2 decimal places to avoid IEEE 754 precision issues
    p = round(price, 2)
    return round((p * 10) % 1, 4) in (0.0, 1.0)


def get_dse_session_status(now_dt: Optional[datetime] = None) -> Dict[str, Any]:
    """Determine current DSE session status."""
    now = now_dt or datetime.now(DHAKA_TZ)
    current_date = now.date()
    current_time = now.time()

    is_trade_day = is_trading_day(current_date)

    if not is_trade_day:
        return {
            "status": "CLOSED",
            "session": "WEEKEND_OR_HOLIDAY",
            "current_time": now.strftime("%Y-%m-%d %H:%M:%S %Z"),
            "is_trading_day": False
        }

    # Session hours
    pre_open_start = time(9, 45)
    market_open = time(10, 0)
    market_close = time(14, 30)
    post_close = time(14, 40)

    if current_time < pre_open_start:
        session = "PRE_MARKET"
        status = "CLOSED"
    elif pre_open_start <= current_time < market_open:
        session = "PRE_OPEN"
        status = "CALL_AUCTION"
    elif market_open <= current_time <= market_close:
        session = "REGULAR_TRADING"
        status = "OPEN"
    elif market_close < current_time <= post_close:
        session = "POST_CLOSING"
        status = "CLOSING_AUCTION"
    else:
        session = "AFTER_HOURS"
        status = "CLOSED"

    return {
        "status": status,
        "session": session,
        "current_time": now.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "is_trading_day": True,
        "trading_hours": "10:00 - 14:30 Asia/Dhaka"
    }


def validate_dse_order(
    symbol: str,
    side: str,
    quantity: int,
    price: float,
    prev_close: Optional[float] = None,
    category: str = "A",
    check_market_hours: bool = False
) -> Dict[str, Any]:
    """Validate order against all DSE market policies."""
    symbol = symbol.upper().strip()
    side = side.upper().strip()
    category = category.upper().strip()
    errors = []

    if side not in ("BUY", "SELL"):
        errors.append(f"Invalid side '{side}'. Side must be BUY or SELL")

    if category not in SETTLEMENT_DAYS:
        errors.append(f"Invalid stock category '{category}'. Must be one of: {list(SETTLEMENT_DAYS.keys())}")

    if quantity <= 0:
        errors.append("Quantity must be at least 1 share")

    if price <= 0:
        errors.append("Price must be greater than zero")

    # 1. Tick size validation
    if not is_valid_tick_size(price):
        errors.append(f"Price {price:.2f} violates DSE tick size of BDT {DSE_TICK_SIZE}")

    # 2. Circuit limits validation
    base_price = prev_close or get_latest_price(symbol)
    circuit = None
    if base_price and base_price > 0:
        circuit = calculate_circuit_limits(base_price)
        if price > circuit["upper_limit"]:
            errors.append(
                f"Price {price:.2f} exceeds upper circuit limit of BDT {circuit['upper_limit']:.2f} "
                f"(+{circuit['circuit_percentage']}%)"
            )
        elif price < circuit["lower_limit"]:
            errors.append(
                f"Price {price:.2f} breaches lower circuit limit of BDT {circuit['lower_limit']:.2f} "
                f"(-{circuit['circuit_percentage']}%)"
            )

    # 3. Category Settlement validation
    settlement_cycle = SETTLEMENT_DAYS.get(category, 2)
    margin_allowed = (category != "Z")

    # 4. Market Hours validation (optional for paper/backtest, strict for live)
    session_status = get_dse_session_status()
    if check_market_hours and session_status["status"] != "OPEN":
        errors.append(f"DSE Market is currently {session_status['status']} ({session_status['session']})")

    return {
        "symbol": symbol,
        "side": side,
        "quantity": quantity,
        "price": price,
        "category": category,
        "settlement_cycle": f"T+{settlement_cycle}",
        "margin_eligible": margin_allowed,
        "is_valid": len(errors) == 0,
        "errors": errors,
        "circuit_limits": circuit,
        "session_status": session_status
    }

