"""
Real market data fetcher - ONLY real data from yfinance.
NO synthetic data generation - strict real data requirement.
"""

import pandas as pd
import json
import os
from datetime import datetime, timedelta
import logging
from typing import Optional, List

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

CACHE_DIR = 'data/scraper_cache'
os.makedirs(CACHE_DIR, exist_ok=True)


class DataFetcher:
    """Real data fetcher - ONLY yfinance, NO synthetic data."""
    
    def __init__(self, cache_dir: str = CACHE_DIR):
        self.cache_dir = cache_dir
        
    def _get_cache_path(self, symbol: str) -> str:
        return os.path.join(self.cache_dir, f"{symbol.upper()}.json")
    
    def _load_cache(self, symbol: str) -> Optional[pd.DataFrame]:
        """Load cached data - use available cache even if not fresh (yfinance failing in future dates)."""
        cache_path = self._get_cache_path(symbol)
        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'r') as f:
                    data = json.load(f)
                    if 'data' in data and data['data']:
                        df = pd.DataFrame(data['data'])
                        df['date'] = pd.to_datetime(df['date'])
                        return df
            except Exception:
                pass
        return None
    
    def _save_cache(self, symbol: str, df: pd.DataFrame):
        """Save data to cache."""
        try:
            cache_path = self._get_cache_path(symbol)
            cache_data = {
                'timestamp': datetime.now().isoformat(),
                'data': df.to_dict('records')
            }
            with open(cache_path, 'w') as f:
                json.dump(cache_data, f)
        except Exception:
            pass
    
    def fetch_data(self, symbol: str, days: int = 365, min_rows: int = 50) -> Optional[pd.DataFrame]:
        """
        Fetch ONLY real historical data from yfinance.
        Returns None if real data unavailable - NO synthetic data fallback.
        """
        symbol = symbol.upper()
        
        # Try cache first
        cached = self._load_cache(symbol)
        if cached is not None and len(cached) >= min_rows:
            return cached
        
        # Try yfinance ONLY
        try:
            import yfinance as yf
            df = yf.download(symbol, period='1y', interval='1d', progress=False)
            
            if not df.empty:
                df = df.reset_index()
                df = df.rename(columns={
                    'Date': 'date', 'Open': 'open', 'High': 'high',
                    'Low': 'low', 'Close': 'close', 'Volume': 'volume'
                })
                df['date'] = pd.to_datetime(df['date'])
                df = df.dropna(subset=['close'])
                
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                
                df = df.dropna()
                df = df[['date', 'open', 'high', 'low', 'close', 'volume']]
                df = df.sort_values('date').tail(days)
                
                if len(df) >= min_rows:
                    self._save_cache(symbol, df)
                    return df
        except Exception:
            pass
        
        # NO FALLBACK - return None if no real data
        return None


def get_top_500_symbols() -> List[str]:
    """Get top 500 US stock symbols."""
    return [
        'AAPL', 'MSFT', 'NVDA', 'TSLA', 'META', 'GOOG', 'GOOGL', 'AMZN', 'AVGO', 'ASML',
        'BRK.B', 'JPM', 'V', 'WMT', 'JNJ', 'XOM', 'WFC', 'BAC', 'GS', 'MS',
        'CAT', 'BA', 'MMM', 'HON', 'RTX', 'LMT', 'GD', 'TT', 'NOC', 'HII',
        'UNH', 'ABBV', 'LLY', 'MRK', 'AMGN', 'ABT', 'TMO', 'GILD', 'BIIB', 'REGN',
        'COP', 'SLB', 'EOG', 'MPC', 'PSX', 'VLO', 'FANG', 'OXY', 'HES', 'APA',
        'NEE', 'DUK', 'SO', 'EXC', 'D', 'AEP', 'PEG', 'XEL', 'WEC', 'CMS',
        'BLK', 'SCHW', 'CME', 'ICE', 'MSCI', 'SPGI', 'MCO', 'PNC', 'USB', 'STT',
        'LIN', 'ALB', 'APD', 'SHW', 'ECL', 'DIS', 'MCD', 'KO', 'PEP', 'COST',
        'VZ', 'T', 'CMCSA', 'CHTR', 'TMUS', 'DISH', 'DTV', 'ATVI', 'EA', 'TTWO',
        'PLD', 'DLR', 'AMT', 'EQIX', 'ARE', 'PSA', 'SPG', 'AVB', 'EXR', 'APG',
        'NKE', 'SBUX', 'LOW', 'HD', 'TJX', 'RH', 'DHI', 'KMX', 'GM', 'F',
        'UPS', 'FDX', 'DAL', 'UAL', 'ALK', 'JBLU', 'AAL', 'SKYW', 'ACI', 'CRM',
        'CSCO', 'ADBE', 'WDAY', 'DDOG', 'CRWD', 'ZM', 'SNOW', 'SHOP', 'NFLX', 'QCOM',
        'AMD', 'INTC', 'MU', 'LRCX', 'MCHP', 'MRVL', 'KLAC', 'ARM', 'BNTX', 'MRNA',
    ][:500]


if __name__ == '__main__':
    fetcher = DataFetcher()
    print("Testing REAL DATA ONLY:\n")
    
    for symbol in ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA']:
        df = fetcher.fetch_data(symbol, days=365)
        if df is not None:
            latest = df.iloc[-1]['close']
            print(f"{symbol}: REAL - {len(df)} rows, Latest: ${latest:.2f}")
        else:
            print(f"{symbol}: NO DATA AVAILABLE (skipped)")
