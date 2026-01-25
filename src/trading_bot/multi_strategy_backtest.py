"""
Multi-Strategy Backtester - 2000-2025

Tests 5 different strategies simultaneously on historical data:
1. RSI Mean Reversion (proved best in Phase 6/7)
2. Simple Mean Reversion
3. Momentum Strategy
4. MACD Strategy
5. Adaptive RSI Learning

Tracks each strategy's performance and learns which works best over time.
"""
import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class StrategyMetrics:
    """Metrics for a single strategy"""
    symbol: str
    strategy_name: str
    total_return: float
    annual_return: float
    max_drawdown: float
    sharpe_ratio: float
    win_rate: float
    trades: int
    avg_trade_return: float
    best_trade: float
    worst_trade: float


class RSIMeanReversionStrategy:
    """RSI-based mean reversion strategy (Phase 6/7 winner)"""
    
    def __init__(self, rsi_period: int = 14, oversold: int = 30, overbought: int = 70,
                 lookback: int = 20):
        self.rsi_period = rsi_period
        self.oversold = oversold
        self.overbought = overbought
        self.lookback = lookback
        self.name = "RSI_MR"
    
    def calculate_rsi(self, prices: np.ndarray, period: int = 14) -> np.ndarray:
        """Calculate RSI"""
        deltas = np.diff(prices)
        seed = deltas[:period+1]
        up = seed[seed >= 0].sum() / period
        down = -seed[seed < 0].sum() / period
        
        rs = up / down if down != 0 else 0
        rsi = np.zeros_like(prices)
        rsi[:period] = 100. - 100. / (1. + rs)
        
        for i in range(period, len(prices)):
            delta = deltas[i - 1]
            if delta > 0:
                up_change = delta
                down_change = 0
            else:
                up_change = 0
                down_change = -delta
            
            up = (up * (period - 1) + up_change) / period
            down = (down * (period - 1) + down_change) / period
            
            rs = up / down if down != 0 else 0
            rsi[i] = 100. - 100. / (1. + rs)
        
        return rsi
    
    def generate_signals(self, df: pd.DataFrame) -> np.ndarray:
        """
        Generate buy/sell signals
        1 = buy, -1 = sell, 0 = hold
        """
        prices = df['Close'].values
        rsi = self.calculate_rsi(prices, self.rsi_period)
        
        signals = np.zeros(len(df))
        
        for i in range(self.rsi_period, len(df)):
            if rsi[i] < self.oversold:
                signals[i] = 1  # Buy
            elif rsi[i] > self.overbought:
                signals[i] = -1  # Sell
        
        return signals


class SimpleMovingAverageStrategy:
    """Simple moving average crossover strategy"""
    
    def __init__(self, fast_ma: int = 20, slow_ma: int = 50):
        self.fast_ma = fast_ma
        self.slow_ma = slow_ma
        self.name = "SMA_Crossover"
    
    def generate_signals(self, df: pd.DataFrame) -> np.ndarray:
        """Generate buy/sell signals from MA crossover"""
        close = df['Close'].values
        fast = pd.Series(close).rolling(window=self.fast_ma).mean().values
        slow = pd.Series(close).rolling(window=self.slow_ma).mean().values
        
        signals = np.zeros(len(df))
        
        for i in range(self.slow_ma, len(df)):
            if fast[i] > slow[i] and fast[i-1] <= slow[i-1]:
                signals[i] = 1  # Crossover up
            elif fast[i] < slow[i] and fast[i-1] >= slow[i-1]:
                signals[i] = -1  # Crossover down
        
        return signals


class MACDStrategy:
    """MACD momentum strategy"""
    
    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9):
        self.fast = fast
        self.slow = slow
        self.signal = signal
        self.name = "MACD"
    
    def generate_signals(self, df: pd.DataFrame) -> np.ndarray:
        """Generate signals from MACD"""
        close = df['Close'].values
        
        # Calculate EMAs
        ema_fast = pd.Series(close).ewm(span=self.fast).mean().values
        ema_slow = pd.Series(close).ewm(span=self.slow).mean().values
        macd = ema_fast - ema_slow
        macd_signal = pd.Series(macd).ewm(span=self.signal).mean().values
        histogram = macd - macd_signal
        
        signals = np.zeros(len(df))
        
        for i in range(1, len(df)):
            if histogram[i] > 0 and histogram[i-1] <= 0:
                signals[i] = 1  # MACD bullish crossover
            elif histogram[i] < 0 and histogram[i-1] >= 0:
                signals[i] = -1  # MACD bearish crossover
        
        return signals


