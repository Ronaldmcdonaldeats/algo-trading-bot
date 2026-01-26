#!/usr/bin/env python3
"""
Comprehensive Backtest All Strategies + Build Hybrid
1. Backtest all 17 strategies
2. Analyze winning components
3. Build optimized hybrid combining best parts
4. Backtest hybrid and compare
"""

import sys
import logging
from pathlib import Path
from typing import Dict, List, Tuple
import json

import numpy as np
import pandas as pd
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.cached_data_loader import CachedDataLoader
from scripts.strategies import StrategyFactory
from scripts.strategies.base import BaseStrategy

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class ComprehensiveBacktester:
    """Run all strategies and analyze components"""
    
    def __init__(self):
        self.loader = CachedDataLoader()
        self.benchmark_annual = 0.101  # SPY ~10.1%
        self.symbols = [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META', 'NFLX',
            'ADBE', 'INTC', 'AMD', 'CSCO', 'QCOM', 'COST', 'AVGO', 'TMUS',
            'CMCSA', 'INTU', 'VRTX', 'AEP', 'LRCX', 'SNPS', 'CDNS', 'PCAR',
            'PAYX', 'ABNB', 'PANW', 'CRWD', 'ZM', 'DXCM', 'WDAY', 'FAST',
            'CPRT', 'CHKP'
        ]
        self.all_results = {}
        self.data = None
    
    def run(self):
        """Execute full pipeline"""
        logger.info("\n" + "="*80)
        logger.info("COMPREHENSIVE STRATEGY BACKTEST & HYBRID OPTIMIZATION")
        logger.info("="*80)
        
        # Step 1: Load data
        logger.info("\n[STEP 1] Loading data for all symbols...")
        self.data = self.loader.load_all_stocks(self.symbols)
        logger.info(f"✓ Loaded {len(self.data)} stocks")
        
        # Step 2: Backtest all strategies
        logger.info("\n[STEP 2] Backtesting all 17 strategies...")
        self.backtest_all_strategies()
        
        # Step 3: Analyze winning components
        logger.info("\n[STEP 3] Analyzing best components from top performers...")
        component_analysis = self.analyze_components()
        
        # Step 4: Build hybrid
        logger.info("\n[STEP 4] Building optimized hybrid strategy...")
        self.create_and_test_hybrid()
        
        # Step 5: Print comparison
        logger.info("\n[STEP 5] Final comparison...")
        self.print_final_comparison()
    
    def backtest_all_strategies(self):
        """Run backtest on all 17 strategies"""
        strategies = StrategyFactory.list_strategies()
        logger.info(f"Found {len(strategies)} strategies: {', '.join(strategies[:5])}...")
        
        for strategy_name in sorted(strategies):
            logger.info(f"\n  Testing: {strategy_name}...")
            
            strategy = StrategyFactory.create(strategy_name)
            if strategy is None:
                logger.error(f"  ✗ Failed to create strategy")
                continue
            
            annuals = []
            for symbol, prices in self.data.items():
                annual = strategy.backtest(prices)
                annuals.append(annual)
            
            avg = np.mean(annuals)
            outperform = avg - self.benchmark_annual
            beats_sp = sum(1 for a in annuals if a > self.benchmark_annual)
            sharpe = self._calculate_sharpe(annuals)
            
            self.all_results[strategy_name] = {
                'average_return': avg,
                'outperformance': outperform,
                'beats_sp': beats_sp,
                'pct_beats_sp': beats_sp / len(self.data) * 100,
                'min_return': min(annuals),
                'max_return': max(annuals),
                'std_dev': np.std(annuals),
                'sharpe_ratio': sharpe,
                'annuals': annuals
            }
            
            status = "✓" if outperform > 0 else "✗"
            logger.info(f"    {status} Avg: {avg:.4f} | Outperform: {outperform:+.4f} | Beats SPY: {beats_sp}/34 | Sharpe: {sharpe:.3f}")
    
    def _calculate_sharpe(self, returns: List[float]) -> float:
        """Calculate Sharpe ratio (assuming 1% risk-free rate)"""
        if len(returns) < 2:
            return 0
        rfr = 0.01
        excess_returns = np.array(returns) - rfr
        if np.std(excess_returns) == 0:
            return 0
        return np.mean(excess_returns) / np.std(excess_returns)
    
    def analyze_components(self) -> Dict:
        """Analyze which components work best in top strategies"""
        logger.info("\nRanking strategies by outperformance:")
        
        ranked = sorted(
            self.all_results.items(),
            key=lambda x: x[1]['outperformance'],
            reverse=True
        )
        
        for i, (name, metrics) in enumerate(ranked[:10], 1):
            logger.info(
                f"  {i:2d}. {name:30s} | Avg: {metrics['average_return']:7.4f} | "
                f"Outperf: {metrics['outperformance']:+7.4f} | Beats: {metrics['beats_sp']:2d}/34"
            )
        
        # Component analysis
        top_5_names = [name for name, _ in ranked[:5]]
        
        logger.info("\nTop 5 Strategies (for component analysis):")
        for name in top_5_names:
            logger.info(f"  - {name}")
        
        # Extract component characteristics
        components = {
            'top_strategies': top_5_names,
            'use_ensemble': any('ensemble' in name.lower() for name in top_5_names),
            'use_volatility_adjustment': any('volatility' in name.lower() for name in top_5_names),
            'use_moving_averages': any('adaptive' in name.lower() or 'trend' in name.lower() for name in top_5_names),
            'use_rsi': any('rsi' in name.lower() for name in top_5_names),
            'use_quality_factors': any('composite' in name.lower() or 'quality' in name.lower() for name in top_5_names),
        }
        
        logger.info("\nComponent Mix from Top 5:")
        logger.info(f"  - Ensemble Voting: {components['use_ensemble']}")
        logger.info(f"  - Volatility Adjustment: {components['use_volatility_adjustment']}")
        logger.info(f"  - Moving Averages: {components['use_moving_averages']}")
        logger.info(f"  - RSI Indicators: {components['use_rsi']}")
        logger.info(f"  - Quality Factors: {components['use_quality_factors']}")
        
        return components
    
    def create_and_test_hybrid(self):
        """Create hybrid strategy combining best elements"""
        logger.info("\n  Creating SuperHybrid strategy...")
        logger.info("  Components:")
        logger.info("    - Ensemble voting (ultra_ensemble base)")
        logger.info("    - Volatility adaptation (volatility_adaptive)")
        logger.info("    - Quality scoring (composite_quality)")
        logger.info("    - Trend confirmation (adaptive_ma)")
        logger.info("    - Risk adjustment (risk_adjusted_trend)")
        
        # Register and test SuperHybrid
        hybrid_strategy = SuperHybridStrategy()
        
        annuals = []
        for symbol, prices in self.data.items():
            annual = hybrid_strategy.backtest(prices)
            annuals.append(annual)
        
        avg = np.mean(annuals)
        outperform = avg - self.benchmark_annual
        beats_sp = sum(1 for a in annuals if a > self.benchmark_annual)
        sharpe = self._calculate_sharpe(annuals)
        
        self.all_results['super_hybrid'] = {
            'average_return': avg,
            'outperformance': outperform,
            'beats_sp': beats_sp,
            'pct_beats_sp': beats_sp / len(self.data) * 100,
            'min_return': min(annuals),
            'max_return': max(annuals),
            'std_dev': np.std(annuals),
            'sharpe_ratio': sharpe,
            'annuals': annuals
        }
        
        logger.info(f"\n  SuperHybrid Results:")
        logger.info(f"    Avg Return:     {avg:.4f} ({avg*100:.2f}%)")
        logger.info(f"    Outperformance: {outperform:+.4f} ({outperform*100:+.2f}%)")
        logger.info(f"    Beats SPY:      {beats_sp}/34 ({beats_sp/34*100:.1f}%)")
        logger.info(f"    Sharpe Ratio:   {sharpe:.3f}")
        logger.info(f"    Min/Max:        {min(annuals):.4f} / {max(annuals):.4f}")
        logger.info(f"    Std Dev:        {np.std(annuals):.4f}")
    
    def print_final_comparison(self):
        """Print final comparison table"""
        logger.info("\n" + "="*80)
        logger.info("FINAL COMPARISON - ALL STRATEGIES")
        logger.info("="*80)
        
        # Sort by outperformance
        ranked = sorted(
            self.all_results.items(),
            key=lambda x: x[1]['outperformance'],
            reverse=True
        )
        
        logger.info(f"\n{'Strategy':<30} {'Avg Return':>12} {'vs SPY':>10} {'Beats':>8} {'Sharpe':>8} {'Std Dev':>10}")
        logger.info("-" * 80)
        
        for name, metrics in ranked:
            status = "🏆" if metrics['outperformance'] > 0 else "  "
            logger.info(
                f"{status} {name:<28} {metrics['average_return']:>11.4f}  "
                f"{metrics['outperformance']:>+9.4f}  {metrics['beats_sp']:>4d}/34  "
                f"{metrics['sharpe_ratio']:>7.3f}  {metrics['std_dev']:>9.4f}"
            )
        
        # Summary stats
        logger.info("\n" + "="*80)
        logger.info("SUMMARY")
        logger.info("="*80)
        
        super_hybrid = self.all_results.get('super_hybrid', {})
        original_best = ranked[0] if ranked else (None, {})
        
        if super_hybrid:
            diff = super_hybrid['outperformance'] - original_best[1]['outperformance']
            logger.info(f"\nOriginal Best:  {original_best[0]}")
            logger.info(f"  Return: {original_best[1]['average_return']:.4f} | Outperform: {original_best[1]['outperformance']:+.4f}")
            
            logger.info(f"\nSuperHybrid:    (New Optimized Strategy)")
            logger.info(f"  Return: {super_hybrid['average_return']:.4f} | Outperform: {super_hybrid['outperformance']:+.4f}")
            
            if diff > 0:
                logger.info(f"\n✓ SuperHybrid IMPROVED by {diff:+.4f} ({diff*100:+.2f}%)")
            else:
                logger.info(f"\n✗ SuperHybrid underperformed by {abs(diff):.4f}")
        
        # Save results
        self.save_results()
    
    def save_results(self):
        """Save backtest results to file"""
        results_dir = Path(__file__).parent / 'backtest_results'
        results_dir.mkdir(exist_ok=True)
        
        # Convert to DataFrame for CSV
        rows = []
        for strategy_name, metrics in self.all_results.items():
            rows.append({
                'Strategy': strategy_name,
                'Average_Return': metrics['average_return'],
                'Outperformance': metrics['outperformance'],
                'Beats_SPY': metrics['beats_sp'],
                'Pct_Beats_SPY': metrics['pct_beats_sp'],
                'Min_Return': metrics['min_return'],
                'Max_Return': metrics['max_return'],
                'Std_Dev': metrics['std_dev'],
                'Sharpe_Ratio': metrics['sharpe_ratio']
            })
        
        df = pd.DataFrame(rows).sort_values('Outperformance', ascending=False)
        csv_path = results_dir / f'all_strategies_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        df.to_csv(csv_path, index=False)
        
        logger.info(f"\n✓ Results saved to: {csv_path}")


