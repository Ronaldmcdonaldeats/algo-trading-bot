"""Volatility-based position sizing with regime detection and dynamic adjustments."""

from __future__ import annotations

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Optional


@dataclass
class VolatilityRegime:
    """Current volatility regime classification."""
    regime: str  # 'low', 'normal', 'high'
    vix_level: float
    historical_vol: float
    percentile: float  # 0-100, where 100 is highest vol
    adjustment_factor: float  # Position size multiplier


class VolatilityRegimeDetector:
    """Detect and adapt to volatility regimes for dynamic position sizing."""

    def __init__(self, lookback_days: int = 60):
        """Initialize volatility detector.
        
        Args:
            lookback_days: Days of history for volatility calculation
        """
        self.lookback_days = lookback_days
        self.volatility_history = []
        
    def calculate_historical_volatility(self, prices: pd.Series) -> float:
        """Calculate historical volatility from price series.
        
        Args:
            prices: Price series (closing prices)
            
        Returns:
            Annualized volatility (0-1)
        """
        if len(prices) < 2:
            return 0.0
        
        returns = prices.pct_change().dropna()
        if len(returns) == 0:
            return 0.0
            
        daily_vol = returns.std()
        annual_vol = daily_vol * np.sqrt(252)  # 252 trading days
        return annual_vol
    
    def detect_regime(
        self, 
        historical_vol: float, 
        vix_level: Optional[float] = None,
        vol_history: Optional[list[float]] = None
    ) -> VolatilityRegime:
        """Detect current volatility regime.
        
        Args:
            historical_vol: Current historical volatility (0-1)
            vix_level: Current VIX level (optional, 0-100)
            vol_history: List of historical volatility levels for percentile calculation
            
        Returns:
            VolatilityRegime object with classification and adjustment factor
        """
        # Use VIX if available, otherwise use historical vol
        if vix_level is not None:
            # VIX-based classification
            if vix_level < 15:
                regime = "low"
                adjustment_factor = 1.2  # Increase size in low vol
            elif vix_level < 25:
                regime = "normal"
                adjustment_factor = 1.0
            else:
                regime = "high"
                adjustment_factor = 0.7  # Reduce size in high vol
        else:
            # Historical volatility based
            if historical_vol < 0.15:
                regime = "low"
                adjustment_factor = 1.2
            elif historical_vol < 0.25:
                regime = "normal"
                adjustment_factor = 1.0
            else:
                regime = "high"
                adjustment_factor = 0.7
        
        # Calculate volatility percentile
        percentile = 0.0
        if vol_history and len(vol_history) > 1:
            percentile = (np.sum(np.array(vol_history) <= historical_vol) / len(vol_history)) * 100
        
        return VolatilityRegime(
            regime=regime,
            vix_level=vix_level or historical_vol * 100,  # Approximate
            historical_vol=historical_vol,
            percentile=percentile,
            adjustment_factor=adjustment_factor,
        )
    
    def calculate_var_based_position_size(
        self,
        portfolio_value: float,
        daily_loss_limit: float,
        volatility: float,
        expected_return: float = 0.005,  # 0.5% average expected return per trade
        confidence_level: float = 0.95,
    ) -> float:
        """Calculate position size based on Value-at-Risk (VaR).
        
        Args:
            portfolio_value: Total portfolio value
            daily_loss_limit: Max loss allowed per day (absolute $)
            volatility: Stock volatility (annualized)
            expected_return: Expected return of the trade
            confidence_level: Confidence level for VaR (0-1)
            
        Returns:
            Maximum position size (fraction of portfolio)
        """
        # Z-score for confidence level
        z_scores = {0.90: 1.28, 0.95: 1.645, 0.99: 2.33}
        z = z_scores.get(confidence_level, 1.645)
        
        # Daily volatility (in fraction)
        daily_vol = volatility / np.sqrt(252)
        
        # VaR calculation: How much can we lose in 1 day at confidence level?
        var_daily = daily_vol * z
        
        # Position size: What fraction of portfolio should we risk?
        # Risk = position_size * var_daily
        max_position_fraction = daily_loss_limit / (portfolio_value * var_daily) if var_daily > 0 else 0.1
        
        # Cap at reasonable maximum (don't exceed 20% per trade)
        max_position_fraction = min(max_position_fraction, 0.20)
        
        return max_position_fraction
    
    def get_dynamic_kelly_fraction(
        self, 
        win_rate: float, 
        avg_win: float, 
        avg_loss: float,
        volatility: float,
        regime: VolatilityRegime,
        base_kelly_fraction: float = 0.25,
    ) -> float:
        """Get Kelly Criterion fraction adjusted for volatility regime.
        
        Args:
            win_rate: Win rate (0-1)
            avg_win: Average win size
            avg_loss: Average loss size (positive number)
            volatility: Current volatility
            regime: Current volatility regime
            base_kelly_fraction: Base Kelly fraction (0.25 for safety)
            
        Returns:
            Adjusted Kelly fraction
        """
        if avg_loss == 0 or win_rate == 0:
            return base_kelly_fraction
        
        # Standard Kelly formula
        kelly_fraction = (win_rate * avg_win - (1 - win_rate) * avg_loss) / avg_win
        
        # Apply fractional Kelly for safety
        kelly_fraction = kelly_fraction * base_kelly_fraction
        
        # Apply volatility adjustment
        kelly_fraction = kelly_fraction * regime.adjustment_factor
        
        # Cap at reasonable limits
        kelly_fraction = max(0.01, min(kelly_fraction, 0.10))  # 1-10% max
        
        return kelly_fraction


