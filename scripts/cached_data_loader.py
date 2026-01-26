#!/usr/bin/env python3
"""
Cached data loader - saves downloaded data to disk for fast reuse
"""

import sys
import logging
from typing import Dict
import numpy as np
import pandas as pd
from pathlib import Path
import pickle

sys.path.insert(0, str(Path(__file__).parent.parent))

from trading_bot.historical_data import HistoricalDataFetcher

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger('DataLoader')


class CachedDataLoader:
    """Load stock data with disk caching"""
    
    def __init__(self, cache_dir: str = None):
        if cache_dir is None:
            cache_dir = str(Path(__file__).parent.parent.parent / 'data_cache')
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.fetcher = HistoricalDataFetcher()
    
    def load_stock_data(self, symbol: str) -> np.ndarray:
        """Load from cache or fetch"""
        cache_file = self.cache_dir / f"{symbol}.pkl"
        
        # Try cache first
        if cache_file.exists():
            try:
                with open(cache_file, 'rb') as f:
                    data = pickle.load(f)
                logger.info(f"Loaded {symbol} from cache ({len(data)} days)")
                return data
            except:
                pass
        
        # Fetch if not cached
        try:
            logger.info(f"Fetching {symbol} from network...")
            df = self.fetcher.fetch_stock_data(symbol)
            if df is not None and len(df) > 100:
                prices = df['Close'].values
                # Save to cache
                with open(cache_file, 'wb') as f:
                    pickle.dump(prices, f)
                logger.info(f"Cached {symbol} ({len(prices)} days)")
                return prices
        except:
            pass
        
        return None
    
    def load_all_stocks(self, symbols: list) -> Dict[str, np.ndarray]:
        """Load all stocks with caching"""
        data = {}
        for symbol in symbols:
            prices = self.load_stock_data(symbol)
            if prices is not None:
                data[symbol] = prices
        logger.info(f"Loaded {len(data)}/{len(symbols)} stocks from cache/network")
        return data
    
    def clear_cache(self):
        """Clear all cached data"""
        import shutil
        if self.cache_dir.exists():
            shutil.rmtree(self.cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        logger.info("Cache cleared")


if __name__ == '__main__':
    loader = CachedDataLoader()
    symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA']
    data = loader.load_all_stocks(symbols)
    print(f"Loaded {len(data)} stocks")
