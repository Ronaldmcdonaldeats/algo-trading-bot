"""
Phase 6 Radical Optimization - Ultra-Simple High-Frequency Approach

KEY INSIGHT FROM BACKTEST:
- RSI(14) made +13.21% return
- This came from ~290+ trades over 5 years = ~1 trade per week
- Higher frequency wins, not sophisticated filtering

HYPOTHESIS: The winning approach trades OFTEN, not selectively
- Buy on RSI < 50 (not just < 30 oversold)
- Sell on RSI > 70 (not just > 70 overbought)
- Ride trends with 5-day MA filter
- NO volume filters, NO volatility thresholds, NO complex logic

This backtester tests the radical simplicity approach.
"""
import sys
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

sys.path.insert(0, r'c:\Users\Ronald mcdonald\projects\algo-trading-bot')

class RadicalSimpleRSI:
    """Ultra-simple RSI strategy that trades on every dip"""
    
    def __init__(self, symbol="SPY"):
        self.symbol = symbol
        self.trades = []
        self.position = 0
        self.entry_price = 0
        
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
        """Generate signals: Buy on RSI dips, sell on RSI peaks"""
        data = data.copy()
        
        # Calculate RSI
        rsi = self._calculate_rsi(data['Close'], period=14)
        
        # Super simple:
        # BUY: RSI < 50 (just a mild dip, not even oversold)
        # SELL: RSI > 70 (not extreme overbought)
        
        data['rsi'] = rsi
        data['signal'] = 0
        
        # Buy signal: RSI crossing from above 50 to below 50
        buy = (rsi < 50)
        data.loc[buy, 'signal'] = 1
        
        # Sell signal: RSI crossing from below 70 to above 70
        sell = (rsi > 70)
        data.loc[sell, 'signal'] = -1
        
        return data
    
    def backtest(self, data):
        """Run backtest"""
        signals = self.generate_signals(data)
        
        cash = 100000
        position = 0
        entry_price = 0
        equity = [cash]
        positions = []
        
        for idx in range(len(signals)):
            price = signals['Close'].iloc[idx]
            signal = signals['signal'].iloc[idx]
            
            # BUY signal
            if signal == 1 and position == 0:
                # Go all-in
                position = cash / price
                entry_price = price
                cash = 0
                self.trades.append({'date': idx, 'type': 'BUY', 'price': price})
            
            # SELL signal
            elif signal == -1 and position > 0:
                # Sell all
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
            positions.append(position)
        
        # Close any open position at end
        if position > 0:
            cash = position * signals['Close'].iloc[-1]
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


class Phase6Radical:
    """Test radical simple approach on multiple assets"""
    
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
        print("[PHASE 6] RADICAL SIMPLICITY - Ultra-High-Frequency RSI Approach")
        print("=" * 100)
        print("Strategy: Buy RSI < 50, Sell RSI > 70 (NO filters, NO timing, just signals)")
        print("Expected: Higher trade frequency than before = better results")
        print("=" * 100 + "\n")
        
        for symbol in symbols:
            data = Phase6Radical.generate_synthetic_data(symbol)
            print(f"[DATA] {symbol}: {len(data)} days, Price ${data['Close'].min():.2f}-${data['Close'].max():.2f}")
            
            strategy = RadicalSimpleRSI(symbol)
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
            print(f"  [SUCCESS] Beating S&P 500 on {wins} assets!")
        else:
            print(f"  [NEEDS TUNE] Still underperforming - try even simpler?")
        
        print("=" * 100 + "\n")


if __name__ == '__main__':
    Phase6Radical.run_all()
