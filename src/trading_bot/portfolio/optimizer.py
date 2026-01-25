"""Portfolio optimization using modern portfolio theory."""

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)


class PortfolioOptimizer:
    """Optimize position sizing and allocation using correlations and volatility."""

    def __init__(self, lookback_periods: int = 20):
        """Initialize optimizer.
        
        Args:
            lookback_periods: Number of periods to use for correlation/volatility calculation
        """
        self.lookback_periods = lookback_periods

    def calculate_sharpe_ratio(
        self, returns: pd.Series, risk_free_rate: float = 0.04
    ) -> float:
        """Calculate Sharpe ratio from returns.
        
        Args:
            returns: Series of returns (daily)
            risk_free_rate: Annual risk-free rate (default 4%)
            
        Returns:
            Annualized Sharpe ratio
        """
        if returns.empty or len(returns) < 2:
            return 0.0
        
        mean_return = returns.mean()
        std_return = returns.std()
        
        if std_return == 0:
            return 0.0
        
        # Annualize (252 trading days)
        annual_return = mean_return * 252
        annual_std = std_return * np.sqrt(252)
        
        sharpe = (annual_return - risk_free_rate) / annual_std if annual_std > 0 else 0.0
        return float(sharpe)

    def calculate_volatility(self, prices: pd.Series) -> float:
        """Calculate annualized volatility.
        
        Args:
            prices: Series of prices
            
        Returns:
            Annualized volatility
        """
        if len(prices) < 2:
            return 0.0
        
        returns = prices.pct_change().dropna()
        if len(returns) == 0:
            return 0.0
        
        return float(returns.std() * np.sqrt(252))

    def get_position_sizes(
        self,
        symbols: List[str],
        prices: Dict[str, float],
        volatilities: Dict[str, float],
        correlations: pd.DataFrame | None = None,
        max_allocation: float = 0.15,
    ) -> Dict[str, float]:
        """Calculate optimal position sizes based on inverse volatility weighting.
        
        Args:
            symbols: List of symbols to trade
            prices: Current prices for each symbol
            volatilities: Volatility for each symbol
            correlations: Correlation matrix (optional)
            max_allocation: Max % of portfolio per position (default 15%)
            
        Returns:
            Dict of symbol -> allocation percentage
        """
        allocations = {}
        
        if not symbols or not volatilities:
            return allocations
        
        # Filter symbols with valid volatility
        valid_symbols = [s for s in symbols if s in volatilities and volatilities[s] > 0]
        
        if not valid_symbols:
            # Equal weight fallback
            equal_weight = 1.0 / len(symbols) if symbols else 0.0
            return {s: min(equal_weight, max_allocation) for s in symbols}
        
        # Inverse volatility weighting (less volatile = higher allocation)
        inv_vol = {}
        for symbol in valid_symbols:
            vol = max(volatilities[symbol], 0.001)  # Avoid division by zero
            inv_vol[symbol] = 1.0 / vol
        
        total_inv_vol = sum(inv_vol.values())
        
        if total_inv_vol == 0:
            equal_weight = 1.0 / len(valid_symbols)
            return {s: min(equal_weight, max_allocation) for s in valid_symbols}
        
        # Calculate weights and apply max allocation cap
        for symbol in valid_symbols:
            weight = inv_vol[symbol] / total_inv_vol
            # Cap at max_allocation and scale down if needed
            allocations[symbol] = min(weight, max_allocation)
        
        # Normalize to 1.0 if we hit caps
        total = sum(allocations.values())
        if total > 1.0:
            for symbol in allocations:
                allocations[symbol] = allocations[symbol] / total
        
        return allocations

    def calculate_correlation_matrix(
        self, price_data: Dict[str, pd.Series]
    ) -> pd.DataFrame:
        """Calculate correlation matrix from price data.
        
        Args:
            price_data: Dict of symbol -> price series
            
        Returns:
            Correlation matrix
        """
        if not price_data:
            return pd.DataFrame()
        
        # Create DataFrame with only recent data
        df = pd.DataFrame(price_data)
        df = df.tail(self.lookback_periods)
        
        if df.empty:
            return pd.DataFrame()
        
        # Calculate returns correlation
        returns = df.pct_change().dropna()
        
        if returns.empty:
            return pd.DataFrame()
        
        return returns.corr()

    def get_diversified_symbols(
        self,
        symbols: List[str],
        correlations: pd.DataFrame,
        max_correlation: float = 0.7,
        min_symbols: int = 5,
    ) -> List[str]:
        """Select diversified subset of symbols based on correlations.
        
        Args:
            symbols: List of candidate symbols
            correlations: Correlation matrix
            max_correlation: Maximum correlation to other selected symbols
            min_symbols: Minimum symbols to return (ignore max_correlation if needed)
            
        Returns:
            List of diversified symbols
        """
        if len(symbols) <= min_symbols:
            return symbols
        
        if correlations.empty:
            return symbols[:min_symbols]
        
        selected = []
        remaining = list(symbols)
        
        # Start with first symbol
        if remaining:
            selected.append(remaining.pop(0))
        
        # Greedily add symbols with lowest correlation to selected set
        while remaining and len(selected) < len(symbols):
            best_symbol = None
            best_correlation = 2.0  # Start high
            
            for symbol in remaining:
                if symbol not in correlations.index:
                    continue
                
                # Get max correlation with already selected
                max_corr = 0.0
                for selected_symbol in selected:
                    if selected_symbol in correlations.columns:
                        corr = abs(correlations.loc[symbol, selected_symbol])
                        max_corr = max(max_corr, corr)
                
                if max_corr < best_correlation:
                    best_correlation = max_corr
                    best_symbol = symbol
            
            if best_symbol and best_correlation < max_correlation:
                selected.append(best_symbol)
                remaining.remove(best_symbol)
            elif len(selected) >= min_symbols:
                # Minimum diversity reached
                break
            else:
                # Add next anyway to meet minimum
                if remaining:
                    selected.append(remaining.pop(0))
        
        return selected
