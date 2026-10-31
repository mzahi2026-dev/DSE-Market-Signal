"""Paper Trading engine for DSE Market Signal App.

Provides virtual orders, position management, trade execution,
portfolio mark-to-market, and realized/unrealized P&L tracking.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo
from backend.db import connect

DHAKA_TZ = ZoneInfo("Asia/Dhaka")


def init_paper_tables():
    """Ensure paper trading database tables exist."""
    with connect() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS virtual_accounts (
                account_id TEXT PRIMARY KEY,
                cash_balance REAL NOT NULL,
                initial_capital REAL NOT NULL,
                peak_equity REAL DEFAULT 0.0,
                realized_pnl REAL DEFAULT 0.0,
                created_at TEXT NOT NULL
            )
        """)
        # Ensure peak_equity column exists in existing tables
        cols = [c[1] for c in con.execute("PRAGMA table_info(virtual_accounts)").fetchall()]
        if "peak_equity" not in cols:
            con.execute("ALTER TABLE virtual_accounts ADD COLUMN peak_equity REAL DEFAULT 0.0")

        con.execute("""
            CREATE TABLE IF NOT EXISTS virtual_positions (
                account_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                avg_entry_price REAL NOT NULL,
                PRIMARY KEY(account_id, symbol)
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS virtual_orders (
                order_id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price REAL NOT NULL,
                order_type TEXT NOT NULL,
                status TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS virtual_trades (
                trade_id TEXT PRIMARY KEY,
                order_id TEXT NOT NULL,
                account_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price REAL NOT NULL,
                realized_pnl REAL DEFAULT 0.0,
                timestamp TEXT NOT NULL
            )
        """)
        con.commit()


def get_or_create_account(account_id: str = "default", initial_capital: float = 100000.0) -> Dict[str, Any]:
    """Retrieve or initialize paper trading account."""
    init_paper_tables()
    with connect() as con:
        row = con.execute(
            "SELECT account_id, cash_balance, initial_capital, realized_pnl, created_at, peak_equity FROM virtual_accounts WHERE account_id=?",
            (account_id,)
        ).fetchone()

        if not row:
            now = datetime.now(DHAKA_TZ).isoformat()
            con.execute(
                "INSERT INTO virtual_accounts (account_id, cash_balance, initial_capital, peak_equity, realized_pnl, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (account_id, initial_capital, initial_capital, initial_capital, 0.0, now)
            )
            con.commit()
            return {
                "account_id": account_id,
                "cash_balance": initial_capital,
                "initial_capital": initial_capital,
                "peak_equity": initial_capital,
                "realized_pnl": 0.0,
                "created_at": now
            }

        peak = float(row[5]) if len(row) > 5 and row[5] is not None and float(row[5]) > 0 else float(row[2])
        return {
            "account_id": row[0],
            "cash_balance": float(row[1]),
            "initial_capital": float(row[2]),
            "realized_pnl": float(row[3]),
            "created_at": row[4],
            "peak_equity": peak
        }


def get_latest_price(symbol: str) -> float:
    """Fetch latest close price for symbol from prices table."""
    with connect() as con:
        row = con.execute(
            "SELECT close FROM prices WHERE symbol=? ORDER BY date DESC LIMIT 1",
            (symbol.upper(),)
        ).fetchone()
        return float(row[0]) if row else 0.0


