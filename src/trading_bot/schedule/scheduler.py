"""Scheduler for pre-market data fetching.

Runs before market open to fetch overnight and pre-market data,
ensuring the bot has fresh data when trading starts.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime, timedelta, timezone
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from trading_bot.schedule.premarket import PremarketDataFetcher, get_seconds_until_market_open

logger = logging.getLogger(__name__)


class PremarketScheduler:
    """Schedules pre-market data fetching and analysis."""

    def __init__(
        self,
        symbols: Optional[list[str]] = None,
        config_path: str = "configs/default.yaml",
        use_alpaca: bool = True,
    ):
        """Initialize scheduler.
        
        Args:
            symbols: Stock symbols to fetch data for (default: AAPL, MSFT, GOOGL)
            config_path: Path to config file
            use_alpaca: Use Alpaca API if True
        """
        self.symbols = symbols or ["AAPL", "MSFT", "GOOGL"]
        self.config_path = config_path
        self.use_alpaca = use_alpaca
        self.fetcher = PremarketDataFetcher(
            config_path=config_path,
            use_alpaca=use_alpaca,
        )
        self.scheduler = BackgroundScheduler()

    def fetch_premarket_job(self):
        """Job that runs to fetch pre-market data."""
        logger.info(f"Running pre-market fetch job at {datetime.now().strftime('%H:%M:%S')}")
        
        try:
            success = self.fetcher.prepare_for_market_open(self.symbols)
            if success:
                logger.info("[OK] Pre-market data fetch completed successfully")
            else:
                logger.warning("[WARN] Pre-market data fetch had issues")
        except Exception as e:
            logger.error(f"[FAILED] Pre-market fetch job failed: {e}")

    def schedule_daily_fetch(self, hour: int = 9, minute: int = 0):
        """Schedule daily pre-market data fetch.
        
        By default, fetches at 9:00 AM EST (30 minutes before market open).
        
        Args:
            hour: Hour to fetch (24-hour format, EST)
            minute: Minute to fetch
        """
        # Schedule for weekdays only (Mon-Fri: 0-4)
        trigger = CronTrigger(
            hour=hour,
            minute=minute,
            day_of_week="0-4",  # Monday to Friday
            timezone="America/New_York",
        )
        
        self.scheduler.add_job(
            self.fetch_premarket_job,
            trigger=trigger,
            id="premarket_fetch",
            name="Pre-market Data Fetch",
            replace_existing=True,
        )
        
        logger.info(f"[OK] Scheduled pre-market fetch at {hour:02d}:{minute:02d} EST (weekdays)")

    def schedule_frequent_updates(self, interval_minutes: int = 5):
        """Schedule frequent pre-market data updates before market open.
        
        Useful for fetching updated pre-market data multiple times before market open.
        
        Args:
            interval_minutes: Update interval in minutes
        """
        trigger = IntervalTrigger(minutes=interval_minutes)
        
        self.scheduler.add_job(
            self.fetch_premarket_job,
            trigger=trigger,
            id="premarket_updates",
            name="Pre-market Data Updates",
            replace_existing=True,
        )
        
        logger.info(f"[OK] Scheduled frequent pre-market updates every {interval_minutes} minutes")

    def start(self):
        """Start the scheduler."""
        if self.scheduler.running:
            logger.warning("Scheduler is already running")
            return
        
        self.scheduler.start()
        logger.info("[OK] Pre-market scheduler started")
        
        seconds = get_seconds_until_market_open()
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        logger.info(f"  Time until market open: {hours}h {minutes}m")

    def stop(self):
        """Stop the scheduler."""
        if not self.scheduler.running:
            logger.warning("Scheduler is not running")
            return
        
        self.scheduler.shutdown()
        logger.info("[OK] Pre-market scheduler stopped")

    def fetch_now(self):
        """Fetch pre-market data immediately (blocking)."""
        logger.info("Fetching pre-market data immediately...")
        self.fetcher.prepare_for_market_open(self.symbols)
        logger.info("[OK] Fetch completed")

    def print_jobs(self):
        """Print scheduled jobs."""
        jobs = self.scheduler.get_jobs()
        if not jobs:
            logger.info("No scheduled jobs")
            return
        
        logger.info("Scheduled jobs:")
        for job in jobs:
            logger.info(f"  - {job.name} (trigger: {job.trigger})")


def run_scheduler(
    symbols: Optional[list[str]] = None,
    fetch_now: bool = False,
    frequent_updates: bool = False,
    fetch_hour: int = 9,
    fetch_minute: int = 0,
):
    """Run the pre-market scheduler.
    
    Args:
        symbols: Stock symbols to track
        fetch_now: If True, fetch data immediately before scheduling
        frequent_updates: If True, update data every 5 minutes before market open
        fetch_hour: Hour to schedule daily fetch (EST)
        fetch_minute: Minute to schedule daily fetch
    """
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    
    symbols = symbols or ["AAPL", "MSFT", "GOOGL", "NVDA", "TSLA"]
    
    logger.info("=" * 80)
    logger.info("INITIALIZING PRE-MARKET SCHEDULER")
    logger.info("=" * 80)
    logger.info(f"Symbols: {', '.join(symbols)}")
    
    scheduler = PremarketScheduler(symbols=symbols)
    
    # Fetch data immediately if requested
    if fetch_now:
        scheduler.fetch_now()
    
    # Schedule daily fetch at specified time
    scheduler.schedule_daily_fetch(hour=fetch_hour, minute=fetch_minute)
    
    # Schedule frequent updates if requested
    if frequent_updates:
        scheduler.schedule_frequent_updates(interval_minutes=5)
    
    scheduler.print_jobs()
    scheduler.start()
    
    # Keep scheduler running
    try:
        logger.info("Press Ctrl+C to stop scheduler")
        while True:
            asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("\nShutting down scheduler...")
        scheduler.stop()
        logger.info("[OK] Scheduler stopped")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Pre-market data fetching scheduler"
    )
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=["AAPL", "MSFT", "GOOGL"],
        help="Stock symbols to track (default: AAPL MSFT GOOGL)",
    )
    parser.add_argument(
        "--fetch-now",
        action="store_true",
        help="Fetch data immediately before scheduling",
    )
    parser.add_argument(
        "--frequent-updates",
        action="store_true",
        help="Update data every 5 minutes before market open",
    )
    parser.add_argument(
        "--hour",
        type=int,
        default=9,
        help="Hour to schedule daily fetch (EST, default: 9)",
    )
    parser.add_argument(
        "--minute",
        type=int,
        default=0,
        help="Minute to schedule daily fetch (default: 0)",
    )
    
    args = parser.parse_args()
    
    run_scheduler(
        symbols=args.symbols,
        fetch_now=args.fetch_now,
        frequent_updates=args.frequent_updates,
        fetch_hour=args.hour,
        fetch_minute=args.minute,
    )
