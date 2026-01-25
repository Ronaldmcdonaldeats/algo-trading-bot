"""
Phase 6 Trend-Riding Approach - Hold Uptrends, Sidestep Downtrends

KEY INSIGHT: 
Looking at B&H returns vs trading returns:
- B&H SPY: +25.7%, Our trading: +9.9% (we're missing 16% of the upside)
- This means we're EXITING during uptrends
- Solution: Only exit on clear trend reversal, not on technical signals

NEW STRATEGY:
1. Enter: When price > SMA200 (in long-term uptrend) AND RSI < 60
2. Stay invested: HOLD while price > SMA50 (strong uptrend)
3. Exit ONLY: When price falls below SMA50 (trend reversal)
4. NO selling on RSI overbought (we're leaving money on table)

This "trend-ride" approach should capture bull markets better.
"""
import sys
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

sys.path.insert(0, r'c:\Users\Ronald mcdonald\projects\algo-trading-bot')

class TrendRidingStrategy:
    """Buy and hold in uptrends, exit on downtrend"""
    
    def __init__(self, symbol="SPY"):
        self.symbol = symbol
        self.trades = []
        
    def _calculate_rsi(self, prices, period=14):
        """Calculate RSI"""
        deltas = prices.diff()
        seed = deltas[:period+1]
        up = seed[seed >= 0].sum() / period
        down = -seed[seed < 0].sum() / period
        rs = up / down if down != 0 else 0
        
        rsi = np.zeros_like(prices)
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
        
        return pd.Series(rsi, index=prices.index)
    
    def generate_signals(self, data):
        """Generate signals"""
        data = data.copy()
        
        # Calculate indicators
        sma50 = data['Close'].rolling(50).mean()
        sma200 = data['Close'].rolling(200).mean()
        rsi = self._calculate_rsi(data['Close'], period=14)
        
        data['rsi'] = rsi
        data['sma50'] = sma50
        data['sma200'] = sma200
        
        # Entry conditions:
        # 1. Price above 200-day MA (long-term uptrend)
        # 2. RSI not too overbought (< 80)
        entry = (data['Close'] > sma200) & (rsi < 80)
        
        # Exit condition:
        # Close below 50-day MA = trend reversal
        exit_signal = (data['Close'] < sma50)
        
        data['signal'] = 0
        
        # Mark entry points
        data.loc[entry, 'signal'] = 1
        
        # Mark exit points (override)
        data.loc[exit_signal, 'signal'] = -1
        
        return data
    
    def backtest(self, data):
        """Run backtest - simplified one entry/exit"""
        signals = self.generate_signals(data)
        
        cash = 100000
        position = 0
        entry_price = 0
        equity = [cash]
        
        for idx in range(len(signals)):
            price = signals['Close'].iloc[idx]
            signal = signals['signal'].iloc[idx]
            
            # Entry: Only if not already in position
            if signal == 1 and position == 0:
                position = cash / price
                entry_price = price
                cash = 0
                self.trades.append({'date': idx, 'type': 'BUY', 'price': price})
            
            # Exit: If we get exit signal AND in position
            elif signal == -1 and position > 0:
                cash = position * price
                profit_pct = (price - entry_price) / entry_price
                self.trades.append({
                    'date': idx, 'type': 'SELL', 'price': price,
                    'profit_pct': profit_pct
                })
                position = 0
                entry_price = 0
            
            # Update equity
            current_equity = cash + (position * price if position > 0 else 0)
            equity.append(current_equity)
        
        # Close any open position at end
        if position > 0:
            final_price = signals['Close'].iloc[-1]
            cash = position * final_price
            current_equity = cash
            equity.append(current_equity)
        
        final_equity = equity[-1]
        total_return = (final_equity - 100000) / 100000
        buy_hold = (signals['Close'].iloc[-1] / signals['Close'].iloc[0] - 1)
        
        return {
            'total_return': total_return,
            'buy_hold': buy_hold,
            'trades': len([t for t in self.trades if t['type'] == 'BUY']),
            'equity_curve': equity
        }


