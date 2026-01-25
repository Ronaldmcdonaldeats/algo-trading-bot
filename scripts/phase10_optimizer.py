#!/usr/bin/env python3
"""
Phase 10: Automated Parameter Optimizer
Finds best parameters to beat S&P 500 by 5%+
Uses focused grid search on high-impact parameters
"""

import os
import sys
import logging
from typing import Dict, Tuple, List
import numpy as np
import pandas as pd
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from trading_bot.historical_data import HistoricalDataFetcher

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Phase10Optimizer:
    """Optimizes Phase 9 strategy to beat S&P 500 by 5%+"""
    
    def __init__(self):
        self.data_fetcher = HistoricalDataFetcher()
        self.results = []
        self.benchmark_annual = 0.011  # S&P 500 from Phase 9: 1.1%
        self.target = self.benchmark_annual + 0.05  # Need 5.1% minimum
        
    def fetch_all_data(self, symbols: List[str]) -> Dict[str, np.ndarray]:
        """Fetch data for all stocks"""
        logger.info(f"Fetching data for {len(symbols)} stocks...")
        data = {}
        
        for i, symbol in enumerate(symbols, 1):
            try:
                df = self.data_fetcher.fetch_stock_data(symbol)
                if df is not None and len(df) > 100:
                    data[symbol] = df['Close'].values
                    logger.info(f"[{i}/{len(symbols)}] {symbol}: {len(data[symbol])} days")
                else:
                    logger.warning(f"[{i}/{len(symbols)}] {symbol}: Insufficient data")
            except Exception as e:
                logger.error(f"[{i}/{len(symbols)}] {symbol}: {e}")
        
        logger.info(f"Successfully fetched {len(data)} stocks")
        return data
    
    def regime_detect(self, prices: np.ndarray, ma_window: int = 200) -> Tuple[float, float]:
        """Detect market regime"""
        if len(prices) < ma_window:
            return 0.0, 0.0
        
        ma = np.mean(prices[-ma_window:])
        current = prices[-1]
        trend = (current - ma) / ma
        volatility = np.std(np.diff(np.log(prices[-ma_window:])))
        
        return trend, volatility
    
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
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def backtest_config(self, prices: np.ndarray, config: Dict) -> float:
        """Test a configuration"""
        if len(prices) < 200:
            return 0.0
        
        capital = 100000.0
        position = 0.0
        trans_cost = 0.001  # 0.1%
        
        sma_fast = config['sma_fast']
        sma_slow = config['sma_slow']
        rsi_window = config['rsi_window']
        rsi_oversold = config['rsi_oversold']
        rsi_overbought = config['rsi_overbought']
        ma_window = config['ma_window']
        
        start_idx = max(sma_slow, ma_window)
        
        for i in range(start_idx, len(prices)):
            price = prices[i]
            
            # Get regime
            trend, vol = self.regime_detect(prices[:i], ma_window)
            
            # Get RSI
            rsi = self.calculate_rsi(prices[:i], rsi_window)
            
            # Get SMAs
            sma_f = np.mean(prices[i-sma_fast:i])
            sma_s = np.mean(prices[i-sma_slow:i])
            
            signal = 0
            
            if trend > 0.3:  # Bull regime
                # SMA crossover
                if sma_f > sma_s:
                    signal = 1
                elif sma_f < sma_s:
                    signal = -1
            elif trend < -0.3:  # Bear regime
                # RSI mean reversion
                if rsi < rsi_oversold:
                    signal = 1
                elif rsi > rsi_overbought:
                    signal = -1
            else:  # Sideways
                if rsi < 20:
                    signal = 1
                elif rsi > 80:
                    signal = -1
            
            # Execute trades
            if signal == 1 and position == 0:
                position = capital / price * (1 - trans_cost)
                capital = 0
            elif signal == -1 and position > 0:
                capital = position * price * (1 - trans_cost)
                position = 0
        
        if position > 0:
            capital = position * prices[-1] * (1 - trans_cost)
        
        total_return = (capital - 100000.0) / 100000.0
        years = len(prices) / 252
        annual = (capital / 100000.0) ** (1 / years) - 1 if years > 0 else 0
        
        return annual
    
    def grid_search(self, data: Dict[str, np.ndarray]) -> Dict:
        """Perform focused grid search"""
        if not data:
            logger.error("No data available for optimization")
            return {}
        
        # Focus on high-impact parameters based on Phase 9
        param_grid = {
            'sma_fast': [8, 12, 15, 20],      # Fast SMA
            'sma_slow': [30, 40, 50, 60],     # Slow SMA
            'rsi_window': [10, 14, 20],       # RSI period
            'rsi_oversold': [25, 30, 35],     # Oversold threshold
            'rsi_overbought': [65, 70, 75],   # Overbought threshold
            'ma_window': [150, 200, 250],     # MA for regime
        }
        
        best_config = None
        best_annual = 0.0
        total_combos = (
            len(param_grid['sma_fast']) * 
            len(param_grid['sma_slow']) *
            len(param_grid['rsi_window']) *
            len(param_grid['rsi_oversold']) *
            len(param_grid['rsi_overbought']) *
            len(param_grid['ma_window'])
        )
        
        logger.info(f"Testing {total_combos} parameter combinations...")
        tested = 0
        
        for sma_f in param_grid['sma_fast']:
            for sma_s in param_grid['sma_slow']:
                if sma_f >= sma_s:
                    continue
                    
                for rsi_w in param_grid['rsi_window']:
                    for rsi_os in param_grid['rsi_oversold']:
                        for rsi_ob in param_grid['rsi_overbought']:
                            if rsi_os >= rsi_ob:
                                continue
                                
                            for ma_w in param_grid['ma_window']:
                                config = {
                                    'sma_fast': sma_f,
                                    'sma_slow': sma_s,
                                    'rsi_window': rsi_w,
                                    'rsi_oversold': rsi_os,
                                    'rsi_overbought': rsi_ob,
                                    'ma_window': ma_w,
                                }
                                
                                # Test on 5 random stocks for speed
                                annuals = []
                                sample_symbols = list(data.keys())[:5]
                                
                                for symbol in sample_symbols:
                                    annual = self.backtest_config(data[symbol], config)
                                    annuals.append(annual)
                                
                                avg_annual = np.mean(annuals)
                                tested += 1
                                
                                if tested % 50 == 0:
                                    logger.info(f"Tested {tested}/{total_combos} combos | Best: {best_annual:.3f}")
                                
                                if avg_annual > best_annual:
                                    best_annual = avg_annual
                                    best_config = config.copy()
                                    logger.info(f"New best: {best_annual:.3f} with {config}")
                                    
                                    # If target reached, we can stop
                                    if best_annual >= self.target:
                                        logger.info(f"TARGET REACHED: {best_annual:.3f} >= {self.target:.3f}")
                                        return best_config
        
        logger.info(f"Grid search complete. Best config: {best_config} ({best_annual:.3f})")
        return best_config
    
    def backtest_full(self, data: Dict[str, np.ndarray], config: Dict) -> Tuple[float, pd.DataFrame]:
        """Full backtest on all stocks"""
        logger.info(f"Running full backtest with config: {config}")
        
        results_list = []
        annuals = []
        
        for i, (symbol, prices) in enumerate(data.items(), 1):
            annual = self.backtest_config(prices, config)
            annuals.append(annual)
            
            results_list.append({
                'Symbol': symbol,
                'Annual_Return': annual,
                'Beats_SP500': 'YES' if annual > self.benchmark_annual else 'NO',
                'vs_Target': annual - self.target,
            })
            
            logger.info(f"[{i}/{len(data)}] {symbol}: {annual:.3f}")
        
        results_df = pd.DataFrame(results_list)
        avg_annual = np.mean(annuals)
        
        logger.info(f"\n{'='*80}")
        logger.info(f"FULL BACKTEST RESULTS")
        logger.info(f"{'='*80}")
        logger.info(f"Avg Annual Return: {avg_annual:.3f}")
        logger.info(f"S&P 500 Benchmark: {self.benchmark_annual:.3f}")
        logger.info(f"Outperformance: {avg_annual - self.benchmark_annual:.3f}")
        logger.info(f"Target (5%+): {self.target:.3f}")
        logger.info(f"Beats Target: {'YES' if avg_annual >= self.target else 'NO'}")
        logger.info(f"Stocks Beating S&P: {(results_df['Beats_SP500'] == 'YES').sum()}/{len(results_df)}")
        logger.info(f"{'='*80}\n")
        
        return avg_annual, results_df
    
    def run(self):
        """Run full optimization"""
        logger.info("Starting Phase 10 Optimization...")
        
        # Stock list
        symbols = [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META', 'NFLX',
            'ADBE', 'INTC', 'AMD', 'CSCO', 'QCOM', 'COST', 'AVGO', 'TMUS',
            'CMCSA', 'INTU', 'VRTX', 'AEP', 'LRCX', 'SNPS', 'CDNS', 'PCAR',
            'PAYX', 'ABNB', 'PANW', 'CRWD', 'ZM', 'DXCM', 'WDAY', 'FAST',
            'CPRT', 'CHKP'
        ]
        
        # Fetch data
        data = self.fetch_all_data(symbols)
        
        if not data:
            logger.error("Failed to fetch any data")
            return
        
        # Grid search for best config
        best_config = self.grid_search(data)
        
        if not best_config:
            logger.error("Grid search failed")
            return
        
        # Full backtest
        avg_annual, results_df = self.backtest_full(data, best_config)
        
        # Save results
        output_dir = Path(__file__).parent.parent.parent / 'phase10_results'
        output_dir.mkdir(exist_ok=True)
        
        results_df.to_csv(output_dir / 'phase10_results.csv', index=False)
        
        with open(output_dir / 'phase10_config.txt', 'w') as f:
            f.write("PHASE 10: OPTIMIZED CONFIGURATION\n")
            f.write("="*80 + "\n\n")
            f.write("BEST PARAMETERS:\n")
            for k, v in best_config.items():
                f.write(f"  {k}: {v}\n")
            f.write(f"\nAVERAGE ANNUAL RETURN: {avg_annual:.3f}\n")
            f.write(f"S&P 500 BENCHMARK: {self.benchmark_annual:.3f}\n")
            f.write(f"OUTPERFORMANCE: {avg_annual - self.benchmark_annual:.3f}\n")
            f.write(f"TARGET (5%+): {self.target:.3f}\n")
            f.write(f"BEATS TARGET: {'YES' if avg_annual >= self.target else 'NO'}\n")
        
        logger.info(f"Results saved to {output_dir}")


if __name__ == '__main__':
    optimizer = Phase10Optimizer()
    optimizer.run()
