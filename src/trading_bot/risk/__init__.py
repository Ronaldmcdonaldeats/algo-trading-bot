"""Risk management and advanced trading features."""

from dataclasses import dataclass

from .portfolio_risk import PortfolioRiskManager
from .position_sizing import PositionSizer, PositionSizeResult
from .advanced_engine import AdvancedRiskEngine


# Legacy functions from trading_bot/risk.py for backward compatibility
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


def kelly_criterion_position_size(
    *,
    win_rate: float,
    avg_win: float,
    avg_loss: float,
    equity: float,
    kelly_fraction: float = 0.25
) -> float:
    """Kelly Criterion optimal position sizing
    
    Kelly % = (bp - q) / b
    where:
    - b = avg_win / avg_loss (odds)
    - p = win_rate
    - q = 1 - win_rate
    
    Uses fractional Kelly (typically 0.25) for risk management
    
    Args:
        win_rate: Fraction of winning trades (0-1)
        avg_win: Average profit per winning trade
        avg_loss: Average loss per losing trade (positive number)
        equity: Current portfolio equity
        kelly_fraction: Fraction of Kelly to use (0.25 = quarter Kelly)
    
    Returns:
        Position size as fraction of equity (0-1)
    """
    
    if not (0 <= win_rate <= 1):
        raise ValueError("win_rate must be between 0 and 1")
    
    if avg_win <= 0 or avg_loss <= 0:
        raise ValueError("avg_win and avg_loss must be positive")
    
    if kelly_fraction <= 0 or kelly_fraction > 1:
        raise ValueError("kelly_fraction must be between 0 and 1")
    
    # Calculate odds
    b = avg_win / avg_loss
    p = win_rate
    q = 1.0 - win_rate
    
    # Kelly formula
    kelly_pct = (b * p - q) / b if b > 0 else 0
    
    # Apply fractional Kelly for safety
    position_fraction = kelly_pct * kelly_fraction
    
    # Ensure position size is reasonable (0 to 1)
    position_fraction = max(0.0, min(1.0, position_fraction))
    
    return position_fraction


def kelly_position_shares(
    *,
    win_rate: float,
    avg_win: float,
    avg_loss: float,
    equity: float,
    entry_price: float,
    kelly_fraction: float = 0.25
) -> int:
    """Calculate shares to buy using Kelly Criterion
    
    Args:
        All Kelly parameters plus:
        entry_price: Current price to buy at
    
    Returns:
        Number of shares to buy
    """
    
    position_fraction = kelly_criterion_position_size(
        win_rate=win_rate,
        avg_win=avg_win,
        avg_loss=avg_loss,
        equity=equity,
        kelly_fraction=kelly_fraction
    )
    
    position_value = equity * position_fraction
    shares = int(position_value / entry_price) if entry_price > 0 else 0
    
    return max(shares, 0)


__all__ = [
    'PortfolioRiskManager',
    'PositionSizer',
    'PositionSizeResult',
    'AdvancedRiskEngine',
    'RiskParams',
    'stop_loss_price',
    'take_profit_price',
    'position_size_shares',
    'kelly_criterion_position_size',
    'kelly_position_shares',
]
