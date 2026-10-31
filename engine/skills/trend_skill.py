"""Trend Following Skill."""

from typing import Any, Dict
import pandas as pd
from engine.skills.base_skill import BaseSkill


class TrendFollowingSkill(BaseSkill):
    @property
    def name(self) -> str:
        return "trend_following"

    @property
    def description(self) -> str:
        return "Evaluates EMA 9/21/50 alignment and moving average directional momentum."

    def execute(self, df: pd.DataFrame, context: Dict[str, Any]) -> Dict[str, Any]:
        if df.empty or len(df) < 5:
            return {"skill": self.name, "trend": "Neutral", "score": 0}

        latest = df.iloc[-1]
        close = float(latest["close"])
        ema_9 = float(latest.get("ema_9", close))
        ema_21 = float(latest.get("ema_21", close))
        ema_50 = float(latest.get("ema_50", close))

        bullish = (close > ema_21) and (ema_9 > ema_21) and (close > ema_50)
        bearish = (close < ema_21) and (ema_9 < ema_21) and (close < ema_50)

        if bullish:
            return {"skill": self.name, "trend": "Bullish", "score": 80, "message": "Strong bullish EMA alignment"}
        elif bearish:
            return {"skill": self.name, "trend": "Bearish", "score": -80, "message": "Strong bearish EMA alignment"}
        else:
            return {"skill": self.name, "trend": "Neutral", "score": 0, "message": "Mixed moving average signals"}

