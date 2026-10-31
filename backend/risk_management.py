"""Risk Management Engine for DSE Market Signal App.

Provides Stop Loss calculation, Trailing Stop, Risk/Reward analysis,
portfolio risk limits, drawdown protection, and order risk validation.
"""

from typing import Any, Dict, List, Optional, Tuple
from backend.db import connect
from backend.paper_trading import get_portfolio, get_latest_price


# Default Risk Configuration
DEFAULT_RISK_CONFIG = {
    "max_portfolio_drawdown_pct": 10.0,  # Max 10% drawdown from peak equity
    "max_concurrent_positions": 5,        # Max 5 simultaneous stock positions
    "max_single_stock_allocation_pct": 25.0,
    "min_risk_reward_ratio": 1.5,        # Minimum 1.5:1 RRR for approval
    "default_trailing_stop_pct": 5.0,     # 5% trailing stop
}


def calculate_stop_loss_levels(
    entry_price: float,
    atr: float = 0.0,
    swing_low: Optional[float] = None,
    fixed_pct: float = 5.0
) -> Dict[str, float]:
    """Calculate multiple stop loss alternatives for trade planning."""
    if entry_price <= 0:
        raise ValueError("Entry price must be positive")

    fixed_sl = round(entry_price * (1.0 - (fixed_pct / 100.0)), 2)
    atr_sl = round(entry_price - (1.5 * atr), 2) if atr > 0 else fixed_sl
    structure_sl = round(swing_low * 0.99, 2) if swing_low and swing_low < entry_price else atr_sl

    # Conservative recommended stop is the highest of valid stops below entry
    valid_stops = [s for s in (fixed_sl, atr_sl, structure_sl) if s < entry_price]
    recommended = max(valid_stops) if valid_stops else fixed_sl

    return {
        "recommended_stop_loss": round(recommended, 2),
        "fixed_percent_stop": fixed_sl,
        "atr_volatility_stop": atr_sl,
        "market_structure_stop": structure_sl
    }


def calculate_targets_and_rrr(
    entry_price: float,
    stop_loss: float,
    resistance_level: Optional[float] = None
) -> Dict[str, Any]:
    """Calculate target prices and Risk/Reward ratios."""
    if entry_price <= 0:
        raise ValueError("Entry price must be positive")
    if stop_loss >= entry_price:
        raise ValueError("Stop loss must be lower than entry price for long positions")

    risk = entry_price - stop_loss

    target_1_5r = round(entry_price + (1.5 * risk), 2)
    target_2_0r = round(entry_price + (2.0 * risk), 2)
    target_3_0r = round(entry_price + (3.0 * risk), 2)

    primary_target = target_2_0r
    if resistance_level and resistance_level > entry_price:
        # If technical resistance exists between 1.5R and 2.5R, align with it
        primary_target = round(resistance_level, 2)

    actual_reward = primary_target - entry_price
    rrr = round(actual_reward / risk, 2) if risk > 0 else 0.0

    return {
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "risk_amount": round(risk, 2),
        "primary_target": primary_target,
        "risk_reward_ratio": rrr,
        "targets": {
            "target_1_5r": target_1_5r,
            "target_2_0r": target_2_0r,
            "target_3_0r": target_3_0r
        },
        "is_acceptable_rrr": rrr >= DEFAULT_RISK_CONFIG["min_risk_reward_ratio"]
    }


def update_trailing_stop(
    entry_price: float,
    highest_price: float,
    current_price: float,
    current_stop_loss: float,
    trailing_pct: float = 5.0,
    atr: Optional[float] = None
) -> Dict[str, Any]:
    """Calculate updated trailing stop loss. Trailing stop only moves UP, never down."""
    if current_price > highest_price:
        highest_price = current_price

    if atr and atr > 0:
        calculated_stop = highest_price - (2.0 * atr)
    else:
        calculated_stop = highest_price * (1.0 - (trailing_pct / 100.0))

    new_stop = max(current_stop_loss, calculated_stop)
    new_stop = round(new_stop, 2)

    return {
        "highest_price": round(highest_price, 2),
        "current_price": round(current_price, 2),
        "current_stop_loss": round(current_stop_loss, 2),
        "new_stop_loss": new_stop,
        "stop_updated": new_stop > current_stop_loss,
        "unrealized_gain_pct": round(((current_price - entry_price) / entry_price * 100.0), 2)
    }


