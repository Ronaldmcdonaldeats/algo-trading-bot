#!/usr/bin/env python3
"""
Phase 13: Extreme Ensemble - Fast with cached data
"""

import sys
import logging
from typing import Dict, List, Tuple
import numpy as np
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.cached_data_loader import CachedDataLoader

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class Phase13Extreme:
    """8 expert ensemble with cached data"""
    
    def __init__(self):
        self.loader = CachedDataLoader()
        self.benchmark_annual = 0.011
        self.target = 0.15
    
    def calculate_features_extreme(self, prices: np.ndarray) -> Dict[str, float]:
        if len(prices) < 200:
            return {}
        
        ma50 = np.mean(prices[-50:])
        ma200 = np.mean(prices[-200:])
        trend = (ma50 - ma200) / ma200
        
        deltas = np.diff(prices[-14:])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        ag = np.mean(gains) if len(gains) > 0 else 0
        al = np.mean(losses) if len(losses) > 0 else 0
        rsi = 100 - (100 / (1 + ag/al)) if al > 0 else 50
        
        momentum = (prices[-1] - prices[-20]) / prices[-20] if prices[-20] != 0 else 0
        
        ma20 = np.mean(prices[-20:])
        std20 = np.std(prices[-20:])
        bb_upper = ma20 + 2 * std20
        bb_lower = ma20 - 2 * std20
        bb_position = (prices[-1] - bb_lower) / (bb_upper - bb_lower) if bb_upper != bb_lower else 0.5
        
        accel_5 = (prices[-1] - prices[-5]) / prices[-5] if prices[-5] != 0 else 0
        accel_20 = (prices[-1] - prices[-20]) / prices[-20] if prices[-20] != 0 else 0
        acceleration = accel_5 - accel_20
        
        atr_fast = np.mean(np.abs(np.diff(prices[-10:])))
        atr_slow = np.mean(np.abs(np.diff(prices[-50:])))
        vol_ratio = atr_fast / (atr_slow + 1e-6)
        
        ma3 = np.mean(prices[-3:])
        ma10 = np.mean(prices[-10:])
        ma20_fast = np.mean(prices[-20:])
        trend_3 = (ma3 - ma10) / ma10
        trend_10 = (ma10 - ma20_fast) / ma20_fast
        multi_trend = trend_3 + trend_10
        
        recent_vol = np.std(np.diff(np.log(prices[-10:])))
        older_vol = np.std(np.diff(np.log(prices[-50:-10])))
        vol_spike = (recent_vol - older_vol) / (older_vol + 1e-6)
        
        return {
            'trend': trend,
            'rsi': rsi,
            'momentum': momentum,
            'mean_reversion': bb_position,
            'acceleration': acceleration,
            'vol_ratio': vol_ratio,
            'multi_trend': multi_trend,
            'vol_spike': vol_spike
        }
    
    def predict_extreme_signal(self, features: Dict[str, float], prev_signal: int = 0) -> Tuple[int, float]:
        if not features:
            return 0, 1.0
        
        trend = features.get('trend', 0)
        rsi = features.get('rsi', 50)
        momentum = features.get('momentum', 0)
        bb_pos = features.get('mean_reversion', 0.5)
        accel = features.get('acceleration', 0)
        vol_ratio = features.get('vol_ratio', 1.0)
        multi_trend = features.get('multi_trend', 0)
        vol_spike = features.get('vol_spike', 0)
        
        trend_signal = 1.0 if trend > 0.01 else (-1.0 if trend < -0.01 else 0.0)
        rsi_signal = 0.9 if rsi < 20 else (-0.9 if rsi > 80 else 0.0)
        momentum_signal = 1.0 if momentum > 0.01 else (-1.0 if momentum < -0.01 else 0.0)
        mr_signal = -0.8 if bb_pos > 0.95 else (0.8 if bb_pos < 0.05 else 0.0)
        accel_signal = 0.7 if accel > 0.005 else (-0.7 if accel < -0.005 else 0.0)
        vol_signal = 0.4 if vol_ratio > 1.2 else (-0.3 if vol_ratio < 0.8 else 0.0)
        multi_signal = 1.0 if multi_trend > 0.01 else (-1.0 if multi_trend < -0.01 else 0.0)
        vol_spike_signal = 0.3 if vol_spike > 0.2 else (-0.2 if vol_spike < -0.2 else 0.0)
        
        vote = (trend_signal * 0.40 + 
                rsi_signal * 0.25 + 
                momentum_signal * 0.15 + 
                mr_signal * 0.10 + 
                accel_signal * 0.05 + 
                vol_signal * 0.03 + 
                multi_signal * 0.01 + 
                vol_spike_signal * 0.01)
        
        if abs(vote) > 0.5:
            position_size = 2.0
        elif abs(vote) > 0.35:
            position_size = 1.7
        elif abs(vote) > 0.25:
            position_size = 1.4
        elif abs(vote) > 0.15:
            position_size = 1.1
        else:
            position_size = 0.6
        
        if vol_ratio < 0.7:
            position_size *= 1.3
        elif vol_ratio < 0.9:
            position_size *= 1.15
        
        if prev_signal == 1 and vote > -0.03:
            return 1, position_size
        elif prev_signal == -1 and vote < 0.03:
            return -1, position_size
        
        if vote > 0.1:
            return 1, position_size
        elif vote < -0.1:
            return -1, position_size
        else:
            return 0, position_size
    
    def backtest(self, prices: np.ndarray) -> float:
        if len(prices) < 200:
            return 0.0
        
        capital = 100000.0
        position = 0.0
        trans_cost = 0.001
        prev_signal = 0
        
        for i in range(200, len(prices)):
            price = prices[i]
            features = self.calculate_features_extreme(prices[:i+1])
            signal, pos_size = self.predict_extreme_signal(features, prev_signal)
            
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
        logger.info("Phase 13: Extreme Ensemble (using cached data)")
        
        symbols = [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META', 'NFLX',
            'ADBE', 'INTC', 'AMD', 'CSCO', 'QCOM', 'COST', 'AVGO', 'TMUS',
            'CMCSA', 'INTU', 'VRTX', 'AEP', 'LRCX', 'SNPS', 'CDNS', 'PCAR',
            'PAYX', 'ABNB', 'PANW', 'CRWD', 'ZM', 'DXCM', 'WDAY', 'FAST',
            'CPRT', 'CHKP'
        ]
        
        logger.info("Loading data from cache...")
        data = self.loader.load_all_stocks(symbols)
        
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
        logger.info(f"PHASE 13: EXTREME ENSEMBLE")
        logger.info(f"{'='*80}")
        logger.info(f"Avg Annual Return:      {avg:7.4f} ({avg*100:6.2f}%)")
        logger.info(f"Outperformance:         {outperform:7.4f} ({outperform*100:6.2f}%)")
        logger.info(f"Target (15%+ beat):     {'YES!' if outperform >= 0.15 else 'NO'}")
        logger.info(f"Stocks Beating S&P:     {sum(1 for a in annuals if a > self.benchmark_annual)}/{len(annuals)}")
        logger.info(f"{'='*80}\n")
        
        out = Path(__file__).parent.parent.parent / 'phase13_results'
        out.mkdir(exist_ok=True)
        pd.DataFrame(results).to_csv(out / 'phase13_extreme_results.csv', index=False)
        logger.info(f"Results saved to {out}")


if __name__ == '__main__':
    Phase13Extreme().run()
