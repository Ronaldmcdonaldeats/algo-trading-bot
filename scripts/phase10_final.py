#!/usr/bin/env python3
"""
Phase 10 FINAL: Optimized Adaptive Strategy
Combines regime detection + momentum + selective entries = 5%+ target
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


class Phase10FinalOptimized:
    """Final optimized strategy targeting 5%+ returns"""
    
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
        return data
    
    def calculate_rsi(self, prices: np.ndarray, window: int = 14) -> float:
        """RSI"""
        if len(prices) < window + 1:
            return 50.0
        deltas = np.diff(prices[-window-1:])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        ag = np.mean(gains)
        al = np.mean(losses)
        if al == 0:
            return 100.0 if ag > 0 else 50.0
        return 100 - (100 / (1 + ag/al))
    
    def calculate_macd(self, prices: np.ndarray) -> float:
        """MACD signal (fast-slow moving averages)"""
        if len(prices) < 27:
            return 0.0
        ema12 = np.mean(prices[-12:])
        ema26 = np.mean(prices[-26:])
        return ema12 - ema26
    
    def calculate_atr(self, prices: np.ndarray, window: int = 14) -> float:
        """Average True Range for volatility"""
        if len(prices) < window:
            return 0.0
        returns = np.diff(prices[-window:]) / prices[-window:-1]
        return np.mean(np.abs(returns))
    
    def backtest(self, prices: np.ndarray) -> float:
        """Optimized backtest"""
        if len(prices) < 200:
            return 0.0
        
        capital = 100000.0
        position = 0.0
        trans_cost = 0.001
        
        for i in range(200, len(prices)):
            price = prices[i]
            
            # Get indicators
            ma200 = np.mean(prices[max(0, i-200):i])
            ma50 = np.mean(prices[max(0, i-50):i])
            ma20 = np.mean(prices[max(0, i-20):i])
            
            trend = (price - ma200) / ma200
            
            rsi = self.calculate_rsi(prices[:i+1])
            macd = self.calculate_macd(prices[:i+1])
            atr = self.calculate_atr(prices[:i+1])
            
            # Multi-factor signals
            signal = 0
            
            # BULL: Strong uptrend
            if trend > 0.15 and ma20 > ma50 > ma200:
                # Confirm with momentum
                if rsi > 40 and rsi < 80 and macd > 0:
                    signal = 1
            
            # BEAR: Strong downtrend
            elif trend < -0.15 and ma20 < ma50 < ma200:
                # RSI oversold and MACD negative
                if rsi < 35 and macd < 0:
                    signal = 1  # Buy dips in downtrend
                elif rsi > 70:
                    signal = -1  # Sell bounces
            
            # SIDEWAYS: Mean reversion
            else:
                if rsi < 25:
                    signal = 1
                elif rsi > 75:
                    signal = -1
                elif macd > 0 and ma20 > ma50:
                    signal = 1
                elif macd < 0 and ma20 < ma50:
                    signal = -1
            
            # Execute
            if signal == 1 and position == 0:
                position = capital / price * (1 - trans_cost)
                capital = 0
            elif signal == -1 and position > 0:
                capital = position * price * (1 - trans_cost)
                position = 0
        
        if position > 0:
            capital = position * prices[-1] * (1 - trans_cost)
        
        total = (capital - 100000.0) / 100000.0
        years = len(prices) / 252
        annual = (capital / 100000.0) ** (1 / years) - 1 if years > 0 else 0
        
        return annual
    
    def run(self):
        """Run optimization"""
        logger.info("Phase 10 FINAL: Optimized Adaptive Strategy")
        
        symbols = [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META', 'NFLX',
            'ADBE', 'INTC', 'AMD', 'CSCO', 'QCOM', 'COST', 'AVGO', 'TMUS',
            'CMCSA', 'INTU', 'VRTX', 'AEP', 'LRCX', 'SNPS', 'CDNS', 'PCAR',
            'PAYX', 'ABNB', 'PANW', 'CRWD', 'ZM', 'DXCM', 'WDAY', 'FAST',
            'CPRT', 'CHKP'
        ]
        
        data = self.fetch_all_data(symbols)
        logger.info(f"Fetched {len(data)} stocks\n")
        
        results = []
        annuals = []
        
        logger.info("Running backtests...")
        for i, (symbol, prices) in enumerate(data.items(), 1):
            annual = self.backtest(prices)
            annuals.append(annual)
            results.append({'Symbol': symbol, 'Annual_Return': annual})
            logger.info(f"[{i:2d}/{len(data)}] {symbol:6s}: {annual:7.4f}")
        
        avg = np.mean(annuals)
        
        logger.info(f"\n{'='*80}")
        logger.info(f"PHASE 10 FINAL: OPTIMIZED ADAPTIVE STRATEGY")
        logger.info(f"{'='*80}")
        logger.info(f"Avg Annual Return:      {avg:7.4f} ({avg*100:6.2f}%)")
        logger.info(f"S&P 500 Benchmark:      {self.benchmark_annual:7.4f} ({self.benchmark_annual*100:6.2f}%)")
        logger.info(f"Outperformance:         {(avg - self.benchmark_annual):7.4f} ({(avg - self.benchmark_annual)*100:6.2f}%)")
        logger.info(f"Target (5%+):           {self.target:7.4f} ({self.target*100:6.2f}%)")
        logger.info(f"Beats Target:           {'YES!' if avg >= self.target else 'NO'}")
        logger.info(f"Stocks Beating S&P:     {sum(1 for a in annuals if a > self.benchmark_annual)}/{len(annuals)}")
        logger.info(f"Best Stock:             {max(zip(data.keys(), annuals), key=lambda x: x[1])[0]} ({max(annuals):.4f})")
        logger.info(f"Worst Stock:            {min(zip(data.keys(), annuals), key=lambda x: x[1])[0]} ({min(annuals):.4f})")
        logger.info(f"{'='*80}\n")
        
        # Save
        out = Path(__file__).parent.parent.parent / 'phase10_results'
        out.mkdir(exist_ok=True)
        
        pd.DataFrame(results).to_csv(out / 'phase10_final_results.csv', index=False)
        
        with open(out / 'PHASE10_FINAL_RESULTS.txt', 'w') as f:
            f.write("PHASE 10 FINAL: OPTIMIZED ADAPTIVE STRATEGY\n")
            f.write("="*80 + "\n\n")
            f.write("STRATEGY LOGIC:\n")
            f.write("  1. BULL REGIME (price > 200MA + trend > 15%):\n")
            f.write("     - Buy if: price > MA20 > MA50 > MA200, RSI(40-80), MACD > 0\n\n")
            f.write("  2. BEAR REGIME (trend < -15%):\n")
            f.write("     - Opportunistic buys at RSI < 35 with negative MACD\n")
            f.write("     - Sell bounces when RSI > 70\n\n")
            f.write("  3. SIDEWAYS (other conditions):\n")
            f.write("     - RSI mean reversion: Buy < 25, Sell > 75\n")
            f.write("     - MACD crossover confirmation\n\n")
            f.write("INDICATORS:\n")
            f.write("  - Moving Averages: 200, 50, 20 day\n")
            f.write("  - RSI: 14-period\n")
            f.write("  - MACD: EMA12 - EMA26\n")
            f.write("  - ATR: Volatility (unused in final)\n\n")
            f.write(f"RESULTS:\n")
            f.write(f"  Avg Annual Return:   {avg:.4f} ({avg*100:.2f}%)\n")
            f.write(f"  S&P 500 Benchmark:   {self.benchmark_annual:.4f}\n")
            f.write(f"  Outperformance:      {(avg - self.benchmark_annual):.4f}\n")
            f.write(f"  Target:              {self.target:.4f}\n")
            f.write(f"  Beats Target:        {'YES!' if avg >= self.target else 'NO'}\n\n")
            f.write("TOP 10 PERFORMERS:\n")
            top = sorted(enumerate(annuals), key=lambda x: x[1], reverse=True)[:10]
            syms = list(data.keys())
            for rank, (idx, ann) in enumerate(top, 1):
                f.write(f"  {rank:2d}. {syms[idx]:6s}: {ann:7.4f} ({ann*100:6.2f}%)\n")
        
        logger.info(f"Results saved to {out}")


if __name__ == '__main__':
    Phase10FinalOptimized().run()
