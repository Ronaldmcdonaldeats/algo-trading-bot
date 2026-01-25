#!/usr/bin/env python3
"""
Phase 11 Final: Hybrid Ensemble Strategy
Combines Phase 10b Advanced Ensemble with Phase 11 Fast ML for maximum returns
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


class Phase11HybridEnsemble:
    """Hybrid ensemble combining best of Phase 10b and Phase 11"""
    
    def __init__(self):
        self.data_fetcher = HistoricalDataFetcher()
        self.benchmark_annual = 0.011
        self.target = 0.061
    
    def fetch_all_data(self, symbols: List[str]) -> Dict[str, np.ndarray]:
        """Fetch data"""
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
    
    def calculate_features(self, prices: np.ndarray) -> Dict[str, float]:
        """Phase 10b features (proven working)"""
        if len(prices) < 200:
            return {}
        
        # Moving averages
        ma50 = np.mean(prices[-50:])
        ma200 = np.mean(prices[-200:])
        
        # Trend
        trend = (ma50 - ma200) / ma200
        
        # RSI
        deltas = np.diff(prices[-14:])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        ag = np.mean(gains) if len(gains) > 0 else 0
        al = np.mean(losses) if len(losses) > 0 else 0
        
        if al == 0:
            rsi = 100.0 if ag > 0 else 50.0
        else:
            rsi = 100 - (100 / (1 + ag/al))
        
        # ATR (volatility)
        highs = np.array([prices[i] for i in range(-14, 0)])
        lows = np.array([prices[i] for i in range(-14, 0)])
        closes = prices[-14:]
        
        trs = []
        for i in range(1, len(closes)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i-1]),
                abs(lows[i] - closes[i-1])
            )
            trs.append(tr)
        
        atr = np.mean(trs) if trs else 0
        atr_ratio = atr / prices[-1] if prices[-1] != 0 else 0
        
        # Momentum
        momentum = (prices[-1] - prices[-20]) / prices[-20] if prices[-20] != 0 else 0
        
        return {
            'trend': trend,
            'rsi': rsi,
            'atr_ratio': atr_ratio,
            'momentum': momentum
        }
    
    def predict_ensemble_signal(self, features: Dict[str, float]) -> Tuple[int, float]:
        """Hybrid ensemble prediction"""
        if not features:
            return 0, 1.0
        
        trend = features.get('trend', 0)
        rsi = features.get('rsi', 50)
        momentum = features.get('momentum', 0)
        atr_ratio = features.get('atr_ratio', 0)
        
        # Expert 1: Trend expert (40%)
        trend_signal = 1.0 if trend > 0.02 else (-1.0 if trend < -0.02 else 0.0)
        
        # Expert 2: RSI expert (30%) - overbought/oversold
        if rsi > 70:
            rsi_signal = -0.7
        elif rsi < 30:
            rsi_signal = 0.7
        else:
            rsi_signal = 0.0
        
        # Expert 3: Momentum expert (20%)
        momentum_signal = 1.0 if momentum > 0.03 else (-1.0 if momentum < -0.03 else 0.0)
        
        # Expert 4: Volatility regime (10%) - avoid trading in extreme vol
        vol_factor = 1.0 if atr_ratio < 0.03 else 0.5
        
        # Ensemble vote
        vote = (trend_signal * 0.4 + rsi_signal * 0.3 + momentum_signal * 0.2) * vol_factor
        
        # Position sizing based on confidence
        if abs(vote) > 0.3:
            position_size = 1.2
        elif abs(vote) > 0.15:
            position_size = 1.0
        else:
            position_size = 0.7
        
        # Decision
        if vote > 0.15:
            return 1, position_size
        elif vote < -0.15:
            return -1, position_size
        else:
            return 0, position_size
    
    def backtest(self, prices: np.ndarray) -> float:
        """Backtest with hybrid ensemble"""
        if len(prices) < 200:
            return 0.0
        
        capital = 100000.0
        position = 0.0
        trans_cost = 0.001
        
        for i in range(200, len(prices)):
            price = prices[i]
            
            # Get features
            features = self.calculate_features(prices[:i+1])
            
            # Predict signal + position size
            signal, pos_size = self.predict_ensemble_signal(features)
            
            # Execute
            if signal == 1 and position == 0:
                position = (capital / price) * pos_size * (1 - trans_cost)
                capital = 0
            elif signal == -1 and position > 0:
                capital = position * price * (1 - trans_cost)
                position = 0
        
        # Close at end
        if position > 0:
            capital = position * prices[-1] * (1 - trans_cost)
        
        years = len(prices) / 252
        annual = (capital / 100000.0) ** (1 / years) - 1 if years > 0 else 0
        
        return annual
    
    def run(self):
        """Run backtest"""
        logger.info("Phase 11 Final: Hybrid Ensemble")
        
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
        std = np.std(annuals)
        
        logger.info(f"\n{'='*80}")
        logger.info(f"PHASE 11 FINAL: HYBRID ENSEMBLE STRATEGY")
        logger.info(f"{'='*80}")
        logger.info(f"Avg Annual Return:      {avg:7.4f} ({avg*100:6.2f}%)")
        logger.info(f"Std Deviation:          {std:7.4f}")
        logger.info(f"S&P 500 Benchmark:      {self.benchmark_annual:7.4f} ({self.benchmark_annual*100:6.2f}%)")
        logger.info(f"Outperformance:         {(avg - self.benchmark_annual):7.4f} ({(avg - self.benchmark_annual)*100:6.2f}%)")
        logger.info(f"Target (5%+):           {self.target:7.4f} ({self.target*100:6.2f}%)")
        logger.info(f"Beats Target:           {'YES!' if avg >= self.target else 'NO'}")
        logger.info(f"Stocks Beating S&P:     {sum(1 for a in annuals if a > self.benchmark_annual)}/{len(annuals)}")
        logger.info(f"{'='*80}\n")
        
        # Save
        out = Path(__file__).parent.parent.parent / 'phase11_results'
        out.mkdir(exist_ok=True)
        
        pd.DataFrame(results).to_csv(out / 'phase11_final_hybrid_results.csv', index=False)
        
        with open(out / 'PHASE11_FINAL_RESULTS.txt', 'w') as f:
            f.write("PHASE 11 FINAL: HYBRID ENSEMBLE STRATEGY\n")
            f.write("="*80 + "\n\n")
            f.write("STRATEGY COMPONENTS:\n")
            f.write("Phase 10b Foundation:\n")
            f.write("  - Trend Expert (40%):     50/200-day MA crossover\n")
            f.write("  - RSI Expert (30%):       Overbought/oversold zones\n")
            f.write("  - Momentum Expert (20%):  20-day price change\n")
            f.write("  - Volatility Filter (10%): ATR-based regime\n\n")
            f.write("Position Sizing:\n")
            f.write("  - High confidence (|vote| > 0.3): 1.2x\n")
            f.write("  - Medium confidence:              1.0x\n")
            f.write("  - Low confidence:                 0.7x\n\n")
            f.write("RESULTS:\n")
            f.write(f"  Avg Annual Return: {avg:.4f} ({avg*100:.2f}%)\n")
            f.write(f"  Std Deviation: {std:.4f}\n")
            f.write(f"  S&P 500: {self.benchmark_annual:.4f}\n")
            f.write(f"  Outperformance: {(avg - self.benchmark_annual):.4f}\n")
            f.write(f"  Beats Target: {'YES!' if avg >= self.target else 'NO'}\n\n")
            f.write("TOP 10 PERFORMERS:\n")
            top = sorted(enumerate(annuals), key=lambda x: x[1], reverse=True)[:10]
            syms = list(data.keys())
            for rank, (idx, ann) in enumerate(top, 1):
                f.write(f"  {rank:2d}. {syms[idx]:6s}: {ann:7.4f} ({ann*100:6.2f}%)\n")
            f.write("\nBOTTOM 5 UNDERPERFORMERS:\n")
            bottom = sorted(enumerate(annuals), key=lambda x: x[1])[:5]
            for rank, (idx, ann) in enumerate(bottom, 1):
                f.write(f"  {rank}. {syms[idx]:6s}: {ann:7.4f} ({ann*100:6.2f}%)\n")
        
        logger.info(f"Results saved to {out}")


if __name__ == '__main__':
    Phase11HybridEnsemble().run()
