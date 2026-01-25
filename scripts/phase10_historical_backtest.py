"""
Phase 10 Historical Backtest
- Run optimized Phase 10 strategy on full 2000-2025 period
- Compare with Phase 9 and S&P 500 benchmark
- Target: 6.1% annual return (5% above S&P 500)
"""

import os
import sys
import logging
import json
import numpy as np
import pandas as pd

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))

from src.trading_bot.historical_data import fetch_stock_data
from src.trading_bot.phase10_optimizer_strategy import (
    Phase10Backtester, Phase10Strategy, PhasePhase10Config
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Phase10HistoricalBacktest:
    """Full historical backtest of Phase 10 optimized strategy"""
    
    STOCKS = [
        'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META', 'NFLX',
        'ADBE', 'INTC', 'AMD', 'CSCO', 'QCOM', 'COST', 'AVGO', 'TMUS',
        'CMCSA', 'INTU', 'VRTX', 'AEP', 'LRCX', 'SNPS', 'CDNS', 'PCAR',
        'PAYX', 'ABNB', 'PANW', 'CRWD', 'ZM', 'DXCM', 'WDAY', 'FAST',
        'CPRT', 'CHKP'
    ]
    
    def __init__(self, config: PhasePhase10Config = None):
        self.config = config or PhasePhase10Config()
        self.results = []
        self.phase8_results = {}
        self.phase9_results = {}
    
    def load_phase8_results(self) -> dict:
        """Load Phase 8 results for comparison"""
        try:
            path = 'phase8_results/phase8_results.csv'
            if os.path.exists(path):
                df = pd.read_csv(path)
                return {row['Symbol']: row['Annual_Return'] 
                        for _, row in df.iterrows()}
        except Exception as e:
            logger.warning(f"Could not load Phase 8 results: {e}")
        return {}
    
    def load_phase9_results(self) -> dict:
        """Load Phase 9 results for comparison"""
        try:
            path = 'phase9_results/phase9_results.csv'
            if os.path.exists(path):
                df = pd.read_csv(path)
                return {row['Symbol']: row['Annual_Return']
                        for _, row in df.iterrows()}
        except Exception as e:
            logger.warning(f"Could not load Phase 9 results: {e}")
        return {}
    
    def run_backtest(self):
        """Run Phase 10 backtest on all stocks"""
        logger.info("Starting Phase 10 Historical Backtest (2000-2025)...")
        logger.info(f"Testing {len(self.STOCKS)} stocks with config:")
        logger.info(f"  SMA: {self.config.sma_fast}/{self.config.sma_slow}")
        logger.info(f"  RSI: {self.config.rsi_oversold}/{self.config.rsi_overbought}")
        logger.info(f"  MA Window: {self.config.ma_window}")
        logger.info("")
        
        backtester = Phase10Backtester(self.config)
        
        # Load comparison data
        self.phase8_results = self.load_phase8_results()
        self.phase9_results = self.load_phase9_results()
        
        # Fetch S&P 500 benchmark
        logger.info("Fetching S&P 500 benchmark...")
        benchmark_df = fetch_stock_data('^GSPC', start_date='2000-01-01', end_date='2025-01-25')
        if benchmark_df is not None and len(benchmark_df) > 100:
            prices = benchmark_df['Close'].values
            total_ret, annual_ret, max_dd, sharpe, trades = backtester.backtest(prices)
            logger.info(f"S&P 500: {annual_ret:.2%} annual, {total_ret:.1%} total")
            benchmark_annual = annual_ret
        else:
            benchmark_annual = 0.011
            logger.warning(f"Using default S&P 500 estimate: {benchmark_annual:.2%}")
        
        logger.info("")
        logger.info(f"[Phase 10] Testing stocks...")
        
        # Test all stocks
        tested_stocks = 0
        for i, symbol in enumerate(self.STOCKS, 1):
            try:
                df = fetch_stock_data(symbol, start_date='2000-01-01', end_date='2025-01-25')
                if df is None or len(df) < 100:
                    logger.info(f"[{i}/{len(self.STOCKS)}] {symbol}: No data found")
                    continue
                
                prices = df['Close'].values
                total_ret, annual_ret, max_dd, sharpe, trades = backtester.backtest(prices)
                
                result = {
                    'Symbol': symbol,
                    'Total_Return': total_ret,
                    'Annual_Return': annual_ret,
                    'Max_Drawdown': max_dd,
                    'Sharpe_Ratio': sharpe,
                    'Trades': trades,
                }
                
                # Add comparison columns
                if symbol in self.phase8_results:
                    result['Phase8_Annual'] = self.phase8_results[symbol]
                    result['P10_vs_P8'] = annual_ret - self.phase8_results[symbol]
                
                if symbol in self.phase9_results:
                    result['Phase9_Annual'] = self.phase9_results[symbol]
                    result['P10_vs_P9'] = annual_ret - self.phase9_results[symbol]
                
                result['vs_SPY'] = annual_ret - benchmark_annual
                
                self.results.append(result)
                tested_stocks += 1
                
                logger.info(
                    f"[{i}/{len(self.STOCKS)}] {symbol}: {annual_ret:7.2%} annual "
                    f"({total_ret:7.1%} total, DD: {max_dd:6.2%}, Sharpe: {sharpe:6.3f})"
                )
            
            except Exception as e:
                logger.error(f"[{i}/{len(self.STOCKS)}] {symbol}: Error - {e}")
        
        logger.info(f"\nSuccessfully tested {tested_stocks} stocks")
        return tested_stocks
    
    def generate_report(self, benchmark_annual: float = 0.011):
        """Generate comparison report"""
        if not self.results:
            logger.warning("No results to report")
            return ""
        
        df = pd.DataFrame(self.results)
        
        report = "\n" + "="*90 + "\n"
        report += "PHASE 10: BAYESIAN OPTIMIZED STRATEGY\n"
        report += "FULL HISTORICAL BACKTEST 2000-2025 WITH PHASE 8/9 COMPARISON\n"
        report += "="*90 + "\n"
        report += f"Generated: {pd.Timestamp.now()}\n"
        report += f"Period: 2000-01-01 to 2025-01-25\n\n"
        
        # Summary stats
        report += "PHASE 10 RESULTS:\n"
        report += "-"*90 + "\n"
        report += f"Stocks Tested:         {len(df)}\n"
        report += f"Avg Total Return:      {df['Total_Return'].mean():7.1%}\n"
        report += f"Avg Annual Return:     {df['Annual_Return'].mean():7.2%}\n"
        report += f"Median Annual:         {df['Annual_Return'].median():7.2%}\n"
        report += f"Best Stock:            {df.loc[df['Annual_Return'].idxmax(), 'Symbol']}\n"
        report += f"Best Return:           {df['Annual_Return'].max():7.2%}\n"
        report += f"Worst Return:          {df['Annual_Return'].min():7.2%}\n\n"
        
        report += f"S&P 500 BENCHMARK:     {benchmark_annual:7.2%}\n"
        report += f"Outperformance:        {df['Annual_Return'].mean() - benchmark_annual:+7.2%}\n"
        beats_spy = (df['Annual_Return'] > benchmark_annual).sum()
        report += f"Stocks Beating S&P 500: {beats_spy}/{len(df)} ({beats_spy/len(df)*100:.0f}%)\n\n"
        
        # Phase 10 vs Phase 9
        if 'Phase9_Annual' in df.columns:
            improved = (df['P10_vs_P9'] > 0).sum()
            report += "PHASE 10 vs PHASE 9 COMPARISON:\n"
            report += "-"*90 + "\n"
            report += f"Improved (P10 > P9):   {improved}/{len(df.dropna(subset=['Phase9_Annual']))} "
            report += f"({improved/len(df.dropna(subset=['Phase9_Annual']))*100:.0f}%)\n"
            report += f"Avg Improvement:       {df['P10_vs_P9'].mean():+7.2%}\n"
            report += f"Median Improvement:    {df['P10_vs_P9'].median():+7.2%}\n"
            report += f"Best Improvement:      {df['P10_vs_P9'].max():+7.2%}\n"
            report += f"Worst Regression:      {df['P10_vs_P9'].min():+7.2%}\n\n"
        
        # Top performers
        report += "TOP 10 PHASE 10 PERFORMERS:\n"
        report += "-"*90 + "\n"
        top10 = df.nlargest(10, 'Annual_Return')
        for idx, (_, row) in enumerate(top10.iterrows(), 1):
            report += f"{idx:2d}. {row['Symbol']:6s} Annual: {row['Annual_Return']:7.2%}  "
            report += f"Total: {row['Total_Return']:8.1%}  DD: {row['Max_Drawdown']:6.2%}  "
            report += f"Sharpe: {row['Sharpe_Ratio']:6.3f}\n"
        
        report += "\n" + "="*90 + "\n"
        
        return report
    
    def save_results(self):
        """Save results to CSV and report"""
        os.makedirs('phase10_results', exist_ok=True)
        
        if self.results:
            df = pd.DataFrame(self.results)
            
            # Save CSV
            csv_path = 'phase10_results/phase10_results.csv'
            df.to_csv(csv_path, index=False)
            logger.info(f"Saved Phase 10 results to {csv_path}")
            
            # Save report
            report = self.generate_report()
            report_path = 'phase10_results/PHASE10_RESULTS.txt'
            try:
                with open(report_path, 'w', encoding='utf-8') as f:
                    f.write(report)
                logger.info(f"Saved report to {report_path}")
            except Exception as e:
                logger.warning(f"Could not save report with UTF-8: {e}")
                with open(report_path, 'w') as f:
                    f.write(report.encode('utf-8', errors='ignore').decode('utf-8'))
            
            print(report)


def load_best_config(config_path: str = 'phase10_results/phase10_best_config.json') -> PhasePhase10Config:
    """Load best config from optimization"""
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                params = json.load(f)
            
            logger.info(f"Loaded best config from {config_path}")
            logger.info(f"  SMA: {params['sma_fast']}/{params['sma_slow']}")
            logger.info(f"  RSI: {params['rsi_oversold']}/{params['rsi_overbought']}")
            logger.info(f"  MA Window: {params['ma_window']}")
            
            config = PhasePhase10Config(
                sma_fast=params['sma_fast'],
                sma_slow=params['sma_slow'],
                rsi_oversold=params['rsi_oversold'],
                rsi_overbought=params['rsi_overbought'],
                ma_window=params['ma_window'],
            )
            return config
        except Exception as e:
            logger.warning(f"Could not load best config: {e}")
    
    logger.info("Using default Phase 10 config")
    return PhasePhase10Config()


if __name__ == '__main__':
    # Load best config from optimization
    config = load_best_config()
    
    # Run backtest
    backtest = Phase10HistoricalBacktest(config)
    backtest.run_backtest()
    backtest.save_results()
