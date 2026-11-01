import json
import logging
from contextlib import asynccontextmanager
from datetime import date, timedelta
from pathlib import Path
from typing import List, Optional
from zoneinfo import ZoneInfo
from fastapi import FastAPI, HTTPException, Body
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.background import BackgroundScheduler
from backend.db import connect
from backend.collector import collect, collect_daily, collect_intraday, get_configured_symbols
from backend.indicators import calculate_all_indicators
from backend.analysis import analyze_stock, get_stock_price_history, calculate_support_resistance
from backend.market_summary import get_market_summary, get_all_symbols
from backend.signals import generate_signal
from backend.telegram import send_telegram_alert
from backend.paper_trading import (
    get_or_create_account,
    place_order,
    get_portfolio,
    get_trade_history,
    reset_account,
    get_latest_price
)
from backend.position_sizing import (
    calculate_position_size,
    get_position_recommendation_for_symbol
)
from backend.risk_management import (
    calculate_stop_loss_levels,
    calculate_targets_and_rrr,
    update_trailing_stop,
    evaluate_order_risk,
    DEFAULT_RISK_CONFIG
)
from backend.dse_rules import (
    calculate_circuit_limits,
    get_dse_session_status,
    validate_dse_order
)
from backend.ai_engine import (
    get_ai_config,
    analyze_stock_with_ai,
    review_signal_with_ai,
    get_ai_market_outlook
)
from backend.automation import (
    get_automation_monitoring_status,
    load_automation_state,
    set_automation_mode,
    execute_automation_cycle,
    RUNS_LOG
)
from backend.chart_service import get_full_chart_data
from backend.screener import (
    screen_stocks,
    get_watchlist,
    add_to_watchlist,
    remove_from_watchlist,
    scan_full_dse_market_and_rank,
    auto_scan_and_sync_watchlist
)
from backend.backtesting import run_backtest
from engine.config import load_engine_config
from engine.skills.registry import skills_registry
from engine.pipeline import run_stock_pipeline
from scripts.gap_audit import audit
from scripts.recovery import run_recovery
from backend.data_collection import (
    collect_hourly_intraday,
    collect_daily_eod,
    run_gap_filling_catchup,
    get_collection_engine_status
)

logger = logging.getLogger("dse.app")

