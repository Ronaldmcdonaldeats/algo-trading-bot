#!/usr/bin/env python3
"""
Phase 10: Advanced Ensemble with Momentum + Volatility + Regime Detection
Combines best of Phase 9 with momentum-based signals for 5%+ returns
"""

import os
import sys
import logging
from typing import Dict, Tuple, List
import numpy as np
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from trading_bot.historical_data import HistoricalDataFetcher

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Phase10AdvancedStrategy:
    """Advanced ensemble combining regime detection + momentum + volatility"""
    
    def __init__(self):
        self.data_fetcher = HistoricalDataFetcher()
        self.benchmark_annual = 0.011  # S&P 500
        self.target = self.benchmark_annual + 0.05  # 5.1%+
    
    def fetch_all_data(self, symbols: List[str]) -> Dict[str, np.ndarray]:
        """Fetch data for all stocks"""
        logger.info(f"Fetching data for {len(symbols)} stocks...")
        data = {}
        
        for i, symbol in enumerate(symbols, 1):
            try:
                df = self.data_fetcher.fetch_stock_data(symbol)
                if df is not None and len(df) > 100:
                    data[symbol] = df['Close'].values
                    if i % 5 == 0:
                        logger.info(f"[{i}/{len(symbols)}] {symbol}: {len(data[symbol])} days")
            except Exception as e:
                pass
        
        logger.info(f"Successfully fetched {len(data)} stocks")
        return data
    
    def calculate_rsi(self, prices: np.ndarray, window: int = 14) -> float:
        """Calculate RSI"""
        if len(prices) < window + 1:
            return 50.0
        
        deltas = np.diff(prices[-window-1:])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)
        
        if avg_loss == 0:
            return 100.0 if avg_gain > 0 else 50.0
        
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    def calculate_momentum(self, prices: np.ndarray, period: int = 20) -> float:
        """Calculate momentum as price change %"""
        if len(prices) < period + 1:
            return 0.0
        
        return (prices[-1] - prices[-period-1]) / prices[-period-1]
    
    def calculate_volatility(self, prices: np.ndarray, window: int = 20) -> float:
        """Calculate volatility (annualized)"""
        if len(prices) < window:
            return 0.0
        
        returns = np.diff(np.log(prices[-window:]))
        return np.std(returns) * np.sqrt(252)
    
    def generate_signal(self, prices: np.ndarray) -> int:
        """
        Generate trading signal using ensemble of indicators:
        1. Regime (trend strength)
        2. RSI (mean reversion)
        3. Momentum (trend following)
        4. Volatility adjustment
        """
        if len(prices) < 200:
            return 0
        
        # Regime detection (200-day MA)
        ma200 = np.mean(prices[-200:])
        current = prices[-1]
        trend_strength = (current - ma200) / ma200
        
        # Signals
        signals = []
        
        # Signal 1: Trend following (if strong bull, buy; if strong bear, sell)
        if trend_strength > 0.1:
            signals.append(1)  # Buy signal
        elif trend_strength < -0.1:
            signals.append(-1)  # Sell signal
        else:
            signals.append(0)
        
        # Signal 2: RSI mean reversion
        rsi = self.calculate_rsi(prices, 14)
        if rsi < 30:
            signals.append(1)  # Oversold, buy
        elif rsi > 70:
            signals.append(-1)  # Overbought, sell
        else:
            signals.append(0)
        
        # Signal 3: Momentum (20-day price change)
        momentum = self.calculate_momentum(prices, 20)
        if momentum > 0.05:
            signals.append(1)  # Strong uptrend
        elif momentum < -0.05:
            signals.append(-1)  # Strong downtrend
        else:
            signals.append(0)
        
        # Signal 4: Volatility-adjusted (higher vol = more cautious)
        volatility = self.calculate_volatility(prices, 20)
        if volatility > 0.3:
            # High volatility: trust regime more, less momentum
            signals[2] = int(signals[2] * 0.5)
        
        # Ensemble vote (majority wins)
        combined = sum(signals)
        if combined >= 1:
            return 1
        elif combined <= -1:
            return -1
        else:
            return 0
    
    def backtest(self, prices: np.ndarray) -> float:
        """Backtest the strategy"""
        if len(prices) < 200:
            return 0.0
        
        capital = 100000.0
        position = 0.0
        trans_cost = 0.001
        start_idx = 200
        
        for i in range(start_idx, len(prices)):
            price = prices[i]
            signal = self.generate_signal(prices[:i+1])
            
            # Execute trades
            if signal == 1 and position == 0:
                # Buy: invest all capital
                position = capital / price * (1 - trans_cost)
                capital = 0
            elif signal == -1 and position > 0:
                # Sell: close position
                capital = position * price * (1 - trans_cost)
                position = 0
        
        # Close any remaining position
        if position > 0:
            capital = position * prices[-1] * (1 - trans_cost)
        
        total_return = (capital - 100000.0) / 100000.0
        years = len(prices) / 252
        annual = (capital / 100000.0) ** (1 / years) - 1 if years > 0 else 0
        
        return annual
    
    def run(self):
        """Run full backtest"""
        logger.info("Starting Phase 10: Advanced Ensemble Strategy...")
        
        symbols = [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META', 'NFLX',
            'ADBE', 'INTC', 'AMD', 'CSCO', 'QCOM', 'COST', 'AVGO', 'TMUS',
            'CMCSA', 'INTU', 'VRTX', 'AEP', 'LRCX', 'SNPS', 'CDNS', 'PCAR',
            'PAYX', 'ABNB', 'PANW', 'CRWD', 'ZM', 'DXCM', 'WDAY', 'FAST',
            'CPRT', 'CHKP'
        ]
        
        data = self.fetch_all_data(symbols)
        
        if not data:
            logger.error("Failed to fetch data")
            return
        
        # Backtest all stocks
        logger.info("Running backtests...")
        results = []
        annuals = []
        
        for i, (symbol, prices) in enumerate(data.items(), 1):
            annual = self.backtest(prices)
            annuals.append(annual)
            
            results.append({
                'Symbol': symbol,
                'Annual_Return': annual,
                'Beats_SP500': 'YES' if annual > self.benchmark_annual else 'NO',
                'vs_Target': annual - self.target,
            })
            
            logger.info(f"[{i}/{len(data)}] {symbol}: {annual:.4f}")
        
        avg_annual = np.mean(annuals)
        
        logger.info(f"\n{'='*80}")
        logger.info(f"PHASE 10: ADVANCED ENSEMBLE RESULTS")
        logger.info(f"{'='*80}")
        logger.info(f"Avg Annual Return: {avg_annual:.4f} ({avg_annual*100:.2f}%)")
        logger.info(f"S&P 500 Benchmark: {self.benchmark_annual:.4f} ({self.benchmark_annual*100:.2f}%)")
        logger.info(f"Outperformance: {(avg_annual - self.benchmark_annual):.4f} ({(avg_annual - self.benchmark_annual)*100:.2f}%)")
        logger.info(f"Target (5%+): {self.target:.4f} ({self.target*100:.2f}%)")
        logger.info(f"Beats Target: {'YES ✓' if avg_annual >= self.target else 'NO'}")
        logger.info(f"Stocks Beating S&P: {sum(1 for a in annuals if a > self.benchmark_annual)}/{len(annuals)}")
        logger.info(f"{'='*80}\n")
        
        # Save results
        output_dir = Path(__file__).parent.parent.parent / 'phase10_results'
        output_dir.mkdir(exist_ok=True)
        
        results_df = pd.DataFrame(results)
        results_df.to_csv(output_dir / 'phase10_advanced_results.csv', index=False)
        
        with open(output_dir / 'phase10_advanced_results.txt', 'w') as f:
            f.write("PHASE 10: ADVANCED ENSEMBLE WITH MOMENTUM + VOLATILITY\n")
            f.write("="*80 + "\n\n")
            f.write("STRATEGY:\n")
            f.write("  - Combines regime detection (200-day MA)\n")
            f.write("  - RSI mean reversion (oversold < 30, overbought > 70)\n")
            f.write("  - Momentum indicator (20-day price change)\n")
            f.write("  - Volatility adjustment (reduces signals in high vol)\n")
            f.write("  - Ensemble voting (majority of indicators)\n\n")
            f.write(f"RESULTS:\n")
            f.write(f"  Avg Annual Return: {avg_annual:.4f} ({avg_annual*100:.2f}%)\n")
            f.write(f"  S&P 500 Benchmark: {self.benchmark_annual:.4f} ({self.benchmark_annual*100:.2f}%)\n")
            f.write(f"  Outperformance: {(avg_annual - self.benchmark_annual):.4f}\n")
            f.write(f"  Target (5%+): {self.target:.4f}\n")
            f.write(f"  Beats Target: {'YES ✓' if avg_annual >= self.target else 'NO'}\n")
            f.write(f"  Stocks Beating S&P: {sum(1 for a in annuals if a > self.benchmark_annual)}/{len(annuals)}\n\n")
            f.write("TOP 10 PERFORMERS:\n")
            
            top10 = sorted(enumerate(annuals), key=lambda x: x[1], reverse=True)[:10]
            symbols_list = list(data.keys())
            
            for rank, (idx, annual) in enumerate(top10, 1):
                f.write(f"  {rank:2d}. {symbols_list[idx]:6s} {annual:7.4f} ({annual*100:6.2f}%)\n")
        
        logger.info(f"Results saved to {output_dir}")


if __name__ == '__main__':
    strategy = Phase10AdvancedStrategy()
    strategy.run()
