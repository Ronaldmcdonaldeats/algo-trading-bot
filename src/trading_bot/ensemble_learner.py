"""
Ensemble Learner - Combines Multiple Strategies

Learns which strategies work best over time and creates an optimal ensemble
that adapts to market conditions. Uses voting, weighting, and meta-learning
to maximize risk-adjusted returns.
"""
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)


@dataclass
class StrategyPerformance:
    """Tracks strategy performance for learning"""
    name: str
    recent_returns: List[float] = field(default_factory=list)
    recent_sharpe: List[float] = field(default_factory=list)
    win_rate: float = 0.5
    max_weight: float = 1.0
    
    def update(self, returns: float, sharpe: float, win_rate: float):
        """Update performance metrics"""
        self.recent_returns.append(returns)
        self.recent_sharpe.append(sharpe)
        self.win_rate = win_rate
        
        # Keep last 10 periods
        if len(self.recent_returns) > 10:
            self.recent_returns.pop(0)
        if len(self.recent_sharpe) > 10:
            self.recent_sharpe.pop(0)
    
    def get_score(self) -> float:
        """Calculate composite score for weighting"""
        if not self.recent_returns:
            return 0.5
        
        # Average recent returns (weighted towards recent)
        ret_score = np.mean(self.recent_returns[-3:]) if len(self.recent_returns) >= 3 else np.mean(self.recent_returns)
        
        # Win rate contribution
        win_score = self.win_rate - 0.5  # -0.5 to +0.5
        
        return max(0, ret_score + win_score * 0.1)


class EnsembleVoter:
    """Combines signals from multiple strategies via voting"""
    
    def __init__(self, voting_method: str = 'weighted'):
        """
        Initialize voter
        
        Args:
            voting_method: 'simple' (majority), 'weighted' (by performance), 'adaptive' (learns)
        """
        self.voting_method = voting_method
        self.strategy_weights: Dict[str, float] = {}
        self.strategy_scores: Dict[str, StrategyPerformance] = {}
    
    def initialize_strategies(self, strategy_names: List[str]):
        """Initialize tracking for strategies"""
        for name in strategy_names:
            self.strategy_scores[name] = StrategyPerformance(name)
            self.strategy_weights[name] = 1.0 / len(strategy_names)  # Equal initially
    
    def update_performance(self, strategy_name: str, returns: float, sharpe: float, 
                          win_rate: float):
        """Update strategy performance for learning"""
        if strategy_name in self.strategy_scores:
            self.strategy_scores[strategy_name].update(returns, sharpe, win_rate)
    
    def reweight_strategies(self, learning_rate: float = 0.1):
        """Adaptively reweight strategies based on recent performance"""
        if not self.strategy_scores:
            return
        
        # Calculate scores for all strategies
        scores = {name: perf.get_score() for name, perf in self.strategy_scores.items()}
        
        # Normalize scores to weights (softmax-like)
        scores_array = np.array(list(scores.values()))
        scores_array = np.maximum(scores_array, 0.01)  # Avoid zero weights
        
        normalized = scores_array / scores_array.sum()
        
        strategy_list = list(scores.keys())
        
        # Update weights with learning rate
        for i, strategy in enumerate(strategy_list):
            old_weight = self.strategy_weights[strategy]
            new_weight = normalized[i]
            self.strategy_weights[strategy] = old_weight * (1 - learning_rate) + new_weight * learning_rate
        
        # Normalize again to ensure they sum to 1
        total = sum(self.strategy_weights.values())
        for strategy in self.strategy_weights:
            self.strategy_weights[strategy] /= total
    
    def vote(self, signals_dict: Dict[str, int]) -> int:
        """
        Combine signals from multiple strategies
        
        Args:
            signals_dict: Dict of strategy_name -> signal (-1, 0, 1)
            
        Returns:
            Combined signal (-1, 0, 1)
        """
        if self.voting_method == 'simple':
            # Simple majority voting
            buy_votes = sum(1 for s in signals_dict.values() if s == 1)
            sell_votes = sum(1 for s in signals_dict.values() if s == -1)
            
            if buy_votes > sell_votes and buy_votes >= len(signals_dict) / 2:
                return 1
            elif sell_votes > buy_votes and sell_votes >= len(signals_dict) / 2:
                return -1
            else:
                return 0
        
        elif self.voting_method == 'weighted':
            # Weighted voting
            buy_weight = sum(self.strategy_weights.get(s, 0) for s, sig in signals_dict.items() if sig == 1)
            sell_weight = sum(self.strategy_weights.get(s, 0) for s, sig in signals_dict.items() if sig == -1)
            
            if buy_weight > sell_weight and buy_weight > 0.4:
                return 1
            elif sell_weight > buy_weight and sell_weight > 0.4:
                return -1
            else:
                return 0
        
        else:  # adaptive (same as weighted for now)
            return self.vote({'weighted' if self.voting_method == 'adaptive' else self.voting_method: 1} | signals_dict)
    
    def get_weights(self) -> Dict[str, float]:
        """Get current strategy weights"""
        return self.strategy_weights.copy()


