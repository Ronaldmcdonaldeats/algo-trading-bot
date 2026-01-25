#!/usr/bin/env python3
"""
Phase 14: Refined Hybrid - Build on Phase 12's success with selective enhancements
Phase 12 achieved 11.15% (10.05% beat). Phase 14 targets 12%+ beat with conservative improvements.
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


class Phase14Refined:
    """Conservative improvements on Phase 12's proven 11.15% strategy"""
    
    def __init__(self):
        self.loader = CachedDataLoader()
        self.benchmark_annual = 0.011
        self.target = 0.12
    
    def calculate_features_refined(self, prices: np.ndarray) -> Dict[str, float]:
        if len(prices) < 200:
            return {}
        
        # Core features from Phase 12 (proven working)
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
        
        # NEW: Profit-taking indicator (avoid holding through reversals)
        prices_5d_ago = prices[-5] if len(prices) > 5 else prices[-1]
        recent_gain = (prices[-1] - prices_5d_ago) / prices_5d_ago
        
        # NEW: Confirm trend with multiple timeframes
        ma10 = np.mean(prices[-10:])
        trend_confirm = 1.0 if (ma50 > ma200 and ma10 > ma50) else (-1.0 if (ma50 < ma200 and ma10 < ma50) else 0.0)
        
        return {
            'trend': trend,
            'rsi': rsi,
            'momentum': momentum,
            'mean_reversion': bb_position,
            'acceleration': acceleration,
            'vol_ratio': vol_ratio,
            'recent_gain': recent_gain,
            'trend_confirm': trend_confirm
        }
    
    def predict_refined_signal(self, features: Dict[str, float], prev_signal: int = 0) -> Tuple[int, float]:
        if not features:
            return 0, 1.0
        
        trend = features.get('trend', 0)
        rsi = features.get('rsi', 50)
        momentum = features.get('momentum', 0)
        bb_pos = features.get('mean_reversion', 0.5)
        accel = features.get('acceleration', 0)
        vol_ratio = features.get('vol_ratio', 1.0)
        recent_gain = features.get('recent_gain', 0)
        trend_confirm = features.get('trend_confirm', 0)
        
        # Phase 12 base weights (proven 11.15%)
        trend_signal = 1.0 if trend > 0.01 else (-1.0 if trend < -0.01 else 0.0)
        rsi_signal = 0.9 if rsi < 20 else (-0.9 if rsi > 80 else 0.0)
        momentum_signal = 1.0 if momentum > 0.01 else (-1.0 if momentum < -0.01 else 0.0)
        mr_signal = -0.8 if bb_pos > 0.95 else (0.8 if bb_pos < 0.05 else 0.0)
        accel_signal = 0.7 if accel > 0.005 else (-0.7 if accel < -0.005 else 0.0)
        vol_signal = 0.4 if vol_ratio > 1.2 else (-0.3 if vol_ratio < 0.8 else 0.0)
        
        # NEW: Profit-taking filter (take gains when momentum reverses)
        profit_take_signal = -0.3 if (prev_signal == 1 and recent_gain > 0.03 and momentum < 0) else 0.0
        
        # NEW: Trend confirmation gives confidence boost
        confirm_boost = 0.1 if trend_confirm != 0 else 0.0
        
        # Phase 12 weights + new signals
        vote = (trend_signal * 0.40 + 
                rsi_signal * 0.25 + 
                momentum_signal * 0.15 + 
                mr_signal * 0.10 + 
                accel_signal * 0.05 + 
                vol_signal * 0.03 + 
                profit_take_signal * 0.01 + 
                confirm_boost * 0.01)
        
        # Phase 12 position sizing (conservative, but improved)
        if abs(vote) > 0.4:
            position_size = 1.5
        elif abs(vote) > 0.25:
            position_size = 1.3
        elif abs(vote) > 0.15:
            position_size = 1.1
        else:
            position_size = 0.7
        
        # Phase 12 volatility boost (slightly enhanced)
        if vol_ratio < 0.8:
            position_size *= 1.2
        elif vol_ratio < 0.95:
            position_size *= 1.1
        
        # Phase 12 hysteresis with profit-taking exit
        if prev_signal == 1:
            if vote > -0.05 and profit_take_signal == 0:
                return 1, position_size
            elif profit_take_signal < 0:
                return 0, position_size
        elif prev_signal == -1:
            if vote < 0.05:
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
        entry_price = 0.0
        
        for i in range(200, len(prices)):
            price = prices[i]
            features = self.calculate_features_refined(prices[:i+1])
            signal, pos_size = self.predict_refined_signal(features, prev_signal)
            
            if signal == 1 and position == 0:
                position = (capital / price) * pos_size * (1 - trans_cost)
                capital = 0
                entry_price = price
                prev_signal = 1
            elif signal == -1 and position > 0:
                capital = position * price * (1 - trans_cost)
                position = 0
                prev_signal = -1
            elif signal == 0 and position > 0:
                capital = position * price * (1 - trans_cost)
                position = 0
                prev_signal = 0
        
        if position > 0:
            capital = position * prices[-1] * (1 - trans_cost)
        
        years = len(prices) / 252
        annual = (capital / 100000.0) ** (1 / years) - 1 if years > 0 else 0
        return annual
    
    def run(self):
        logger.info("Phase 14: Refined Hybrid (build on Phase 12's 11.15%)")
        
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
        logger.info(f"PHASE 14: REFINED HYBRID")
        logger.info(f"{'='*80}")
        logger.info(f"Avg Annual Return:      {avg:7.4f} ({avg*100:6.2f}%)")
        logger.info(f"Outperformance:         {outperform:7.4f} ({outperform*100:6.2f}%)")
        logger.info(f"Target (12%+ beat):     {'YES!' if outperform >= 0.12 else 'NO'}")
        logger.info(f"Stocks Beating S&P:     {sum(1 for a in annuals if a > self.benchmark_annual)}/{len(annuals)}")
        logger.info(f"{'='*80}\n")
        
        out = Path(__file__).parent.parent.parent / 'phase14_results'
        out.mkdir(exist_ok=True)
        pd.DataFrame(results).to_csv(out / 'phase14_refined_results.csv', index=False)
        logger.info(f"Results saved to {out}")


if __name__ == '__main__':
    Phase14Refined().run()