def evaluate_order_risk(
    account_id: str,
    symbol: str,
    side: str,
    quantity: int,
    price: float,
    stop_loss: Optional[float] = None,
    target: Optional[float] = None,
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Evaluate whether an order passes all risk limits before execution."""
    cfg = dict(DEFAULT_RISK_CONFIG)
    if config:
        cfg.update(config)

    portfolio = get_portfolio(account_id)
    equity = portfolio["total_equity"]
    initial_cap = portfolio["initial_capital"]
    positions = portfolio["positions"]

    reasons = []
    is_approved = True

    # 1. Max Drawdown Circuit Breaker (Calculated from Peak Equity)
    peak_equity = portfolio.get("peak_equity", initial_cap)
    if peak_equity < initial_cap:
        peak_equity = initial_cap
    drawdown_pct = ((peak_equity - equity) / peak_equity * 100.0) if peak_equity > 0 else 0.0
    if drawdown_pct >= cfg["max_portfolio_drawdown_pct"] and side.upper() == "BUY":
        is_approved = False
        reasons.append(
            f"Drawdown Circuit Breaker active: Portfolio drawdown is {drawdown_pct:.1f}% from peak equity BDT {peak_equity:.2f} "
            f"(Limit: {cfg['max_portfolio_drawdown_pct']}%). New BUY orders suspended."
        )

    # 2. Maximum Concurrent Positions Limit
    existing_syms = {p["symbol"] for p in positions}
    if side.upper() == "BUY" and symbol.upper() not in existing_syms:
        if len(existing_syms) >= cfg["max_concurrent_positions"]:
            is_approved = False
            reasons.append(
                f"Maximum open positions reached ({len(existing_syms)}/{cfg['max_concurrent_positions']})."
            )

    # 3. Single Stock Allocation Concentration
    order_val = quantity * price
    current_pos_val = sum(p["market_value"] for p in positions if p["symbol"] == symbol.upper())
    projected_pos_val = current_pos_val + order_val
    pos_weight_pct = (projected_pos_val / equity * 100.0) if equity > 0 else 0.0

    if side.upper() == "BUY" and pos_weight_pct > cfg["max_single_stock_allocation_pct"]:
        is_approved = False
        reasons.append(
            f"Concentration limit exceeded: Position would be {pos_weight_pct:.1f}% of equity "
            f"(Max: {cfg['max_single_stock_allocation_pct']}%)."
        )

    # 4. Risk / Reward Ratio Check
    rrr = 0.0
    if side.upper() == "BUY" and stop_loss and target and stop_loss < price and target > price:
        rrr_res = calculate_targets_and_rrr(price, stop_loss, target)
        rrr = rrr_res["risk_reward_ratio"]
        if rrr < cfg["min_risk_reward_ratio"]:
            is_approved = False
            reasons.append(
                f"Low Risk/Reward Ratio: {rrr:.2f} is below minimum threshold {cfg['min_risk_reward_ratio']}."
            )

    if not reasons:
        reasons.append("All risk parameters validated successfully.")

    return {
        "account_id": account_id,
        "symbol": symbol.upper(),
        "side": side.upper(),
        "is_approved": is_approved,
        "drawdown_pct": round(drawdown_pct, 2),
        "open_positions_count": len(existing_syms),
        "projected_portfolio_weight_pct": round(pos_weight_pct, 2),
        "risk_reward_ratio": rrr,
        "reasons": reasons
    }

