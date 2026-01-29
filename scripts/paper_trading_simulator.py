"""
Paper Trading Simulator
Test Gen 364 strategy on live market data without real capital
Tracks entry/exit signals, P&L, and compares to backtest predictions
"""
import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any
import numpy as np
import yaml

class PaperTradingSimulator:
    """Simulates paper trading with live market updates"""
    
    def __init__(self, strategy_config_file='config/evolved_strategy_gen364.yaml', 
                 initial_capital=100000):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions = {}  # symbol -> {shares, entry_price, entry_date, entry_signal}
        self.trades = []  # Closed trades
        self.equity_curve = [initial_capital]
        self.dates = []
        self.start_time = datetime.now()
        
        # Load strategy parameters
        self.strategy = self._load_strategy(strategy_config_file)
        self.paper_trading_dir = Path('logs/paper_trading')
        self.paper_trading_dir.mkdir(parents=True, exist_ok=True)
    
    def _load_strategy(self, config_file: str) -> Dict:
        """Load strategy configuration"""
        try:
            with open(config_file, 'r') as f:
                config = yaml.safe_load(f)
                # Ensure all required keys exist
                defaults = {
                    'entry_threshold': 0.7756,
                    'profit_target': 0.1287,
                    'stop_loss': 0.0927,
                    'position_size_pct': 0.05,
                    'max_position_pct': 0.1774,
                    'momentum_weight': 0.2172,
                    'rsi_weight': 0.1000,
                    'name': 'Gen 364 (Loaded)',
                    'max_positions': 20,
                    'backtest_return': 7.32
                }
                defaults.update(config or {})
                return defaults
        except:
            # Return Gen 364 defaults
            return {
                'entry_threshold': 0.7756,
                'profit_target': 0.1287,
                'stop_loss': 0.0927,
                'position_size_pct': 0.05,
                'max_position_pct': 0.1774,
                'momentum_weight': 0.2172,
                'rsi_weight': 0.1000,
                'name': 'Gen 364 (Default)',
                'max_positions': 20,
                'backtest_return': 7.32
            }
    
    def load_market_data(self, db_path='data/real_market_data.db'):
        """Load latest market data from database"""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all symbols
        cursor.execute("SELECT DISTINCT symbol FROM daily_prices ORDER BY symbol")
        symbols = [row[0] for row in cursor.fetchall()]
        
        data = {}
        for symbol in symbols:
            cursor.execute("""
                SELECT date, open, high, low, close, volume 
                FROM daily_prices 
                WHERE symbol = ? 
                ORDER BY date DESC LIMIT 100
            """, (symbol,))
            rows = cursor.fetchall()
            if rows:
                data[symbol] = list(reversed(rows))
        
        conn.close()
        return data, symbols
    
    def calculate_rsi(self, prices, period=14):
        """Calculate RSI"""
        if len(prices) < period:
            return 50
        
        deltas = np.diff(prices[-period-1:])
        seed = deltas[:period]
        up = seed[seed >= 0].sum() / period
        down = -seed[seed < 0].sum() / period
        
        rs = up / down if down else 0
        return 100 - 100 / (1 + rs) if rs > 0 else 50
    
    def calculate_momentum(self, prices, period=10):
        """Calculate momentum"""
        if len(prices) < period:
            return 0
        return ((prices[-1] - prices[-period-1]) / prices[-period-1]) * 100
    
    def calculate_ml_score(self, symbol_data):
        """Calculate trading signal"""
        if len(symbol_data) < 20:
            return 0
        
        prices = [x[4] for x in symbol_data]
        
        rsi = self.calculate_rsi(prices)
        momentum = self.calculate_momentum(prices)
        
        # Combine signals
        momentum_signal = max(0, min(1, (momentum + 50) / 100))
        rsi_signal = 1 - (rsi / 100)
        
        ml_score = (self.strategy['momentum_weight'] * momentum_signal + 
                   self.strategy['rsi_weight'] * rsi_signal)
        
        return ml_score
    
    def check_exits(self, current_prices):
        """Check if any positions should exit"""
        closes = []
        
        for symbol in list(self.positions.keys()):
            entry_price = self.positions[symbol]['entry_price']
            current_price = current_prices.get(symbol, entry_price)
            
            ret = (current_price - entry_price) / entry_price
            
            # Exit on targets
            if ret >= self.strategy['profit_target'] or ret <= -self.strategy['stop_loss']:
                profit = self.positions[symbol]['shares'] * (current_price - entry_price)
                self.cash += self.positions[symbol]['shares'] * current_price
                
                closes.append({
                    'symbol': symbol,
                    'entry_price': entry_price,
                    'exit_price': current_price,
                    'entry_date': self.positions[symbol]['entry_date'],
                    'exit_date': datetime.now().date(),
                    'shares': self.positions[symbol]['shares'],
                    'return': ret,
                    'profit': profit,
                    'reason': 'profit_target' if ret > 0 else 'stop_loss'
                })
                
                del self.positions[symbol]
        
        self.trades.extend(closes)
        return closes
    
    def check_entries(self, market_data, current_prices):
        """Check for entry signals"""
        entries = []
        
        if len(self.positions) >= self.strategy.get('max_positions', 20):
            return entries
        
        for symbol in market_data:
            if symbol not in self.positions and self.cash > 0:
                symbol_data = market_data[symbol]
                
                if len(symbol_data) >= 20:
                    ml_score = self.calculate_ml_score(symbol_data)
                    current_price = current_prices.get(symbol, symbol_data[-1][4])
                    
                    if ml_score >= self.strategy['entry_threshold']:
                        # Entry
                        shares = int((self.cash * self.strategy['position_size_pct']) / current_price)
                        
                        if shares > 0:
                            cost = shares * current_price
                            
                            if cost <= self.cash:
                                self.cash -= cost
                                self.positions[symbol] = {
                                    'shares': shares,
                                    'entry_price': current_price,
                                    'entry_date': datetime.now().date(),
                                    'ml_score': ml_score
                                }
                                
                                entries.append({
                                    'symbol': symbol,
                                    'price': current_price,
                                    'shares': shares,
                                    'ml_score': ml_score,
                                    'timestamp': datetime.now()
                                })
        
        return entries
    
    def update_equity(self, current_prices):
        """Calculate current portfolio value"""
        total_equity = self.cash
        
        for symbol in self.positions:
            current_price = current_prices.get(symbol, self.positions[symbol]['entry_price'])
            total_equity += self.positions[symbol]['shares'] * current_price
        
        self.equity_curve.append(total_equity)
        return total_equity
    
    def get_performance_stats(self):
        """Calculate performance metrics"""
        if len(self.equity_curve) < 2:
            return {}
        
        equity = np.array(self.equity_curve)
        returns = np.diff(equity) / equity[:-1]
        
        total_return = (equity[-1] - self.initial_capital) / self.initial_capital
        
        # Drawdown
        peak = np.maximum.accumulate(equity)
        drawdown = (equity - peak) / peak
        max_drawdown = np.min(drawdown)
        
        # Sharpe
        sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0
        
        # Win rate
        wins = sum(1 for t in self.trades if t['profit'] > 0)
        total_trades = len(self.trades)
        
        return {
            'total_return_pct': total_return * 100,
            'current_equity': equity[-1],
            'total_profit': equity[-1] - self.initial_capital,
            'trades_executed': total_trades,
            'winning_trades': wins,
            'win_rate_pct': (wins / total_trades * 100) if total_trades > 0 else 0,
            'sharpe_ratio': sharpe,
            'max_drawdown_pct': max_drawdown * 100,
            'current_positions': len(self.positions),
            'cash_available': self.cash
        }
    
    def save_journal(self):
        """Save paper trading journal"""
        journal = {
            'strategy': self.strategy,
            'performance': self.get_performance_stats(),
            'trades': self.trades,
            'started_at': self.start_time.isoformat(),
            'last_update': datetime.now().isoformat(),
            'current_positions': [
                {
                    'symbol': s,
                    'shares': self.positions[s]['shares'],
                    'entry_price': self.positions[s]['entry_price'],
                    'entry_date': self.positions[s]['entry_date'].isoformat(),
                    'current_unrealized_pnl': 'See live prices'
                }
                for s in self.positions
            ]
        }
        
        filename = f"paper_trading_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(self.paper_trading_dir / filename, 'w') as f:
            json.dump(journal, f, indent=2, default=str)
        
        return filename
    
    def generate_report(self):
        """Generate paper trading report"""
        stats = self.get_performance_stats()
        
        report = f"""
{'='*80}
PAPER TRADING REPORT - Gen 364 Strategy
{'='*80}

Session Started: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}
Current Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Duration: {datetime.now() - self.start_time}

{'='*80}
PERFORMANCE METRICS
{'='*80}

Starting Capital:        ${self.initial_capital:>12,.2f}
Current Equity:          ${stats.get('current_equity', 0):>12,.2f}
Total Profit/Loss:       ${stats.get('total_profit', 0):>12,.2f}
Total Return:            {stats.get('total_return_pct', 0):>12.2f}%

{'='*80}
TRADING STATISTICS
{'='*80}

Total Trades Executed:   {stats.get('trades_executed', 0):>12}
Winning Trades:          {stats.get('winning_trades', 0):>12}
Losing Trades:           {stats.get('trades_executed', 0) - stats.get('winning_trades', 0):>12}
Win Rate:                {stats.get('win_rate_pct', 0):>12.2f}%

{'='*80}
RISK METRICS
{'='*80}

Sharpe Ratio (ann):      {stats.get('sharpe_ratio', 0):>12.2f}
Max Drawdown:            {stats.get('max_drawdown_pct', 0):>12.2f}%
Current Positions:       {stats.get('current_positions', 0):>12}
Cash Available:          ${stats.get('cash_available', 0):>12,.2f}

{'='*80}
STRATEGY PARAMETERS
{'='*80}

Entry Threshold:         {self.strategy['entry_threshold']:>12.4f}
Profit Target:           {self.strategy['profit_target'] * 100:>12.2f}%
Stop Loss:               {self.strategy['stop_loss'] * 100:>12.2f}%
Position Size:           {self.strategy['position_size_pct'] * 100:>12.2f}%

{'='*80}
COMPARISON TO BACKTEST
{'='*80}

Backtest Expected Return: {self.strategy.get('backtest_return', 7.32):>12.2f}%
Actual Return:            {stats.get('total_return_pct', 0):>12.2f}%
Variance:                 {stats.get('total_return_pct', 0) - self.strategy.get('backtest_return', 7.32):>12.2f}pp

Status: {'✓ ON TRACK' if abs(stats.get('total_return_pct', 0) - self.strategy.get('backtest_return', 7.32)) < 5 else '⚠ DIVERGING'}

{'='*80}
RECENT TRADES (Last 5)
{'='*80}
"""
        
        for i, trade in enumerate(self.trades[-5:], 1):
            report += f"""
Trade {i}: {trade['symbol']}
  Entry:  ${trade['entry_price']:.2f} on {trade['entry_date']}
  Exit:   ${trade['exit_price']:.2f} on {trade['exit_date']}
  Return: {trade['return']*100:>6.2f}%  Profit: ${trade['profit']:>10,.2f}  ({trade['reason']})
"""
        
        report += f"\n{'='*80}\n"
        
        return report

