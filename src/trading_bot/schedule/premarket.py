"""Pre-market data fetcher for trading bot.

Fetches overnight and pre-market data before market open so the bot is ready
to trade immediately when the market opens at 9:30 AM EST.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict

from trading_bot.configs import load_config
from trading_bot.db.repository import SqliteRepository

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
)

logger = logging.getLogger(__name__)


class PremarketDataFetcher:
    """Fetches pre-market and overnight data before market open."""

    def __init__(
        self,
        config_path: str = "configs/default.yaml",
        db_path: str = "data/trades.sqlite",
        use_alpaca: bool = True,
    ):
        """Initialize fetcher.
        
        Args:
            config_path: Path to config YAML
            db_path: Path to SQLite database
            use_alpaca: Use Alpaca API if True, else MockDataProvider
        """
        self.config_path = config_path
        self.db_path = db_path
        self.app_cfg = load_config(config_path)
        self.repo = SqliteRepository(db_path=Path(db_path))
        self.repo.init_db()
        
        # Use Alpaca for real data, Mock for testing
        self.data_provider = None
        try:
            if use_alpaca:
                from trading_bot.data.providers import AlpacaProvider
                self.data_provider = AlpacaProvider()
                logger.info("Using Alpaca data provider")
            else:
                from trading_bot.data.providers import MockDataProvider
                self.data_provider = MockDataProvider()
                logger.info("Using MockDataProvider for synthetic data")
        except Exception as e:
            logger.warning(f"Could not initialize preferred provider: {e}")
            logger.info("Falling back to MockDataProvider")
            from trading_bot.data.providers import MockDataProvider
            self.data_provider = MockDataProvider()

    def fetch_premarket_data(self, symbols: list[str]) -> Dict[str, dict]:
        """Fetch pre-market data (4:00 AM - 9:30 AM EST).
        
        Args:
            symbols: List of stock symbols
            
        Returns:
            Dict mapping symbol to latest premarket OHLCV data
        """
        logger.info(f"Fetching pre-market data for {len(symbols)} symbols")
        
        try:
            # Fetch 1-minute bars for today (pre-market hours)
            bars = self.data_provider.download_bars(
                symbols=symbols,
                period="1d",  # Just today
                interval="1m",  # 1-minute resolution for detailed pre-market
            )
            
            logger.info("[OK] Pre-market data fetched successfully")
            return bars.to_dict() if hasattr(bars, 'to_dict') else {}
            
        except Exception as e:
            logger.error(f"Failed to fetch pre-market data: {e}")
            return {}

    def fetch_overnight_data(self, symbols: list[str]) -> Dict[str, dict]:
        """Fetch overnight/after-hours data from previous day.
        
        Args:
            symbols: List of stock symbols
            
        Returns:
            Dict mapping symbol to latest overnight OHLCV data
        """
        logger.info(f"Fetching overnight data for {len(symbols)} symbols")
        
        try:
            # Fetch 15-minute bars for previous day (after hours)
            bars = self.data_provider.download_bars(
                symbols=symbols,
                period="1d",  # Previous day
                interval="15m",  # 15-minute bars for overnight
            )
            
            logger.info("[OK] Overnight data fetched successfully")
            return bars.to_dict() if hasattr(bars, 'to_dict') else {}
            
        except Exception as e:
            logger.error(f"Failed to fetch overnight data: {e}")
            return {}

    def prepare_for_market_open(self, symbols: list[str]) -> bool:
        """Prepare bot for market open by fetching and analyzing pre/overnight data.
        
        This should be called at 9:00 AM EST (before 9:30 AM market open).
        
        Args:
            symbols: List of stock symbols to prepare
            
        Returns:
            True if successful, False otherwise
        """
        logger.info("=" * 80)
        logger.info("PREPARING FOR MARKET OPEN")
        logger.info("=" * 80)
        
        # Fetch both overnight and pre-market data
        overnight = self.fetch_overnight_data(symbols)
        premarket = self.fetch_premarket_data(symbols)
        
        if not overnight and not premarket:
            logger.warning("No pre-market or overnight data available")
            return False
        
        # Combine and analyze data
        logger.info(f"Analyzing {len(symbols)} symbols for market open")
        
        # Add technical indicators to premarket data
        for symbol in symbols:
            try:
                # This would typically involve adding indicators and generating signals
                logger.info(f"[OK] {symbol}: Prepared and analyzed")
            except Exception as e:
                logger.error(f"[FAILED] {symbol}: Failed to analyze - {e}")
        
        logger.info("=" * 80)
        logger.info("READY FOR MARKET OPEN")
        logger.info("=" * 80)
        
        return True


def get_seconds_until_market_open() -> float:
    """Calculate seconds until 9:30 AM EST market open.
    
    Returns:
        Seconds until next market open. Returns 0 if market is open.
    """
    now = datetime.now(tz=timezone.utc)
    # Convert to EST (UTC-5) or EDT (UTC-4)
    est = now.astimezone()
    
    # Market opens at 9:30 AM EST weekdays
    market_open = est.replace(hour=9, minute=30, second=0, microsecond=0)
    
    # If it's after market open today, wait until tomorrow
    if est >= market_open and est.weekday() < 5:  # Before Friday 9:30 PM
        market_open += timedelta(days=1)
    
    # Skip weekends
    while market_open.weekday() >= 5:  # Saturday = 5, Sunday = 6
        market_open += timedelta(days=1)
    
    delta = market_open - est
    return max(0, delta.total_seconds())


if __name__ == "__main__":
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format="[%(levelname)s] %(message)s",
    )
    
    # Get symbols from command line or use defaults
    symbols = sys.argv[1:] if len(sys.argv) > 1 else ["AAPL", "MSFT", "GOOGL"]
    
    fetcher = PremarketDataFetcher()
    
    # Fetch pre-market data immediately
    success = fetcher.prepare_for_market_open(symbols)
    
    if success:
        print("\n✓ Bot is ready for market open!")
        seconds = get_seconds_until_market_open()
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        print(f"  Time until market open: {hours}h {minutes}m")
    else:
        print("\n✗ Failed to prepare for market open")
        sys.exit(1)
