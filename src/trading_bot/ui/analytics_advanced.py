"""Advanced performance analytics - Sharpe ratio, Sortino ratio, drawdown, trade analysis."""

import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Any
import math


class PerformanceAnalytics:
    """Calculate advanced performance metrics and trade analytics."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.risk_free_rate = 0.04  # 4% annual
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """Calculate all performance metrics."""
        result = {
            'timestamp': datetime.now().isoformat(),
            'returns': self._calculate_returns(),
            'sharpe_ratio': self._calculate_sharpe_ratio(),
            'sortino_ratio': self._calculate_sortino_ratio(),
            'max_drawdown': self._calculate_max_drawdown(),
            'win_rate_by_symbol': self._calculate_win_rate_by_symbol(),
            'win_rate_by_hour': self._calculate_win_rate_by_hour(),
            'trade_duration_stats': self._calculate_trade_duration(),
            'best_trade': self._get_best_trade(),
            'worst_trade': self._get_worst_trade(),
            'profit_factor': self._calculate_profit_factor()
        }
        return result
    
    def _calculate_returns(self) -> Dict[str, float]:
        """Calculate daily, weekly, monthly, and overall returns."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get starting capital and current equity
            starting_capital = 100000
            
            cursor.execute(
                """SELECT 
                   SUM(CASE WHEN side = 'SELL' THEN qty * price 
                            ELSE -qty * price END) as realized_pnl,
                   SUM(CASE WHEN side = 'BUY' THEN fee ELSE fee END) as total_fees
                   FROM fills"""
            )
            
            result = cursor.fetchone()
            realized_pnl = result['realized_pnl'] or 0
            total_fees = result['total_fees'] or 0
            net_pnl = realized_pnl - total_fees
            
            # Overall return
            overall_return = (net_pnl / starting_capital) * 100 if starting_capital else 0
            
            # Daily returns (last 5 trading days)
            cursor.execute(
                """SELECT DATE(timestamp) as date,
                   SUM(CASE WHEN side = 'SELL' THEN qty * price 
                            ELSE -qty * price END) - SUM(fee) as daily_pnl
                   FROM fills
                   WHERE timestamp > datetime('now', '-7 days')
                   GROUP BY DATE(timestamp)
                   ORDER BY date DESC
                   LIMIT 5"""
            )
            
            daily_returns = []
            for row in cursor.fetchall():
                daily_return = (row['daily_pnl'] / starting_capital) * 100 if row['daily_pnl'] else 0
                daily_returns.append({
                    'date': row['date'],
                    'return_pct': round(daily_return, 2),
                    'pnl': round(row['daily_pnl'], 2)
                })
            
            conn.close()
            
            return {
                'overall_pct': round(overall_return, 2),
                'overall_pnl': round(net_pnl, 2),
                'daily': daily_returns
            }
        except Exception as e:
            return {'overall_pct': 0, 'overall_pnl': 0, 'daily': [], 'error': str(e)}
    
    def _calculate_sharpe_ratio(self) -> float:
        """Sharpe ratio = (return - rf) / std_dev. Use 252 trading days."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get daily returns
            cursor.execute(
                """SELECT DATE(timestamp) as date,
                   SUM(CASE WHEN side = 'SELL' THEN qty * price 
                            ELSE -qty * price END) - SUM(fee) as daily_pnl
                   FROM fills
                   WHERE timestamp > datetime('now', '-90 days')
                   GROUP BY DATE(timestamp)"""
            )
            
            returns = []
            for row in cursor.fetchall():
                daily_return = (row[1] / 100000) if row[1] else 0
                returns.append(daily_return)
            
            conn.close()
            
            if len(returns) < 2:
                return 0
            
            # Calculate mean return
            mean_return = sum(returns) / len(returns)
            
            # Calculate std dev
            variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
            std_dev = math.sqrt(variance)
            
            if std_dev == 0:
                return 0
            
            # Annualize
            annual_return = mean_return * 252
            annual_std = std_dev * math.sqrt(252)
            
            sharpe = (annual_return - self.risk_free_rate) / annual_std if annual_std != 0 else 0
            return round(sharpe, 2)
        except Exception:
            return 0
    
    def _calculate_sortino_ratio(self) -> float:
        """Sortino ratio = (return - rf) / downside_std. Only penalizes downside volatility."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                """SELECT DATE(timestamp) as date,
                   SUM(CASE WHEN side = 'SELL' THEN qty * price 
                            ELSE -qty * price END) - SUM(fee) as daily_pnl
                   FROM fills
                   WHERE timestamp > datetime('now', '-90 days')
                   GROUP BY DATE(timestamp)"""
            )
            
            returns = []
            for row in cursor.fetchall():
                daily_return = (row[1] / 100000) if row[1] else 0
                returns.append(daily_return)
            
            conn.close()
            
            if len(returns) < 2:
                return 0
            
            mean_return = sum(returns) / len(returns)
            
            # Downside deviation (only negative returns)
            downside_returns = [r for r in returns if r < 0]
            if not downside_returns:
                return round((mean_return * 252 - self.risk_free_rate) / 0.001, 2)
            
            downside_variance = sum((r - 0) ** 2 for r in downside_returns) / len(returns)
            downside_std = math.sqrt(downside_variance)
            
            if downside_std == 0:
                return 0
            
            annual_return = mean_return * 252
            annual_downside_std = downside_std * math.sqrt(252)
            
            sortino = (annual_return - self.risk_free_rate) / annual_downside_std if annual_downside_std != 0 else 0
            return round(sortino, 2)
        except Exception:
            return 0
    
    def _calculate_max_drawdown(self) -> Dict[str, Any]:
        """Calculate maximum drawdown percentage and when it occurred."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get cumulative equity
            cursor.execute(
                """SELECT timestamp,
                   100000 + SUM(CASE WHEN side = 'SELL' THEN qty * price 
                                     ELSE -qty * price END) - SUM(fee)
                   OVER (ORDER BY timestamp) as equity
                   FROM fills
                   WHERE timestamp > datetime('now', '-90 days')
                   ORDER BY timestamp"""
            )
            
            rows = cursor.fetchall()
            conn.close()
            
            if not rows:
                return {'max_drawdown_pct': 0, 'current_drawdown_pct': 0}
            
            peak = 100000
            max_dd = 0
            current_dd = 0
            
            for timestamp, equity in rows:
                if equity > peak:
                    peak = equity
                
                dd = ((peak - equity) / peak) * 100
                if dd > max_dd:
                    max_dd = dd
                current_dd = dd
            
            return {
                'max_drawdown_pct': round(max_dd, 2),
                'current_drawdown_pct': round(current_dd, 2)
            }
        except Exception:
            return {'max_drawdown_pct': 0, 'current_drawdown_pct': 0}
    
    def _calculate_win_rate_by_symbol(self) -> Dict[str, Dict[str, Any]]:
        """Win rate, avg win, avg loss by symbol."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute(
                """SELECT symbol,
                   COUNT(CASE WHEN pnl > 0 THEN 1 END) as winning_trades,
                   COUNT(CASE WHEN pnl < 0 THEN 1 END) as losing_trades,
                   AVG(CASE WHEN pnl > 0 THEN pnl END) as avg_win,
                   AVG(CASE WHEN pnl < 0 THEN pnl END) as avg_loss,
                   SUM(pnl) as total_pnl
                   FROM fills
                   WHERE timestamp > datetime('now', '-30 days')
                   GROUP BY symbol
                   ORDER BY total_pnl DESC"""
            )
            
            result = {}
            for row in cursor.fetchall():
                total = row['winning_trades'] + row['losing_trades']
                win_rate = (row['winning_trades'] / total * 100) if total > 0 else 0
                
                result[row['symbol']] = {
                    'win_rate_pct': round(win_rate, 1),
                    'winning_trades': row['winning_trades'],
                    'losing_trades': row['losing_trades'],
                    'avg_win': round(row['avg_win'], 2) if row['avg_win'] else 0,
                    'avg_loss': round(row['avg_loss'], 2) if row['avg_loss'] else 0,
                    'total_pnl': round(row['total_pnl'], 2) if row['total_pnl'] else 0
                }
            
            conn.close()
            return result
        except Exception:
            return {}
    
    def _calculate_win_rate_by_hour(self) -> List[Dict[str, Any]]:
        """Win rate by hour of day."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                """SELECT CAST(strftime('%H', timestamp) AS INTEGER) as hour,
                   COUNT(CASE WHEN pnl > 0 THEN 1 END) as wins,
                   COUNT(CASE WHEN pnl < 0 THEN 1 END) as losses,
                   AVG(pnl) as avg_pnl,
                   SUM(pnl) as total_pnl
                   FROM fills
                   WHERE timestamp > datetime('now', '-30 days')
                   GROUP BY hour
                   ORDER BY hour"""
            )
            
            result = []
            for row in cursor.fetchall():
                total = row[1] + row[2]  # wins + losses
                win_rate = (row[1] / total * 100) if total > 0 else 0
                
                result.append({
                    'hour': f"{row[0]:02d}:00",
                    'win_rate_pct': round(win_rate, 1),
                    'trades': total,
                    'avg_pnl': round(row[3], 2) if row[3] else 0,
                    'total_pnl': round(row[4], 2) if row[4] else 0
                })
            
            conn.close()
            return result
        except Exception:
            return []
    
    def _calculate_trade_duration(self) -> Dict[str, Any]:
        """Trade duration statistics."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # For simplicity, estimate duration from timestamp gaps per symbol
            cursor.execute(
                """SELECT symbol,
                   COUNT(*) as trade_count,
                   MIN(timestamp) as first_time,
                   MAX(timestamp) as last_time
                   FROM fills
                   WHERE timestamp > datetime('now', '-30 days')
                   GROUP BY symbol"""
            )
            
            durations = []
            for row in cursor.fetchall():
                if row[2] and row[3]:
                    first = datetime.fromisoformat(row[2])
                    last = datetime.fromisoformat(row[3])
                    duration_hours = (last - first).total_seconds() / 3600
                    durations.append(duration_hours)
            
            conn.close()
            
            if not durations:
                return {'avg_duration_hours': 0, 'min_duration_hours': 0, 'max_duration_hours': 0}
            
            return {
                'avg_duration_hours': round(sum(durations) / len(durations), 2),
                'min_duration_hours': round(min(durations), 2),
                'max_duration_hours': round(max(durations), 2),
                'total_trades': len(durations)
            }
        except Exception:
            return {'avg_duration_hours': 0}
    
    def _get_best_trade(self) -> Dict[str, Any]:
        """Get best performing trade."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute(
                """SELECT symbol, qty, price, pnl, timestamp
                   FROM fills
                   WHERE timestamp > datetime('now', '-30 days')
                   ORDER BY pnl DESC
                   LIMIT 1"""
            )
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    'symbol': row['symbol'],
                    'pnl': round(row['pnl'], 2),
                    'qty': row['qty'],
                    'price': round(row['price'], 2),
                    'timestamp': row['timestamp']
                }
            return {}
        except Exception:
            return {}
    
    def _get_worst_trade(self) -> Dict[str, Any]:
        """Get worst performing trade."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute(
                """SELECT symbol, qty, price, pnl, timestamp
                   FROM fills
                   WHERE timestamp > datetime('now', '-30 days')
                   ORDER BY pnl ASC
                   LIMIT 1"""
            )
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    'symbol': row['symbol'],
                    'pnl': round(row['pnl'], 2),
                    'qty': row['qty'],
                    'price': round(row['price'], 2),
                    'timestamp': row['timestamp']
                }
            return {}
        except Exception:
            return {}
    
    def _calculate_profit_factor(self) -> float:
        """Profit factor = gross profit / gross loss."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                """SELECT 
                   SUM(CASE WHEN pnl > 0 THEN pnl ELSE 0 END) as gross_profit,
                   SUM(CASE WHEN pnl < 0 THEN ABS(pnl) ELSE 0 END) as gross_loss
                   FROM fills
                   WHERE timestamp > datetime('now', '-30 days')"""
            )
            
            row = cursor.fetchone()
            conn.close()
            
            gross_profit = row[0] or 0
            gross_loss = row[1] or 0
            
            if gross_loss == 0:
                return 0
            
            return round(gross_profit / gross_loss, 2)
        except Exception:
            return 0


# Global instance
analytics = PerformanceAnalytics('/app/data/trades.sqlite')