def main():
    """Test paper trading system"""
    print("\n" + "="*80)
    print("PAPER TRADING SIMULATOR - Gen 364 Strategy")
    print("="*80)
    
    simulator = PaperTradingSimulator()
    
    print(f"\n✓ Simulator initialized")
    print(f"  Strategy: {simulator.strategy.get('name', 'Gen 364')}")
    print(f"  Initial Capital: ${simulator.initial_capital:,.2f}")
    
    # Load market data
    print("\nLoading market data...")
    market_data, symbols = simulator.load_market_data()
    print(f"✓ Loaded {len(symbols)} symbols")
    
    # Simulate a trading day
    print("\nSimulating trading activity...")
    
    # Use latest prices as current
    current_prices = {symbol: market_data[symbol][-1][4] if market_data.get(symbol) else 0 
                     for symbol in symbols}
    
    # Check entries
    entries = simulator.check_entries(market_data, current_prices)
    print(f"✓ Entry signals: {len(entries)} positions")
    
    # Check exits
    exits = simulator.check_exits(current_prices)
    print(f"✓ Exit signals: {len(exits)} closed trades")
    
    # Update equity
    equity = simulator.update_equity(current_prices)
    print(f"✓ Current equity: ${equity:,.2f}")
    
    # Save journal
    journal_file = simulator.save_journal()
    print(f"✓ Journal saved: {journal_file}")
    
    # Generate report
    report = simulator.generate_report()
    print(report)
    
    print("="*80)
    print("Paper trading ready! Monitor daily for 2+ weeks before going live.")
    print("="*80)

if __name__ == '__main__':
    main()
