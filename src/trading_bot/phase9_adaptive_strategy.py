"""
Phase 9: Adaptive Strategy with Market Regime Detection

Combines SMA (trending) and RSI (mean reverting) strategies with automatic
market regime detection. Switches between strategies based on market conditions:
- Bull market (uptrend): Use SMA Crossover (2.6% annual)
- Bear market (downtrend): Use RSI Mean Reversion (2.0% annual + downside protection)
- Sideways (range-bound): Use RSI with tight bands

Market Regime Detection:
- Bull: Price > 200-day MA AND trend strength > 0.5
- Bear: Price < 200-day MA OR trend strength < -0.5
- Sideways: Everything else
"""
import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Dict, Tuple, List
import logging

logger = logging.getLogger(__name__)


@dataclass
class RegimeMetrics:
    """Market regime indicators"""
    regime: str  # 'bull', 'bear', 'sideways'
    trend_strength: float  # -1.0 to 1.0
    volatility: float  # Current volatility %
    ma_200: float  # 200-day moving average
    current_price: float


class MarketRegimeDetector:
    """Detects bull/bear/sideways market conditions"""
    
    def __init__(self, ma_period: int = 200, atr_period: int = 14):
        self.ma_period = ma_period
        self.atr_period = atr_period
    
    def calculate_ma(self, prices: np.ndarray, period: int) -> np.ndarray:
        """Calculate simple moving average"""
        return pd.Series(prices).rolling(window=period).mean().values
    
    def calculate_atr(self, high: np.ndarray, low: np.ndarray, close: np.ndarray,
                     period: int = 14) -> np.ndarray:
        """Calculate Average True Range (volatility)"""
        tr1 = high - low
        tr2 = np.abs(high - np.roll(close, 1))
        tr3 = np.abs(low - np.roll(close, 1))
        
        tr = np.maximum(tr1, np.maximum(tr2, tr3))
        atr = pd.Series(tr).rolling(window=period).mean().values
        
        return atr
    
    def calculate_trend_strength(self, prices: np.ndarray, period: int = 50) -> np.ndarray:
        """
        Calculate trend strength from -1.0 to 1.0
        
        Positive = uptrend, Negative = downtrend
        """
        ma_fast = self.calculate_ma(prices, period // 2)
        ma_slow = self.calculate_ma(prices, period)
        
        # Distance from fast MA to slow MA
        distance = (ma_fast - ma_slow) / (ma_slow + 1e-6)
        
        # Normalize to -1 to 1 range
        trend_strength = np.tanh(distance * 10)  # Tanh squashes to [-1, 1]
        
        return trend_strength
    
    def get_regime(self, df: pd.DataFrame, current_idx: int) -> RegimeMetrics:
        """
        Determine current market regime
        
        Args:
            df: DataFrame with OHLCV data
            current_idx: Current bar index
            
        Returns:
            RegimeMetrics with current regime
        """
        prices = df['Close'].values
        
        # Require minimum data
        if current_idx < self.ma_period:
            return RegimeMetrics(
                regime='sideways',
                trend_strength=0.0,
                volatility=0.01,
                ma_200=prices[current_idx] if current_idx > 0 else prices[0],
                current_price=prices[current_idx]
            )
        
        # Calculate indicators
        ma_200 = self.calculate_ma(prices[:current_idx+1], self.ma_period)[-1]
        trend_strength_arr = self.calculate_trend_strength(prices[:current_idx+1])
        trend_strength = trend_strength_arr[-1] if len(trend_strength_arr) > 0 else 0.0
        
        # Calculate volatility
        returns = np.diff(prices[:current_idx+1]) / prices[:current_idx]
        volatility = np.std(returns[-20:]) if len(returns) >= 20 else 0.015
        
        current_price = prices[current_idx]
        
        # Determine regime
        price_above_ma = current_price > ma_200
        strong_uptrend = trend_strength > 0.5
        strong_downtrend = trend_strength < -0.5
        
        if price_above_ma and strong_uptrend:
            regime = 'bull'
        elif not price_above_ma or strong_downtrend:
            regime = 'bear'
        else:
            regime = 'sideways'
        
        return RegimeMetrics(
            regime=regime,
            trend_strength=float(trend_strength),
            volatility=float(volatility),
            ma_200=float(ma_200),
            current_price=float(current_price)
        )


class AdaptivePhase9Strategy:
    """
    Adaptive strategy that switches between SMA and RSI based on market regime
    
    - Bull market: Use SMA Crossover (trend following)
    - Bear/Sideways: Use RSI Mean Reversion (defensive)
    """
    
    def __init__(self, sma_fast: int = 20, sma_slow: int = 50,
                 rsi_period: int = 14, rsi_oversold: int = 30, rsi_overbought: int = 70):
        self.sma_fast = sma_fast
        self.sma_slow = sma_slow
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        
        self.regime_detector = MarketRegimeDetector()
        self.name = "Adaptive_Phase9"
    
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
        Generate adaptive signals based on market regime
        
        Returns:
            Signal array: 1 = buy, -1 = sell, 0 = hold
        """
        prices = df['Close'].values
        signals = np.zeros(len(df))
        
        # Get indicators
        sma_fast = pd.Series(prices).rolling(window=self.sma_fast).mean().values
        sma_slow = pd.Series(prices).rolling(window=self.sma_slow).mean().values
        rsi = self.calculate_rsi(prices, self.rsi_period)
        
        # Generate signals per regime
        for i in range(self.sma_slow, len(df)):
            # Get current regime
            regime_metrics = self.regime_detector.get_regime(df, i)
            regime = regime_metrics.regime
            
            if regime == 'bull':
                # In bull market: Use SMA crossover (trend following)
                if sma_fast[i] > sma_slow[i] and sma_fast[i-1] <= sma_slow[i-1]:
                    signals[i] = 1  # Buy signal
                elif sma_fast[i] < sma_slow[i] and sma_fast[i-1] >= sma_slow[i-1]:
                    signals[i] = -1  # Sell signal
            
            elif regime == 'bear':
                # In bear market: Use RSI (mean reversion + defensive)
                if rsi[i] < self.rsi_oversold:
                    signals[i] = 1  # Oversold bounce
                elif rsi[i] > self.rsi_overbought:
                    signals[i] = -1  # Overbought sell
            
            else:  # sideways
                # Range-bound: Use RSI with tighter bands
                if rsi[i] < 20:  # Very oversold
                    signals[i] = 1
                elif rsi[i] > 80:  # Very overbought
                    signals[i] = -1
        
        return signals


class Phase9Backtester:
    """Backtests the adaptive Phase 9 strategy"""
    
    def __init__(self, initial_capital: float = 100000, transaction_cost: float = 0.001):
        self.initial_capital = initial_capital
        self.transaction_cost = transaction_cost
        self.strategy = AdaptivePhase9Strategy()
    
    def backtest(self, df: pd.DataFrame, symbol: str = 'Unknown') -> Tuple[float, float, float, float, List]:
        """
        Run backtest of adaptive strategy
        
        Returns:
            total_return, annual_return, max_drawdown, sharpe_ratio, trades
        """
        signals = self.strategy.generate_signals(df)
        prices = df['Close'].values
        
        portfolio = np.ones(len(df)) * self.initial_capital
        position = 0
        entry_price = 0
        trades = []
        
        for i in range(len(df)):
            if signals[i] == 1 and position == 0:
                position = 1
                entry_price = prices[i] * (1 + self.transaction_cost)
                trades.append({
                    'Date': df.index[i],
                    'Type': 'BUY',
                    'Price': prices[i]
                })
            
            elif signals[i] == -1 and position == 1:
                position = 0
                exit_price = prices[i] * (1 - self.transaction_cost)
                ret = (exit_price - entry_price) / entry_price
                portfolio[i:] *= (1 + ret)
                trades.append({
                    'Date': df.index[i],
                    'Type': 'SELL',
                    'Price': prices[i],
                    'Return': ret
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
        
        return total_return, annual_return, max_drawdown, sharpe, trades


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    # Test with sample data
    dates = pd.date_range('2020-01-01', '2025-01-25', freq='D')
    prices = 100 * np.exp(np.cumsum(np.random.normal(0.0003, 0.015, len(dates))))
    
    df = pd.DataFrame({
        'Open': prices,
        'High': prices * 1.01,
        'Low': prices * 0.99,
        'Close': prices,
        'Volume': np.random.uniform(1e6, 10e6, len(dates))
    }, index=dates)
    
    backtester = Phase9Backtester()
    ret, annual, dd, sharpe, trades = backtester.backtest(df, 'TEST')
    
    print(f"\nPhase 9 Adaptive Strategy Results:")
    print(f"  Total Return: {ret:.1%}")
    print(f"  Annual Return: {annual:.1%}")
    print(f"  Max Drawdown: {dd:.1%}")
    print(f"  Sharpe Ratio: {sharpe:.2f}")
    print(f"  Trades: {len([t for t in trades if t['Type'] == 'BUY'])}")
