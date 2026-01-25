"""
Walk-Forward Backtesting Module
Rolling optimization windows, out-of-sample testing, overfitting detection.
Prevents optimization bias and validates robustness across market regimes.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Callable
import numpy as np
import pandas as pd
from enum import Enum

logger = logging.getLogger(__name__)


class BacktestMetric(Enum):
    """Backtesting metrics"""
    TOTAL_RETURN = "total_return"
    ANNUAL_RETURN = "annual_return"
    SHARPE_RATIO = "sharpe_ratio"
    SORTINO_RATIO = "sortino_ratio"
    MAX_DRAWDOWN = "max_drawdown"
    WIN_RATE = "win_rate"
    PROFIT_FACTOR = "profit_factor"
    CALMAR_RATIO = "calmar_ratio"


@dataclass
class BacktestWindow:
    """Time window for backtesting"""
    start_date: datetime
    end_date: datetime
    training_end_date: datetime  # Where optimization ends, test begins


@dataclass
class StrategyParams:
    """Strategy parameters for optimization"""
    param_name: str
    min_value: float
    max_value: float
    step: float


@dataclass
class OptimizationResult:
    """Result of parameter optimization"""
    window: BacktestWindow
    best_params: Dict[str, float]
    best_metric_value: float
    in_sample_performance: Dict[str, float]
    out_of_sample_performance: Dict[str, float]
    overfitting_ratio: float  # in_sample / out_of_sample


class PerformanceCalculator:
    """Calculates performance metrics from trade data"""

    def __init__(self, risk_free_rate: float = 0.05):
        self.risk_free_rate = risk_free_rate

    def calculate_returns(self, equity_curve: pd.Series) -> pd.Series:
        """Calculate daily returns from equity curve"""
        return equity_curve.pct_change().dropna()

    def calculate_sharpe_ratio(
        self,
        returns: pd.Series,
        periods_per_year: int = 252,
    ) -> float:
        """Calculate Sharpe ratio"""
        if returns.empty or returns.std() == 0:
            return 0.0

        excess_returns = returns.mean() - self.risk_free_rate / periods_per_year
        return (excess_returns / returns.std()) * np.sqrt(periods_per_year)

    def calculate_sortino_ratio(
        self,
        returns: pd.Series,
        periods_per_year: int = 252,
    ) -> float:
        """Calculate Sortino ratio (downside volatility only)"""
        if returns.empty:
            return 0.0

        excess_returns = returns.mean() - self.risk_free_rate / periods_per_year

        downside_returns = returns[returns < 0]
        downside_volatility = downside_returns.std() if not downside_returns.empty else 0

        if downside_volatility == 0:
            return 0.0

        return (excess_returns / downside_volatility) * np.sqrt(periods_per_year)

    def calculate_max_drawdown(self, equity_curve: pd.Series) -> float:
        """Calculate maximum drawdown"""
        cumulative_max = equity_curve.cummax()
        drawdown = (equity_curve - cumulative_max) / cumulative_max
        return drawdown.min()

    def calculate_win_rate(self, returns: pd.Series) -> float:
        """Calculate percentage of winning days"""
        if returns.empty:
            return 0.0
        return (returns > 0).sum() / len(returns) * 100

    def calculate_profit_factor(self, returns: pd.Series) -> float:
        """Calculate profit factor"""
        if returns.empty:
            return 0.0

        gains = returns[returns > 0].sum()
        losses = abs(returns[returns < 0].sum())

        if losses == 0:
            return float('inf') if gains > 0 else 0.0

        return gains / losses

    def calculate_calmar_ratio(
        self,
        returns: pd.Series,
        equity_curve: pd.Series,
        periods_per_year: int = 252,
    ) -> float:
        """Calculate Calmar ratio"""
        annual_return = returns.mean() * periods_per_year
        max_drawdown = self.calculate_max_drawdown(equity_curve)

        if max_drawdown == 0:
            return 0.0

        return annual_return / abs(max_drawdown)

    def calculate_all_metrics(
        self,
        returns: pd.Series,
        equity_curve: pd.Series,
        periods_per_year: int = 252,
    ) -> Dict[str, float]:
        """Calculate all performance metrics"""
        return {
            "total_return": (equity_curve.iloc[-1] / equity_curve.iloc[0] - 1) * 100 if len(equity_curve) > 0 else 0,
            "annual_return": returns.mean() * periods_per_year * 100,
            "sharpe_ratio": self.calculate_sharpe_ratio(returns, periods_per_year),
            "sortino_ratio": self.calculate_sortino_ratio(returns, periods_per_year),
            "max_drawdown": self.calculate_max_drawdown(equity_curve) * 100,
            "win_rate": self.calculate_win_rate(returns),
            "profit_factor": self.calculate_profit_factor(returns),
            "calmar_ratio": self.calculate_calmar_ratio(returns, equity_curve, periods_per_year),
        }


class WalkForwardOptimizer:
    """Implements walk-forward optimization with rolling windows"""

    def __init__(
        self,
        window_size_days: int = 252,  # 1 year
        step_size_days: int = 63,  # 1 quarter
        test_size_ratio: float = 0.25,  # 25% of window is test
    ):
        self.window_size_days = window_size_days
        self.step_size_days = step_size_days
        self.test_size_ratio = test_size_ratio
        self.performance_calculator = PerformanceCalculator()
        self.optimization_results: List[OptimizationResult] = []

    def create_windows(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> List[BacktestWindow]:
        """Create walk-forward windows"""
        windows = []
        current_start = start_date

        while current_start + timedelta(days=self.window_size_days) <= end_date:
            window_end = current_start + timedelta(days=self.window_size_days)
            training_end = current_start + timedelta(
                days=int(self.window_size_days * (1 - self.test_size_ratio))
            )

            windows.append(BacktestWindow(
                start_date=current_start,
                end_date=window_end,
                training_end_date=training_end,
            ))

            current_start += timedelta(days=self.step_size_days)

        return windows

    def optimize_parameters(
        self,
        training_data: pd.DataFrame,
        strategy_func: Callable,
        parameters: List[StrategyParams],
        target_metric: BacktestMetric = BacktestMetric.SHARPE_RATIO,
    ) -> Dict[str, float]:
        """Optimize parameters on training data (in-sample)"""

        best_params = {}
        best_metric = float('-inf')

        # Generate parameter grid
        param_ranges = {}
        for param in parameters:
            values = np.arange(param.min_value, param.max_value + param.step, param.step)
            param_ranges[param.param_name] = values

        # Grid search over parameter space
        def grid_search(params_dict):
            nonlocal best_params, best_metric

            # Run backtest with these parameters
            equity_curve = strategy_func(training_data, **params_dict)
            returns = self.performance_calculator.calculate_returns(equity_curve)
            metrics = self.performance_calculator.calculate_all_metrics(returns, equity_curve)

            metric_value = metrics.get(target_metric.value, 0)

            if metric_value > best_metric:
                best_metric = metric_value
                best_params = params_dict.copy()

        # Recursive grid search
        def recursive_grid_search(param_list, current_params=None):
            if current_params is None:
                current_params = {}

            if not param_list:
                grid_search(current_params)
                return

            param = param_list[0]
            remaining_params = param_list[1:]

            for value in param_ranges[param.param_name]:
                current_params[param.param_name] = value
                recursive_grid_search(remaining_params, current_params)

        param_list = [p.param_name for p in parameters]
        recursive_grid_search(param_list)

        return best_params

    def backtest_on_test_set(
        self,
        test_data: pd.DataFrame,
        strategy_func: Callable,
        parameters: Dict[str, float],
    ) -> Tuple[pd.Series, Dict[str, float]]:
        """Backtest on out-of-sample test data"""

        equity_curve = strategy_func(test_data, **parameters)
        returns = self.performance_calculator.calculate_returns(equity_curve)
        metrics = self.performance_calculator.calculate_all_metrics(returns, equity_curve)

        return equity_curve, metrics

    def run_walk_forward(
        self,
        data: pd.DataFrame,
        strategy_func: Callable,
        parameters: List[StrategyParams],
        target_metric: BacktestMetric = BacktestMetric.SHARPE_RATIO,
    ) -> List[OptimizationResult]:
        """Run complete walk-forward analysis"""

        start_date = pd.to_datetime(data.index[0])
        end_date = pd.to_datetime(data.index[-1])

        windows = self.create_windows(start_date, end_date)

        results = []

        for i, window in enumerate(windows):
            logger.info(f"Processing window {i+1}/{len(windows)}: {window.start_date.date()} to {window.end_date.date()}")

            # Split into training and test
            training_data = data.loc[data.index < window.training_end_date.isoformat()]
            test_data = data.loc[
                (data.index >= window.training_end_date.isoformat())
                & (data.index <= window.end_date.isoformat())
            ]

            if len(training_data) == 0 or len(test_data) == 0:
                continue

            # Optimize on training data
            best_params = self.optimize_parameters(
                training_data,
                strategy_func,
                parameters,
                target_metric,
            )

            # Test on out-of-sample data
            test_equity, test_metrics = self.backtest_on_test_set(
                test_data,
                strategy_func,
                best_params,
            )

            # Also evaluate training performance for comparison
            training_equity = strategy_func(training_data, **best_params)
            training_returns = self.performance_calculator.calculate_returns(training_equity)
            training_metrics = self.performance_calculator.calculate_all_metrics(training_returns, training_equity)

            # Calculate overfitting ratio
            in_sample_metric = training_metrics.get(target_metric.value, 0)
            out_of_sample_metric = test_metrics.get(target_metric.value, 0)

            if out_of_sample_metric != 0:
                overfitting_ratio = in_sample_metric / out_of_sample_metric
            else:
                overfitting_ratio = float('inf')

            result = OptimizationResult(
                window=window,
                best_params=best_params,
                best_metric_value=in_sample_metric,
                in_sample_performance=training_metrics,
                out_of_sample_performance=test_metrics,
                overfitting_ratio=overfitting_ratio,
            )

            results.append(result)
            self.optimization_results.append(result)

        return results

    def get_overfitting_summary(self) -> Dict[str, float]:
        """Get summary of overfitting across all windows"""
        if not self.optimization_results:
            return {}

        overfitting_ratios = [r.overfitting_ratio for r in self.optimization_results if r.overfitting_ratio != float('inf')]

        return {
            "avg_overfitting_ratio": np.mean(overfitting_ratios) if overfitting_ratios else 0,
            "max_overfitting_ratio": max(overfitting_ratios) if overfitting_ratios else 0,
            "high_overfitting_windows": sum(1 for r in overfitting_ratios if r > 2.0),
        }


class MonteCarloSimulator:
    """Runs Monte Carlo simulations to test strategy robustness"""

    def __init__(self, num_simulations: int = 100):
        self.num_simulations = num_simulations
        self.performance_calculator = PerformanceCalculator()

    def generate_random_paths(
        self,
        returns: pd.Series,
        num_paths: int = 100,
        num_periods: int = 252,
    ) -> np.ndarray:
        """Generate random price paths using bootstrap resampling"""

        paths = np.zeros((num_periods, num_paths))

        for path_idx in range(num_paths):
            # Randomly sample returns with replacement
            sampled_returns = np.random.choice(returns, size=num_periods, replace=True)
            path = np.cumprod(1 + sampled_returns) * 100
            paths[:, path_idx] = path

        return paths

    def calculate_path_statistics(self, paths: np.ndarray) -> Dict[str, np.ndarray]:
        """Calculate percentile statistics across paths"""

        return {
            "mean_path": np.mean(paths, axis=1),
            "p5_path": np.percentile(paths, 5, axis=1),
            "p25_path": np.percentile(paths, 25, axis=1),
            "p50_path": np.percentile(paths, 50, axis=1),
            "p75_path": np.percentile(paths, 75, axis=1),
            "p95_path": np.percentile(paths, 95, axis=1),
            "min_path": np.min(paths, axis=1),
            "max_path": np.max(paths, axis=1),
        }

    def run_simulation(
        self,
        historical_returns: pd.Series,
        initial_capital: float = 100_000,
    ) -> Dict[str, any]:
        """Run full Monte Carlo simulation"""

        num_periods = len(historical_returns)

        paths = self.generate_random_paths(
            historical_returns,
            num_paths=self.num_simulations,
            num_periods=num_periods,
        )

        # Scale to initial capital
        paths = paths * (initial_capital / 100)

        stats = self.calculate_path_statistics(paths)

        # Calculate ending capital percentiles
        ending_capitals = paths[-1, :]

        return {
            "paths": paths,
            "statistics": stats,
            "ending_capital_mean": np.mean(ending_capitals),
            "ending_capital_std": np.std(ending_capitals),
            "ending_capital_p5": np.percentile(ending_capitals, 5),
            "ending_capital_p95": np.percentile(ending_capitals, 95),
            "probability_profit": (ending_capitals > initial_capital).sum() / len(ending_capitals),
        }


class StressTestSuite:
    """Runs strategy against historical stress scenarios"""

    def __init__(self):
        self.performance_calculator = PerformanceCalculator()
        self.stress_scenarios = self._create_stress_scenarios()

    def _create_stress_scenarios(self) -> Dict[str, Dict]:
        """Create historical stress test scenarios"""
        return {
            "2008_crisis": {
                "name": "2008 Financial Crisis",
                "description": "September 2008 - March 2009",
                "return_shock": -0.40,  # -40% shock
                "volatility_multiplier": 3.0,
            },
            "2020_covid": {
                "name": "COVID-19 Crash",
                "description": "February - March 2020",
                "return_shock": -0.35,  # -35% shock
                "volatility_multiplier": 2.5,
            },
            "1987_crash": {
                "name": "Black Monday",
                "description": "October 1987",
                "return_shock": -0.22,  # -22% single day
                "volatility_multiplier": 4.0,
            },
            "flash_crash": {
                "name": "Flash Crash",
                "description": "May 2010",
                "return_shock": -0.10,  # -10% intraday
                "volatility_multiplier": 5.0,
            },
        }

    def apply_stress_scenario(
        self,
        equity_curve: pd.Series,
        scenario_name: str,
    ) -> pd.Series:
        """Apply stress scenario to equity curve"""

        if scenario_name not in self.stress_scenarios:
            return equity_curve

        scenario = self.stress_scenarios[scenario_name]

        # Apply shock
        shocked_curve = equity_curve * (1 + scenario["return_shock"])

        return shocked_curve

    def stress_test_strategy(
        self,
        equity_curve: pd.Series,
        returns: pd.Series,
    ) -> Dict[str, Dict]:
        """Run all stress tests on strategy"""

        results = {}

        for scenario_name, scenario_info in self.stress_scenarios.items():
            shocked_curve = self.apply_stress_scenario(equity_curve, scenario_name)
            shocked_returns = self.performance_calculator.calculate_returns(shocked_curve)
            metrics = self.performance_calculator.calculate_all_metrics(shocked_returns, shocked_curve)

            results[scenario_name] = {
                "name": scenario_info["name"],
                "description": scenario_info["description"],
                "metrics": metrics,
                "shock_drawdown": self.performance_calculator.calculate_max_drawdown(shocked_curve) * 100,
            }

        return results
