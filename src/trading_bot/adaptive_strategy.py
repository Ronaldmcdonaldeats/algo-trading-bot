"""
Adaptive RSI Strategy with Online Learning

Implements a self-optimizing RSI strategy that learns and adapts parameters
for each stock in real-time as it trades.

Key Features:
- Per-stock parameter optimization
- Online learning (updates running mean/variance)
- Adaptive thresholds based on volatility
- Performance tracking for each stock
- Automatic parameter tuning during trading
"""
import numpy as np
import pandas as pd
from typing import Dict, Tuple, Optional, List
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class AdaptiveParameters:
    """Parameters that adapt per stock"""
    rsi_period: int = 14
    buy_threshold: float = 30.0
    sell_threshold: float = 70.0
    volatility_scalar: float = 1.0  # Adjust thresholds based on volatility
    trade_frequency: float = 1.0  # Scale entry signals by frequency
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'rsi_period': self.rsi_period,
            'buy_threshold': self.buy_threshold,
            'sell_threshold': self.sell_threshold,
            'volatility_scalar': self.volatility_scalar,
            'trade_frequency': self.trade_frequency
        }


@dataclass
class OnlineLearningStats:
    """Track learning statistics for online updates"""
    n_samples: int = 0
    mean_return: float = 0.0
    mean_volatility: float = 0.0
    mean_win_rate: float = 0.5
    last_trade_return: float = 0.0
    
    def update(self, trade_return: float, volatility: float) -> None:
        """Update stats with new trade data"""
        n = self.n_samples
        # Running mean update
        self.mean_return = (self.mean_return * n + trade_return) / (n + 1)
        self.mean_volatility = (self.mean_volatility * n + volatility) / (n + 1)
        self.last_trade_return = trade_return
        self.n_samples += 1
        
        # Update win rate
        if trade_return > 0:
            self.mean_win_rate = (self.mean_win_rate * n + 1.0) / (n + 1)
        else:
            self.mean_win_rate = (self.mean_win_rate * n + 0.0) / (n + 1)


