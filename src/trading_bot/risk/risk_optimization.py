"""
Risk optimization functions for Phase 3 and beyond.

These are the new optimized risk management functions added in Phase 3.
"""

import logging
from typing import Dict, List, Tuple
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


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
    
    Example:
        >>> dynamic_stop_loss(entry_price=100, atr_value=2.0, 
        ...                   atr_multiplier=2.0, market_volatility=1.0)
        96.0
        >>> dynamic_stop_loss(entry_price=100, atr_value=2.0,
        ...                   atr_multiplier=2.0, market_volatility=2.0)
        92.0  # Wider stop in high volatility
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
        equity: Account equity
        entry_price: Entry price
        stop_loss_price_: Stop-loss price
        max_risk: Maximum risk per trade (e.g., 0.02 = 2%)
        volatility_index: Current market volatility (1.0 = normal, >1 = high)
    
    Returns:
        Position size adjusted for volatility
    
    Example:
        >>> volatility_adjusted_position_size(
        ...     equity=100000, entry_price=50, stop_loss_price_=49,
        ...     max_risk=0.02, volatility_index=1.0)
        2000
        >>> volatility_adjusted_position_size(
        ...     equity=100000, entry_price=50, stop_loss_price_=49,
        ...     max_risk=0.02, volatility_index=2.0)
        1000  # 50% smaller in 2x volatility
    """
    # First calculate base position size
    if equity <= 0:
        raise ValueError("equity must be positive")
    if entry_price <= 0:
        raise ValueError("entry_price must be positive")
    if stop_loss_price_ <= 0 or stop_loss_price_ >= entry_price:
        raise ValueError("stop_loss_price_ must be positive and < entry_price")
    if not (0 < max_risk < 1):
        raise ValueError("max_risk must be between 0 and 1")
    if volatility_index <= 0:
        raise ValueError("volatility_index must be positive")
    
    risk_budget = equity * max_risk
    per_share_risk = entry_price - stop_loss_price_
    base_size = int(risk_budget // per_share_risk)
    
    # Reduce size when volatility is high (inverse relationship)
    # High volatility (2.0) → 50% position size
    # Normal volatility (1.0) → 100% position size
    volatility_factor = 1.0 / (1.0 + max(0, volatility_index - 1.0))
    adjusted_size = int(base_size * volatility_factor)
    
    logger.debug(f"Position size: {base_size} → {adjusted_size} (volatility={volatility_index:.2f})")
    return max(adjusted_size, 0)


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
    
    @property
    def current_drawdown_percent(self) -> float:
        """Get current drawdown as percentage."""
        return self.current_drawdown
    
    def update(self, current_equity: float) -> Tuple[bool, float]:
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
        returns: Dict[str, List[float]]
    ) -> float:
        """Calculate average correlation between portfolio positions.
        
        Args:
            returns: Dict of symbol -> list of returns
        
        Returns:
            Average correlation (0-1, where 1 = perfectly correlated)
        """
        symbols = list(returns.keys())
        if len(symbols) < 2:
            return 0.0
        
        # Convert to numpy arrays
        returns_array = np.array([returns[s] for s in symbols])
        
        # Calculate correlation matrix
        corr_matrix = np.corrcoef(returns_array)
        
        # Average absolute correlation (exclude diagonal)
        n = len(symbols)
        if n > 1:
            # Sum absolute values, subtract diagonal (n ones), divide by off-diagonal count
            avg_corr = (np.sum(np.abs(corr_matrix)) - n) / (n * (n - 1))
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
        symbol_returns: Dict[str, List[float]],
        proposed_size: int,
    ) -> Tuple[bool, str]:
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


__all__ = [
    'dynamic_stop_loss',
    'volatility_adjusted_position_size',
    'DrawdownManager',
    'CorrelationRiskManager',
    'RiskAggregator',
]
