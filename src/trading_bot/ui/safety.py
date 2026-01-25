"""Safety & Risk Management for Trading Bot Dashboard."""

import logging
import shutil
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class DatabaseBackupManager:
    """Manages automatic database backups with retention policy."""
    
    def __init__(self, db_path: str = "data/trades.sqlite", backup_dir: str = "data/backups"):
        self.db_path = Path(db_path)
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    def create_backup(self) -> Optional[Path]:
        """Create a backup of the database."""
        if not self.db_path.exists():
            logger.warning("Database not found, skipping backup")
            return None
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = self.backup_dir / f"trades_backup_{timestamp}.sqlite"
            shutil.copy2(self.db_path, backup_path)
            logger.info(f"Database backed up to {backup_path}")
            return backup_path
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return None
    
    def cleanup_old_backups(self, retention_days: int = 7):
        """Remove backups older than retention_days."""
        try:
            cutoff_date = datetime.now() - timedelta(days=retention_days)
            for backup_file in self.backup_dir.glob("trades_backup_*.sqlite"):
                file_time = datetime.fromtimestamp(backup_file.stat().st_mtime)
                if file_time < cutoff_date:
                    backup_file.unlink()
                    logger.info(f"Deleted old backup: {backup_file}")
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
    
    def list_backups(self) -> list:
        """List all available backups."""
        try:
            backups = sorted(self.backup_dir.glob("trades_backup_*.sqlite"), reverse=True)
            return [{"path": str(b), "size": b.stat().st_size, "date": b.stat().st_mtime} for b in backups[:10]]
        except Exception as e:
            logger.error(f"Failed to list backups: {e}")
            return []
    
    def restore_backup(self, backup_path: str) -> bool:
        """Restore database from backup."""
        try:
            backup = Path(backup_path)
            if not backup.exists():
                logger.error(f"Backup not found: {backup_path}")
                return False
            shutil.copy2(backup, self.db_path)
            logger.info(f"Database restored from {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Restore failed: {e}")
            return False


class PositionValidator:
    """Validates position sizes and risk constraints."""
    
    def __init__(self, 
                 max_position_pct: float = 0.15,  # 15% of portfolio per symbol
                 max_sector_exposure: float = 0.30,  # 30% per sector
                 max_leverage: float = 1.5):  # 1.5x leverage max
        self.max_position_pct = max_position_pct
        self.max_sector_exposure = max_sector_exposure
        self.max_leverage = max_leverage
    
    def validate_position(self, symbol: str, qty: int, entry_price: float, 
                         portfolio_value: float, current_positions: Dict) -> Tuple[bool, str]:
        """
        Validate if a position can be opened.
        
        Returns: (is_valid, message)
        """
        position_value = qty * entry_price
        position_pct = (position_value / portfolio_value) * 100
        
        # Check individual position limit
        if position_pct > (self.max_position_pct * 100):
            return False, f"Position {position_pct:.1f}% exceeds limit of {self.max_position_pct*100:.1f}%"
        
        # Check symbol already held
        if symbol in current_positions:
            existing_value = current_positions[symbol]['qty'] * current_positions[symbol]['avg_price']
            total_value = existing_value + position_value
            total_pct = (total_value / portfolio_value) * 100
            if total_pct > (self.max_position_pct * 100):
                return False, f"Total {symbol} exposure {total_pct:.1f}% exceeds limit"
        
        # Calculate total equity exposure
        total_equity_exposure = sum(
            pos['qty'] * pos['avg_price'] 
            for pos in current_positions.values()
        ) + position_value
        
        leverage = total_equity_exposure / portfolio_value
        if leverage > self.max_leverage:
            return False, f"Leverage {leverage:.2f}x exceeds limit of {self.max_leverage}x"
        
        return True, "Position valid"
    
    def get_constraints(self) -> Dict:
        """Get current constraints."""
        return {
            'max_position_pct': self.max_position_pct,
            'max_sector_exposure': self.max_sector_exposure,
            'max_leverage': self.max_leverage,
        }


class SafetyManager:
    """Unified safety management system."""
    
    def __init__(self, db_path: str = "data/trades.sqlite"):
        self.backup_manager = DatabaseBackupManager(db_path)
        self.position_validator = PositionValidator()
        self.errors = []
        self.warnings = []
    
    def daily_maintenance(self):
        """Run daily maintenance tasks."""
        try:
            self.backup_manager.create_backup()
            self.backup_manager.cleanup_old_backups(retention_days=7)
            logger.info("Daily maintenance completed")
        except Exception as e:
            logger.error(f"Daily maintenance failed: {e}")
            self.errors.append(str(e))
    
    def get_safety_status(self) -> Dict:
        """Get current safety status."""
        backups = self.backup_manager.list_backups()
        return {
            'backups_available': len(backups),
            'last_backup': backups[0]['date'] if backups else None,
            'constraints': self.position_validator.get_constraints(),
            'errors': self.errors[-10:],  # Last 10 errors
            'warnings': self.warnings[-10:],  # Last 10 warnings
        }


# Global instance
safety_manager = SafetyManager()
