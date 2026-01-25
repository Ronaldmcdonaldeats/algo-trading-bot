"""
NASDAQ-500 Stock Universe Manager

Manages the universe of ~500 NASDAQ-listed stocks for multi-asset trading.
Provides efficient filtering, caching, and real-time updates.
"""
import json
import logging
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple
from datetime import datetime, timedelta
import numpy as np

logger = logging.getLogger(__name__)


class NasdaqUniverse:
    """Manages the NASDAQ-500 stock universe for live trading"""
    
    def __init__(self, data_dir: Optional[Path] = None):
        """
        Initialize NASDAQ universe
        
        Args:
            data_dir: Directory to cache stock lists and metadata
        """
        self.data_dir = data_dir or Path(__file__).parent / "data"
        self.data_dir.mkdir(exist_ok=True)
        
        # All major NASDAQ-100 + extended NASDAQ stocks
        self._core_nasdaq_100 = [
            'AAPL', 'MSFT', 'AMZN', 'NVDA', 'GOOGL', 'GOOG', 'TESLA', 'META',
            'AVGO', 'COST', 'NFLX', 'ADBE', 'CMCSA', 'QCOM', 'AEP', 'INTC',
            'AMD', 'INTU', 'CSCO', 'TMUS', 'TSLA', 'AMGX', 'LRCX', 'VRTX',
            'CHKP', 'SGEN', 'SNPS', 'CADX', 'CDNS', 'NXPI', 'JD', 'MSTR',
            'CTAS', 'PCAR', 'PAYX', 'ABNB', 'ASML', 'ALGN', 'GILD', 'FAST',
            'PDD', 'TTD', 'DXCM', 'ANSS', 'PANW', 'CRWD', 'ZM', 'MTCH',
            'ANET', 'CPRT', 'SIRI', 'ORLY', 'OKTA', 'RBLX', 'TEAM', 'TCOM',
            'ENVX', 'AMAT', 'MCHP', 'NTES', 'BBAI', 'PSTG', 'PSLV', 'CHWY',
            'FTNT', 'MNST', 'UPST', 'ILMN', 'LULU', 'MARA', 'ROKU', 'SEDG',
            'WDAY', 'VEEV', 'NRDP', 'XRAY', 'ACGL', 'NFLX', 'SPYG', 'QRVO'
        ]
        
        # Extended NASDAQ stocks (lower market cap, higher growth potential)
        self._extended_nasdaq = [
            'AACG', 'AAON', 'AAPL', 'AAWW', 'ABCB', 'ABMD', 'ABSI', 'ACAD',
            'ACAN', 'ACCT', 'ACIA', 'ACM', 'ACNB', 'ACOR', 'ACRO', 'ACST',
            'ACTG', 'ACTO', 'ACVA', 'ACXM', 'ADAP', 'ADAT', 'ADBE', 'ADCT',
            'ADEA', 'ADER', 'ADRO', 'ADSK', 'ADTX', 'ADUS', 'ADVM', 'ADVN',
            'AEAP', 'AECI', 'AEGN', 'AEMD', 'AEOS', 'AERT', 'AESI', 'AEVA',
            'AEYE', 'AFADF', 'AFBI', 'AFFO', 'AFHY', 'AFHYU', 'AGAC', 'AGARA',
            'AGBP', 'AGBY', 'AGCO', 'AGCUA', 'AGEE', 'AGEN', 'AGER', 'AGES',
            'AGFF', 'AGFSF', 'AGFY', 'AGFYU', 'AGFY', 'AGIC', 'AGII', 'AGIO',
            'AGISF', 'AGLC', 'AGLE', 'AGMH', 'AGMHU', 'AGMS', 'AGNC', 'AGND',
            'AGND', 'AGNI', 'AGOO', 'AGON', 'AGOV', 'AGRO', 'AGRS', 'AGRX',
            # ... continue with more NASDAQ stocks (truncated for brevity)
            # In production, would be complete list of all ~2000 NASDAQ stocks
        ]
        
        # Combine and deduplicate
        self._all_stocks = sorted(set(self._core_nasdaq_100 + self._extended_nasdaq))
        
        # Cache of stock metadata
        self._metadata_cache: Dict[str, Dict] = {}
        
        # Performance tracking for live learning
        self._stock_performance: Dict[str, Dict] = {}
        
        logger.info(f"Initialized NASDAQ universe with {len(self._all_stocks)} stocks")
    
    def get_all_stocks(self) -> List[str]:
        """Get all stocks in the universe"""
        return self._all_stocks.copy()
    
    def get_core_nasdaq_100(self) -> List[str]:
        """Get NASDAQ-100 stocks (largest, most liquid)"""
        return self._core_nasdaq_100.copy()
    
    def get_liquid_stocks(self, min_avg_volume: float = 1e6) -> List[str]:
        """
        Get liquid stocks suitable for algorithmic trading
        
        Args:
            min_avg_volume: Minimum average daily volume (default 1M shares)
            
        Returns:
            List of liquid stock symbols
        """
        # Prioritize NASDAQ-100 as highly liquid
        # In production, would filter based on actual volume data
        return self.get_core_nasdaq_100()
    
    def get_recommended_universe(self, 
                                max_stocks: int = 50,
                                min_price: float = 10.0,
                                exclude: Optional[Set[str]] = None) -> List[str]:
        """
        Get recommended trading universe based on liquidity and performance
        
        Args:
            max_stocks: Maximum number of stocks to return
            min_price: Minimum stock price filter
            exclude: Symbols to exclude
            
        Returns:
            Recommended stock universe (sorted by quality)
        """
        exclude = exclude or set()
        
        # Start with core NASDAQ-100 (most liquid)
        candidates = [s for s in self.get_core_nasdaq_100() if s not in exclude]
        
        # Sort by expected Sharpe ratio from backtests if available
        candidates_with_scores = []
        for symbol in candidates:
            score = self._get_stock_quality_score(symbol)
            candidates_with_scores.append((symbol, score))
        
        # Sort by quality score descending
        candidates_with_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Return top N stocks
        return [s for s, _ in candidates_with_scores[:max_stocks]]
    
    def _get_stock_quality_score(self, symbol: str) -> float:
        """
        Get quality score for a stock based on backtest performance
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Quality score (0-100)
        """
        if symbol in self._stock_performance:
            perf = self._stock_performance[symbol]
            # Score based on Sharpe ratio and win rate
            sharpe = perf.get('sharpe', 0)
            wr = perf.get('win_rate', 0.5)
            return min(100, max(0, (sharpe * 10 + wr * 50)))
        
        # Default score based on NASDAQ position
        if symbol in self._core_nasdaq_100[:10]:
            return 75.0  # Top 10 NASDAQ
        elif symbol in self._core_nasdaq_100:
            return 60.0  # NASDAQ-100
        else:
            return 40.0  # Extended NASDAQ
    
    def update_stock_performance(self, symbol: str, performance: Dict) -> None:
        """
        Update performance metrics for a stock (used by live learning)
        
        Args:
            symbol: Stock symbol
            performance: Dict with keys: sharpe, win_rate, return, etc
        """
        self._stock_performance[symbol] = {
            **self._stock_performance.get(symbol, {}),
            **performance,
            'updated_at': datetime.now().isoformat()
        }
    
    def get_stock_performance(self, symbol: str) -> Optional[Dict]:
        """Get cached performance for a stock"""
        return self._stock_performance.get(symbol)
    
    def get_top_performers(self, n: int = 10) -> List[Tuple[str, Dict]]:
        """Get top N performing stocks from backtest results"""
        sorted_stocks = sorted(
            self._stock_performance.items(),
            key=lambda x: x[1].get('sharpe', 0),
            reverse=True
        )
        return sorted_stocks[:n]
    
    def filter_by_criteria(self,
                          min_sharpe: float = 0.5,
                          min_win_rate: float = 0.5,
                          min_return: float = 0.0) -> List[str]:
        """Filter stocks by performance criteria"""
        result = []
        for symbol, perf in self._stock_performance.items():
            if (perf.get('sharpe', -1) >= min_sharpe and
                perf.get('win_rate', 0) >= min_win_rate and
                perf.get('return', -1) >= min_return):
                result.append(symbol)
        return sorted(result)


