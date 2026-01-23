from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Protocol

import pandas as pd


@dataclass(frozen=True)
class StrategyOutput:
    signal: int  # 1 = long, 0 = flat
    confidence: float
    explanation: Dict[str, Any]


class Strategy(Protocol):
    name: str

    def evaluate(self, df: pd.DataFrame) -> StrategyOutput:
        ...


@dataclass(frozen=True)
class StrategyDecision:
    """Explainable decision used by the engine and persisted for auditability."""

    signal: int
    confidence: float
    votes: Dict[str, int]
    weights: Dict[str, float]
    explanations: Dict[str, Dict[str, Any]]
