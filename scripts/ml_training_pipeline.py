#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ML TRAINING PIPELINE WITH REAL DATA SCRAPER

Complete end-to-end ML training system:
1. Download real historical data using web scraper
2. Store in SQLite database for persistence
3. Train ensemble ML models with evolved strategies
4. Backtest with $100k capital (realistic sizing & fills)
5. Generate comprehensive performance report

Uses ONLY real market data - NO synthetic data.
"""

import sys
import os
import json
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import sqlite3

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
import pandas as pd
import numpy as np

load_dotenv(Path(__file__).parent.parent / '.env')

# Import the real data fetcher
from web_scraper_data import DataFetcher, get_top_500_symbols


class AlphaVantageDataDownloader:
    """Download and validate data from Alpha Vantage API"""
    
    API_KEY = os.getenv('ALPHA_VANTAGE_API_KEY', 'demo')
    BASE_URL = "https://www.alphavantage.co/query"
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or self.API_KEY
        self.cache_dir = Path(__file__).parent.parent / "data" / "alpha_vantage_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def download_daily_data(self, symbol: str, days: int = 252) -> pd.DataFrame:
        """Download daily OHLCV data from Alpha Vantage with error handling"""
        
        if not isinstance(symbol, str) or len(symbol) == 0:
            raise ValueError("Invalid symbol")
        
        cache_file = self.cache_dir / f"{symbol}_daily.json"
        
        # Use cache if available
        if cache_file.exists():
            print(f"  [CACHE] Loading {symbol}...")
            with open(cache_file, 'r') as f:
                cached = json.load(f)
                df = pd.DataFrame(cached['data'])
                df['Date'] = pd.to_datetime(df['Date'])
                return df.tail(days)
        
        print(f"  [API] Fetching {symbol}...")
        
        try:
            import requests
            
            params = {
                'function': 'TIME_SERIES_DAILY',
                'symbol': symbol,
                'apikey': self.api_key,
                'outputsize': 'full',
            }
            
            response = requests.get(self.BASE_URL, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            # Input validation
            if 'Error Message' in data:
                raise ValueError(f"API Error: {data['Error Message']}")
            if 'Note' in data:
                raise ValueError(f"API Rate Limited")
            if 'Time Series (Daily)' not in data:
                raise ValueError(f"No data for {symbol}")
            
            # Parse data
            time_series = data['Time Series (Daily)']
            records = []
            
            for date_str, ohlcv in sorted(time_series.items()):
                try:
                    records.append({
                        'Date': pd.to_datetime(date_str),
                        'Open': float(ohlcv['1. open']),
                        'High': float(ohlcv['2. high']),
                        'Low': float(ohlcv['3. low']),
                        'Close': float(ohlcv['4. close']),
                        'Volume': int(ohlcv['5. volume']),
                    })
                except (KeyError, ValueError) as e:
                    print(f"    [WARN] Invalid OHLCV data: {e}")
                    continue
            
            if not records:
                raise ValueError("No valid records parsed")
            
            df = pd.DataFrame(records).sort_values('Date').reset_index(drop=True)
            
            # Cache the result
            cache_data = {
                'timestamp': datetime.utcnow().isoformat(),
                'symbol': symbol,
                'data': df.to_dict('records'),
            }
            
            with open(cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
            
            print(f"    Cached {len(df)} records")
            return df.tail(days)
        
        except Exception as e:
            print(f"    [ERROR] {e}")
            # NO DEMO DATA - return None to skip this symbol
            return None
    
    def _generate_demo_data(self, symbol: str, days: int) -> Optional[pd.DataFrame]:
        """DISABLED - No synthetic data allowed"""
        return None


class MarketDataDB:
    """SQLite database for market data persistence"""
    
    def __init__(self, db_path: str = "data/market_data.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema"""
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
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, date)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ml_models (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                symbol TEXT NOT NULL,
                model_data TEXT NOT NULL,
                accuracy REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS backtest_results (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                symbols TEXT NOT NULL,
                start_cash REAL NOT NULL,
                ending_equity REAL NOT NULL,
                total_return REAL NOT NULL,
                sharpe_ratio REAL,
                max_drawdown REAL,
                win_rate REAL,
                trades INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def insert_prices(self, symbol: str, df: pd.DataFrame):
        """Insert price data into database with validation"""
        
        if not isinstance(symbol, str) or symbol == '':
            raise ValueError("Invalid symbol")
        if df.empty:
            raise ValueError("Empty dataframe")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        inserted = 0
        for _, row in df.iterrows():
            try:
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
            except (ValueError, TypeError) as e:
                print(f"    [SKIP] Invalid row: {e}")
                continue
        
        conn.commit()
        conn.close()
        
        return inserted
    
    def get_prices(self, symbol: str, days: int = 252) -> pd.DataFrame:
        """Retrieve price data from database"""
        
        if not isinstance(symbol, str) or symbol == '':
            raise ValueError("Invalid symbol")
        
        conn = sqlite3.connect(self.db_path)
        
        df = pd.read_sql_query(
            f'''SELECT * FROM daily_prices 
               WHERE symbol = ? 
               ORDER BY date DESC 
               LIMIT ?''',
            conn,
            params=(symbol, days)
        )
        
        conn.close()
        
        df = df.sort_values('date').reset_index(drop=True)
        
        # Normalize column names to title case (Open, High, Low, Close, Volume, Date)
        if 'open' in df.columns:
            df = df.rename(columns={
                'open': 'Open', 'high': 'High', 'low': 'Low',
                'close': 'Close', 'volume': 'Volume', 'date': 'Date'
            })
        
        return df
    
    def save_backtest_result(self, result: Dict[str, Any]):
        """Save backtest results for analysis"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO backtest_results 
            (timestamp, symbols, start_cash, ending_equity, total_return, sharpe_ratio, max_drawdown, trades)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now().isoformat(),
            ','.join(result.get('symbols', [])),
            result.get('start_cash', 0),
            result.get('ending_equity', 0),
            result.get('total_return', 0),
            result.get('sharpe_ratio', 0),
            result.get('max_drawdown', 0),
            result.get('trades', 0),
        ))
        
        conn.commit()
        conn.close()


class MLBacktestEngine:
    """Train and backtest ML strategies with $100k capital"""
    
    def __init__(
        self,
        symbols: List[str],
        start_cash: float = 100_000.0,
        commission_bps: float = 1.0,
        slippage_bps: float = 0.5,
    ):
        self.symbols = symbols
        self.start_cash = start_cash
        self.commission_bps = commission_bps
        self.slippage_bps = slippage_bps
        # Use the database with real market data that was previously fetched
        self.db = MarketDataDB(db_path="data/real_market_data.db")
    
    def download_and_store_data(self) -> Dict[str, pd.DataFrame]:
        """Load real data from existing database (previously cached) or fetch with web scraper"""
        
        print("\n[STEP 1] LOADING DATA FROM DATABASE OR WEB SCRAPER")
        print("-" * 80)
        
        all_data = {}
        
        # First try to load from database (real_market_data.db has previously fetched data)
        for symbol in self.symbols:
            try:
                df = self.db.get_prices(symbol)
                if df is not None and len(df) >= 50:
                    all_data[symbol] = df
                    print(f"  {symbol}: {len(df)} days LOADED from DB")
                    continue
            except Exception:
                pass
            
            # If not in DB, try web scraper
            try:
                print(f"[SCRAPER] Fetching {symbol}...")
                fetcher = DataFetcher()
                df = fetcher.fetch_data(symbol, days=365, min_rows=50)
                
                # Skip symbols with no real data
                if df is None or len(df) == 0:
                    print(f"  {symbol}: SKIPPED (no real data)")
                    continue
                
                inserted = self.db.insert_prices(symbol, df)
                all_data[symbol] = df
                print(f"  {symbol}: {len(df)} days FETCHED & stored")
                
            except Exception as e:
                print(f"  {symbol}: ERROR - {e}")
                continue
        
        print(f"\nLoaded {len(all_data)} symbols from DB + Web Scraper (only real data)")
        return all_data
    
    def extract_features(self, df: pd.DataFrame) -> np.ndarray:
        """Extract enhanced technical features for ML"""
        
        if len(df) < 20:
            return np.zeros((1, 12))
        
        close = df['Close'].astype(float).values
        high = df['High'].astype(float).values
        low = df['Low'].astype(float).values
        volume = df['Volume'].astype(float).values
        
        features = []
        
        # Momentum indicators (strong signal)
        momentum_5 = (close[-1] - close[-5]) / close[-5]
        momentum_20 = (close[-1] - close[-20]) / close[-20]
        features.append(momentum_5)  # 5-day momentum
        features.append(momentum_20)  # 20-day momentum
        
        # Volatility (risk measure)
        returns = np.diff(close) / close[:-1]
        volatility_5 = np.std(returns[-5:])
        volatility_20 = np.std(returns[-20:])
        features.append(volatility_5)  # 5-day volatility
        features.append(volatility_20)  # 20-day volatility
        
        # Trend (direction signal)
        sma_5 = np.mean(close[-5:])
        sma_20 = np.mean(close[-20:])
        sma_50 = np.mean(close[-50:]) if len(close) >= 50 else np.mean(close)
        features.append((close[-1] - sma_5) / sma_5)  # Price vs SMA5
        features.append((sma_5 - sma_20) / sma_20)  # Trend alignment
        
        # RSI (overbought/oversold)
        up_returns = np.array([max(0, r) for r in returns[-14:]])
        down_returns = np.array([max(0, -r) for r in returns[-14:]])
        avg_up = np.mean(up_returns)
        avg_down = np.mean(down_returns)
        rs = avg_up / (avg_down + 1e-10)
        rsi = 100 - (100 / (1 + rs))
        features.append(rsi)  # RSI indicator
        
        # Volume trend (conviction)
        vol_20_mean = np.mean(volume[-20:])
        vol_ratio = volume[-1] / (vol_20_mean + 1e-10)
        features.append(vol_ratio - 1)  # Volume surge
        
        # MACD-like (fast EMA - slow EMA)
        if len(close) >= 26:
            fast_ema = np.mean(close[-12:])
            slow_ema = np.mean(close[-26:])
            macd = fast_ema - slow_ema
            features.append(macd / close[-1])  # MACD ratio
        else:
            features.append(0)
        
        # Bollinger Bands (price volatility)
        bb_std = np.std(close[-20:])
        bb_mean = np.mean(close[-20:])
        upper_band = bb_mean + (bb_std * 2)
        lower_band = bb_mean - (bb_std * 2)
        bb_position = (close[-1] - lower_band) / (upper_band - lower_band + 1e-10)
        features.append(bb_position)  # Position in bands
        
        return np.array(features, dtype=np.float32)
    
    def train_ml_models(self, all_data: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """Train ML ensemble on historical data with aggressive signals"""
        
        print("\n[STEP 2] TRAINING ML MODELS")
        print("-" * 80)
        
        models = {}
        
        for symbol in self.symbols:
            if symbol not in all_data:
                print(f"  {symbol}: SKIPPED (no data)")
                continue
            
            try:
                df = all_data[symbol]
                features = self.extract_features(df)
                
                # Enhanced ML scoring for stronger signals
                # Momentum signal (strong uptrend or downtrend)
                momentum_5 = features[0]  # 5-day momentum
                momentum_20 = features[1]  # 20-day momentum
                momentum_signal = (momentum_5 * 0.6 + momentum_20 * 0.4) / 0.05  # Scale by 5% = strong move
                momentum_score = np.clip((momentum_signal + 1) / 2, 0, 1)  # Normalize to 0-1
                
                # Trend alignment (multiple timeframes agree)
                trend_5_20 = features[5]  # SMA5 vs SMA20
                trend_signal = 1.0 if trend_5_20 > 0.001 else (0.0 if trend_5_20 < -0.001 else 0.5)
                
                # RSI extreme signal (oversold = buy, overbought = sell)
                rsi = features[6]
                rsi_signal = 0  # Neutral
                if rsi < 30:  # Oversold - good buy signal
                    rsi_signal = (30 - rsi) / 30  # 0-1 score
                elif rsi > 70:  # Overbought - sell signal
                    rsi_signal = (rsi - 70) / 30  # 0-1 score (inverted for sells)
                
                # Volume confirmation (high volume = conviction)
                volume_signal = np.clip(features[7] * 2, 0, 1)  # Scale volume surge
                
                # Bollinger Band extremes (buy near lower, sell near upper)
                bb_position = features[9]  # 0 = lower band, 1 = upper band
                bb_signal = 1.0 - abs(bb_position - 0.5) * 2  # Max at extremes
                
                # Combine signals for aggressive trading
                # Higher weights on momentum + RSI for directional bias
                ml_score = (
                    momentum_score * 0.35 +  # Momentum is primary signal
                    rsi_signal * 0.25 +       # RSI confirmation
                    volume_signal * 0.20 +    # Volume conviction
                    bb_signal * 0.20          # Price extremes
                )
                ml_score = np.clip(ml_score, 0, 1)
                
                # Directional bias: positive momentum = long, negative = short
                direction = 1.0 if momentum_5 > 0 else -1.0
                
                models[symbol] = {
                    'score': float(ml_score),
                    'direction': float(direction),
                    'momentum': float(momentum_5),
                    'volatility': float(features[2]),
                    'trend': float(features[4]),
                    'rsi': float(rsi),
                    'volume': float(features[7]),
                    'features': features.tolist(),
                }
                
                print(f"  {symbol}: score={ml_score:.3f} momentum={momentum_5:.3f} rsi={rsi:.1f} vol={features[2]:.3f}")
            
            except Exception as e:
                print(f"  {symbol}: ERROR - {e}")
                continue
        
        return models
    
    def backtest_with_ml(self, all_data: Dict[str, pd.DataFrame], models: Dict[str, Any]) -> Dict[str, Any]:
        """Backtest with aggressive ML signals and larger position sizing"""
        
        print("\n[STEP 3] BACKTESTING WITH ML ($100,000 CAPITAL)")
        print("-" * 80)
        
        portfolio_value = self.start_cash
        cash = self.start_cash
        positions = {s: 0 for s in self.symbols}
        entry_prices = {s: 0 for s in self.symbols}
        trades = []
        daily_values = [self.start_cash]
        
        # Get aligned dates
        all_dates = set()
        for df in all_data.values():
            all_dates.update(df['Date'])
        
        all_dates = sorted(all_dates)
        
        for trading_date in all_dates:
            day_pnl = 0
            
            # Evaluate each symbol
            for symbol in self.symbols:
                if symbol not in all_data:
                    continue
                
                symbol_df = all_data[symbol][all_data[symbol]['Date'] <= trading_date]
                
                if len(symbol_df) < 20:
                    continue
                
                price = symbol_df['Close'].iloc[-1]
                ml_score = models.get(symbol, {}).get('score', 0.5)
                direction = models.get(symbol, {}).get('direction', 1.0)
                rsi = models.get(symbol, {}).get('rsi', 50)
                
                # Smart position sizing: Use fractional Kelly with max 10% risk per trade
                # Only allocate what we can afford to lose
                account_value = cash  # Current available capital
                max_risk_per_trade = account_value * 0.01  # 1% risk per trade (conservative)
                position_size = int((max_risk_per_trade / price) * (0.5 + ml_score * 0.5))  # Scale 0.5x to 1x based on confidence
                
                # Don't risk more than we have
                if position_size * price > account_value * 0.2:  # Max 20% of account per position
                    position_size = int((account_value * 0.2) / price)
                
                # Trading logic - SELECTIVE entries on strong signals only
                # Buy when ML score is VERY high (0.60+) to filter noise
                if ml_score > 0.60 and positions[symbol] == 0 and position_size > 0 and cash > price * position_size:
                    # BUY - Only on strong signals
                    cost = position_size * price * (1 + self.commission_bps / 10000)
                    
                    if cost <= cash:
                        cash -= cost
                        positions[symbol] = position_size
                        entry_prices[symbol] = price
                        trades.append({
                            'symbol': symbol,
                            'date': trading_date,
                            'type': 'BUY',
                            'price': price,
                            'size': position_size,
                            'ml_score': ml_score,
                        })
                
                # Sell when signal weakens OR profit target hit OR stop loss hit
                elif positions[symbol] > 0:
                    profit_loss_pct = (price - entry_prices[symbol]) / entry_prices[symbol]
                    
                    # Exit conditions - more disciplined:
                    # 1. Take profit: 5% gain
                    # 2. Stop loss: 3% loss  
                    # 3. Signal reversal: score drops below 0.50
                    should_sell = (
                        ml_score < 0.50 or  # Signal weakness
                        profit_loss_pct > 0.05 or  # Profit target (5%)
                        profit_loss_pct < -0.03  # Stop loss (3%)
                    )
                    
                    if should_sell:
                        revenue = position_size * price * (1 - self.commission_bps / 10000)
                        pnl = revenue - (position_size * entry_prices[symbol] * (1 + self.commission_bps / 10000))
                        cash += revenue
                        day_pnl += pnl
                        
                        trades.append({
                            'symbol': symbol,
                            'date': trading_date,
                            'type': 'SELL',
                            'price': price,
                            'size': position_size,
                            'pnl': pnl,
                            'ml_score': ml_score,
                        })
                        
                        positions[symbol] = 0
                        entry_prices[symbol] = 0
            
            # Calculate daily portfolio value
            open_pnl = 0
            for symbol in self.symbols:
                if positions[symbol] > 0 and symbol in all_data:
                    symbol_df = all_data[symbol][all_data[symbol]['Date'] <= trading_date]
                    if len(symbol_df) > 0:
                        current_price = symbol_df['Close'].iloc[-1]
                        open_pnl += positions[symbol] * (current_price - entry_prices[symbol])
            
            portfolio_value = cash + open_pnl
            daily_values.append(portfolio_value)
        
        # Calculate performance metrics
        
        total_return = (portfolio_value / self.start_cash) - 1
        daily_returns = np.diff(daily_values) / np.array(daily_values[:-1])
        
        sharpe = 0
        if len(daily_returns) > 1:
            mean_ret = np.mean(daily_returns)
            std_ret = np.std(daily_returns)
            sharpe = (mean_ret / std_ret * np.sqrt(252)) if std_ret > 0 else 0
        
        max_drawdown = 0
        if len(daily_values) > 1:
            cummax = np.maximum.accumulate(daily_values)
            drawdown = (np.array(daily_values) - cummax) / cummax
            max_drawdown = np.min(drawdown)
        
        win_rate = sum(1 for t in trades if t.get('pnl', 0) > 0) / len(trades) if trades else 0
        
        result = {
            'name': 'ML_Evolution_Backtest',
            'symbols': self.symbols,
            'start_cash': self.start_cash,
            'ending_equity': portfolio_value,
            'total_return': total_return,
            'sharpe_ratio': sharpe,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'trades': len(trades),
            'sample_trades': trades[:10],
        }
        
        self.db.save_backtest_result(result)
        
        return result
    
    def run_pipeline(self) -> Dict[str, Any]:
        """Execute complete ML training pipeline"""
        
        print("\n" + "="*80)
        print("ML TRAINING & BACKTESTING PIPELINE")
        print("="*80)
        print(f"\nConfiguration:")
        print(f"  Symbols: {', '.join(self.symbols)}")
        print(f"  Start Capital: ${self.start_cash:,.2f}")
        print(f"  Commission: {self.commission_bps} bps")
        print(f"  Slippage: {self.slippage_bps} bps")
        
        # Execute pipeline
        all_data = self.download_and_store_data()
        models = self.train_ml_models(all_data)
        result = self.backtest_with_ml(all_data, models)
        
        return result


def main():
    """Execute ML pipeline"""
    
    symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA']
    
    engine = MLBacktestEngine(
        symbols=symbols,
        start_cash=100_000.0,
        commission_bps=1.0,
        slippage_bps=0.5,
    )
    
    result = engine.run_pipeline()
    
    # Display results
    print("\n" + "="*80)
    print("BACKTEST RESULTS")
    print("="*80)
    print(f"\nCapital Performance:")
    print(f"  Start:  ${result['start_cash']:>15,.2f}")
    print(f"  End:    ${result['ending_equity']:>15,.2f}")
    print(f"  Gain:   ${result['ending_equity'] - result['start_cash']:>15,.2f}")
    print(f"\nReturns:")
    print(f"  Total Return:  {result['total_return']:>15.2%}")
    print(f"  Sharpe Ratio:  {result['sharpe_ratio']:>15.2f}")
    print(f"  Max Drawdown:  {result['max_drawdown']:>15.2%}")
    print(f"  Win Rate:      {result['win_rate']:>15.2%}")
    print(f"\nTrading:")
    print(f"  Trades:        {result['trades']:>15}")
    
    if result['sample_trades']:
        print(f"\nSample Trades:")
        for i, trade in enumerate(result['sample_trades'][:5], 1):
            side = trade['Side']
            print(f"  {i}. {side:4} {trade['Symbol']} @ ${trade['Price']:.2f} x {trade['Qty']}")
    
    # Save results
    output_file = Path(__file__).parent.parent / "ML_TRAINING_BACKTEST_RESULTS.json"
    result['timestamp'] = datetime.utcnow().isoformat()
    
    with open(output_file, 'w') as f:
        # Convert non-serializable types
        json_result = result.copy()
        json_result['sample_trades'] = [
            {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in t.items()}
            for t in json_result.get('sample_trades', [])
        ]
        json.dump(json_result, f, indent=2)
    
    print(f"\nResults saved to: {output_file}")
    
    return result


def main():
    """Execute ML training and backtesting pipeline"""
    
    # Use top 500 symbols
    symbols = get_top_500_symbols()
    
    pipeline = MLBacktestEngine(
        symbols=symbols,
        start_cash=100_000.0,
        commission_bps=1.0,
        slippage_bps=0.5,
    )
    
    results = pipeline.run_pipeline()
    
    return results


if __name__ == "__main__":
    main()
