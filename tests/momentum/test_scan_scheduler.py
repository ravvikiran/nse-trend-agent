"""Unit tests for ScanScheduler class."""

import asyncio
from datetime import date, time, datetime, timedelta, timezone

import pytest

from src.momentum.scan_scheduler import ScanScheduler, IST, NSE_HOLIDAYS
from src.momentum.models import ScannerConfig


def _run(coro):
    """Helper to run async coroutines in sync tests."""
    return asyncio.run(coro)


@pytest.fixture
def config():
    """Default scanner config."""
    return ScannerConfig()


@pytest.fixture
def scan_log():
    """List to track scan callback invocations."""
    return []


@pytest.fixture
def pre_market_log():
    """List to track pre-market callback invocations."""
    return []


@pytest.fixture
def scheduler(config, scan_log, pre_market_log):
    """ScanScheduler with tracking callbacks."""

    async def scan_cb():
        scan_log.append(datetime.now(IST))

    async def pre_market_cb():
        pre_market_log.append(datetime.now(IST))

    return ScanScheduler(config, scan_cb, pre_market_callback=pre_market_cb)


class TestTimeConfiguration:
    """Tests for time parsing and configuration."""

    def test_default_market_open(self, scheduler):
        """Market open should be 09:15 IST."""
        assert scheduler.market_open == time(9, 15)

    def test_default_market_close(self, scheduler):
        """Market close should be 15:30 IST."""
        assert scheduler.market_close == time(15, 30)

    def test_default_first_scan_time(self, scheduler):
        """First scan should be at 09:30 IST."""
        assert scheduler.first_scan_time == time(9, 30)

    def test_default_pre_market_time(self, scheduler):
        """Pre-market preparation should be at 09:00 IST."""
        assert scheduler.pre_market_time == time(9, 0)

    def test_default_scan_interval(self, scheduler):
        """Scan interval should be 120 seconds (2 minutes)."""
        assert scheduler.scan_interval_seconds == 120

    def test_custom_config_times(self, scan_log):
        """Custom config times should be parsed correctly."""
        config = ScannerConfig(
            scan_interval_seconds=60,
            market_open="09:30",
            market_close="15:00",
            pre_market_time="08:45",
        )

        async def noop():
            pass

        s = ScanScheduler(config, noop)
        assert s.market_open == time(9, 30)
        assert s.market_close == time(15, 0)
        assert s.pre_market_time == time(8, 45)
        assert s.scan_interval_seconds == 60


class TestIsMarketDay:
    """Tests for is_market_day() method."""

    def test_weekday_not_holiday_is_market_day(self, scheduler):
        """A regular weekday should be a market day."""
        # Monday Dec 2, 2024
        assert scheduler.is_market_day(date(2024, 12, 2)) is True

    def test_all_weekdays_are_market_days(self, scheduler):
        """Monday through Friday should be market days (if not holidays)."""
        # Week of Dec 2-6, 2024 (Mon-Fri, no holidays)
        for day in range(2, 7):
            assert scheduler.is_market_day(date(2024, 12, day)) is True

    def test_saturday_is_not_market_day(self, scheduler):
        """Saturday should not be a market day."""
        assert scheduler.is_market_day(date(2024, 12, 7)) is False

    def test_sunday_is_not_market_day(self, scheduler):
        """Sunday should not be a market day."""
        assert scheduler.is_market_day(date(2024, 12, 8)) is False

    def test_republic_day_2024_is_not_market_day(self, scheduler):
        """Republic Day (Jan 26) should not be a market day."""
        assert scheduler.is_market_day(date(2024, 1, 26)) is False

    def test_independence_day_2024_is_not_market_day(self, scheduler):
        """Independence Day (Aug 15) should not be a market day."""
        assert scheduler.is_market_day(date(2024, 8, 15)) is False

    def test_christmas_2024_is_not_market_day(self, scheduler):
        """Christmas (Dec 25) should not be a market day."""
        assert scheduler.is_market_day(date(2024, 12, 25)) is False

    def test_diwali_2024_is_not_market_day(self, scheduler):
        """Diwali (Oct 31, 2024) should not be a market day."""
        assert scheduler.is_market_day(date(2024, 10, 31)) is False

    def test_gandhi_jayanti_2024_is_not_market_day(self, scheduler):
        """Gandhi Jayanti (Oct 2) should not be a market day."""
        assert scheduler.is_market_day(date(2024, 10, 2)) is False

    def test_holi_2025_is_not_market_day(self, scheduler):
        """Holi 2025 (Mar 14) should not be a market day."""
        assert scheduler.is_market_day(date(2025, 3, 14)) is False

    def test_republic_day_2025_is_not_market_day(self, scheduler):
        """Republic Day 2025 (Jan 26) should not be a market day."""
        assert scheduler.is_market_day(date(2025, 1, 26)) is False

    def test_holiday_on_weekend_still_not_market_day(self, scheduler):
        """A holiday that falls on a weekend is still not a market day."""
        # Find a holiday that falls on a weekend (if any)
        for holiday in NSE_HOLIDAYS:
            if holiday.weekday() >= 5:
                assert scheduler.is_market_day(holiday) is False
                break


