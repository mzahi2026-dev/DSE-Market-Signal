"""Breakout Detection Skill."""

from typing import Any, Dict
import pandas as pd
from engine.skills.base_skill import BaseSkill


class BreakoutDetectionSkill(BaseSkill):
    @property
    def name(self) -> str:
        return "breakout_detection"

    @property
    def description(self) -> str:
        return "Detects resistance breakouts and volume expansion surges."

    def execute(self, df: pd.DataFrame, context: Dict[str, Any]) -> Dict[str, Any]:
        if df.empty or len(df) < 15:
            return {"skill": self.name, "breakout": False, "score": 0}

        latest = df.iloc[-1]
        prior_20 = df.iloc[-21:-1] if len(df) >= 21 else df.iloc[:-1]

        high_20 = float(prior_20["high"].max())
        low_20 = float(prior_20["low"].min())
        close = float(latest["close"])
        vol_surge = bool(latest.get("volume_surge", False))

        if close > high_20 and vol_surge:
            return {
                "skill": self.name,
                "breakout": True,
                "type": "BULLISH_BREAKOUT",
                "score": 90,
                "message": f"Volume-backed breakout above 20-period high ({high_20:.2f})"
            }
        elif close < low_20 and vol_surge:
            return {
                "skill": self.name,
                "breakout": True,
                "type": "BEARISH_BREAKDOWN",
                "score": -90,
                "message": f"Volume-backed breakdown below 20-period low ({low_20:.2f})"
            }

        return {"skill": self.name, "breakout": False, "score": 0, "message": "Trading within 20-period channel"}

