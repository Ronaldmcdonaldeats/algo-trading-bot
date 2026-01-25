"""Portfolio Rebalancing Engine"""

from typing import Dict, List, Tuple, Optional
import numpy as np
import pandas as pd
from dataclasses import dataclass
from .manager import PortfolioManager


@dataclass
class RebalanceAction:
    """Action to rebalance portfolio"""
    symbol: str
    action: str  # "BUY", "SELL"
    quantity: float
    current_weight: float
    target_weight: float
    value_change: float


class PortfolioRebalancer:
    """Rebalance portfolio to target allocations"""
    
    def __init__(self, portfolio: PortfolioManager, tolerance: float = 0.02):
        """
        Args:
            portfolio: PortfolioManager instance
            tolerance: Rebalance threshold (default 2%)
        """
        self.portfolio = portfolio
        self.tolerance = tolerance
        self.target_allocations: Dict[str, float] = {}
        self.rebalance_history: List[Dict] = []
    
    def set_target_allocation(self, allocations: Dict[str, float]) -> None:
        """Set target allocations for symbols
        
        Args:
            allocations: Dict of {symbol: target_weight_pct}
                        Must sum to <= 100%
        """
        if sum(allocations.values()) > 100:
            raise ValueError("Allocations sum to >100%")
        
        self.target_allocations = allocations
    
    def get_rebalance_actions(self) -> List[RebalanceAction]:
        """Calculate rebalancing actions needed"""
        actions = []
        total = self.portfolio.total_value
        
        if total == 0:
            return actions
        
        # Check each target allocation
        for symbol, target_pct in self.target_allocations.items():
            target_weight = target_pct / 100.0
            target_value = total * target_weight
            
            current_pos = self.portfolio.get_position(symbol)
            current_value = current_pos.current_value if current_pos else 0.0
            current_weight = current_value / total if total > 0 else 0.0
            
            # Check if rebalance needed
            diff = abs(current_weight - target_weight)
            if diff > self.tolerance:
                value_diff = target_value - current_value
                
                if value_diff > 0:
                    # Need to buy
                    if current_pos:
                        qty = (target_value - current_value) / current_pos.current_price
                    else:
                        # Can't buy if we don't have current price
                        continue
                    
                    actions.append(RebalanceAction(
                        symbol=symbol,
                        action="BUY",
                        quantity=qty,
                        current_weight=current_weight * 100,
                        target_weight=target_weight * 100,
                        value_change=value_diff
                    ))
                else:
                    # Need to sell
                    if current_pos:
                        qty = abs(value_diff) / current_pos.current_price
                        actions.append(RebalanceAction(
                            symbol=symbol,
                            action="SELL",
                            quantity=qty,
                            current_weight=current_weight * 100,
                            target_weight=target_weight * 100,
                            value_change=value_diff
                        ))
        
        # Check for positions not in target allocation
        for symbol, pos in self.portfolio.positions.items():
            if symbol not in self.target_allocations:
                weight = pos.current_value / total if total > 0 else 0.0
                if weight > self.tolerance:
                    # Sell off excess
                    actions.append(RebalanceAction(
                        symbol=symbol,
                        action="SELL",
                        quantity=pos.quantity,
                        current_weight=weight * 100,
                        target_weight=0.0,
                        value_change=-pos.current_value
                    ))
        
        return actions
    
    def execute_rebalance(self, dry_run: bool = False) -> Tuple[int, int]:
        """Execute rebalancing
        
        Args:
            dry_run: If True, don't actually execute
            
        Returns:
            (buys_executed, sells_executed)
        """
        actions = self.get_rebalance_actions()
        
        if not actions:
            return 0, 0
        
        buys = 0
        sells = 0
        
        for action in actions:
            try:
                if action.action == "BUY" and not dry_run:
                    self.portfolio.open_position(
                        action.symbol,
                        action.quantity,
                        self.portfolio.get_position(action.symbol).current_price
                    )
                    buys += 1
                elif action.action == "SELL" and not dry_run:
                    self.portfolio.close_position(
                        action.symbol,
                        action.quantity
                    )
                    sells += 1
            except Exception as e:
                print(f"Error executing {action.action} for {action.symbol}: {e}")
        
        self.rebalance_history.append({
            "timestamp": pd.Timestamp.now(),
            "buys": buys,
            "sells": sells,
            "actions": [
                {
                    "symbol": a.symbol,
                    "action": a.action,
                    "quantity": a.quantity
                }
                for a in actions
            ]
        })
        
        return buys, sells
    
    def schedule_rebalance(self, frequency: str = "monthly") -> bool:
        """Check if rebalance is due based on frequency
        
        Args:
            frequency: "daily", "weekly", "monthly", "quarterly"
            
        Returns:
            True if rebalance is due
        """
        if not self.rebalance_history:
            return True
        
        last_rebalance = self.rebalance_history[-1]["timestamp"]
        time_since = pd.Timestamp.now() - last_rebalance
        
        if frequency == "daily":
            return time_since.days >= 1
        elif frequency == "weekly":
            return time_since.days >= 7
        elif frequency == "monthly":
            return time_since.days >= 30
        elif frequency == "quarterly":
            return time_since.days >= 90
        
        return False
    
    def get_rebalance_report(self) -> Dict:
        """Get rebalancing summary"""
        actions = self.get_rebalance_actions()
        
        return {
            "needs_rebalance": len(actions) > 0,
            "num_actions": len(actions),
            "actions": [
                {
                    "symbol": a.symbol,
                    "action": a.action,
                    "quantity": a.quantity,
                    "current_weight_pct": a.current_weight,
                    "target_weight_pct": a.target_weight,
                    "drift_pct": a.target_weight - a.current_weight
                }
                for a in actions
            ],
            "rebalance_history": self.rebalance_history[-10:]  # Last 10
        }