class EnsembleBacktester:
    """Backtests ensemble strategy with learning"""
    
    def __init__(self, initial_capital: float = 100000, transaction_cost: float = 0.001,
                 reweight_period: int = 20):
        """
        Initialize ensemble backtester
        
        Args:
            initial_capital: Starting capital
            transaction_cost: Transaction cost as fraction
            reweight_period: How often to reweight strategies (days)
        """
        self.initial_capital = initial_capital
        self.transaction_cost = transaction_cost
        self.reweight_period = reweight_period
    
    def backtest_ensemble(self, df: pd.DataFrame, signals_by_strategy: Dict[str, np.ndarray],
                         symbol: str = 'Unknown') -> Tuple[float, float, float, float, List]:
        """
        Backtest ensemble with learning
        
        Args:
            df: Price data
            signals_by_strategy: Dict of strategy_name -> signal array
            symbol: Stock symbol
            
        Returns:
            total_return, annual_return, max_drawdown, sharpe_ratio, trades
        """
        voter = EnsembleVoter(voting_method='weighted')
        voter.initialize_strategies(list(signals_by_strategy.keys()))
        
        prices = df['Close'].values
        ensemble_signals = np.zeros(len(df))
        
        portfolio = np.ones(len(df)) * self.initial_capital
        position = 0
        entry_price = 0
        trades = []
        
        # Track strategy performance in windows
        window_returns = {name: [] for name in signals_by_strategy}
        window_start = 0
        
        for i in range(len(df)):
            # Get signals from all strategies
            current_signals = {
                name: signals[i] if i < len(signals) else 0
                for name, signals in signals_by_strategy.items()
            }
            
            # Reweight strategies periodically
            if i > 0 and i % self.reweight_period == 0:
                # Calculate recent performance for each strategy
                if i - self.reweight_period > 0:
                    for name in signals_by_strategy.keys():
                        recent_prices = prices[i - self.reweight_period:i]
                        recent_signals = signals_by_strategy[name][i - self.reweight_period:i]
                        
                        strategy_returns = []
                        for j, sig in enumerate(recent_signals):
                            if sig == 1 and j + 1 < len(recent_prices):
                                ret = (recent_prices[j + 1] - recent_prices[j]) / recent_prices[j]
                                strategy_returns.append(ret)
                        
                        if strategy_returns:
                            avg_ret = np.mean(strategy_returns)
                            sharpe = avg_ret / (np.std(strategy_returns) + 1e-6)
                            win_rate = len([r for r in strategy_returns if r > 0]) / len(strategy_returns)
                            voter.update_performance(name, avg_ret, sharpe, win_rate)
                
                # Reweight
                voter.reweight_strategies(learning_rate=0.1)
            
            # Get ensemble signal
            ensemble_signal = voter.vote(current_signals)
            ensemble_signals[i] = ensemble_signal
            
            # Execute trades
            if ensemble_signal == 1 and position == 0:
                position = 1
                entry_price = prices[i] * (1 + self.transaction_cost)
                trades.append({
                    'Date': df.index[i],
                    'Type': 'BUY',
                    'Price': prices[i],
                    'Portfolio': portfolio[i]
                })
            
            elif ensemble_signal == -1 and position == 1:
                position = 0
                exit_price = prices[i] * (1 - self.transaction_cost)
                ret = (exit_price - entry_price) / entry_price
                portfolio[i:] *= (1 + ret)
                trades.append({
                    'Date': df.index[i],
                    'Type': 'SELL',
                    'Price': prices[i],
                    'Return': ret,
                    'Portfolio': portfolio[i]
                })
            elif position == 1:
                portfolio[i] = self.initial_capital * (prices[i] / entry_price)
        
        # Calculate metrics
        returns = np.diff(portfolio) / portfolio[:-1]
        total_return = (portfolio[-1] - self.initial_capital) / self.initial_capital
        annual_return = (1 + total_return) ** (252 / len(df)) - 1
        
        # Drawdown
        cumulative = np.cumprod(1 + returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = -np.min(drawdown)
        
        # Sharpe Ratio
        excess_returns = returns - 0.0001
        sharpe = np.mean(excess_returns) / (np.std(excess_returns) + 1e-6) * np.sqrt(252)
        
        return total_return, annual_return, max_drawdown, sharpe, trades, voter


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    # Test ensemble voting
    voter = EnsembleVoter(voting_method='weighted')
    voter.initialize_strategies(['RSI', 'SMA', 'MACD'])
    
    # Simulate voting
    signals = {'RSI': 1, 'SMA': 1, 'MACD': 0}
    result = voter.vote(signals)
    print(f"Ensemble vote: {result} (1=BUY, 0=HOLD, -1=SELL)")
    
    # Update performance
    voter.update_performance('RSI', 0.02, 1.5, 0.6)
    voter.update_performance('SMA', -0.01, -0.5, 0.4)
    voter.update_performance('MACD', 0.01, 1.0, 0.5)
    
    voter.reweight_strategies()
    print(f"New weights: {voter.get_weights()}")
