"""Learn optimal strategies from trading history and backtesting results."""

from __future__ import annotations

import logging
import json
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StrategyParams:
    """Parameters learned for a strategy."""
    name: str
    parameters: Dict[str, float]
    performance: Dict[str, float]  # metrics like win_rate, profit_factor, sharpe
    confidence: float  # 0-1, how confident we are in these params
    samples: int  # number of trades used to learn
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass(frozen=True)
class HybridStrategy:
    """A new hybrid strategy learned from multiple strategies."""
    name: str
    base_strategies: List[str]  # e.g., ['mean_reversion_rsi', 'macd_volume_momentum']
    weights: Dict[str, float]  # allocation to each base strategy
    meta_parameters: Dict[str, float]  # parameters for the hybrid logic
    expected_metrics: Dict[str, float]  # predicted performance
    learning_timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def get_combined_parameters(self, strategy_params: Dict[str, StrategyParams]) -> Dict[str, float]:
        """Combine parameters from base strategies using learned weights."""
        combined = {}
        
        for strat_name, weight in self.weights.items():
            if strat_name in strategy_params:
                params = strategy_params[strat_name].parameters
                for key, val in params.items():
                    combined_key = f"{strat_name}_{key}"
                    combined[combined_key] = val
        
        combined.update(self.meta_parameters)
        return combined


