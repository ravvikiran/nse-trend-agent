"""Scan scheduler for the NSE Momentum Scanner.

Manages scan cycle execution during market hours (09:15-15:30 IST) with:
- 2-minute scan intervals
- Pre-market preparation at 09:00 IST
- First scan at 09:30 IST (after first 15m candle completes)
- NSE holiday calendar awareness
- Weekday-only execution
"""

import asyncio
import logging
from datetime import date, datetime, time, timedelta, timezone
from typing import Awaitable, Callable, Optional, Set

from src.momentum.models import ScannerConfig

logger = logging.getLogger(__name__)

# IST timezone: UTC+5:30
IST = timezone(timedelta(hours=5, minutes=30))

# NSE Market Holidays 2024-2025 (major holidays)
# These are dates when NSE is closed for trading
NSE_HOLIDAYS: Set[date] = {
    # 2024 holidays
    date(2024, 1, 26),   # Republic Day
    date(2024, 3, 8),    # Maha Shivaratri
    date(2024, 3, 25),   # Holi
    date(2024, 3, 29),   # Good Friday
    date(2024, 4, 11),   # Eid ul-Fitr
    date(2024, 4, 17),   # Ram Navami
    date(2024, 4, 21),   # Mahavir Jayanti
    date(2024, 5, 23),   # Buddha Purnima
    date(2024, 6, 17),   # Eid ul-Adha
    date(2024, 7, 17),   # Muharram
    date(2024, 8, 15),   # Independence Day
    date(2024, 10, 2),   # Gandhi Jayanti
    date(2024, 10, 12),  # Dussehra
    date(2024, 10, 31),  # Diwali (Laxmi Puja)
    date(2024, 11, 1),   # Diwali (Balipratipada)
    date(2024, 11, 15),  # Guru Nanak Jayanti
    date(2024, 12, 25),  # Christmas
    # 2025 holidays
    date(2025, 1, 26),   # Republic Day
    date(2025, 2, 26),   # Maha Shivaratri
    date(2025, 3, 14),   # Holi
    date(2025, 3, 31),   # Eid ul-Fitr
    date(2025, 4, 10),   # Mahavir Jayanti
    date(2025, 4, 14),   # Dr. Ambedkar Jayanti
    date(2025, 4, 18),   # Good Friday
    date(2025, 5, 12),   # Buddha Purnima
    date(2025, 6, 7),    # Eid ul-Adha
    date(2025, 7, 6),    # Muharram
    date(2025, 8, 15),   # Independence Day
    date(2025, 8, 16),   # Janmashtami
    date(2025, 9, 5),    # Milad un-Nabi
    date(2025, 10, 2),   # Gandhi Jayanti / Dussehra
    date(2025, 10, 21),  # Diwali (Laxmi Puja)
    date(2025, 10, 22),  # Diwali (Balipratipada)
    date(2025, 11, 5),   # Guru Nanak Jayanti
    date(2025, 12, 25),  # Christmas
}