class AdaptiveRSIStrategy:
    """RSI with adaptive parameters that learn"""
    
    def __init__(self, base_period: int = 14, learning_rate: float = 0.01):
        self.base_period = base_period
        self.learning_rate = learning_rate
        self.rsi_period = base_period
        self.oversold = 30
        self.overbought = 70
        self.name = "Adaptive_RSI"
    
    def calculate_rsi(self, prices: np.ndarray, period: int) -> np.ndarray:
        """Calculate RSI with given period"""
        deltas = np.diff(prices)
        seed = deltas[:period+1]
        up = seed[seed >= 0].sum() / period
        down = -seed[seed < 0].sum() / period
        
        rs = up / down if down != 0 else 0
        rsi = np.zeros_like(prices)
        rsi[:period] = 100. - 100. / (1. + rs)
        
        for i in range(period, len(prices)):
            delta = deltas[i - 1]
            up_change = delta if delta > 0 else 0
            down_change = -delta if delta < 0 else 0
            
            up = (up * (period - 1) + up_change) / period
            down = (down * (period - 1) + down_change) / period
            
            rs = up / down if down != 0 else 0
            rsi[i] = 100. - 100. / (1. + rs)
        
        return rsi
    
    def generate_signals(self, df: pd.DataFrame) -> np.ndarray:
        """Generate signals with learning"""
        prices = df['Close'].values
        rsi = self.calculate_rsi(prices, self.rsi_period)
        
        signals = np.zeros(len(df))
        
        # Track wins/losses to adapt parameters
        recent_trades = []
        
        for i in range(self.rsi_period, len(df)):
            # Adapt oversold/overbought based on recent performance
            if len(recent_trades) >= 10:
                win_rate = sum(1 for t in recent_trades[-10:] if t > 0) / 10
                # Tighten thresholds if win rate is high
                adapt_factor = 1.0 + (win_rate - 0.5) * self.learning_rate
                current_oversold = max(10, min(50, 30 / adapt_factor))
                current_overbought = min(90, max(50, 70 * adapt_factor))
            else:
                current_oversold = self.oversold
                current_overbought = self.overbought
            
            if rsi[i] < current_oversold:
                signals[i] = 1
            elif rsi[i] > current_overbought:
                signals[i] = -1
            
            # Track trade result
            if i > 0 and signals[i] != 0:
                price_change = (prices[i] - prices[i-1]) / prices[i-1]
                recent_trades.append(price_change if signals[i] == 1 else -price_change)
        
        return signals


