"""
Historical Data Fetcher - 2000-2025

Fetches real historical price data from multiple sources for backtesting
across 25+ years of market history with all major events (2000 crash,
2008 financial crisis, 2020 COVID, etc.)

Sources tried in order:
1. Yahoo Finance (yfinance)
2. Alpha Vantage API
3. Synthetic data fallback
"""
import sys
import requests
from pathlib import Path
from typing import Dict, Optional, Tuple, List
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import logging
import time

logger = logging.getLogger(__name__)


class HistoricalDataFetcher:
    """Fetches real historical data from multiple sources"""
    
    # Alpha Vantage API key (free tier available)
    ALPHA_VANTAGE_KEY = "demo"  # Use demo key, can be overridden
    ALPHA_VANTAGE_URL = "https://www.alphavantage.co/query"
    
    def __init__(self, cache_dir: Optional[Path] = None, alpha_vantage_key: str = None):
        """
        Initialize fetcher
        
        Args:
            cache_dir: Directory to cache downloaded data
            alpha_vantage_key: Alpha Vantage API key (optional)
        """
        self.cache_dir = cache_dir or Path(__file__).parent.parent / "data" / "historical"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        if alpha_vantage_key:
            self.ALPHA_VANTAGE_KEY = alpha_vantage_key
    
    def _fetch_from_alpha_vantage(self, symbol: str, start_date: str, 
                                  end_date: str) -> Optional[pd.DataFrame]:
        """
        Fetch from Alpha Vantage API (free monthly data)
        
        Returns OHLCV data if successful, None otherwise
        """
        try:
            logger.info(f"Trying Alpha Vantage for {symbol}...")
            
            params = {
                'function': 'TIME_SERIES_MONTHLY_ADJUSTED',
                'symbol': symbol,
                'outputsize': 'full',
                'apikey': self.ALPHA_VANTAGE_KEY
            }
            
            response = requests.get(self.ALPHA_VANTAGE_URL, params=params, timeout=10)
            data = response.json()
            
            if 'Error Message' in data or 'Note' in data or 'Time Series (Monthly Adjusted)' not in data:
                logger.debug(f"Alpha Vantage failed for {symbol}: {data.get('Error Message', 'No data')}")
                return None
            
            time_series = data['Time Series (Monthly Adjusted)']
            
            # Convert to DataFrame
            rows = []
            for date_str, values in time_series.items():
                rows.append({
                    'Date': pd.Timestamp(date_str),
                    'Open': float(values.get('1. open', 0)),
                    'High': float(values.get('2. high', 0)),
                    'Low': float(values.get('3. low', 0)),
                    'Close': float(values.get('4. close', 0)),
                    'Volume': int(float(values.get('6. volume', 0)))
                })
            
            if not rows:
                return None
            
            df = pd.DataFrame(rows)
            df.set_index('Date', inplace=True)
            df.sort_index(inplace=True)
            
            # Filter by date range
            start = pd.Timestamp(start_date)
            end = pd.Timestamp(end_date)
            df = df[(df.index >= start) & (df.index <= end)]
            
            logger.info(f"Alpha Vantage found {len(df)} rows for {symbol}")
            
            # Rate limiting for free tier
            time.sleep(0.3)
            
            return df if len(df) > 0 else None
            
        except Exception as e:
            logger.debug(f"Alpha Vantage error for {symbol}: {e}")
            return None
    
    def fetch_stock_data(self, symbol: str, start_date: str = "2000-01-01", 
                        end_date: str = "2025-01-25") -> Optional[pd.DataFrame]:
        """
        Fetch historical stock data from multiple sources
        
        Tries in order:
        1. Cache
        2. Yahoo Finance
        3. Alpha Vantage API
        4. Synthetic data fallback (always available)
        
        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            DataFrame with OHLCV data (never None - uses synthetic if needed)
        """
        cache_file = self.cache_dir / f"{symbol}_{start_date}_{end_date}.csv"
        
        # Try to load from cache first
        if cache_file.exists():
            try:
                df = pd.read_csv(cache_file, index_col='Date', parse_dates=True)
                logger.info(f"Loaded {symbol} from cache ({len(df)} rows)")
                return df
            except Exception as e:
                logger.warning(f"Failed to load cache for {symbol}: {e}")
        
        # Try Yahoo Finance
        data = None
        try:
            import yfinance as yf
            
            logger.info(f"Fetching {symbol} from Yahoo Finance...")
            data = yf.download(symbol, start=start_date, end=end_date, progress=False)
            
            # Check if we got valid data
            if data is not None and not data.empty and len(data) > 50:
                # Rename columns to lowercase
                data.columns = [col.lower() for col in data.columns]
                
                # Save to cache
                try:
                    data.to_csv(cache_file)
                    logger.info(f"Cached {symbol} from Yahoo Finance ({len(data)} rows)")
                except Exception as e:
                    logger.debug(f"Could not cache {symbol}: {e}")
                
                return data
            else:
                logger.debug(f"Yahoo Finance returned insufficient data for {symbol}")
                data = None
            
        except Exception as e:
            logger.debug(f"Yahoo Finance failed for {symbol}: {e}")
            data = None
        
        # Try Alpha Vantage API if Yahoo Finance failed
        if data is None:
            try:
                data = self._fetch_from_alpha_vantage(symbol, start_date, end_date)
                if data is not None and len(data) > 50:
                    # Save to cache
                    try:
                        data.to_csv(cache_file)
                        logger.info(f"Cached {symbol} from Alpha Vantage ({len(data)} rows)")
                    except Exception as e:
                        logger.debug(f"Could not cache {symbol}: {e}")
                    
                    return data
                else:
                    logger.debug(f"Alpha Vantage returned insufficient data for {symbol}")
                    data = None
            except Exception as e:
                logger.debug(f"Alpha Vantage failed for {symbol}: {e}")
                data = None
        
        # Fallback to synthetic data (always works)
        logger.info(f"Using synthetic data for {symbol}")
        return self._generate_synthetic_data(symbol, start_date, end_date)
    
    def _generate_synthetic_data(self, symbol: str, start_date: str, 
                                 end_date: str) -> pd.DataFrame:
        """
        Generate realistic synthetic historical data if real data unavailable
        
        Includes major market events:
        - 2000 tech bubble burst
        - 2008 financial crisis
        - 2020 COVID crash
        """
        start = pd.Timestamp(start_date)
        end = pd.Timestamp(end_date)
        
        # Create business day range
        dates = pd.bdate_range(start=start, end=end)
        n_days = len(dates)
        
        np.random.seed(hash(symbol) % 2**32)
        
        # Base parameters by symbol
        if symbol == '^GSPC':  # S&P 500
            base_price = 1500
            drift = 0.07  # 7% annual return
            vol = 0.15
        elif symbol in ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA']:
            base_price = np.random.randint(50, 200)
            drift = 0.12  # Tech higher growth
            vol = 0.30
        else:
            base_price = np.random.randint(30, 150)
            drift = 0.08
            vol = 0.20
        
        # Generate base GBM
        daily_drift = drift / 252
        daily_vol = vol / np.sqrt(252)
        
        returns = np.random.normal(daily_drift, daily_vol, n_days)
        
        # Add major market events
        event_dates = {
            '2000-03-10': -0.15,  # Tech crash peak
            '2000-09-30': -0.10,  # Further decline
            '2008-09-15': -0.20,  # Lehman collapse
            '2008-10-10': -0.15,  # Further crisis
            '2020-03-16': -0.20,  # COVID crash
            '2020-03-23': 0.10,   # Bounce
            '2022-09-28': -0.08,  # Rate hike impact
        }
        
        for event_date_str, event_return in event_dates.items():
            event_date = pd.Timestamp(event_date_str)
            if start <= event_date <= end:
                idx = (event_date - start).days
                if 0 <= idx < n_days:
                    # Scale event based on symbol
                    if symbol == '^GSPC':
                        returns[idx] += event_return
                    else:
                        # Tech stocks react more
                        if 'tech' in symbol.lower() or symbol in ['AAPL', 'MSFT', 'GOOGL']:
                            returns[idx] += event_return * 1.5
                        else:
                            returns[idx] += event_return * 0.8
        
        # Generate price from returns
        prices = base_price * np.exp(np.cumsum(returns))
        
        df = pd.DataFrame({
            'Date': dates,
            'Open': prices * (1 + np.random.normal(0, 0.005, n_days)),
            'High': prices * (1 + np.abs(np.random.normal(0, 0.01, n_days))),
            'Low': prices * (1 - np.abs(np.random.normal(0, 0.01, n_days))),
            'Close': prices,
            'Volume': np.random.uniform(1e6, 100e6, n_days),
            'Adj Close': prices
        })
        
        df.set_index('Date', inplace=True)
        
        logger.info(f"Generated synthetic data for {symbol} ({n_days} trading days)")
        return df
    
    def fetch_sp500_data(self, start_date: str = "2000-01-01", 
                        end_date: str = "2025-01-25") -> pd.DataFrame:
        """Fetch S&P 500 benchmark data"""
        return self.fetch_stock_data('^GSPC', start_date, end_date)
    
    def get_stock_list(self) -> List[str]:
        """Get recommended stocks for testing"""
        # Top NASDAQ stocks that existed in 2000
        return [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 
            'TSLA', 'META', 'NFLX', 'ADBE', 'INTC',
            'AMD', 'CSCO', 'QCOM', 'COST', 'AVGO',
            'TMUS', 'CMCSA', 'INTU', 'VRTX', 'NFLX',
            'AEP', 'LRCX', 'SNPS', 'CDNS', 'PCAR',
            'PAYX', 'ABNB', 'PANW', 'CRWD', 'ZM',
            'DXCM', 'WDAY', 'FAST', 'CPRT', 'CHKP'
        ]


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    fetcher = HistoricalDataFetcher()
    
    # Fetch S&P 500
    sp500 = fetcher.fetch_sp500_data()
    if sp500 is not None:
        print(f"\nS&P 500 Data:")
        print(f"  Date range: {sp500.index.min()} to {sp500.index.max()}")
        print(f"  Trading days: {len(sp500)}")
        print(f"  Start price: ${sp500['Close'].iloc[0]:.2f}")
        print(f"  End price: ${sp500['Close'].iloc[-1]:.2f}")
        print(f"  Return: {(sp500['Close'].iloc[-1] / sp500['Close'].iloc[0] - 1):.1%}")
    
    # Fetch one sample stock
    aapl = fetcher.fetch_stock_data('AAPL')
    if aapl is not None:
        print(f"\nAAPL Data:")
        print(f"  Date range: {aapl.index.min()} to {aapl.index.max()}")
        print(f"  Trading days: {len(aapl)}")
        print(f"  Return: {(aapl['Close'].iloc[-1] / aapl['Close'].iloc[0] - 1):.1%}")
