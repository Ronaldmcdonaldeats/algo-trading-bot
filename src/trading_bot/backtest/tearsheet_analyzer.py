"""Strategy Backtester Tearsheets - Walk-forward analysis, out-of-sample testing

Generates detailed backtest reports:
- Tearsheets with monthly/annual returns
- Walk-forward analysis (in-sample vs out-of-sample)
- Parameter sensitivity analysis
- Out-of-sample performance validation
- Risk metrics by period
"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class MonthlyReturns:
    """Monthly performance data"""
    year: int
    month: int
    total_return: float
    trade_count: int
    win_rate: float
    max_dd: float
    sharpe: float


@dataclass
class AnnualReturns:
    """Annual performance data"""
    year: int
    total_return: float
    trade_count: int
    win_rate: float
    max_dd: float
    sharpe: float
    best_month: float
    worst_month: float


@dataclass
class WalkForwardResult:
    """Walk-forward analysis result"""
    period: str
    in_sample_return: float
    out_sample_return: float
    out_sample_drawdown: float
    parameter_set: Dict
    degradation: float  # How much worse OOS vs IS


@dataclass
class Tearsheet:
    """Complete backtest tearsheet"""
    strategy_name: str
    symbol: str
    start_date: str
    end_date: str
    total_return: float
    annual_return: float
    volatility: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float  # Gross profit / gross loss
    monthly_returns: List[MonthlyReturns]
    annual_returns: List[AnnualReturns]
    walk_forward_results: List[WalkForwardResult]
    best_trade: float
    worst_trade: float
    avg_trade: float
    trades_count: int


class TearsheetAnalyzer:
    """Generate detailed backtest tearsheets"""
    
    def __init__(self, cache_dir: str = ".cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
    def generate_tearsheet(self, equity_curve: pd.Series,
                          trades: List[Dict],
                          strategy_name: str = "Strategy",
                          symbol: str = "UNKNOWN") -> Tearsheet:
        """Generate comprehensive tearsheet from backtest results
        
        Args:
            equity_curve: Series with datetime index and equity values
            trades: List of {date, side, price, qty, pnl}
            strategy_name: Name of strategy
            symbol: Trading symbol
        """
        
        # Basic metrics
        total_return = (equity_curve.iloc[-1] - equity_curve.iloc[0]) / equity_curve.iloc[0]
        daily_returns = equity_curve.pct_change()
        annual_return = daily_returns.mean() * 252
        volatility = daily_returns.std() * np.sqrt(252)
        sharpe_ratio = (annual_return - 0.02) / volatility if volatility > 0 else 0
        
        # Drawdown
        running_max = equity_curve.expanding().max()
        drawdown = (equity_curve - running_max) / running_max
        max_drawdown = drawdown.min()
        
        # Trade metrics
        pnl_list = [t.get('pnl', 0) for t in trades]
        winning = [p for p in pnl_list if p > 0]
        losing = [p for p in pnl_list if p < 0]
        
        win_rate = len(winning) / len(pnl_list) if pnl_list else 0
        gross_profit = sum(winning) if winning else 0
        gross_loss = abs(sum(losing)) if losing else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        
        best_trade = max(pnl_list) if pnl_list else 0
        worst_trade = min(pnl_list) if pnl_list else 0
        avg_trade = sum(pnl_list) / len(pnl_list) if pnl_list else 0
        
        # Monthly returns
        monthly = self._calculate_monthly_returns(equity_curve, trades)
        
        # Annual returns
        annual = self._calculate_annual_returns(equity_curve, trades)
        
        # Walk-forward analysis
        walk_forward = self._perform_walk_forward_analysis(equity_curve, trades)
        
        return Tearsheet(
            strategy_name=strategy_name,
            symbol=symbol,
            start_date=equity_curve.index[0].strftime('%Y-%m-%d'),
            end_date=equity_curve.index[-1].strftime('%Y-%m-%d'),
            total_return=total_return,
            annual_return=annual_return,
            volatility=volatility,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            profit_factor=profit_factor,
            monthly_returns=monthly,
            annual_returns=annual,
            walk_forward_results=walk_forward,
            best_trade=best_trade,
            worst_trade=worst_trade,
            avg_trade=avg_trade,
            trades_count=len(trades)
        )
    
    def _calculate_monthly_returns(self, equity_curve: pd.Series,
                                  trades: List[Dict]) -> List[MonthlyReturns]:
        """Calculate monthly performance"""
        
        monthly_list = []
        
        for year in equity_curve.index.year.unique():
            for month in range(1, 13):
                # Get data for this month
                month_data = equity_curve[
                    (equity_curve.index.year == year) & 
                    (equity_curve.index.month == month)
                ]
                
                if len(month_data) == 0:
                    continue
                
                # Month return
                month_return = (month_data.iloc[-1] - month_data.iloc[0]) / month_data.iloc[0]
                
                # Trades in month
                month_trades = [t for t in trades if 
                               datetime.fromisoformat(t.get('date', '')).year == year and
                               datetime.fromisoformat(t.get('date', '')).month == month]
                
                pnl = [t.get('pnl', 0) for t in month_trades]
                win_rate = len([p for p in pnl if p > 0]) / len(pnl) if pnl else 0
                
                # Max DD in month
                running_max = month_data.expanding().max()
                dd = (month_data - running_max) / running_max
                max_dd = dd.min()
                
                # Sharpe
                daily_ret = month_data.pct_change()
                sharpe = (daily_ret.mean() * 252 - 0.02) / (daily_ret.std() * np.sqrt(252)) \
                    if daily_ret.std() > 0 else 0
                
                monthly_list.append(MonthlyReturns(
                    year=year,
                    month=month,
                    total_return=month_return,
                    trade_count=len(month_trades),
                    win_rate=win_rate,
                    max_dd=max_dd,
                    sharpe=sharpe
                ))
        
        return monthly_list
    
    def _calculate_annual_returns(self, equity_curve: pd.Series,
                                 trades: List[Dict]) -> List[AnnualReturns]:
        """Calculate annual performance"""
        
        annual_list = []
        
        for year in equity_curve.index.year.unique():
            year_data = equity_curve[equity_curve.index.year == year]
            
            if len(year_data) == 0:
                continue
            
            year_return = (year_data.iloc[-1] - year_data.iloc[0]) / year_data.iloc[0]
            
            # Trades in year
            year_trades = [t for t in trades if 
                          datetime.fromisoformat(t.get('date', '')).year == year]
            
            pnl = [t.get('pnl', 0) for t in year_trades]
            winning = [p for p in pnl if p > 0]
            win_rate = len(winning) / len(pnl) if pnl else 0
            
            # Max DD
            running_max = year_data.expanding().max()
            dd = (year_data - running_max) / running_max
            max_dd = dd.min()
            
            # Sharpe
            daily_ret = year_data.pct_change()
            sharpe = (daily_ret.mean() * 252 - 0.02) / (daily_ret.std() * np.sqrt(252)) \
                if daily_ret.std() > 0 else 0
            
            # Monthly breakdown
            monthly_returns = []
            for month in range(1, 13):
                month_data = year_data[year_data.index.month == month]
                if len(month_data) > 0:
                    m_ret = (month_data.iloc[-1] - month_data.iloc[0]) / month_data.iloc[0]
                    monthly_returns.append(m_ret)
            
            best_month = max(monthly_returns) if monthly_returns else 0
            worst_month = min(monthly_returns) if monthly_returns else 0
            
            annual_list.append(AnnualReturns(
                year=year,
                total_return=year_return,
                trade_count=len(year_trades),
                win_rate=win_rate,
                max_dd=max_dd,
                sharpe=sharpe,
                best_month=best_month,
                worst_month=worst_month
            ))
        
        return annual_list
    
    def _perform_walk_forward_analysis(self, equity_curve: pd.Series,
                                      trades: List[Dict],
                                      window_size: int = 252) -> List[WalkForwardResult]:
        """Perform walk-forward analysis (in-sample vs out-of-sample)"""
        
        results = []
        total_len = len(equity_curve)
        
        # Split into overlapping windows
        for i in range(0, total_len - window_size, window_size // 2):
            in_sample_end = i + window_size
            out_sample_end = min(i + window_size + window_size // 2, total_len)
            
            if in_sample_end >= total_len:
                break
            
            # In-sample performance
            in_sample = equity_curve.iloc[i:in_sample_end]
            in_return = (in_sample.iloc[-1] - in_sample.iloc[0]) / in_sample.iloc[0]
            
            # Out-of-sample performance
            out_sample = equity_curve.iloc[in_sample_end:out_sample_end]
            out_return = (out_sample.iloc[-1] - out_sample.iloc[0]) / out_sample.iloc[0]
            
            # Out-of-sample drawdown
            running_max = out_sample.expanding().max()
            dd = (out_sample - running_max) / running_max
            out_dd = dd.min()
            
            # Degradation
            degradation = in_return - out_return
            
            results.append(WalkForwardResult(
                period=f"{equity_curve.index[i].strftime('%Y-%m-%d')} to "
                       f"{equity_curve.index[out_sample_end-1].strftime('%Y-%m-%d')}",
                in_sample_return=in_return,
                out_sample_return=out_return,
                out_sample_drawdown=out_dd,
                parameter_set={},
                degradation=degradation
            ))
        
        return results
    
    def save_tearsheet(self, tearsheet: Tearsheet, 
                      filename: str = "tearsheet.json") -> str:
        """Save tearsheet to JSON"""
        
        filepath = self.cache_dir / filename
        
        data = {
            'strategy': tearsheet.strategy_name,
            'symbol': tearsheet.symbol,
            'period': f"{tearsheet.start_date} to {tearsheet.end_date}",
            'total_return': tearsheet.total_return,
            'annual_return': tearsheet.annual_return,
            'volatility': tearsheet.volatility,
            'sharpe_ratio': tearsheet.sharpe_ratio,
            'max_drawdown': tearsheet.max_drawdown,
            'win_rate': tearsheet.win_rate,
            'profit_factor': tearsheet.profit_factor,
            'best_trade': tearsheet.best_trade,
            'worst_trade': tearsheet.worst_trade,
            'avg_trade': tearsheet.avg_trade,
            'total_trades': tearsheet.trades_count,
            'monthly_returns': [
                {
                    'year': m.year,
                    'month': m.month,
                    'return': m.total_return,
                    'win_rate': m.win_rate
                }
                for m in tearsheet.monthly_returns
            ],
            'annual_returns': [
                {
                    'year': a.year,
                    'return': a.total_return,
                    'best_month': a.best_month,
                    'worst_month': a.worst_month,
                    'sharpe': a.sharpe
                }
                for a in tearsheet.annual_returns
            ],
            'walk_forward': [
                {
                    'period': w.period,
                    'in_sample_return': w.in_sample_return,
                    'out_sample_return': w.out_sample_return,
                    'degradation': w.degradation
                }
                for w in tearsheet.walk_forward_results
            ]
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Tearsheet saved to {filepath}")
        return str(filepath)
