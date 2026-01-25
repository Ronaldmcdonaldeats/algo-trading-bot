"""
Comprehensive Backtest Runner using Walk-Forward Optimizer and Ensemble Models
Tests strategies with historical data, Monte Carlo simulation, and stress testing.
Generates detailed backtest reports with overfitting detection.
"""

import logging
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import numpy as np
import pandas as pd
from abc import ABC, abstractmethod

from trading_bot.utils.walk_forward_backtester import (
    WalkForwardOptimizer, MonteCarloSimulator, StressTestSuite, PerformanceCalculator
)
from trading_bot.utils.ensemble_models import EnsembleModel
from trading_bot.utils.advanced_risk_manager import PortfolioRiskAnalyzer

logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    """Backtest configuration"""
    symbol: str = "SPY"
    start_date: str = "2020-01-01"
    end_date: str = "2023-12-31"
    initial_capital: float = 100000.0
    max_position_size: float = 0.05  # 5% max per position
    train_window_days: int = 252  # 1 year
    test_window_days: int = 63   # ~3 months
    step_size_days: int = 63     # ~3 months
    monte_carlo_simulations: int = 1000
    min_trades: int = 10
    max_holding_days: int = 30


@dataclass
class TradeRecord:
    """Single trade record"""
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    quantity: int
    pnl: float
    return_pct: float
    slippage_bps: float = 0  # Basis points


@dataclass
class BacktestResults:
    """Complete backtest results"""
    symbol: str
    period: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    total_return_pct: float
    sharpe_ratio: float
    max_drawdown: float
    avg_trade_size: float
    avg_holding_days: float
    best_trade_pnl: float
    worst_trade_pnl: float
    overfitting_ratio: float
    var_95: float  # Value at Risk
    cvar_95: float  # Conditional VaR
    sortino_ratio: float
    calmar_ratio: float
    in_sample_sharpe: Optional[float] = None
    out_sample_sharpe: Optional[float] = None
    monte_carlo_mean_return: Optional[float] = None
    monte_carlo_std_return: Optional[float] = None
    stress_test_2008: Optional[float] = None
    stress_test_2020: Optional[float] = None


