"""Trade reconciliation system - verify fills, detect orphaned orders, match portfolio."""

import sqlite3
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple


class TradeReconciliation:
    """Reconcile database records with broker state and detect discrepancies."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.issues = []
        self.warnings = []
    
    def _db_available(self) -> bool:
        """Check if database file exists and is accessible."""
        if not os.path.exists(self.db_path):
            return False
        try:
            conn = sqlite3.connect(self.db_path, timeout=1)
            conn.close()
            return True
        except Exception:
            return False
    
    def reconcile(self, paper_engine: Any = None) -> Dict[str, Any]:
        """Run full reconciliation suite."""
        self.issues = []
        self.warnings = []
        
        result = {
            'timestamp': datetime.now().isoformat(),
            'status': 'healthy',
            'database_fills': 0,
            'engine_orders': 0,
            'orphaned_orders': [],
            'missing_fills': [],
            'portfolio_mismatch': None,
            'reconciliation_issues': [],
            'warnings': [],
            'last_sync': None
        }
        
        # Check if database is available
        if not self._db_available():
            self.warnings.append(f"Database not available: {self.db_path}")
            result['warnings'] = self.warnings
            result['status'] = 'warning'
            result['last_sync'] = datetime.now().isoformat()
            return result
        
        # Get database fills
        result['database_fills'] = self._count_fills()
        
        # Get engine orders if available
        if paper_engine:
            result['engine_orders'] = len(paper_engine.orders)
            result['orphaned_orders'] = self._find_orphaned_orders(paper_engine)
            result['missing_fills'] = self._find_missing_fills(paper_engine)
            result['portfolio_mismatch'] = self._check_portfolio_match(paper_engine)
        
        # Check for duplicate fills
        duplicates = self._find_duplicate_fills()
        if duplicates:
            self.issues.append(f"Found {len(duplicates)} duplicate fills")
            result['reconciliation_issues'].append({'type': 'duplicate_fills', 'count': len(duplicates)})
        
        # Check for negative cash
        negative_cash = self._check_negative_cash()
        if negative_cash:
            self.issues.append("Negative cash balance detected")
            result['reconciliation_issues'].append({'type': 'negative_cash', 'amount': negative_cash})
        
        # Check for stale orders (>30 min old)
        stale = self._find_stale_orders()
        if stale:
            self.warnings.append(f"Found {len(stale)} stale orders (>30 min old)")
            result['warnings'].append({'type': 'stale_orders', 'count': len(stale)})
        
        # Set status
        if self.issues:
            result['status'] = 'critical'
        elif self.warnings:
            result['status'] = 'warning'
        
        result['reconciliation_issues'].extend(self.issues)
        result['warnings'].extend(self.warnings)
        result['last_sync'] = datetime.now().isoformat()
        
        return result
    
    def _count_fills(self) -> int:
        """Count total fills in database."""
        try:
            conn = sqlite3.connect(self.db_path, timeout=2)
            cursor = conn.cursor()
            
            # Check if fills table exists
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='fills'"
            )
            if not cursor.fetchone():
                conn.close()
                self.warnings.append("No fills table found in database")
                return 0
            
            cursor.execute("SELECT COUNT(*) FROM fills")
            count = cursor.fetchone()[0]
            conn.close()
            return count
        except sqlite3.DatabaseError as e:
            self.warnings.append(f"Database error: {str(e)}")
            return 0
        except Exception as e:
            self.warnings.append(f"Could not count fills: {str(e)}")
            return 0
    
    def _find_orphaned_orders(self, paper_engine: Any) -> List[Dict[str, Any]]:
        """Find orders in engine but not in database."""
        orphaned = []
        
        try:
            if not os.path.exists(self.db_path):
                return orphaned
                
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Check if fills table exists
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='fills'"
            )
            if not cursor.fetchone():
                conn.close()
                return orphaned
            
            for order_id, order in paper_engine.orders.items():
                cursor.execute(
                    "SELECT id FROM fills WHERE order_id = ? OR external_id = ?",
                    (order_id, order_id)
                )
                if not cursor.fetchone():
                    orphaned.append({
                        'order_id': order_id,
                        'symbol': order.get('symbol', 'UNKNOWN'),
                        'shares': order.get('shares', 0),
                        'created_at': order.get('created_at', '')
                    })
            
            conn.close()
        except Exception as e:
            self.warnings.append(f"Could not check orphaned orders: {str(e)}")
        
        return orphaned
    
    def _find_missing_fills(self, paper_engine: Any) -> List[Dict[str, Any]]:
        """Find database fills not yet in engine holdings."""
        missing = []
        
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get latest fills (last 100)
            cursor.execute(
                """SELECT id, symbol, qty, price, fee, ts FROM fills 
                   ORDER BY ts DESC LIMIT 100"""
            )
            
            for fill in cursor.fetchall():
                symbol = fill['symbol']
                qty = fill['qty']
                
                # Check if symbol is in engine holdings with matching quantity
                engine_qty = paper_engine.holdings.get(symbol, {}).get('shares', 0)
                
                # Simple check: if fill is recent and qty doesn't match
                fill_time = datetime.fromisoformat(fill['ts']) if isinstance(fill['ts'], str) else fill['ts']
                if (datetime.now() - fill_time).seconds > 300:  # >5 min old
                    if abs(engine_qty) < abs(qty):
                        missing.append({
                            'fill_id': fill['id'],
                            'symbol': symbol,
                            'qty': qty,
                            'engine_qty': engine_qty
                        })
            
            conn.close()
        except Exception as e:
            self.warnings.append(f"Could not check missing fills: {str(e)}")
        
        return missing
    
    def _check_portfolio_match(self, paper_engine: Any) -> Dict[str, Any]:
        """Verify database holdings match engine holdings."""
        mismatch = None
        
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get current holdings from database
            cursor.execute(
                """SELECT symbol, SUM(qty) as total_qty, SUM(qty * price) as total_value
                   FROM fills
                   GROUP BY symbol
                   HAVING total_qty IS NOT NULL AND total_qty != 0"""
            )
            
            db_holdings = {}
            for row in cursor.fetchall():
                db_holdings[row['symbol']] = {
                    'qty': row['total_qty'],
                    'value': row['total_value']
                }
            
            # Compare with engine
            engine_holdings = {}
            for symbol, data in paper_engine.holdings.items():
                if data.get('shares', 0) != 0:
                    engine_holdings[symbol] = {
                        'qty': data['shares'],
                        'value': data.get('market_value', 0)
                    }
            
            # Check for differences
            all_symbols = set(db_holdings.keys()) | set(engine_holdings.keys())
            differences = []
            
            for symbol in all_symbols:
                db_qty = db_holdings.get(symbol, {}).get('qty', 0)
                eng_qty = engine_holdings.get(symbol, {}).get('qty', 0)
                
                if db_qty != eng_qty:
                    differences.append({
                        'symbol': symbol,
                        'database_qty': db_qty,
                        'engine_qty': eng_qty,
                        'difference': db_qty - eng_qty
                    })
            
            if differences:
                mismatch = {
                    'status': 'mismatch',
                    'count': len(differences),
                    'differences': differences
                }
            else:
                mismatch = {'status': 'matched'}
            
            conn.close()
        except Exception as e:
            self.warnings.append(f"Could not check portfolio match: {str(e)}")
            mismatch = {'status': 'error', 'error': str(e)}
        
        return mismatch
    
    def _find_duplicate_fills(self) -> List[Tuple]:
        """Find duplicate fills (same symbol/qty/price within 1 second)."""
        duplicates = []
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                """SELECT symbol, qty, price, COUNT(*) as cnt
                   FROM fills
                   WHERE ts > datetime('now', '-1 day')
                   GROUP BY symbol, qty, price, datetime(ts, 'seconds')
                   HAVING cnt > 1"""
            )
            
            duplicates = cursor.fetchall()
            conn.close()
        except Exception as e:
            self.warnings.append(f"Could not find duplicates: {str(e)}")
        
        return duplicates
    
    def _check_negative_cash(self) -> float:
        """Check if any account state has negative cash."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Calculate cash from initial balance - fills
            cursor.execute(
                """SELECT 
                   100000 - SUM(CASE WHEN side = 'BUY' THEN qty * price + fee 
                                     ELSE -qty * price + fee END) as cash
                   FROM fills"""
            )
            
            result = cursor.fetchone()
            cash = result['cash'] if result and result['cash'] is not None else 100000
            conn.close()
            
            if cash is not None and cash < 0:
                return abs(cash)
        except Exception as e:
            self.warnings.append(f"Could not check cash: {str(e)}")
        
        return 0
    
    def _find_stale_orders(self) -> List[Dict[str, Any]]:
        """Find orders older than 30 minutes without fills."""
        stale = []
        
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get orders >30 min old (from orders table, not fills)
            thirty_min_ago = (datetime.now() - timedelta(minutes=30)).isoformat()
            
            cursor.execute(
                """SELECT id as order_id, symbol, qty FROM orders
                   WHERE ts < ? AND status = 'PENDING'""",
                (thirty_min_ago,)
            )
            
            stale = [dict(row) for row in cursor.fetchall()]
            conn.close()
        except Exception as e:
            self.warnings.append(f"Could not find stale orders: {str(e)}")
        
        return stale
    
    def repair_duplicates(self) -> int:
        """Remove duplicate fills (keep first occurrence)."""
        count = 0
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Find and delete duplicate rows
            cursor.execute(
                """DELETE FROM fills WHERE id NOT IN (
                   SELECT MIN(id) FROM fills
                   GROUP BY symbol, qty, price, datetime(ts, 'seconds'))"""
            )
            
            count = cursor.rowcount
            conn.commit()
            conn.close()
            
            self.issues.append(f"Repaired {count} duplicate fills")
        except Exception as e:
            self.warnings.append(f"Could not repair duplicates: {str(e)}")
        
        return count


# Global instance
db_path = os.getenv('TRADES_DB_PATH', '/app/data/trades.sqlite')
reconciliation = TradeReconciliation(db_path)
