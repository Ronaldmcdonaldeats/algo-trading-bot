#!/usr/bin/env python3
"""Test script for PremarketScheduler functionality"""

import time
import datetime
from src.trading_bot.scheduler import PremarketScheduler

def test_scheduler():
    print("Testing PremarketScheduler...")
    print("=" * 80)
    
    # Create scheduler with mock data
    scheduler = PremarketScheduler(['AAPL', 'MSFT'], use_alpaca=False)
    
    # Get current time
    now = datetime.datetime.now()
    next_minute = now + datetime.timedelta(minutes=1)
    
    print(f"Current time: {now.strftime('%H:%M:%S')}")
    print(f"Scheduling fetch for: {next_minute.strftime('%H:%M:%S')}")
    print()
    
    # Schedule daily fetch
    scheduler.schedule_daily_fetch(
        hour=next_minute.hour, 
        minute=next_minute.minute
    )
    
    # Start scheduler
    scheduler.start()
    print("Scheduler started. Waiting 15 seconds...")
    print()
    
    # Wait and monitor
    start_time = time.time()
    
    while time.time() - start_time < 15:
        elapsed = int(time.time() - start_time)
        if elapsed % 10 == 0 and elapsed > 0:
            print(f"[{elapsed}s] Scheduler running...")
        
        time.sleep(1)
    
    # Stop scheduler
    scheduler.stop()
    print()
    print("Scheduler stopped")
    print("=" * 80)
    print("SUCCESS: Scheduler test completed!")

if __name__ == '__main__':
    test_scheduler()
