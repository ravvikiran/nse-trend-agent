"""
Scanner Scheduler
Runs the accumulation scanner at a specific time on weekdays
Supports two modes:
- Continuous mode: every 15 minutes for monitoring
- Signal generation mode: daily at 3:00 PM IST
"""

import logging
from datetime import datetime
from typing import Callable, Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.executors.pool import ThreadPoolExecutor

logger = logging.getLogger(__name__)


class ScannerScheduler:
    """
    Scheduler for running the accumulation scanner in two modes:
    1. Continuous mode (every 15 min) - Monitoring only
    2. Signal generation mode (3:00 PM) - Generate new signals
    """
    
    def __init__(self, config: dict):
        self.config = config
        self.scheduler_config = config.get('scheduler', {})
        signal_config = config.get('signal_mode', {})
        
        # Configure scheduler
        self.timezone = self.scheduler_config.get('timezone', 'Asia/Kolkata')
        
        # Signal generation time (default 3:00 PM IST)
        self.signal_hour = signal_config.get('daily_signal_hour', 15)
        self.signal_minute = 0
        
        # Max signals per day
        self.max_signals_per_day = signal_config.get('max_signals_per_day', 3)
        
        # Scan interval for continuous monitoring (default 15 min)
        self.scan_interval_minutes = self.scheduler_config.get('scan_interval_minutes', 15)
        
        # Run days: Monday=0, Tuesday=1, ..., Friday=4
        self.run_days = self.scheduler_config.get('run_days', [1, 2, 3, 4, 5])
        
        # Configure executors
        executors = {
            'default': ThreadPoolExecutor(max_workers=4)
        }
        
        # Create scheduler
        self.scheduler = BackgroundScheduler(
            executors=executors,
            timezone=self.timezone
        )
        
        self.continuous_job = None
        self.signal_job = None
        
    def add_continuous_job(self, func: Callable, job_id: str = 'continuous_monitor') -> None:
        """
        Add continuous monitoring job - runs every 15 minutes.
        Used for tracking active signals, checking SL/Target hits.
        """
        trigger = IntervalTrigger(
            minutes=self.scan_interval_minutes,
            timezone=self.timezone
        )
        
        self.continuous_job = self.scheduler.add_job(
            func,
            trigger=trigger,
            id=job_id,
            name=f'Continuous Monitor (every {self.scan_interval_minutes} min)',
            replace_existing=True
        )
        
        logger.info(f"Continuous monitoring job scheduled: every {self.scan_interval_minutes} minutes")
    
    def add_signal_generation_job(self, func: Callable, job_id: str = 'signal_generator') -> None:
        """
        Add signal generation job - runs once daily at 3:00 PM IST.
        Generates new trading signals (max 3 per day).
        """
        trigger = CronTrigger(
            hour=self.signal_hour,
            minute=self.signal_minute,
            day_of_week=self.run_days,
            timezone=self.timezone
        )
        
        self.signal_job = self.scheduler.add_job(
            func,
            trigger=trigger,
            id=job_id,
            name=f'Signal Generator (daily at {self.signal_hour}:{self.signal_minute:02d} IST)',
            replace_existing=True
        )
        
        logger.info(f"Signal generation job scheduled: {self.signal_hour}:{self.signal_minute:02d} IST on days {self.run_days}")
    
    def add_job(self, func: Callable, job_id: str = 'scanner_job') -> None:
        """Legacy method - adds signal generation job."""
        self.add_signal_generation_job(func, job_id)
        
    def start(self) -> None:
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info(f"Scheduler started - Signal gen: {self.signal_hour}:{self.signal_minute:02d} IST, Monitor: every {self.scan_interval_minutes} min")
            
    def stop(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler stopped")
            
    def get_next_run(self) -> Optional[datetime]:
        if self.signal_job:
            return self.signal_job.next_run_time
        return None
    
    def get_status(self) -> dict:
        return {
            'running': self.scheduler.running,
            'next_signal_run': self.signal_job.next_run_time if self.signal_job else None,
            'continuous_interval': f"{self.scan_interval_minutes} min",
            'signal_time': f'{self.signal_hour}:{self.signal_minute:02d}',
            'run_days': self.run_days,
            'max_signals_per_day': self.max_signals_per_day
        }


def create_scheduler(config: dict) -> ScannerScheduler:
    return ScannerScheduler(config)