def place_order(
    account_id: str = "default",
    symbol: str = "GP",
    side: str = "BUY",
    quantity: int = 10,
    price: Optional[float] = None,
    order_type: str = "MARKET",
    stop_loss: Optional[float] = None,
    target: Optional[float] = None,
    category: str = "A",
    enforce_dse_rules: bool = True,
    enforce_risk_limits: bool = True,
    check_market_hours: bool = False
) -> Dict[str, Any]:
    """Execute a paper trading order with DSE market rules and risk management verification."""
    init_paper_tables()
    symbol = symbol.upper().strip()
    side = side.upper().strip()
    order_type = order_type.upper().strip()
    category = category.upper().strip()

    if quantity <= 0:
        raise ValueError("Quantity must be greater than zero")
    if side not in ("BUY", "SELL"):
        raise ValueError("Side must be BUY or SELL")

    market_price = get_latest_price(symbol)
    if market_price <= 0 and price is None:
        raise ValueError(f"No market price found for {symbol}; price must be provided")

    exec_price = float(price) if price and price > 0 else market_price

    # 1. Enforce DSE Market Rules
    if enforce_dse_rules:
        from backend.dse_rules import validate_dse_order
        dse_res = validate_dse_order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=exec_price,
            prev_close=market_price if market_price > 0 else None,
            category=category,
            check_market_hours=check_market_hours
        )
        if not dse_res["is_valid"]:
            raise ValueError(f"DSE Rule Violation: {'; '.join(dse_res['errors'])}")

    # 2. Enforce Risk Management Limits
    if enforce_risk_limits:
        from backend.risk_management import evaluate_order_risk
        risk_res = evaluate_order_risk(
            account_id=account_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=exec_price,
            stop_loss=stop_loss,
            target=target
        )
        if not risk_res["is_approved"]:
            raise ValueError(f"Risk Management Violation: {'; '.join(risk_res['reasons'])}")

    total_cost = exec_price * quantity
    now = datetime.now(DHAKA_TZ).isoformat()
    order_id = f"ord_{uuid.uuid4().hex[:10]}"
    trade_id = f"trd_{uuid.uuid4().hex[:10]}"

    # 3. Check LIMIT order price matching
    is_pending = False
    if order_type == "LIMIT" and market_price > 0:
        if side == "BUY" and exec_price < market_price:
            is_pending = True
        elif side == "SELL" and exec_price > market_price:
            is_pending = True

    if is_pending:
        with connect() as con:
            con.execute(
                """INSERT INTO virtual_orders
                   (order_id, account_id, symbol, side, quantity, price, order_type, status, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (order_id, account_id, symbol, side, quantity, exec_price, order_type, "PENDING", now)
            )
            con.commit()
        return {
            "order_id": order_id,
            "trade_id": None,
            "account_id": account_id,
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": exec_price,
            "total_value": round(total_cost, 2),
            "realized_pnl": 0.0,
            "status": "PENDING",
            "message": f"Limit order placed. Waiting for market price to reach {exec_price:.2f} (current: {market_price:.2f})",
            "timestamp": now
        }

    with connect() as con:
        acc = con.execute(
            "SELECT cash_balance, realized_pnl FROM virtual_accounts WHERE account_id=?",
            (account_id,)
        ).fetchone()
        if not acc:
            get_or_create_account(account_id)
            acc = con.execute(
                "SELECT cash_balance, realized_pnl FROM virtual_accounts WHERE account_id=?",
                (account_id,)
            ).fetchone()

        cash, realized_pnl = float(acc[0]), float(acc[1])

        if side == "BUY":
            if cash < total_cost:
                raise ValueError(f"Insufficient cash balance (Required: BDT {total_cost:.2f}, Available: BDT {cash:.2f})")

            new_cash = cash - total_cost

            # Update or create position
            pos = con.execute(
                "SELECT quantity, avg_entry_price FROM virtual_positions WHERE account_id=? AND symbol=?",
                (account_id, symbol)
            ).fetchone()

            if pos:
                old_qty, old_avg = int(pos[0]), float(pos[1])
                new_qty = old_qty + quantity
                new_avg = ((old_qty * old_avg) + (quantity * exec_price)) / new_qty
                con.execute(
                    "UPDATE virtual_positions SET quantity=?, avg_entry_price=? WHERE account_id=? AND symbol=?",
                    (new_qty, new_avg, account_id, symbol)
                )
            else:
                con.execute(
                    "INSERT INTO virtual_positions (account_id, symbol, quantity, avg_entry_price) VALUES (?, ?, ?, ?)",
                    (account_id, symbol, quantity, exec_price)
                )

            trade_realized = 0.0

        else:  # SELL
            pos = con.execute(
                "SELECT quantity, avg_entry_price FROM virtual_positions WHERE account_id=? AND symbol=?",
                (account_id, symbol)
            ).fetchone()

            if not pos or int(pos[0]) < quantity:
                avail_qty = int(pos[0]) if pos else 0
                raise ValueError(f"Insufficient shares to sell (Requested: {quantity}, Available: {avail_qty})")

            old_qty, avg_entry = int(pos[0]), float(pos[1])
            trade_realized = (exec_price - avg_entry) * quantity
            realized_pnl += trade_realized
            new_cash = cash + total_cost

            rem_qty = old_qty - quantity
            if rem_qty > 0:
                con.execute(
                    "UPDATE virtual_positions SET quantity=? WHERE account_id=? AND symbol=?",
                    (rem_qty, account_id, symbol)
                )
            else:
                con.execute(
                    "DELETE FROM virtual_positions WHERE account_id=? AND symbol=?",
                    (account_id, symbol)
                )

        # Update Account Cash & Realized PnL
        con.execute(
            "UPDATE virtual_accounts SET cash_balance=?, realized_pnl=? WHERE account_id=?",
            (new_cash, realized_pnl, account_id)
        )

        # Insert Order and Trade
        con.execute(
            """INSERT INTO virtual_orders
               (order_id, account_id, symbol, side, quantity, price, order_type, status, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (order_id, account_id, symbol, side, quantity, exec_price, order_type, "FILLED", now)
        )
        con.execute(
            """INSERT INTO virtual_trades
               (trade_id, order_id, account_id, symbol, side, quantity, price, realized_pnl, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (trade_id, order_id, account_id, symbol, side, quantity, exec_price, trade_realized, now)
        )
        con.commit()

    return {
        "order_id": order_id,
        "trade_id": trade_id,
        "account_id": account_id,
        "symbol": symbol,
        "side": side,
        "quantity": quantity,
        "price": exec_price,
        "total_value": round(total_cost, 2),
        "realized_pnl": round(trade_realized, 2),
        "status": "FILLED",
        "timestamp": now
    }


def get_portfolio(account_id: str = "default") -> Dict[str, Any]:
    """Calculate complete mark-to-market portfolio snapshot and P&L."""
    acc = get_or_create_account(account_id)
    cash = acc["cash_balance"]
    initial_cap = acc["initial_capital"]
    realized_pnl = acc["realized_pnl"]

    with connect() as con:
        pos_rows = con.execute(
            "SELECT symbol, quantity, avg_entry_price FROM virtual_positions WHERE account_id=?",
            (account_id,)
        ).fetchall()

    positions = []
    total_market_value = 0.0
    total_unrealized_pnl = 0.0

    for r in pos_rows:
        symbol = r[0]
        qty = int(r[1])
        avg_entry = float(r[2])
        cur_price = get_latest_price(symbol) or avg_entry

        market_val = cur_price * qty
        cost_basis = avg_entry * qty
        unrealized = market_val - cost_basis
        unrealized_pct = (unrealized / cost_basis * 100) if cost_basis > 0 else 0.0

        total_market_value += market_val
        total_unrealized_pnl += unrealized

        positions.append({
            "symbol": symbol,
            "quantity": qty,
            "avg_entry_price": round(avg_entry, 2),
            "current_price": round(cur_price, 2),
            "market_value": round(market_val, 2),
            "unrealized_pnl": round(unrealized, 2),
            "unrealized_pnl_pct": round(unrealized_pct, 2)
        })

    total_equity = cash + total_market_value
    current_peak = float(acc.get("peak_equity", initial_cap) or initial_cap)
    peak_equity = max(current_peak, initial_cap, total_equity)

    if peak_equity > current_peak:
        with connect() as con:
            con.execute(
                "UPDATE virtual_accounts SET peak_equity=? WHERE account_id=?",
                (peak_equity, account_id)
            )
            con.commit()

    total_pnl = realized_pnl + total_unrealized_pnl
    total_return_pct = ((total_equity - initial_cap) / initial_cap * 100) if initial_cap > 0 else 0.0

    return {
        "account_id": account_id,
        "initial_capital": round(initial_cap, 2),
        "peak_equity": round(peak_equity, 2),
        "cash_balance": round(cash, 2),
        "market_value": round(total_market_value, 2),
        "total_equity": round(total_equity, 2),
        "realized_pnl": round(realized_pnl, 2),
        "unrealized_pnl": round(total_unrealized_pnl, 2),
        "total_pnl": round(total_pnl, 2),
        "total_return_pct": round(total_return_pct, 2),
        "positions": positions
    }


def get_trade_history(account_id: str = "default", limit: int = 50) -> List[Dict[str, Any]]:
    """Fetch chronological trade execution history."""
    init_paper_tables()
    with connect() as con:
        rows = con.execute(
            """SELECT trade_id, order_id, symbol, side, quantity, price, realized_pnl, timestamp
               FROM virtual_trades
               WHERE account_id=?
               ORDER BY timestamp DESC
               LIMIT ?""",
            (account_id, limit)
        ).fetchall()

    return [
        {
            "trade_id": r[0],
            "order_id": r[1],
            "symbol": r[2],
            "side": r[3],
            "quantity": r[4],
            "price": r[5],
            "realized_pnl": r[6],
            "timestamp": r[7]
        }
        for r in rows
    ]


def reset_account(account_id: str = "default", initial_capital: float = 100000.0) -> Dict[str, Any]:
    """Reset virtual account and clear its positions and trades."""
    init_paper_tables()
    now = datetime.now(DHAKA_TZ).isoformat()
    with connect() as con:
        con.execute("DELETE FROM virtual_positions WHERE account_id=?", (account_id,))
        con.execute("DELETE FROM virtual_orders WHERE account_id=?", (account_id,))
        con.execute("DELETE FROM virtual_trades WHERE account_id=?", (account_id,))
        con.execute(
            """INSERT OR REPLACE INTO virtual_accounts
               (account_id, cash_balance, initial_capital, peak_equity, realized_pnl, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (account_id, initial_capital, initial_capital, initial_capital, 0.0, now)
        )
        con.commit()

    return {
        "status": "reset",
        "account_id": account_id,
        "cash_balance": initial_capital,
        "initial_capital": initial_capital,
        "peak_equity": initial_capital
    }

