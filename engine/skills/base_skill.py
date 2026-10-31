from abc import ABC, abstractmethod
from typing import Any, Dict
import pandas as pd


class BaseSkill(ABC):
    """Abstract base class for all market analysis skills."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for the skill."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of skill logic."""
        pass

    @abstractmethod
    def execute(self, df: pd.DataFrame, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute skill on time series DataFrame and return analysis findings."""
        pass

