"""Mean Reversion & Oversold Bounce Skill."""

from typing import Any, Dict
import pandas as pd
from engine.skills.base_skill import BaseSkill


class MeanReversionSkill(BaseSkill):
    @property
    def name(self) -> str:
        return "mean_reversion"

    @property
    def description(self) -> str:
        return "Identifies extreme RSI exhaustion and Bollinger Band mean reversion setups."

    def execute(self, df: pd.DataFrame, context: Dict[str, Any]) -> Dict[str, Any]:
        if df.empty or len(df) < 5:
            return {"skill": self.name, "reversion_signal": "NONE", "score": 0}

        latest = df.iloc[-1]
        rsi = float(latest.get("rsi_14", 50.0))
        close = float(latest["close"])
        bb_lower = float(latest.get("bb_lower", close))
        bb_upper = float(latest.get("bb_upper", close))

        if rsi < 30 or close < bb_lower:
            return {
                "skill": self.name,
                "reversion_signal": "OVERSOLD_BOUNCE",
                "score": 75,
                "message": f"Oversold condition (RSI {rsi:.1f}, below lower Bollinger)"
            }
        elif rsi > 70 or close > bb_upper:
            return {
                "skill": self.name,
                "reversion_signal": "OVERBOUGHT_PULLBACK",
                "score": -75,
                "message": f"Overbought condition (RSI {rsi:.1f}, above upper Bollinger)"
            }

        return {"skill": self.name, "reversion_signal": "NONE", "score": 0, "message": "Normal valuation zone"}

