"""Trade Journal System - Track trades with notes, tags, and A/B testing

Features:
- Trade note-taking and tagging
- Trade grouping (A/B testing)
- Performance analysis by tag/group
- Trade pattern recognition
- Win/loss analysis
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import json
from pathlib import Path
import sqlite3


@dataclass
class TradeNote:
    """Note attached to a trade"""
    trade_id: str
    content: str
    created_at: datetime
    updated_at: datetime
    
    def to_dict(self) -> dict:
        return {
            'trade_id': self.trade_id,
            'content': self.content,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }


@dataclass
class TradeTag:
    """Tag for organizing trades"""
    name: str
    color: str = "gray"  # For UI display
    description: str = ""
    
    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'color': self.color,
            'description': self.description,
        }


@dataclass
class ABTestGroup:
    """Group trades for A/B testing (e.g., "Strategy A" vs "Strategy B")"""
    group_id: str
    name: str
    start_date: datetime
    end_date: Optional[datetime] = None
    description: str = ""
    parameters: Dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            'group_id': self.group_id,
            'name': self.name,
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'description': self.description,
            'parameters': self.parameters,
        }


@dataclass
class JournalEntry:
    """Complete journal entry for a trade"""
    trade_id: str
    symbol: str
    entry_price: float
    exit_price: Optional[float]
    quantity: int
    side: str  # BUY, SELL
    entry_time: datetime
    exit_time: Optional[datetime]
    profit_loss: Optional[float]
    profit_loss_pct: Optional[float]
    strategy: str
    tags: List[str] = field(default_factory=list)
    notes: List[TradeNote] = field(default_factory=list)
    ab_group: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            'trade_id': self.trade_id,
            'symbol': self.symbol,
            'entry_price': self.entry_price,
            'exit_price': self.exit_price,
            'quantity': self.quantity,
            'side': self.side,
            'entry_time': self.entry_time.isoformat(),
            'exit_time': self.exit_time.isoformat() if self.exit_time else None,
            'profit_loss': self.profit_loss,
            'profit_loss_pct': self.profit_loss_pct,
            'strategy': self.strategy,
            'tags': self.tags,
            'notes': [n.to_dict() for n in self.notes],
            'ab_group': self.ab_group,
        }


class TradeJournal:
    """Manage trade journal with notes, tags, and analysis"""
    
    def __init__(self, db_path: str = "trade_journal.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Trade journal entries
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS journal_entries (
                trade_id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL,
                quantity INTEGER NOT NULL,
                side TEXT NOT NULL,
                entry_time TEXT NOT NULL,
                exit_time TEXT,
                profit_loss REAL,
                profit_loss_pct REAL,
                strategy TEXT NOT NULL,
                ab_group TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tags
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                color TEXT,
                description TEXT
            )
        ''')
        
        # Trade-tag mapping
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trade_tags (
                trade_id TEXT NOT NULL,
                tag_name TEXT NOT NULL,
                PRIMARY KEY (trade_id, tag_name),
                FOREIGN KEY (trade_id) REFERENCES journal_entries (trade_id),
                FOREIGN KEY (tag_name) REFERENCES tags (name)
            )
        ''')
        
        # Trade notes
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trade_notes (
                id INTEGER PRIMARY KEY,
                trade_id TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (trade_id) REFERENCES journal_entries (trade_id)
            )
        ''')
        
        # A/B test groups
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ab_groups (
                group_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT,
                description TEXT,
                parameters TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def add_trade(self, entry: JournalEntry) -> bool:
        """Add trade to journal"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO journal_entries 
                (trade_id, symbol, entry_price, exit_price, quantity, side, 
                 entry_time, exit_time, profit_loss, profit_loss_pct, strategy, ab_group)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                entry.trade_id, entry.symbol, entry.entry_price, entry.exit_price,
                entry.quantity, entry.side, entry.entry_time.isoformat(),
                entry.exit_time.isoformat() if entry.exit_time else None,
                entry.profit_loss, entry.profit_loss_pct, entry.strategy, entry.ab_group
            ))
            
            # Add tags
            for tag in entry.tags:
                cursor.execute('''
                    INSERT OR IGNORE INTO trade_tags (trade_id, tag_name)
                    VALUES (?, ?)
                ''', (entry.trade_id, tag))
            
            # Add notes
            for note in entry.notes:
                cursor.execute('''
                    INSERT INTO trade_notes (trade_id, content, created_at, updated_at)
                    VALUES (?, ?, ?, ?)
                ''', (note.trade_id, note.content, 
                      note.created_at.isoformat(), note.updated_at.isoformat()))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Error adding trade: {e}")
            return False
        finally:
            conn.close()
    
    def add_tag(self, tag: TradeTag) -> bool:
        """Create new tag"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO tags (name, color, description)
                VALUES (?, ?, ?)
            ''', (tag.name, tag.color, tag.description))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error adding tag: {e}")
            return False
        finally:
            conn.close()
    
    def tag_trade(self, trade_id: str, tag_name: str) -> bool:
        """Add tag to trade"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO trade_tags (trade_id, tag_name)
                VALUES (?, ?)
            ''', (trade_id, tag_name))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error tagging trade: {e}")
            return False
        finally:
            conn.close()
    
    def add_note(self, trade_id: str, content: str) -> bool:
        """Add note to trade"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        now = datetime.now()
        
        try:
            cursor.execute('''
                INSERT INTO trade_notes (trade_id, content, created_at, updated_at)
                VALUES (?, ?, ?, ?)
            ''', (trade_id, content, now.isoformat(), now.isoformat()))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error adding note: {e}")
            return False
        finally:
            conn.close()
    
    def create_ab_group(self, group: ABTestGroup) -> bool:
        """Create A/B test group"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO ab_groups 
                (group_id, name, start_date, end_date, description, parameters)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (group.group_id, group.name, group.start_date.isoformat(),
                  group.end_date.isoformat() if group.end_date else None,
                  group.description, json.dumps(group.parameters)))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error creating AB group: {e}")
            return False
        finally:
            conn.close()
    
    def analyze_by_tag(self, tag_name: str) -> Dict:
        """Analyze trades by tag"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT j.profit_loss, j.profit_loss_pct, j.side
            FROM journal_entries j
            JOIN trade_tags t ON j.trade_id = t.trade_id
            WHERE t.tag_name = ? AND j.exit_price IS NOT NULL
        ''', (tag_name,))
        
        results = cursor.fetchall()
        conn.close()
        
        if not results:
            return {}
        
        pnls = [r[0] for r in results if r[0] is not None]
        pnl_pcts = [r[1] for r in results if r[1] is not None]
        
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        
        return {
            'tag': tag_name,
            'total_trades': len(results),
            'winning_trades': len(wins),
            'losing_trades': len(losses),
            'win_rate': len(wins) / len(results) if results else 0,
            'total_pnl': sum(pnls),
            'avg_pnl': sum(pnls) / len(pnls) if pnls else 0,
            'avg_win': sum(wins) / len(wins) if wins else 0,
            'avg_loss': sum(losses) / len(losses) if losses else 0,
            'largest_win': max(wins) if wins else 0,
            'largest_loss': min(losses) if losses else 0,
            'avg_pnl_pct': sum(pnl_pcts) / len(pnl_pcts) if pnl_pcts else 0,
        }
    
    def analyze_by_ab_group(self, group_id: str) -> Dict:
        """Analyze trades by A/B test group"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT profit_loss, profit_loss_pct, side
            FROM journal_entries
            WHERE ab_group = ? AND exit_price IS NOT NULL
        ''', (group_id,))
        
        results = cursor.fetchall()
        conn.close()
        
        if not results:
            return {}
        
        pnls = [r[0] for r in results if r[0] is not None]
        pnl_pcts = [r[1] for r in results if r[1] is not None]
        
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        
        return {
            'group_id': group_id,
            'total_trades': len(results),
            'winning_trades': len(wins),
            'losing_trades': len(losses),
            'win_rate': len(wins) / len(results) if results else 0,
            'total_pnl': sum(pnls),
            'avg_pnl': sum(pnls) / len(pnls) if pnls else 0,
            'avg_win': sum(wins) / len(wins) if wins else 0,
            'avg_loss': sum(losses) / len(losses) if losses else 0,
            'largest_win': max(wins) if wins else 0,
            'largest_loss': min(losses) if losses else 0,
            'avg_pnl_pct': sum(pnl_pcts) / len(pnl_pcts) if pnl_pcts else 0,
        }
    
    def analyze_by_symbol(self, symbol: str) -> Dict:
        """Analyze trades by symbol"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT profit_loss, profit_loss_pct, strategy
            FROM journal_entries
            WHERE symbol = ? AND exit_price IS NOT NULL
        ''', (symbol,))
        
        results = cursor.fetchall()
        conn.close()
        
        if not results:
            return {}
        
        pnls = [r[0] for r in results if r[0] is not None]
        pnl_pcts = [r[1] for r in results if r[1] is not None]
        
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        
        return {
            'symbol': symbol,
            'total_trades': len(results),
            'winning_trades': len(wins),
            'losing_trades': len(losses),
            'win_rate': len(wins) / len(results) if results else 0,
            'total_pnl': sum(pnls),
            'avg_pnl': sum(pnls) / len(pnls) if pnls else 0,
            'avg_win': sum(wins) / len(wins) if wins else 0,
            'avg_loss': sum(losses) / len(losses) if losses else 0,
            'largest_win': max(wins) if wins else 0,
            'largest_loss': min(losses) if losses else 0,
            'avg_pnl_pct': sum(pnl_pcts) / len(pnl_pcts) if pnl_pcts else 0,
        }
    
    def find_winning_patterns(self, min_occurrences: int = 3) -> List[Dict]:
        """Find patterns in winning trades"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Find common tags/strategies in winning trades
        cursor.execute('''
            SELECT strategy, COUNT(*) as count, AVG(profit_loss_pct) as avg_return
            FROM journal_entries
            WHERE profit_loss > 0 AND exit_price IS NOT NULL
            GROUP BY strategy
            HAVING COUNT(*) >= ?
            ORDER BY avg_return DESC
        ''', (min_occurrences,))
        
        strategies = cursor.fetchall()
        conn.close()
        
        patterns = []
        for strategy, count, avg_return in strategies:
            patterns.append({
                'pattern_type': 'strategy',
                'name': strategy,
                'frequency': count,
                'avg_return_pct': avg_return,
                'strength': min(1.0, avg_return / 5.0),  # Normalize to 0-1
            })
        
        return patterns
    
    def compare_ab_groups(self, group_ids: List[str]) -> Dict[str, Dict]:
        """Compare metrics across A/B test groups"""
        results = {}
        for group_id in group_ids:
            results[group_id] = self.analyze_by_ab_group(group_id)
        return results
    
    def get_recent_trades(self, days: int = 7, limit: int = 50) -> List[JournalEntry]:
        """Get recent trades"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff = datetime.now() - timedelta(days=days)
        cursor.execute('''
            SELECT trade_id, symbol, entry_price, exit_price, quantity, side,
                   entry_time, exit_time, profit_loss, profit_loss_pct, strategy, ab_group
            FROM journal_entries
            WHERE entry_time > ?
            ORDER BY entry_time DESC
            LIMIT ?
        ''', (cutoff.isoformat(), limit))
        
        entries = []
        for row in cursor.fetchall():
            entries.append(JournalEntry(
                trade_id=row[0],
                symbol=row[1],
                entry_price=row[2],
                exit_price=row[3],
                quantity=row[4],
                side=row[5],
                entry_time=datetime.fromisoformat(row[6]),
                exit_time=datetime.fromisoformat(row[7]) if row[7] else None,
                profit_loss=row[8],
                profit_loss_pct=row[9],
                strategy=row[10],
                ab_group=row[11],
            ))
        
        conn.close()
        return entries
    
    def export_journal(self, filepath: str = "trade_journal.json"):
        """Export journal to JSON"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM journal_entries')
        entries = cursor.fetchall()
        
        data = {
            'export_date': datetime.now().isoformat(),
            'total_trades': len(entries),
            'trades': [self._row_to_dict(row) for row in entries],
        }
        
        conn.close()
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        return filepath
    
    def _row_to_dict(self, row) -> dict:
        """Convert database row to dictionary"""
        return {
            'trade_id': row[0],
            'symbol': row[1],
            'entry_price': row[2],
            'exit_price': row[3],
            'quantity': row[4],
            'side': row[5],
            'entry_time': row[6],
            'exit_time': row[7],
            'profit_loss': row[8],
            'profit_loss_pct': row[9],
            'strategy': row[10],
            'ab_group': row[11],
        }
