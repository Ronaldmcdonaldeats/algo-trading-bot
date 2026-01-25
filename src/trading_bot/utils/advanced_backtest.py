"""
Phase 15: Advanced Backtesting

Walk-forward optimization, parameter sensitivity analysis,
drawdown analysis, and Monte Carlo simulation.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable, Optional
import math


@dataclass
class BacktestResult:
    """Results from a single backtest"""
    name: str
    total_trades: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    profit_factor: float = 0.0
    winning_trades: int = 0
    losing_trades: int = 0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    trades: list[float] = field(default_factory=list)  # Trade P&Ls


@dataclass
class WalkForwardResult:
    """Results from walk-forward optimization"""
    parameter: str
    parameter_value: any
    in_sample_performance: BacktestResult
    out_sample_performance: BacktestResult
    out_of_sample_pct_change: float = 0.0  # How much OOS perf differs from IS


@dataclass
class ParameterSensitivity:
    """Sensitivity of a parameter on performance"""
    parameter_name: str
    parameter_values: list = field(default_factory=list)
    sharpe_ratios: list[float] = field(default_factory=list)
    profit_factors: list[float] = field(default_factory=list)
    max_drawdowns: list[float] = field(default_factory=list)
    total_pnls: list[float] = field(default_factory=list)

    def get_optimal_value(self):
        """Get parameter value with highest Sharpe ratio"""
        if not self.sharpe_ratios:
            return None
        max_idx = self.sharpe_ratios.index(max(self.sharpe_ratios))
        return self.parameter_values[max_idx]

    def get_sensitivity_range(self):
        """Get range of Sharpe ratios"""
        if not self.sharpe_ratios:
            return 0.0
        return max(self.sharpe_ratios) - min(self.sharpe_ratios)


@dataclass
class MonteCarloResult:
    """Results from Monte Carlo simulation"""
    num_simulations: int
    trade_pnls: list[float]
    simulated_equity_curves: list[list[float]] = field(default_factory=list)
    percentile_5: float = 0.0
    percentile_25: float = 0.0
    percentile_50: float = 0.0  # Median
    percentile_75: float = 0.0
    percentile_95: float = 0.0
    confidence_level: float = 0.95  # 95% confidence interval
    expected_value: float = 0.0
    std_dev: float = 0.0


class AdvancedBacktester:
    """Advanced backtesting with optimization and analysis"""

    @staticmethod
    def calculate_metrics(trades: list[float]) -> BacktestResult:
        """Calculate comprehensive metrics from trade P&Ls"""
        result = BacktestResult(name="backtest")

        if not trades:
            return result

        result.total_trades = len(trades)
        result.winning_trades = sum(1 for t in trades if t > 0)
        result.losing_trades = sum(1 for t in trades if t < 0)
        result.total_pnl = sum(trades)
        result.trades = trades

        if result.total_trades > 0:
            result.win_rate = result.winning_trades / result.total_trades

        # Win/loss statistics
        winning_trades = [t for t in trades if t > 0]
        losing_trades = [t for t in trades if t < 0]

        if winning_trades:
            result.avg_win = sum(winning_trades) / len(winning_trades)
            result.largest_win = max(winning_trades)

        if losing_trades:
            result.avg_loss = sum(losing_trades) / len(losing_trades)
            result.largest_loss = min(losing_trades)

        # Profit factor
        total_wins = sum(winning_trades) if winning_trades else 0
        total_losses = abs(sum(losing_trades)) if losing_trades else 1
        result.profit_factor = total_wins / total_losses if total_losses > 0 else 0.0

        # Sharpe ratio
        cumulative_pnl = []
        running_total = 0
        for t in trades:
            running_total += t
            cumulative_pnl.append(running_total)

        if len(cumulative_pnl) > 1:
            returns = [cumulative_pnl[i] - cumulative_pnl[i-1] for i in range(1, len(cumulative_pnl))]
            mean_return = sum(returns) / len(returns)
            variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
            std_dev = math.sqrt(variance) if variance > 0 else 0.0

            if std_dev > 0:
                result.sharpe_ratio = (mean_return * 252) / (std_dev * math.sqrt(252))

            # Sortino (downside deviation only)
            downside_returns = [r for r in returns if r < 0]
            if downside_returns:
                downside_variance = sum(r ** 2 for r in downside_returns) / len(returns)
                downside_std = math.sqrt(downside_variance) if downside_variance > 0 else 0.0
                if downside_std > 0:
                    result.sortino_ratio = (mean_return * 252) / (downside_std * math.sqrt(252))

        # Max drawdown
        if cumulative_pnl:
            max_peak = cumulative_pnl[0]
            max_dd = 0.0
            for value in cumulative_pnl:
                if value > max_peak:
                    max_peak = value
                drawdown = (max_peak - value) / max(abs(max_peak), 1)
                max_dd = max(max_dd, drawdown)
            result.max_drawdown = max_dd * 100

        return result

    @staticmethod
    def walk_forward_optimization(
        trade_generator: Callable[[any], list[float]],
        parameter_name: str,
        parameter_values: list,
        in_sample_periods: int = 20,
        out_sample_periods: int = 5
    ) -> list[WalkForwardResult]:
        """
        Perform walk-forward optimization.
        
        Test parameter on in-sample data, then evaluate on out-of-sample data.
        """
        results = []

        for param_value in parameter_values:
            # Generate trades for this parameter
            all_trades = trade_generator(param_value)

            if len(all_trades) < in_sample_periods + out_sample_periods:
                continue

            # Split into in-sample and out-of-sample
            in_sample = all_trades[:in_sample_periods]
            out_sample = all_trades[in_sample_periods:in_sample_periods + out_sample_periods]

            # Calculate metrics
            in_sample_result = AdvancedBacktester.calculate_metrics(in_sample)
            in_sample_result.name = f"{parameter_name}={param_value} (In-Sample)"

            out_sample_result = AdvancedBacktester.calculate_metrics(out_sample)
            out_sample_result.name = f"{parameter_name}={param_value} (Out-Sample)"

            # Calculate OOS degradation
            oos_change = ((out_sample_result.sharpe_ratio - in_sample_result.sharpe_ratio) /
                         max(abs(in_sample_result.sharpe_ratio), 0.01))

            result = WalkForwardResult(
                parameter=parameter_name,
                parameter_value=param_value,
                in_sample_performance=in_sample_result,
                out_sample_performance=out_sample_result,
                out_of_sample_pct_change=oos_change
            )
            results.append(result)

        return results

    @staticmethod
    def parameter_sensitivity_analysis(
        trade_generator: Callable[[any], list[float]],
        parameter_name: str,
        parameter_values: list
    ) -> ParameterSensitivity:
        """
        Analyze how sensitive performance is to a parameter.
        """
        sensitivity = ParameterSensitivity(parameter_name=parameter_name)

        for param_value in parameter_values:
            trades = trade_generator(param_value)
            result = AdvancedBacktester.calculate_metrics(trades)

            sensitivity.parameter_values.append(param_value)
            sensitivity.sharpe_ratios.append(result.sharpe_ratio)
            sensitivity.profit_factors.append(result.profit_factor)
            sensitivity.max_drawdowns.append(result.max_drawdown)
            sensitivity.total_pnls.append(result.total_pnl)

        return sensitivity

    @staticmethod
    def monte_carlo_simulation(
        trades: list[float],
        num_simulations: int = 1000,
        replacement: bool = True
    ) -> MonteCarloResult:
        """
        Perform Monte Carlo simulation to estimate confidence intervals.
        
        Randomly resamples trades (with or without replacement) to simulate
        different possible outcomes.
        """
        result = MonteCarloResult(
            num_simulations=num_simulations,
            trade_pnls=trades
        )

        if not trades or len(trades) < 2:
            return result

        # Calculate original metrics
        result.expected_value = sum(trades) / len(trades)
        variance = sum((t - result.expected_value) ** 2 for t in trades) / len(trades)
        result.std_dev = math.sqrt(variance)

        # Run simulations
        simulated_final_pnls = []

        for _ in range(num_simulations):
            # Resample trades
            if replacement:
                simulated_trades = [random.choice(trades) for _ in range(len(trades))]
            else:
                simulated_trades = random.sample(trades, len(trades))

            # Calculate cumulative P&L
            cumulative_pnl = []
            running_total = 0
            for t in simulated_trades:
                running_total += t
                cumulative_pnl.append(running_total)

            result.simulated_equity_curves.append(cumulative_pnl)
            simulated_final_pnls.append(cumulative_pnl[-1])

        # Calculate percentiles
        sorted_pnls = sorted(simulated_final_pnls)
        result.percentile_5 = sorted_pnls[int(len(sorted_pnls) * 0.05)]
        result.percentile_25 = sorted_pnls[int(len(sorted_pnls) * 0.25)]
        result.percentile_50 = sorted_pnls[int(len(sorted_pnls) * 0.50)]
        result.percentile_75 = sorted_pnls[int(len(sorted_pnls) * 0.75)]
        result.percentile_95 = sorted_pnls[int(len(sorted_pnls) * 0.95)]

        return result

    @staticmethod
    def drawdown_analysis(trades: list[float]) -> dict:
        """Analyze drawdown characteristics"""
        if not trades:
            return {}

        cumulative_pnl = []
        running_total = 0
        for t in trades:
            running_total += t
            cumulative_pnl.append(running_total)

        # Track drawdowns
        max_peak = cumulative_pnl[0]
        current_drawdown = 0.0
        max_drawdown = 0.0
        drawdown_periods = 0
        total_drawdown_periods = 0

        for value in cumulative_pnl:
            if value > max_peak:
                if drawdown_periods > 0:
                    total_drawdown_periods += drawdown_periods
                max_peak = value
                current_drawdown = 0.0
                drawdown_periods = 0
            else:
                drawdown = (max_peak - value) / max(abs(max_peak), 1)
                if drawdown > 0:
                    drawdown_periods += 1
                    current_drawdown = max(current_drawdown, drawdown)
                    max_drawdown = max(max_drawdown, drawdown)

        avg_drawdown = total_drawdown_periods / len(trades) if len(trades) > 0 else 0.0

        # Recovery analysis
        recovery_periods = []
        peak_time = 0
        for i, value in enumerate(cumulative_pnl):
            if i > 0 and value > cumulative_pnl[peak_time]:
                if i > peak_time:
                    recovery_periods.append(i - peak_time)
                peak_time = i

        avg_recovery = sum(recovery_periods) / len(recovery_periods) if recovery_periods else 0.0

        return {
            "max_drawdown_pct": max_drawdown * 100,
            "avg_drawdown_duration_trades": avg_drawdown,
            "avg_recovery_duration_trades": avg_recovery,
            "largest_recovery_trades": max(recovery_periods) if recovery_periods else 0,
        }

    @staticmethod
    def print_backtest_results(result: BacktestResult):
        """Print formatted backtest results"""
        print(f"\n{'='*60}")
        print(f"[BACKTEST RESULTS] {result.name}")
        print(f"{'='*60}")
        print(f"\nTrade Statistics:")
        print(f"  Total Trades: {result.total_trades}")
        print(f"  Winning: {result.winning_trades} | Losing: {result.losing_trades}")
        print(f"  Win Rate: {result.win_rate*100:.1f}%")
        print(f"\nProfit Metrics:")
        print(f"  Total P&L: ${result.total_pnl:,.2f}")
        print(f"  Avg Win: ${result.avg_win:,.2f}")
        print(f"  Avg Loss: ${result.avg_loss:,.2f}")
        print(f"  Largest Win: ${result.largest_win:,.2f}")
        print(f"  Largest Loss: ${result.largest_loss:,.2f}")
        print(f"  Profit Factor: {result.profit_factor:.2f}")
        print(f"\nRisk-Adjusted Returns:")
        print(f"  Sharpe Ratio: {result.sharpe_ratio:.2f}")
        print(f"  Sortino Ratio: {result.sortino_ratio:.2f}")
        print(f"  Max Drawdown: {result.max_drawdown:.2f}%")
        print(f"{'='*60}\n")

    @staticmethod
    def print_walk_forward_results(results: list[WalkForwardResult]):
        """Print walk-forward optimization results"""
        print(f"\n{'='*80}")
        print("[WALK-FORWARD OPTIMIZATION RESULTS]")
        print(f"{'='*80}")

        for result in results:
            print(f"\n{result.parameter} = {result.parameter_value}")
            print(f"  In-Sample Sharpe:  {result.in_sample_performance.sharpe_ratio:.2f}")
            print(f"  Out-Sample Sharpe: {result.out_sample_performance.sharpe_ratio:.2f}")
            print(f"  OOS Degradation:   {result.out_of_sample_pct_change*100:+.1f}%")
            print(f"  OOS Trades:        {result.out_sample_performance.total_trades}")
            print(f"  OOS P&L:           ${result.out_sample_performance.total_pnl:,.2f}")

    @staticmethod
    def print_monte_carlo_results(result: MonteCarloResult):
        """Print Monte Carlo simulation results"""
        print(f"\n{'='*60}")
        print(f"[MONTE CARLO SIMULATION] {result.num_simulations} simulations")
        print(f"{'='*60}")
        print(f"\nOriginal Trade Series:")
        print(f"  Trades: {len(result.trade_pnls)}")
        print(f"  Expected Value: ${result.expected_value:,.2f}")
        print(f"  Std Dev: ${result.std_dev:,.2f}")
        print(f"\nSimulated Outcome Percentiles:")
        print(f"  5th percentile:   ${result.percentile_5:,.2f}")
        print(f"  25th percentile:  ${result.percentile_25:,.2f}")
        print(f"  50th percentile:  ${result.percentile_50:,.2f}")
        print(f"  75th percentile:  ${result.percentile_75:,.2f}")
        print(f"  95th percentile:  ${result.percentile_95:,.2f}")
        print(f"\n95% Confidence Interval: [${result.percentile_5:,.2f}, ${result.percentile_95:,.2f}]")
        print(f"{'='*60}\n")