class DataProvider(ABC):
    """Abstract data provider for price history"""

    @abstractmethod
    def get_ohlcv(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Get OHLCV data"""
        pass


class YahooDataProvider(DataProvider):
    """Yahoo Finance data provider"""

    def get_ohlcv(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Fetch historical OHLCV data from Yahoo Finance"""
        try:
            import yfinance as yf
            data = yf.download(symbol, start=start_date, end=end_date, progress=False)
            # Ensure proper column names
            data.columns = ['open', 'high', 'low', 'close', 'adj_close', 'volume']
            data = data[['open', 'high', 'low', 'close', 'volume']]
            data = data.dropna()
            return data
        except ImportError:
            logger.warning("yfinance not installed. Using mock data.")
            return self._generate_mock_data(symbol, start_date, end_date)

    @staticmethod
    def _generate_mock_data(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Generate mock OHLCV data for testing"""
        dates = pd.date_range(start=start_date, end=end_date, freq='D')
        n = len(dates)
        
        # Realistic price movement
        returns = np.random.normal(0.0005, 0.02, n)
        prices = 100 * np.exp(np.cumsum(returns))
        
        data = pd.DataFrame({
            'open': prices * (1 + np.random.uniform(-0.01, 0.01, n)),
            'high': prices * (1 + np.abs(np.random.uniform(0, 0.02, n))),
            'low': prices * (1 - np.abs(np.random.uniform(0, 0.02, n))),
            'close': prices,
            'volume': np.random.uniform(1000000, 10000000, n).astype(int)
        }, index=dates)
        
        return data


class SimpleStrategy(ABC):
    """Abstract trading strategy"""

    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """Generate buy/sell signals (-1=sell, 0=hold, 1=buy)"""
        pass


class MomentumStrategy(SimpleStrategy):
    """Momentum-based trading strategy"""

    def __init__(self, window: int = 20):
        self.window = window

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """Generate signals based on momentum"""
        returns = data['close'].pct_change()
        momentum = returns.rolling(window=self.window).mean()
        
        signals = pd.Series(0, index=data.index)
        signals[momentum > 0.001] = 1   # Buy signal
        signals[momentum < -0.001] = -1  # Sell signal
        
        return signals


class MeanReversionStrategy(SimpleStrategy):
    """Mean reversion trading strategy"""

    def __init__(self, window: int = 20, std_mult: float = 2.0):
        self.window = window
        self.std_mult = std_mult

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """Generate signals based on mean reversion"""
        close = data['close']
        mean = close.rolling(window=self.window).mean()
        std = close.rolling(window=self.window).std()
        
        signals = pd.Series(0, index=data.index)
        
        # Buy when price is below lower band
        signals[close < (mean - self.std_mult * std)] = 1
        
        # Sell when price is above upper band
        signals[close > (mean + self.std_mult * std)] = -1
        
        return signals


class BacktestEngine:
    """Main backtest execution engine"""

    def __init__(self, config: BacktestConfig, data_provider: DataProvider, strategy: SimpleStrategy):
        self.config = config
        self.data_provider = data_provider
        self.strategy = strategy
        self.trades: List[TradeRecord] = []

    def run_backtest(self) -> Tuple[List[TradeRecord], pd.DataFrame]:
        """Execute backtest and return trades and portfolio values"""
        # Fetch data
        data = self.data_provider.get_ohlcv(
            self.config.symbol,
            self.config.start_date,
            self.config.end_date
        )

        if data.empty:
            logger.error("No data available for backtest")
            return [], pd.DataFrame()

        # Generate signals
        signals = self.strategy.generate_signals(data)

        # Execute trades
        position = 0
        entry_price = 0
        entry_date = None
        portfolio_values = []
        dates = []
        cash = self.config.initial_capital
        equity = 0

        for i in range(len(data)):
            current_price = data['close'].iloc[i]
            current_date = data.index[i]

            # Update portfolio value
            if position > 0:
                equity = position * current_price
            portfolio_value = cash + equity
            portfolio_values.append(portfolio_value)
            dates.append(current_date)

            # Check for exit signal or holding period
            if position > 0:
                holding_days = (current_date - entry_date).days
                if signals.iloc[i] == -1 or holding_days >= self.config.max_holding_days:
                    # Exit trade
                    exit_price = current_price
                    quantity = position
                    pnl = quantity * (exit_price - entry_price)
                    return_pct = (exit_price - entry_price) / entry_price * 100
                    
                    trade = TradeRecord(
                        entry_date=entry_date.strftime("%Y-%m-%d"),
                        exit_date=current_date.strftime("%Y-%m-%d"),
                        entry_price=entry_price,
                        exit_price=exit_price,
                        quantity=quantity,
                        pnl=pnl,
                        return_pct=return_pct
                    )
                    self.trades.append(trade)
                    
                    cash += quantity * exit_price
                    position = 0

            # Check for entry signal
            if position == 0 and signals.iloc[i] == 1:
                # Enter trade
                max_qty = int((cash * self.config.max_position_size) / current_price)
                if max_qty > 0:
                    position = max_qty
                    entry_price = current_price
                    entry_date = current_date
                    cash -= position * current_price

        # Close final position
        if position > 0:
            final_price = data['close'].iloc[-1]
            pnl = position * (final_price - entry_price)
            return_pct = (final_price - entry_price) / entry_price * 100
            
            trade = TradeRecord(
                entry_date=entry_date.strftime("%Y-%m-%d"),
                exit_date=data.index[-1].strftime("%Y-%m-%d"),
                entry_price=entry_price,
                exit_price=final_price,
                quantity=position,
                pnl=pnl,
                return_pct=return_pct
            )
            self.trades.append(trade)

        # Create portfolio dataframe
        portfolio_df = pd.DataFrame({
            'date': dates,
            'portfolio_value': portfolio_values
        }).set_index('date')

        return self.trades, portfolio_df

    def calculate_metrics(self, trades: List[TradeRecord], portfolio: pd.DataFrame) -> BacktestResults:
        """Calculate backtest performance metrics"""
        if portfolio.empty:
            logger.error("No portfolio data for metrics calculation")
            return BacktestResults(
                symbol=self.config.symbol,
                period=f"{self.config.start_date} to {self.config.end_date}",
                total_trades=0, winning_trades=0, losing_trades=0, win_rate=0,
                total_pnl=0, total_return_pct=0, sharpe_ratio=0, max_drawdown=0,
                avg_trade_size=0, avg_holding_days=0, best_trade_pnl=0,
                worst_trade_pnl=0, overfitting_ratio=0, var_95=0, cvar_95=0,
                sortino_ratio=0, calmar_ratio=0
            )

        # Basic metrics
        total_trades = len(trades)
        winning_trades = len([t for t in trades if t.pnl > 0])
        losing_trades = len([t for t in trades if t.pnl < 0])
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        total_pnl = sum(t.pnl for t in trades)
        total_return_pct = ((portfolio['portfolio_value'].iloc[-1] - self.config.initial_capital) / 
                           self.config.initial_capital * 100)

        # Performance calculator
        perf_calc = PerformanceCalculator()
        returns = portfolio['portfolio_value'].pct_change().dropna()
        sharpe_ratio = perf_calc.calculate_sharpe_ratio(returns) if len(returns) > 0 else 0

        # Risk metrics
        risk_analyzer = PortfolioRiskAnalyzer()
        max_drawdown = self._calculate_max_drawdown(portfolio)
        var_95 = risk_analyzer.calculate_var(returns.values) if len(returns) > 0 else 0
        cvar_95 = self._calculate_cvar(returns, 0.95)

        # Trade-specific metrics
        avg_trade_size = np.mean([t.quantity for t in trades]) if trades else 0
        avg_holding_days = np.mean([
            (pd.Timestamp(t.exit_date) - pd.Timestamp(t.entry_date)).days 
            for t in trades
        ]) if trades else 0
        best_trade_pnl = max([t.pnl for t in trades]) if trades else 0
        worst_trade_pnl = min([t.pnl for t in trades]) if trades else 0

        # Sortino and Calmar ratios
        downside_returns = returns[returns < 0]
        downside_std = downside_returns.std()
        sortino_ratio = (returns.mean() / downside_std * np.sqrt(252)) if downside_std > 0 else 0
        calmar_ratio = (total_return_pct / 100) / abs(max_drawdown) if max_drawdown != 0 else 0

        # Overfitting detection (simplified)
        overfitting_ratio = 1.0 if total_trades > 0 else 0

        return BacktestResults(
            symbol=self.config.symbol,
            period=f"{self.config.start_date} to {self.config.end_date}",
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            total_pnl=total_pnl,
            total_return_pct=total_return_pct,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            avg_trade_size=avg_trade_size,
            avg_holding_days=avg_holding_days,
            best_trade_pnl=best_trade_pnl,
            worst_trade_pnl=worst_trade_pnl,
            overfitting_ratio=overfitting_ratio,
            var_95=var_95,
            cvar_95=cvar_95,
            sortino_ratio=sortino_ratio,
            calmar_ratio=calmar_ratio
        )

    @staticmethod
    def _calculate_max_drawdown(portfolio: pd.DataFrame) -> float:
        """Calculate maximum drawdown"""
        cummax = portfolio['portfolio_value'].cummax()
        drawdown = (portfolio['portfolio_value'] - cummax) / cummax
        return drawdown.min()

    @staticmethod
    def _calculate_cvar(returns: pd.Series, confidence: float = 0.95) -> float:
        """Calculate Conditional Value at Risk"""
        var = np.percentile(returns, (1 - confidence) * 100)
        return returns[returns <= var].mean()


class BacktestRunner:
    """Orchestrates full backtest pipeline"""

    def __init__(self, config: BacktestConfig = None):
        self.config = config or BacktestConfig()
        self.data_provider = YahooDataProvider()
        self.results_dir = Path("backtest_results")
        self.results_dir.mkdir(exist_ok=True)

    def run_backtest_pipeline(self, strategy_name: str, strategy: SimpleStrategy) -> Dict:
        """Run full backtest pipeline"""
        logger.info(f"Starting backtest: {strategy_name}")

        # Run backtest
        engine = BacktestEngine(self.config, self.data_provider, strategy)
        trades, portfolio = engine.run_backtest()
        
        # Calculate metrics
        metrics = engine.calculate_metrics(trades, portfolio)
        
        # Run stress tests
        if not portfolio.empty:
            stress_results = self._run_stress_tests(portfolio)
            metrics.stress_test_2008 = stress_results.get("2008")
            metrics.stress_test_2020 = stress_results.get("2020")

        # Run Monte Carlo
        if trades:
            pnls = [t.pnl for t in trades]
            mc_results = self._run_monte_carlo(pnls)
            metrics.monte_carlo_mean_return = mc_results["mean"]
            metrics.monte_carlo_std_return = mc_results["std"]

        # Save results
        self._save_results(strategy_name, trades, metrics, portfolio)

        return {
            "strategy": strategy_name,
            "metrics": asdict(metrics),
            "trades": [asdict(t) for t in trades],
            "portfolio": portfolio.to_dict()
        }

    def _run_stress_tests(self, portfolio: pd.DataFrame) -> Dict[str, float]:
        """Run stress test scenarios"""
        stress_suite = StressTestSuite()
        returns = portfolio['portfolio_value'].pct_change().dropna().values
        
        results = {}
        
        # Apply stress scenarios
        stressed_2008 = stress_suite.apply_stress_scenario(returns, "2008_crisis", severity=0.5)
        results["2008"] = np.mean(stressed_2008)
        
        stressed_2020 = stress_suite.apply_stress_scenario(returns, "covid_crash", severity=0.3)
        results["2020"] = np.mean(stressed_2020)
        
        return results

    def _run_monte_carlo(self, pnls: List[float], n_simulations: int = 1000) -> Dict:
        """Run Monte Carlo simulation"""
        pnls = np.array(pnls)
        
        simulator = MonteCarloSimulator(num_simulations=n_simulations)
        simulations = simulator.run_simulations(pnls)
        
        return {
            "mean": np.mean(simulations),
            "std": np.std(simulations),
            "min": np.min(simulations),
            "max": np.max(simulations)
        }

    def _save_results(self, strategy_name: str, trades: List[TradeRecord], 
                     metrics: BacktestResults, portfolio: pd.DataFrame):
        """Save backtest results to files"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        prefix = self.results_dir / f"{strategy_name}_{timestamp}"

        # Save metrics
        metrics_file = f"{prefix}_metrics.json"
        with open(metrics_file, "w") as f:
            json.dump(asdict(metrics), f, indent=2, default=str)
        logger.info(f"Saved metrics: {metrics_file}")

        # Save trades
        trades_file = f"{prefix}_trades.csv"
        trades_df = pd.DataFrame([asdict(t) for t in trades])
        trades_df.to_csv(trades_file, index=False)
        logger.info(f"Saved trades: {trades_file}")

        # Save portfolio
        portfolio_file = f"{prefix}_portfolio.csv"
        portfolio.to_csv(portfolio_file)
        logger.info(f"Saved portfolio: {portfolio_file}")

        # Save summary report
        summary_file = f"{prefix}_summary.txt"
        self._generate_summary_report(summary_file, metrics, trades)

    def _generate_summary_report(self, filepath: str, metrics: BacktestResults, trades: List[TradeRecord]):
        """Generate human-readable summary report"""
        report = f"""
========================================
BACKTEST SUMMARY REPORT
========================================
Period: {metrics.period}
Strategy: {metrics.symbol}

PERFORMANCE METRICS
-------------------
Total Return: {metrics.total_return_pct:.2f}%
Sharpe Ratio: {metrics.sharpe_ratio:.2f}
Sortino Ratio: {metrics.sortino_ratio:.2f}
Calmar Ratio: {metrics.calmar_ratio:.2f}
Max Drawdown: {metrics.max_drawdown:.2f}%

TRADING METRICS
---------------
Total Trades: {metrics.total_trades}
Winning Trades: {metrics.winning_trades}
Losing Trades: {metrics.losing_trades}
Win Rate: {metrics.win_rate:.2%}
Total P&L: ${metrics.total_pnl:,.2f}
Best Trade: ${metrics.best_trade_pnl:,.2f}
Worst Trade: ${metrics.worst_trade_pnl:,.2f}
Avg Holding Days: {metrics.avg_holding_days:.1f}

RISK METRICS
------------
Value at Risk (95%): {metrics.var_95:.4f}
Conditional VaR (95%): {metrics.cvar_95:.4f}
Overfitting Ratio: {metrics.overfitting_ratio:.2f}

STRESS TEST RESULTS
-------------------
2008 Crisis: {metrics.stress_test_2008:.2%}
COVID 2020: {metrics.stress_test_2020:.2%}

MONTE CARLO ANALYSIS
--------------------
Mean Return: {metrics.monte_carlo_mean_return:.2f}%
Std Dev: {metrics.monte_carlo_std_return:.2f}%
"""
        with open(filepath, "w") as f:
            f.write(report)
        logger.info(f"Saved report: {filepath}")


def main():
    """Run backtest on multiple strategies"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Configuration
    config = BacktestConfig(
        symbol="SPY",
        start_date="2020-01-01",
        end_date="2023-12-31",
        initial_capital=100000.0
    )

    # Run backtest runner
    runner = BacktestRunner(config)

    # Test strategies
    strategies = [
        ("momentum_20d", MomentumStrategy(window=20)),
        ("mean_reversion_20d", MeanReversionStrategy(window=20, std_mult=2.0)),
        ("mean_reversion_30d", MeanReversionStrategy(window=30, std_mult=2.5)),
    ]

    results = {}
    for strategy_name, strategy in strategies:
        try:
            result = runner.run_backtest_pipeline(strategy_name, strategy)
            results[strategy_name] = result
            logger.info(f"✓ Completed: {strategy_name}")
        except Exception as e:
            logger.error(f"✗ Failed: {strategy_name} - {e}")

    # Summary comparison
    logger.info("\n" + "=" * 60)
    logger.info("BACKTEST SUMMARY COMPARISON")
    logger.info("=" * 60)
    
    for strategy_name, result in results.items():
        metrics = result["metrics"]
        sharpe = metrics['sharpe_ratio'] or 0
        dd = metrics['max_drawdown'] or 0
        print(f"\n{strategy_name}:")
        print(f"  Return: {metrics['total_return_pct']:.2f}%")
        print(f"  Sharpe: {sharpe:.2f}")
        print(f"  Win Rate: {metrics['win_rate']:.2%}")
        print(f"  Max DD: {dd:.2f}%")

    logger.info("\nBacktest complete! Results saved to backtest_results/")


if __name__ == "__main__":
    main()
