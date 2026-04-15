"""
Scheduler Module

Manages the scanner execution schedule during NSE market hours using APScheduler.
"""

import logging
import threading
import time
from datetime import datetime, time as dt_time, timedelta
from typing import Callable, Optional, Dict, Tuple
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)


class MarketScheduler:
    """
    Manages scanner execution every 15 minutes during NSE market hours.
    
    Market Hours: 09:15 AM to 03:30 PM IST
    Scan Interval: Every 15 minutes (aligned to 00, 15, 30, 45)
    Special Jobs: 3:00 PM IST update
    
    Session Awareness:
    - Pre-market (09:00-09:15): NSE pre-open session
    - Mid-day (12:00-14:00): Dead zone, reduce signals based on ATR
    - Closing (15:00+): Active moves
    """
    
    MARKET_OPEN_HOUR = 9
    MARKET_OPEN_MINUTE = 15
    MARKET_CLOSE_HOUR = 15
    MARKET_CLOSE_MINUTE = 30
    
    SCAN_INTERVAL = 15
    
    PM_UPDATE_HOUR = 15
    PM_UPDATE_MINUTE = 0
    
    AM_UPDATE_HOUR = 10
    AM_UPDATE_MINUTE = 0
    
    PRE_OPEN_START = dt_time(9, 0)
    PRE_OPEN_END = dt_time(9, 15)
    MIDDAY_START = dt_time(12, 0)
    MIDDAY_END = dt_time(14, 0)
    
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
        self.last_signal_time: Dict[str, Tuple[float, str, str]] = {}
        self.cooldown_minutes = self.DEFAULT_COOLDOWN_MINUTES
        self.market_condition = 'normal'
        
        self._signal_lock = threading.Lock()
        
        executors = {
            'default': ThreadPoolExecutor(max_workers=4)
        }
        self.scheduler = BackgroundScheduler(
            executors=executors,
            timezone=self.ist
        )
        
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
    
    def get_midday_reduce_factor(self, stocks_data: list = None) -> float:
        """
        Get signal reduction factor based on ATR/volatility.
        Returns 1.0 for normal conditions, lower for low volatility.
        """
        session = self.get_session_name()
        
        if session != 'MIDDAY' and self.market_condition != 'sideways':
            return 1.0
        
        if not stocks_data:
            return 0.5
        
        total_atr = 0
        count = 0
        for stock in stocks_data:
            if hasattr(stock, 'atr') and stock.atr:
                total_atr += stock.atr
                count += 1
        
        if count == 0:
            return 0.5
        
        avg_atr = total_atr / count
        
        if hasattr(stocks_data[0], 'current_price') and stocks_data[0].current_price:
            current_price = stocks_data[0].current_price
            atr_percent = (avg_atr / current_price) * 100 if current_price > 0 else 0
            
            if atr_percent < 0.5:
                return 0.3
            elif atr_percent < 1.0:
                return 0.5
            elif atr_percent < 2.0:
                return 0.7
            else:
                return 1.0
        
        return 0.5
    
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
    
    def is_symbol_in_cooldown(self, symbol: str, strategy_type: str = 'TREND', direction: str = 'BUY') -> bool:
        """
        Check if symbol is in cooldown period for given strategy and direction.
        """
        key = f"{symbol}_{strategy_type}_{direction}"
        
        with self._signal_lock:
            if key in self.last_signal_time:
                stored_ts, _, _ = self.last_signal_time[key]
                return self._check_cooldown_elapsed_locked(key, stored_ts)
            
            simple_key = symbol
            if simple_key in self.last_signal_time:
                stored_ts, _, _ = self.last_signal_time[simple_key]
                return self._check_cooldown_elapsed_locked(simple_key, stored_ts)
            
            return False
    
    def _check_cooldown_elapsed_locked(self, key: str, stored_ts: float) -> bool:
        """Check if cooldown has elapsed for a specific key. Must be called with lock held."""
        elapsed = time.time() - stored_ts
        cooldown_seconds = self.cooldown_minutes * 60
        
        if elapsed >= cooldown_seconds:
            if key in self.last_signal_time:
                del self.last_signal_time[key]
            return False
        
        logger.debug(f"{key} in cooldown: {elapsed/60:.1f} min elapsed")
        return True
    
    def record_signal(self, symbol: str, strategy_type: str = 'TREND', direction: str = 'BUY'):
        """Record that a signal was sent for this symbol with strategy and direction."""
        key = f"{symbol}_{strategy_type}_{direction}"
        simple_key = symbol
        
        with self._signal_lock:
            self.last_signal_time[key] = (time.time(), strategy_type, direction)
            self.last_signal_time[simple_key] = (time.time(), strategy_type, direction)
        
        logger.debug(f"Signal recorded for {symbol} ({strategy_type} {direction})")
    
    def is_market_open(self) -> bool:
        """
        Check if NSE market is currently open.
        
        Returns:
            True if market is open, False otherwise
        """
        now = datetime.now(self.ist)
        
        if now.weekday() >= 5:
            return False
        
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
            days_ahead = 7 - now.weekday()
            next_monday = now.replace(hour=0, minute=0, second=0, microsecond=0)
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
        """Set the callback function to execute for each scan."""
        self.scan_callback = callback
        logger.debug("Scan callback set")
    
    def set_pm_update_callback(self, callback: Callable):
        """Set the 3PM update callback function."""
        self.pm_update_callback = callback
        logger.debug("PM update callback set")
    
    def set_am_update_callback(self, callback: Callable):
        """Set the 10AM signal alert callback function."""
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
                logger.warning("No stock data fetched during update")
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
            
            filtered_signals = []
            for signal in all_signals:
                symbol = getattr(signal, 'symbol', '')
                strategy_type = getattr(signal, 'strategy_type', 'TREND')
                direction = getattr(signal, 'direction', 'BUY')
                
                if symbol and self.is_symbol_in_cooldown(symbol, strategy_type, direction):
                    logger.debug(f"Skipping {symbol}: in cooldown ({strategy_type} {direction})")
                    continue
                
                filtered_signals.append(signal)
            
            filtered_signals.sort(key=lambda x: getattr(x, 'rank_score', 0), reverse=True)
            
            reduce_factor = self.get_midday_reduce_factor(stocks_data)
            max_signals = max(1, int(5 * reduce_factor))
            final_signals = filtered_signals[:max_signals]
            
            for signal in final_signals:
                strategy_type = getattr(signal, 'strategy_type', 'TREND')
                direction = getattr(signal, 'direction', 'BUY')
                self.process_signal_fn(signal, strategy_type, is_startup=is_startup)
                symbol = getattr(signal, 'symbol', '')
                if symbol:
                    self.record_signal(symbol, strategy_type, direction)
            
            logger.info(f"Update processed {len(final_signals)} signals (reduce_factor: {reduce_factor})")
        except Exception as e:
            logger.error(f"Error executing scanner logic: {str(e)}")
    
    def schedule_jobs(self):
        """Schedule the scan jobs using APScheduler with CronTrigger."""
        scan_trigger = CronTrigger(
            minute='0,15,30,45',
            day_of_week='0,1,2,3,4',
            timezone=self.ist
        )
        
        self.scheduler.add_job(
            self.run_scan,
            trigger=scan_trigger,
            id='market_scan',
            name='Market Scan (every 15 min at :00, :15, :30, :45)',
            replace_existing=True
        )
        
        pm_trigger = CronTrigger(
            hour=self.PM_UPDATE_HOUR,
            minute=self.PM_UPDATE_MINUTE,
            day_of_week='0,1,2,3,4',
            timezone=self.ist
        )
        
        self.scheduler.add_job(
            self.run_pm_update,
            trigger=pm_trigger,
            id='pm_update',
            name=f'Signal Generator (daily at {self.PM_UPDATE_HOUR}:{self.PM_UPDATE_MINUTE:02d} IST)',
            replace_existing=True
        )
        
        am_trigger = CronTrigger(
            hour=self.AM_UPDATE_HOUR,
            minute=self.AM_UPDATE_MINUTE,
            day_of_week='0,1,2,3,4',
            timezone=self.ist
        )
        
        self.scheduler.add_job(
            self.run_am_update,
            trigger=am_trigger,
            id='am_update',
            name=f'Morning Signal Alert (daily at {self.AM_UPDATE_HOUR}:{self.AM_UPDATE_MINUTE:02d} IST)',
            replace_existing=True
        )
        
        logger.info("Scheduled jobs: market scan (0,15,30,45), 3PM signal generator, 10AM alert")
    
    def start(self):
        """Start the scheduler."""
        if self.running:
            logger.debug("Scheduler already running")
            return
        
        self.running = True
        self.schedule_jobs()
        
        if self.scheduler:
            self.scheduler.start()
            logger.debug("APScheduler started")
        
        logger.debug("Scheduler started")
    
    def stop(self):
        """Stop the scheduler."""
        if not self.running:
            return
        
        self.running = False
        
        if self.scheduler:
            self.scheduler.shutdown(wait=False)
        
        logger.debug("Scheduler stopped")
    
    def run_once(self):
        """Run a single scan immediately."""
        if not self.is_market_open():
            logger.debug("Market is closed. Scan will run but may not have live data.")
        
        self.run_scan()
    
    def get_status(self) -> dict:
        """Get current scheduler status."""
        jobs = self.scheduler.get_jobs()
        
        return {
            'running': self.running,
            'market_open': self.is_market_open(),
            'scheduled_jobs': len(jobs),
            'ist_time': datetime.now(self.ist).strftime("%Y-%m-%d %H:%M:%S")
        }

    def force_market_hours_scan(self):
        """Force a scan to run during market hours check."""
        if self.is_market_open():
            logger.debug("Forcing market hours scan...")
            self.run_scan()
        else:
            logger.debug("Cannot force scan - market is closed")
    
    def add_continuous_job(self, func: Callable, job_id: str = 'continuous_monitor') -> None:
        """Add continuous monitoring job."""
        from apscheduler.triggers.interval import IntervalTrigger
        
        trigger = IntervalTrigger(
            minutes=self.SCAN_INTERVAL,
            timezone=self.ist
        )
        
        self.scheduler.add_job(
            func,
            trigger=trigger,
            id=job_id,
            name=f'Continuous Monitor (every {self.SCAN_INTERVAL} min)',
            replace_existing=True
        )
        
        logger.info(f"Continuous monitoring job scheduled: every {self.SCAN_INTERVAL} minutes")
    
    def add_signal_generation_job(self, func: Callable, job_id: str = 'signal_generator') -> None:
        """Add signal generation job - runs once daily at 3:00 PM IST on weekdays."""
        trigger = CronTrigger(
            hour=self.PM_UPDATE_HOUR,
            minute=self.PM_UPDATE_MINUTE,
            day_of_week='0,1,2,3,4',
            timezone=self.ist
        )
        
        self.scheduler.add_job(
            func,
            trigger=trigger,
            id=job_id,
            name=f'Signal Generator (daily at {self.PM_UPDATE_HOUR}:{self.PM_UPDATE_MINUTE:02d} IST)',
            replace_existing=True
        )
        
        logger.info(f"Signal generation job scheduled: {self.PM_UPDATE_HOUR}:{self.PM_UPDATE_MINUTE:02d} IST on weekdays")


def create_scheduler(scan_callback: Callable) -> MarketScheduler:
    """Factory function to create and configure a scheduler."""
    scheduler = MarketScheduler()
    scheduler.set_scan_callback(scan_callback)
    return scheduler