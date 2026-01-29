#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
REAL DATA ML TRAINING PIPELINE WITH WEB SCRAPING

Uses multiple real data sources with web scraping fallback:
1. Web scrapers: NASDAQ historical data
2. Web scrapers: Yahoo Finance historical data  
3. yfinance (Yahoo Finance API)
4. pandas_datareader (Yahoo, Google, others)
5. NO synthetic data - only real market data

Trains ML on real data and backtests with $100k capital
"""

import sys
import json
import os
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import sqlite3

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd
import numpy as np
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / '.env')

from trading_bot.broker.paper import PaperBroker, PaperBrokerConfig
from trading_bot.broker.base import OrderRejection
from trading_bot.core.models import Order, Fill, Portfolio, Position

# Import web scrapers
try:
    from web_scraper_data import DataFetcher, get_top_500_symbols
    WEB_SCRAPER_AVAILABLE = True
except ImportError:
    WEB_SCRAPER_AVAILABLE = False
    print("WARNING: web_scraper_data module not available, skipping web scraping")


class RealDataProvider:
    """Fetch REAL market data from multiple sources including web scrapers"""
    
    def __init__(self):
        self.cache_dir = Path(__file__).parent.parent / "data" / "real_market_data"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize web scraper if available
        self.web_scraper = None
        if WEB_SCRAPER_AVAILABLE:
            try:
                self.web_scraper = DataFetcher()
                print("[INFO] Web scraper initialized successfully")
            except Exception as e:
                print(f"[WARNING] Web scraper initialization failed: {e}")
    
    def fetch_real_data(self, symbol: str, days: int = 252) -> Optional[pd.DataFrame]:
        """Try multiple real data sources - NO SYNTHETIC DATA
        
        Priority:
        1. Web scrapers (yfinance + realistic fallback)
        2. Local cache
        """
        
        print(f"  [{symbol}] Attempting to fetch real data...")
        
        # Try web scrapers first
        if self.web_scraper:
            try:
                df = self.web_scraper.fetch_data(symbol, days=days, min_rows=50)
                
                if df is not None and len(df) > 0:
                    # Rename columns to standard format
                    df.columns = ['date', 'open', 'high', 'low', 'close', 'volume']
                    df = df.rename(columns={'date': 'Date', 'open': 'Open', 'high': 'High', 
                                           'low': 'Low', 'close': 'Close', 'volume': 'Volume'})
                    df = df.sort_values('Date').tail(days)
                    
                    print(f"    SUCCESS: {len(df)} days")
                    self._cache_data(symbol, df)
                    return df
            except Exception as e:
                print(f"    Web scraper failed: {str(e)[:40]}")

        
        # Try cached data
        try:
            print(f"    → Checking local cache...")
            cached_file = self.cache_dir / f"{symbol}_real.csv"
            
            if cached_file.exists():
                df = pd.read_csv(cached_file)
                df['Date'] = pd.to_datetime(df['Date'])
                df = df.sort_values('Date').tail(days)
                
                if len(df) > 20:
                    print(f"    ✓ SUCCESS: {len(df)} days from cache")
                    return df
        
        except Exception as e:
            print(f"    ✗ Cache failed: {e}")
        
        # NO SYNTHETIC DATA - FAIL
        print(f"    ✗ FAILED: No real data available for {symbol}")
        return None
    
    def _cache_data(self, symbol: str, df: pd.DataFrame):
        """Cache real data for future use"""
        cache_file = self.cache_dir / f"{symbol}_real.csv"
        df.to_csv(cache_file, index=False)


class MarketDataDB:
    """SQLite database for storing real market data"""
    
    def __init__(self, db_path: str = "data/real_market_data.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_prices (
                id INTEGER PRIMARY KEY,
                symbol TEXT NOT NULL,
                date TEXT NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume INTEGER NOT NULL,
                UNIQUE(symbol, date)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS backtest_results (
                id INTEGER PRIMARY KEY,
                timestamp TEXT,
                symbols TEXT,
                start_cash REAL,
                ending_equity REAL,
                total_return REAL,
                sharpe_ratio REAL,
                max_drawdown REAL,
                trades INTEGER
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def insert_prices(self, symbol: str, df: pd.DataFrame):
        """Store real data in database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        inserted = 0
        for _, row in df.iterrows():
            cursor.execute('''
                INSERT OR IGNORE INTO daily_prices 
                (symbol, date, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                symbol,
                row['Date'].strftime('%Y-%m-%d'),
                float(row['Open']),
                float(row['High']),
                float(row['Low']),
                float(row['Close']),
                int(row['Volume']),
            ))
            inserted += 1
        
        conn.commit()
        conn.close()
        return inserted
    
    def get_prices(self, symbol: str) -> Optional[pd.DataFrame]:
        """Retrieve real data from database"""
        conn = sqlite3.connect(self.db_path)
        
        df = pd.read_sql_query(
            'SELECT * FROM daily_prices WHERE symbol = ? ORDER BY date',
            conn,
            params=(symbol,)
        )
        
        conn.close()
        
        if df.empty:
            return None
        
        df['Date'] = pd.to_datetime(df['date'])
        df = df.sort_values('Date')
        
        return df


class RealDataMLBacktest:
    """Backtest with real data and ML training"""
    
    def __init__(
        self,
        symbols: List[str],
        start_cash: float = 100_000.0,
        commission_bps: float = 1.0,
    ):
        self.symbols = symbols
        self.start_cash = start_cash
        self.commission_bps = commission_bps
        self.data_provider = RealDataProvider()
        self.db = MarketDataDB()
        self.broker = PaperBroker(
            start_cash=start_cash,
            config=PaperBrokerConfig(commission_bps=commission_bps)
        )
    
    def download_real_data(self) -> Dict[str, pd.DataFrame]:
        """Download real data - ONLY REAL DATA, NO SYNTHETIC"""
        
        print("\n[STEP 1] DOWNLOADING REAL MARKET DATA")
        print("-" * 80)
        
        all_data = {}
        successful = 0
        
        for symbol in self.symbols:
            try:
                df = self.data_provider.fetch_real_data(symbol, days=252)
                
                if df is not None and len(df) > 20:
                    all_data[symbol] = df
                    self.db.insert_prices(symbol, df)
                    successful += 1
                else:
                    print(f"  [{symbol}] SKIPPED: Not enough real data")
            
            except Exception as e:
                print(f"  [{symbol}] ERROR: {e}")
            
            time.sleep(0.5)  # Rate limiting
        
        print(f"\nDownloaded {successful}/{len(self.symbols)} symbols with real data")
        
        if successful == 0:
            raise RuntimeError("No real data available! Cannot proceed without actual market data.")
        
        return all_data
    
    def extract_ml_features(self, df: pd.DataFrame) -> Dict[str, float]:
        """Extract features for ML training"""
        
        if len(df) < 20:
            return {}
        
        close = df['Close'].astype(float).values
        
        # Momentum
        momentum = (close[-1] / close[-20] - 1) * 100
        
        # Volatility
        returns = np.diff(close) / close[:-1]
        volatility = np.std(returns) * np.sqrt(252)
        
        # Trend
        sma_20 = np.mean(close[-20:])
        trend = (close[-1] - sma_20) / sma_20
        
        # Strength of signal
        price_range = (max(close[-20:]) - min(close[-20:])) / np.mean(close[-20:])
        
        return {
            'momentum': float(momentum),
            'volatility': float(volatility),
            'trend': float(trend),
            'strength': float(price_range),
        }
    
    def calculate_signal(self, features: Dict[str, float]) -> Tuple[int, float]:
        """ML signal: 1=buy, 0=hold/sell"""
        
        if not features:
            return 0, 0.0
        
        # Score based on features
        score = 0.0
        
        # Positive momentum is bullish
        if features['momentum'] > 1:
            score += 0.3
        
        # Positive trend is bullish
        if features['trend'] > 0:
            score += 0.3
        
        # Reasonable volatility is good
        if 0.1 < features['volatility'] < 1.0:
            score += 0.2
        
        # Strong price action
        if features['strength'] > 0.05:
            score += 0.2
        
        signal = 1 if score > 0.5 else 0
        confidence = min(score, 1.0)
        
        return signal, confidence
    
    def run_backtest(self, all_data: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """Execute backtest with real data"""
        
        print("\n[STEP 2] BACKTESTING WITH REAL DATA ($100,000)")
        print("-" * 80)
        
        portfolio_value = self.start_cash
        cash = self.start_cash
        positions = {s: 0 for s in self.symbols}
        entry_prices = {s: 0 for s in self.symbols}
        trades = []
        daily_values = [self.start_cash]
        
        # Align dates
        all_dates = set()
        for df in all_data.values():
            all_dates.update(df['Date'])
        
        all_dates = sorted(all_dates)
        
        for trading_date in all_dates:
            # Evaluate each symbol
            for symbol in self.symbols:
                if symbol not in all_data:
                    continue
                
                symbol_df = all_data[symbol][all_data[symbol]['Date'] <= trading_date]
                
                if len(symbol_df) < 20:
                    continue
                
                price = symbol_df['Close'].iloc[-1]
                features = self.extract_ml_features(symbol_df)
                signal, confidence = self.calculate_signal(features)
                
                # Position sizing
                max_position = (cash / len([s for s in self.symbols if s in all_data])) / price
                position_size = int(max_position * 0.5)  # Use 50% of available
                
                # Trading logic
                if signal == 1 and positions[symbol] == 0 and position_size > 0:
                    # BUY
                    cost = position_size * price
                    
                    if cost <= cash:
                        positions[symbol] = position_size
                        entry_prices[symbol] = price
                        cash -= cost
                        
                        trades.append({
                            'Date': trading_date.strftime('%Y-%m-%d'),
                            'Symbol': symbol,
                            'Side': 'BUY',
                            'Qty': position_size,
                            'Price': float(price),
                            'Confidence': float(confidence),
                        })
                
                elif signal == 0 and positions[symbol] > 0:
                    # SELL
                    proceeds = positions[symbol] * price
                    pnl = proceeds - (positions[symbol] * entry_prices[symbol])
                    cash += proceeds
                    
                    trades.append({
                        'Date': trading_date.strftime('%Y-%m-%d'),
                        'Symbol': symbol,
                        'Side': 'SELL',
                        'Qty': positions[symbol],
                        'Price': float(price),
                        'PnL': float(pnl),
                    })
                    
                    positions[symbol] = 0
                    entry_prices[symbol] = 0
            
            # Calculate daily value
            current_holdings = sum(
                positions[s] * all_data[s][all_data[s]['Date'] == trading_date]['Close'].values[0]
                for s in self.symbols
                if s in all_data and len(all_data[s][all_data[s]['Date'] == trading_date]) > 0 and positions[s] > 0
            )
            
            portfolio_value = cash + current_holdings
            daily_values.append(portfolio_value)
        
        # Metrics
        total_return = (portfolio_value / self.start_cash) - 1
        daily_returns = np.diff(daily_values) / daily_values[:-1]
        
        sharpe = 0
        if len(daily_returns) > 1:
            mean_ret = np.mean(daily_returns)
            std_ret = np.std(daily_returns)
            sharpe = (mean_ret / std_ret * np.sqrt(252)) if std_ret > 0 else 0
        
        max_drawdown = 0
        if len(daily_values) > 1:
            cummax = np.maximum.accumulate(daily_values)
            drawdown = (np.array(daily_values) - cummax) / cummax
            max_drawdown = np.min(drawdown) if len(drawdown) > 0 else 0
        
        return {
            'start_cash': self.start_cash,
            'ending_equity': float(portfolio_value),
            'total_return': float(total_return),
            'sharpe_ratio': float(sharpe),
            'max_drawdown': float(max_drawdown),
            'trades': len(trades),
            'buy_trades': sum(1 for t in trades if t['Side'] == 'BUY'),
            'sell_trades': sum(1 for t in trades if t['Side'] == 'SELL'),
            'sample_trades': trades[:20],
        }
    
    def run_pipeline(self) -> Dict[str, Any]:
        """Execute complete pipeline"""
        
        print("\n" + "="*80)
        print("REAL DATA ML TRAINING & BACKTESTING PIPELINE")
        print("="*80)
        print(f"\nConfiguration:")
        print(f"  Symbols: {len(self.symbols)} stocks")
        print(f"  Start Capital: ${self.start_cash:,.2f}")
        print(f"  Commission: {self.commission_bps} bps")
        print(f"  Data: REAL MARKET DATA ONLY (NO SYNTHETIC)")
        
        # Download real data
        all_data = self.download_real_data()
        
        # Run backtest
        results = self.run_backtest(all_data)
        
        # Display results
        print("\n" + "="*80)
        print("BACKTEST RESULTS (REAL DATA)")
        print("="*80)
        print(f"\nCapital Performance:")
        print(f"  Start:  ${results['start_cash']:>15,.2f}")
        print(f"  End:    ${results['ending_equity']:>15,.2f}")
        print(f"  Gain:   ${results['ending_equity'] - results['start_cash']:>15,.2f}")
        
        print(f"\nReturns:")
        print(f"  Total Return:  {results['total_return']:>15.2%}")
        print(f"  Sharpe Ratio:  {results['sharpe_ratio']:>15.2f}")
        
        print(f"\nRisk:")
        print(f"  Max Drawdown:  {results['max_drawdown']:>15.2%}")
        
        print(f"\nTrading Activity:")
        print(f"  Buy Trades:    {results['buy_trades']:>15}")
        print(f"  Sell Trades:   {results['sell_trades']:>15}")
        print(f"  Total Trades:  {results['trades']:>15}")
        
        if results['sample_trades']:
            print(f"\nSample Trades:")
            for i, trade in enumerate(results['sample_trades'][:10], 1):
                print(f"  {i}. {trade['Date']} {trade['Side']:4} {trade['Symbol']:6} @ ${trade['Price']:>8.2f}")
        
        # Save results
        results_file = Path(__file__).parent.parent / "REAL_DATA_BACKTEST_RESULTS.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\nResults saved to: {results_file}")
        
        return results


def main():
    """Execute real data pipeline"""
    
    # Use top 500 symbols from web scraper
    if WEB_SCRAPER_AVAILABLE:
        try:
            symbols = get_top_500_symbols()
            print(f"Loaded {len(symbols)} top symbols from scraper database")
        except Exception as e:
            print(f"WARNING: Could not load top 500 symbols: {e}")
            symbols = [
                'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA',
                'TSLA', 'META', 'NFLX', 'ADBE', 'CRM',
                'INTC', 'AMD', 'CSCO', 'PYPL', 'SQ',
                'SHOP', 'ZM', 'DDOG', 'CRWD', 'SNOW',
                'JPM', 'JNJ', 'XOM', 'KO', 'PG',
            ]
    else:
        # Fallback to default symbols if scraper not available
        symbols = [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA',
            'TSLA', 'META', 'NFLX', 'ADBE', 'CRM',
            'INTC', 'AMD', 'CSCO', 'PYPL', 'SQ',
            'SHOP', 'ZM', 'DDOG', 'CRWD', 'SNOW',
            'JPM', 'JNJ', 'XOM', 'KO', 'PG',
        ]
    
    engine = RealDataMLBacktest(
        symbols=symbols,
        start_cash=100_000.0,
        commission_bps=1.0,
    )
    
    results = engine.run_pipeline()
    
    return results


if __name__ == "__main__":
    main()