scheduler = BackgroundScheduler(timezone=ZoneInfo("Asia/Dhaka"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure database schema is ready
    with connect():
        pass

    # Autonomous offline gap filling on startup (catch-up engine)
    try:
        logger.info("⚡ [Startup] Executing autonomous offline gap-filling catch-up...")
        run_gap_filling_catchup(max_batches_per_symbol=2)
    except Exception as exc:
        logger.error("FastAPI startup gap-filling error: %s", exc)

    # Schedule daily EOD collection at 16:30 Asia/Dhaka for all configured symbols
    # Prevent duplicate runs with max_instances=1, coalesce=True, replace_existing=True
    scheduler.add_job(
        collect_daily_eod,
        "cron",
        hour=16,
        minute=30,
        id="daily_dse",
        kwargs={"symbols": get_configured_symbols()},
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600
    )

    # Schedule hourly intraday collection during active DSE market hours (Sun-Thu 10:00 - 14:00 Asia/Dhaka)
    scheduler.add_job(
        collect_hourly_intraday,
        "cron",
        day_of_week="sun,mon,tue,wed,thu",
        hour="10-14",
        minute=0,
        id="hourly_intraday_dse",
        kwargs={"symbols": get_configured_symbols()},
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=1800
    )

    # Check automation state: if MANUAL, pause the daily and intraday scheduler jobs
    auto_state = load_automation_state()
    if auto_state.get("mode") == "MANUAL":
        logger.info("FastAPI startup: Automation mode is MANUAL. Pausing collection jobs.")
        scheduler.pause_job("daily_dse")
        scheduler.pause_job("hourly_intraday_dse")

    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="DSE Market Signal", lifespan=lifespan)


@app.get("/health")
def health():
    daily_job = scheduler.get_job("daily_dse")
    intraday_job = scheduler.get_job("hourly_intraday_dse")
    auto_state = load_automation_state()
    return {
        "status": "ok",
        "app": "DSE Market Signal",
        "automation_mode": auto_state.get("mode", "AUTO"),
        "scheduler_running": scheduler.running,
        "jobs": {
            "daily_dse": {
                "active": (daily_job.next_run_time is not None) if daily_job else False,
                "next_run": str(daily_job.next_run_time) if daily_job else None
            },
            "hourly_intraday_dse": {
                "active": (intraday_job.next_run_time is not None) if intraday_job else False,
                "next_run": str(intraday_job.next_run_time) if intraday_job else None
            }
        },
        "next_run": str(daily_job.next_run_time) if daily_job else None
    }


@app.get("/prices")
def prices(symbol: str = "GP", limit: int = 20):
    with connect() as con:
        rows = con.execute(
            """SELECT date, open, high, low, close, volume
               FROM prices WHERE symbol=?
               ORDER BY date DESC LIMIT ?""",
            (symbol.upper(), limit)
        ).fetchall()
    return {"symbol": symbol.upper(), "rows": rows}


@app.post("/collect")
def manual_collect(symbol: str = "GP", days: int = 7):
    if days < 1 or days > 7:
        raise HTTPException(400, "days must be 1 to 7")
    end = date.today()
    start = end - timedelta(days=days-1)
    try:
        return collect(symbol, str(start), str(end))
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        if "403" in str(exc) or "Forbidden" in str(exc):
            raise HTTPException(403, f"Source access forbidden: {exc}")
        raise HTTPException(502, f"Data provider error: {exc}")


@app.get("/recovery/status")
def recovery_status(symbol: str = "GP"):
    """Audit trading calendar and report missing sessions / pending batches."""
    try:
        gap_report = audit(symbol.upper())
        return {
            "status": "ok",
            "audit": gap_report
        }
    except Exception as exc:
        raise HTTPException(500, f"Recovery audit failed: {exc}")


@app.post("/recovery/run")
def trigger_recovery(symbol: str = "GP", max_batches: int = 1):
    """Controlled manual recovery execution."""
    if max_batches < 1 or max_batches > 5:
        raise HTTPException(400, "max_batches must be between 1 and 5")
    try:
        report = run_recovery(symbol=symbol, execute=True, max_batches=max_batches)
        return {"status": "ok", "report": report}
    except Exception as exc:
        raise HTTPException(500, f"Recovery execution failed: {exc}")


# Phase 3 - Market Analysis & Indicators Endpoints

@app.get("/analysis/{symbol}")
def stock_analysis(symbol: str):
    """Return technical analysis, trend direction, support/resistance, and indicator scores."""
    result = analyze_stock(symbol)
    if result.get("status") == "no_data":
        raise HTTPException(404, result.get("message"))
    return result


@app.get("/indicators/{symbol}")
def stock_indicators(symbol: str, limit: int = 60):
    """Return historical series with all calculated technical indicators."""
    df = get_stock_price_history(symbol, limit=limit)
    if df.empty:
        raise HTTPException(404, f"No price data available for {symbol}")
    df_ind = calculate_all_indicators(df)
    records = df_ind.fillna(0).to_dict(orient="records")
    sr_levels = calculate_support_resistance(df)
    return {
        "symbol": symbol.upper(),
        "count": len(records),
        "data": records,
        "levels": sr_levels
    }


@app.get("/market/summary")
def market_summary():
    """Return market summary, market breadth (advancers/decliners), and top gainers/losers."""
    return get_market_summary()


# Phase 4 - Signal Engine & Notifications Endpoints

@app.get("/signals/{symbol}")
def stock_signal(symbol: str):
    """Generate Buy/Sell/Hold signal for a specific stock."""
    sig = generate_signal(symbol)
    return sig


@app.get("/signals")
def all_signals():
    """Scan and generate signals for all tracked stocks."""
    symbols = get_all_symbols()
    results = [generate_signal(sym) for sym in symbols]
    return {
        "count": len(results),
        "signals": results
    }


@app.post("/signals/notify/{symbol}")
def notify_signal(symbol: str):
    """Evaluate stock signal and send alert via Telegram (with simulation fallback)."""
    sig = generate_signal(symbol)
    res = send_telegram_alert(sig)
    return {
        "signal": sig,
        "notification": res
    }


# Phase 5 - Paper Trading Endpoints

@app.get("/paper/portfolio")
def paper_portfolio(account_id: str = "default"):
    """Retrieve virtual trading portfolio, cash, positions, and unrealized/realized P&L."""
    return get_portfolio(account_id)


@app.post("/paper/order")
def paper_order(
    symbol: str = "GP",
    side: str = "BUY",
    quantity: int = 10,
    price: Optional[float] = None,
    order_type: str = "MARKET",
    account_id: str = "default",
    stop_loss: Optional[float] = None,
    target: Optional[float] = None,
    category: str = "A",
    enforce_dse_rules: bool = True,
    enforce_risk_limits: bool = True,
    check_market_hours: bool = False
):
    """Execute virtual BUY or SELL paper order with DSE market rules and risk management verification."""
    try:
        return place_order(
            account_id=account_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            order_type=order_type,
            stop_loss=stop_loss,
            target=target,
            category=category,
            enforce_dse_rules=enforce_dse_rules,
            enforce_risk_limits=enforce_risk_limits,
            check_market_hours=check_market_hours
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        raise HTTPException(500, f"Order execution failed: {exc}")


@app.get("/paper/trades")
def paper_trades(account_id: str = "default", limit: int = 50):
    """Retrieve virtual trading history."""
    return {
        "account_id": account_id,
        "trades": get_trade_history(account_id, limit=limit)
    }


@app.post("/paper/reset")
def paper_reset(account_id: str = "default", initial_capital: float = 100000.0):
    """Reset virtual account and clear positions."""
    return reset_account(account_id, initial_capital=initial_capital)


# Phase 6 - Position Calculation Endpoints

@app.post("/position/calculate")
def position_calculate(
    total_capital: float = 100000.0,
    entry_price: float = 250.0,
    stop_loss: float = 240.0,
    risk_pct: float = 2.0,
    max_allocation_pct: float = 20.0
):
    """Calculate recommended position quantity and capital allocation."""
    try:
        return calculate_position_size(
            total_capital=total_capital,
            entry_price=entry_price,
            stop_loss=stop_loss,
            risk_pct=risk_pct,
            max_allocation_pct=max_allocation_pct
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@app.get("/position/recommendation/{symbol}")
def position_recommendation(
    symbol: str,
    account_id: str = "default",
    risk_pct: float = 2.0,
    max_allocation_pct: float = 20.0
):
    """Get automated position sizing recommendation based on active account equity."""
    return get_position_recommendation_for_symbol(
        symbol=symbol,
        account_id=account_id,
        risk_pct=risk_pct,
        max_allocation_pct=max_allocation_pct
    )


# Phase 7 - Risk Management Endpoints

@app.post("/risk/evaluate")
def evaluate_risk(
    symbol: str = "GP",
    side: str = "BUY",
    quantity: int = 10,
    price: float = 250.0,
    stop_loss: Optional[float] = None,
    target: Optional[float] = None,
    account_id: str = "default"
):
    """Validate order against risk limits, drawdown protection, and RRR thresholds."""
    return evaluate_order_risk(
        account_id=account_id,
        symbol=symbol,
        side=side,
        quantity=quantity,
        price=price,
        stop_loss=stop_loss,
        target=target
    )


@app.get("/risk/account/{account_id}")
def account_risk_status(account_id: str = "default"):
    """Get account risk overview, drawdown status, and circuit breaker state."""
    portfolio = get_portfolio(account_id)
    initial_cap = portfolio["initial_capital"]
    equity = portfolio["total_equity"]
    peak_equity = portfolio.get("peak_equity", initial_cap)
    if peak_equity < initial_cap:
        peak_equity = initial_cap
    drawdown_pct = ((peak_equity - equity) / peak_equity * 100.0) if peak_equity > 0 else 0.0
    breaker_active = drawdown_pct >= DEFAULT_RISK_CONFIG["max_portfolio_drawdown_pct"]

    return {
        "account_id": account_id,
        "initial_capital": initial_cap,
        "peak_equity": peak_equity,
        "equity": equity,
        "drawdown_pct": round(drawdown_pct, 2),
        "circuit_breaker_active": breaker_active,
        "max_drawdown_limit_pct": DEFAULT_RISK_CONFIG["max_portfolio_drawdown_pct"],
        "open_positions_count": len(portfolio["positions"]),
        "max_positions_limit": DEFAULT_RISK_CONFIG["max_concurrent_positions"]
    }


@app.post("/risk/trailing-stop")
def trailing_stop_calc(
    entry_price: float,
    highest_price: float,
    current_price: float,
    current_stop_loss: float,
    trailing_pct: float = 5.0,
    atr: Optional[float] = None
):
    """Compute updated trailing stop loss."""
    return update_trailing_stop(
        entry_price=entry_price,
        highest_price=highest_price,
        current_price=current_price,
        current_stop_loss=current_stop_loss,
        trailing_pct=trailing_pct,
        atr=atr
    )


# Phase 8 - DSE Market Rules Endpoints

@app.get("/dse/circuit-limits/{symbol}")
def dse_circuit_limits(symbol: str):
    """Get official upper and lower circuit breaker limits for symbol."""
    price = get_latest_price(symbol)
    if price <= 0:
        raise HTTPException(404, f"No price available for {symbol}")
    return calculate_circuit_limits(price)


@app.get("/dse/market-status")
def dse_market_status():
    """Get current DSE session status and trading hours."""
    return get_dse_session_status()


@app.post("/dse/validate-order")
def dse_validate_order(
    symbol: str = "GP",
    side: str = "BUY",
    quantity: int = 10,
    price: float = 250.0,
    prev_close: Optional[float] = None,
    category: str = "A"
):
    """Validate order against all DSE market policies (circuit limits, tick size, settlement)."""
    return validate_dse_order(
        symbol=symbol,
        side=side,
        quantity=quantity,
        price=price,
        prev_close=prev_close,
        category=category
    )


# Phase 10 - Gemini AI Endpoints

@app.get("/ai/status")
def ai_status():
    """Get Gemini AI configuration status and active mode."""
    cfg = get_ai_config()
    has_key = bool(cfg.get("api_key"))
    return {
        "status": "ok",
        "has_api_key": has_key,
        "active_mode": "gemini_live" if has_key else "rule_based_fallback",
        "model": cfg.get("model", "gemini-1.5-flash")
    }


@app.get("/ai/analyze/{symbol}")
def ai_stock_analysis(symbol: str):
    """Get AI analysis and technical breakdown for stock."""
    return analyze_stock_with_ai(symbol)


@app.get("/ai/review-signal/{symbol}")
def ai_signal_review(symbol: str):
    """Get AI second opinion on algorithmic signal."""
    return review_signal_with_ai(symbol)


@app.get("/ai/market-outlook")
def ai_market_outlook():
    """Get AI overview of general DSE market conditions."""
    return get_ai_market_outlook()


# Phase 11 - Modular Engine Architecture Endpoints

@app.get("/engine/config")
def engine_configuration():
    """Get current engine JSON configuration."""
    return load_engine_config()


@app.get("/engine/skills")
def engine_skills_list():
    """List all registered modular analysis skills."""
    return {
        "skills": skills_registry.list_skills()
    }


@app.get("/engine/pipeline/{symbol}")
def engine_pipeline_run(symbol: str, account_id: str = "default"):
    """Execute end-to-end engine analysis pipeline for stock."""
    res = run_stock_pipeline(symbol=symbol, account_id=account_id)
    if res.get("status") == "no_data":
        raise HTTPException(404, f"No price data available for {symbol}")
    return res


# Phase 12 - Automation Endpoints

@app.get("/automation/status")
def automation_status():
    """Get automation mode, last execution report, and health monitoring metrics."""
    return get_automation_monitoring_status()


@app.post("/automation/mode")
def set_mode(mode: str = "AUTO"):
    """Set automation mode to AUTO or MANUAL and synchronize scheduler."""
    try:
        updated = set_automation_mode(mode)
        try:
            for job_id in ("daily_dse", "hourly_intraday_dse"):
                job = scheduler.get_job(job_id)
                if job:
                    if updated["mode"] == "MANUAL":
                        scheduler.pause_job(job_id)
                        logger.info("Scheduler %s paused due to MANUAL mode", job_id)
                    else:
                        scheduler.resume_job(job_id)
                        logger.info("Scheduler %s resumed due to AUTO mode", job_id)
        except Exception as sched_err:
            logger.warning("Could not sync scheduler with mode: %s", sched_err)
        return updated
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@app.post("/collector/intraday")
def trigger_intraday_collection(symbols: Optional[List[str]] = None):
    """Trigger real-time intraday price collection for configured stocks."""
    return collect_intraday(symbols=symbols)


@app.post("/automation/trigger")
def trigger_automation_cycle(symbol: str = "GP"):
    """Trigger full automation cycle manually."""
    return execute_automation_cycle(symbols=[symbol])


@app.get("/automation/logs")
def automation_logs(limit: int = 10):
    """Get recent automation run logs."""
    if not RUNS_LOG.exists():
        return {"runs": []}
    lines = RUNS_LOG.read_text(encoding="utf-8").splitlines()[-limit:]
    runs = []
    for l in lines:
        try:
            runs.append(json.loads(l))
        except Exception:
            pass
    return {"runs": runs}


# Phase 13 - Technical Charts Endpoints

@app.get("/charts/full/{symbol}")
def chart_full(symbol: str, limit: int = 100):
    """Get multi-panel candlestick, volume, moving average, RSI, and MACD chart payload."""
    data = get_full_chart_data(symbol=symbol, limit=limit)
    if data.get("status") == "no_data":
        raise HTTPException(404, f"No price data found for {symbol}")
    return data


@app.get("/charts/candlestick/{symbol}")
def chart_candlesticks(symbol: str, limit: int = 100):
    """Get candlestick bars and overlay moving averages."""
    data = get_full_chart_data(symbol=symbol, limit=limit)
    return {
        "symbol": symbol.upper(),
        "candlesticks": data.get("candlesticks", []),
        "volume": data.get("volume", []),
        "overlays": data.get("overlays", {})
    }


@app.get("/charts/rsi/{symbol}")
def chart_rsi(symbol: str, limit: int = 100):
    """Get RSI indicator series with 70/30 reference lines."""
    data = get_full_chart_data(symbol=symbol, limit=limit)
    return {
        "symbol": symbol.upper(),
        "rsi": data.get("indicators", {}).get("rsi", []),
        "references": {"overbought": 70, "oversold": 30, "midline": 50}
    }


@app.get("/charts/macd/{symbol}")
def chart_macd(symbol: str, limit: int = 100):
    """Get MACD line, signal line, and color-coded histogram series."""
    data = get_full_chart_data(symbol=symbol, limit=limit)
    return {
        "symbol": symbol.upper(),
        "macd": data.get("indicators", {}).get("macd", [])
    }


# Phase 14 - Stock Screener & Watchlist Endpoints

@app.get("/screener/scan")
def screener_scan(
    signal_filter: str = "ALL",
    trend_filter: str = "ALL",
    rsi_filter: str = "ALL",
    volume_surge_only: bool = False,
    min_confidence: int = 50
):
    """Filter all stocks by technical and signal criteria."""
    return {
        "matches": screen_stocks(
            signal_filter=signal_filter,
            trend_filter=trend_filter,
            rsi_filter=rsi_filter,
            volume_surge_only=volume_surge_only,
            min_confidence=min_confidence
        )
    }


@app.get("/watchlist")
def watchlist_get():
    """Retrieve user watchlist with live technical indicators and AI consensus."""
    return {
        "watchlist": get_watchlist()
    }


@app.post("/watchlist/add")
def watchlist_add(symbol: str, note: str = ""):
    """Add stock to user watchlist."""
    return add_to_watchlist(symbol=symbol, note=note)


@app.delete("/watchlist/{symbol}")
def watchlist_remove(symbol: str):
    """Remove stock from user watchlist."""
    return remove_from_watchlist(symbol=symbol)


@app.get("/screener/live-market")
def screener_live_market(top_n: int = 15):
    """Scan all 390+ live traded DSE stocks and rank by volume, turnover, and momentum."""
    return {
        "status": "success",
        "stocks": scan_full_dse_market_and_rank(top_n=top_n)
    }


@app.post("/screener/auto-sync-watchlist")
def screener_auto_sync(top_n: int = 5, backfill_months: int = 6):
    """Auto-scan entire DSE market, pick the best momentum breakout stocks,
    backfill historical data, generate signals, and add directly to watchlist."""
    return auto_scan_and_sync_watchlist(top_n=top_n, backfill_months=backfill_months)



# Phase 15 - Backtesting Endpoints

@app.post("/backtest/run")
def backtest_run(
    symbol: str = "GP",
    initial_capital: float = 100000.0,
    risk_per_trade_pct: float = 2.0,
    max_allocation_pct: float = 25.0
):
    """Execute strategy backtest on historical price series."""
    res = run_backtest(
        symbol=symbol,
        initial_capital=initial_capital,
        risk_per_trade_pct=risk_per_trade_pct,
        max_allocation_pct=max_allocation_pct
    )
    if res.get("status") == "insufficient_data":
        raise HTTPException(400, res.get("message"))
    return res


# Autonomous Data Collection Engine Endpoints
@app.get("/collection/status")
def collection_status():
    """Return comprehensive diagnostics of the data collection & catch-up engine."""
    return get_collection_engine_status()


@app.post("/collection/run-gap-fill")
def collection_trigger_gap_fill(symbols: Optional[List[str]] = None):
    """Manually trigger offline gap-filling catch-up across symbols."""
    return run_gap_filling_catchup(symbols=symbols)


@app.post("/collection/run-hourly")
def collection_trigger_hourly(symbols: Optional[List[str]] = None):
    """Manually trigger hourly intraday collection."""
    return collect_hourly_intraday(symbols=symbols)


@app.post("/collection/run-eod")
def collection_trigger_eod(symbols: Optional[List[str]] = None):
    """Manually trigger daily EOD collection."""
    return collect_daily_eod(symbols=symbols)


# Phase 9 - Frontend Static Mount
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
