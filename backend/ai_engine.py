"""Gemini AI Integration with Graceful Fallback for DSE Market Signal App.

Provides stock commentary, technical second opinion, and market outlook.
When GEMINI_API_KEY is not set or network fails, automatically falls back
to an algorithmic expert system without failing.
"""

import os
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional
from backend.analysis import analyze_stock
from backend.signals import generate_signal
from backend.market_summary import get_market_summary

logger = logging.getLogger("dse.ai")

CONFIG_PATH = Path(__file__).resolve().parent / "ai_config.json"


def get_ai_config() -> Dict[str, Any]:
    config = {
        "api_key": os.getenv("GEMINI_API_KEY", ""),
        "model": "gemini-1.5-flash",
        "temperature": 0.2
    }
    if CONFIG_PATH.exists():
        try:
            stored = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            config.update(stored)
        except Exception:
            pass
    if os.getenv("GEMINI_API_KEY"):
        config["api_key"] = os.getenv("GEMINI_API_KEY")
    return config


def generate_fallback_stock_analysis(symbol: str, analysis: Dict[str, Any], signal: Dict[str, Any]) -> Dict[str, Any]:
    """Expert Rule-Based AI Engine fallback when Gemini API key is not present."""
    price = analysis["price"]
    ind = analysis["indicators"]
    sr = analysis["levels"]
    trend = analysis["trend"]
    sig = signal["signal"]
    conf = signal["confidence"]

    commentary = (
        f"{symbol} is currently trading at BDT {price['close']:.2f} with a {trend.lower()} technical bias. "
        f"The 14-period RSI sits at {ind['rsi_14']:.1f} ({ind['rsi_state']}), while MACD histogram "
        f"shows momentum at {ind['macd']['histogram']:+.2f}. Price is trading relative to key pivot "
        f"at BDT {sr['pivot']:.2f} with first resistance at BDT {sr['resistance_1']:.2f} and support at "
        f"BDT {sr['support_1']:.2f}."
    )

    key_catalysts = [
        f"Trend Alignment: Price holding {'above' if price['close'] > ind['moving_averages']['ema_21'] else 'below'} 21 EMA",
        f"Momentum: RSI indicates {ind['rsi_state']} conditions",
        f"Volume Confirmation: {'High volume participation detected' if ind['volume_surge'] else 'Average trading volume'}"
    ]

    risks = [
        f"Breach of immediate support at BDT {sr['support_1']:.2f} would trigger defensive stops.",
        "Market volatility and overall Dhaka Stock Exchange liquidity fluctuations.",
        "Respect DSE regulatory circuit breaker bands before entering orders."
    ]

    return {
        "symbol": symbol.upper(),
        "mode": "rule_based_fallback",
        "model": "expert-rule-engine-v1",
        "verdict": sig,
        "confidence": conf,
        "summary": commentary,
        "key_catalysts": key_catalysts,
        "risks": risks,
        "action_plan": {
            "entry_range": f"BDT {price['close'] * 0.99:.1f} - {price['close'] * 1.01:.1f}",
            "primary_target": f"BDT {signal['target']:.1f}",
            "stop_loss": f"BDT {signal['stop_loss']:.1f}",
            "risk_reward": f"1:{signal['risk_reward_ratio']}"
        }
    }


def analyze_stock_with_ai(symbol: str) -> Dict[str, Any]:
    """Analyze stock using Gemini AI if configured, otherwise use expert fallback."""
    symbol = symbol.upper().strip()
    analysis = analyze_stock(symbol)
    signal = generate_signal(symbol)

    if analysis.get("status") == "no_data":
        return {
            "symbol": symbol,
            "status": "error",
            "message": f"No market data available for {symbol}"
        }

    config = get_ai_config()
    api_key = config.get("api_key", "").strip()

    if not api_key:
        return generate_fallback_stock_analysis(symbol, analysis, signal)

    # Attempt live Gemini API call
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        prompt = (
            f"Act as a professional Dhaka Stock Exchange financial analyst. Analyze {symbol}.\n"
            f"Price: {analysis['price']['close']}, Trend: {analysis['trend']}, RSI: {analysis['indicators']['rsi_14']}\n"
            f"Signal: {signal['signal']}, Reasons: {signal['reasons']}\n"
            f"Provide concise JSON output with keys: verdict, confidence, summary, key_catalysts, risks."
        )
        response = client.models.generate_content(
            model=config.get("model", "gemini-1.5-flash"),
            contents=prompt
        )
        return {
            "symbol": symbol,
            "mode": "gemini_live",
            "model": config.get("model", "gemini-1.5-flash"),
            "raw_analysis": response.text,
            "signal": signal["signal"]
        }
    except Exception as exc:
        logger.warning("Gemini AI live call failed (%s); reverting to fallback", exc)
        res = generate_fallback_stock_analysis(symbol, analysis, signal)
        res["live_error"] = str(exc)
        return res


def review_signal_with_ai(symbol: str) -> Dict[str, Any]:
    """Generate an AI second opinion on the algorithmic signal."""
    sig = generate_signal(symbol)
    analysis = analyze_stock(symbol)
    ai_result = analyze_stock_with_ai(symbol)

    return {
        "symbol": symbol.upper(),
        "algorithmic_signal": sig["signal"],
        "algorithmic_confidence": sig["confidence"],
        "ai_verdict": ai_result.get("verdict", sig["signal"]),
        "ai_confidence": ai_result.get("confidence", sig["confidence"]),
        "consensus": "ALIGNED" if sig["signal"] == ai_result.get("verdict", sig["signal"]) else "DIVERGENT",
        "ai_summary": ai_result.get("summary", ""),
        "mode": ai_result.get("mode", "fallback")
    }


def get_ai_market_outlook() -> Dict[str, Any]:
    """Generate an AI perspective on general DSE market breadth and conditions."""
    summary = get_market_summary()
    return {
        "status": "ok",
        "market_sentiment": summary.get("sentiment", "Neutral"),
        "advancers": summary.get("advancers", 0),
        "decliners": summary.get("decliners", 0),
        "advance_decline_ratio": summary.get("advance_decline_ratio", 1.0),
        "ai_commentary": (
            f"Dhaka Stock Exchange currently reflects {summary.get('sentiment', 'Neutral')} sentiment "
            f"with {summary.get('advancers', 0)} gainers and {summary.get('decliners', 0)} decliners. "
            f"Active risk management and adherence to circuit bands is recommended."
        )
    }

