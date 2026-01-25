"""Walk-forward backtesting with out-of-sample validation.

This module implements professional walk-forward analysis to avoid lookahead bias
and provide realistic performance estimates for trading strategies.

Walk-forward analysis:
1. Train on in-sample data
2. Test on out-of-sample data
3. Move forward and repeat

This prevents overfitting and provides realistic performance metrics.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Callable

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WalkForwardWindow:
    """Configuration for a single walk-forward window."""
    start_date: datetime
    end_date: datetime
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime
    window_num: int


@dataclass
class WalkForwardResult:
    """Results from a single walk-forward window."""
    window_num: int
    train_period: Tuple[datetime, datetime]
    test_period: Tuple[datetime, datetime]
    train_metrics: Dict
    test_metrics: Dict
    parameter_set: Dict  # Best parameters found in training
    out_of_sample_sharpe: float
    out_of_sample_returns: float
    out_of_sample_max_dd: float
    out_of_sample_win_rate: float
    parameter_stability: float  # How stable parameters are across windows


@dataclass
class WalkForwardAnalysis:
    """Complete walk-forward analysis results."""
    windows: List[WalkForwardResult] = field(default_factory=list)
    overall_metrics: Dict = field(default_factory=dict)
    parameter_stability: float = 0.0
    overfitting_score: float = 0.0  # 0-1: how much overfitting detected
    out_of_sample_sharpe: float = 0.0
    out_of_sample_returns: float = 0.0
    recommendation: str = "NEUTRAL"  # BUY, HOLD, SELL


class WalkForwardOptimizer:
    """Implements walk-forward analysis for strategy optimization."""
    
    def __init__(
        self,
        total_days: int = 252,
        train_pct: float = 0.7,
        step_days: int = 20,
        min_window_days: int = 50
    ):
        """Initialize walk-forward optimizer.
        
        Args:
            total_days: Total trading days to analyze
            train_pct: Percentage of each window for training (0-1)
            step_days: Days to move forward each iteration
            min_window_days: Minimum days required for training/testing
        """
        self.total_days = total_days
        self.train_pct = train_pct
        self.step_days = step_days
        self.min_window_days = min_window_days
    
    def create_windows(
        self,
        data: pd.DataFrame,
        lookback_days: int = 252
    ) -> List[WalkForwardWindow]:
        """Create walk-forward windows from data.
        
        Args:
            data: Price data with datetime index
            lookback_days: Days for full analysis window
        
        Returns:
            List of WalkForwardWindow configurations
        """
        if len(data) < lookback_days:
            logger.warning(f"Data length {len(data)} < lookback {lookback_days}")
            return []
        
        windows = []
        end_idx = len(data)
        start_idx = max(0, end_idx - lookback_days)
        
        window_size = int((end_idx - start_idx) * self.train_pct)
        train_size = int(window_size * 0.8)
        test_size = window_size - train_size
        
        window_num = 0
        current_idx = start_idx
        
        while current_idx + window_size + test_size <= end_idx:
            train_start_idx = current_idx
            train_end_idx = train_start_idx + train_size
            test_start_idx = train_end_idx
            test_end_idx = test_start_idx + test_size
            
            # Skip small windows
            if (train_end_idx - train_start_idx) < self.min_window_days:
                current_idx += self.step_days
                continue
            
            window = WalkForwardWindow(
                start_date=data.index[train_start_idx],
                end_date=data.index[test_end_idx - 1],
                train_start=data.index[train_start_idx],
                train_end=data.index[train_end_idx - 1],
                test_start=data.index[test_start_idx],
                test_end=data.index[test_end_idx - 1],
                window_num=window_num
            )
            
            windows.append(window)
            window_num += 1
            current_idx += self.step_days
        
        logger.info(f"Created {len(windows)} walk-forward windows")
        return windows
    
    @staticmethod
    def split_data_by_window(
        data: pd.DataFrame,
        window: WalkForwardWindow
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Split data into train and test sets for a window.
        
        Args:
            data: Full dataset
            window: WalkForwardWindow configuration
        
        Returns:
            (train_data, test_data) tuple
        """
        train_data = data[(data.index >= window.train_start) & 
                         (data.index <= window.train_end)]
        test_data = data[(data.index >= window.test_start) & 
                        (data.index <= window.test_end)]
        
        return train_data, test_data