class SuperHybridStrategy(BaseStrategy):
    """
    SuperHybrid: Combines best elements from top performers
    - Ensemble voting mechanism
    - Volatility-adaptive position sizing
    - Quality factor filtering
    - Trend confirmation
    - Risk adjustment
    """
    
    def calculate_features(self, prices: np.ndarray) -> Dict[str, float]:
        """Calculate all needed features"""
        features = {}
        
        # Basic MAs for trend
        features['ma_20'] = np.mean(prices[-20:])
        features['ma_50'] = np.mean(prices[-50:])
        features['ma_200'] = np.mean(prices[-200:])
        
        # Current price relative to MAs
        current = prices[-1]
        features['price_above_200'] = 1.0 if current > features['ma_200'] else -1.0
        
        # Volatility
        returns = np.diff(prices[-50:]) / prices[-50:-1]
        features['volatility'] = np.std(returns)
        features['vol_20'] = np.std(np.diff(prices[-20:]) / prices[-20:-1])
        
        # Momentum
        features['momentum'] = (prices[-1] - prices[-20]) / prices[-20] if prices[-20] > 0 else 0
        features['trend_strength'] = abs(features['momentum']) / max(features['volatility'], 0.001)
        
        # RSI
        delta = np.diff(prices[-30:])
        gain = np.mean([d for d in delta if d > 0]) if any(d > 0 for d in delta) else 0
        loss = abs(np.mean([d for d in delta if d < 0])) if any(d < 0 for d in delta) else 0
        rs = gain / loss if loss > 0 else 0
        features['rsi'] = 100 - (100 / (1 + rs)) if rs > 0 else 50
        
        # Mean reversion (price deviation from MA50)
        features['deviation_from_ma50'] = (current - features['ma_50']) / features['ma_50']
        
        # Support/Resistance
        features['52w_high'] = np.max(prices[-252:])
        features['52w_low'] = np.min(prices[-252:])
        features['distance_to_high'] = (features['52w_high'] - current) / features['52w_high']
        
        # MACD-like indicator
        ema_12 = self._ema(prices[-50:], 12)[-1]
        ema_26 = self._ema(prices[-50:], 26)[-1]
        features['macd'] = ema_12 - ema_26
        
        return features
    
    def generate_signal(self, features: Dict[str, float], prev_signal: int = 0) -> Tuple[int, float]:
        """
        Ensemble of signals with volatility adjustment
        Combines trend, momentum, quality, and mean reversion
        """
        signals = []
        
        # Signal 1: Trend confirmation (40% weight)
        if features['ma_20'] > features['ma_50'] > features['ma_200']:
            signals.append((1, 0.4))  # Strong uptrend
        elif features['ma_20'] < features['ma_50'] < features['ma_200']:
            signals.append((-1, 0.4))  # Strong downtrend
        else:
            signals.append((0, 0.4))  # Mixed trend
        
        # Signal 2: Momentum & MACD (25% weight)
        momentum_score = 0
        if features['momentum'] > 0.01:
            momentum_score = min(1.0, features['momentum'] / 0.05)
        elif features['momentum'] < -0.01:
            momentum_score = max(-1.0, features['momentum'] / -0.05)
        
        if features['macd'] > 0:
            momentum_score = max(momentum_score, 0.5)
        
        signals.append((np.sign(momentum_score) if momentum_score != 0 else 0, 0.25))
        
        # Signal 3: Mean reversion (20% weight)
        reversion_signal = 0
        if features['deviation_from_ma50'] < -0.05:  # Price below MA50
            reversion_signal = 1  # Buy signal
        elif features['deviation_from_ma50'] > 0.05:  # Price above MA50
            reversion_signal = -1  # Sell signal
        
        signals.append((reversion_signal, 0.20))
        
        # Signal 4: RSI overbought/oversold (15% weight)
        rsi_signal = 0
        if features['rsi'] < 30:
            rsi_signal = 1
        elif features['rsi'] > 70:
            rsi_signal = -1
        
        signals.append((rsi_signal, 0.15))
        
        # Calculate weighted ensemble
        ensemble_score = sum(sig * weight for sig, weight in signals)
        
        # Determine final signal
        final_signal = 0
        if ensemble_score > 0.3:
            final_signal = 1
        elif ensemble_score < -0.3:
            final_signal = -1
        
        # Volatility-adaptive position sizing
        # High volatility = smaller position, Low volatility = larger position
        volatility_adjustment = 1.0 / (1.0 + features['volatility'] * 10)
        
        # Base position size
        position_size = 1.0
        
        # Adjust based on signal strength
        if final_signal == 1:
            position_size = 0.8 + 0.7 * abs(ensemble_score)
        elif final_signal == -1:
            position_size = 0.7 + 0.6 * abs(ensemble_score)
        
        # Apply volatility adjustment
        position_size *= volatility_adjustment
        
        # Clamp to reasonable range
        position_size = max(0.5, min(1.5, position_size))
        
        return (final_signal, position_size)
    
    def _ema(self, prices: np.ndarray, period: int) -> np.ndarray:
        """Calculate EMA"""
        if len(prices) < period:
            return prices
        ema = np.zeros(len(prices))
        ema[period-1] = np.mean(prices[:period])
        multiplier = 2 / (period + 1)
        for i in range(period, len(prices)):
            ema[i] = prices[i] * multiplier + ema[i-1] * (1 - multiplier)
        return ema


if __name__ == '__main__':
    backtester = ComprehensiveBacktester()
    backtester.run()
