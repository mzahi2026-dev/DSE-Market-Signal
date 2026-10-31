"""Telegram Notification Service for DSE Market Signals.

Provides formatted alert dispatches with graceful simulation/fallback
when bot token or chat ID is not configured.
"""

import os
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional
import urllib.request
import urllib.parse

logger = logging.getLogger("dse.telegram")

CONFIG_PATH = Path(__file__).resolve().parent / "notification_config.json"


def load_telegram_config() -> Dict[str, Any]:
    config = {
        "bot_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
        "chat_id": os.getenv("TELEGRAM_CHAT_ID", ""),
        "enabled": False,
        "notify_on_strong_only": False
    }
    if CONFIG_PATH.exists():
        try:
            stored = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            config.update(stored)
        except Exception:
            pass
    # Override from environment variables if present
    if os.getenv("TELEGRAM_BOT_TOKEN"):
        config["bot_token"] = os.getenv("TELEGRAM_BOT_TOKEN")
    if os.getenv("TELEGRAM_CHAT_ID"):
        config["chat_id"] = os.getenv("TELEGRAM_CHAT_ID")
    return config


def format_signal_message(signal_data: Dict[str, Any]) -> str:
    """Format signal data into a readable Telegram message with Markdown/emojis."""
    sym = signal_data.get("symbol", "UNKNOWN")
    sig = signal_data.get("signal", "HOLD")
    price = signal_data.get("close", 0.0)
    conf = signal_data.get("confidence", 50)
    target = signal_data.get("target", 0.0)
    sl = signal_data.get("stop_loss", 0.0)
    rr = signal_data.get("risk_reward_ratio", 1.0)
    reasons = signal_data.get("reasons", [])

    if "BUY" in sig:
        icon = "🟢" if sig == "BUY" else "🚀"
    elif "SELL" in sig:
        icon = "🔴" if sig == "SELL" else "🔻"
    else:
        icon = "⚪"

    lines = [
        f"{icon} *DSE MARKET SIGNAL: {sym}*",
        f"📅 Date: {signal_data.get('date', 'N/A')}",
        f"🎯 Signal: *{sig}* (Confidence: {conf}%)",
        f"💵 Last Price: BDT {price:.2f}",
        f"🎯 Target: BDT {target:.2f}",
        f"🛑 Stop Loss: BDT {sl:.2f}",
        f"⚖️ Risk/Reward: 1:{rr}",
        "",
        "*Confluence Factors:*"
    ]
    for r in reasons[:4]:
        lines.append(f"• {r}")

    lines.append("\n⚠️ _DSE Market Signal automated paper/analysis alert._")
    return "\n".join(lines)


def send_telegram_alert(signal_data: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Send formatted signal alert via Telegram.
    If no bot token / chat ID is set, logs the message and returns simulated status.
    """
    if config is None:
        config = load_telegram_config()

    bot_token = config.get("bot_token", "").strip()
    chat_id = config.get("chat_id", "").strip()
    message = format_signal_message(signal_data)

    if not bot_token or not chat_id:
        logger.info("Telegram not configured. Fallback simulation: %s", message)
        return {
            "status": "simulated",
            "delivered": False,
            "message": "Telegram credentials not configured; alert simulated successfully.",
            "preview": message
        }

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = json.dumps({
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            return {
                "status": "delivered",
                "delivered": True,
                "telegram_response": res_data
            }
    except Exception as exc:
        logger.error("Failed to send Telegram alert: %s", exc)
        return {
            "status": "failed",
            "delivered": False,
            "error": str(exc),
            "preview": message
        }

