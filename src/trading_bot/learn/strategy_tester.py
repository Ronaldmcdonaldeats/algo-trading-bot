"""
Strategy Tester: Validates strategy candidates against historical data.

Tests strategies using:
1. Backtesting vs 1-3 year historical data
2. Comparing against S&P 500 benchmark
3. Computing risk-adjusted metrics (Sharpe, Max Drawdown)
4. Determining pass/fail based on >10% outperformance vs S&P 500
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
import numpy as np
import pandas as pd

from trading_bot.learn.strategy_maker import StrategyCandidate, StrategyPerformance
from trading_bot.data.providers import MarketDataProvider, YFinanceProvider
from trading_bot.broker.paper import PaperBroker, PaperBrokerConfig
from trading_bot.core.models import Order

logger = logging.getLogger(__name__)


class StrategyTester:
    """Test strategy candidates against historical data"""
    
    def __init__(
        self,
        data_provider: Optional[MarketDataProvider] = None,
        start_cash: float = 100_000.0,
        benchmark_symbol: str = "SPY",  # S&P 500 ETF
        test_period_days: int = 365,  # 1 year
    ):
        """
        Initialize StrategyTester.
        
        Args:
            data_provider: Market data provider (defaults to YFinance)
            start_cash: Starting portfolio cash
            benchmark_symbol: Symbol to use for benchmark (SPY = S&P 500)
            test_period_days: How many days of history to test on
        """
        self.data_provider = data_provider or YFinanceProvider()
        self.start_cash = float(start_cash)
        self.benchmark_symbol = str(benchmark_symbol)
        self.test_period_days = max(30, int(test_period_days))
        
        logger.info(f"StrategyTester initialized: benchmark={self.benchmark_symbol}, "
                   f"period={self.test_period_days}d, capital=${self.start_cash:,.0f}")
    
    def test_candidate(
        self,
        candidate: StrategyCandidate,
        symbols: List[str],
    ) -> Optional[StrategyPerformance]:
        """
        Test a strategy candidate on historical data.
        
        Args:
            candidate: Strategy to test
            symbols: Symbols to trade
            
        Returns:
            StrategyPerformance with results, or None if test failed
        """
        try:
            # Get historical data
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=self.test_period_days)
            
            logger.info(f"Testing {candidate.name} on {symbols} from {start_date} to {end_date}")
            
            # Download OHLCV data
            ohlcv = self.data_provider.download_bars(
                symbols=symbols + [self.benchmark_symbol],
                period="1y",
                interval="1d",
            )
            
            if ohlcv.empty:
                logger.warning(f"No data available for {symbols}")
                return None
            
            # Run backtest
            equity_curve, trades = self._run_backtest(candidate, ohlcv, symbols)
            
            if not equity_curve:
                logger.warning(f"Backtest produced no equity curve for {candidate.name}")
                return None
            
            # Calculate metrics
            metrics = self._calculate_metrics(equity_curve, trades)
            
            # Get benchmark return
            benchmark_return = self._get_benchmark_return(ohlcv)
            
            # Calculate outperformance
            strategy_return = metrics["total_return"]
            outperformance = strategy_return - benchmark_return
            passed = outperformance >= 10.0  # >10% above benchmark
            
            performance = StrategyPerformance(
                candidate_id=candidate.id,
                total_return=strategy_return,
                sharpe_ratio=metrics["sharpe"],
                max_drawdown=metrics["max_drawdown"],
                win_rate=metrics["win_rate"],
                num_trades=len(trades),
                spx_return=benchmark_return,
                outperformance=outperformance,
                passed=passed,
            )
            
            logger.info(
                f"Completed test for {candidate.name}: "
                f"Return {strategy_return:.1f}%, "
                f"Sharpe {metrics['sharpe']:.2f}, "
                f"MaxDD {metrics['max_drawdown']:.1f}%, "
                f"Outperformance {outperformance:+.1f}% "
                f"({'PASS' if passed else 'FAIL'})"
            )
            
            return performance
        
        except Exception as e:
            logger.error(f"Error testing strategy {candidate.name}: {e}", exc_info=True)
            return None
    
    def _run_backtest(
        self,
        candidate: StrategyCandidate,
        ohlcv: pd.DataFrame,
        symbols: List[str],
    ) -> Tuple[List[float], List[Dict[str, Any]]]:
        """
        Run backtest simulation with candidate parameters.
        
        Returns:
            (equity_curve, trades)
        """
        broker = PaperBroker(
            start_cash=self.start_cash,
            config=PaperBrokerConfig(
                commission_bps=10.0,
                slippage_bps=5.0,
                min_fee=1.0,
            ),
        )
        
        equity_curve = [self.start_cash]
        trades = []
        
        # Simulate trading using strategy parameters
        # For now, use a simple implementation that applies the parameters
        for date_idx in range(1, min(len(ohlcv), 252)):  # Max 1 year of trading days
            
            # Get current prices
            current_row = ohlcv.iloc[date_idx]
            
            for sym in symbols:
                if sym in current_row.index:
                    try:
                        price = float(current_row[sym])
                    except (ValueError, KeyError):
                        continue
                    
                    # Simple strategy: Use candidate parameters to decide
                    signal = self._apply_strategy(candidate.parameters, ohlcv, sym, date_idx)
                    
                    portfolio = broker.portfolio()
                    pos = portfolio.get_position(sym)
                    
                    if signal == 1 and pos.qty == 0:
                        # Buy signal - size based on parameter
                        size_pct = candidate.parameters.get("position_size_pct", 0.05)
                        qty = int((broker.cash() * size_pct) / price)
                        if qty > 0:
                            order = Order(
                                id=f"{date_idx}_{sym}_buy",
                                ts=datetime.now(),
                                symbol=sym,
                                side="BUY",
                                qty=qty,
                                type="MARKET",
                            )
                            result = broker.submit_order(order)
                            if result:
                                trades.append({"symbol": sym, "side": "BUY", "date": date_idx})
                    
                    elif signal == -1 and pos.qty > 0:
                        # Sell signal
                        order = Order(
                            id=f"{date_idx}_{sym}_sell",
                            ts=datetime.now(),
                            symbol=sym,
                            side="SELL",
                            qty=pos.qty,
                            type="MARKET",
                        )
                        result = broker.submit_order(order)
                        if result:
                            trades.append({"symbol": sym, "side": "SELL", "date": date_idx})
            
            # Record equity
            portfolio = broker.portfolio()
            equity = portfolio.equity
            equity_curve.append(equity)
        
        return equity_curve, trades
    
    def _apply_strategy(
        self,
        params: Dict[str, float],
        ohlcv: pd.DataFrame,
        symbol: str,
        current_idx: int,
    ) -> int:
        """
        Apply strategy logic with given parameters.
        
        Returns:
            1 = buy signal, -1 = sell signal, 0 = no signal
        """
        if current_idx < 20:
            return 0  # Not enough history
        
        try:
            # Get recent closes
            close_col = symbol if symbol in ohlcv.columns else None
            if not close_col:
                return 0
            
            closes = ohlcv[close_col].iloc[:current_idx].values
            if len(closes) < 14:
                return 0
            
            # Simple RSI-based strategy using parameters
            rsi = self._calculate_rsi(closes, int(params.get("rsi_period", 14)))
            rsi_buy = params.get("rsi_buy", 30)
            rsi_sell = params.get("rsi_sell", 70)
            
            if rsi < rsi_buy:
                return 1  # Buy signal
            elif rsi > rsi_sell:
                return -1  # Sell signal
            
            return 0
        
        except Exception as e:
            logger.debug(f"Error applying strategy for {symbol}: {e}")
            return 0
    
    @staticmethod
    def _calculate_rsi(prices: np.ndarray, period: int = 14) -> float:
        """Calculate RSI at the end of price series"""
        if len(prices) < period + 1:
            return 50.0  # Neutral
        
        deltas = np.diff(prices[-period-1:])
        gains = deltas.copy()
        losses = deltas.copy()
        
        gains[gains < 0] = 0
        losses[losses > 0] = 0
        losses = -losses
        
        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)
        
        if avg_loss == 0:
            return 100.0 if avg_gain > 0 else 50.0
        
        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return float(rsi)
    
    def _calculate_metrics(self, equity_curve: List[float], trades: List[Dict]) -> Dict[str, float]:
        """Calculate performance metrics from equity curve"""
        if len(equity_curve) < 2:
            return {
                "total_return": 0.0,
                "sharpe": 0.0,
                "max_drawdown": 0.0,
                "win_rate": 0.0,
            }
        
        equity_array = np.array(equity_curve)
        
        # Total return
        total_return = ((equity_array[-1] - equity_array[0]) / equity_array[0]) * 100
        
        # Sharpe ratio
        returns = np.diff(equity_array) / equity_array[:-1]
        sharpe = np.mean(returns) / (np.std(returns) + 1e-8) * np.sqrt(252)
        
        # Max drawdown
        cummax = np.maximum.accumulate(equity_array)
        drawdown = (equity_array - cummax) / (cummax + 1e-8)
        max_drawdown = np.min(drawdown) * 100
        
        # Win rate (simple: % of days with positive return)
        win_days = np.sum(returns > 0)
        win_rate = (win_days / len(returns)) * 100 if len(returns) > 0 else 0.0
        
        return {
            "total_return": float(total_return),
            "sharpe": float(sharpe),
            "max_drawdown": float(max_drawdown),
            "win_rate": float(win_rate),
        }
    
    def _get_benchmark_return(self, ohlcv: pd.DataFrame) -> float:
        """Calculate S&P 500 benchmark return"""
        try:
            if self.benchmark_symbol not in ohlcv.columns:
                logger.warning(f"Benchmark {self.benchmark_symbol} not in data")
                return 0.0
            
            prices = ohlcv[self.benchmark_symbol].dropna()
            if len(prices) < 2:
                return 0.0
            
            return ((prices.iloc[-1] - prices.iloc[0]) / prices.iloc[0]) * 100
        
        except Exception as e:
            logger.error(f"Error calculating benchmark return: {e}")
            return 0.0


class BatchStrategyTester:
    """Test multiple strategy candidates in batch"""
    
    def __init__(self, tester: Optional[StrategyTester] = None):
        """Initialize batch tester"""
        self.tester = tester or StrategyTester()
        self.results: List[StrategyPerformance] = []
    
    def test_batch(
        self,
        candidates: List[StrategyCandidate],
        symbols: List[str],
    ) -> List[StrategyPerformance]:
        """
        Test multiple candidates.
        
        Returns:
            List of performance results (in order of input candidates)
        """
        self.results = []
        
        for i, candidate in enumerate(candidates, 1):
            logger.info(f"[{i}/{len(candidates)}] Testing {candidate.name}...")
            performance = self.tester.test_candidate(candidate, symbols)
            if performance:
                self.results.append(performance)
        
        # Summary
        passed = [r for r in self.results if r.passed]
        logger.info(
            f"Batch complete: {len(passed)}/{len(self.results)} passed, "
            f"avg outperformance: {np.mean([r.outperformance for r in self.results]):.1f}%"
        )
        
        return self.results
    
    def get_passed_candidates(self) -> List[Tuple[StrategyCandidate, StrategyPerformance]]:
        """Get all candidates that passed testing"""
        # This would require access to original candidates
        return [(r.candidate_id, r) for r in self.results if r.passed]
