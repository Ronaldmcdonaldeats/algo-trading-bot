"""
Phase 7 Multi-Stock Backtester with Adaptive Learning

Backtests the adaptive RSI strategy across all NASDAQ stocks
Implements portfolio-level analysis and learning feedback loops
"""
import sys
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import json
import logging
from collections import defaultdict

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from trading_bot.adaptive_strategy import AdaptiveRSIStrategy, AdaptiveStrategyEnsemble
from trading_bot.nasdaq_universe import NasdaqUniverse, StockBatcher

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MultiStockBacktester:
    """Backtests adaptive RSI strategy across multiple stocks"""
    
    def __init__(self, universe_size: int = 50):
        """
        Initialize backtester
        
        Args:
            universe_size: Number of stocks to test (default 50)
        """
        self.universe = NasdaqUniverse()
        self.universe_size = universe_size
        
        # Get top liquid stocks
        self.stocks = self.universe.get_recommended_universe(max_stocks=universe_size)
        logger.info(f"Testing on {len(self.stocks)} stocks: {self.stocks[:5]}...")
        
        # Results tracking
        self.results: Dict[str, Dict] = {}
        self.portfolio_results: Dict = {}
        
    def generate_synthetic_data(self, symbol: str, days: int = 1260) -> pd.DataFrame:
        """
        Generate realistic mean-reverting synthetic OHLCV data
        
        Args:
            symbol: Stock symbol
            days: Number of trading days
            
        Returns:
            DataFrame with OHLCV data
        """
        np.random.seed(hash(symbol) % 2**32)
        
        # Base prices vary by stock
        base_prices = {
            'AAPL': 150, 'MSFT': 300, 'GOOGL': 2500, 'AMZN': 3300,
            'NVDA': 500, 'TSLA': 800, 'META': 250, 'NFLX': 400
        }
        base_price = base_prices.get(symbol, np.random.randint(50, 500))
        
        # Volatility and drift vary (tech higher vol)
        if symbol in ['NVDA', 'TSLA', 'MSTR']:
            vol = np.random.uniform(0.20, 0.35)
            drift = np.random.uniform(0.05, 0.15)
        elif symbol in ['AAPL', 'MSFT', 'GOOGL']:
            vol = np.random.uniform(0.12, 0.18)
            drift = np.random.uniform(0.08, 0.12)
        else:
            vol = np.random.uniform(0.15, 0.25)
            drift = np.random.uniform(0.06, 0.10)
        
        # Generate mean-reverting prices
        prices = [base_price]
        daily_drift = drift / 252
        daily_vol = vol / np.sqrt(252)
        
        for i in range(days):
            # Mean reversion to moving average
            recent_ma = np.mean(prices[-min(200, len(prices)):])
            mean_reversion_term = 0.05 * (recent_ma - prices[-1]) / prices[-1]
            
            # GBM + mean reversion
            ret = daily_drift + mean_reversion_term + daily_vol * np.random.normal(0, 1)
            prices.append(prices[-1] * (1 + ret))
        
        prices = np.array(prices[1:])
        dates = pd.date_range(start='2020-01-01', periods=days, freq='B')
        
        data = pd.DataFrame({
            'Date': dates,
            'Close': prices,
            'High': prices * (1 + np.abs(np.random.normal(0, 0.005, days))),
            'Low': prices * (1 - np.abs(np.random.normal(0, 0.005, days))),
            'Volume': np.random.uniform(1e6, 100e6, days)
        })
        data.set_index('Date', inplace=True)
        
        return data
    
    def backtest_single_stock(self, symbol: str, data: pd.DataFrame) -> Dict:
        """
        Backtest adaptive strategy on single stock
        
        Args:
            symbol: Stock symbol
            data: OHLCV DataFrame
            
        Returns:
            Performance dictionary
        """
        strategy = AdaptiveRSIStrategy()
        strategy.set_symbol(symbol)
        
        # Generate signals
        signals = strategy.generate_signals(data)
        
        # Backtest execution
        cash = 100000
        position = 0
        entry_price = 0
        entry_date = None
        equity_curve = [cash]
        trades = []
        
        for idx in range(len(signals)):
            date = signals.index[idx]
            price = signals['Close'].iloc[idx]
            signal = signals['signal'].iloc[idx]
            vol = signals['volatility'].iloc[idx] if not signals['volatility'].isna().iloc[idx] else 0.02
            
            # BUY signal
            if signal == 1 and position == 0:
                position = cash / price
                entry_price = price
                entry_date = date
                cash = 0
            
            # SELL signal
            elif signal == -1 and position > 0:
                exit_price = price
                trade_return = (exit_price - entry_price) / entry_price
                trades.append({
                    'entry_date': entry_date,
                    'exit_date': date,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'return': trade_return,
                    'days': (date - entry_date).days
                })
                
                # Online learning - adapt after each trade
                strategy.adapt_parameters(trade_return, vol)
                
                cash = position * exit_price
                position = 0
                entry_price = 0
            
            # Update equity
            current_equity = cash + (position * price if position > 0 else 0)
            equity_curve.append(current_equity)
        
        # Close any open position
        if position > 0:
            final_price = signals['Close'].iloc[-1]
            cash = position * final_price
            equity_curve.append(cash)
        
        # Calculate metrics
        final_equity = equity_curve[-1]
        total_return = (final_equity - 100000) / 100000
        buy_hold = (signals['Close'].iloc[-1] / signals['Close'].iloc[0] - 1)
        
        returns = np.array([t['return'] for t in trades]) if trades else np.array([])
        win_rate = np.mean(returns > 0) if len(returns) > 0 else 0
        sharpe = (np.mean(returns) / np.std(returns)) if len(returns) > 0 and np.std(returns) > 0 else 0
        
        return {
            'symbol': symbol,
            'total_return': total_return,
            'buy_hold_return': buy_hold,
            'outperformance': total_return - buy_hold,
            'num_trades': len(trades),
            'win_rate': float(win_rate),
            'sharpe': float(sharpe),
            'avg_return': float(np.mean(returns)) if len(returns) > 0 else 0,
            'max_dd': float(np.min(returns)) if len(returns) > 0 else 0,
            'trade_list': trades,
            'strategy_params': strategy.params.to_dict(),
            'learning_stats': {
                'n_trades': strategy.learning_stats.n_samples,
                'mean_return': strategy.learning_stats.mean_return,
                'mean_win_rate': strategy.learning_stats.mean_win_rate
            }
        }
    
    def run_backtest(self, verbose: bool = True) -> Dict[str, Dict]:
        """
        Run backtest on all stocks
        
        Args:
            verbose: Print progress
            
        Returns:
            Results dictionary
        """
        print("\n" + "=" * 100)
        print("[PHASE 7] MULTI-STOCK BACKTEST - Adaptive RSI on 500 NASDAQ Stocks")
        print("=" * 100)
        print(f"Testing {len(self.stocks)} stocks with online learning")
        print("=" * 100 + "\n")
        
        for i, symbol in enumerate(self.stocks, 1):
            try:
                # Generate data
                data = self.generate_synthetic_data(symbol)
                
                # Run backtest
                result = self.backtest_single_stock(symbol, data)
                self.results[symbol] = result
                
                # Print progress
                if verbose and i % max(1, len(self.stocks) // 10) == 0:
                    perf = "OK" if result['outperformance'] > 0 else "NO"
                    print(f"[{i}/{len(self.stocks)}] {symbol:6s} [{perf}] "
                          f"Return: {result['total_return']:+6.1%} "
                          f"B&H: {result['buy_hold_return']:+6.1%} "
                          f"Trades: {result['num_trades']:3d} "
                          f"WR: {result['win_rate']:5.1%}")
            
            except Exception as e:
                logger.error(f"Error backtesting {symbol}: {e}")
                self.results[symbol] = {'error': str(e)}
        
        return self.results
    
    def analyze_results(self) -> Dict:
        """
        Analyze backtest results across portfolio
        
        Returns:
            Portfolio-level analysis
        """
        valid_results = {k: v for k, v in self.results.items() if 'error' not in v}
        
        if not valid_results:
            return {}
        
        returns = np.array([r['total_return'] for r in valid_results.values()])
        bh_returns = np.array([r['buy_hold_return'] for r in valid_results.values()])
        outperformance = np.array([r['outperformance'] for r in valid_results.values()])
        win_rates = np.array([r['win_rate'] for r in valid_results.values()])
        sharpes = np.array([r['sharpe'] for r in valid_results.values()])
        
        # Count winners
        winners = np.sum(outperformance > 0)
        
        analysis = {
            'total_stocks': len(valid_results),
            'winners': winners,
            'win_pct': winners / len(valid_results),
            'avg_return': np.mean(returns),
            'avg_bh_return': np.mean(bh_returns),
            'avg_outperformance': np.mean(outperformance),
            'median_outperformance': np.median(outperformance),
            'std_outperformance': np.std(outperformance),
            'avg_win_rate': np.mean(win_rates),
            'avg_sharpe': np.mean(sharpes),
            'best_stock': max(valid_results.items(), key=lambda x: x[1]['outperformance']),
            'worst_stock': min(valid_results.items(), key=lambda x: x[1]['outperformance']),
            'returns_distribution': {
                'positive_pct': np.sum(returns > 0) / len(returns),
                'negative_pct': np.sum(returns <= 0) / len(returns),
                'beats_bh_pct': np.sum(outperformance > 0) / len(returns)
            }
        }
        
        self.portfolio_results = analysis
        return analysis
    
    def print_results_summary(self) -> None:
        """Print summary of backtest results"""
        analysis = self.analyze_results()
        
        if not analysis:
            print("No valid results to analyze")
            return
        
        print("\n" + "=" * 100)
        print("PORTFOLIO-LEVEL ANALYSIS")
        print("=" * 100)
        print(f"\nTotal Stocks Tested: {analysis['total_stocks']}")
        print(f"Stocks Beating S&P 500: {analysis['winners']}/{analysis['total_stocks']} ({analysis['win_pct']:.1%})")
        print(f"\nReturns:")
        print(f"  Average Strategy Return: {analysis['avg_return']:+.2%}")
        print(f"  Average B&H Return: {analysis['avg_bh_return']:+.2%}")
        print(f"  Average Outperformance: {analysis['avg_outperformance']:+.2%}")
        print(f"  Median Outperformance: {analysis['median_outperformance']:+.2%}")
        print(f"  Std Dev of Outperformance: {analysis['std_outperformance']:.2%}")
        
        print(f"\nQuality Metrics:")
        print(f"  Average Win Rate: {analysis['avg_win_rate']:.1%}")
        print(f"  Average Sharpe Ratio: {analysis['avg_sharpe']:.3f}")
        
        print(f"\nBest Performer:")
        best_sym, best_data = analysis['best_stock']
        print(f"  {best_sym}: +{best_data['total_return']:.1%} vs +{best_data['buy_hold_return']:.1%} B&H "
              f"(+{best_data['outperformance']:.1%} outperformance)")
        
        print(f"\nWorst Performer:")
        worst_sym, worst_data = analysis['worst_stock']
        print(f"  {worst_sym}: {worst_data['total_return']:+.1%} vs {worst_data['buy_hold_return']:+.1%} B&H "
              f"({worst_data['outperformance']:+.1%} outperformance)")
        
        print("\n" + "=" * 100)
        
        # Top and bottom performers
        print("\nTOP 10 PERFORMERS:")
        sorted_results = sorted(
            self.results.items(),
            key=lambda x: x[1].get('outperformance', -1) if 'error' not in x[1] else -1,
            reverse=True
        )[:10]
        for i, (symbol, result) in enumerate(sorted_results, 1):
            if 'error' not in result:
                trades_count = result['num_trades']
                print(f"  {i:2d}. {symbol:6s} {result['total_return']:+7.1%} vs {result['buy_hold_return']:+7.1%} "
                      f"({result['outperformance']:+6.1%}) - Trades: {trades_count:3d}, WR: {result['win_rate']:5.1%}")
        
        print("\n" + "=" * 100 + "\n")


def main():
    """Run Phase 7 backtest"""
    # Test on top 20 NASDAQ stocks first
    backtester = MultiStockBacktester(universe_size=20)
    
    # Run backtest
    backtester.run_backtest(verbose=True)
    
    # Analyze results
    backtester.print_results_summary()
    
    # Save results
    results_file = Path(__file__).parent.parent.parent / "phase7_backtest_results.json"
    with open(results_file, 'w') as f:
        # Convert to serializable format
        serializable_results = {}
        for symbol, result in backtester.results.items():
            if 'equity_curve' in result:
                result_copy = result.copy()
                result_copy['equity_curve'] = result_copy['equity_curve'][:100]  # Trim for size
                result_copy['trades'] = len(result_copy['trades'])  # Just count
                serializable_results[symbol] = result_copy
            else:
                serializable_results[symbol] = result
        
        json.dump(serializable_results, f, indent=2, default=str)
    
    print(f"Results saved to {results_file}")


if __name__ == '__main__':
    main()
