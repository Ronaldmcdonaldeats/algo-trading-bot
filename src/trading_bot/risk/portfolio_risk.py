"""Portfolio-level risk management with VaR, CVaR calculations."""

import numpy as np
from typing import Dict, List, Any, Tuple
from datetime import datetime, timedelta
import pandas as pd
from scipy import stats


class PortfolioRiskManager:
    """Calculate portfolio risk metrics (VaR, CVaR, Greeks, concentration risk)."""
    
    def __init__(self, confidence_level: float = 0.95, lookback_days: int = 252):
        self.confidence_level = confidence_level
        self.lookback_days = lookback_days
        self.alpha = 1 - confidence_level
    
    def calculate_var(self, returns: np.ndarray, method: str = "historical") -> float:
        """
        Calculate Value at Risk (VaR).
        
        Args:
            returns: Array of returns (e.g., daily returns)
            method: "historical", "gaussian", or "cornish-fisher"
        
        Returns:
            VaR value (negative number, e.g., -0.05 for 5% loss)
        """
        if method == "historical":
            return np.percentile(returns, self.alpha * 100)
        
        elif method == "gaussian":
            mean = np.mean(returns)
            std = np.std(returns)
            return mean + std * stats.norm.ppf(self.alpha)
        
        elif method == "cornish-fisher":
            mean = np.mean(returns)
            std = np.std(returns)
            skew = stats.skew(returns)
            kurt = stats.kurtosis(returns)
            
            z_alpha = stats.norm.ppf(self.alpha)
            z_cf = z_alpha + (z_alpha**2 - 1) / 6 * skew + (z_alpha**3 - 3*z_alpha) / 24 * kurt
            
            return mean + std * z_cf
        
        else:
            raise ValueError(f"Unknown method: {method}")
    
    def calculate_cvar(self, returns: np.ndarray, method: str = "historical") -> float:
        """
        Calculate Conditional Value at Risk (CVaR/Expected Shortfall).
        Average loss when loss exceeds VaR.
        
        Returns:
            CVaR value (more negative than VaR, represents tail risk)
        """
        var = self.calculate_var(returns, method="historical")
        
        if method == "historical":
            return returns[returns <= var].mean()
        
        elif method == "gaussian":
            mean = np.mean(returns)
            std = np.std(returns)
            pdf_value = stats.norm.pdf(stats.norm.ppf(self.alpha))
            return mean - std * pdf_value / self.alpha
        
        else:
            return returns[returns <= var].mean()
    
    def portfolio_var(self, positions: Dict[str, float], returns_dict: Dict[str, np.ndarray]) -> float:
        """
        Calculate portfolio VaR across all positions.
        
        Args:
            positions: {symbol: quantity}
            returns_dict: {symbol: array_of_returns}
        
        Returns:
            Portfolio VaR in dollars
        """
        if not positions:
            return 0.0
        
        # Get correlation matrix
        symbols = list(positions.keys())
        returns_list = []
        valid_symbols = []
        
        for sym in symbols:
            if sym in returns_dict and len(returns_dict[sym]) > 0:
                returns_list.append(returns_dict[sym])
                valid_symbols.append(sym)
        
        if not returns_list:
            return 0.0
        
        # Align returns to same length
        min_length = min(len(r) for r in returns_list)
        aligned_returns = np.array([r[-min_length:] for r in returns_list])
        
        # Calculate correlation matrix
        corr_matrix = np.corrcoef(aligned_returns)
        
        # Portfolio returns
        weights = np.array([positions.get(sym, 0) for sym in valid_symbols])
        portfolio_std = np.sqrt(weights @ corr_matrix @ weights.T)
        
        mean_return = np.mean(aligned_returns, axis=1)
        portfolio_mean = weights @ mean_return
        
        var_single = portfolio_mean - portfolio_std * stats.norm.ppf(1 - self.alpha)
        
        return var_single
    
    def calculate_concentration_risk(self, positions: Dict[str, float]) -> Dict[str, Any]:
        """
        Calculate concentration risk metrics.
        
        Returns:
            {
                'herfindahl_index': HHI (0=diversified, 1=concentrated),
                'top_3_concentration': % of portfolio in top 3 positions,
                'sector_concentration': concentration by sector,
                'position_weight': weight of each position
            }
        """
        total_value = sum(abs(v) for v in positions.values())
        
        if total_value == 0:
            return {'herfindahl_index': 0, 'top_3_concentration': 0, 'position_weight': {}}
        
        weights = {k: abs(v) / total_value for k, v in positions.items()}
        
        # Herfindahl-Hirschman Index
        hhi = sum(w**2 for w in weights.values())
        
        # Top 3 concentration
        top_3 = sorted(weights.values(), reverse=True)[:3]
        top_3_conc = sum(top_3)
        
        return {
            'herfindahl_index': hhi,
            'top_3_concentration': top_3_conc,
            'position_weight': weights,
            'max_position': max(weights.values()) if weights else 0,
            'min_position': min(weights.values()) if weights else 0
        }
    
    def calculate_drawdown(self, equity_curve: np.ndarray) -> Tuple[float, float]:
        """
        Calculate maximum drawdown and current drawdown.
        
        Returns:
            (max_drawdown, current_drawdown) as decimals (e.g., -0.15 for -15%)
        """
        if len(equity_curve) < 2:
            return 0.0, 0.0
        
        cummax = np.maximum.accumulate(equity_curve)
        drawdown = (equity_curve - cummax) / cummax
        max_dd = np.min(drawdown)
        current_dd = drawdown[-1]
        
        return float(max_dd), float(current_dd)
    
    def calculate_sharpe_ratio(self, returns: np.ndarray, risk_free_rate: float = 0.02) -> float:
        """Calculate Sharpe Ratio."""
        if len(returns) < 2:
            return 0.0
        
        excess_returns = returns - risk_free_rate / 252  # Daily
        return np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252)
    
    def calculate_sortino_ratio(self, returns: np.ndarray, risk_free_rate: float = 0.02) -> float:
        """Calculate Sortino Ratio (downside deviation)."""
        if len(returns) < 2:
            return 0.0
        
        excess_returns = returns - risk_free_rate / 252
        downside_returns = returns[returns < 0]
        
        if len(downside_returns) == 0:
            return float('inf')
        
        downside_std = np.std(downside_returns)
        return np.mean(excess_returns) / downside_std * np.sqrt(252)
    
    def calculate_calmar_ratio(self, returns: np.ndarray, equity_curve: np.ndarray) -> float:
        """Calculate Calmar Ratio (return / max drawdown)."""
        max_dd, _ = self.calculate_drawdown(equity_curve)
        
        if max_dd == 0:
            return 0.0
        
        annual_return = np.mean(returns) * 252
        return annual_return / abs(max_dd)
    
    def risk_metrics_summary(
        self, 
        positions: Dict[str, float],
        returns_dict: Dict[str, np.ndarray],
        equity_curve: np.ndarray,
        current_price: float = 100.0
    ) -> Dict[str, Any]:
        """Generate comprehensive risk metrics summary."""
        
        # Combine all returns
        all_returns = np.concatenate(list(returns_dict.values())) if returns_dict else np.array([])
        
        return {
            'timestamp': datetime.now().isoformat(),
            'var_95': self.calculate_var(all_returns) if len(all_returns) > 0 else 0,
            'cvar_95': self.calculate_cvar(all_returns) if len(all_returns) > 0 else 0,
            'portfolio_var': self.portfolio_var(positions, returns_dict),
            'concentration_risk': self.calculate_concentration_risk(positions),
            'max_drawdown': self.calculate_drawdown(equity_curve)[0],
            'current_drawdown': self.calculate_drawdown(equity_curve)[1],
            'sharpe_ratio': self.calculate_sharpe_ratio(all_returns) if len(all_returns) > 0 else 0,
            'sortino_ratio': self.calculate_sortino_ratio(all_returns) if len(all_returns) > 0 else 0,
            'calmar_ratio': self.calculate_calmar_ratio(all_returns, equity_curve) if len(all_returns) > 0 else 0,
            'num_positions': len(positions),
            'total_exposure': sum(abs(v) for v in positions.values())
        }