class StrategyLearner:
    """Learn optimal parameters and combinations from strategy performance."""
    
    def __init__(self, cache_dir: str = ".cache/strategy_learning"):
        """Initialize strategy learner."""
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.learned_strategies: Dict[str, StrategyParams] = {}
        self.hybrid_strategies: Dict[str, HybridStrategy] = {}
        
        self._load_cached()
        logger.info(f"StrategyLearner initialized with {len(self.learned_strategies)} learned strategies")
    
    def learn_from_backtest(
        self,
        strategy_name: str,
        parameters: Dict[str, float],
        backtest_results: Dict[str, Any],
    ) -> Optional[StrategyParams]:
        """
        Learn optimal parameters from a backtest result.
        
        Args:
            strategy_name: Name of the strategy
            parameters: Parameters used in backtest
            backtest_results: Backtest results with metrics
            
        Returns:
            StrategyParams if learning was successful
        """
        try:
            # Extract performance metrics
            metrics = {
                'sharpe_ratio': float(backtest_results.get('sharpe_ratio', 0)),
                'max_drawdown': float(backtest_results.get('max_drawdown', 0)),
                'win_rate': float(backtest_results.get('win_rate', 0)),
                'profit_factor': float(backtest_results.get('profit_factor', 1.0)),
                'total_return': float(backtest_results.get('total_return', 0)),
                'num_trades': int(backtest_results.get('num_trades', 0)),
            }
            
            # Calculate confidence based on number of trades
            # Need at least 10 trades for high confidence
            confidence = min(1.0, max(0.1, metrics['num_trades'] / 30))
            
            # Create learned strategy
            strat_params = StrategyParams(
                name=f"{strategy_name}_learned",
                parameters=parameters,
                performance=metrics,
                confidence=confidence,
                samples=metrics['num_trades'],
            )
            
            self.learned_strategies[strat_params.name] = strat_params
            logger.info(
                f"Learned {strategy_name}: sharpe={metrics['sharpe_ratio']:.2f}, "
                f"win_rate={metrics['win_rate']:.1%}, confidence={confidence:.1%}"
            )
            
            return strat_params
            
        except Exception as e:
            logger.error(f"Error learning from backtest: {e}")
            return None
    
    def learn_from_performance_history(
        self,
        strategy_name: str,
        trades: List[Dict[str, Any]],
        initial_params: Dict[str, float],
    ) -> Optional[StrategyParams]:
        """
        Learn from actual trading performance history.
        
        Args:
            strategy_name: Name of the strategy
            trades: List of completed trades
            initial_params: Initial parameters
            
        Returns:
            StrategyParams with optimized parameters
        """
        if not trades or len(trades) < 5:
            logger.warning(f"Not enough trades ({len(trades)}) to learn from {strategy_name}")
            return None
        
        try:
            # Calculate metrics from trades
            profits = []
            losses = []
            
            for trade in trades:
                entry = float(trade.get('entry_price', 0))
                exit_val = float(trade.get('exit_price', 0))
                
                if entry > 0:
                    pnl_pct = ((exit_val - entry) / entry) * 100
                    if pnl_pct > 0:
                        profits.append(pnl_pct)
                    else:
                        losses.append(abs(pnl_pct))
            
            num_trades = len(trades)
            num_wins = len(profits)
            num_losses = len(losses)
            
            win_rate = num_wins / num_trades if num_trades > 0 else 0
            avg_win = np.mean(profits) if profits else 0
            avg_loss = np.mean(losses) if losses else 0
            profit_factor = (num_wins * avg_win) / max(num_losses * avg_loss, 0.01) if num_losses > 0 else (num_wins * avg_win) if num_wins > 0 else 1.0
            total_return = sum(profits) - sum(losses)
            
            metrics = {
                'win_rate': float(win_rate),
                'profit_factor': float(profit_factor),
                'total_return': float(total_return),
                'avg_win': float(avg_win),
                'avg_loss': float(avg_loss),
                'num_trades': int(num_trades),
                'sharpe_ratio': 0.0,  # Would need equity curve
                'max_drawdown': 0.0,  # Would need equity curve
            }
            
            # Suggest parameter adjustments based on performance
            optimized_params = self._suggest_parameter_adjustments(initial_params, metrics)
            
            confidence = min(1.0, num_trades / 30)  # More trades = higher confidence
            
            strat_params = StrategyParams(
                name=f"{strategy_name}_optimized",
                parameters=optimized_params,
                performance=metrics,
                confidence=confidence,
                samples=num_trades,
            )
            
            self.learned_strategies[strat_params.name] = strat_params
            logger.info(
                f"Learned {strategy_name} from {num_trades} trades: "
                f"win_rate={win_rate:.1%}, profit_factor={profit_factor:.2f}"
            )
            
            return strat_params
            
        except Exception as e:
            logger.error(f"Error learning from performance history: {e}")
            return None
    
    def _suggest_parameter_adjustments(
        self,
        current_params: Dict[str, float],
        metrics: Dict[str, float],
    ) -> Dict[str, float]:
        """
        Suggest parameter adjustments based on performance metrics.
        
        This is a heuristic approach - adjust parameters that likely affected the outcome.
        """
        adjusted = current_params.copy()
        
        win_rate = metrics.get('win_rate', 0.5)
        profit_factor = metrics.get('profit_factor', 1.0)
        num_trades = metrics.get('num_trades', 10)
        
        # If win rate is too low, we're over-trading
        # Increase thresholds to be more selective
        if win_rate < 0.4:
            # Increase any threshold parameters
            for key in list(adjusted.keys()):
                if 'threshold' in key.lower() or 'level' in key.lower():
                    adjusted[key] *= 1.1  # 10% more selective
        
        # If profit factor is low, reduce position size or increase stops
        if profit_factor < 1.0:
            # Increase stop loss (become more defensive)
            for key in list(adjusted.keys()):
                if 'stop' in key.lower() or 'loss' in key.lower():
                    adjusted[key] *= 1.2  # Tighter stops
        
        # If we're not trading enough, loosen requirements
        if num_trades < 5:
            for key in list(adjusted.keys()):
                if 'threshold' in key.lower():
                    adjusted[key] *= 0.9  # 10% less selective
        
        return adjusted
    
    def build_hybrid_strategy(
        self,
        name: str,
        base_strategies: List[str],
        strategy_params: Dict[str, StrategyParams],
        weight_by: str = 'sharpe_ratio',
    ) -> Optional[HybridStrategy]:
        """
        Build a hybrid strategy from multiple learned strategies.
        
        Args:
            name: Name for the new hybrid strategy
            base_strategies: List of learned strategy names to combine
            strategy_params: Dict mapping strategy names to their StrategyParams
            weight_by: Metric to use for weighting ('sharpe_ratio', 'profit_factor', 'win_rate')
            
        Returns:
            HybridStrategy if successful
        """
        # Check we have all strategies
        available_strats = {s: strategy_params[s] for s in base_strategies if s in strategy_params}
        
        if len(available_strats) != len(base_strategies):
            missing = set(base_strategies) - set(available_strats.keys())
            logger.warning(f"Missing strategies: {missing}")
            return None
        
        try:
            # Calculate weights based on selected metric
            metrics = {}
            for strat_name, params in available_strats.items():
                metric_val = params.performance.get(weight_by, 1.0)
                metrics[strat_name] = float(metric_val)
            
            # Normalize metrics to 0-1
            metric_values = list(metrics.values())
            min_val = min(metric_values)
            max_val = max(metric_values)
            
            if max_val > min_val:
                normalized = {k: (v - min_val) / (max_val - min_val) for k, v in metrics.items()}
            else:
                normalized = {k: 1.0 / len(metrics) for k in metrics}
            
            # Convert to weights (sum to 1)
            total = sum(normalized.values())
            weights = {k: v / total for k, v in normalized.items()}
            
            # Meta parameters: how to combine the strategies
            meta_params = {
                'weight_by_metric': weight_by,
                'rebalance_frequency': 5.0,  # rebalance every 5 bars
                'volatility_adjustment': 1.0,  # scale by realized volatility
                'drawdown_defense': 0.1,  # reduce position if drawdown exceeds 10%
            }
            
            # Predict performance as weighted average
            expected_metrics = {}
            for metric_key in ['sharpe_ratio', 'win_rate', 'profit_factor', 'total_return']:
                weighted_sum = sum(
                    available_strats[s].performance.get(metric_key, 0) * weights[s]
                    for s in base_strategies
                )
                expected_metrics[metric_key] = weighted_sum
            
            hybrid = HybridStrategy(
                name=name,
                base_strategies=base_strategies,
                weights=weights,
                meta_parameters=meta_params,
                expected_metrics=expected_metrics,
            )
            
            self.hybrid_strategies[name] = hybrid
            logger.info(
                f"Created hybrid strategy '{name}' combining {len(base_strategies)} strategies. "
                f"Expected sharpe={expected_metrics.get('sharpe_ratio', 0):.2f}, "
                f"win_rate={expected_metrics.get('win_rate', 0):.1%}"
            )
            
            return hybrid
            
        except Exception as e:
            logger.error(f"Error building hybrid strategy: {e}")
            return None
    
    def get_learned_strategies(self) -> Dict[str, StrategyParams]:
        """Get all learned strategies."""
        return self.learned_strategies.copy()
    
    def get_hybrid_strategies(self) -> Dict[str, HybridStrategy]:
        """Get all hybrid strategies."""
        return self.hybrid_strategies.copy()
    
    def get_top_strategies(self, top_n: int = 5, metric: str = 'sharpe_ratio') -> List[StrategyParams]:
        """
        Get top performing learned strategies.
        
        Args:
            top_n: Number of top strategies to return
            metric: Metric to rank by
            
        Returns:
            List of StrategyParams sorted by metric
        """
        strategies = list(self.learned_strategies.values())
        strategies.sort(
            key=lambda s: s.performance.get(metric, 0) * s.confidence,
            reverse=True
        )
        return strategies[:top_n]
    
    def save(self) -> None:
        """Save learned strategies to disk."""
        # Save learned strategies
        learned_path = self.cache_dir / 'learned_strategies.json'
        learned_data = {
            name: {
                'parameters': params.parameters,
                'performance': params.performance,
                'confidence': params.confidence,
                'samples': params.samples,
                'created_at': params.created_at,
            }
            for name, params in self.learned_strategies.items()
        }
        
        with open(learned_path, 'w') as f:
            json.dump(learned_data, f, indent=2)
        
        # Save hybrid strategies
        hybrid_path = self.cache_dir / 'hybrid_strategies.json'
        hybrid_data = {
            name: {
                'base_strategies': strat.base_strategies,
                'weights': strat.weights,
                'meta_parameters': strat.meta_parameters,
                'expected_metrics': strat.expected_metrics,
                'learning_timestamp': strat.learning_timestamp,
            }
            for name, strat in self.hybrid_strategies.items()
        }
        
        with open(hybrid_path, 'w') as f:
            json.dump(hybrid_data, f, indent=2)
        
        logger.info(f"Saved {len(self.learned_strategies)} learned and {len(self.hybrid_strategies)} hybrid strategies")
    
    def _load_cached(self) -> None:
        """Load cached learned strategies from disk."""
        try:
            learned_path = self.cache_dir / 'learned_strategies.json'
            if learned_path.exists():
                with open(learned_path) as f:
                    data = json.load(f)
                    for name, info in data.items():
                        self.learned_strategies[name] = StrategyParams(
                            name=name,
                            parameters=info.get('parameters', {}),
                            performance=info.get('performance', {}),
                            confidence=float(info.get('confidence', 0.5)),
                            samples=int(info.get('samples', 0)),
                            created_at=info.get('created_at', datetime.now().isoformat()),
                        )
            
            hybrid_path = self.cache_dir / 'hybrid_strategies.json'
            if hybrid_path.exists():
                with open(hybrid_path) as f:
                    data = json.load(f)
                    for name, info in data.items():
                        self.hybrid_strategies[name] = HybridStrategy(
                            name=name,
                            base_strategies=info.get('base_strategies', []),
                            weights=info.get('weights', {}),
                            meta_parameters=info.get('meta_parameters', {}),
                            expected_metrics=info.get('expected_metrics', {}),
                            learning_timestamp=info.get('learning_timestamp', datetime.now().isoformat()),
                        )
        except Exception as e:
            logger.warning(f"Error loading cached strategies: {e}")


if __name__ == "__main__":
    # Example usage
    learner = StrategyLearner()
    
    # Learn from backtest results
    backtest_results = {
        'sharpe_ratio': 1.5,
        'max_drawdown': -0.08,
        'win_rate': 0.55,
        'profit_factor': 1.8,
        'total_return': 0.25,
        'num_trades': 50,
    }
    
    params = learner.learn_from_backtest(
        'mean_reversion_rsi',
        {'rsi_threshold': 30, 'lookback': 14},
        backtest_results
    )
    
    if params:
        print(f"Learned: {params}")
