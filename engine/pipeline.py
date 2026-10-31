"""Engine Execution Pipeline."""

from typing import Any, Dict, List
from backend.analysis import get_stock_price_history
from backend.indicators import calculate_all_indicators
from backend.signals import generate_signal
from backend.risk_management import evaluate_order_risk
from engine.config import load_engine_config
from engine.skills.registry import skills_registry


def run_stock_pipeline(symbol: str, account_id: str = "default") -> Dict[str, Any]:
    """Execute end-to-end modular engine pipeline for a stock."""
    symbol = symbol.upper().strip()
    config = load_engine_config()

    # 1. Fetch & Indicators
    df = get_stock_price_history(symbol)
    if df.empty:
        return {"symbol": symbol, "status": "no_data"}

    df_ind = calculate_all_indicators(df)

    # 2. Execute Enabled Skills
    enabled_skills = config.get("skills", {}).get("enabled", [])
    skill_results = {}
    total_skill_score = 0

    for skill_name in enabled_skills:
        skill = skills_registry.get(skill_name)
        if skill:
            res = skill.execute(df_ind, {"symbol": symbol})
            skill_results[skill_name] = res
            total_skill_score += res.get("score", 0)

    # 3. Core Signal
    signal = generate_signal(symbol)

    # 4. Risk Assessment
    risk_eval = evaluate_order_risk(
        account_id=account_id,
        symbol=symbol,
        side="BUY" if "BUY" in signal["signal"] else "SELL",
        quantity=10,
        price=signal["close"],
        stop_loss=signal["stop_loss"],
        target=signal["target"]
    )

    return {
        "symbol": symbol,
        "date": signal["date"],
        "price": signal["close"],
        "signal": signal["signal"],
        "confidence": signal["confidence"],
        "pipeline_skills_score": total_skill_score,
        "skill_findings": skill_results,
        "risk_evaluation": risk_eval,
        "target": signal["target"],
        "stop_loss": signal["stop_loss"],
        "status": "success"
    }

