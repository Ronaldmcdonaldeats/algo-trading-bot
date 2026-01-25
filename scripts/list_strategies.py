#!/usr/bin/env python3
"""
List and test available strategies
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.strategies import StrategyFactory


def main():
    print("\n" + "="*70)
    print("AVAILABLE STRATEGIES")
    print("="*70 + "\n")
    
    for info in StrategyFactory.list_all_info().values():
        print(f"Name: {info['name']}")
        print(f"  Class: {info['class']}")
        print(f"  Description: {info['description']}")
        print()
    
    print("="*70)
    print("HOW TO USE")
    print("="*70)
    print("""
1. Edit strategy_config.yaml and change the 'strategy' field to your choice
2. Run: python scripts/multi_strategy_backtest.py
3. Results will be saved in 'results_<strategy_name>/' directory

Example:
  - Change 'strategy: ultra_ensemble' to 'strategy: trend_following'
  - Run backtest
  - Compare results!
""")


if __name__ == '__main__':
    main()