class DynamicPositionSizer:
    """Dynamic position sizing based on multiple factors."""
    
    def __init__(self, portfolio_value: float, daily_loss_limit: float = 0.02):
        """Initialize position sizer.
        
        Args:
            portfolio_value: Total portfolio value
            daily_loss_limit: Max loss as fraction of portfolio (default 2%)
        """
        self.portfolio_value = portfolio_value
        self.daily_loss_limit = portfolio_value * daily_loss_limit
        self.volatility_detector = VolatilityRegimeDetector()
    
    def calculate_position_size(
        self,
        symbol: str,
        current_price: float,
        volatility: float,
        vix_level: Optional[float] = None,
        win_rate: Optional[float] = None,
        avg_win: Optional[float] = None,
        avg_loss: Optional[float] = None,
        vol_history: Optional[list[float]] = None,
    ) -> dict:
        """Calculate optimal position size.
        
        Args:
            symbol: Stock symbol
            current_price: Current stock price
            volatility: Stock volatility (annualized)
            vix_level: Current VIX level (optional)
            win_rate: Historical win rate (optional)
            avg_win: Average win size (optional)
            avg_loss: Average loss size (optional)
            vol_history: Historical volatility levels (optional)
            
        Returns:
            Dict with position sizing details
        """
        # Detect volatility regime
        regime = self.volatility_detector.detect_regime(volatility, vix_level, vol_history)
        
        # Calculate VaR-based position size
        var_position_fraction = self.volatility_detector.calculate_var_based_position_size(
            self.portfolio_value,
            self.daily_loss_limit,
            volatility,
        )
        
        # Calculate Kelly-based position size if we have performance metrics
        kelly_fraction = 0.05  # Default conservative fraction
        if win_rate is not None and avg_win is not None and avg_loss is not None:
            kelly_fraction = self.volatility_detector.get_dynamic_kelly_fraction(
                win_rate=win_rate,
                avg_win=avg_win,
                avg_loss=avg_loss,
                volatility=volatility,
                regime=regime,
            )
        
        # Use more conservative of the two methods
        position_fraction = min(var_position_fraction, kelly_fraction)
        
        # Calculate actual shares
        cash_available = self.portfolio_value * position_fraction
        shares = int(cash_available / current_price)
        
        return {
            "symbol": symbol,
            "shares": shares,
            "position_fraction": position_fraction,
            "position_value": shares * current_price,
            "regime": regime.regime,
            "volatility": volatility,
            "adjustment_factor": regime.adjustment_factor,
            "var_based_fraction": var_position_fraction,
            "kelly_based_fraction": kelly_fraction,
            "vix_level": regime.vix_level,
            "vol_percentile": regime.percentile,
        }
    
    def update_portfolio_value(self, new_value: float) -> None:
        """Update portfolio value and loss limit."""
        self.portfolio_value = new_value
        self.daily_loss_limit = new_value * 0.02
