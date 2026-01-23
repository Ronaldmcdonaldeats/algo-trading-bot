from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskParams:
    max_risk_per_trade: float  # e.g. 0.02
    stop_loss_pct: float  # e.g. 0.015
    take_profit_pct: float  # e.g. 0.03


def stop_loss_price(entry_price: float, stop_loss_pct: float) -> float:
    return entry_price * (1.0 - stop_loss_pct)


def take_profit_price(entry_price: float, take_profit_pct: float) -> float:
    return entry_price * (1.0 + take_profit_pct)


def position_size_shares(
    *,
    equity: float,
    entry_price: float,
    stop_loss_price_: float,
    max_risk: float,
) -> int:
    """Fixed-fractional sizing.

    Risk per trade = equity * max_risk
    Per-share risk = entry_price - stop_loss
    Shares = floor(risk_per_trade / per_share_risk)
    """
    if equity <= 0:
        raise ValueError("equity must be positive")
    if entry_price <= 0:
        raise ValueError("entry_price must be positive")
    if stop_loss_price_ <= 0 or stop_loss_price_ >= entry_price:
        raise ValueError("stop_loss_price_ must be positive and < entry_price")
    if not (0 < max_risk < 1):
        raise ValueError("max_risk must be between 0 and 1")

    risk_budget = equity * max_risk
    per_share_risk = entry_price - stop_loss_price_
    shares = int(risk_budget // per_share_risk)
    return max(shares, 0)
