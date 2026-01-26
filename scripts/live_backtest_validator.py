#!/usr/bin/env python
"""Live Backtest Validator - Run strategy backtests while bot trades live."""

import sys
import json
import logging
from pathlib import Path

import pandas as pd

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from trading_bot.configs import load_config
from trading_bot.data.providers import AlpacaProvider
from trading_bot.broker.alpaca import AlpacaConfig

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


class LiveBacktestValidator:
    """Run backtests while bot trades live."""
    
    def __init__(self, config_path):
        self.config = load_config(config_path)
        self.alpaca_config = AlpacaConfig.from_env(paper_mode=True)
        self.provider = AlpacaProvider(config=self.alpaca_config)
        self.symbols = [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META', 'NFLX',
            'AMD', 'INTC', 'MRNA', 'COIN', 'DDOG', 'SNOW', 'PLTR', 'SHOP',
            'CRM', 'PYPL', 'SQ', 'UPST', 'ROKU', 'ZOOM', 'TWLO', 'PINS'
        ]
        self.results = {}
    
    def download_historical_data(self, period='90d', interval='1d'):
        """Download historical data for backtesting."""
        logger.info("Downloading %s of %s data for %d symbols...", period, interval, len(self.symbols))
        try:
            df = self.provider.download(
                symbols=self.symbols,
                period=period,
                interval=interval
            )
            logger.info("Downloaded data shape: %s", df.shape)
            return df
        except Exception as e:
            logger.error("Failed to download data: %s", e)
            return None
    
    def extract_symbol_data(self, df, symbol):
        """Extract data for a specific symbol."""
        try:
            # Try MultiIndex format
            if isinstance(df.columns, pd.MultiIndex):
                try:
                    symbol_df = df.xs(symbol, level=1, axis=1)
                    return symbol_df
                except Exception:
                    pass
            
            # Try string tuple format
            symbol_cols = []
            for col in df.columns:
                if isinstance(col, str) and symbol in col:
                    symbol_cols.append(col)
                elif isinstance(col, tuple) and symbol in col:
                    symbol_cols.append(col)
            
            if symbol_cols:
                symbol_df = df[symbol_cols].copy()
                # Standardize column names
                new_cols = []
                for col in symbol_df.columns:
                    if isinstance(col, str):
                        if 'Open' in col or "'Open'" in col:
                            new_cols.append('Open')
                        elif 'High' in col or "'High'" in col:
                            new_cols.append('High')
                        elif 'Low' in col or "'Low'" in col:
                            new_cols.append('Low')
                        elif 'Close' in col or "'Close'" in col:
                            new_cols.append('Close')
                        elif 'Volume' in col or "'Volume'" in col:
                            new_cols.append('Volume')
                    elif isinstance(col, tuple):
                        new_cols.append(col[0])
                
                symbol_df.columns = new_cols[:len(symbol_df.columns)]
                return symbol_df[['Open', 'High', 'Low', 'Close', 'Volume']]
        except Exception as e:
            logger.debug("Error extracting %s: %s", symbol, e)
        
        return None
    
    def backtest_rsi_strategy(self, df):
        """Backtest RSI mean reversion strategy."""
        strategy_name = 'RSI Mean Reversion'
        logger.info("\nBacktesting: %s", strategy_name)
        
        total_trades = 0
        winning_trades = 0
        total_pnl = 0.0
        
        for symbol in self.symbols:
            try:
                symbol_df = self.extract_symbol_data(df, symbol)
                if symbol_df is None or len(symbol_df) < 50:
                    continue
                
                # Generate RSI signals
                signals = self._generate_rsi_signals(symbol_df.copy())
                if signals is None or signals.empty or 'signal' not in signals.columns:
                    continue
                
                # Simple backtest
                signal_vals = signals['signal'].values
                closes = symbol_df['Close'].values
                
                entry_price = None
                for i in range(len(signal_vals)):
                    if signal_vals[i] == 1 and entry_price is None:
                        entry_price = float(closes[i])
                    elif signal_vals[i] == 0 and entry_price is not None and i > 0:
                        exit_price = float(closes[i])
                        pnl = (exit_price - entry_price) / entry_price
                        total_pnl += pnl
                        total_trades += 1
                        if pnl > 0:
                            winning_trades += 1
                        entry_price = None
            
            except Exception as e:
                logger.debug("Error testing %s: %s", symbol, e)
                continue
        
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        avg_pnl = (total_pnl / total_trades) if total_trades > 0 else 0
        
        result = {
            'strategy': strategy_name,
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'win_rate': win_rate,
            'total_pnl_pct': total_pnl * 100,
            'avg_pnl_pct': avg_pnl * 100
        }
        
        logger.info("  Total Trades: %d", total_trades)
        logger.info("  Win Rate: %.1f%%", win_rate)
        logger.info("  Total P&L: %.2f%%", total_pnl * 100)
        logger.info("  Avg P&L: %.2f%%", avg_pnl * 100)
        
        return result
    
    def backtest_macd_strategy(self, df):
        """Backtest MACD trend following strategy."""
        strategy_name = 'MACD Trend Following'
        logger.info("\nBacktesting: %s", strategy_name)
        
        total_trades = 0
        winning_trades = 0
        total_pnl = 0.0
        
        for symbol in self.symbols:
            try:
                symbol_df = self.extract_symbol_data(df, symbol)
                if symbol_df is None or len(symbol_df) < 50:
                    continue
                
                # Generate MACD signals
                signals = self._generate_macd_signals(symbol_df.copy())
                if signals is None or signals.empty or 'signal' not in signals.columns:
                    continue
                
                # Simple backtest
                signal_vals = signals['signal'].values
                closes = symbol_df['Close'].values
                
                entry_price = None
                for i in range(len(signal_vals)):
                    if signal_vals[i] == 1 and entry_price is None:
                        entry_price = float(closes[i])
                    elif signal_vals[i] == -1 and entry_price is not None:
                        exit_price = float(closes[i])
                        pnl = (exit_price - entry_price) / entry_price
                        total_pnl += pnl
                        total_trades += 1
                        if pnl > 0:
                            winning_trades += 1
                        entry_price = None
            
            except Exception as e:
                logger.debug("Error testing %s: %s", symbol, e)
                continue
        
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        avg_pnl = (total_pnl / total_trades) if total_trades > 0 else 0
        
        result = {
            'strategy': strategy_name,
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'win_rate': win_rate,
            'total_pnl_pct': total_pnl * 100,
            'avg_pnl_pct': avg_pnl * 100
        }
        
        logger.info("  Total Trades: %d", total_trades)
        logger.info("  Win Rate: %.1f%%", win_rate)
        logger.info("  Total P&L: %.2f%%", total_pnl * 100)
        logger.info("  Avg P&L: %.2f%%", avg_pnl * 100)
        
        return result
    
    def _generate_rsi_signals(self, df):
        """Generate RSI-based signals."""
        try:
            from trading_bot.indicators import calculate_rsi
            
            if 'Close' not in df.columns:
                return None
            
            rsi = calculate_rsi(df['Close'].values, period=14)
            if rsi is None or len(rsi) == 0:
                return None
            
            signals = []
            for i in range(len(rsi)):
                if i == 0:
                    signals.append(0)
                elif rsi[i] < 30 and rsi[i-1] >= 30:
                    signals.append(1)
                elif rsi[i] > 70:
                    signals.append(-1)
                else:
                    signals.append(0)
            
            return pd.DataFrame({
                'rsi': rsi,
                'signal': signals
            }, index=df.index)
        except Exception as e:
            logger.debug("RSI signal generation failed: %s", e)
            return None
    
    def _generate_macd_signals(self, df):
        """Generate MACD-based signals."""
        try:
            from trading_bot.indicators import calculate_macd
            
            if 'Close' not in df.columns:
                return None
            
            macd_result = calculate_macd(df['Close'].values)
            if macd_result is None:
                return None
            
            macd_line, signal_line, histogram = macd_result
            if len(macd_line) == 0 or len(histogram) == 0:
                return None
            
            signals = []
            for i in range(len(histogram)):
                if i == 0:
                    signals.append(0)
                elif histogram[i] > 0 and histogram[i-1] <= 0:
                    signals.append(1)
                elif histogram[i] < 0 and histogram[i-1] >= 0:
                    signals.append(-1)
                else:
                    signals.append(0)
            
            return pd.DataFrame({
                'macd': macd_line,
                'signal_line': signal_line,
                'histogram': histogram,
                'signal': signals
            }, index=df.index[:len(signals)])
        except Exception as e:
            logger.debug("MACD signal generation failed: %s", e)
            return None
    
    def print_comparison(self):
        """Print strategy comparison."""
        logger.info("\n" + "="*80)
        logger.info("BACKTEST RESULTS COMPARISON")
        logger.info("="*80)
        
        if not self.results:
            logger.warning("No results to compare")
            return
        
        sorted_results = sorted(
            self.results.values(),
            key=lambda x: x.get('win_rate', 0),
            reverse=True
        )
        
        logger.info("\nRanking (by Win Rate):\n")
        for rank, result in enumerate(sorted_results, 1):
            logger.info("%d. %s", rank, result['strategy'])
            logger.info("   Trades: %d | Wins: %d | Win Rate: %.1f%%",
                       result['total_trades'], result['winning_trades'], result['win_rate'])
            logger.info("   Total P&L: %+.2f%% | Avg P&L: %+.2f%%",
                       result['total_pnl_pct'], result['avg_pnl_pct'])
            logger.info("")
    
    def save_results(self, filename='backtest_results.json'):
        """Save backtest results to JSON."""
        try:
            output_path = Path(filename)
            with open(str(output_path), 'w') as f:
                json.dump(self.results, f, indent=2, default=str)
            logger.info("\nResults saved to %s", output_path)
        except Exception as e:
            logger.error("Failed to save results: %s", e)
    
    def run(self):
        """Run all backtests."""
        logger.info("\n" + "="*80)
        logger.info("LIVE BACKTEST VALIDATOR - Starting background backtests")
        logger.info("Bot continues trading live while this runs")
        logger.info("="*80 + "\n")
        
        df = self.download_historical_data(period='90d', interval='1d')
        if df is None:
            logger.error("Failed to download data - aborting backtest")
            return
        
        logger.info("\nTesting RSI Mean Reversion Strategy...")
        self.results['rsi'] = self.backtest_rsi_strategy(df)
        
        logger.info("\nTesting MACD Trend Following Strategy...")
        self.results['macd'] = self.backtest_macd_strategy(df)
        
        self.print_comparison()
        self.save_results()
        
        logger.info("\n" + "="*80)
        logger.info("BACKTEST COMPLETE - Bot continues trading uninterrupted")
        logger.info("="*80 + "\n")


def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )
    
    try:
        config_path = Path('configs/default.yaml')
        validator = LiveBacktestValidator(str(config_path))
        validator.run()
    except Exception as e:
        logger.error("Backtest validator failed: %s", e, exc_info=True)
        raise


if __name__ == '__main__':
    main()