class Phase6Trending:
    """Test trend-riding approach"""
    
    @staticmethod
    def generate_synthetic_data(symbol, days=1260):
        """Generate realistic synthetic OHLCV data"""
        np.random.seed(hash(symbol) % 2**32)
        
        # Base prices
        bases = {'SPY': 210, 'QQQ': 270, 'IWM': 160, 'TLT': 97}
        base_price = bases.get(symbol, 200)
        
        # Volatility (annualized)
        vols = {'SPY': 0.15, 'QQQ': 0.20, 'IWM': 0.18, 'TLT': 0.08}
        vol = vols.get(symbol, 0.15)
        
        # Drift (annual return)
        drifts = {'SPY': 0.069, 'QQQ': 0.079, 'IWM': 0.075, 'TLT': 0.042}
        drift = drifts.get(symbol, 0.06)
        
        # Generate GBM with volatility clustering
        daily_drift = drift / 252
        daily_vol = vol / np.sqrt(252)
        
        prices = [base_price]
        vol_cluster = vol
        
        for _ in range(days):
            # Volatility clustering
            vol_cluster = 0.95 * vol_cluster + 0.05 * abs(np.random.normal(0, vol))
            
            # GBM step
            ret = np.random.normal(daily_drift, daily_vol * vol_cluster)
            prices.append(prices[-1] * (1 + ret))
        
        prices = np.array(prices[1:])
        
        dates = pd.date_range(start='2019-01-01', periods=days, freq='B')
        
        data = pd.DataFrame({
            'Date': dates,
            'Close': prices,
            'High': prices * (1 + np.abs(np.random.normal(0, 0.005, days))),
            'Low': prices * (1 - np.abs(np.random.normal(0, 0.005, days))),
            'Volume': np.random.uniform(50e6, 200e6, days)
        })
        data.set_index('Date', inplace=True)
        return data
    
    @staticmethod
    def run_all():
        """Test on all 4 assets"""
        symbols = ['SPY', 'QQQ', 'IWM', 'TLT']
        results = []
        
        print("\n" + "=" * 100)
        print("[PHASE 6] TREND-RIDING - Hold Uptrends, Sidestep Downtrends")
        print("=" * 100)
        print("Strategy: Enter when above SMA200 + RSI < 80, Hold while above SMA50, Exit on SMA50 break")
        print("Key: NO selling on overbought RSI - we let winners run")
        print("=" * 100 + "\n")
        
        for symbol in symbols:
            data = Phase6Trending.generate_synthetic_data(symbol)
            print(f"[DATA] {symbol}: {len(data)} days, Price ${data['Close'].min():.2f}-${data['Close'].max():.2f}")
            
            strategy = TrendRidingStrategy(symbol)
            result = strategy.backtest(data)
            
            ret = result['total_return']
            bh = result['buy_hold']
            outperf = ret - bh
            trades = result['trades']
            
            print(f"[TEST] {symbol}... Return: {ret:+.1%} (B&H: {bh:+.1%}, Trades: {trades})")
            
            results.append({
                'Symbol': symbol,
                'Strategy Return': ret,
                'B&H Return': bh,
                'Outperformance': outperf,
                'Trades': trades,
                'Beats B&H': 'YES [+]' if outperf > 0 else 'NO [-]'
            })
        
        # Summary table
        print("\n" + "=" * 100)
        print(f"{'Symbol':<8} {'Strategy Return':>15} {'B&H Return':>15} {'Outperformance':>18} {'Trades':>8} {'Result':>12}")
        print("-" * 100)
        for r in results:
            print(f"{r['Symbol']:<8} {r['Strategy Return']:>14.1%} {r['B&H Return']:>14.1%} {r['Outperformance']:>17.1%} {r['Trades']:>8.0f} {r['Beats B&H']:>12}")
        
        print("=" * 100)
        
        # Overall verdict
        wins = sum(1 for r in results if 'YES' in r['Beats B&H'])
        avg_ret = np.mean([r['Strategy Return'] for r in results])
        avg_outperf = np.mean([r['Outperformance'] for r in results])
        
        print(f"\nVERDICT:")
        print(f"  Beats S&P 500: {wins}/4 assets")
        print(f"  Average return: {avg_ret:+.1%}")
        print(f"  Average outperformance: {avg_outperf:+.1%}")
        
        if wins >= 2:
            print(f"  [SUCCESS] Beating S&P 500 on {wins} assets! Phase 6 complete!")
        else:
            print(f"  [NEEDS TUNE] Still underperforming - try alpha extraction?")
        
        print("=" * 100 + "\n")


if __name__ == '__main__':
    Phase6Trending.run_all()
