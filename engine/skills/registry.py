"""Skill Registry and Dispatcher."""

from typing import Dict, List, Optional
from engine.skills.base_skill import BaseSkill
from engine.skills.trend_skill import TrendFollowingSkill
from engine.skills.breakout_skill import BreakoutDetectionSkill
from engine.skills.mean_reversion_skill import MeanReversionSkill


class SkillRegistry:
    """Registry managing available trading and market analysis skills."""

    def __init__(self):
        self._skills: Dict[str, BaseSkill] = {}
        # Register default skills
        self.register(TrendFollowingSkill())
        self.register(BreakoutDetectionSkill())
        self.register(MeanReversionSkill())

    def register(self, skill: BaseSkill):
        self._skills[skill.name] = skill

    def get(self, name: str) -> Optional[BaseSkill]:
        return self._skills.get(name)

    def list_skills(self) -> List[Dict[str, str]]:
        return [
            {"name": name, "description": skill.description}
            for name, skill in self._skills.items()
        ]


# Global Registry Instance
skills_registry = SkillRegistry()