class TestMarketHoursChecks:
    """Tests for internal market hours helper methods."""

    def test_during_market_hours_at_open(self, scheduler):
        """09:15 should be during market hours."""
        assert scheduler._is_during_market_hours(time(9, 15)) is True

    def test_during_market_hours_at_close(self, scheduler):
        """15:30 should be during market hours."""
        assert scheduler._is_during_market_hours(time(15, 30)) is True

    def test_during_market_hours_midday(self, scheduler):
        """12:00 should be during market hours."""
        assert scheduler._is_during_market_hours(time(12, 0)) is True

    def test_before_market_open_not_during_hours(self, scheduler):
        """09:14 should not be during market hours."""
        assert scheduler._is_during_market_hours(time(9, 14)) is False

    def test_after_market_close_not_during_hours(self, scheduler):
        """15:31 should not be during market hours."""
        assert scheduler._is_during_market_hours(time(15, 31)) is False

    def test_early_morning_not_during_hours(self, scheduler):
        """08:00 should not be during market hours."""
        assert scheduler._is_during_market_hours(time(8, 0)) is False

    def test_after_first_scan_time_at_930(self, scheduler):
        """09:30 should be at/after first scan time."""
        assert scheduler._is_after_first_scan_time(time(9, 30)) is True

    def test_after_first_scan_time_at_931(self, scheduler):
        """09:31 should be after first scan time."""
        assert scheduler._is_after_first_scan_time(time(9, 31)) is True

    def test_before_first_scan_time(self, scheduler):
        """09:29 should be before first scan time."""
        assert scheduler._is_after_first_scan_time(time(9, 29)) is False

    def test_pre_market_time_at_900(self, scheduler):
        """09:00 should be pre-market time."""
        assert scheduler._is_pre_market_time(time(9, 0)) is True

    def test_pre_market_time_at_910(self, scheduler):
        """09:10 should be pre-market time."""
        assert scheduler._is_pre_market_time(time(9, 10)) is True

    def test_pre_market_time_at_914(self, scheduler):
        """09:14 should be pre-market time."""
        assert scheduler._is_pre_market_time(time(9, 14)) is True

    def test_market_open_not_pre_market(self, scheduler):
        """09:15 (market open) should not be pre-market."""
        assert scheduler._is_pre_market_time(time(9, 15)) is False

    def test_before_pre_market_not_pre_market(self, scheduler):
        """08:59 should not be pre-market time."""
        assert scheduler._is_pre_market_time(time(8, 59)) is False


