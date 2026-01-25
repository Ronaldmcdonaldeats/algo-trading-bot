"""Performance Attribution and Analysis"""

from typing import Dict, List, Tuple
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from .manager import PortfolioManager


class PerformanceAnalytics:
    """Analyze portfolio performance and attribute returns"""
    
    def __init__(self, portfolio: PortfolioManager):
        self.portfolio = portfolio
    
    def calculate_returns(self) -> pd.Series:
        """Calculate daily returns from portfolio history"""
        history_df = self.portfolio.get_history_df()
        
        if history_df.empty:
            return pd.Series()
        
        returns = history_df["total_value"].pct_change()
        return returns
    
    def calculate_cumulative_returns(self) -> float:
        """Calculate total cumulative return %"""
        if self.portfolio.total_value == 0:
            return 0.0
        
        return (
            (self.portfolio.total_value - self.portfolio.initial_capital) 
            / self.portfolio.initial_capital
        ) * 100
    
    def calculate_sharpe_ratio(self, risk_free_rate: float = 0.02) -> float:
        """Calculate Sharpe ratio (annualized)"""
        returns = self.calculate_returns()
        
        if len(returns) < 2:
            return 0.0
        
        excess_returns = returns - risk_free_rate / 252
        sharpe = excess_returns.mean() / excess_returns.std() * np.sqrt(252)
        
        return sharpe if not np.isnan(sharpe) else 0.0
    
    def calculate_sortino_ratio(self, target_return: float = 0.0) -> float:
        """Calculate Sortino ratio (downside risk only)"""
        returns = self.calculate_returns()
        
        if len(returns) < 2:
            return 0.0
        
        excess = returns - target_return / 252
        downside = excess[excess < 0].std() * np.sqrt(252)
        
        if downside == 0:
            return 0.0
        
        sortino = (returns.mean() * 252 - target_return) / downside
        return sortino if not np.isnan(sortino) else 0.0
    
    def calculate_calmar_ratio(self) -> float:
        """Calculate Calmar ratio (return / max drawdown)"""
        history_df = self.portfolio.get_history_df()
        
        if history_df.empty or len(history_df) < 2:
            return 0.0
        
        values = history_df["total_value"].values
        annual_return = (
            (values[-1] - values[0]) / values[0] * 252 / len(values)
        )
        
        max_dd = self.calculate_max_drawdown()
        
        if max_dd == 0:
            return 0.0
        
        calmar = annual_return / abs(max_dd)
        return calmar if not np.isnan(calmar) else 0.0
    
    def calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown"""
        history_df = self.portfolio.get_history_df()
        
        if history_df.empty:
            return 0.0
        
        values = history_df["total_value"].values
        running_max = np.maximum.accumulate(values)
        drawdown = (values - running_max) / running_max
        
        return drawdown.min()
    
    def calculate_current_drawdown(self) -> float:
        """Calculate current drawdown from peak"""
        history_df = self.portfolio.get_history_df()
        
        if history_df.empty:
            return 0.0
        
        current = self.portfolio.total_value
        peak = history_df["total_value"].max()
        
        if peak == 0:
            return 0.0
        
        return (current - peak) / peak
    
    def calculate_win_rate(self) -> float:
        """Calculate % of profitable trades"""
        realized_trades = [
            t for t in self.portfolio.trades 
            if t["type"] == "SELL"
        ]
        
        if not realized_trades:
            return 0.0
        
        winners = sum(
            1 for t in realized_trades 
            if t.get("realized_pnl", 0) > 0
        )
        
        return (winners / len(realized_trades)) * 100
    
    def calculate_profit_factor(self) -> float:
        """Calculate profit factor (gross profit / gross loss)"""
        realized_trades = [
            t for t in self.portfolio.trades 
            if t["type"] == "SELL"
        ]
        
        if not realized_trades:
            return 0.0
        
        gross_profit = sum(
            t.get("realized_pnl", 0) 
            for t in realized_trades 
            if t.get("realized_pnl", 0) > 0
        )
        
        gross_loss = sum(
            abs(t.get("realized_pnl", 0))
            for t in realized_trades
            if t.get("realized_pnl", 0) < 0
        )
        
        if gross_loss == 0:
            return float('inf') if gross_profit > 0 else 0.0
        
        return gross_profit / gross_loss
    
    def get_return_distribution(self) -> Dict[str, float]:
        """Get return distribution stats"""
        returns = self.calculate_returns()
        
        if returns.empty:
            return {}
        
        return {
            "mean": returns.mean() * 252,
            "std": returns.std() * np.sqrt(252),
            "skewness": returns.skew(),
            "kurtosis": returns.kurtosis(),
            "min_daily": returns.min() * 100,
            "max_daily": returns.max() * 100,
            "median": returns.median() * 252
        }
    
    def attribution_by_trade(self) -> List[Dict]:
        """Attribute returns by individual trade"""
        attribution = []
        
        for trade in self.portfolio.trades:
            if trade["type"] == "SELL":
                attr = {
                    "symbol": trade["symbol"],
                    "entry_price": self.portfolio.get_position(trade["symbol"]).entry_price 
                        if trade["symbol"] in self.portfolio.positions else trade["price"],
                    "exit_price": trade["price"],
                    "quantity": trade["quantity"],
                    "realized_pnl": trade.get("realized_pnl", 0),
                    "return_pct": (
                        (trade["price"] - self.portfolio.get_position(trade["symbol"]).entry_price) 
                        / self.portfolio.get_position(trade["symbol"]).entry_price * 100
                    ) if trade["symbol"] in self.portfolio.positions else 0,
                    "timestamp": trade["timestamp"]
                }
                attribution.append(attr)
        
        return sorted(attribution, key=lambda x: x["realized_pnl"], reverse=True)
    
    def get_performance_summary(self) -> Dict:
        """Get comprehensive performance summary"""
        return {
            "cumulative_return_pct": self.calculate_cumulative_returns(),
            "annual_return_pct": self.calculate_cumulative_returns() / max(1, self.portfolio.avg_holding_days / 365),
            "sharpe_ratio": self.calculate_sharpe_ratio(),
            "sortino_ratio": self.calculate_sortino_ratio(),
            "calmar_ratio": self.calculate_calmar_ratio(),
            "max_drawdown_pct": self.calculate_max_drawdown() * 100,
            "current_drawdown_pct": self.calculate_current_drawdown() * 100,
            "win_rate_pct": self.calculate_win_rate(),
            "profit_factor": self.calculate_profit_factor(),
            "total_trades": len([t for t in self.portfolio.trades if t["type"] == "SELL"]),
            "avg_trade_return": (
                np.mean([t.get("realized_pnl", 0) for t in self.portfolio.trades if t["type"] == "SELL"])
                if any(t["type"] == "SELL" for t in self.portfolio.trades) else 0
            ),
            "largest_win": (
                max([t.get("realized_pnl", 0) for t in self.portfolio.trades if t["type"] == "SELL"])
                if any(t["type"] == "SELL" for t in self.portfolio.trades) else 0
            ),
            "largest_loss": (
                min([t.get("realized_pnl", 0) for t in self.portfolio.trades if t["type"] == "SELL"])
                if any(t["type"] == "SELL" for t in self.portfolio.trades) else 0
            ),
            "return_distribution": self.get_return_distribution(),
            "top_trades": self.attribution_by_trade()[:10]
        }
