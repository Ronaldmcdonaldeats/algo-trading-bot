#!/usr/bin/env python3
"""
Phase 12 Quick Test - Single stock to verify strategy works
"""

import sys
import logging
from typing import Dict, Tuple
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.cached_data_loader import CachedDataLoader

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


class Phase12QuickTest:
    """Quick test with single stock"""
    
    def __init__(self):
        self.loader = CachedDataLoader()
        self.benchmark_annual = 0.011
    
    def calculate_features_ultra(self, prices: np.ndarray) -> Dict[str, float]:
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
        
        return {
            'trend': trend,
            'rsi': rsi,
            'momentum': momentum,
            'mean_reversion': bb_position,
            'acceleration': acceleration,
            'vol_ratio': vol_ratio
        }
    
    def predict_ultra_signal(self, features: Dict[str, float], prev_signal: int = 0) -> Tuple[int, float]:
        if not features:
            return 0, 1.0
        
        trend = features.get('trend', 0)
        rsi = features.get('rsi', 50)
        momentum = features.get('momentum', 0)
        bb_pos = features.get('mean_reversion', 0.5)
        accel = features.get('acceleration', 0)
        vol_ratio = features.get('vol_ratio', 1.0)
        
        trend_signal = 1.0 if trend > 0.01 else (-1.0 if trend < -0.01 else 0.0)
        rsi_signal = 0.9 if rsi < 20 else (-0.9 if rsi > 80 else 0.0)
        momentum_signal = 1.0 if momentum > 0.01 else (-1.0 if momentum < -0.01 else 0.0)
        mr_signal = -0.8 if bb_pos > 0.95 else (0.8 if bb_pos < 0.05 else 0.0)
        accel_signal = 0.7 if accel > 0.005 else (-0.7 if accel < -0.005 else 0.0)
        vol_signal = 0.4 if vol_ratio > 1.2 else (-0.3 if vol_ratio < 0.8 else 0.0)
        
        vote = (trend_signal * 0.40 + 
                rsi_signal * 0.25 + 
                momentum_signal * 0.20 + 
                mr_signal * 0.10 + 
                accel_signal * 0.03 + 
                vol_signal * 0.02)
        
        if abs(vote) > 0.4:
            position_size = 1.5
        elif abs(vote) > 0.25:
            position_size = 1.3
        elif abs(vote) > 0.15:
            position_size = 1.1
        else:
            position_size = 0.7
        
        if vol_ratio < 0.8:
            position_size *= 1.2
        
        if prev_signal == 1 and vote > -0.03:
            return 1, position_size
        elif prev_signal == -1 and vote < 0.03:
            return -1, position_size
        
        if vote > 0.12:
            return 1, position_size
        elif vote < -0.12:
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
            features = self.calculate_features_ultra(prices[:i+1])
            signal, pos_size = self.predict_ultra_signal(features, prev_signal)
            
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
        logger.info("Phase 12 Quick Test (AAPL only)")
        logger.info("Loading AAPL...")
        
        data = self.loader.load_all_stocks(['AAPL'])
        
        if not data:
            logger.error("Failed to load AAPL")
            return
        
        for symbol, prices in data.items():
            logger.info(f"Backtesting {symbol} ({len(prices)} days)...")
            annual = self.backtest(prices)
            outperform = annual - self.benchmark_annual
            
            logger.info(f"\n{'='*60}")
            logger.info(f"PHASE 12 QUICK TEST - {symbol}")
            logger.info(f"{'='*60}")
            logger.info(f"Annual Return:    {annual:7.4f} ({annual*100:6.2f}%)")
            logger.info(f"Outperformance:   {outperform:7.4f} ({outperform*100:6.2f}%)")
            logger.info(f"vs S&P 500 (1.1%): {'PASS' if outperform > 0 else 'FAIL'}")
            logger.info(f"{'='*60}\n")


if __name__ == '__main__':
    Phase12QuickTest().run()
