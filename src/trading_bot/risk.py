from __future__ import annotations

from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RiskParams:
    max_risk_per_trade: float  # e.g. 0.02
    stop_loss_pct: float  # e.g. 0.015
    take_profit_pct: float  # e.g. 0.03


def stop_loss_price(entry_price: float, stop_loss_pct: float) -> float:
    """Calculate stop-loss price with ATR-aware adjustment"""
    return entry_price * (1.0 - stop_loss_pct)


def take_profit_price(entry_price: float, take_profit_pct: float) -> float:
    """Calculate take-profit price"""
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


def dynamic_stop_loss(
    *,
    entry_price: float,
    atr_value: float,
    atr_multiplier: float = 2.0,
    market_volatility: float = 1.0,
) -> float:
    """OPTIMIZED: Calculate dynamic stop-loss based on volatility
    
    Adjusts stop-loss distance based on ATR and market volatility.
    - Higher volatility → wider stops (to avoid whipsaws)
    - Lower volatility → tighter stops (to limit downside)
    
    Args:
        entry_price: Entry price
        atr_value: Current ATR value
        atr_multiplier: Multiplier for ATR (typically 1.5-3.0)
        market_volatility: Volatility adjustment (1.0 = normal, >1 = high volatility)
    
    Returns:
        Stop-loss price
    """
    if entry_price <= 0:
        raise ValueError("entry_price must be positive")
    if atr_value <= 0:
        raise ValueError("atr_value must be positive")
    if atr_multiplier <= 0:
        raise ValueError("atr_multiplier must be positive")
    if market_volatility <= 0:
        raise ValueError("market_volatility must be positive")
    
    # Adjust ATR-based stop by volatility factor
    adjusted_atr = atr_value * atr_multiplier * market_volatility
    stop_loss = entry_price - adjusted_atr
    
    # Ensure stop is at least slightly below entry
    min_stop = entry_price * 0.98
    return max(stop_loss, min_stop)


def volatility_adjusted_position_size(
    *,
    equity: float,
    entry_price: float,
    stop_loss_price_: float,
    max_risk: float,
    volatility_index: float = 1.0,
) -> int:
    """OPTIMIZED: Position sizing with volatility adjustment
    
    Reduces position size when volatility is high (risk management).
    
    Args:
        volatility_index: Current market volatility (1.0 = normal, >1 = high)
    
    Returns:
        Position size adjusted for volatility
    """
    # First calculate base position size
    base_size = position_size_shares(
        equity=equity,
        entry_price=entry_price,
        stop_loss_price_=stop_loss_price_,
        max_risk=max_risk,
    )
    
    # Reduce size when volatility is high (inverse relationship)
    # High volatility (2.0) → 50% position size
    # Normal volatility (1.0) → 100% position size
    volatility_factor = 1.0 / (1.0 + max(0, volatility_index - 1.0))
    adjusted_size = int(base_size * volatility_factor)
    
    logger.debug(f"Position size: {base_size} → {adjusted_size} (volatility={volatility_index:.2f})")
    return max(adjusted_size, 0)


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


@dataclass(frozen=True)
class PortfolioRiskMetrics:
    """Portfolio-level risk metrics."""
    total_exposure: float  # % of equity exposed
    portfolio_beta: float  # Systematic risk
    max_drawdown_limit: float  # Maximum acceptable drawdown %
    var_95: float  # Value at Risk at 95% confidence
    correlation_risk: float  # Risk from correlated positions (0-1)


