"""Advanced Portfolio Analytics - Correlation, Beta, Diversification, Sharpe

Calculates advanced portfolio metrics:
- Correlation matrix between holdings
- Beta (market sensitivity) per position
- Diversification metrics
- Sharpe ratio improvements via rebalancing
- Efficient frontier analysis
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from pathlib import Path
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class PortfolioMetrics:
    """Portfolio performance metrics"""
    correlation_matrix: Dict[str, Dict[str, float]]
    beta_per_position: Dict[str, float]
    portfolio_beta: float
    diversification_ratio: float
    effective_assets: float
    sharpe_ratio: float
    expected_return: float
    portfolio_volatility: float
    correlation_strength: str  # "low", "moderate", "high"
    concentration: float  # 0-1, closer to 1 = concentrated
    rebalance_recommendation: str


class PortfolioAnalytics:
    """Advanced portfolio analysis and optimization"""
    
    def __init__(self, cache_dir: str = ".cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.market_return = 0.10  # Annual 10% market return
        self.risk_free_rate = 0.02  # Annual 2% risk-free rate
        
    def analyze_portfolio(self, holdings: Dict[str, float], 
                         returns_data: pd.DataFrame,
                         market_returns: Optional[pd.Series] = None) -> PortfolioMetrics:
        """Analyze portfolio correlations, beta, diversification
        
        Args:
            holdings: {symbol: quantity} or {symbol: weight}
            returns_data: DataFrame with returns for each symbol (columns = symbols)
            market_returns: Series of market returns (for beta calculation)
        """
        
        symbols = list(holdings.keys())
        weights = np.array(list(holdings.values()))
        weights = weights / weights.sum()  # Normalize to sum to 1
        
        # Calculate correlation matrix
        corr_matrix = returns_data[symbols].corr().to_dict()
        
        # Calculate beta per position
        beta_per_pos = {}
        portfolio_beta = 0.0
        
        if market_returns is not None:
            for symbol in symbols:
                beta = self._calculate_beta(returns_data[symbol], market_returns)
                beta_per_pos[symbol] = beta
                portfolio_beta += beta * weights[list(holdings.keys()).index(symbol)]
        else:
            # Use market beta of 1.0 if no market data
            for symbol in symbols:
                beta_per_pos[symbol] = 1.0
            portfolio_beta = 1.0
        
        # Diversification metrics
        diversification_ratio = self._calculate_diversification_ratio(
            returns_data[symbols], weights
        )
        effective_assets = self._calculate_effective_assets(corr_matrix)
        
        # Sharpe ratio
        portfolio_return = self._calculate_portfolio_return(returns_data[symbols], weights)
        portfolio_vol = self._calculate_portfolio_volatility(returns_data[symbols], weights)
        sharpe_ratio = (portfolio_return - self.risk_free_rate) / portfolio_vol if portfolio_vol > 0 else 0
        
        # Concentration
        concentration = float(np.sum(weights ** 2))  # Herfindahl index
        
        # Correlation strength
        avg_corr = np.mean([corr_matrix[s1][s2] for s1 in symbols for s2 in symbols if s1 != s2])
        if avg_corr < 0.3:
            corr_strength = "low"
        elif avg_corr < 0.6:
            corr_strength = "moderate"
        else:
            corr_strength = "high"
        
        # Rebalancing recommendation
        rebalance_rec = self._get_rebalance_recommendation(
            concentration, corr_strength, sharpe_ratio, len(symbols)
        )
        
        return PortfolioMetrics(
            correlation_matrix=corr_matrix,
            beta_per_position=beta_per_pos,
            portfolio_beta=portfolio_beta,
            diversification_ratio=diversification_ratio,
            effective_assets=effective_assets,
            sharpe_ratio=sharpe_ratio,
            expected_return=portfolio_return,
            portfolio_volatility=portfolio_vol,
            correlation_strength=corr_strength,
            concentration=concentration,
            rebalance_recommendation=rebalance_rec
        )
    
    def _calculate_beta(self, asset_returns: pd.Series, 
                       market_returns: pd.Series) -> float:
        """Calculate beta (systematic risk)"""
        covariance = asset_returns.cov(market_returns)
        market_variance = market_returns.var()
        return covariance / market_variance if market_variance > 0 else 1.0
    
    def _calculate_diversification_ratio(self, returns_df: pd.DataFrame, 
                                        weights: np.ndarray) -> float:
        """Diversification ratio = weighted avg volatility / portfolio volatility"""
        individual_vols = returns_df.std()
        weighted_vol = np.sum(weights * individual_vols.values)
        portfolio_vol = np.sqrt(np.dot(weights, np.dot(returns_df.cov(), weights)))
        return weighted_vol / portfolio_vol if portfolio_vol > 0 else 0
    
    def _calculate_effective_assets(self, corr_matrix: Dict) -> float:
        """Number of uncorrelated assets (diversification measure)"""
        symbols = list(corr_matrix.keys())
        if len(symbols) < 2:
            return 1.0
        
        corr_array = np.array([
            [corr_matrix[s1][s2] for s2 in symbols] for s1 in symbols
        ])
        eigenvalues = np.linalg.eigvals(corr_array)
        return np.sum(eigenvalues ** 2) / (np.sum(eigenvalues) ** 2)
    
    def _calculate_portfolio_return(self, returns_df: pd.DataFrame, 
                                   weights: np.ndarray) -> float:
        """Expected annual portfolio return"""
        return float(np.sum(weights * returns_df.mean().values)) * 252  # Annualized
    
    def _calculate_portfolio_volatility(self, returns_df: pd.DataFrame, 
                                       weights: np.ndarray) -> float:
        """Portfolio standard deviation (volatility)"""
        cov_matrix = returns_df.cov()
        return float(np.sqrt(np.dot(weights, np.dot(cov_matrix, weights)))) * np.sqrt(252)
    
    def _get_rebalance_recommendation(self, concentration: float, 
                                     corr_strength: str,
                                     sharpe_ratio: float,
                                     num_positions: int) -> str:
        """Recommend if rebalancing needed"""
        issues = []
        
        if concentration > 0.25:
            issues.append("Portfolio too concentrated")
        
        if corr_strength == "high":
            issues.append("Correlations too high - add uncorrelated assets")
        
        if sharpe_ratio < 1.0:
            issues.append("Sharpe ratio below 1.0 - optimize weights")
        
        if num_positions < 3:
            issues.append("Insufficient diversification - add more positions")
        
        if not issues:
            return "Portfolio well-diversified"
        
        return "; ".join(issues)
    
    def suggest_allocation(self, symbols: List[str], 
                          returns_data: pd.DataFrame) -> Dict[str, float]:
        """Suggest optimal portfolio weights using equal-risk-contribution"""
        
        if not symbols:
            return {}
        
        # Use inverse volatility weighting (simple but effective)
        volatilities = returns_data[symbols].std()
        inverse_vol = 1.0 / volatilities
        weights = inverse_vol / inverse_vol.sum()
        
        return {sym: float(w) for sym, w in zip(symbols, weights)}
    
    def efficient_frontier_points(self, returns_data: pd.DataFrame,
                                 num_portfolios: int = 100) -> Tuple[List[float], List[float]]:
        """Generate efficient frontier (volatility vs return)"""
        
        symbols = returns_data.columns.tolist()
        returns_list = []
        vols_list = []
        
        np.random.seed(42)
        for _ in range(num_portfolios):
            weights = np.random.dirichlet(np.ones(len(symbols)))
            ret = self._calculate_portfolio_return(returns_data, weights)
            vol = self._calculate_portfolio_volatility(returns_data, weights)
            returns_list.append(ret)
            vols_list.append(vol)
        
        return vols_list, returns_list
    
    def save_analysis(self, metrics: PortfolioMetrics, filename: str = "portfolio_metrics.json"):
        """Save analysis to JSON"""
        filepath = self.cache_dir / filename
        data = {
            'correlation_matrix': metrics.correlation_matrix,
            'beta_per_position': metrics.beta_per_position,
            'portfolio_beta': metrics.portfolio_beta,
            'diversification_ratio': metrics.diversification_ratio,
            'effective_assets': metrics.effective_assets,
            'sharpe_ratio': metrics.sharpe_ratio,
            'expected_return': metrics.expected_return,
            'portfolio_volatility': metrics.portfolio_volatility,
            'correlation_strength': metrics.correlation_strength,
            'concentration': metrics.concentration,
            'rebalance_recommendation': metrics.rebalance_recommendation,
            'timestamp': datetime.now().isoformat()
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Portfolio analysis saved to {filepath}")
        return str(filepath)
