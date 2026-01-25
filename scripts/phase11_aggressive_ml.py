#!/usr/bin/env python3
"""
Phase 11: Aggressive ML Strategy with Adaptive Position Sizing
Incorporates market timing and aggressive entry/exit signals
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


class Phase11AggressiveML:
    """Aggressive ML strategy with adaptive position sizing"""
    
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
    
    def calculate_advanced_features(self, prices: np.ndarray) -> Dict[str, float]:
        """Calculate advanced ML features"""
        if len(prices) < 200:
            return {}
        
        # 1. TREND STRENGTH (more aggressive)
        ma5 = np.mean(prices[-5:])
        ma20 = np.mean(prices[-20:])
        ma50 = np.mean(prices[-50:])
        ma200 = np.mean(prices[-200:])
        
        # Multi-level trend
        trend_short = (ma5 - ma20) / ma20
        trend_medium = (ma20 - ma50) / ma50
        trend_long = (ma50 - ma200) / ma200
        
        combined_trend = trend_short * 0.5 + trend_medium * 0.3 + trend_long * 0.2
        trend = np.tanh(combined_trend * 10)
        
        # 2. VOLATILITY-ADJUSTED MOMENTUM (aggressive on low vol)
        rets = np.diff(np.log(prices[-20:]))
        volatility = np.std(rets) * np.sqrt(252)
        vol_factor = 1.0 if volatility < 0.2 else 0.5  # 2x boost for low vol
        
        momentum = (prices[-1] - prices[-20]) / prices[-20]
        momentum_adj = np.clip(momentum * vol_factor, -0.5, 0.5)
        
        # 3. MEAN REVERSION (overshoot detection)
        ma_price = np.mean(prices[-50:])
        deviation = (prices[-1] - ma_price) / ma_price
        mean_reversion = -np.tanh(deviation * 8)  # Negative: mean reverts
        
        # 4. RSI (aggressive buy/sell zones)
        deltas = np.diff(prices[-15:])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        ag = np.mean(gains)
        al = np.mean(losses) if np.mean(losses) > 0 else 1e-6
        rsi = 100 - (100 / (1 + ag/al))
        
        # Convert to signal: overbought (-1), oversold (+1)
        if rsi > 70:
            rsi_signal = -0.8  # Sell
        elif rsi < 30:
            rsi_signal = 0.8  # Buy
        else:
            rsi_signal = (50 - rsi) / 50  # Neutral zone
        
        # 5. PRICE ACCELERATION
        accel_5 = (prices[-1] - prices[-5]) / prices[-5]
        accel_20 = (prices[-5] - prices[-25]) / prices[-25]
        acceleration = (accel_5 - accel_20) / max(abs(accel_20), 0.001)
        acceleration = np.clip(acceleration, -1, 1)
        
        # 6. VOLATILITY TREND (rising vol = more trading)
        vol_short = np.std(np.diff(np.log(prices[-10:])))
        vol_long = np.std(np.diff(np.log(prices[-50:])))
        vol_trend = 1.0 + (vol_short - vol_long) / (vol_long + 1e-6)
        vol_trend = np.clip(vol_trend, 0.5, 2.0)
        
        return {
            'trend': combined_trend,
            'rsi': rsi_signal,
            'momentum': momentum_adj,
            'mean_reversion': mean_reversion,
            'acceleration': acceleration,
            'vol_factor': vol_trend
        }
    
    def predict_signal_advanced(self, features: Dict[str, float], prev_signal: int = 0) -> Tuple[int, float]:
        """Advanced ML prediction with position sizing"""
        if not features:
            return 0, 1.0
        
        # Weighted ensemble: each feature expert votes
        trend = features.get('trend', 0) * 0.25
        rsi = features.get('rsi', 0) * 0.25
        momentum = features.get('momentum', 0) * 0.2
        mean_reversion = features.get('mean_reversion', 0) * 0.2
        acceleration = features.get('acceleration', 0) * 0.1
        
        # Momentum expert
        momentum_signal = 1.0 if momentum > 0.05 else (-1.0 if momentum < -0.05 else 0.0)
        
        # Trend expert
        trend_signal = 1.0 if trend > 0.03 else (-1.0 if trend < -0.03 else 0.0)
        
        # Mean reversion expert
        mr_signal = 1.0 if mean_reversion > 0.3 else (-1.0 if mean_reversion < -0.3 else 0.0)
        
        # Ensemble vote
        vote = momentum_signal * 0.35 + trend_signal * 0.35 + rsi * 0.2 + mr_signal * 0.1
        
        # Position sizing (vol_factor increases size in calm markets)
        position_size = min(2.0, 1.0 * features.get('vol_factor', 1.0))
        
        # Hysteresis: stick with current signal
        if prev_signal == 1 and vote > -0.1:
            return 1, position_size
        elif prev_signal == -1 and vote < 0.1:
            return -1, position_size
        
        # New signal
        if vote > 0.2:
            return 1, position_size
        elif vote < -0.2:
            return -1, position_size
        else:
            return 0, 1.0
    
    def backtest(self, prices: np.ndarray) -> float:
        """Backtest with aggressive ML signals"""
        if len(prices) < 200:
            return 0.0
        
        capital = 100000.0
        position = 0.0
        trans_cost = 0.001
        prev_signal = 0
        
        for i in range(200, len(prices)):
            price = prices[i]
            
            # Get ML features
            features = self.calculate_advanced_features(prices[:i+1])
            
            # Predict signal + position size
            signal, pos_size = self.predict_signal_advanced(features, prev_signal)
            
            # Execute
            if signal == 1 and position == 0:
                position = (capital / price) * pos_size * (1 - trans_cost)
                capital = 0
                prev_signal = 1
            elif signal == -1 and position > 0:
                capital = position * price * (1 - trans_cost)
                position = 0
                prev_signal = -1
            elif signal == 0 and position > 0:
                # Partial exit on neutral (more conservative)
                capital = position * price * 0.3 * (1 - trans_cost)
                position = position * 0.7
                prev_signal = 0
        
        if position > 0:
            capital = position * prices[-1] * (1 - trans_cost)
        
        years = len(prices) / 252
        annual = (capital / 100000.0) ** (1 / years) - 1 if years > 0 else 0
        
        return annual
    
    def run(self):
        """Run backtest"""
        logger.info("Phase 11: Aggressive ML Strategy")
        
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
        
        logger.info(f"\n{'='*80}")
        logger.info(f"PHASE 11: AGGRESSIVE ML STRATEGY")
        logger.info(f"{'='*80}")
        logger.info(f"Avg Annual Return:      {avg:7.4f} ({avg*100:6.2f}%)")
        logger.info(f"S&P 500 Benchmark:      {self.benchmark_annual:7.4f} ({self.benchmark_annual*100:6.2f}%)")
        logger.info(f"Outperformance:         {(avg - self.benchmark_annual):7.4f} ({(avg - self.benchmark_annual)*100:6.2f}%)")
        logger.info(f"Target (5%+):           {self.target:7.4f} ({self.target*100:6.2f}%)")
        logger.info(f"Beats Target:           {'YES!' if avg >= self.target else 'NO'}")
        logger.info(f"Stocks Beating S&P:     {sum(1 for a in annuals if a > self.benchmark_annual)}/{len(annuals)}")
        logger.info(f"{'='*80}\n")
        
        # Save
        out = Path(__file__).parent.parent.parent / 'phase11_results'
        out.mkdir(exist_ok=True)
        
        pd.DataFrame(results).to_csv(out / 'phase11_aggressive_ml_results.csv', index=False)
        
        with open(out / 'PHASE11_AGGRESSIVE_ML_RESULTS.txt', 'w') as f:
            f.write("PHASE 11: AGGRESSIVE ML STRATEGY\n")
            f.write("="*80 + "\n\n")
            f.write("MODEL: Ensemble of Expert Classifiers\n")
            f.write("  1. Momentum Expert (35%):      Positive/negative momentum\n")
            f.write("  2. Trend Expert (35%):        Multi-level trend (5/20/50/200-day)\n")
            f.write("  3. RSI Expert (20%):          Overbought/oversold zones\n")
            f.write("  4. Mean Reversion (10%):      Price overshooting MA\n\n")
            f.write("POSITION SIZING:\n")
            f.write("  - Base: 1.0x\n")
            f.write("  - Low volatility boost: 2.0x\n")
            f.write("  - Hysteresis: Stick with signal until reversal\n\n")
            f.write("DECISION RULE:\n")
            f.write("  - Ensemble vote > 0.2: Buy with position sizing\n")
            f.write("  - Ensemble vote < -0.2: Sell\n")
            f.write("  - Neutral zone: Hold or 30% partial exit\n\n")
            f.write(f"RESULTS:\n")
            f.write(f"  Avg Annual Return: {avg:.4f} ({avg*100:.2f}%)\n")
            f.write(f"  S&P 500: {self.benchmark_annual:.4f}\n")
            f.write(f"  Outperformance: {(avg - self.benchmark_annual):.4f}\n")
            f.write(f"  Beats Target: {'YES!' if avg >= self.target else 'NO'}\n\n")
            f.write("TOP 10 PERFORMERS:\n")
            top = sorted(enumerate(annuals), key=lambda x: x[1], reverse=True)[:10]
            syms = list(data.keys())
            for rank, (idx, ann) in enumerate(top, 1):
                f.write(f"  {rank:2d}. {syms[idx]:6s}: {ann:7.4f} ({ann*100:6.2f}%)\n")
        
        logger.info(f"Results saved to {out}")


if __name__ == '__main__':
    Phase11AggressiveML().run()
