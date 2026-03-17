"""
Scheduler Module

Manages the scanner execution schedule during NSE market hours.
"""

import schedule
import time
import logging
import threading
from datetime import datetime, time as dt_time
from typing import Callable, Optional
import pytz

# Configure logging
logger = logging.getLogger(__name__)


class MarketScheduler:
    """
    Manages scanner execution every 15 minutes during market hours.
    
    Market Hours: 09:15 AM to 03:30 PM IST
    Scan Interval: Every 15 minutes
    """
    
    # Market hours in IST
    MARKET_OPEN_HOUR = 9
    MARKET_OPEN_MINUTE = 15
    MARKET_CLOSE_HOUR = 15
    MARKET_CLOSE_MINUTE = 30
    
    # Scan interval in minutes
    SCAN_INTERVAL = 15
    
    def __init__(self):
        """Initialize the MarketScheduler."""
        self.running = False
        self.scheduler_thread = None
        self.scan_callback = None
        self.ist = pytz.timezone('Asia/Kolkata')
        logger.info("MarketScheduler initialized")
    
    def is_market_open(self) -> bool:
        """
        Check if NSE market is currently open.
        
        Returns:
            True if market is open, False otherwise
        """
        now = datetime.now(self.ist)
        
        # Check if weekday (Monday=0, Sunday=6)
        if now.weekday() >= 5:  # Saturday=5, Sunday=6
            return False
        
        # Create time objects for comparison
        current_time = now.time()
        market_open = dt_time(self.MARKET_OPEN_HOUR, self.MARKET_OPEN_MINUTE)
        market_close = dt_time(self.MARKET_CLOSE_HOUR, self.MARKET_CLOSE_MINUTE)
        
        return market_open <= current_time <= market_close
    
    def get_time_until_market_open(self) -> Optional[float]:
        """
        Get seconds until market opens.
        
        Returns:
            Seconds until market open, or None if already open
        """
        now = datetime.now(self.ist)
        
        if now.weekday() >= 5:
            # Find next Monday
            days_ahead = 7 - now.weekday()
            next_monday = now.replace(hour=0, minute=0, second=0, microsecond=0)
            from datetime import timedelta
            next_monday += timedelta(days=days_ahead)
            return (next_monday - now).total_seconds()
        
        current_time = now.time()
        market_open = dt_time(self.MARKET_OPEN_HOUR, self.MARKET_OPEN_MINUTE)
        
        if current_time < market_open:
            market_open_dt = now.replace(
                hour=self.MARKET_OPEN_HOUR,
                minute=self.MARKET_OPEN_MINUTE,
                second=0,
                microsecond=0
            )
            return (market_open_dt - now).total_seconds()
        
        return None
    
    def get_time_until_market_close(self) -> Optional[float]:
        """
        Get seconds until market closes.
        
        Returns:
            Seconds until market close, or None if already closed
        """
        now = datetime.now(self.ist)
        
        if now.weekday() >= 5 or now.time() > dt_time(self.MARKET_CLOSE_HOUR, self.MARKET_CLOSE_MINUTE):
            return None
        
        market_close_dt = now.replace(
            hour=self.MARKET_CLOSE_HOUR,
            minute=self.MARKET_CLOSE_MINUTE,
            second=0,
            microsecond=0
        )
        
        return (market_close_dt - now).total_seconds()
    
    def set_scan_callback(self, callback: Callable):
        """
        Set the callback function to execute for each scan.
        
        Args:
            callback: Function to call for scanning
        """
        self.scan_callback = callback
        logger.info("Scan callback set")
    
    def run_scan(self):
        """Execute the scan callback if market is open."""
        if not self.is_market_open():
            logger.info("Market is closed, skipping scan")
            return
        
        if self.scan_callback:
            try:
                logger.info("Executing scheduled scan...")
                self.scan_callback()
                logger.info("Scan completed")
            except Exception as e:
                logger.error(f"Error during scheduled scan: {str(e)}")
        else:
            logger.warning("No scan callback set")
    
    def schedule_jobs(self):
        """Schedule the scan jobs."""
        # Schedule scans every 15 minutes during market hours
        schedule.every(self.SCAN_INTERVAL).minutes.do(self.run_scan)
        
        logger.info(f"Scheduled scans every {self.SCAN_INTERVAL} minutes during market hours")
    
    def start(self):
        """Start the scheduler in a background thread."""
        if self.running:
            logger.warning("Scheduler already running")
            return
        
        self.running = True
        self.schedule_jobs()
        
        # Start scheduler in background thread
        self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.scheduler_thread.start()
        
        logger.info("Scheduler started in background")
    
    def stop(self):
        """Stop the scheduler."""
        if not self.running:
            return
        
        self.running = False
        schedule.clear()
        
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        
        logger.info("Scheduler stopped")
    
    def _run_scheduler(self):
        """Run the scheduler loop."""
        logger.info("Scheduler loop started")
        
        while self.running:
            # Check if market is open
            if self.is_market_open():
                # Run pending scheduled jobs
                schedule.run_pending()
            else:
                # Market is closed, wait and check again
                wait_time = self.get_time_until_market_open()
                if wait_time:
                    logger.info(f"Market closed. Waiting {wait_time/60:.1f} minutes until open")
                    time.sleep(min(wait_time, 60))  # Check at least every minute
            
            # Sleep for a bit to avoid CPU spinning
            time.sleep(1)
        
        logger.info("Scheduler loop exited")
    
    def run_once(self):
        """
        Run a single scan immediately.
        Used for testing or manual triggers.
        """
        if not self.is_market_open():
            logger.warning("Market is closed. Scan will run but may not have live data.")
        
        self.run_scan()
    
    def get_status(self) -> dict:
        """
        Get current scheduler status.
        
        Returns:
            Dictionary with status information
        """
        return {
            'running': self.running,
            'market_open': self.is_market_open(),
            'next_scan': str(schedule.next_run()) if schedule.next_run() else None,
            'scheduled_jobs': len(schedule.jobs),
            'ist_time': datetime.now(self.ist).strftime("%Y-%m-%d %H:%M:%S")
        }
    
    def force_market_hours_scan(self):
        """
        Force a scan to run during market hours check.
        This can be called externally to trigger a scan.
        """
        if self.is_market_open():
            logger.info("Forcing market hours scan...")
            self.run_scan()
        else:
            logger.info("Cannot force scan - market is closed")


def create_scheduler(scan_callback: Callable) -> MarketScheduler:
    """
    Factory function to create and configure a scheduler.
    
    Args:
        scan_callback: Function to call for scanning
        
    Returns:
        Configured MarketScheduler instance
    """
    scheduler = MarketScheduler()
    scheduler.set_scan_callback(scan_callback)
    return scheduler
