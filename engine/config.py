"""Engine configuration manager with JSON schema loading."""

import json
from pathlib import Path
from typing import Any, Dict

ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT_DIR / "config" / "settings.json"

DEFAULT_SETTINGS = {
    "app_name": "DSE Market Signal",
    "version": "2.0.0",
    "timezone": "Asia/Dhaka",
    "market": {
        "symbols": ["GP"],
        "historical_months": 6
    },
    "risk": {
        "max_portfolio_drawdown_pct": 10.0,
        "max_concurrent_positions": 5,
        "min_risk_reward_ratio": 1.5
    },
    "skills": {
        "enabled": ["trend_following", "breakout_detection", "mean_reversion"]
    }
}


def load_engine_config(path: Path = CONFIG_PATH) -> Dict[str, Any]:
    """Load settings from JSON file with fallback to defaults."""
    cfg = dict(DEFAULT_SETTINGS)
    if path.exists():
        try:
            stored = json.loads(path.read_text(encoding="utf-8"))
            # Deep update
            for k, v in stored.items():
                if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                    cfg[k].update(v)
                else:
                    cfg[k] = v
        except Exception:
            pass
    return cfg