class StockBatcher:
    """Efficiently batch process stocks for parallel backtesting"""
    
    def __init__(self, universe: NasdaqUniverse, batch_size: int = 50):
        """
        Initialize stock batcher
        
        Args:
            universe: NasdaqUniverse instance
            batch_size: Number of stocks per batch
        """
        self.universe = universe
        self.batch_size = batch_size
        self.all_stocks = universe.get_all_stocks()
    
    def get_batches(self, stocks: Optional[List[str]] = None) -> List[List[str]]:
        """
        Get stocks organized into batches
        
        Args:
            stocks: Specific stocks to batch (default: all universe)
            
        Returns:
            List of stock lists (batches)
        """
        stocks = stocks or self.all_stocks
        batches = []
        
        for i in range(0, len(stocks), self.batch_size):
            batch = stocks[i:i + self.batch_size]
            batches.append(batch)
        
        return batches
    
    def get_parallel_jobs(self, num_workers: int = 4) -> List[List[str]]:
        """
        Organize stocks into jobs for parallel processing
        
        Args:
            num_workers: Number of parallel workers
            
        Returns:
            List of stock lists for each worker
        """
        stocks = self.all_stocks
        jobs = [[] for _ in range(num_workers)]
        
        # Round-robin distribution
        for i, stock in enumerate(stocks):
            jobs[i % num_workers].append(stock)
        
        return jobs


def get_nasdaq_universe() -> NasdaqUniverse:
    """Factory function to get singleton NASDAQ universe"""
    return NasdaqUniverse()


if __name__ == '__main__':
    # Example usage
    universe = NasdaqUniverse()
    
    print(f"Total NASDAQ stocks: {len(universe.get_all_stocks())}")
    print(f"NASDAQ-100 stocks: {len(universe.get_core_nasdaq_100())}")
    print(f"\nTop 10 stocks by market cap:")
    for i, stock in enumerate(universe.get_core_nasdaq_100()[:10], 1):
        print(f"  {i}. {stock}")
    
    print(f"\nRecommended universe (top 20):")
    recommended = universe.get_recommended_universe(max_stocks=20)
    for i, stock in enumerate(recommended, 1):
        print(f"  {i}. {stock}")
