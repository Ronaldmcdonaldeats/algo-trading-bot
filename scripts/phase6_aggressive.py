"""
Phase 6 AGGRESSIVE OPTIMIZATION - Beat S&P 500
Based on backtest data: RSI(14) works, Momentum is broken, Mean Reversion works with modifications
"""

import numpy as np
import pandas as pd


class AgggressivePhase6System:
    """
    Most aggressive Phase 6 system to beat S&P 500
    
    Strategy:
    1. Use RSI but be LESS selective (lower oversold threshold)
    2. Add mean reversion for stable entries
    3. Use volatility-adjusted exits
    4. Combine with trend bias
    5. Scale positions by confidence
    """

    def __init__(self):
        self.name = "Phase6_Aggressive"

    def generate_signals(self, data):
        """Generate signals optimized to beat S&P 500"""
        data = data.copy()
        
        # ===== INDICATOR 1: RSI (Proven Winner) =====
        rsi = self._calculate_rsi(data['Close'], window=14)
        
        # ===== INDICATOR 2: Simple Moving Average Trend =====
        sma_50 = data['Close'].rolling(50).mean()
        sma_200 = data['Close'].rolling(200).mean()
        in_uptrend = data['Close'] > sma_50
        strong_uptrend = sma_50 > sma_200
        
        # ===== INDICATOR 3: Momentum (simple price change) =====
        momentum = data['Close'].pct_change(10)  # 10-day momentum
        
        # ===== INDICATOR 4: Volume (confirm moves) =====
        avg_volume = data['Volume'].rolling(20).mean()
        volume_spike = data['Volume'] > avg_volume
        
        # ===== SIGNAL GENERATION =====
        data['signal'] = 0
        data['confidence'] = 0.0
        
        # BUY SIGNAL 1: RSI oversold + uptrend
        buy1 = (rsi < 40) & in_uptrend
        data.loc[buy1, 'signal'] = 1
        data.loc[buy1, 'confidence'] = 0.6
        
        # BUY SIGNAL 2: Strong oversold + volume
        buy2 = (rsi < 30) & volume_spike
        data.loc[buy2, 'signal'] = 1
        data.loc[buy2, 'confidence'] = 0.8
        
        # BUY SIGNAL 3: Strong momentum + in uptrend
        buy3 = (momentum > 0.02) & strong_uptrend
        data.loc[buy3, 'signal'] = 1
        data.loc[buy3, 'confidence'] = 0.7
        
        # EXIT SIGNAL: RSI overbought OR downtrend
        exit_signal = (rsi > 70) | (data['Close'] < sma_50)
        data.loc[exit_signal, 'signal'] = 0
        
        # Time-based exit: max 20 days holding
        data['holding_days'] = 0
        position_started = None
        
        for idx in range(len(data)):
            if data.iloc[idx]['signal'] == 1 and position_started is None:
                position_started = idx
            elif position_started is not None:
                days_held = idx - position_started
                data.iloc[idx, data.columns.get_loc('holding_days')] = days_held
                
                if days_held >= 20:
                    data.iloc[idx, data.columns.get_loc('signal')] = 0
                    position_started = None
        
        return data

    @staticmethod
    def _calculate_rsi(prices, window=14):
        """Calculate RSI"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi


class DynamicPositionSizing:
    """Scale positions based on market conditions"""
    
    @staticmethod
    def calculate_size(confidence, volatility):
        """
        Position size based on confidence and volatility
        
        High confidence + Low vol = larger position (up to 100%)
        Low confidence + High vol = smaller position (down to 25%)
        """
        vol_factor = np.exp(-volatility * 10)  # Higher vol = smaller position
        size = confidence * vol_factor
        return np.clip(size, 0.25, 1.0)  # Between 25% and 100%


class Phase6OptimizedBacktester:
    """Backtest Phase 6 aggressive system"""

    def __init__(self, symbol="SPY", days=1260):
        self.symbol = symbol
        self.days = days
        self.system = AgggressivePhase6System()
        self.data = None

    def fetch_synthetic_data(self):
        """Generate synthetic data"""
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent))
        from real_data_backtest import SyntheticMarketGenerator
        
        print(f"[DATA] Generating synthetic {self.symbol} data...")
        
        if self.symbol == "SPY":
            self.data = SyntheticMarketGenerator.generate_price_series(
                symbol=self.symbol, days=self.days, volatility=0.15, drift=0.10, initial_price=200
            )
        elif self.symbol == "QQQ":
            self.data = SyntheticMarketGenerator.generate_price_series(
                symbol=self.symbol, days=self.days, volatility=0.22, drift=0.12, initial_price=250
            )
        elif self.symbol == "IWM":
            self.data = SyntheticMarketGenerator.generate_price_series(
                symbol=self.symbol, days=self.days, volatility=0.20, drift=0.11, initial_price=150
            )
        else:
            self.data = SyntheticMarketGenerator.generate_price_series(
                symbol=self.symbol, days=self.days, volatility=0.10, drift=0.04, initial_price=95
            )
        
        print(f"[OK] Generated {len(self.data)} days")
        return self.data

    def backtest(self):
        """Run backtest"""
        if self.data is None:
            self.fetch_synthetic_data()
        
        print(f"[TEST] Phase 6 Aggressive System on {self.symbol}...")
        
        data = self.data.copy()
        data = self.system.generate_signals(data)
        
        # Calculate volatility for position sizing
        data['volatility'] = data['Close'].pct_change().rolling(20).std()
        
        # Position sizing
        data['position_size'] = data.apply(
            lambda row: DynamicPositionSizing.calculate_size(
                row['confidence'], row['volatility']
            ) if row['signal'] == 1 else 1.0,
            axis=1
        )
        
        # Strategy returns (with position sizing)
        data['daily_return'] = data['Close'].pct_change()
        data['strategy_return'] = (
            data['signal'].shift(1) * 
            data['position_size'].shift(1) * 
            data['daily_return']
        )
        data['cumulative_return'] = (1 + data['strategy_return']).cumprod()
        
        # B&H returns
        data['bh_cumulative'] = (1 + data['daily_return']).cumprod()
        
        return self._calculate_metrics(data)

    def _calculate_metrics(self, data):
        """Calculate metrics"""
        data = data.dropna()
        
        strategy_return = (data['cumulative_return'].iloc[-1] - 1) * 100
        bh_return = (data['bh_cumulative'].iloc[-1] - 1) * 100
        
        winning = len(data[data['strategy_return'] > 0])
        total = len(data)
        win_rate = (winning / total * 100) if total > 0 else 0
        
        sharpe = self._sharpe(data['strategy_return'])
        sortino = self._sortino(data['strategy_return'])
        max_dd = self._max_drawdown(data['cumulative_return'])
        bh_max_dd = self._max_drawdown(data['bh_cumulative'])
        
        return {
            'symbol': self.symbol,
            'strategy_return': round(strategy_return, 2),
            'bh_return': round(bh_return, 2),
            'outperformance': round(strategy_return - bh_return, 2),
            'win_rate': round(win_rate, 2),
            'sharpe': round(sharpe, 2),
            'sortino': round(sortino, 2),
            'max_dd': round(max_dd * 100, 2),
            'bh_max_dd': round(bh_max_dd * 100, 2),
            'beats_bh': strategy_return > bh_return
        }

    @staticmethod
    def _sharpe(returns, rf=0.02):
        excess = returns - (rf / 252)
        return (excess.mean() / excess.std() * np.sqrt(252)) if excess.std() > 0 else 0

    @staticmethod
    def _sortino(returns, rf=0.02):
        excess = returns - (rf / 252)
        down = returns[returns < 0].std()
        return (excess.mean() / down * np.sqrt(252)) if down > 0 else 0

    @staticmethod
    def _max_drawdown(cum_returns):
        running_max = cum_returns.expanding().max()
        dd = (cum_returns - running_max) / running_max
        return dd.min()


def main():
    """Run Phase 6 aggressive backtest"""
    print("\n" + "=" * 120)
    print("[PHASE 6] AGGRESSIVE OPTIMIZATION - BEAT S&P 500")
    print("=" * 120)
    print("Strategy: Combined RSI + Momentum + Trend + Dynamic Position Sizing")
    print("=" * 120 + "\n")
    
    symbols = ["SPY", "QQQ", "IWM", "TLT"]
    results = []
    
    for symbol in symbols:
        backtester = Phase6OptimizedBacktester(symbol=symbol, days=1260)
        result = backtester.backtest()
        results.append(result)
    
    # Print results
    print("\n" + "=" * 120)
    print("RESULTS")
    print("=" * 120)
    print(f"{'Symbol':<8} {'Return %':<12} {'B&H Ret %':<12} {'Outperf %':<12} {'Sharpe':<8} {'Win %':<8} {'Beats B&H':<10}")
    print("-" * 120)
    
    for r in results:
        beats = "YES [+]" if r['beats_bh'] else "NO [-]"
        print(
            f"{r['symbol']:<8} "
            f"{r['strategy_return']:>10.2f}% "
            f"{r['bh_return']:>10.2f}% "
            f"{r['outperformance']:>10.2f}% "
            f"{r['sharpe']:>6.2f} "
            f"{r['win_rate']:>6.2f}% "
            f"{beats:<10}"
        )
    
    # Summary
    beats_count = sum(1 for r in results if r['beats_bh'])
    avg_return = np.mean([r['strategy_return'] for r in results])
    avg_outperf = np.mean([r['outperformance'] for r in results])
    
    print("=" * 120)
    print(f"\nSUMMARY:")
    print(f"  Beating S&P 500: {beats_count}/4 assets")
    print(f"  Average return: {avg_return:.2f}%")
    print(f"  Average outperformance: {avg_outperf:+.2f}%")
    
    if beats_count >= 3:
        print(f"\n[SUCCESS] Phase 6 WINS - Beats S&P 500 on {beats_count} out of 4 assets!")
    elif beats_count >= 2:
        print(f"\n[GOOD] Phase 6 is competitive - Beats S&P 500 on {beats_count} out of 4 assets")
    else:
        print(f"\n[NEEDS WORK] Phase 6 still underperforming - Only beats {beats_count}/4 assets")
    
    print("=" * 120 + "\n")


if __name__ == "__main__":
    main()
