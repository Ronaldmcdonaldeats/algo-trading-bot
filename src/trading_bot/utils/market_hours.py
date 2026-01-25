"""Market hours utilities for trading bot."""

from datetime import datetime, time, timezone
import pytz


class MarketHours:
    """Utilities for US market hours (NYSE/NASDAQ)."""
    
    # US Eastern timezone
    ET = pytz.timezone('US/Eastern')
    
    # Regular trading hours: 9:30 AM - 4:00 PM ET
    MARKET_OPEN = time(9, 30)
    MARKET_CLOSE = time(16, 0)
    
    # Extended hours
    PRE_MARKET_OPEN = time(4, 0)
    AFTER_MARKET_CLOSE = time(20, 0)

    @classmethod
    def is_market_open(cls, dt: datetime | None = None) -> bool:
        """Check if market is currently open (regular hours only).
        
        Args:
            dt: Datetime to check (default: now in ET)
            
        Returns:
            True if market is open, False otherwise
        """
        if dt is None:
            dt = datetime.now(cls.ET)
        elif dt.tzinfo is None:
            # Assume UTC if no timezone
            dt = dt.replace(tzinfo=timezone.utc).astimezone(cls.ET)
        else:
            dt = dt.astimezone(cls.ET)
        
        # Check if weekday (Mon=0, Sun=6)
        if dt.weekday() >= 5:  # Saturday or Sunday
            return False
        
        # Check time within market hours
        current_time = dt.time()
        return cls.MARKET_OPEN <= current_time < cls.MARKET_CLOSE

    @classmethod
    def is_extended_hours(cls, dt: datetime | None = None) -> bool:
        """Check if market is in pre-market or after-hours.
        
        Args:
            dt: Datetime to check (default: now in ET)
            
        Returns:
            True if in extended hours, False otherwise
        """
        if dt is None:
            dt = datetime.now(cls.ET)
        elif dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc).astimezone(cls.ET)
        else:
            dt = dt.astimezone(cls.ET)
        
        # Check if weekday
        if dt.weekday() >= 5:
            return False
        
        current_time = dt.time()
        return (cls.PRE_MARKET_OPEN <= current_time < cls.MARKET_OPEN or
                cls.MARKET_CLOSE <= current_time < cls.AFTER_MARKET_CLOSE)

    @classmethod
    def minutes_until_close(cls, dt: datetime | None = None) -> int:
        """Calculate minutes until market close.
        
        Args:
            dt: Datetime to check (default: now in ET)
            
        Returns:
            Minutes until close, or -1 if market closed
        """
        if dt is None:
            dt = datetime.now(cls.ET)
        elif dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc).astimezone(cls.ET)
        else:
            dt = dt.astimezone(cls.ET)
        
        if not cls.is_market_open(dt):
            return -1
        
        close_dt = dt.replace(hour=16, minute=0, second=0, microsecond=0)
        delta = (close_dt - dt).total_seconds() / 60
        return int(delta)

    @classmethod
    def minutes_until_open(cls, dt: datetime | None = None) -> int:
        """Calculate minutes until market open.
        
        Args:
            dt: Datetime to check (default: now in ET)
            
        Returns:
            Minutes until open, or -1 if market is open
        """
        if dt is None:
            dt = datetime.now(cls.ET)
        elif dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc).astimezone(cls.ET)
        else:
            dt = dt.astimezone(cls.ET)
        
        if cls.is_market_open(dt):
            return -1
        
        # Check if it's a weekend
        if dt.weekday() >= 5:
            # Calculate next Monday 9:30 AM
            days_ahead = 7 - dt.weekday()
            open_dt = dt.replace(hour=9, minute=30, second=0, microsecond=0)
            open_dt = open_dt + __import__('datetime').timedelta(days=days_ahead)
        else:
            # Market is closed during weekday, open at 9:30 AM tomorrow
            open_dt = dt.replace(hour=9, minute=30, second=0, microsecond=0)
            open_dt = open_dt + __import__('datetime').timedelta(days=1)
        
        delta = (open_dt - dt).total_seconds() / 60
        return int(delta)

    @classmethod
    def format_time_until_open(cls, dt: datetime | None = None) -> str:
        """Format time until market open as 'X days, Y hours, Z minutes'.
        
        Args:
            dt: Datetime to check (default: now in ET)
            
        Returns:
            Formatted string like "1 day, 5 hours, 30 minutes"
        """
        minutes = cls.minutes_until_open(dt)
        if minutes < 0:
            return "Market is open"
        
        days = minutes // (24 * 60)
        remaining_minutes = minutes % (24 * 60)
        hours = remaining_minutes // 60
        mins = remaining_minutes % 60
        
        parts = []
        if days > 0:
            parts.append(f"{days} day{'s' if days > 1 else ''}")
        if hours > 0:
            parts.append(f"{hours} hour{'s' if hours > 1 else ''}")
        if mins > 0 or not parts:
            parts.append(f"{mins} minute{'s' if mins != 1 else ''}")
        
        return ", ".join(parts)

    @classmethod
    def format_time_until_close(cls, dt: datetime | None = None) -> str:
        """Format time until market close as 'X hours, Y minutes'.
        
        Args:
            dt: Datetime to check (default: now in ET)
            
        Returns:
            Formatted string like "3 hours, 45 minutes"
        """
        minutes = cls.minutes_until_close(dt)
        if minutes < 0:
            return "Market is closed"
        
        hours = minutes // 60
        mins = minutes % 60
        
        parts = []
        if hours > 0:
            parts.append(f"{hours} hour{'s' if hours > 1 else ''}")
        if mins > 0 or not parts:
            parts.append(f"{mins} minute{'s' if mins != 1 else ''}")
        
        return ", ".join(parts)