class WalkForwardBacktester:
    """Backtester that uses walk-forward analysis."""
    
    def __init__(self, initial_capital: float = 100000):
        self.initial_capital = initial_capital
        self.optimizer = WalkForwardOptimizer()
    
    def run_walk_forward_analysis(
        self,
        data: pd.DataFrame,
        strategy_func: Callable,
        param_ranges: Dict[str, Tuple[float, float]],
        optimization_metric: str = "sharpe_ratio"
    ) -> WalkForwardAnalysis:
        """Run complete walk-forward analysis.
        
        Args:
            data: Price data with datetime index
            strategy_func: Function(data, params) -> signals
            param_ranges: Dict of parameter ranges for optimization
            optimization_metric: Metric to optimize ("sharpe_ratio", "returns", "win_rate")
        
        Returns:
            WalkForwardAnalysis with complete results
        """
        
        windows = self.optimizer.create_windows(data)
        if not windows:
            logger.error("No valid windows created")
            return WalkForwardAnalysis()
        
        results = []
        all_test_metrics = []
        all_parameters = []
        
        for window in windows:
            logger.info(f"Processing window {window.window_num + 1}/{len(windows)}")
            
            # Split data
            train_data, test_data = self.optimizer.split_data_by_window(data, window)
            
            if len(train_data) < 20 or len(test_data) < 10:
                logger.warning(f"Insufficient data for window {window.window_num}")
                continue
            
            # Optimize on training data
            best_params = self._optimize_parameters(
                train_data,
                strategy_func,
                param_ranges,
                optimization_metric
            )
            all_parameters.append(best_params)
            
            # Evaluate on test data (out-of-sample)
            train_metrics = self._evaluate_strategy(
                train_data,
                strategy_func,
                best_params
            )
            
            test_metrics = self._evaluate_strategy(
                test_data,
                strategy_func,
                best_params
            )
            all_test_metrics.append(test_metrics)
            
            # Create result
            result = WalkForwardResult(
                window_num=window.window_num,
                train_period=(window.train_start, window.train_end),
                test_period=(window.test_start, window.test_end),
                train_metrics=train_metrics,
                test_metrics=test_metrics,
                parameter_set=best_params,
                out_of_sample_sharpe=test_metrics.get("sharpe_ratio", 0.0),
                out_of_sample_returns=test_metrics.get("total_return", 0.0),
                out_of_sample_max_dd=test_metrics.get("max_drawdown", 0.0),
                out_of_sample_win_rate=test_metrics.get("win_rate", 0.0),
                parameter_stability=self._calculate_parameter_stability(
                    best_params,
                    all_parameters[:-1] if len(all_parameters) > 1 else []
                )
            )
            
            results.append(result)
        
        # Calculate overall metrics
        analysis = self._create_analysis_summary(results, all_test_metrics)
        analysis.windows = results
        
        return analysis
    
    def _optimize_parameters(
        self,
        data: pd.DataFrame,
        strategy_func: Callable,
        param_ranges: Dict[str, Tuple[float, float]],
        metric: str
    ) -> Dict:
        """Optimize parameters on training data."""
        # Simple grid search (in production, use Bayesian optimization)
        best_params = None
        best_score = -np.inf
        
        # Generate parameter combinations
        for params in self._generate_param_grid(param_ranges, samples=10):
            metrics = self._evaluate_strategy(data, strategy_func, params)
            score = metrics.get(metric, 0.0)
            
            if score > best_score:
                best_score = score
                best_params = params
        
        return best_params or list(param_ranges.keys())[0]
    
    def _evaluate_strategy(
        self,
        data: pd.DataFrame,
        strategy_func: Callable,
        params: Dict
    ) -> Dict:
        """Evaluate strategy and return metrics."""
        try:
            signals = strategy_func(data, params)
            
            # Calculate returns
            if 'Close' in data.columns:
                close = data['Close']
            else:
                close = data['close']
            
            returns = close.pct_change()
            strategy_returns = returns * signals.shift(1).fillna(0)
            
            # Calculate metrics
            cumulative_returns = (1 + strategy_returns).cumprod() - 1
            total_return = float(cumulative_returns.iloc[-1])
            
            # Sharpe ratio
            excess_returns = strategy_returns - 0.0001 / 252  # Risk-free rate
            sharpe = excess_returns.mean() / excess_returns.std() * np.sqrt(252)
            
            # Max drawdown
            running_max = cumulative_returns.cummax()
            drawdown = (cumulative_returns - running_max) / (1 + running_max)
            max_dd = drawdown.min()
            
            # Win rate
            wins = (strategy_returns > 0).sum()
            trades = (strategy_returns != 0).sum()
            win_rate = wins / trades if trades > 0 else 0.0
            
            return {
                "total_return": total_return,
                "sharpe_ratio": float(sharpe) if not np.isnan(sharpe) else 0.0,
                "max_drawdown": float(max_dd),
                "win_rate": float(win_rate),
                "num_trades": int(trades)
            }
        except Exception as e:
            logger.error(f"Evaluation error: {e}")
            return {
                "total_return": 0.0,
                "sharpe_ratio": 0.0,
                "max_drawdown": 0.0,
                "win_rate": 0.0,
                "num_trades": 0
            }
    
    @staticmethod
    def _generate_param_grid(ranges: Dict, samples: int = 5) -> List[Dict]:
        """Generate parameter combinations."""
        from itertools import product
        
        params_list = []
        for param_name, (min_val, max_val) in ranges.items():
            params_list.append(
                np.linspace(min_val, max_val, samples).tolist()
            )
        
        combinations = list(product(*params_list))
        param_names = list(ranges.keys())
        
        return [
            {name: val for name, val in zip(param_names, combo)}
            for combo in combinations
        ]
    
    @staticmethod
    def _calculate_parameter_stability(current: Dict, previous: List[Dict]) -> float:
        """Calculate how stable parameters are across windows."""
        if not previous:
            return 1.0
        
        # Average deviation from mean
        all_params = previous + [current]
        
        deviations = []
        for key in current.keys():
            values = [p.get(key, 0) for p in all_params]
            if max(values) > min(values):
                avg = np.mean(values)
                std = np.std(values)
                deviation = std / avg if avg != 0 else 0
                deviations.append(deviation)
        
        # Lower is better (0 = perfect stability, 1 = high variation)
        stability = 1.0 / (1.0 + np.mean(deviations)) if deviations else 1.0
        return float(stability)
    
    @staticmethod
    def _create_analysis_summary(
        results: List[WalkForwardResult],
        test_metrics: List[Dict]
    ) -> WalkForwardAnalysis:
        """Create summary of walk-forward analysis."""
        
        if not results:
            return WalkForwardAnalysis()
        
        # Extract OOS metrics
        oos_sharpes = [r.out_of_sample_sharpe for r in results]
        oos_returns = [r.out_of_sample_returns for r in results]
        oos_max_dds = [r.out_of_sample_max_dd for r in results]
        oos_win_rates = [r.out_of_sample_win_rate for r in results]
        
        # Calculate overfitting score
        is_returns = [r.train_metrics.get("total_return", 0) for r in results]
        oos_return_ratio = np.mean(oos_returns) / (np.mean(is_returns) + 1e-6)
        overfitting_score = min(1.0, max(0.0, 1.0 - oos_return_ratio))
        
        # Determine recommendation
        avg_sharpe = np.mean(oos_sharpes)
        if avg_sharpe > 1.5 and overfitting_score < 0.3:
            recommendation = "BUY"
        elif avg_sharpe > 1.0 and overfitting_score < 0.5:
            recommendation = "HOLD"
        else:
            recommendation = "SELL"
        
        analysis = WalkForwardAnalysis(
            overall_metrics={
                "num_windows": len(results),
                "avg_oos_sharpe": float(np.mean(oos_sharpes)),
                "std_oos_sharpe": float(np.std(oos_sharpes)),
                "avg_oos_returns": float(np.mean(oos_returns)),
                "std_oos_returns": float(np.std(oos_returns)),
                "avg_oos_max_dd": float(np.mean(oos_max_dds)),
                "avg_win_rate": float(np.mean(oos_win_rates)),
            },
            parameter_stability=float(np.mean([r.parameter_stability for r in results])),
            overfitting_score=overfitting_score,
            out_of_sample_sharpe=float(np.mean(oos_sharpes)),
            out_of_sample_returns=float(np.mean(oos_returns)),
            recommendation=recommendation
        )
        
        return analysis
