"""
Phase 10: Bayesian Optimizer + Multi-Strategy Combiner
- Tunes Phase 9 parameters (SMA periods, RSI thresholds, MA window)
- Adds MACD momentum and Bollinger Bands for additional signals
- Blends multiple strategies with weighted voting
- Target: Beat S&P 500 by 5% (6.1% annual return)
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Tuple, List


@dataclass
class PhasePhase10Config:
    """Tunable parameters for Phase 10 optimizer"""
    # Regime detection
    ma_window: int = 200  # Moving average window for regime
    trend_threshold: float = 0.5  # Trend strength threshold
    volatility_factor: float = 1.0  # Volatility scaling
    
    # SMA Crossover (for bull markets)
    sma_fast: int = 20
    sma_slow: int = 50
    sma_weight: float = 0.4  # Weight in ensemble
    
    # RSI Mean Reversion (for bear/sideways)
    rsi_oversold: int = 30
    rsi_overbought: int = 70
    rsi_window: int = 14
    rsi_weight: float = 0.3
    
    # MACD Momentum (new)
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    macd_weight: float = 0.2
    
    # Bollinger Bands (new)
    bb_window: int = 20
    bb_std_dev: float = 2.0
    bb_weight: float = 0.1
    
    # Risk management
    position_size: float = 0.95  # % of capital per trade
    stop_loss_pct: float = 0.05  # 5% stop loss
    take_profit_pct: float = 0.15  # 15% take profit


class MarketRegimeDetectorV2:
    """Enhanced regime detector with volatility consideration"""
    
    def __init__(self, config: PhasePhase10Config):
        self.config = config
    
    def calculate_volatility(self, prices: np.ndarray, window: int = 20) -> float:
        """Calculate volatility as rolling std dev of returns"""
        if len(prices) < window:
            return 0.0
        returns = np.diff(np.log(prices[-window:]))
        return float(np.std(returns))
    
    def calculate_ma(self, prices: np.ndarray, window: int) -> float:
        """Simple moving average"""
        if len(prices) < window:
            return prices[-1]
        return float(np.mean(prices[-window:]))
    
    def calculate_trend_strength(self, prices: np.ndarray) -> float:
        """Trend strength from -1 to 1 using slope over last 50 days"""
        if len(prices) < 50:
            return 0.0
        recent = prices[-50:]
        x = np.arange(len(recent))
        slope = np.polyfit(x, recent, 1)[0]
        # Normalize: divide by average price to get % change
        avg_price = np.mean(recent)
        trend_pct = slope / avg_price if avg_price > 0 else 0
        # Tanh to bound between -1 and 1
        return float(np.tanh(trend_pct * 10))
    
    def get_regime(self, prices: np.ndarray) -> Tuple[str, float, float, float]:
        """
        Returns (regime, trend_strength, volatility, ma_value)
        - regime: 'bull', 'bear', or 'sideways'
        - trend_strength: -1 to 1
        - volatility: annualized volatility
        - ma_value: moving average value
        """
        if len(prices) < self.config.ma_window:
            return 'sideways', 0.0, 0.0, prices[-1]
        
        ma = self.calculate_ma(prices, self.config.ma_window)
        trend = self.calculate_trend_strength(prices)
        volatility = self.calculate_volatility(prices) * np.sqrt(252)  # Annualize
        current_price = prices[-1]
        
        # Regime classification
        price_above_ma = current_price > ma
        strong_trend = abs(trend) > self.config.trend_threshold
        
        if price_above_ma and trend > self.config.trend_threshold:
            regime = 'bull'
        elif not price_above_ma or trend < -self.config.trend_threshold:
            regime = 'bear'
        else:
            regime = 'sideways'
        
        return regime, trend, volatility, ma


class Phase10Strategy:
    """Multi-strategy combiner with regime-based weighting"""
    
    def __init__(self, config: PhasePhase10Config):
        self.config = config
        self.regime_detector = MarketRegimeDetectorV2(config)
    
    def calculate_sma_signal(self, prices: np.ndarray) -> float:
        """SMA Crossover signal (-1, 0, 1)"""
        if len(prices) < self.config.sma_slow:
            return 0.0
        
        fast_ma = np.mean(prices[-self.config.sma_fast:])
        slow_ma = np.mean(prices[-self.config.sma_slow:])
        
        if fast_ma > slow_ma:
            return 1.0
        elif fast_ma < slow_ma:
            return -1.0
        return 0.0
    
    def calculate_rsi(self, prices: np.ndarray, window: int = 14) -> float:
        """Relative Strength Index"""
        if len(prices) < window + 1:
            return 50.0
        
        deltas = np.diff(prices[-window-1:])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)
        
        if avg_loss == 0:
            return 100.0 if avg_gain > 0 else 50.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return float(rsi)
    
    def calculate_rsi_signal(self, prices: np.ndarray, regime: str) -> float:
        """RSI signal based on regime"""
        rsi = self.calculate_rsi(prices, self.config.rsi_window)
        
        if regime == 'bear':
            # Mean reversion in bear market
            if rsi < self.config.rsi_oversold:
                return 1.0
            elif rsi > self.config.rsi_overbought:
                return -1.0
        elif regime == 'sideways':
            # Tight bands in sideways market
            if rsi < 20:
                return 1.0
            elif rsi > 80:
                return -1.0
        
        return 0.0
    
    def calculate_macd(self, prices: np.ndarray) -> Tuple[float, float, float]:
        """MACD indicator: (MACD line, Signal line, Histogram)"""
        if len(prices) < self.config.macd_slow + self.config.macd_signal:
            return 0.0, 0.0, 0.0
        
        ema_fast = self._ema(prices, self.config.macd_fast)
        ema_slow = self._ema(prices, self.config.macd_slow)
        macd_line = ema_fast - ema_slow
        
        # Signal line is EMA of MACD
        macd_values = np.array([
            self._ema(prices[:i], self.config.macd_fast) - 
            self._ema(prices[:i], self.config.macd_slow)
            for i in range(self.config.macd_slow, len(prices))
        ])
        
        if len(macd_values) < self.config.macd_signal:
            signal_line = macd_line
        else:
            signal_line = np.mean(macd_values[-self.config.macd_signal:])
        
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram
    
    def _ema(self, prices: np.ndarray, window: int) -> float:
        """Exponential Moving Average"""
        if len(prices) < window:
            return np.mean(prices)
        
        alpha = 2 / (window + 1)
        ema = prices[0]
        for price in prices[1:]:
            ema = alpha * price + (1 - alpha) * ema
        return ema
    
    def calculate_macd_signal(self, prices: np.ndarray) -> float:
        """MACD momentum signal (-1, 0, 1)"""
        macd, signal, histogram = self.calculate_macd(prices)
        
        if histogram > 0 and macd > signal:
            return 1.0
        elif histogram < 0 and macd < signal:
            return -1.0
        return 0.0
    
    def calculate_bollinger_bands(self, prices: np.ndarray) -> Tuple[float, float, float]:
        """Bollinger Bands: (upper, middle, lower)"""
        if len(prices) < self.config.bb_window:
            mid = np.mean(prices)
            return mid, mid, mid
        
        mid = np.mean(prices[-self.config.bb_window:])
        std = np.std(prices[-self.config.bb_window:])
        upper = mid + (self.config.bb_std_dev * std)
        lower = mid - (self.config.bb_std_dev * std)
        
        return upper, mid, lower
    
    def calculate_bb_signal(self, prices: np.ndarray) -> float:
        """Bollinger Bands mean reversion signal"""
        upper, mid, lower = self.calculate_bollinger_bands(prices)
        current = prices[-1]
        
        if current < lower:
            return 1.0  # Oversold, buy signal
        elif current > upper:
            return -1.0  # Overbought, sell signal
        return 0.0
    
    def generate_signal(self, prices: np.ndarray) -> Tuple[float, str, dict]:
        """
        Generate weighted ensemble signal
        Returns (signal, regime, debug_info)
        """
        regime, trend, volatility, ma_val = self.regime_detector.get_regime(prices)
        
        # Collect signals from all strategies
        sma_sig = self.calculate_sma_signal(prices)
        rsi_sig = self.calculate_rsi_signal(prices, regime)
        macd_sig = self.calculate_macd_signal(prices)
        bb_sig = self.calculate_bb_signal(prices)
        
        # Weighted ensemble (normalize weights)
        total_weight = (self.config.sma_weight + self.config.rsi_weight + 
                       self.config.macd_weight + self.config.bb_weight)
        
        weighted_signal = (
            (sma_sig * self.config.sma_weight) +
            (rsi_sig * self.config.rsi_weight) +
            (macd_sig * self.config.macd_weight) +
            (bb_sig * self.config.bb_weight)
        ) / total_weight
        
        # Convert to -1, 0, or 1
        if weighted_signal > 0.3:
            final_signal = 1.0
        elif weighted_signal < -0.3:
            final_signal = -1.0
        else:
            final_signal = 0.0
        
        debug_info = {
            'regime': regime,
            'trend_strength': trend,
            'volatility': volatility,
            'sma_signal': sma_sig,
            'rsi_signal': rsi_sig,
            'macd_signal': macd_sig,
            'bb_signal': bb_sig,
            'weighted_signal': weighted_signal,
            'ma_value': ma_val
        }
        
        return final_signal, regime, debug_info


class Phase10Backtester:
    """Backtest Phase 10 strategy"""
    
    def __init__(self, config: PhasePhase10Config, initial_capital: float = 100000):
        self.config = config
        self.strategy = Phase10Strategy(config)
        self.initial_capital = initial_capital
    
    def backtest(self, prices: np.ndarray) -> Tuple[float, float, float, float, int]:
        """
        Run backtest
        Returns (total_return, annual_return, max_drawdown, sharpe_ratio, num_trades)
        """
        capital = self.initial_capital
        position = 0  # 0=cash, 1=long
        entry_price = 0
        trades = 0
        equity_curve = [capital]
        
        for i in range(100, len(prices)):  # Start after enough data
            price = prices[i]
            signal, regime, debug_info = self.strategy.generate_signal(prices[:i+1])
            
            # Simple position management
            if position == 0 and signal > 0:
                # Enter long
                position_amount = capital * self.config.position_size
                position = position_amount / price
                entry_price = price
                trades += 1
            
            elif position > 0:
                # Check exit conditions
                unrealized_pnl = (price - entry_price) / entry_price
                
                # Stop loss or take profit
                if unrealized_pnl < -self.config.stop_loss_pct:
                    capital = position * price  # Exit at loss
                    position = 0
                    trades += 1
                elif unrealized_pnl > self.config.take_profit_pct:
                    capital = position * price  # Exit at profit
                    position = 0
                    trades += 1
                # Signal-based exit
                elif signal < 0:
                    capital = position * price
                    position = 0
                    trades += 1
            
            # Update equity
            if position > 0:
                equity = capital + (position * price)
            else:
                equity = capital
            
            equity_curve.append(equity)
        
        # Close position if open
        if position > 0:
            capital = position * prices[-1]
        
        # Calculate metrics
        final_capital = capital
        total_return = (final_capital - self.initial_capital) / self.initial_capital
        
        # Annual return (25 years)
        years = 25
        annual_return = (final_capital / self.initial_capital) ** (1/years) - 1
        
        # Max drawdown
        equity_array = np.array(equity_curve)
        running_max = np.maximum.accumulate(equity_array)
        drawdown = (equity_array - running_max) / running_max
        max_drawdown = float(np.min(drawdown))
        
        # Sharpe ratio
        returns = np.diff(equity_array) / equity_array[:-1]
        sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0
        
        return total_return, annual_return, max_drawdown, sharpe, trades
