from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class RiskConfig:
    max_risk_per_trade: float = 0.02
    stop_loss_pct: float = 0.015
    take_profit_pct: float = 0.03


@dataclass(frozen=True)
class PortfolioConfig:
    target_sector_count: int = 5


@dataclass(frozen=True)
class StrategyConfig:
    raw: dict[str, Any]


@dataclass(frozen=True)
class AppConfig:
    risk: RiskConfig
    portfolio: PortfolioConfig
    strategy: StrategyConfig


def load_yaml(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Config at {p} must be a mapping")
    return data


def load_config(path: str | Path) -> AppConfig:
    raw = load_yaml(path)

    risk = raw.get("risk", {}) or {}
    portfolio = raw.get("portfolio", {}) or {}
    strategy = raw.get("strategy", {}) or {}

    return AppConfig(
        risk=RiskConfig(
            max_risk_per_trade=float(risk.get("max_risk_per_trade", 0.02)),
            stop_loss_pct=float(risk.get("stop_loss_pct", 0.015)),
            take_profit_pct=float(risk.get("take_profit_pct", 0.03)),
        ),
        portfolio=PortfolioConfig(target_sector_count=int(portfolio.get("target_sector_count", 5))),
        strategy=StrategyConfig(raw=strategy),
    )
