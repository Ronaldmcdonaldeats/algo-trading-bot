"""
Phase 7 Extended Backtest - 50 Top NASDAQ Stocks

Tests the full recommended universe (50 stocks) to demonstrate scalability
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.phase7_multistock_backtest import MultiStockBacktester

def main():
    """Run backtest on 50 top NASDAQ stocks"""
    # Test on top 50 NASDAQ stocks
    backtester = MultiStockBacktester(universe_size=50)
    
    # Run backtest
    backtester.run_backtest(verbose=True)
    
    # Analyze results
    backtester.print_results_summary()

if __name__ == '__main__':
    main()
