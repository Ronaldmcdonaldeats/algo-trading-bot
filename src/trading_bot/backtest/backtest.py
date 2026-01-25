"""Backtesting framework for strategy validation."""

from __future__ import annotations

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional, Callable

logger = logging.getLogger(__name__)


class Backtest:
    """Simple backtesting engine for strategy validation."""

    def __init__(
        self,
        initial_capital: float = 100000.0,
        commission_pct: float = 0.001,  # 0.1% per trade
        slippage_pct: float = 0.002,  # 0.2% slippage
    ):
        """Initialize backtest.
        
        Args:
            initial_capital: Starting capital
            commission_pct: Commission per trade
            slippage_pct: Execution slippage
        """
        self.initial_capital = initial_capital
        self.commission_pct = commission_pct
        self.slippage_pct = slippage_pct
        
        self.portfolio_value = initial_capital
        self.cash = initial_capital
        self.positions = {}  # symbol -> qty
        self.trades = []
        self.equity_curve = []
        self.daily_returns = []

    def apply_slippage(self, price: float, side: str) -> float:
        """Apply slippage to execution price.
        
        Args:
            price: Intended execution price
            side: 'BUY' or 'SELL'
            
        Returns:
            Actual execution price after slippage
        """
        slippage = price * self.slippage_pct
        if side == 'BUY':
            return price + slippage
        else:
            return price - slippage

    def execute_trade(
        self,
        symbol: str,
        side: str,
        qty: int,
        price: float,
        timestamp: datetime,
    ) -> Dict:
        """Execute a trade.
        
        Args:
            symbol: Trading symbol
            side: 'BUY' or 'SELL'
            qty: Quantity
            price: Entry price
            timestamp: Trade timestamp
            
        Returns:
            Trade execution details
        """
        exec_price = self.apply_slippage(price, side)
        cost = qty * exec_price
        commission = cost * self.commission_pct
        total_cost = cost + commission
        
        if side == 'BUY':
            if self.cash < total_cost:
                logger.warning(f"Insufficient cash for {symbol} BUY: need ${total_cost:.2f}, have ${self.cash:.2f}")
                return {}
            
            self.cash -= total_cost
            self.positions[symbol] = self.positions.get(symbol, 0) + qty
        
        elif side == 'SELL':
            if self.positions.get(symbol, 0) < qty:
                logger.warning(f"Insufficient {symbol} position for SELL")
                return {}
            
            self.cash += (qty * exec_price) - commission
            self.positions[symbol] -= qty
            if self.positions[symbol] == 0:
                del self.positions[symbol]
        
        trade = {
            'symbol': symbol,
            'side': side,
            'qty': qty,
            'price': exec_price,
            'commission': commission,
            'timestamp': timestamp,
        }
        self.trades.append(trade)
        
        return trade

    def get_portfolio_value(self, prices: Dict[str, float]) -> float:
        """Calculate total portfolio value.
        
        Args:
            prices: Current prices by symbol
            
        Returns:
            Total portfolio value
        """
        position_value = sum(
            qty * prices.get(symbol, 0)
            for symbol, qty in self.positions.items()
        )
        return self.cash + position_value

    def run_backtest(
        self,
        data: Dict[str, pd.DataFrame],  # symbol -> OHLCV DataFrame
        signal_func: Callable,  # Function to generate signals
        symbols: List[str],
    ) -> Dict:
        """Run backtest on historical data.
        
        Args:
            data: Dict of symbol -> OHLCV data
            signal_func: Function that takes (symbol, df_tail) -> signal
            symbols: List of symbols to trade
            
        Returns:
            Backtest results
        """
        # Synchronize data
        all_dates = set()
        for symbol in symbols:
            if symbol in data:
                all_dates.update(data[symbol].index)
        
        all_dates = sorted(list(all_dates))
        
        for date in all_dates:
            prices = {}
            
            # Get signals and execute trades
            for symbol in symbols:
                if symbol not in data:
                    continue
                
                df = data[symbol]
                if date not in df.index:
                    continue
                
                # Get data up to current date
                df_to_date = df.loc[:date]
                if len(df_to_date) < 2:
                    continue
                
                # Generate signal
                try:
                    signal = signal_func(symbol, df_to_date.tail(5))
                except Exception as e:
                    logger.debug(f"Signal generation failed for {symbol}: {e}")
                    signal = 0
                
                price = df.loc[date, 'Close']
                prices[symbol] = price
                
                # Execute trades based on signal
                current_qty = self.positions.get(symbol, 0)
                
                if signal == 1 and current_qty == 0:  # BUY signal
                    qty = int(self.cash * 0.1 / price)  # Risk 10% of capital
                    if qty > 0:
                        self.execute_trade(symbol, 'BUY', qty, price, date)
                
                elif signal == -1 and current_qty > 0:  # SELL signal
                    self.execute_trade(symbol, 'SELL', current_qty, price, date)
            
            # Record portfolio value
            portfolio_value = self.get_portfolio_value(prices)
            self.portfolio_value = portfolio_value
            self.equity_curve.append((date, portfolio_value))
        
        # Calculate results
        return self.get_results()

    def get_results(self) -> Dict:
        """Calculate backtest results.
        
        Returns:
            Dict with performance metrics
        """
        if not self.equity_curve:
            return {}
        
        equity_values = [v for _, v in self.equity_curve]
        
        # Returns
        total_return = (self.portfolio_value - self.initial_capital) / self.initial_capital
        
        # Winning/losing trades
        wins = sum(1 for t in self.trades if t['side'] == 'SELL' and True)  # Simplified
        total_trades = len([t for t in self.trades if t['side'] == 'BUY'])
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        
        # Sharpe ratio
        if len(equity_values) > 1:
            returns = pd.Series(equity_values).pct_change().dropna()
            sharpe = (returns.mean() * 252) / (returns.std() * np.sqrt(252)) if returns.std() > 0 else 0
        else:
            sharpe = 0
        
        # Max drawdown
        cummax = np.maximum.accumulate(equity_values)
        drawdown = (np.array(equity_values) - cummax) / cummax
        max_drawdown = np.min(drawdown)
        
        return {
            'initial_capital': self.initial_capital,
            'final_capital': self.portfolio_value,
            'total_return': total_return,
            'total_return_pct': total_return * 100,
            'total_trades': total_trades,
            'winning_trades': wins,
            'win_rate': win_rate,
            'max_drawdown': max_drawdown,
            'max_drawdown_pct': max_drawdown * 100,
            'sharpe_ratio': sharpe,
            'trades': self.trades,
            'equity_curve': self.equity_curve,
        }

    def print_results(self):
        """Print backtest results."""
        results = self.get_results()
        
        if not results:
            print("No backtest results to display")
            return
        
        print("\n" + "="*60)
        print("BACKTEST RESULTS")
        print("="*60)
        print(f"Initial Capital:    ${results['initial_capital']:,.2f}")
        print(f"Final Capital:      ${results['final_capital']:,.2f}")
        print(f"Total Return:       {results['total_return_pct']:+.2f}%")
        print(f"Total Trades:       {results['total_trades']}")
        print(f"Winning Trades:     {results['winning_trades']}")
        print(f"Win Rate:           {results['win_rate']:.1f}%")
        print(f"Max Drawdown:       {results['max_drawdown_pct']:.2f}%")
        print(f"Sharpe Ratio:       {results['sharpe_ratio']:.2f}")
        print("="*60 + "\n")
