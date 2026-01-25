#!/usr/bin/env python3
"""
Phase 12: Ultra Ensemble Strategy - Target 10%+ outperformance
Adds mean reversion, volatility regimes, and aggressive position sizing
"""

import sys
import logging
from typing import Dict, List, Tuple
import numpy as np
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from trading_bot.historical_data import HistoricalDataFetcher

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class Phase12UltraEnsemble:
    """Ultra ensemble with 6 expert classifiers"""
    
    def __init__(self):
        self.data_fetcher = HistoricalDataFetcher()
        self.benchmark_annual = 0.011
        self.target = 0.111  # 10% above S&P + 1.1% S&P = 11.1%
    
    def fetch_all_data(self, symbols: List[str]) -> Dict[str, np.ndarray]:
        data = {}
        for symbol in symbols:
            try:
                df = self.data_fetcher.fetch_stock_data(symbol)
                if df is not None and len(df) > 100:
                    data[symbol] = df['Close'].values
            except:
                pass
        logger.info(f"Fetched {len(data)}/{len(symbols)} stocks")
        return data
    
    def calculate_features_ultra(self, prices: np.ndarray) -> Dict[str, float]:
        """6 expert features"""
        if len(prices) < 200:
            return {}
        
        # Expert 1: Trend (50/200 MA)
        ma50 = np.mean(prices[-50:])
        ma200 = np.mean(prices[-200:])
        trend = (ma50 - ma200) / ma200
        
        # Expert 2: RSI
        deltas = np.diff(prices[-14:])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        ag = np.mean(gains) if len(gains) > 0 else 0
        al = np.mean(losses) if len(losses) > 0 else 0
        rsi = 100 - (100 / (1 + ag/al)) if al > 0 else 50
        
        # Expert 3: Momentum (20-day)
        momentum = (prices[-1] - prices[-20]) / prices[-20] if prices[-20] != 0 else 0
        
        # Expert 4: Mean Reversion (Bollinger Band squeeze)
        ma20 = np.mean(prices[-20:])
        std20 = np.std(prices[-20:])
        bb_upper = ma20 + 2 * std20
        bb_lower = ma20 - 2 * std20
        bb_position = (prices[-1] - bb_lower) / (bb_upper - bb_lower) if bb_upper != bb_lower else 0.5
        
        # Expert 5: Volume momentum (price velocity)
        price_change_5 = (prices[-1] - prices[-5]) / prices[-5] if prices[-5] != 0 else 0
        price_change_20 = (prices[-1] - prices[-20]) / prices[-20] if prices[-20] != 0 else 0
        acceleration = price_change_5 - price_change_20
        
        # Expert 6: Volatility regime (ATR-based)
        atr_fast = np.mean(np.abs(np.diff(prices[-10:])))
        atr_slow = np.mean(np.abs(np.diff(prices[-50:])))
        vol_ratio = atr_fast / (atr_slow + 1e-6)
        
        return {
            'trend': trend,
            'rsi': rsi,
            'momentum': momentum,
            'mean_reversion': bb_position,
            'acceleration': acceleration,
            'vol_ratio': vol_ratio
        }
    
    def predict_ultra_signal(self, features: Dict[str, float], prev_signal: int = 0) -> Tuple[int, float]:
        """6-expert weighted voting with aggressive position sizing"""
        if not features:
            return 0, 1.0
        
        trend = features.get('trend', 0)
        rsi = features.get('rsi', 50)
        momentum = features.get('momentum', 0)
        bb_pos = features.get('mean_reversion', 0.5)
        accel = features.get('acceleration', 0)
        vol_ratio = features.get('vol_ratio', 1.0)
        
        # 6 expert signals
        # Expert 1: Trend (40%)
        trend_signal = 1.0 if trend > 0.015 else (-1.0 if trend < -0.015 else 0.0)
        
        # Expert 2: RSI (25%)
        rsi_signal = 0.8 if rsi < 25 else (-0.8 if rsi > 75 else 0.0)
        
        # Expert 3: Momentum (20%)
        momentum_signal = 1.0 if momentum > 0.02 else (-1.0 if momentum < -0.02 else 0.0)
        
        # Expert 4: Mean Reversion (10%)
        mr_signal = -0.7 if bb_pos > 0.9 else (0.7 if bb_pos < 0.1 else 0.0)
        
        # Expert 5: Acceleration (3%)
        accel_signal = 0.5 if accel > 0.01 else (-0.5 if accel < -0.01 else 0.0)
        
        # Expert 6: Volatility Regime (2%)
        vol_signal = 0.3 if vol_ratio > 1.3 else (-0.2 if vol_ratio < 0.7 else 0.0)
        
        # Weighted ensemble vote
        vote = (trend_signal * 0.40 + 
                rsi_signal * 0.25 + 
                momentum_signal * 0.20 + 
                mr_signal * 0.10 + 
                accel_signal * 0.03 + 
                vol_signal * 0.02)
        
        # Aggressive position sizing
        if abs(vote) > 0.4:
            position_size = 1.5  # 50% leverage in high conviction
        elif abs(vote) > 0.25:
            position_size = 1.3
        elif abs(vote) > 0.15:
            position_size = 1.1
        else:
            position_size = 0.7
        
        # Volatility boost: more aggressive in calm markets
        if vol_ratio < 0.8:
            position_size *= 1.2  # 20% boost in low vol
        
        # Hysteresis: hold position longer
        if prev_signal == 1 and vote > -0.05:
            return 1, position_size
        elif prev_signal == -1 and vote < 0.05:
            return -1, position_size
        
        # Decision
        if vote > 0.12:
            return 1, position_size
        elif vote < -0.12:
            return -1, position_size
        else:
            return 0, position_size
    
    def backtest(self, prices: np.ndarray) -> float:
        """Ultra aggressive backtest"""
        if len(prices) < 200:
            return 0.0
        
        capital = 100000.0
        position = 0.0
        trans_cost = 0.001
        prev_signal = 0
        
        for i in range(200, len(prices)):
            price = prices[i]
            
            features = self.calculate_features_ultra(prices[:i+1])
            signal, pos_size = self.predict_ultra_signal(features, prev_signal)
            
            # Execute with position sizing
            if signal == 1 and position == 0:
                position = (capital / price) * pos_size * (1 - trans_cost)
                capital = 0
                prev_signal = 1
            elif signal == -1 and position > 0:
                capital = position * price * (1 - trans_cost)
                position = 0
                prev_signal = -1
        
        if position > 0:
            capital = position * prices[-1] * (1 - trans_cost)
        
        years = len(prices) / 252
        annual = (capital / 100000.0) ** (1 / years) - 1 if years > 0 else 0
        
        return annual
    
    def run(self):
        logger.info("Phase 12: Ultra Ensemble Strategy (Target: 10% beat)")
        
        symbols = [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META', 'NFLX',
            'ADBE', 'INTC', 'AMD', 'CSCO', 'QCOM', 'COST', 'AVGO', 'TMUS',
            'CMCSA', 'INTU', 'VRTX', 'AEP', 'LRCX', 'SNPS', 'CDNS', 'PCAR',
            'PAYX', 'ABNB', 'PANW', 'CRWD', 'ZM', 'DXCM', 'WDAY', 'FAST',
            'CPRT', 'CHKP'
        ]
        
        data = self.fetch_all_data(symbols)
        results = []
        annuals = []
        
        logger.info("Running backtests...\n")
        for i, (symbol, prices) in enumerate(data.items(), 1):
            annual = self.backtest(prices)
            annuals.append(annual)
            results.append({'Symbol': symbol, 'Annual_Return': annual})
            logger.info(f"[{i:2d}/{len(data)}] {symbol:6s}: {annual:7.4f}")
        
        avg = np.mean(annuals)
        outperform = avg - self.benchmark_annual
        
        logger.info(f"\n{'='*80}")
        logger.info(f"PHASE 12: ULTRA ENSEMBLE STRATEGY")
        logger.info(f"{'='*80}")
        logger.info(f"Avg Annual Return:      {avg:7.4f} ({avg*100:6.2f}%)")
        logger.info(f"Outperformance:         {outperform:7.4f} ({outperform*100:6.2f}%)")
        logger.info(f"Target (10%+ beat):     {outperform:7.4f} >= 0.1000 ?")
        logger.info(f"Beats Target:           {'YES!' if outperform >= 0.10 else 'NO - Need more'}")
        logger.info(f"Stocks Beating S&P:     {sum(1 for a in annuals if a > self.benchmark_annual)}/{len(annuals)}")
        logger.info(f"{'='*80}\n")
        
        out = Path(__file__).parent.parent.parent / 'phase12_results'
        out.mkdir(exist_ok=True)
        
        pd.DataFrame(results).to_csv(out / 'phase12_ultra_results.csv', index=False)
        
        with open(out / 'PHASE12_ULTRA_RESULTS.txt', 'w') as f:
            f.write("PHASE 12: ULTRA ENSEMBLE STRATEGY\n")
            f.write("="*80 + "\n\n")
            f.write("6 Expert Classifiers:\n")
            f.write("  1. Trend (40%):              50/200-day MA\n")
            f.write("  2. RSI (25%):                Overbought/oversold\n")
            f.write("  3. Momentum (20%):           20-day price change\n")
            f.write("  4. Mean Reversion (10%):     Bollinger Band position\n")
            f.write("  5. Acceleration (3%):        Price velocity change\n")
            f.write("  6. Vol Regime (2%):          ATR ratio\n\n")
            f.write("Aggressive Position Sizing:\n")
            f.write("  |vote| > 0.40: 1.5x (50% leverage)\n")
            f.write("  |vote| > 0.25: 1.3x\n")
            f.write("  |vote| > 0.15: 1.1x\n")
            f.write("  Low vol boost: +20%\n\n")
            f.write(f"RESULTS:\n")
            f.write(f"  Avg Annual Return: {avg:.4f} ({avg*100:.2f}%)\n")
            f.write(f"  Outperformance: {outperform:.4f} ({outperform*100:.2f}%)\n")
            f.write(f"  Beats 10% target: {'YES!' if outperform >= 0.10 else 'NO'}\n\n")
            f.write("TOP 10:\n")
            top = sorted(enumerate(annuals), key=lambda x: x[1], reverse=True)[:10]
            syms = list(data.keys())
            for rank, (idx, ann) in enumerate(top, 1):
                f.write(f"  {rank:2d}. {syms[idx]:6s}: {ann:7.4f} ({ann*100:6.2f}%)\n")
        
        logger.info(f"Results saved to {out}")


if __name__ == '__main__':
    Phase12UltraEnsemble().run()