class TestPreMarketCallback:
    """Tests for pre-market preparation logic."""

    def test_pre_market_callback_called(self, config):
        """Pre-market callback should be called once."""
        pre_market_log = []

        async def scan():
            pass

        async def pre_market():
            pre_market_log.append("called")

        async def run_test():
            s = ScanScheduler(config, scan, pre_market_callback=pre_market)
            await s._perform_pre_market()
            assert len(pre_market_log) == 1

        _run(run_test())

    def test_pre_market_not_called_twice_same_day(self, config):
        """Pre-market callback should only be called once per day."""
        pre_market_log = []

        async def scan():
            pass

        async def pre_market():
            pre_market_log.append("called")

        async def run_test():
            s = ScanScheduler(config, scan, pre_market_callback=pre_market)
            await s._perform_pre_market()
            await s._perform_pre_market()
            assert len(pre_market_log) == 1

        _run(run_test())

    def test_no_pre_market_callback_skips_gracefully(self, config):
        """If no pre-market callback is set, it should skip without error."""

        async def scan():
            pass

        async def run_test():
            s = ScanScheduler(config, scan, pre_market_callback=None)
            await s._perform_pre_market()

        _run(run_test())

    def test_pre_market_error_does_not_crash(self, config):
        """Pre-market callback errors should be caught and logged."""

        async def scan():
            pass

        async def failing_pre_market():
            raise RuntimeError("Data load failed")

        async def run_test():
            s = ScanScheduler(config, scan, pre_market_callback=failing_pre_market)
            await s._perform_pre_market()
            assert s._last_pre_market_date is None

        _run(run_test())


class TestScanCycleExecution:
    """Tests for scan cycle execution."""

    def test_scan_callback_called(self, config):
        """Scan callback should be invoked during execute_scan_cycle."""
        scan_log = []

        async def scan():
            scan_log.append("scan")

        async def run_test():
            s = ScanScheduler(config, scan)
            await s._execute_scan_cycle()
            assert len(scan_log) == 1

        _run(run_test())

    def test_scan_callback_error_does_not_crash(self, config):
        """Scan callback errors should be caught and logged."""

        async def failing_scan():
            raise RuntimeError("Scan failed")

        async def run_test():
            s = ScanScheduler(config, failing_scan)
            await s._execute_scan_cycle()

        _run(run_test())


class TestStopBehavior:
    """Tests for stop() method."""

    def test_stop_sets_running_false(self, scheduler):
        """stop() should set _running to False."""
        scheduler._running = True
        scheduler.stop()
        assert scheduler._running is False

    def test_stop_before_run(self, scheduler):
        """stop() before run() should work without error."""
        scheduler.stop()
        assert scheduler._running is False


class TestNSEHolidayCalendar:
    """Tests for the NSE holiday calendar completeness."""

    def test_holidays_are_date_objects(self):
        """All holidays should be date objects."""
        for holiday in NSE_HOLIDAYS:
            assert isinstance(holiday, date)

    def test_2024_holidays_present(self):
        """Key 2024 holidays should be in the calendar."""
        assert date(2024, 1, 26) in NSE_HOLIDAYS  # Republic Day
        assert date(2024, 8, 15) in NSE_HOLIDAYS  # Independence Day
        assert date(2024, 10, 2) in NSE_HOLIDAYS  # Gandhi Jayanti
        assert date(2024, 12, 25) in NSE_HOLIDAYS  # Christmas

    def test_2025_holidays_present(self):
        """Key 2025 holidays should be in the calendar."""
        assert date(2025, 1, 26) in NSE_HOLIDAYS  # Republic Day
        assert date(2025, 8, 15) in NSE_HOLIDAYS  # Independence Day
        assert date(2025, 10, 2) in NSE_HOLIDAYS  # Gandhi Jayanti
        assert date(2025, 12, 25) in NSE_HOLIDAYS  # Christmas

    def test_holiday_count_reasonable(self):
        """Should have a reasonable number of holidays (15-20 per year)."""
        holidays_2024 = [h for h in NSE_HOLIDAYS if h.year == 2024]
        holidays_2025 = [h for h in NSE_HOLIDAYS if h.year == 2025]
        assert 14 <= len(holidays_2024) <= 20
        assert 14 <= len(holidays_2025) <= 20
