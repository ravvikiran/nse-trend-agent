"""
Scheduler Module

Manages the scanner execution schedule during NSE market hours.
"""

import schedule
import time
import logging
import threading
from datetime import datetime, time as dt_time
from typing import Callable, Optional, Dict
import pytz

# Configure logging
logger = logging.getLogger(__name__)


class MarketScheduler:
    """
    Manages scanner execution every 15 minutes during NSE market hours.
    
    Market Hours: 09:15 AM to 03:30 PM IST
    Scan Interval: Every 15 minutes
    Special Jobs: 3:00 PM IST update
    
    Session Awareness:
    - Pre-market (09:15-09:30): High noise, skip
    - Mid-day (12:00-14:00): Dead zone, reduce signals
    - Closing (15:00+): Active moves
    """
    
    # Market hours in IST
    MARKET_OPEN_HOUR = 9
    MARKET_OPEN_MINUTE = 15
    MARKET_CLOSE_HOUR = 15
    MARKET_CLOSE_MINUTE = 30
    
    # Scan interval in minutes
    SCAN_INTERVAL = 15
    
    # 3PM update time in IST
    PM_UPDATE_HOUR = 15
    PM_UPDATE_MINUTE = 0
    
    # 10AM update time in IST (signal alert time)
    AM_UPDATE_HOUR = 10
    AM_UPDATE_MINUTE = 0
    
    # Session time ranges
    PRE_OPEN_START = dt_time(9, 15)
    PRE_OPEN_END = dt_time(9, 30)
    MIDDAY_START = dt_time(12, 0)
    MIDDAY_END = dt_time(14, 0)
    
    # Cooldown settings
    DEFAULT_COOLDOWN_MINUTES = 30
    
    def __init__(self):
        """Initialize the MarketScheduler."""
        self.running = False
        self.scheduler_thread = None
        self.scan_callback = None
        self.pm_update_callback = None
        self.am_update_callback = None
        self.ist = pytz.timezone('Asia/Kolkata')
        self.data_fetcher = None
        self.get_trend_signals_fn = None
        self.get_verc_signals_fn = None
        self.process_signal_fn = None
        self.trade_journal = None
        self.alert_service = None
        self.strategy = 'trend'
        self.stocks = []
        self.last_signal_time: Dict[str, float] = {}
        self.cooldown_minutes = self.DEFAULT_COOLDOWN_MINUTES
        self.market_condition = 'normal'
        logger.debug("MarketScheduler initialized")

    def set_scanner_components(
        self,
        data_fetcher,
        get_trend_signals_fn,
        get_verc_signals_fn,
        process_signal_fn,
        strategy='trend',
        stocks=None
    ):
        """Set scanner components for direct execution."""
        self.data_fetcher = data_fetcher
        self.get_trend_signals_fn = get_trend_signals_fn
        self.get_verc_signals_fn = get_verc_signals_fn
        self.process_signal_fn = process_signal_fn
        self.strategy = strategy
        self.stocks = stocks or []
        logger.debug("Scanner components set for PM update")

    def set_trade_journal(self, trade_journal):
        """Set trade journal for signal tracking."""
        self.trade_journal = trade_journal
        logger.debug("Trade journal set")

    def set_alert_service(self, alert_service):
        """Set alert service for Telegram notifications."""
        self.alert_service = alert_service
        logger.debug("Alert service set")
    
    def set_cooldown(self, minutes: int = 30):
        """Set cooldown period per symbol in minutes."""
        self.cooldown_minutes = minutes
        logger.debug(f"Cooldown set to {minutes} minutes")
    
    def set_market_condition(self, condition: str):
        """Set current market condition: normal, volatile, sideways."""
        valid_conditions = ['normal', 'volatile', 'sideways']
        if condition not in valid_conditions:
            logger.warning(f"Invalid condition: {condition}, using 'normal'")
            condition = 'normal'
        self.market_condition = condition
        logger.debug(f"Market condition set to: {condition}")
    
    def get_session_name(self) -> str:
        """Get current market session name."""
        now = datetime.now(self.ist)
        current_time = now.time()
        
        if self.PRE_OPEN_START <= current_time <= self.PRE_OPEN_END:
            return 'PRE_OPEN'
        
        if self.MIDDAY_START <= current_time <= self.MIDDAY_END:
            return 'MIDDAY'
        
        if current_time >= dt_time(15, 0):
            return 'CLOSING'
        
        return 'OPEN'
    
    def should_skip_session(self) -> bool:
        """Check if current session should be skipped due to high noise or dead zone."""
        session = self.get_session_name()
        
        if session == 'PRE_OPEN':
            logger.debug("Skipping pre-open: high noise")
            return True
        
        return False
    
    def should_reduce_signals(self) -> bool:
        """Check if signal count should be reduced in current session."""
        session = self.get_session_name()
        
        if session == 'MIDDAY':
            logger.debug("Reducing signals: mid-day dead zone")
            return True
        
        if self.market_condition == 'sideways':
            logger.debug("Reducing signals: market sideways")
            return True
        
        return False
    
    def is_symbol_in_cooldown(self, symbol: str) -> bool:
        """Check if symbol is in cooldown period."""
        if symbol not in self.last_signal_time:
            return False
        
        elapsed = time.time() - self.last_signal_time[symbol]
        cooldown_seconds = self.cooldown_minutes * 60
        
        if elapsed < cooldown_seconds:
            logger.debug(f"{symbol} in cooldown: {elapsed/60:.1f} min elapsed")
            return True
        
        del self.last_signal_time[symbol]
        return False
    
    def record_signal(self, symbol: str):
        """Record that a signal was sent for this symbol."""
        self.last_signal_time[symbol] = time.time()
        logger.debug(f"Signal recorded for {symbol}")
    
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
        logger.debug("Scan callback set")
    
    def set_pm_update_callback(self, callback: Callable):
        """
        Set the 3PM update callback function.
        
        Args:
            callback: Function to call for 3PM update
        """
        self.pm_update_callback = callback
        logger.debug("PM update callback set")
    
    def set_am_update_callback(self, callback: Callable):
        """
        Set the 10AM signal alert callback function.
        
        Args:
            callback: Function to call for 10AM update
        """
        self.am_update_callback = callback
        logger.debug("AM update callback set")
    
    def run_scan(self):
        """Execute the scan callback if market is open."""
        if not self.is_market_open():
            logger.debug("Market is closed, skipping scan")
            return
        
        if self.should_skip_session():
            logger.debug(f"Skipping {self.get_session_name()} session")
            return
        
        if self.scan_callback:
            try:
                logger.debug("Executing scheduled scan...")
                self.scan_callback()
                logger.debug("Scan completed")
            except Exception as e:
                logger.error(f"Error during scheduled scan: {str(e)}")
        else:
            logger.debug("No scan callback set")
    
    def run_pm_update(self):
        """Execute 3PM update: trigger scanner, get signals, use trade journal for deduplication."""
        try:
            if not self.is_market_open():
                logger.debug("Market is closed, skipping 3PM update")
                return
            
            if self._has_scanner_components():
                logger.info("Executing 3PM update with scanner components...")
                self._execute_scanner_logic(is_startup=False)
                logger.info("3PM update completed successfully")
            elif self.pm_update_callback:
                logger.info("Executing 3PM update via callback...")
                self.pm_update_callback()
                logger.info("3PM update completed via callback")
            else:
                logger.warning("No scanner components or callback set for PM update")
        except Exception as e:
            logger.error(f"Error during 3PM update: {str(e)}")
    
    def run_am_update(self):
        """Execute 10AM signal alert: scan and send signals to Telegram."""
        try:
            if not self.is_market_open():
                logger.debug("Market is closed, skipping 10AM update")
                return
            
            if self._has_scanner_components():
                logger.info("Executing 10AM signal alert with scanner components...")
                self._execute_scanner_logic(is_startup=False)
                logger.info("10AM signal alert completed successfully")
            elif self.am_update_callback:
                logger.info("Executing 10AM update via callback...")
                self.am_update_callback()
                logger.info("10AM update completed via callback")
            else:
                logger.warning("No scanner components or callback set for AM update")
        except Exception as e:
            logger.error(f"Error during 10AM update: {str(e)}")

    def _has_scanner_components(self) -> bool:
        """Check if all required scanner components are set."""
        return (
            self.data_fetcher is not None
            and self.get_trend_signals_fn is not None
            and self.process_signal_fn is not None
            and self.trade_journal is not None
        )

    def _execute_scanner_logic(self, is_startup: bool = False):
        """Execute scanner logic: fetch data, get signals, process with trade journal."""
        try:
            stocks_data = self.data_fetcher.fetch_multiple_stocks(self.stocks)
            if not stocks_data:
                logger.warning("No stock data fetched during PM update")
                return
            
            all_signals = []
            
            if self.strategy in ['trend', 'all']:
                trend_signals = self.get_trend_signals_fn(stocks_data)
                for signal in trend_signals:
                    signal.strategy_type = 'TREND'
                    all_signals.append(signal)
            
            if self.strategy in ['verc', 'all'] and self.get_verc_signals_fn:
                verc_signals = self.get_verc_signals_fn(stocks_data)
                for signal in verc_signals:
                    signal.strategy_type = 'VERC'
                    all_signals.append(signal)
            
            all_signals.sort(key=lambda x: getattr(x, 'rank_score', 0), reverse=True)
            
            filtered_signals = []
            for signal in all_signals:
                symbol = getattr(signal, 'symbol', '')
                if symbol and self.is_symbol_in_cooldown(symbol):
                    logger.debug(f"Skipping {symbol}: in cooldown")
                    continue
                filtered_signals.append(signal)
                if len(filtered_signals) >= 5:
                    break
            
            reduce_factor = 0.5 if self.should_reduce_signals() else 1.0
            max_signals = max(1, int(5 * reduce_factor))
            final_signals = filtered_signals[:max_signals]
            
            for signal in final_signals:
                strategy_type = signal.strategy_type if hasattr(signal, 'strategy_type') and signal.strategy_type else 'TREND'
                self.process_signal_fn(signal, strategy_type, is_startup=is_startup)
                symbol = getattr(signal, 'symbol', '')
                if symbol:
                    self.record_signal(symbol)
            
            logger.info(f"PM update processed {len(final_signals)} signals (reduced: {reduce_factor < 1.0})")
        except Exception as e:
            logger.error(f"Error executing scanner logic: {str(e)}")
    
    def schedule_jobs(self):
        """Schedule the scan jobs."""
        # Schedule scans every 15 minutes during market hours
        # Each scan will check if it's 3PM and run signal generation
        schedule.every(self.SCAN_INTERVAL).minutes.do(self.run_scan)
        
        # Schedule 3PM update (15:00 IST) - calls run_signal_generation
        schedule.every().day.at("15:00").do(self.run_pm_update)
        
        logger.debug(f"Scheduled scans every {self.SCAN_INTERVAL} minutes during market hours")
        logger.debug("Scheduled 3PM signal generation job")
    
    def start(self):
        """Start the scheduler in a background thread."""
        if self.running:
            logger.debug("Scheduler already running")
            return
        
        self.running = True
        self.schedule_jobs()
        
        # Start scheduler in background thread
        self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.scheduler_thread.start()
        
        logger.debug("Scheduler started in background")
    
    def stop(self):
        """Stop the scheduler."""
        if not self.running:
            return
        
        self.running = False
        schedule.clear()
        
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        
        logger.debug("Scheduler stopped")
    
    def _run_scheduler(self):
        """Run the scheduler loop."""
        logger.debug("Scheduler loop started")
        
        while self.running:
            # Check if market is open
            if self.is_market_open():
                # Run pending scheduled jobs
                schedule.run_pending()
            else:
                # Market is closed, wait and check again
                wait_time = self.get_time_until_market_open()
                if wait_time:
                    logger.debug(f"Market closed. Waiting {wait_time/60:.1f} minutes until open")
                    time.sleep(min(wait_time, 60))  # Check at least every minute
            
            # Sleep for a bit to avoid CPU spinning
            time.sleep(1)
        
        logger.debug("Scheduler loop exited")
    
    def run_once(self):
        """
        Run a single scan immediately.
        Used for testing or manual triggers.
        """
        if not self.is_market_open():
            logger.debug("Market is closed. Scan will run but may not have live data.")
        
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
            logger.debug("Forcing market hours scan...")
            self.run_scan()
        else:
            logger.debug("Cannot force scan - market is closed")
    
    def add_continuous_job(self, func: Callable, job_id: str = 'continuous_monitor') -> None:
        """
        Add continuous monitoring job - runs every 15 minutes during market hours.
        Used for tracking active signals, checking SL/Target hits.
        """
        from apscheduler.triggers.interval import IntervalTrigger
        
        scan_interval = self.SCAN_INTERVAL
        
        trigger = IntervalTrigger(
            minutes=scan_interval,
            timezone=self.ist
        )
        
        self.scheduler.add_job(
            func,
            trigger=trigger,
            id=job_id,
            name=f'Continuous Monitor (every {scan_interval} min)',
            replace_existing=True
        )
        
        logger.info(f"Continuous monitoring job scheduled: every {scan_interval} minutes")
    
    def add_signal_generation_job(self, func: Callable, job_id: str = 'signal_generator') -> None:
        """
        Add signal generation job - runs once daily at 3:00 PM IST.
        Generates new trading signals (max 3 per day).
        """
        from apscheduler.triggers.cron import CronTrigger
        
        trigger = CronTrigger(
            hour=self.PM_UPDATE_HOUR,
            minute=self.PM_UPDATE_MINUTE,
            timezone=self.ist
        )
        
        self.scheduler.add_job(
            func,
            trigger=trigger,
            id=job_id,
            name=f'Signal Generator (daily at {self.PM_UPDATE_HOUR}:{self.PM_UPDATE_MINUTE:02d} IST)',
            replace_existing=True
        )
        
        logger.info(f"Signal generation job scheduled: {self.PM_UPDATE_HOUR}:{self.PM_UPDATE_MINUTE:02d} IST")


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
