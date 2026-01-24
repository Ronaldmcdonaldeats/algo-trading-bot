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

    cfg = AppConfig(
        risk=RiskConfig(
            max_risk_per_trade=float(risk.get("max_risk_per_trade", 0.02)),
            stop_loss_pct=float(risk.get("stop_loss_pct", 0.015)),
            take_profit_pct=float(risk.get("take_profit_pct", 0.03)),
        ),
        portfolio=PortfolioConfig(target_sector_count=int(portfolio.get("target_sector_count", 5))),
        strategy=StrategyConfig(raw=strategy),
    )
    
    # Validate config on load
    _validate_config(cfg)
    return cfg


def _validate_config(cfg: AppConfig) -> None:
    """Validate configuration values to catch errors early."""
    errors = []
    
    # Risk validation
    if cfg.risk.max_risk_per_trade <= 0 or cfg.risk.max_risk_per_trade > 1.0:
        errors.append(f"risk.max_risk_per_trade must be 0 < x <= 1.0, got {cfg.risk.max_risk_per_trade}")
    
    if cfg.risk.stop_loss_pct <= 0 or cfg.risk.stop_loss_pct > 0.5:
        errors.append(f"risk.stop_loss_pct must be 0 < x <= 0.5 (50%), got {cfg.risk.stop_loss_pct}")
    
    if cfg.risk.take_profit_pct <= 0 or cfg.risk.take_profit_pct > 1.0:
        errors.append(f"risk.take_profit_pct must be 0 < x <= 1.0 (100%), got {cfg.risk.take_profit_pct}")
    
    if cfg.risk.take_profit_pct <= cfg.risk.stop_loss_pct:
        errors.append(f"risk.take_profit_pct ({cfg.risk.take_profit_pct}) must be > stop_loss_pct ({cfg.risk.stop_loss_pct})")
    
    # Portfolio validation
    if cfg.portfolio.target_sector_count < 1:
        errors.append(f"portfolio.target_sector_count must be >= 1, got {cfg.portfolio.target_sector_count}")
    
    if errors:
        error_msg = "[CONFIG ERROR] Configuration validation failed:\n" + "\n".join(f"  • {e}" for e in errors)
        raise ValueError(error_msg)