class DrawdownManager:
    """Track and enforce drawdown limits."""
    
    def __init__(self, max_drawdown_pct: float = 0.20):
        """
        Args:
            max_drawdown_pct: Stop trading if drawdown exceeds this (e.g., 0.20 = 20%)
        """
        if not (0 < max_drawdown_pct < 1):
            raise ValueError("max_drawdown_pct must be between 0 and 1")
        
        self.max_drawdown_pct = max_drawdown_pct
        self.peak_equity = None
        self.current_drawdown = 0.0
    
    def update(self, current_equity: float) -> tuple[bool, float]:
        """Update drawdown tracking and check if trading should stop.
        
        Args:
            current_equity: Current portfolio equity
        
        Returns:
            (should_continue_trading, current_drawdown_pct)
        """
        if self.peak_equity is None or current_equity > self.peak_equity:
            self.peak_equity = current_equity
        
        if self.peak_equity > 0:
            self.current_drawdown = (self.peak_equity - current_equity) / self.peak_equity
        
        should_continue = self.current_drawdown <= self.max_drawdown_pct
        return should_continue, self.current_drawdown
    
    def reset(self, new_peak: float) -> None:
        """Reset drawdown tracking (e.g., after recovery)."""
        self.peak_equity = new_peak
        self.current_drawdown = 0.0


class CorrelationRiskManager:
    """Manage portfolio risk from correlated positions."""
    
    @staticmethod
    def calculate_portfolio_correlation(
        returns: dict[str, list[float]]
    ) -> float:
        """Calculate average correlation between portfolio positions.
        
        Args:
            returns: Dict of symbol -> list of returns
        
        Returns:
            Average correlation (0-1, where 1 = perfectly correlated)
        """
        import numpy as np
        
        symbols = list(returns.keys())
        if len(symbols) < 2:
            return 0.0
        
        # Convert to numpy arrays
        returns_array = np.array([returns[s] for s in symbols])
        
        # Calculate correlation matrix
        corr_matrix = np.corrcoef(returns_array)
        
        # Average off-diagonal elements (exclude 1s on diagonal)
        n = len(symbols)
        if n > 1:
            avg_corr = np.sum(np.abs(corr_matrix)) / (n * (n - 1))
        else:
            avg_corr = 0.0
        
        return float(avg_corr)
    
    @staticmethod
    def adjust_position_size_for_correlation(
        base_position: int,
        correlation: float,
        correlation_threshold: float = 0.7
    ) -> int:
        """Reduce position size if correlation with portfolio is too high.
        
        Args:
            base_position: Original position size
            correlation: Portfolio correlation (0-1)
            correlation_threshold: Above this, reduce position size
        
        Returns:
            Adjusted position size
        """
        if correlation >= correlation_threshold:
            # Reduce position by percentage above threshold
            excess = correlation - correlation_threshold
            reduction_factor = 1.0 - (excess * 2)  # Up to 60% reduction
            return int(base_position * max(0.4, reduction_factor))
        
        return base_position


class RiskAggregator:
    """Aggregate and manage multiple risk constraints."""
    
    def __init__(
        self,
        max_drawdown_pct: float = 0.20,
        max_correlation: float = 0.7,
        max_exposure_pct: float = 0.95,
    ):
        self.drawdown_mgr = DrawdownManager(max_drawdown_pct)
        self.correlation_threshold = max_correlation
        self.max_exposure_pct = max_exposure_pct
    
    def check_position_allowed(
        self,
        current_equity: float,
        current_exposure_pct: float,
        symbol_returns: dict[str, list[float]],
        proposed_size: int,
    ) -> tuple[bool, str]:
        """Check if a new position is allowed under all risk constraints.
        
        Args:
            current_equity: Current portfolio value
            current_exposure_pct: % of equity already deployed
            symbol_returns: Returns for each symbol to calculate correlation
            proposed_size: Size of proposed new position
        
        Returns:
            (allowed, reason)
        """
        # Check drawdown limit
        can_trade, dd = self.drawdown_mgr.update(current_equity)
        if not can_trade:
            return False, f"Drawdown limit exceeded: {dd:.1%}"
        
        # Check exposure limit
        if current_exposure_pct >= self.max_exposure_pct:
            return False, f"Exposure limit reached: {current_exposure_pct:.1%}/{self.max_exposure_pct:.1%}"
        
        # Check correlation
        if symbol_returns:
            correlation = CorrelationRiskManager.calculate_portfolio_correlation(symbol_returns)
            if correlation > self.correlation_threshold:
                return False, f"Portfolio correlation too high: {correlation:.2f}"
        
        return True, "Position allowed"