"""
Realistic Synthetic Data Backtesting - Validate Strategy Profitability
Uses realistic synthetic OHLCV data to test multiple strategies
Simulates actual market behavior with volatility, trends, and mean reversion
"""

import logging
import json
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class SyntheticMarketGenerator:
    """Generate realistic synthetic market data"""

    @staticmethod
    def generate_price_series(symbol="SPY", days=1260, volatility=0.15, drift=0.10, initial_price=100):
        """Generate realistic synthetic price data using geometric Brownian motion"""
        np.random.seed(42)
        
        dates = pd.date_range(end=datetime.now(), periods=days, freq='B')
        daily_vol = volatility / np.sqrt(252)
        daily_drift = drift / 252
        
        returns = []
        current_price = initial_price
        trend_change = np.random.randn()
        
        for i in range(days):
            if i % 100 == 0:
                trend_change = np.random.randn()
            
            vol_cluster = daily_vol * (1 + 0.5 * np.sin(i / 50))
            mean_reversion = -0.01 * (current_price - initial_price) / initial_price
            daily_return = daily_drift + vol_cluster * np.random.randn() + mean_reversion + 0.02 * trend_change / 100
            returns.append(daily_return)
            current_price *= (1 + daily_return)
        
        close_prices = [initial_price]
        for ret in returns:
            close_prices.append(close_prices[-1] * (1 + ret))
        
        data = {
            'Date': dates,
            'Open': [p * (1 + np.random.randn() * 0.005) for p in close_prices[:-1]],
            'High': [max(o, c * (1 + abs(np.random.randn()) * 0.01)) for o, c in zip(close_prices[:-1], close_prices[1:])],
            'Low': [min(o, c * (1 - abs(np.random.randn()) * 0.01)) for o, c in zip(close_prices[:-1], close_prices[1:])],
            'Close': close_prices[1:],
            'Volume': np.random.randint(40000000, 100000000, len(close_prices) - 1)
        }
        
        df = pd.DataFrame(data)
        df.set_index('Date', inplace=True)
        return df