class MultiStrategyBacktester:
    """Backtests multiple strategies simultaneously"""
    
    def __init__(self, initial_capital: float = 100000, transaction_cost: float = 0.001):
        """
        Initialize backtester
        
        Args:
            initial_capital: Starting capital per stock
            transaction_cost: Transaction cost as fraction (0.001 = 0.1%)
        """
        self.initial_capital = initial_capital
        self.transaction_cost = transaction_cost
        self.strategies = [
            RSIMeanReversionStrategy(),
            SimpleMovingAverageStrategy(),
            MACDStrategy(),
            AdaptiveRSIStrategy(),
        ]
    
    def backtest_strategy(self, df: pd.DataFrame, strategy) -> Tuple[np.ndarray, pd.DataFrame]:
        """
        Backtest a single strategy
        
        Returns:
            signals: Buy/sell signals
            trades: DataFrame with trade details
        """
        signals = strategy.generate_signals(df)
        prices = df['Close'].values
        
        trades = []
        position = 0
        entry_price = 0
        
        for i in range(len(df)):
            if signals[i] == 1 and position == 0:  # Buy signal
                position = 1
                entry_price = prices[i]
                trades.append({
                    'Date': df.index[i],
                    'Type': 'BUY',
                    'Price': entry_price,
                    'Signal_Strength': signals[i]
                })
            
            elif signals[i] == -1 and position == 1:  # Sell signal
                position = 0
                exit_price = prices[i]
                ret = (exit_price - entry_price) / entry_price - self.transaction_cost
                trades.append({
                    'Date': df.index[i],
                    'Type': 'SELL',
                    'Price': exit_price,
                    'Return': ret,
                    'Signal_Strength': signals[i]
                })
        
        return signals, pd.DataFrame(trades) if trades else pd.DataFrame()
    
    def calculate_metrics(self, df: pd.DataFrame, strategy, signals: np.ndarray,
                         trades_df: pd.DataFrame) -> StrategyMetrics:
        """Calculate performance metrics for a strategy"""
        symbol = df.index.name if df.index.name else 'Unknown'
        prices = df['Close'].values
        
        # Calculate portfolio value over time
        portfolio = np.ones(len(df)) * self.initial_capital
        position = 0
        entry_price = 0
        
        for i in range(len(df)):
            if signals[i] == 1 and position == 0:
                position = 1
                entry_price = prices[i] * (1 + self.transaction_cost)
            elif signals[i] == -1 and position == 1:
                position = 0
                exit_price = prices[i] * (1 - self.transaction_cost)
                ret = (exit_price - entry_price) / entry_price
                portfolio[i:] *= (1 + ret)
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
        excess_returns = returns - 0.0001  # Risk-free rate ~0.01% daily
        sharpe = np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252) if np.std(excess_returns) > 0 else 0
        
        # Win rate and trade stats
        if len(trades_df) > 0 and 'Return' in trades_df.columns:
            sell_trades = trades_df[trades_df['Type'] == 'SELL']
            if len(sell_trades) > 0:
                returns_list = sell_trades['Return'].values
                win_rate = len(returns_list[returns_list > 0]) / len(returns_list)
                avg_trade = np.mean(returns_list)
                best_trade = np.max(returns_list)
                worst_trade = np.min(returns_list)
            else:
                win_rate = 0
                avg_trade = 0
                best_trade = 0
                worst_trade = 0
        else:
            win_rate = 0
            avg_trade = 0
            best_trade = 0
            worst_trade = 0
        
        return StrategyMetrics(
            symbol=symbol,
            strategy_name=strategy.name,
            total_return=total_return,
            annual_return=annual_return,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe,
            win_rate=win_rate,
            trades=len([t for t in trades_df['Type'].values if t == 'BUY']),
            avg_trade_return=avg_trade,
            best_trade=best_trade,
            worst_trade=worst_trade
        )
    
    def backtest_all(self, df: pd.DataFrame, symbol: str = 'Unknown') -> Dict[str, StrategyMetrics]:
        """Backtest all strategies on one stock"""
        df.index.name = symbol
        results = {}
        
        for strategy in self.strategies:
            signals, trades = self.backtest_strategy(df, strategy)
            metrics = self.calculate_metrics(df, strategy, signals, trades)
            results[strategy.name] = metrics
        
        return results


if __name__ == '__main__':
    # Test with sample data
    import pandas as pd
    
    logging.basicConfig(level=logging.INFO)
    
    # Create sample data
    dates = pd.date_range('2020-01-01', '2025-01-25', freq='D')
    prices = 100 * np.exp(np.cumsum(np.random.normal(0.0003, 0.015, len(dates))))
    
    df = pd.DataFrame({
        'Open': prices,
        'High': prices * 1.01,
        'Low': prices * 0.99,
        'Close': prices,
        'Volume': np.random.uniform(1e6, 10e6, len(dates))
    }, index=dates)
    
    backtester = MultiStrategyBacktester()
    results = backtester.backtest_all(df, 'TEST')
    
    print("\nStrategy Comparison:")
    for strategy_name, metrics in results.items():
        print(f"\n{strategy_name}:")
        print(f"  Return: {metrics.total_return:.1%}")
        print(f"  Annual Return: {metrics.annual_return:.1%}")
        print(f"  Max Drawdown: {metrics.max_drawdown:.1%}")
        print(f"  Sharpe Ratio: {metrics.sharpe_ratio:.2f}")
        print(f"  Win Rate: {metrics.win_rate:.1%}")
        print(f"  Trades: {metrics.trades}")
