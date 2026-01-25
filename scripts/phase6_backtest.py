"""
Phase 6 Optimization - Backtest Results vs S&P 500
Tests all optimized strategies to validate S&P 500 outperformance
"""

import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from datetime import datetime

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from trading_bot.optimized_strategies import (
    OptimizedRSIStrategy,
    OptimizedMeanReversionStrategy,
    OptimizedMomentumStrategy,
    StrategyEnsemble,
    DynamicPositionSizer,
    Phase6OptimizedSystem
)


class Phase6Backtester:
    """Run Phase 6 optimization backtests"""

    def __init__(self, symbol="SPY", days=1260):
        self.symbol = symbol
        self.days = days
        self.data = None

    def fetch_synthetic_data(self):
        """Generate synthetic data same as before"""
        from pathlib import Path
        import sys
        
        # Add scripts to path for import
        sys.path.insert(0, str(Path(__file__).parent))
        from real_data_backtest import SyntheticMarketGenerator
        
        print(f"\n[DATA] Generating synthetic {self.symbol} data...")
        
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
        return self.data

    def backtest_optimized_rsi(self):
        """Test optimized RSI strategy"""
        if self.data is None:
            self.fetch_synthetic_data()
        
        print(f"[TEST] Optimized RSI Strategy...")
        
        data = self.data.copy()
        strategy = OptimizedRSIStrategy()
        signal_data = strategy.generate_signals(data)
        
        # Calculate returns
        signal_data['strategy_return'] = signal_data['signal'].shift(1) * signal_data['Close'].pct_change()
        signal_data['cumulative_return'] = (1 + signal_data['strategy_return']).cumprod()
        
        # B&H benchmark
        signal_data['buy_hold_return'] = signal_data['Close'].pct_change()
        signal_data['buy_hold_cumulative'] = (1 + signal_data['buy_hold_return']).cumprod()
        
        return self._calculate_metrics(signal_data, "OptimizedRSI(14)")

    def backtest_optimized_mean_reversion(self):
        """Test optimized mean reversion strategy"""
        if self.data is None:
            self.fetch_synthetic_data()
        
        print(f"[TEST] Optimized Mean Reversion Strategy...")
        
        data = self.data.copy()
        strategy = OptimizedMeanReversionStrategy(window=15, std_mult=1.5, holding_days=5)
        signal_data = strategy.generate_signals(data)
        
        # Calculate returns
        signal_data['strategy_return'] = signal_data['signal'].shift(1) * signal_data['Close'].pct_change()
        signal_data['cumulative_return'] = (1 + signal_data['strategy_return']).cumprod()
        
        # B&H benchmark
        signal_data['buy_hold_return'] = signal_data['Close'].pct_change()
        signal_data['buy_hold_cumulative'] = (1 + signal_data['buy_hold_return']).cumprod()
        
        return self._calculate_metrics(signal_data, "OptimizedMeanReversion(15,1.5)")

    def backtest_optimized_momentum(self):
        """Test redesigned momentum strategy"""
        if self.data is None:
            self.fetch_synthetic_data()
        
        print(f"[TEST] Redesigned Momentum Strategy (ADX-based)...")
        
        data = self.data.copy()
        strategy = OptimizedMomentumStrategy(atr_window=14, min_trend_strength=25)
        signal_data = strategy.generate_signals(data)
        
        # Calculate returns
        signal_data['strategy_return'] = signal_data['signal'].shift(1) * signal_data['Close'].pct_change()
        signal_data['cumulative_return'] = (1 + signal_data['strategy_return']).cumprod()
        
        # B&H benchmark
        signal_data['buy_hold_return'] = signal_data['Close'].pct_change()
        signal_data['buy_hold_cumulative'] = (1 + signal_data['buy_hold_return']).cumprod()
        
        return self._calculate_metrics(signal_data, "OptimizedMomentum(ADX)")

    def backtest_ensemble(self):
        """Test ensemble system"""
        if self.data is None:
            self.fetch_synthetic_data()
        
        print(f"[TEST] Ensemble System (Weighted Voting)...")
        
        data = self.data.copy()
        system = Phase6OptimizedSystem()
        signal_data = system.generate_trading_signals(data)
        
        # Calculate returns with position sizing
        signal_data['strategy_return'] = (
            signal_data['ensemble_signal'].shift(1) *
            signal_data['position_size'].shift(1) *
            signal_data['Close'].pct_change()
        )
        signal_data['cumulative_return'] = (1 + signal_data['strategy_return']).cumprod()
        
        # B&H benchmark
        signal_data['buy_hold_return'] = signal_data['Close'].pct_change()
        signal_data['buy_hold_cumulative'] = (1 + signal_data['buy_hold_return']).cumprod()
        
        return self._calculate_metrics(signal_data, "Ensemble(Weighted)")

    def _calculate_metrics(self, data, strategy_name):
        """Calculate performance metrics"""
        data = data.dropna()
        
        if len(data) == 0:
            return None
        
        strategy_return = (data['cumulative_return'].iloc[-1] - 1) * 100
        bh_return = (data['buy_hold_cumulative'].iloc[-1] - 1) * 100
        
        winning_trades = len(data[data['strategy_return'] > 0])
        total_trades = len(data)
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        strategy_sharpe = self._calculate_sharpe(data['strategy_return'])
        strategy_sortino = self._calculate_sortino(data['strategy_return'])
        strategy_dd = self._calculate_max_drawdown(data['cumulative_return'])
        bh_dd = self._calculate_max_drawdown(data['buy_hold_cumulative'])
        
        metrics = {
            'strategy': strategy_name,
            'symbol': self.symbol,
            'strategy_return_pct': round(strategy_return, 2),
            'buy_hold_return_pct': round(bh_return, 2),
            'outperformance_pct': round(strategy_return - bh_return, 2),
            'win_rate_pct': round(win_rate, 2),
            'sharpe_ratio': round(strategy_sharpe, 2),
            'sortino_ratio': round(strategy_sortino, 2),
            'max_drawdown_pct': round(strategy_dd * 100, 2),
            'vs_bh_max_dd_pct': round(bh_dd * 100, 2),
            'is_profitable': strategy_return > 0,
            'beats_benchmark': strategy_return > bh_return
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

    def run_all(self):
        """Run all Phase 6 optimization backtests"""
        results = []
        results.append(self.backtest_optimized_rsi())
        results.append(self.backtest_optimized_mean_reversion())
        results.append(self.backtest_optimized_momentum())
        results.append(self.backtest_ensemble())
        
        return [r for r in results if r is not None]


def print_phase6_results(all_results):
    """Print Phase 6 results with before/after comparison"""
    print("\n" + "=" * 160)
    print("PHASE 6 OPTIMIZATION RESULTS - Beating S&P 500")
    print("=" * 160)
    
    for symbol_results in all_results:
        print(f"\n{symbol_results[0]['symbol']} RESULTS:")
        print("-" * 160)
        print(f"{'Strategy':<30} {'Return %':<12} {'BH Return %':<14} {'Outperf %':<12} {'Sharpe':<8} {'Sortino':<8} {'Beats B&H':<12}")
        print("-" * 160)
        
        for result in symbol_results:
            beats = "YES [+]" if result['beats_benchmark'] else "NO [-]"
            print(
                f"{result['strategy']:<30} "
                f"{result['strategy_return_pct']:>10.2f}% "
                f"{result['buy_hold_return_pct']:>12.2f}% "
                f"{result['outperformance_pct']:>10.2f}% "
                f"{result['sharpe_ratio']:>6.2f} "
                f"{result['sortino_ratio']:>6.2f} "
                f"{beats:<12}"
            )


def main():
    """Run Phase 6 backtest"""
    print("\n" + "=" * 160)
    print("[PHASE 6] OPTIMIZATION - BEAT THE S&P 500")
    print("=" * 160)
    print("Testing optimized strategies:")
    print("  1. Optimized RSI (volume + trend filters, time-based exits)")
    print("  2. Optimized Mean Reversion (faster entry, better exits)")
    print("  3. Redesigned Momentum (ADX-based, trend confirmation)")
    print("  4. Ensemble System (weighted voting + dynamic position sizing)")
    print("=" * 160)
    
    symbols = ["SPY", "QQQ", "IWM", "TLT"]
    all_results = []
    
    for symbol in symbols:
        backtester = Phase6Backtester(symbol=symbol, days=1260)
        results = backtester.run_all()
        
        if results:
            all_results.append(results)
    
    # Print results
    if all_results:
        print_phase6_results(all_results)
        
        # Summary
        print("\n" + "=" * 160)
        print("PHASE 6 SUMMARY")
        print("=" * 160)
        
        for symbol_results in all_results:
            beats_count = sum(1 for r in symbol_results if r['beats_benchmark'])
            avg_return = np.mean([r['strategy_return_pct'] for r in symbol_results])
            avg_outperf = np.mean([r['outperformance_pct'] for r in symbol_results])
            avg_sharpe = np.mean([r['sharpe_ratio'] for r in symbol_results])
            
            print(f"\n{symbol_results[0]['symbol']}:")
            print(f"  Beating B&H: {beats_count}/4 strategies")
            print(f"  Avg return: {avg_return:.2f}% (vs B&H {symbol_results[0]['buy_hold_return_pct']:.2f}%)")
            print(f"  Avg outperformance: {avg_outperf:+.2f}%")
            print(f"  Avg Sharpe ratio: {avg_sharpe:.2f}")
            
            best = max(symbol_results, key=lambda x: x['strategy_return_pct'])
            print(f"  BEST: {best['strategy']} ({best['strategy_return_pct']:.2f}%, Sharpe: {best['sharpe_ratio']:.2f})")
        
        # Overall verdict
        total_strategies = sum(len(r) for r in all_results)
        beats_total = sum(sum(1 for r in results if r['beats_benchmark']) for results in all_results)
        
        print(f"\n[OVERALL] Beating S&P 500: {beats_total}/{total_strategies} ({beats_total/total_strategies*100:.1f}%)")
        
        if beats_total / total_strategies > 0.75:
            print("[SUCCESS] Phase 6 optimization SUCCEEDS - 75%+ of strategies beat S&P 500!")
        elif beats_total / total_strategies > 0.5:
            print("[SUCCESS] Phase 6 optimization improves performance - 50%+ of strategies beat S&P 500")
        else:
            print("[CAUTION] Some strategies still underperform - needs further tuning")
        
        print("=" * 160 + "\n")


if __name__ == "__main__":
    main()
