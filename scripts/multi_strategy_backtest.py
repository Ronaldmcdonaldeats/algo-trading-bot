#!/usr/bin/env python3
"""
Multi-Strategy Backtester
Load and run any strategy without code changes - purely config-driven
"""

import sys
import logging
from typing import Dict
import yaml
import numpy as np
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.cached_data_loader import CachedDataLoader
from scripts.strategies import StrategyFactory

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MultiStrategyBacktester:
    """Run any strategy without code changes"""
    
    def __init__(self, config_file: str = 'strategy_config.yaml'):
        self.config_file = config_file
        self.config = self._load_config()
        self.loader = CachedDataLoader()
        self.benchmark_annual = 0.011
    
    def _load_config(self) -> Dict:
        """Load strategy configuration from YAML"""
        config_path = Path(self.config_file)
        
        if not config_path.exists():
            logger.warning(f"Config file {config_path} not found, using defaults")
            return self._get_default_config()
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        logger.info(f"Loaded config from {config_path}")
        return config
    
    def _get_default_config(self) -> Dict:
        """Return default configuration"""
        return {
            'strategy': 'ultra_ensemble',
            'symbols': [
                'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META', 'NFLX',
                'ADBE', 'INTC', 'AMD', 'CSCO', 'QCOM', 'COST', 'AVGO', 'TMUS',
                'CMCSA', 'INTU', 'VRTX', 'AEP', 'LRCX', 'SNPS', 'CDNS', 'PCAR',
                'PAYX', 'ABNB', 'PANW', 'CRWD', 'ZM', 'DXCM', 'WDAY', 'FAST',
                'CPRT', 'CHKP'
            ],
            'strategy_config': {
                'entry_threshold': 0.12,
                'exit_threshold': -0.12,
                'max_position_size': 1.5,
                'transaction_cost': 0.001
            }
        }
    
    def run(self):
        """Run backtest with configured strategy"""
        strategy_name = self.config.get('strategy', 'ultra_ensemble')
        symbols = self.config.get('symbols', [])
        strategy_config = self.config.get('strategy_config', {})
        
        logger.info(f"\n{'='*70}")
        logger.info(f"MULTI-STRATEGY BACKTESTER")
        logger.info(f"{'='*70}")
        logger.info(f"Strategy: {strategy_name}")
        logger.info(f"Symbols: {len(symbols)} stocks")
        logger.info(f"Loading strategies...\n")
        
        # Create strategy
        strategy = StrategyFactory.create(strategy_name, strategy_config)
        if strategy is None:
            logger.error(f"Unknown strategy: {strategy_name}")
            logger.info(f"Available strategies: {', '.join(StrategyFactory.list_strategies())}")
            return
        
        logger.info(f"Strategy: {strategy}\n")
        
        # Load data
        logger.info(f"Loading data for {len(symbols)} stocks...")
        data = self.loader.load_all_stocks(symbols)
        logger.info(f"Loaded {len(data)} stocks\n")
        
        # Run backtests
        results = []
        annuals = []
        
        logger.info(f"Running backtests...")
        for i, (symbol, prices) in enumerate(data.items(), 1):
            annual = strategy.backtest(prices)
            annuals.append(annual)
            results.append({'Symbol': symbol, 'Annual_Return': annual})
            if i % 5 == 0:
                logger.info(f"  Processed {i}/{len(data)}...")
        
        # Print results
        avg = np.mean(annuals)
        outperform = avg - self.benchmark_annual
        beats_sp = sum(1 for a in annuals if a > self.benchmark_annual)
        
        logger.info(f"\n{'='*70}")
        logger.info(f"RESULTS: {strategy_name.upper()}")
        logger.info(f"{'='*70}")
        logger.info(f"Average Annual Return:    {avg:7.4f} ({avg*100:6.2f}%)")
        logger.info(f"S&P 500 Benchmark:        {self.benchmark_annual:7.4f} ({self.benchmark_annual*100:6.2f}%)")
        logger.info(f"Outperformance:           {outperform:7.4f} ({outperform*100:6.2f}%)")
        logger.info(f"Stocks Beating S&P:       {beats_sp}/{len(data)} ({beats_sp/len(data)*100:.1f}%)")
        logger.info(f"Min Return:               {min(annuals):7.4f} ({min(annuals)*100:6.2f}%)")
        logger.info(f"Max Return:               {max(annuals):7.4f} ({max(annuals)*100:6.2f}%)")
        logger.info(f"Std Dev:                  {np.std(annuals):7.4f}")
        logger.info(f"{'='*70}\n")
        
        # Save results
        out = Path(self.config_file).parent / f'results_{strategy_name}'
        out.mkdir(exist_ok=True)
        
        df = pd.DataFrame(results).sort_values('Annual_Return', ascending=False)
        df.to_csv(out / 'results.csv', index=False)
        logger.info(f"Results saved to {out}\n")
        
        # Print top and bottom performers
        logger.info("Top 5 Performers:")
        for idx, row in df.head(5).iterrows():
            logger.info(f"  {row['Symbol']:6s}: {row['Annual_Return']:7.4f} ({row['Annual_Return']*100:6.2f}%)")
        
        logger.info("\nBottom 5 Performers:")
        for idx, row in df.tail(5).iterrows():
            logger.info(f"  {row['Symbol']:6s}: {row['Annual_Return']:7.4f} ({row['Annual_Return']*100:6.2f}%)")
        
        return {
            'strategy': strategy_name,
            'average_return': avg,
            'outperformance': outperform,
            'beats_sp': beats_sp,
            'results': df
        }


if __name__ == '__main__':
    backtester = MultiStrategyBacktester()
    backtester.run()
