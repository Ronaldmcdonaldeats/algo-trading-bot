"""
Advanced portfolio optimization using correlations and Sharpe optimization.
Dynamically adjusts position sizes based on portfolio-level risk metrics.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple


@dataclass
class CorrelationMatrix:
    """Correlation analysis of portfolio symbols"""
    timestamp: datetime
    symbols: List[str]
    correlation: np.ndarray  # N x N correlation matrix
    avg_correlation: float
    max_correlation: float
    min_correlation: float
    
    def get_correlation(self, sym1: str, sym2: str) -> float:
        """Get correlation between two symbols"""
        if sym1 == sym2:
            return 1.0
        try:
            idx1 = self.symbols.index(sym1)
            idx2 = self.symbols.index(sym2)
            return float(self.correlation[idx1, idx2])
        except (ValueError, IndexError):
            return 0.0


@dataclass
class PortfolioRiskMetrics:
    """Portfolio-level risk statistics"""
    timestamp: datetime
    total_position_value: float
    portfolio_delta: float  # Sum of position betas
    concentration_ratio: float  # Herfindahl index (higher = more concentrated)
    effective_num_positions: int  # 1/concentration
    portfolio_volatility: float  # Overall portfolio vol
    correlation_drag: float  # Loss from correlation (vs uncorrelated)
    diversification_ratio: float  # Weighted avg vol / portfolio vol
    
    def is_concentrated(self) -> bool:
        """Check if portfolio is too concentrated"""
        return self.concentration_ratio > 0.25  # >25% in top position


@dataclass
class PositionAllocation:
    """Optimized position allocation"""
    symbol: str
    base_size: int  # Original position size
    optimized_size: int  # After portfolio optimization
    size_adjustment_pct: float  # % change in size
    correlation_penalty: float  # Adjustment due to correlations
    vol_adjustment: float  # Adjustment for volatility
    allocation_ratio: float  # % of portfolio
    recommendation: str  # INCREASE, DECREASE, HOLD
    
    def to_dict(self) -> Dict:
        return {
            'symbol': self.symbol,
            'base_size': self.base_size,
            'optimized_size': self.optimized_size,
            'adjustment_pct': self.size_adjustment_pct,
            'recommendation': self.recommendation,
        }


class PortfolioOptimizer:
    """
    Portfolio-level optimization engine.
    Adjusts position sizes based on correlations, volatility, and Sharpe ratio.
    """
    
    def __init__(
        self,
        lookback_bars: int = 50,  # Use last 50 bars for correlation
        rebalance_interval: int = 20,  # Rebalance every 20 bars
        max_concentration: float = 0.25,  # Max 25% in single position
        correlation_threshold: float = 0.7,  # Flag high correlations
    ):
        self.lookback_bars = lookback_bars
        self.rebalance_interval = rebalance_interval
        self.max_concentration = max_concentration
        self.correlation_threshold = correlation_threshold
        
        self.ohlcv_history: Dict[str, pd.DataFrame] = {}
        self.last_rebalance_bar = 0
        self.correlation_matrix: Optional[CorrelationMatrix] = None
        self.risk_metrics: Optional[PortfolioRiskMetrics] = None
        self.allocations: Dict[str, PositionAllocation] = {}
        self.rebalance_history: List[Tuple[int, float]] = []  # (bar, sharpe)
    
    def update_history(self, symbol: str, ohlcv: pd.DataFrame):
        """Update OHLCV history for correlation calculation"""
        # Keep only recent bars
        if len(ohlcv) > self.lookback_bars * 2:
            ohlcv = ohlcv.iloc[-self.lookback_bars * 2:]
        self.ohlcv_history[symbol] = ohlcv.copy()
    
    def calculate_correlations(self, symbols: List[str]) -> Optional[CorrelationMatrix]:
        """
        Calculate correlation matrix from returns
        
        Args:
            symbols: List of symbols to correlate
            
        Returns:
            CorrelationMatrix or None if insufficient data
        """
        if len(symbols) < 2:
            return None
        
        # Collect returns for all symbols
        returns_data = {}
        min_len = float('inf')
        
        for sym in symbols:
            if sym not in self.ohlcv_history:
                continue
            
            df = self.ohlcv_history[sym]
            if len(df) < 2:
                continue
            
            # Calculate returns
            returns = df['close'].pct_change().dropna()
            if len(returns) == 0:
                continue
            
            returns_data[sym] = returns
            min_len = min(min_len, len(returns))
        
        if len(returns_data) < 2 or min_len < 10:
            return None
        
        # Align all returns to same length
        returns_list = []
        symbol_list = []
        for sym, ret in returns_data.items():
            returns_list.append(ret.values[-min_len:])
            symbol_list.append(sym)
        
        # Create correlation matrix
        returns_array = np.array(returns_list).T
        corr_matrix = np.corrcoef(returns_array, rowvar=False)
        corr_matrix = np.nan_to_num(corr_matrix, nan=0.0)  # Replace NaN with 0
        
        # Calculate summary statistics
        # Exclude diagonal (self-correlation = 1.0)
        mask = ~np.eye(len(corr_matrix), dtype=bool)
        avg_corr = np.mean(corr_matrix[mask]) if np.any(mask) else 0.0
        max_corr = np.max(corr_matrix[mask]) if np.any(mask) else 0.0
        min_corr = np.min(corr_matrix[mask]) if np.any(mask) else 0.0
        
        return CorrelationMatrix(
            timestamp=datetime.now(),
            symbols=symbol_list,
            correlation=corr_matrix,
            avg_correlation=float(avg_corr),
            max_correlation=float(max_corr),
            min_correlation=float(min_corr),
        )
    
    def calculate_portfolio_metrics(
        self,
        positions: Dict,
        prices: Dict[str, float],
        equity: float,
        returns_by_symbol: Dict[str, float],
    ) -> PortfolioRiskMetrics:
        """
        Calculate portfolio-level risk metrics
        
        Args:
            positions: Current positions (symbol -> Position)
            prices: Current prices
            equity: Total equity
            returns_by_symbol: Recent returns by symbol
            
        Returns:
            PortfolioRiskMetrics
        """
        if equity <= 0:
            return PortfolioRiskMetrics(
                timestamp=datetime.now(),
                total_position_value=0,
                portfolio_delta=0,
                concentration_ratio=0,
                effective_num_positions=0,
                portfolio_volatility=0,
                correlation_drag=0,
                diversification_ratio=1.0,
            )
        
        # Calculate position values and weights
        position_values = {}
        weights = {}
        total_value = 0
        
        for symbol, position in positions.items():
            if position.qty == 0:
                continue
            
            price = prices.get(symbol, 0)
            if price <= 0:
                continue
            
            value = abs(position.qty * price)
            position_values[symbol] = value
            total_value += value
        
        if total_value == 0:
            return PortfolioRiskMetrics(
                timestamp=datetime.now(),
                total_position_value=0,
                portfolio_delta=0,
                concentration_ratio=0,
                effective_num_positions=0,
                portfolio_volatility=0,
                correlation_drag=0,
                diversification_ratio=1.0,
            )
        
        for symbol in position_values:
            weights[symbol] = position_values[symbol] / total_value
        
        # Calculate concentration (Herfindahl index)
        concentration = sum(w**2 for w in weights.values())
        effective_num = 1.0 / (concentration + 1e-6)
        
        # Calculate portfolio volatility
        symbol_vols = {}
        for symbol in weights:
            ret = np.array(returns_by_symbol.get(symbol, [0]))
            if len(ret) > 1:
                symbol_vols[symbol] = float(np.std(ret))
            else:
                symbol_vols[symbol] = 0.01
        
        # Weighted average volatility
        weighted_vol = sum(weights[s] * symbol_vols.get(s, 0.01) for s in weights)
        
        # Portfolio volatility with correlations
        if self.correlation_matrix is not None and len(weights) > 1:
            port_vol = self._calculate_portfolio_volatility(weights, symbol_vols)
            correlation_drag = (weighted_vol - port_vol) / (weighted_vol + 1e-6)
            diversification_ratio = weighted_vol / (port_vol + 1e-6)
        else:
            port_vol = weighted_vol
            correlation_drag = 0.0
            diversification_ratio = 1.0
        
        return PortfolioRiskMetrics(
            timestamp=datetime.now(),
            total_position_value=total_value,
            portfolio_delta=total_value / equity,
            concentration_ratio=float(concentration),
            effective_num_positions=int(effective_num),
            portfolio_volatility=float(port_vol),
            correlation_drag=float(correlation_drag),
            diversification_ratio=float(diversification_ratio),
        )
    
    def _calculate_portfolio_volatility(
        self,
        weights: Dict[str, float],
        symbol_vols: Dict[str, float],
    ) -> float:
        """Calculate portfolio volatility using correlation matrix"""
        if self.correlation_matrix is None:
            return sum(weights.get(s, 0) * symbol_vols.get(s, 0) for s in symbol_vols)
        
        symbols = list(weights.keys())
        if len(symbols) < 2:
            return symbol_vols.get(symbols[0], 0.01) if symbols else 0.01
        
        # Build weight vector aligned with correlation matrix
        w_vec = np.array([weights.get(s, 0) for s in self.correlation_matrix.symbols])
        vol_vec = np.array([symbol_vols.get(s, 0.01) for s in self.correlation_matrix.symbols])
        
        # Scale volatilities by weights
        scaled_vols = vol_vec * w_vec
        
        # Portfolio variance = w^T * V * Corr * V * w
        cov_matrix = np.outer(scaled_vols, scaled_vols) * self.correlation_matrix.correlation
        port_var = np.sum(cov_matrix)
        port_vol = np.sqrt(max(port_var, 0))
        
        return float(port_vol)
    
    def optimize_allocations(
        self,
        positions: Dict,
        prices: Dict[str, float],
        equity: float,
        current_bar: int,
    ) -> Dict[str, PositionAllocation]:
        """
        Optimize position allocations based on portfolio metrics
        
        Args:
            positions: Current positions
            prices: Current prices
            equity: Total equity
            current_bar: Current bar number
            
        Returns:
            Dict of symbol -> optimized allocation
        """
        self.allocations.clear()
        
        # Check if rebalancing needed
        if current_bar - self.last_rebalance_bar < self.rebalance_interval:
            return {}  # Not yet due for rebalance
        
        # Collect returns for metrics
        returns_by_symbol = {}
        for symbol, df in self.ohlcv_history.items():
            if len(df) > 1:
                returns_by_symbol[symbol] = df['close'].pct_change().dropna().values
        
        # Calculate portfolio metrics
        self.risk_metrics = self.calculate_portfolio_metrics(
            positions=positions,
            prices=prices,
            equity=equity,
            returns_by_symbol=returns_by_symbol,
        )
        
        # If not concentrated, no major adjustment needed
        if not self.risk_metrics.is_concentrated():
            return {}
        
        # Calculate new allocations
        target_allocation = 1.0 / max(len(positions), 1)
        
        for symbol, position in positions.items():
            if position.qty == 0:
                continue
            
            price = prices.get(symbol, 0)
            if price <= 0:
                continue
            
            base_size = position.qty
            
            # Correlation adjustment
            corr_penalty = 0.0
            if self.correlation_matrix is not None:
                for other_sym in self.correlation_matrix.symbols:
                    if other_sym == symbol:
                        continue
                    if other_sym not in positions or positions[other_sym].qty == 0:
                        continue
                    
                    corr = self.correlation_matrix.get_correlation(symbol, other_sym)
                    if corr > self.correlation_threshold:
                        corr_penalty += (corr - 0.5) * 0.1  # Penalize high correlations
            
            # Volatility adjustment
            vol = np.std(returns_by_symbol.get(symbol, [0.01]))
            vol_adjustment = 1.0 - min(vol * 5, 0.3)  # Reduce high vol positions by up to 30%
            
            # Calculate optimized size
            adjustment_factor = (1.0 - corr_penalty) * vol_adjustment
            adjustment_factor = np.clip(adjustment_factor, 0.7, 1.3)  # Cap at ±30%
            
            optimized_size = int(base_size * adjustment_factor)
            optimized_size = max(optimized_size, 1) if base_size > 0 else 0
            
            # Recommendation
            size_change = optimized_size - base_size
            if size_change > base_size * 0.1:
                recommendation = "INCREASE"
            elif size_change < -base_size * 0.1:
                recommendation = "DECREASE"
            else:
                recommendation = "HOLD"
            
            allocation = PositionAllocation(
                symbol=symbol,
                base_size=base_size,
                optimized_size=optimized_size,
                size_adjustment_pct=(size_change / base_size * 100) if base_size > 0 else 0,
                correlation_penalty=float(corr_penalty),
                vol_adjustment=float(vol_adjustment),
                allocation_ratio=optimized_size * price / equity if equity > 0 else 0,
                recommendation=recommendation,
            )
            
            self.allocations[symbol] = allocation
        
        self.last_rebalance_bar = current_bar
        return self.allocations
    
    def get_high_correlation_pairs(self) -> List[Tuple[str, str, float]]:
        """Get pairs of symbols with correlation above threshold"""
        if self.correlation_matrix is None:
            return []
        
        pairs = []
        symbols = self.correlation_matrix.symbols
        
        for i in range(len(symbols)):
            for j in range(i + 1, len(symbols)):
                corr = self.correlation_matrix.correlation[i, j]
                if corr > self.correlation_threshold:
                    pairs.append((symbols[i], symbols[j], float(corr)))
        
        return sorted(pairs, key=lambda x: x[2], reverse=True)
    
    def print_summary(self):
        """Print portfolio optimization summary"""
        if self.risk_metrics is None or not self.allocations:
            print("[PORTFOLIO OPT] Not yet optimizing")
            return
        
        print("\n[PORTFOLIO OPTIMIZATION REPORT]")
        print(f"  Concentration Ratio: {self.risk_metrics.concentration_ratio:.3f} " +
              f"({'CONCENTRATED' if self.risk_metrics.is_concentrated() else 'diversified'})")
        print(f"  Effective Positions: {self.risk_metrics.effective_num_positions}")
        print(f"  Portfolio Volatility: {self.risk_metrics.portfolio_volatility:.4f}")
        print(f"  Diversification Ratio: {self.risk_metrics.diversification_ratio:.3f}x")
        
        if self.allocations:
            print(f"\n  Position Adjustments:")
            for symbol, alloc in sorted(self.allocations.items()):
                print(f"    {symbol}: {alloc.base_size} → {alloc.optimized_size} " +
                      f"({alloc.size_adjustment_pct:+.1f}%) [{alloc.recommendation}]")
        
        # High correlation pairs
        high_corr_pairs = self.get_high_correlation_pairs()
        if high_corr_pairs:
            print(f"\n  High Correlation Pairs (>{self.correlation_threshold}):")
            for sym1, sym2, corr in high_corr_pairs[:5]:
                print(f"    {sym1}-{sym2}: {corr:.3f}")
