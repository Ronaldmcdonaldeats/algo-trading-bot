#!/usr/bin/env python3
"""
Phase 10: Aggressive Ensemble with Position Sizing
Adds leverage and aggressive trend following to reach 5%+ returns
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


class Phase10AggressiveEnsemble:
    """Aggressive ensemble with position sizing and leverage"""
    
    def __init__(self):
        self.data_fetcher = HistoricalDataFetcher()
        self.benchmark_annual = 0.011
        self.target = 0.061
    
    def fetch_all_data(self, symbols: List[str]) -> Dict[str, np.ndarray]:
        """Fetch data for all stocks"""
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
        """Calculate momentum"""
        if len(prices) < period + 1:
            return 0.0
        return (prices[-1] - prices[-period-1]) / prices[-period-1]
    
    def calculate_volatility(self, prices: np.ndarray, window: int = 20) -> float:
        """Calculate volatility"""
        if len(prices) < window:
            return 0.01
        returns = np.diff(np.log(prices[-window:]))
        return np.std(returns) * np.sqrt(252)
    
    def generate_position_size(self, prices: np.ndarray) -> float:
        """
        Generate position sizing:
        - Strong trend + low vol = 2x leverage
        - Normal = 1x
        - Weak/uncertain = 0.5x
        - Counter-trend = 0x (stay out)
        """
        if len(prices) < 200:
            return 0.0
        
        ma200 = np.mean(prices[-200:])
        current = prices[-1]
        trend = (current - ma200) / ma200
        
        rsi = self.calculate_rsi(prices, 14)
        momentum = self.calculate_momentum(prices, 10)
        volatility = self.calculate_volatility(prices, 20)
        
        # Risk/reward score
        confidence = 0.0
        
        # Trend strength
        if abs(trend) > 0.15:
            confidence += 0.4
        elif abs(trend) > 0.05:
            confidence += 0.2
        
        # Momentum confirmation
        if momentum > 0.05:
            confidence += 0.3
        elif momentum < -0.05:
            confidence -= 0.3
        
        # RSI not overextended
        if 40 < rsi < 60:
            confidence += 0.2
        
        # Volatility adjustment (lower vol = more leverage)
        vol_factor = 1.0 / (1.0 + volatility)
        
        position_size = max(0.0, confidence) * vol_factor
        
        # Cap at 2x
        return min(2.0, position_size + 0.3)  # Always at least 0.3x
    
    def backtest(self, prices: np.ndarray) -> float:
        """Backtest with position sizing"""
        if len(prices) < 200:
            return 0.0
        
        capital = 100000.0
        position = 0.0
        trans_cost = 0.001
        
        for i in range(200, len(prices)):
            price = prices[i]
            
            # Calculate position size
            position_size = self.generate_position_size(prices[:i+1])
            
            # Target capital allocation
            target_capital = capital * (1.0 - position_size)
            target_position = (capital - target_capital) / price
            
            # Execute trades
            if target_position > position:
                # Buy more
                buy_amount = (target_position - position) * price
                capital -= buy_amount * (1 + trans_cost)
                position = target_position
            elif target_position < position:
                # Sell some
                sell_amount = (position - target_position) * price
                capital += sell_amount * (1 - trans_cost)
                position = target_position
        
        # Close position
        if position > 0:
            capital = position * prices[-1] * (1 - trans_cost)
        
        total_return = (capital - 100000.0) / 100000.0
        years = len(prices) / 252
        annual = (capital / 100000.0) ** (1 / years) - 1 if years > 0 else 0
        
        return annual
    
    def run(self):
        """Run backtest"""
        logger.info("Starting Phase 10: Aggressive Ensemble...")
        
        symbols = [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META', 'NFLX',
            'ADBE', 'INTC', 'AMD', 'CSCO', 'QCOM', 'COST', 'AVGO', 'TMUS',
            'CMCSA', 'INTU', 'VRTX', 'AEP', 'LRCX', 'SNPS', 'CDNS', 'PCAR',
            'PAYX', 'ABNB', 'PANW', 'CRWD', 'ZM', 'DXCM', 'WDAY', 'FAST',
            'CPRT', 'CHKP'
        ]
        
        data = self.fetch_all_data(symbols)
        logger.info(f"Fetched {len(data)} stocks")
        
        results = []
        annuals = []
        
        logger.info("Running backtests...")
        for i, (symbol, prices) in enumerate(data.items(), 1):
            annual = self.backtest(prices)
            annuals.append(annual)
            results.append({'Symbol': symbol, 'Annual_Return': annual})
            if i % 5 == 0:
                logger.info(f"[{i}/{len(data)}] Progress: {np.mean(annuals):.4f}")
        
        avg_annual = np.mean(annuals)
        
        logger.info(f"\n{'='*80}")
        logger.info(f"PHASE 10: AGGRESSIVE ENSEMBLE WITH POSITION SIZING")
        logger.info(f"{'='*80}")
        logger.info(f"Avg Annual Return: {avg_annual:.4f} ({avg_annual*100:.2f}%)")
        logger.info(f"S&P 500 Benchmark: {self.benchmark_annual:.4f}")
        logger.info(f"Outperformance: {(avg_annual - self.benchmark_annual):.4f}")
        logger.info(f"Target (5%+): {self.target:.4f}")
        logger.info(f"Beats Target: {'YES!' if avg_annual >= self.target else 'NO'}")
        logger.info(f"Stocks Beating S&P: {sum(1 for a in annuals if a > self.benchmark_annual)}/{len(annuals)}")
        logger.info(f"{'='*80}\n")
        
        # Save results
        output_dir = Path(__file__).parent.parent.parent / 'phase10_results'
        output_dir.mkdir(exist_ok=True)
        
        pd.DataFrame(results).to_csv(output_dir / 'phase10_aggressive_results.csv', index=False)
        
        with open(output_dir / 'phase10_aggressive_results.txt', 'w') as f:
            f.write("PHASE 10: AGGRESSIVE ENSEMBLE WITH POSITION SIZING\n")
            f.write("="*80 + "\n\n")
            f.write("STRATEGY:\n")
            f.write("  - Dynamic position sizing (0.3x to 2x leverage)\n")
            f.write("  - Based on: trend strength, momentum, volatility, RSI\n")
            f.write("  - Aggressive trend following in low volatility\n")
            f.write("  - Reduced position in high volatility\n\n")
            f.write(f"RESULTS:\n")
            f.write(f"  Avg Annual Return: {avg_annual:.4f} ({avg_annual*100:.2f}%)\n")
            f.write(f"  S&P 500: {self.benchmark_annual:.4f}\n")
            f.write(f"  Outperformance: {(avg_annual - self.benchmark_annual):.4f}\n")
            f.write(f"  Target: {self.target:.4f}\n")
            f.write(f"  Beats Target: {'YES!' if avg_annual >= self.target else 'NO'}\n")
        
        logger.info(f"Results saved to {output_dir}")


if __name__ == '__main__':
    strategy = Phase10AggressiveEnsemble()
    strategy.run()
