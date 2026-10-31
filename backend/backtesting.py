"""Backtesting Engine for DSE Market Signal App.

Simulates algorithmic trading strategies on historical data bar-by-bar
without lookahead bias, tracking positions, stops, profit targets,
drawdown, and comprehensive performance analytics.
"""

from typing import Any, Dict, List, Optional
import pandas as pd
from backend.analysis import get_stock_price_history
from backend.indicators import calculate_all_indicators


def run_backtest(
    symbol: str = "GP",
    initial_capital: float = 100000.0,
    risk_per_trade_pct: float = 2.0,
    max_allocation_pct: float = 25.0,
    stop_loss_atr_mult: float = 1.5,
    take_profit_atr_mult: float = 2.5
) -> Dict[str, Any]:
    """Execute strategy backtest on historical price series."""
    symbol = symbol.upper().strip()
    df = get_stock_price_history(symbol, limit=250)
    if df.empty or len(df) < 30:
        return {
            "symbol": symbol,
            "status": "insufficient_data",
            "message": f"Need at least 30 historical bars for backtesting {symbol}"
        }

    df_ind = calculate_all_indicators(df)

    cash = initial_capital
    position_qty = 0
    entry_price = 0.0
    entry_date = ""
    stop_loss = 0.0
    take_profit = 0.0

    trades = []
    equity_curve = []
    peak_equity = initial_capital
    max_drawdown = 0.0

    # Start loop after initial indicator burn-in (21 periods)
    for i in range(21, len(df_ind)):
        current_bar = df_ind.iloc[i]
        prev_bar = df_ind.iloc[i - 1]

        bar_date = str(current_bar["date"])
        bar_close = float(current_bar["close"])
        bar_high = float(current_bar["high"])
        bar_low = float(current_bar["low"])
        bar_atr = float(current_bar.get("atr_14", bar_close * 0.02))

        # Check existing position exits
        if position_qty > 0:
            exit_trade = False
            exit_price = bar_close
            exit_reason = ""

            # Check stop loss hit
            if bar_low <= stop_loss:
                exit_trade = True
                exit_price = stop_loss
                exit_reason = "STOP_LOSS"
            # Check take profit hit
            elif bar_high >= take_profit:
                exit_trade = True
                exit_price = take_profit
                exit_reason = "TAKE_PROFIT"
            # Check technical reversal (EMA 9 crosses below EMA 21)
            elif float(current_bar.get("ema_9", 0)) < float(current_bar.get("ema_21", 0)):
                exit_trade = True
                exit_price = bar_close
                exit_reason = "TREND_REVERSAL"

            if exit_trade:
                trade_pnl = (exit_price - entry_price) * position_qty
                trade_return_pct = (exit_price - entry_price) / entry_price * 100.0
                cash += exit_price * position_qty

                trades.append({
                    "entry_date": entry_date,
                    "exit_date": bar_date,
                    "side": "BUY",
                    "quantity": position_qty,
                    "entry_price": round(entry_price, 2),
                    "exit_price": round(exit_price, 2),
                    "pnl": round(trade_pnl, 2),
                    "return_pct": round(trade_return_pct, 2),
                    "exit_reason": exit_reason
                })

                position_qty = 0
                entry_price = 0.0

        # Check for new entry if flat
        if position_qty == 0:
            # Bullish Entry Condition:
            # 1. EMA 9 > EMA 21
            # 2. Close > EMA 50
            # 3. RSI between 45 and 65
            # 4. MACD Histogram > 0
            ema_9 = float(current_bar.get("ema_9", 0))
            ema_21 = float(current_bar.get("ema_21", 0))
            ema_50 = float(current_bar.get("ema_50", 0))
            rsi = float(current_bar.get("rsi_14", 50))
            macd_hist = float(current_bar.get("macd_histogram", 0))

            is_entry = (ema_9 > ema_21) and (bar_close > ema_50) and (45 <= rsi <= 68) and (macd_hist > 0)

            if is_entry:
                stop_loss = round(bar_close - (stop_loss_atr_mult * bar_atr), 2)
                take_profit = round(bar_close + (take_profit_atr_mult * bar_atr), 2)
                risk_per_share = max(0.1, bar_close - stop_loss)

                risk_budget = cash * (risk_per_trade_pct / 100.0)
                max_capital_for_pos = cash * (max_allocation_pct / 100.0)

                qty_by_risk = int(risk_budget // risk_per_share)
                qty_by_cap = int(max_capital_for_pos // bar_close)
                shares_to_buy = max(1, min(qty_by_risk, qty_by_cap))

                total_cost = shares_to_buy * bar_close
                if total_cost <= cash:
                    cash -= total_cost
                    position_qty = shares_to_buy
                    entry_price = bar_close
                    entry_date = bar_date

        # Mark-to-market equity
        current_equity = cash + (position_qty * bar_close)
        peak_equity = max(peak_equity, current_equity)
        dd = (peak_equity - current_equity) / peak_equity * 100.0
        max_drawdown = max(max_drawdown, dd)

        equity_curve.append({
            "date": bar_date,
            "equity": round(current_equity, 2),
            "drawdown_pct": round(dd, 2)
        })

    # Close any open trade at final close
    if position_qty > 0:
        final_bar = df_ind.iloc[-1]
        final_close = float(final_bar["close"])
        final_pnl = (final_close - entry_price) * position_qty
        final_return = (final_close - entry_price) / entry_price * 100.0
        cash += final_close * position_qty
        trades.append({
            "entry_date": entry_date,
            "exit_date": str(final_bar["date"]),
            "side": "BUY",
            "quantity": position_qty,
            "entry_price": round(entry_price, 2),
            "exit_price": round(final_close, 2),
            "pnl": round(final_pnl, 2),
            "return_pct": round(final_return, 2),
            "exit_reason": "END_OF_DATA"
        })

    total_trades = len(trades)
    winning_trades = [t for t in trades if t["pnl"] > 0]
    losing_trades = [t for t in trades if t["pnl"] < 0]

    total_pnl = sum(t["pnl"] for t in trades)
    gross_profits = sum(t["pnl"] for t in winning_trades)
    gross_losses = abs(sum(t["pnl"] for t in losing_trades))

    win_rate = (len(winning_trades) / total_trades * 100.0) if total_trades > 0 else 0.0
    profit_factor = (gross_profits / gross_losses) if gross_losses > 0 else (gross_profits if gross_profits > 0 else 1.0)
    final_equity = cash
    total_return_pct = (final_equity - initial_capital) / initial_capital * 100.0

    return {
        "symbol": symbol,
        "initial_capital": initial_capital,
        "final_equity": round(final_equity, 2),
        "total_pnl": round(total_pnl, 2),
        "total_return_pct": round(total_return_pct, 2),
        "max_drawdown_pct": round(max_drawdown, 2),
        "total_trades": total_trades,
        "winning_trades": len(winning_trades),
        "losing_trades": len(losing_trades),
        "win_rate_pct": round(win_rate, 2),
        "profit_factor": round(profit_factor, 2),
        "trades": trades
    }