class AdaptiveRSIStrategy:
    """RSI strategy that learns and optimizes per stock"""
    
    def __init__(self):
        """Initialize adaptive strategy"""
        self.symbol = None
        self.params = AdaptiveParameters()
        self.learning_stats = OnlineLearningStats()
        self.trade_history: List[Dict] = []
        
        # Cache for running calculations
        self._rsi_cache = None
        self._price_cache = None
        self._last_signal = 0
    
    def set_symbol(self, symbol: str) -> None:
        """Set symbol for this strategy instance"""
        self.symbol = symbol
        logger.debug(f"AdaptiveRSI initialized for {symbol}")
    
    def _calculate_rsi(self, prices: pd.Series, period: Optional[int] = None) -> np.ndarray:
        """Calculate RSI with adaptive period"""
        period = period or self.params.rsi_period
        
        if len(prices) < period:
            return np.full(len(prices), 50.0)
        
        deltas = prices.diff()
        seed = deltas[:period+1]
        up = seed[seed >= 0].sum() / period
        down = -seed[seed < 0].sum() / period
        rs = up / down if down != 0 else 0
        
        rsi = np.zeros(len(prices))
        rsi[:period] = 100.0 - 100.0 / (1.0 + rs) if rs > 0 else 50
        
        for i in range(period, len(prices)):
            delta = deltas.iloc[i]
            if delta > 0:
                upval = delta
                downval = 0.
            else:
                upval = 0.
                downval = -delta
            
            up = (up * (period - 1) + upval) / period
            down = (down * (period - 1) + downval) / period
            
            rs = up / down if down != 0 else 0
            rsi[i] = 100.0 - 100.0 / (1.0 + rs) if rs > 0 else 50
        
        return rsi
    
    def calculate_adaptive_thresholds(self, volatility: float) -> Tuple[float, float]:
        """
        Calculate adaptive buy/sell thresholds based on volatility
        
        High volatility → wider thresholds (less frequent trading)
        Low volatility → tighter thresholds (more frequent trading)
        """
        # Normalize volatility to 0-1 range (typical 0.01 to 0.05)
        vol_factor = min(max(volatility / 0.02, 0.5), 2.0)
        
        buy = self.params.buy_threshold - (30 - self.params.buy_threshold) * (vol_factor - 1)
        sell = self.params.sell_threshold + (100 - self.params.sell_threshold) * (vol_factor - 1)
        
        return buy, sell
    
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Generate trading signals with online learning
        
        Args:
            data: OHLCV dataframe with columns: Close, High, Low, Volume
            
        Returns:
            DataFrame with 'signal' column (1=buy, -1=sell, 0=hold)
        """
        data = data.copy()
        
        # Calculate RSI
        rsi = self._calculate_rsi(data['Close'])
        data['rsi'] = rsi
        
        # Calculate volatility
        returns = data['Close'].pct_change()
        volatility = returns.rolling(20).std()
        data['volatility'] = volatility
        
        # Get adaptive thresholds
        current_vol = volatility.iloc[-1] if not volatility.isna().all() else 0.02
        buy_thresh, sell_thresh = self.calculate_adaptive_thresholds(current_vol)
        
        data['signal'] = 0
        
        # Buy signals (oversold)
        buy_mask = rsi < buy_thresh
        data.loc[buy_mask, 'signal'] = 1
        
        # Sell signals (overbought)
        sell_mask = rsi > sell_thresh
        data.loc[sell_mask, 'signal'] = -1
        
        # Cache for learning
        self._rsi_cache = rsi
        self._price_cache = data['Close'].values
        
        return data
    
    def adapt_parameters(self, trade_return: float, volatility: float) -> None:
        """
        Adapt strategy parameters based on trade outcome
        
        This runs after each trade to optimize future trading
        
        Args:
            trade_return: Return of the completed trade (%)
            volatility: Current market volatility
        """
        # Update learning statistics
        self.learning_stats.update(trade_return, volatility)
        
        n = self.learning_stats.n_samples
        
        # Adapt RSI period based on win rate
        # Lower period (faster) if high win rate, higher period (slower) if low
        win_rate = self.learning_stats.mean_win_rate
        if win_rate > 0.7:  # Winning consistently
            self.params.rsi_period = max(10, self.params.rsi_period - 1)
        elif win_rate < 0.4:  # Losing frequently
            self.params.rsi_period = min(21, self.params.rsi_period + 1)
        
        # Adapt thresholds based on recent returns
        recent_return = self.learning_stats.mean_return
        if recent_return > 0.01:  # Making money
            # Tighten thresholds to trade more
            self.params.buy_threshold = min(35, self.params.buy_threshold + 0.5)
            self.params.sell_threshold = max(65, self.params.sell_threshold - 0.5)
        elif recent_return < -0.005:  # Losing money
            # Loosen thresholds to trade less (more selective)
            self.params.buy_threshold = max(20, self.params.buy_threshold - 0.5)
            self.params.sell_threshold = min(80, self.params.sell_threshold + 0.5)
        
        # Adapt based on volatility
        self.params.volatility_scalar = volatility / 0.02  # Normalize to 0.02 baseline
        
        logger.debug(
            f"{self.symbol} - Adapted: RSI={self.params.rsi_period}, "
            f"Buy={self.params.buy_threshold:.1f}, Sell={self.params.sell_threshold:.1f}, "
            f"WR={self.learning_stats.mean_win_rate:.2%}, Ret={self.learning_stats.mean_return:.2%}"
        )
    
    def log_trade(self, entry_price: float, exit_price: float, 
                  entry_date: datetime, exit_date: datetime) -> None:
        """Log trade for learning purposes"""
        trade_return = (exit_price - entry_price) / entry_price
        days_held = (exit_date - entry_date).days
        
        self.trade_history.append({
            'entry_price': entry_price,
            'exit_price': exit_price,
            'return': trade_return,
            'entry_date': entry_date,
            'exit_date': exit_date,
            'days_held': days_held
        })
    
    def get_performance_summary(self) -> Dict:
        """Get current performance summary for this symbol"""
        if not self.trade_history:
            return {}
        
        trades = self.trade_history
        returns = [t['return'] for t in trades]
        
        total_return = np.prod([1 + r for r in returns]) - 1
        win_count = sum(1 for r in returns if r > 0)
        win_rate = win_count / len(returns)
        
        return {
            'total_trades': len(trades),
            'total_return': total_return,
            'win_rate': win_rate,
            'avg_return': np.mean(returns),
            'sharpe': np.mean(returns) / np.std(returns) if np.std(returns) > 0 else 0,
            'max_drawdown': min(returns) if returns else 0,
            'current_params': self.params.to_dict()
        }


class AdaptiveStrategyEnsemble:
    """Manages adaptive strategies for multiple stocks"""
    
    def __init__(self, symbols: List[str]):
        """
        Initialize ensemble
        
        Args:
            symbols: List of symbols to trade
        """
        self.strategies = {}
        for symbol in symbols:
            strategy = AdaptiveRSIStrategy()
            strategy.set_symbol(symbol)
            self.strategies[symbol] = strategy
    
    def generate_all_signals(self, data_dict: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        """
        Generate signals for all symbols
        
        Args:
            data_dict: Dict of symbol -> OHLCV DataFrame
            
        Returns:
            Dict of symbol -> DataFrame with signals
        """
        results = {}
        for symbol, data in data_dict.items():
            if symbol in self.strategies:
                results[symbol] = self.strategies[symbol].generate_signals(data)
        return results
    
    def adapt_all(self, trade_results: Dict[str, Dict]) -> None:
        """
        Adapt all strategies based on trade results
        
        Args:
            trade_results: Dict of symbol -> {return, volatility}
        """
        for symbol, result in trade_results.items():
            if symbol in self.strategies:
                self.strategies[symbol].adapt_parameters(
                    result['return'],
                    result['volatility']
                )
    
    def get_all_performance(self) -> Dict[str, Dict]:
        """Get performance summary for all symbols"""
        return {
            symbol: strategy.get_performance_summary()
            for symbol, strategy in self.strategies.items()
        }


if __name__ == '__main__':
    # Example usage
    strategy = AdaptiveRSIStrategy()
    strategy.set_symbol('AAPL')
    
    # Simulate some trades
    for i in range(10):
        return_pct = np.random.normal(0.001, 0.02)
        vol = np.random.uniform(0.01, 0.03)
        strategy.adapt_parameters(return_pct, vol)
    
    summary = strategy.get_performance_summary()
    print(f"\nPerformance Summary:")
    print(f"  Trades: {summary.get('total_trades', 0)}")
    print(f"  Win Rate: {summary.get('win_rate', 0):.1%}")
    print(f"  Avg Return: {summary.get('avg_return', 0):.2%}")
