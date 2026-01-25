"""Advanced backtesting engine with walk-forward, Monte Carlo, and stress testing."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
import logging
import numpy as np
from enum import Enum

logger = logging.getLogger(__name__)


class BacktestMode(Enum):
    """Backtest execution modes."""
    NORMAL = "normal"
    WALK_FORWARD = "walk_forward"
    MONTE_CARLO = "monte_carlo"
    STRESS_TEST = "stress_test"
    SENSITIVITY = "sensitivity"


@dataclass
class BacktestResult:
    """Single backtest result."""
    strategy_name: str
    total_return: float  # %
    sharpe_ratio: float
    max_drawdown: float  # %
    win_rate: float  # %
    profit_factor: float
    trades: int
    winning_trades: int
    losing_trades: int
    avg_win: float
    avg_loss: float
    start_date: datetime
    end_date: datetime
    final_balance: float
    initial_balance: float
    
    @property
    def duration_days(self) -> int:
        """Backtest duration in days."""
        return (self.end_date - self.start_date).days
    
    @property
    def duration_years(self) -> float:
        """Backtest duration in years."""
        return self.duration_days / 252  # Trading days
    
    @property
    def annual_return(self) -> float:
        """Annualized return."""
        if self.duration_years == 0:
            return 0.0
        return self.total_return / self.duration_years
    
    @property
    def annual_sharpe(self) -> float:
        """Annualized Sharpe ratio."""
        return self.sharpe_ratio * np.sqrt(252)
    
    @property
    def recovery_factor(self) -> float:
        """Recovery factor (total return / max drawdown)."""
        if self.max_drawdown == 0:
            return 0.0
        return self.total_return / abs(self.max_drawdown)


@dataclass
class MonteCarloResult:
    """Monte Carlo simulation result."""
    base_result: BacktestResult
    simulations: int
    percentile_10: BacktestResult  # 10th percentile
    percentile_25: BacktestResult  # 25th percentile
    percentile_50: BacktestResult  # 50th (median)
    percentile_75: BacktestResult  # 75th percentile
    percentile_90: BacktestResult  # 90th percentile
    worst_case: BacktestResult
    best_case: BacktestResult
    std_dev_return: float
    probability_profitable: float  # % of sims with positive return


@dataclass
class WalkForwardResult:
    """Walk-forward analysis result."""
    in_sample_periods: int  # Number of IS periods
    out_of_sample_periods: int  # Number of OOS periods
    avg_is_return: float  # Average IS return
    avg_oos_return: float  # Average OOS return
    avg_is_sharpe: float
    avg_oos_sharpe: float
    degradation_factor: float  # OOS_return / IS_return
    results: List[Dict] = field(default_factory=list)


@dataclass
class StressTestScenario:
    """Stress test scenario."""
    name: str
    market_shock: float  # % shock (e.g., -20 for 20% drop)
    volatility_multiplier: float = 2.0  # Volatility increase
    correlation_increase: float = 0.2  # Correlation change
    liquidity_impact: float = 1.0  # Slippage multiplier


class BacktestEngine:
    """Core backtesting engine."""
    
    def __init__(self, initial_balance: float = 100000.0):
        """Initialize backtesting engine.
        
        Args:
            initial_balance: Starting capital
        """
        self.initial_balance = initial_balance
        self.results: List[BacktestResult] = []
    
    def run_backtest(
        self,
        strategy_func,
        price_data: Dict[str, List[float]],
        volume_data: Dict[str, List[int]],
        dates: List[datetime],
        transaction_cost: float = 0.001,  # 0.1%
    ) -> BacktestResult:
        """Run single backtest.
        
        Args:
            strategy_func: Strategy function that returns trades
            price_data: Dict of symbol -> price list
            volume_data: Dict of symbol -> volume list
            dates: List of dates corresponding to bars
            transaction_cost: Transaction cost as %
            
        Returns:
            BacktestResult
        """
        balance = self.initial_balance
        equity_curve = [balance]
        trades = []
        
        # Simulate trading
        for i in range(1, len(dates)):
            # Get signals from strategy
            signals = strategy_func(
                price_data=price_data,
                volume_data=volume_data,
                current_date=dates[i],
                bar_index=i,
                balance=balance
            )
            
            # Process trades
            for signal in signals:
                symbol = signal.get('symbol')
                qty = signal.get('quantity', 0)
                action = signal.get('action', 'hold')
                
                if action != 'hold' and symbol in price_data:
                    price = price_data[symbol][i]
                    cost = qty * price * (1 + transaction_cost)
                    
                    if action == 'buy' and balance >= cost:
                        balance -= cost
                        trades.append({
                            'symbol': symbol,
                            'date': dates[i],
                            'action': 'buy',
                            'price': price,
                            'quantity': qty
                        })
                    elif action == 'sell':
                        balance += qty * price * (1 - transaction_cost)
                        trades.append({
                            'symbol': symbol,
                            'date': dates[i],
                            'action': 'sell',
                            'price': price,
                            'quantity': qty
                        })
            
            equity_curve.append(balance)
        
        # Calculate metrics
        equity_array = np.array(equity_curve)
        returns = np.diff(equity_array) / equity_array[:-1]
        
        result = BacktestResult(
            strategy_name="test_strategy",
            total_return=(balance - self.initial_balance) / self.initial_balance * 100,
            sharpe_ratio=self._calculate_sharpe(returns),
            max_drawdown=self._calculate_max_drawdown(equity_array),
            win_rate=self._calculate_win_rate(trades),
            profit_factor=self._calculate_profit_factor(trades),
            trades=len(trades),
            winning_trades=len([t for t in trades if t.get('pnl', 0) > 0]),
            losing_trades=len([t for t in trades if t.get('pnl', 0) <= 0]),
            avg_win=self._calculate_avg_win(trades),
            avg_loss=self._calculate_avg_loss(trades),
            start_date=dates[0],
            end_date=dates[-1],
            final_balance=balance,
            initial_balance=self.initial_balance,
        )
        
        self.results.append(result)
        return result
    
    def _calculate_sharpe(self, returns: np.ndarray, rf_rate: float = 0.02) -> float:
        """Calculate Sharpe ratio.
        
        Args:
            returns: Array of returns
            rf_rate: Risk-free rate
            
        Returns:
            Sharpe ratio
        """
        if len(returns) < 2:
            return 0.0
        
        excess_returns = returns - (rf_rate / 252)
        return np.sqrt(252) * np.mean(excess_returns) / (np.std(excess_returns) + 1e-8)
    
    def _calculate_max_drawdown(self, equity: np.ndarray) -> float:
        """Calculate maximum drawdown.
        
        Args:
            equity: Equity curve
            
        Returns:
            Max drawdown %
        """
        peak = np.maximum.accumulate(equity)
        drawdown = (equity - peak) / peak
        return np.min(drawdown) * 100
    
    def _calculate_win_rate(self, trades: List[Dict]) -> float:
        """Calculate win rate.
        
        Args:
            trades: List of trades
            
        Returns:
            Win rate %
        """
        if not trades:
            return 0.0
        
        wins = len([t for t in trades if t.get('pnl', 0) > 0])
        return (wins / len(trades)) * 100
    
    def _calculate_profit_factor(self, trades: List[Dict]) -> float:
        """Calculate profit factor.
        
        Args:
            trades: List of trades
            
        Returns:
            Profit factor
        """
        gross_profit = sum(t.get('pnl', 0) for t in trades if t.get('pnl', 0) > 0)
        gross_loss = abs(sum(t.get('pnl', 0) for t in trades if t.get('pnl', 0) <= 0))
        
        if gross_loss == 0:
            return 0.0
        
        return gross_profit / gross_loss
    
    def _calculate_avg_win(self, trades: List[Dict]) -> float:
        """Calculate average win.
        
        Args:
            trades: List of trades
            
        Returns:
            Average win
        """
        wins = [t.get('pnl', 0) for t in trades if t.get('pnl', 0) > 0]
        return np.mean(wins) if wins else 0.0
    
    def _calculate_avg_loss(self, trades: List[Dict]) -> float:
        """Calculate average loss.
        
        Args:
            trades: List of trades
            
        Returns:
            Average loss
        """
        losses = [t.get('pnl', 0) for t in trades if t.get('pnl', 0) <= 0]
        return np.mean(losses) if losses else 0.0


class WalkForwardAnalyzer:
    """Performs walk-forward analysis."""
    
    def __init__(self, engine: BacktestEngine):
        """Initialize analyzer.
        
        Args:
            engine: BacktestEngine instance
        """
        self.engine = engine
    
    def run_walk_forward(
        self,
        strategy_func,
        price_data: Dict[str, List[float]],
        volume_data: Dict[str, List[int]],
        dates: List[datetime],
        is_period: int = 252,  # In-sample period (1 year)
        oos_period: int = 63,  # Out-of-sample period (3 months)
    ) -> WalkForwardResult:
        """Run walk-forward analysis.
        
        Args:
            strategy_func: Strategy function
            price_data: Price data
            volume_data: Volume data
            dates: Dates
            is_period: In-sample period
            oos_period: Out-of-sample period
            
        Returns:
            WalkForwardResult
        """
        result = WalkForwardResult(
            in_sample_periods=0,
            out_of_sample_periods=0,
            avg_is_return=0.0,
            avg_oos_return=0.0,
            avg_is_sharpe=0.0,
            avg_oos_sharpe=0.0,
            degradation_factor=0.0,
        )
        
        total_len = len(dates)
        is_returns = []
        oos_returns = []
        
        # Walk forward
        i = 0
        while i + is_period + oos_period <= total_len:
            # In-sample training period
            is_start = i
            is_end = i + is_period
            
            # Out-of-sample testing period
            oos_start = is_end
            oos_end = oos_start + oos_period
            
            # Optimize on IS period
            is_result = self.engine.run_backtest(
                strategy_func,
                {k: v[is_start:is_end] for k, v in price_data.items()},
                {k: v[is_start:is_end] for k, v in volume_data.items()},
                dates[is_start:is_end],
            )
            
            # Test on OOS period
            oos_result = self.engine.run_backtest(
                strategy_func,
                {k: v[oos_start:oos_end] for k, v in price_data.items()},
                {k: v[oos_start:oos_end] for k, v in volume_data.items()},
                dates[oos_start:oos_end],
            )
            
            is_returns.append(is_result.total_return)
            oos_returns.append(oos_result.total_return)
            
            result.results.append({
                'is_period': is_result.total_return,
                'oos_period': oos_result.total_return,
            })
            
            i += oos_period
        
        result.in_sample_periods = len(is_returns)
        result.out_of_sample_periods = len(oos_returns)
        result.avg_is_return = np.mean(is_returns) if is_returns else 0.0
        result.avg_oos_return = np.mean(oos_returns) if oos_returns else 0.0
        result.degradation_factor = (
            result.avg_oos_return / result.avg_is_return 
            if result.avg_is_return > 0 else 0.0
        )
        
        return result


class MonteCarloSimulator:
    """Performs Monte Carlo simulations."""
    
    def __init__(self, engine: BacktestEngine):
        """Initialize simulator.
        
        Args:
            engine: BacktestEngine instance
        """
        self.engine = engine
    
    def run_monte_carlo(
        self,
        base_result: BacktestResult,
        price_data: Dict[str, List[float]],
        volume_data: Dict[str, List[int]],
        dates: List[datetime],
        simulations: int = 1000,
        return_distribution: Optional[np.ndarray] = None,
    ) -> MonteCarloResult:
        """Run Monte Carlo simulations.
        
        Args:
            base_result: Base backtest result
            price_data: Price data
            volume_data: Volume data
            dates: Dates
            simulations: Number of simulations
            return_distribution: Distribution of returns (default: normal)
            
        Returns:
            MonteCarloResult
        """
        simulated_returns = []
        
        for _ in range(simulations):
            if return_distribution is None:
                # Use normal distribution based on base result
                sim_return = np.random.normal(
                    base_result.total_return / base_result.duration_years,
                    base_result.annual_return * 0.3,  # Volatility estimate
                )
            else:
                sim_return = np.random.choice(return_distribution)
            
            simulated_returns.append(sim_return)
        
        simulated_returns = np.array(simulated_returns)
        
        # Calculate percentiles
        percentiles = np.percentile(simulated_returns, [10, 25, 50, 75, 90])
        
        # Create result objects for each percentile
        def create_result(return_val):
            result = BacktestResult(
                strategy_name=base_result.strategy_name,
                total_return=return_val * base_result.duration_years,
                sharpe_ratio=base_result.sharpe_ratio * (1 + return_val / base_result.total_return),
                max_drawdown=base_result.max_drawdown * (1 + abs(return_val) / base_result.total_return),
                win_rate=base_result.win_rate,
                profit_factor=base_result.profit_factor,
                trades=base_result.trades,
                winning_trades=base_result.winning_trades,
                losing_trades=base_result.losing_trades,
                avg_win=base_result.avg_win,
                avg_loss=base_result.avg_loss,
                start_date=base_result.start_date,
                end_date=base_result.end_date,
                final_balance=base_result.initial_balance * (1 + return_val),
                initial_balance=base_result.initial_balance,
            )
            return result
        
        return MonteCarloResult(
            base_result=base_result,
            simulations=simulations,
            percentile_10=create_result(percentiles[0]),
            percentile_25=create_result(percentiles[1]),
            percentile_50=create_result(percentiles[2]),
            percentile_75=create_result(percentiles[3]),
            percentile_90=create_result(percentiles[4]),
            worst_case=create_result(np.min(simulated_returns)),
            best_case=create_result(np.max(simulated_returns)),
            std_dev_return=np.std(simulated_returns),
            probability_profitable=float(np.sum(simulated_returns > 0) / len(simulated_returns) * 100),
        )


class StressTestRunner:
    """Runs stress tests on strategies."""
    
    def __init__(self, engine: BacktestEngine):
        """Initialize stress tester.
        
        Args:
            engine: BacktestEngine instance
        """
        self.engine = engine
    
    def run_stress_test(
        self,
        strategy_func,
        price_data: Dict[str, List[float]],
        volume_data: Dict[str, List[int]],
        dates: List[datetime],
        scenarios: Optional[List[StressTestScenario]] = None,
    ) -> Dict[str, BacktestResult]:
        """Run stress tests with various scenarios.
        
        Args:
            strategy_func: Strategy function
            price_data: Price data
            volume_data: Volume data
            dates: Dates
            scenarios: List of stress scenarios
            
        Returns:
            Dict of scenario name -> result
        """
        if scenarios is None:
            scenarios = [
                StressTestScenario("bear_market", -20),
                StressTestScenario("crash", -30),
                StressTestScenario("flash_crash", -50),
                StressTestScenario("high_volatility", market_shock=0, volatility_multiplier=3.0),
            ]
        
        results = {}
        
        for scenario in scenarios:
            # Apply shock to prices
            shocked_prices = {}
            for symbol, prices in price_data.items():
                prices_array = np.array(prices)
                shock_factor = 1 + (scenario.market_shock / 100)
                shocked_prices[symbol] = list(prices_array * shock_factor)
            
            # Run backtest with shocked prices
            result = self.engine.run_backtest(
                strategy_func,
                shocked_prices,
                volume_data,
                dates,
            )
            
            results[scenario.name] = result
        
        return results