class EfficientFrontier:
    """Calculate efficient frontier and optimal portfolios"""
    
    def __init__(self, returns_df: pd.DataFrame, risk_free_rate: float = 0.02):
        """
        Args:
            returns_df: DataFrame of asset returns (dates x assets)
            risk_free_rate: Annual risk-free rate
        """
        self.returns = returns_df
        self.risk_free_rate = risk_free_rate
        self.cov_matrix = returns_df.cov() * 252  # Annualized
        self.mean_returns = returns_df.mean() * 252
        
    def generate_random_portfolios(self, n: int = 10000) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Generate random portfolio weights and calculate metrics
        
        Returns:
            (returns, volatilities, sharpe_ratios)
        """
        results = np.zeros((3, n))
        num_assets = len(self.mean_returns)
        
        for i in range(n):
            weights = np.random.random(num_assets)
            weights /= np.sum(weights)
            
            port_return = np.sum(self.mean_returns * weights)
            port_vol = np.sqrt(np.dot(weights.T, np.dot(self.cov_matrix, weights)))
            sharpe = (port_return - self.risk_free_rate) / port_vol if port_vol > 0 else 0
            
            results[0, i] = port_return
            results[1, i] = port_vol
            results[2, i] = sharpe
        
        return results[0], results[1], results[2]
    
    def min_variance_portfolio(self) -> Tuple[np.ndarray, float, float]:
        """Find minimum variance portfolio
        
        Returns:
            (weights, return, volatility)
        """
        num_assets = len(self.mean_returns)
        ones = np.ones(num_assets)
        
        # Solve: w = cov^-1 * 1 / (1^T * cov^-1 * 1)
        cov_inv = np.linalg.inv(self.cov_matrix)
        weights = cov_inv @ ones / (ones @ cov_inv @ ones)
        
        port_return = np.sum(self.mean_returns * weights)
        port_vol = np.sqrt(weights @ self.cov_matrix @ weights)
        
        return weights, port_return, port_vol
    
    def max_sharpe_portfolio(self) -> Tuple[np.ndarray, float, float]:
        """Find maximum Sharpe ratio portfolio
        
        Returns:
            (weights, return, volatility)
        """
        num_assets = len(self.mean_returns)
        excess_returns = self.mean_returns - self.risk_free_rate
        
        # Solve: w = cov^-1 * excess_returns / (1^T * cov^-1 * excess_returns)
        cov_inv = np.linalg.inv(self.cov_matrix)
        weights = cov_inv @ excess_returns / (np.ones(num_assets) @ cov_inv @ excess_returns)
        
        port_return = np.sum(self.mean_returns * weights)
        port_vol = np.sqrt(weights @ self.cov_matrix @ weights)
        
        return weights, port_return, port_vol
    
    def risk_parity_portfolio(self) -> Tuple[np.ndarray, float, float]:
        """Risk parity - equal risk contribution from each asset
        
        Returns:
            (weights, return, volatility)
        """
        num_assets = len(self.mean_returns)
        
        # Risk parity: weights inversely proportional to volatilities
        vols = np.sqrt(np.diag(self.cov_matrix))
        weights = (1 / vols) / np.sum(1 / vols)
        
        port_return = np.sum(self.mean_returns * weights)
        port_vol = np.sqrt(weights @ self.cov_matrix @ weights)
        
        return weights, port_return, port_vol