class ScanScheduler:
    """Manages scan cycle execution during NSE market hours.

    The scheduler runs an async loop that:
    1. Performs pre-market preparation at 09:00 IST (calls pre_market_callback)
    2. Waits for the first 15m candle to complete at 09:30 IST
    3. Executes scan cycles every 2 minutes from 09:30 to 15:30 IST
    4. Only runs on weekdays that are not NSE holidays
    """

    def __init__(
        self,
        config: ScannerConfig,
        scan_callback: Callable[[], Awaitable[None]],
        pre_market_callback: Optional[Callable[[], Awaitable[None]]] = None,
    ):
        """Initialize the ScanScheduler.

        Args:
            config: Scanner configuration with timing parameters.
            scan_callback: Async function to execute for each scan cycle.
            pre_market_callback: Optional async function for pre-market data loading.
        """
        self.scan_interval_seconds: int = config.scan_interval_seconds  # 120
        self.market_open: time = self._parse_time(config.market_open)  # 09:15
        self.market_close: time = self._parse_time(config.market_close)  # 15:30
        self.first_scan_time: time = time(9, 30)  # After first 15m candle completes
        self.pre_market_time: time = self._parse_time(config.pre_market_time)  # 09:00

        self._scan_callback = scan_callback
        self._pre_market_callback = pre_market_callback
        self._running: bool = False
        self._pre_market_done_today: bool = False
        self._last_pre_market_date: Optional[date] = None

    @staticmethod
    def _parse_time(time_str: str) -> time:
        """Parse a time string in HH:MM format to a time object."""
        parts = time_str.split(":")
        return time(int(parts[0]), int(parts[1]))

    def is_market_day(self, check_date: date) -> bool:
        """Check if the given date is a valid market trading day.

        A market day is a weekday (Monday-Friday) that is NOT in the
        NSE holiday calendar.

        Args:
            check_date: The date to check.

        Returns:
            True if it's a valid trading day, False otherwise.
        """
        # Weekday check: Monday=0, Friday=4, Saturday=5, Sunday=6
        if check_date.weekday() >= 5:
            return False

        # Holiday check
        if check_date in NSE_HOLIDAYS:
            return False

        return True

    def _now_ist(self) -> datetime:
        """Get current datetime in IST."""
        return datetime.now(IST)

    def _is_during_market_hours(self, current_time: time) -> bool:
        """Check if the given time is within market hours (09:15-15:30 IST)."""
        return self.market_open <= current_time <= self.market_close

    def _is_after_first_scan_time(self, current_time: time) -> bool:
        """Check if the given time is at or after the first scan time (09:30 IST)."""
        return current_time >= self.first_scan_time

    def _is_pre_market_time(self, current_time: time) -> bool:
        """Check if the given time is at or after pre-market time but before market open."""
        return self.pre_market_time <= current_time < self.market_open

    async def _perform_pre_market(self) -> None:
        """Execute pre-market preparation if callback is set.

        Pre-market preparation includes:
        - Preloading stock universe
        - Fetching previous day data
        - Loading sector indices
        - Loading NIFTY data
        """
        if self._pre_market_callback is None:
            logger.debug("No pre-market callback configured, skipping.")
            return

        today = self._now_ist().date()
        if self._last_pre_market_date == today:
            logger.debug("Pre-market preparation already done today.")
            return

        logger.info("Starting pre-market preparation at %s IST", self._now_ist().strftime("%H:%M:%S"))
        try:
            await self._pre_market_callback()
            self._last_pre_market_date = today
            self._pre_market_done_today = True
            logger.info("Pre-market preparation completed successfully.")
        except Exception as e:
            logger.error("Pre-market preparation failed: %s", e)
            # Continue anyway — scanner can work with stale/cached data

    async def _execute_scan_cycle(self) -> None:
        """Execute a single scan cycle via the scan callback."""
        logger.info("Executing scan cycle at %s IST", self._now_ist().strftime("%H:%M:%S"))
        try:
            await self._scan_callback()
        except Exception as e:
            logger.error("Scan cycle failed: %s", e)

    async def _sleep_until(self, target_time: time) -> None:
        """Sleep until the specified IST time today.

        If the target time has already passed today, returns immediately.

        Args:
            target_time: The target time in IST to sleep until.
        """
        now = self._now_ist()
        target_dt = now.replace(
            hour=target_time.hour,
            minute=target_time.minute,
            second=0,
            microsecond=0,
        )

        if target_dt <= now:
            return

        sleep_seconds = (target_dt - now).total_seconds()
        logger.debug("Sleeping %.1f seconds until %s IST", sleep_seconds, target_time.strftime("%H:%M"))
        await asyncio.sleep(sleep_seconds)

    async def run(self) -> None:
        """Run scan cycles during market hours, then exit.

        Designed for cron-based deployment (e.g., Railway cron job):
        - Cron starts the process at 09:00 IST on market days
        - Process runs pre-market prep, then scans every 2 minutes
        - Process exits after market close (15:30 IST)
        - No compute charges outside market hours

        Flow:
        1. Check if today is a market day — exit immediately if not
        2. Perform pre-market preparation
        3. Wait until 09:30 IST (first 15m candle completes)
        4. Execute scan cycles every 2 minutes until 15:30 IST
        5. Exit cleanly after market close
        """
        self._running = True
        now = self._now_ist()
        today = now.date()
        current_time = now.time()

        logger.info("ScanScheduler started. Scan interval: %ds", self.scan_interval_seconds)

        # Check if today is a market day — exit if not
        if not self.is_market_day(today):
            logger.info(
                "Today (%s) is not a market day. Exiting (cron will restart on next market day).",
                today.isoformat(),
            )
            return

        # If we're already past market close, exit
        if current_time > self.market_close:
            logger.info("Market already closed for today. Exiting.")
            return

        # Pre-market preparation
        if current_time < self.first_scan_time:
            await self._perform_pre_market()
            # Wait until first scan time (09:30 IST)
            await self._sleep_until(self.first_scan_time)

        # Late start — still do pre-market if not done
        if self._last_pre_market_date != today:
            await self._perform_pre_market()

        # Main scan loop: run until market close
        logger.info("Entering scan loop (until %s IST)", self.market_close.strftime("%H:%M"))

        while self._running:
            now = self._now_ist()
            current_time = now.time()

            # Exit after market close
            if current_time > self.market_close:
                logger.info("Market closed (15:30 IST). Exiting process.")
                break

            # Execute scan cycle
            await self._execute_scan_cycle()

            # Sleep for the scan interval
            await asyncio.sleep(self.scan_interval_seconds)

        logger.info("ScanScheduler finished for today.")

    def stop(self) -> None:
        """Stop the scheduler loop.

        The loop will exit after the current sleep/cycle completes.
        """
        self._running = False
        logger.info("ScanScheduler stop requested.")
