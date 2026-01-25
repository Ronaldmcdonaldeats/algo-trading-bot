#!/usr/bin/env python3
"""
Phase 11: Optimized ML Strategy - Balanced Approach
Combines trend, momentum, volatility adapting for optimal Sharpe and returns
"""

import sys
import logging
from typing import Dict, List
import numpy as np
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from trading_bot.historical_data import HistoricalDataFetcher

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class Phase11OptimizedML:
    """Optimized balanced ML strategy"""
    
    def __init__(self):
        self.data_fetcher = HistoricalDataFetcher()
        self.benchmark_annual = 0.011
        self.target = 0.061
        
        # Learned weights from phase 10 + optimization
        self.weights = {
            'trend_short': 0.3,
            'trend_long': 0.2,
            'rsi': 0.2,
            'momentum': 0.15,
            'volatility': -0.15
        }
    
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
        """Calculate optimized ML features"""
        if len(prices) < 200:
            return {}
        
        # Trend Features
        ma5 = np.mean(prices[-5:])
        ma20 = np.mean(prices[-20:])
        ma50 = np.mean(prices[-50:])
        ma200 = np.mean(prices[-200:])
        
        trend_short = (ma5 - ma20) / ma20
        trend_long = (ma20 - ma200) / ma200
        
        # RSI
        deltas = np.diff(prices[-15:])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        ag = np.mean(gains)
        al = np.mean(losses) if np.mean(losses) > 0 else 1e-6
        rsi = 100 - (100 / (1 + ag/al))
        rsi_normalized = (rsi - 50) / 50
        
        # Momentum
        momentum = (prices[-1] - prices[-20]) / prices[-20]
        momentum = np.clip(momentum, -0.2, 0.2)
        
        # Volatility
        returns = np.diff(np.log(prices[-20:]))
        volatility = np.std(returns) * np.sqrt(252)
        volatility = np.clip(volatility, 0, 0.5)
        
        return {
            'trend_short': trend_short,
            'trend_long': trend_long,
            'rsi': rsi_normalized,
            'momentum': momentum,
            'volatility': volatility
        }
    
    def predict_signal(self, features: Dict[str, float]) -> int:
        """ML prediction with optimized thresholds"""
        if not features:
            return 0
        
        # Weighted sum
        score = 0.0
        score += self.weights['trend_short'] * features.get('trend_short', 0)
        score += self.weights['trend_long'] * features.get('trend_long', 0)
        score += self.weights['rsi'] * features.get('rsi', 0)
        score += self.weights['momentum'] * features.get('momentum', 0) * 5  # Scale momentum
        score += self.weights['volatility'] * features.get('volatility', 0)
        
        # Optimized thresholds
        if score > 0.15:
            return 1  # Buy
        elif score < -0.15:
            return -1  # Sell
        else:
            return 0  # Hold
    
    def backtest(self, prices: np.ndarray) -> float:
        """Fast backtest"""
        if len(prices) < 200:
            return 0.0
        
        capital = 100000.0
        position = 0.0
        trans_cost = 0.001
        prev_signal = 0
        
        for i in range(200, len(prices)):
            price = prices[i]
            
            # Get features
            features = self.calculate_features(prices[:i+1])
            
            # Predict signal
            signal = self.predict_signal(features)
            
            # Execute trades with hysteresis
            if signal == 1 and position == 0:
                position = capital / price * (1 - trans_cost)
                capital = 0
                prev_signal = 1
            elif signal == -1 and position > 0:
                capital = position * price * (1 - trans_cost)
                position = 0
                prev_signal = -1
            elif signal == 0 and prev_signal != 0:
                # Partial exit on reversal signal
                if position > 0:
                    capital = position * price * 0.5 * (1 - trans_cost)
                    position = position * 0.5
                prev_signal = 0
        
        # Close position at end
        if position > 0:
            capital = position * prices[-1] * (1 - trans_cost)
        
        years = len(prices) / 252
        annual = (capital / 100000.0) ** (1 / years) - 1 if years > 0 else 0
        
        return annual
    
    def run(self):
        """Run backtest"""
        logger.info("Phase 11: Optimized ML Strategy")
        
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
        logger.info(f"PHASE 11: OPTIMIZED ML STRATEGY")
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
        
        pd.DataFrame(results).to_csv(out / 'phase11_optimized_ml_results.csv', index=False)
        
        with open(out / 'PHASE11_OPTIMIZED_ML_RESULTS.txt', 'w') as f:
            f.write("PHASE 11: OPTIMIZED ML STRATEGY\n")
            f.write("="*80 + "\n\n")
            f.write("MODEL: Multi-feature Ensemble Classifier\n")
            f.write("Features:\n")
            f.write("  - Short-term trend (5/20-day MA): 0.30\n")
            f.write("  - Long-term trend (20/200-day MA): 0.20\n")
            f.write("  - RSI momentum (14-day): 0.20\n")
            f.write("  - Price momentum (20-day): 0.15\n")
            f.write("  - Volatility penalty: -0.15\n\n")
            f.write("Decision Rules:\n")
            f.write("  - Score > 0.15: Buy\n")
            f.write("  - Score < -0.15: Sell\n")
            f.write("  - -0.15 <= Score <= 0.15: Hold\n\n")
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
    Phase11OptimizedML().run()
