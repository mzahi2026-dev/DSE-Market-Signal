"""Position Sizing, Capital Allocation, and Quantity Calculation for DSE."""

import math
from typing import Any, Dict, Optional
from backend.paper_trading import get_portfolio
from backend.signals import generate_signal


def calculate_position_size(
    total_capital: float,
    entry_price: float,
    stop_loss: float,
    risk_pct: float = 2.0,            # Max risk of capital per trade (e.g. 2.0%)
    max_allocation_pct: float = 20.0,  # Max portfolio % in a single stock (e.g. 20.0%)
    min_cash_buffer_pct: float = 10.0  # Cash buffer reserve (e.g. 10.0%)
) -> Dict[str, Any]:
    """Calculate recommended position quantity and capital allocation based on risk management rules.
    
    Rules:
    1. Capital Allocation Cap: Never allocate more than `max_allocation_pct` of capital to one stock.
    2. Risk-per-trade Cap: Dollar risk (loss at stop-loss) must not exceed `risk_pct` of total capital.
    3. Cash Reserve: Total deployment must leave `min_cash_buffer_pct` reserve.
    """
    if total_capital <= 0:
        raise ValueError("Total capital must be greater than zero")
    if entry_price <= 0:
        raise ValueError("Entry price must be greater than zero")
    if stop_loss <= 0:
        raise ValueError("Stop loss must be greater than zero")
    if risk_pct <= 0 or risk_pct > 100:
        raise ValueError("Risk percentage must be between 0 and 100")
    if max_allocation_pct <= 0 or max_allocation_pct > 100:
        raise ValueError("Max allocation percentage must be between 0 and 100")

    risk_per_share = abs(entry_price - stop_loss)
    if risk_per_share == 0:
        raise ValueError("Entry price and stop loss cannot be identical")

    # 1. Maximum allowable loss in BDT
    max_risk_amount = total_capital * (risk_pct / 100.0)

    # 2. Maximum capital allowable for this single position
    max_position_capital = total_capital * (max_allocation_pct / 100.0)

    # 3. Available deployment capital considering cash reserve
    usable_capital = total_capital * ((100.0 - min_cash_buffer_pct) / 100.0)
    max_position_capital = min(max_position_capital, usable_capital)

    # Share count from risk constraint
    shares_by_risk = math.floor(max_risk_amount / risk_per_share)

    # Share count from capital allocation constraint
    shares_by_capital = math.floor(max_position_capital / entry_price)

    # Final recommended quantity is the most conservative of the two
    recommended_shares = max(0, min(shares_by_risk, shares_by_capital))

    actual_investment = recommended_shares * entry_price
    portfolio_weight = (actual_investment / total_capital * 100.0) if total_capital > 0 else 0.0
    actual_risk_amount = recommended_shares * risk_per_share
    actual_risk_pct = (actual_risk_amount / total_capital * 100.0) if total_capital > 0 else 0.0

    limiting_factor = "risk_per_trade" if shares_by_risk <= shares_by_capital else "max_capital_allocation"
    if recommended_shares == 0:
        limiting_factor = "capital_too_small_for_unit_risk"

    return {
        "recommended_quantity": int(recommended_shares),
        "entry_price": round(entry_price, 2),
        "stop_loss": round(stop_loss, 2),
        "risk_per_share": round(risk_per_share, 2),
        "investment_required": round(actual_investment, 2),
        "portfolio_weight_pct": round(portfolio_weight, 2),
        "potential_loss": round(actual_risk_amount, 2),
        "actual_risk_pct": round(actual_risk_pct, 2),
        "limiting_factor": limiting_factor,
        "limits": {
            "max_risk_budget": round(max_risk_amount, 2),
            "max_position_capital": round(max_position_capital, 2),
            "shares_by_risk": int(shares_by_risk),
            "shares_by_capital": int(shares_by_capital)
        }
    }


def get_position_recommendation_for_symbol(
    symbol: str,
    account_id: str = "default",
    risk_pct: float = 2.0,
    max_allocation_pct: float = 20.0
) -> Dict[str, Any]:
    """Combine live stock signal, ATR stop loss, and paper trading portfolio equity
    to generate an automatic position size recommendation."""
    symbol = symbol.upper().strip()
    portfolio = get_portfolio(account_id)
    total_capital = portfolio["total_equity"]
    if total_capital <= 0:
        total_capital = portfolio["cash_balance"]

    sig = generate_signal(symbol)
    entry_price = sig.get("close", 0.0)
    stop_loss = sig.get("stop_loss", entry_price * 0.95)

    if entry_price <= 0:
        return {
            "symbol": symbol,
            "status": "error",
            "message": f"Unable to fetch valid market price for {symbol}"
        }

    sizing = calculate_position_size(
        total_capital=total_capital,
        entry_price=entry_price,
        stop_loss=stop_loss,
        risk_pct=risk_pct,
        max_allocation_pct=max_allocation_pct
    )

    return {
        "symbol": symbol,
        "signal": sig.get("signal", "HOLD"),
        "confidence": sig.get("confidence", 50),
        "account_id": account_id,
        "account_equity": round(total_capital, 2),
        "available_cash": round(portfolio["cash_balance"], 2),
        "sizing": sizing
    }