class SyntheticDataBacktester:
    """Backtester using realistic synthetic market data"""

    def __init__(self, symbol="SPY", days=1260):
        self.symbol = symbol
        self.days = days
        self.data = None

    def fetch_data(self):
        """Generate realistic synthetic historical data"""
        print(f"\n[DATA] Generating synthetic {self.symbol} data ({self.days} trading days)...")
        
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
        
        print(f"[OK] Generated {len(self.data)} trading days")
        print(f"     Price range: ${self.data['Close'].min():.2f} - ${self.data['Close'].max():.2f}")
        return self.data

    def backtest_momentum(self, short_window=20, long_window=50):
        """Momentum strategy: Buy when short MA > long MA"""
        if self.data is None:
            return None

        print(f"\n[TEST] Momentum Strategy ({short_window}/{long_window} days)...")
        
        data = self.data.copy()
        data['short_ma'] = data['Close'].rolling(window=short_window).mean()
        data['long_ma'] = data['Close'].rolling(window=long_window).mean()
        
        data['signal'] = 0
        data.loc[data['short_ma'] > data['long_ma'], 'signal'] = 1
        data.loc[data['short_ma'] <= data['long_ma'], 'signal'] = 0
        
        data['strategy_return'] = data['signal'].shift(1) * data['Close'].pct_change()
        data['cumulative_return'] = (1 + data['strategy_return']).cumprod()
        
        data['buy_hold_return'] = data['Close'].pct_change()
        data['buy_hold_cumulative'] = (1 + data['buy_hold_return']).cumprod()
        
        return self._calculate_metrics(data, f"Momentum({short_window}/{long_window})")

    def backtest_mean_reversion(self, window=20, std_mult=2.0):
        """Mean reversion: Buy oversold, Sell overbought"""
        if self.data is None:
            return None

        print(f"[TEST] Mean Reversion Strategy (window={window}, std_mult={std_mult})...")
        
        data = self.data.copy()
        data['ma'] = data['Close'].rolling(window=window).mean()
        data['std'] = data['Close'].rolling(window=window).std()
        data['upper_band'] = data['ma'] + (std_mult * data['std'])
        data['lower_band'] = data['ma'] - (std_mult * data['std'])
        
        data['signal'] = 0
        data.loc[data['Close'] < data['lower_band'], 'signal'] = 1
        data.loc[data['Close'] > data['upper_band'], 'signal'] = -1
        
        data['signal'] = data['signal'].apply(lambda x: 1 if x > 0 else 0)
        
        data['strategy_return'] = data['signal'].shift(1) * data['Close'].pct_change()
        data['cumulative_return'] = (1 + data['strategy_return']).cumprod()
        
        data['buy_hold_return'] = data['Close'].pct_change()
        data['buy_hold_cumulative'] = (1 + data['buy_hold_return']).cumprod()
        
        return self._calculate_metrics(data, f"MeanReversion({window},{std_mult})")

    def backtest_rsi(self, window=14, oversold=30, overbought=70):
        """RSI strategy: Buy oversold, Sell overbought"""
        if self.data is None:
            return None

        print(f"[TEST] RSI Strategy (window={window}, oversold={oversold}, overbought={overbought})...")
        
        data = self.data.copy()
        
        delta = data['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        rs = gain / loss
        data['rsi'] = 100 - (100 / (1 + rs))
        
        data['signal'] = 0
        data.loc[data['rsi'] < oversold, 'signal'] = 1
        data.loc[data['rsi'] > overbought, 'signal'] = 0
        
        data['strategy_return'] = data['signal'].shift(1) * data['Close'].pct_change()
        data['cumulative_return'] = (1 + data['strategy_return']).cumprod()
        
        data['buy_hold_return'] = data['Close'].pct_change()
        data['buy_hold_cumulative'] = (1 + data['buy_hold_return']).cumprod()
        
        return self._calculate_metrics(data, f"RSI({window})")

    def backtest_macd(self):
        """MACD strategy: Buy when MACD > Signal"""
        if self.data is None:
            return None

        print(f"[TEST] MACD Strategy...")
        
        data = self.data.copy()
        
        exp1 = data['Close'].ewm(span=12, adjust=False).mean()
        exp2 = data['Close'].ewm(span=26, adjust=False).mean()
        data['macd'] = exp1 - exp2
        data['signal'] = data['macd'].ewm(span=9, adjust=False).mean()
        data['histogram'] = data['macd'] - data['signal']
        
        data['position'] = 0
        data.loc[data['histogram'] > 0, 'position'] = 1
        
        data['strategy_return'] = data['position'].shift(1) * data['Close'].pct_change()
        data['cumulative_return'] = (1 + data['strategy_return']).cumprod()
        
        data['buy_hold_return'] = data['Close'].pct_change()
        data['buy_hold_cumulative'] = (1 + data['buy_hold_return']).cumprod()
        
        return self._calculate_metrics(data, "MACD(12,26)")

    def _calculate_metrics(self, data, strategy_name):
        """Calculate performance metrics"""
        data = data.dropna()
        
        if len(data) == 0:
            return None
        
        strategy_total_return = (data['cumulative_return'].iloc[-1] - 1) * 100
        bh_total_return = (data['buy_hold_cumulative'].iloc[-1] - 1) * 100
        
        winning_trades = len(data[data['strategy_return'] > 0])
        total_trades = len(data[data['position'].diff() != 0]) if 'position' in data.columns else len(data)
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        strategy_sharpe = self._calculate_sharpe(data['strategy_return'])
        bh_sharpe = self._calculate_sharpe(data['buy_hold_return'])
        
        strategy_sortino = self._calculate_sortino(data['strategy_return'])
        
        strategy_dd = self._calculate_max_drawdown(data['cumulative_return'])
        bh_dd = self._calculate_max_drawdown(data['buy_hold_cumulative'])
        
        gains = data[data['strategy_return'] > 0]['strategy_return'].sum()
        losses = abs(data[data['strategy_return'] <= 0]['strategy_return'].sum())
        profit_factor = gains / losses if losses > 0 else 0
        
        calmar = (strategy_total_return / 100) / abs(strategy_dd) if strategy_dd != 0 else 0
        
        metrics = {
            'strategy': strategy_name,
            'symbol': self.symbol,
            'period': 'Realistic Synthetic (5 years)',
            'total_trades': int(total_trades),
            'strategy_return_pct': round(strategy_total_return, 2),
            'buy_hold_return_pct': round(bh_total_return, 2),
            'outperformance_pct': round(strategy_total_return - bh_total_return, 2),
            'win_rate_pct': round(win_rate, 2),
            'sharpe_ratio': round(strategy_sharpe, 2),
            'vs_bh_sharpe': round(bh_sharpe, 2),
            'sortino_ratio': round(strategy_sortino, 2),
            'max_drawdown_pct': round(strategy_dd * 100, 2),
            'vs_bh_max_dd_pct': round(bh_dd * 100, 2),
            'profit_factor': round(profit_factor, 2),
            'calmar_ratio': round(calmar, 2),
            'is_profitable': strategy_total_return > 0,
            'beats_benchmark': strategy_total_return > bh_total_return
        }
        
        return metrics

    @staticmethod
    def _calculate_sharpe(returns, risk_free_rate=0.02):
        """Calculate Sharpe ratio"""
        excess_returns = returns - (risk_free_rate / 252)
        return (excess_returns.mean() / excess_returns.std() * np.sqrt(252)) if excess_returns.std() > 0 else 0

    @staticmethod
    def _calculate_sortino(returns, risk_free_rate=0.02):
        """Calculate Sortino ratio"""
        excess_returns = returns - (risk_free_rate / 252)
        downside = returns[returns < 0].std()
        return (excess_returns.mean() / downside * np.sqrt(252)) if downside > 0 else 0

    @staticmethod
    def _calculate_max_drawdown(cumulative_returns):
        """Calculate maximum drawdown"""
        running_max = cumulative_returns.expanding().max()
        drawdown = (cumulative_returns - running_max) / running_max
        return drawdown.min()

    def run_all_strategies(self):
        """Run all strategies and compare"""
        if self.data is None:
            self.fetch_data()
        
        if self.data is None:
            print("[ERROR] Cannot fetch data")
            return None
        
        results = []
        
        results.append(self.backtest_momentum(short_window=20, long_window=50))
        results.append(self.backtest_momentum(short_window=10, long_window=30))
        results.append(self.backtest_mean_reversion(window=20, std_mult=2.0))
        results.append(self.backtest_mean_reversion(window=30, std_mult=2.5))
        results.append(self.backtest_rsi(window=14, oversold=30, overbought=70))
        results.append(self.backtest_macd())
        
        results = [r for r in results if r is not None]
        
        return results


def print_results_table(all_results):
    """Print results in formatted table"""
    print("\n" + "=" * 150)
    print("BACKTEST RESULTS - REALISTIC SYNTHETIC MARKET DATA ANALYSIS")
    print("=" * 150)
    
    for symbol_results in all_results:
        print(f"\nSYMBOL: {symbol_results[0]['symbol']}")
        print("-" * 150)
        print(f"{'Strategy':<20} {'Return %':<12} {'BH Ret %':<12} {'Outperf %':<14} {'Win %':<10} {'Sharpe':<8} {'Sortino':<8} {'Drawdown %':<12} {'Status':<12}")
        print("-" * 150)
        
        for result in symbol_results:
            status = 'PROFIT' if result['is_profitable'] else 'LOSS'
            beats = ' [BEATS B&H]' if result['beats_benchmark'] else ''
            print(
                f"{result['strategy']:<20} "
                f"{result['strategy_return_pct']:>10.2f}% "
                f"{result['buy_hold_return_pct']:>10.2f}% "
                f"{result['outperformance_pct']:>12.2f}% "
                f"{result['win_rate_pct']:>8.2f}% "
                f"{result['sharpe_ratio']:>6.2f} "
                f"{result['sortino_ratio']:>6.2f} "
                f"{result['max_drawdown_pct']:>10.2f}% "
                f"{status:<12}{beats}"
            )

    print("\n" + "=" * 150)
    print("METRICS EXPLAINED:")
    print("  Return % = Total strategy return over period")
    print("  BH Ret % = Buy & Hold (benchmark) total return")
    print("  Outperf % = How much strategy beats/loses to B&H")
    print("  Win % = Percentage of winning trades")
    print("  Sharpe = Risk-adjusted return (>1.0 is good)")
    print("  Sortino = Return per unit of downside risk")
    print("  Drawdown % = Maximum peak-to-trough decline")
    print("  BEATS B&H = Strategy outperforms buy & hold")
    print("=" * 150 + "\n")


def main():
    """Run backtests on multiple symbols"""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    
    symbols = ["SPY", "QQQ", "IWM", "TLT"]
    all_results = []
    
    print("\n" + "=" * 150)
    print("[LAUNCH] ALGO TRADING BOT - STRATEGY VALIDATION WITH REALISTIC SYNTHETIC DATA")
    print("=" * 150)
    print(f"Testing Period: 5 Years (1,260 trading days)")
    print(f"Data Source: Realistic synthetic OHLCV (market dynamics)")
    print(f"Symbols: {', '.join(symbols)}")
    print("=" * 150)
    
    for symbol in symbols:
        backtester = SyntheticDataBacktester(symbol=symbol, days=1260)
        results = backtester.run_all_strategies()
        
        if results:
            all_results.append(results)
        else:
            print(f"[FAILED] Failed to backtest {symbol}")
    
    if all_results:
        print_results_table(all_results)
        
        results_file = Path("backtest_results/synthetic_data_backtest.json")
        results_file.parent.mkdir(exist_ok=True)
        
        # Convert numpy booleans to Python booleans for JSON serialization
        json_results = []
        for symbol_group in all_results:
            json_group = []
            for result in symbol_group:
                json_result = {k: bool(v) if isinstance(v, np.bool_) else v for k, v in result.items()}
                json_group.append(json_result)
            json_results.append(json_group)
        
        with open(results_file, "w") as f:
            json.dump(json_results, f, indent=2)
        
        print(f"[SAVE] Results saved to: {results_file}\n")
        
        print("EXECUTIVE SUMMARY:")
        print("-" * 150)
        
        for symbol_results in all_results:
            profitable_count = sum(1 for r in symbol_results if r['is_profitable'])
            beats_bh_count = sum(1 for r in symbol_results if r['beats_benchmark'])
            avg_return = np.mean([r['strategy_return_pct'] for r in symbol_results])
            avg_outperformance = np.mean([r['outperformance_pct'] for r in symbol_results])
            avg_sharpe = np.mean([r['sharpe_ratio'] for r in symbol_results])
            avg_win_rate = np.mean([r['win_rate_pct'] for r in symbol_results])
            
            print(f"\n{symbol_results[0]['symbol']}:")
            print(f"  [OK] Profitable strategies: {profitable_count}/{len(symbol_results)}")
            print(f"  [BEATS] Beating B&H: {beats_bh_count}/{len(symbol_results)}")
            print(f"  [RETURN] Avg strategy return: {avg_return:.2f}%")
            print(f"  [ALPHA] Avg outperformance: {avg_outperformance:+.2f}%")
            print(f"  [SHARPE] Avg Sharpe ratio: {avg_sharpe:.2f} {'[GOOD]' if avg_sharpe > 1.0 else '[POOR]'}")
            print(f"  [WINRATE] Avg win rate: {avg_win_rate:.2f}%")
            
            best = max(symbol_results, key=lambda x: x['strategy_return_pct'])
            worst = min(symbol_results, key=lambda x: x['strategy_return_pct'])
            print(f"  [BEST] {best['strategy']} ({best['strategy_return_pct']:.2f}% return, Sharpe: {best['sharpe_ratio']:.2f})")
            print(f"  [WORST] {worst['strategy']} ({worst['strategy_return_pct']:.2f}% return, Sharpe: {worst['sharpe_ratio']:.2f})")
        
        print("\n" + "=" * 150)
        print("OVERALL SYSTEM ASSESSMENT:")
        print("=" * 150)
        
        total_strategies = sum(len(r) for r in all_results)
        total_profitable = sum(sum(1 for r in results if r['is_profitable']) for results in all_results)
        total_beats_bh = sum(sum(1 for r in results if r['beats_benchmark']) for results in all_results)
        
        profitability_rate = (total_profitable / total_strategies * 100) if total_strategies > 0 else 0
        bh_beating_rate = (total_beats_bh / total_strategies * 100) if total_strategies > 0 else 0
        
        print(f"\nTotal strategies tested: {total_strategies}")
        print(f"Profitable strategies: {total_profitable} ({profitability_rate:.1f}%)")
        print(f"Beat buy-and-hold: {total_beats_bh} ({bh_beating_rate:.1f}%)")
        
        if profitability_rate > 75:
            print(f"\n[SUCCESS] System is HIGHLY PROFITABLE - {profitability_rate:.1f}% of strategies make money")
        elif profitability_rate > 50:
            print(f"\n[SUCCESS] System is PROFITABLE - {profitability_rate:.1f}% of strategies make money")
        elif profitability_rate > 30:
            print(f"\n[WARNING] System shows potential - {profitability_rate:.1f}% of strategies are profitable")
        else:
            print(f"\n[FAILURE] System needs improvement - Only {profitability_rate:.1f}% of strategies are profitable")
        
        if bh_beating_rate > 50:
            print(f"[SUCCESS] Strategies beat buy-and-hold in {bh_beating_rate:.1f}% of cases")
        else:
            print(f"[WARNING] Strategies beat B&H in only {bh_beating_rate:.1f}% of cases - passive indexing wins")
        
        print("\n" + "=" * 150)


if __name__ == "__main__":
    main()
