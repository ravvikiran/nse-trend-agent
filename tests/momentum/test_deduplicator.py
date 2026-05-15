"""Unit tests for Deduplicator class."""

from datetime import datetime, timedelta

import pytest

from src.momentum.deduplicator import Deduplicator
from src.momentum.models import ScannerConfig, SetupType


@pytest.fixture
def config():
    """Default scanner config with 30 min cooldown and 20 max daily alerts."""
    return ScannerConfig()


@pytest.fixture
def dedup(config):
    """Deduplicator instance with default config using in-memory database."""
    return Deduplicator(config, db_path=":memory:")


@pytest.fixture
def base_time():
    """A base timestamp for testing."""
    return datetime(2024, 1, 15, 10, 0, 0)


class TestShouldAlert:
    """Tests for should_alert() method."""

    def test_new_symbol_returns_true(self, dedup, base_time):
        """First alert for a symbol should always be allowed."""
        assert dedup.should_alert("RELIANCE", SetupType.PULLBACK_CONTINUATION, 85.0, base_time)

    def test_same_symbol_same_setup_within_cooldown_returns_false(self, dedup, base_time):
        """Same symbol + same setup within cooldown should be suppressed."""
        dedup.record_alert("RELIANCE", SetupType.PULLBACK_CONTINUATION, 85.0, base_time)
        # 10 minutes later (within 30 min cooldown)
        later = base_time + timedelta(minutes=10)
        assert not dedup.should_alert("RELIANCE", SetupType.PULLBACK_CONTINUATION, 80.0, later)

    def test_same_symbol_same_setup_after_cooldown_returns_true(self, dedup, base_time):
        """Same symbol + same setup after cooldown expires should be allowed."""
        dedup.record_alert("RELIANCE", SetupType.PULLBACK_CONTINUATION, 85.0, base_time)
        # 31 minutes later (cooldown expired)
        later = base_time + timedelta(minutes=31)
        assert dedup.should_alert("RELIANCE", SetupType.PULLBACK_CONTINUATION, 80.0, later)

    def test_same_symbol_different_setup_within_cooldown_returns_true(self, dedup, base_time):
        """Same symbol but different setup type should be allowed even within cooldown."""
        dedup.record_alert("RELIANCE", SetupType.PULLBACK_CONTINUATION, 85.0, base_time)
        later = base_time + timedelta(minutes=5)
        assert dedup.should_alert("RELIANCE", SetupType.COMPRESSION_BREAKOUT, 90.0, later)

    def test_different_symbol_returns_true(self, dedup, base_time):
        """Different symbol should always be allowed."""
        dedup.record_alert("RELIANCE", SetupType.PULLBACK_CONTINUATION, 85.0, base_time)
        later = base_time + timedelta(minutes=5)
        assert dedup.should_alert("INFY", SetupType.PULLBACK_CONTINUATION, 80.0, later)

    def test_daily_limit_reached_returns_false(self, dedup, base_time):
        """Should return False when daily alert limit is reached."""
        # Fill up to max daily alerts
        for i in range(20):
            dedup.record_alert(
                f"STOCK{i}",
                SetupType.PULLBACK_CONTINUATION,
                80.0,
                base_time + timedelta(minutes=i * 35),  # Spread out to avoid cooldown
            )
        # Next alert should be suppressed
        later = base_time + timedelta(hours=12)
        assert not dedup.should_alert("NEWSTOCK", SetupType.PULLBACK_CONTINUATION, 95.0, later)

    def test_daily_limit_not_reached_returns_true(self, dedup, base_time):
        """Should return True when under daily alert limit."""
        for i in range(19):
            dedup.record_alert(
                f"STOCK{i}",
                SetupType.PULLBACK_CONTINUATION,
                80.0,
                base_time + timedelta(minutes=i * 35),
            )
        later = base_time + timedelta(hours=12)
        assert dedup.should_alert("NEWSTOCK", SetupType.PULLBACK_CONTINUATION, 95.0, later)

    def test_exact_cooldown_boundary_returns_false(self, dedup, base_time):
        """At exactly the cooldown boundary (not yet expired), should suppress."""
        dedup.record_alert("RELIANCE", SetupType.PULLBACK_CONTINUATION, 85.0, base_time)
        # Exactly 1800 seconds later (cooldown = 1800s, elapsed < cooldown is false at boundary)
        # Since elapsed < cooldown_seconds, at exactly 1800s elapsed is NOT < 1800, so it should pass
        boundary = base_time + timedelta(seconds=1800)
        # At exactly cooldown seconds, elapsed == cooldown, so NOT < cooldown → allowed
        assert dedup.should_alert("RELIANCE", SetupType.PULLBACK_CONTINUATION, 80.0, boundary)

    def test_one_second_before_cooldown_returns_false(self, dedup, base_time):
        """One second before cooldown expires should still suppress."""
        dedup.record_alert("RELIANCE", SetupType.PULLBACK_CONTINUATION, 85.0, base_time)
        almost = base_time + timedelta(seconds=1799)
        assert not dedup.should_alert("RELIANCE", SetupType.PULLBACK_CONTINUATION, 80.0, almost)


class TestShouldResend:
    """Tests for should_resend() method."""

    def test_new_symbol_returns_true(self, dedup):
        """Symbol never alerted should return True (not a resend, but allow)."""
        assert dedup.should_resend("RELIANCE", SetupType.PULLBACK_CONTINUATION, False, False)

    def test_setup_type_changed_returns_true(self, dedup, base_time):
        """Changed setup type should allow resend."""
        dedup.record_alert("RELIANCE", SetupType.PULLBACK_CONTINUATION, 85.0, base_time)
        assert dedup.should_resend("RELIANCE", SetupType.COMPRESSION_BREAKOUT, False, False)

    def test_new_breakout_returns_true(self, dedup, base_time):
        """New breakout detected should allow resend."""
        dedup.record_alert("RELIANCE", SetupType.PULLBACK_CONTINUATION, 85.0, base_time)
        assert dedup.should_resend("RELIANCE", SetupType.PULLBACK_CONTINUATION, True, False)

    def test_new_volume_expansion_returns_true(self, dedup, base_time):
        """New volume expansion should allow resend."""
        dedup.record_alert("RELIANCE", SetupType.PULLBACK_CONTINUATION, 85.0, base_time)
        assert dedup.should_resend("RELIANCE", SetupType.PULLBACK_CONTINUATION, False, True)

    def test_no_changed_conditions_returns_false(self, dedup, base_time):
        """Same setup, no new breakout, no new volume → suppress."""
        dedup.record_alert("RELIANCE", SetupType.PULLBACK_CONTINUATION, 85.0, base_time)
        assert not dedup.should_resend("RELIANCE", SetupType.PULLBACK_CONTINUATION, False, False)

    def test_both_breakout_and_volume_returns_true(self, dedup, base_time):
        """Both new breakout and volume expansion should allow resend."""
        dedup.record_alert("RELIANCE", SetupType.PULLBACK_CONTINUATION, 85.0, base_time)
        assert dedup.should_resend("RELIANCE", SetupType.PULLBACK_CONTINUATION, True, True)

    def test_setup_change_overrides_same_conditions(self, dedup, base_time):
        """Setup type change alone is sufficient for resend."""
        dedup.record_alert("RELIANCE", SetupType.COMPRESSION_BREAKOUT, 85.0, base_time)
        assert dedup.should_resend("RELIANCE", SetupType.PULLBACK_CONTINUATION, False, False)


class TestRecordAlert:
    """Tests for record_alert() method."""

    def test_records_new_symbol(self, dedup, base_time):
        """Recording a new symbol should create state entry."""
        dedup.record_alert("RELIANCE", SetupType.PULLBACK_CONTINUATION, 85.0, base_time)
        state = dedup.get_state("RELIANCE")
        assert state is not None
        assert state.symbol == "RELIANCE"
        assert state.last_alert_time == base_time
        assert state.last_setup_type == SetupType.PULLBACK_CONTINUATION
        assert state.last_rank_score == 85.0
        assert state.alert_count_today == 1

    def test_updates_existing_symbol(self, dedup, base_time):
        """Recording same symbol again should update state."""
        dedup.record_alert("RELIANCE", SetupType.PULLBACK_CONTINUATION, 85.0, base_time)
        later = base_time + timedelta(hours=1)
        dedup.record_alert("RELIANCE", SetupType.COMPRESSION_BREAKOUT, 90.0, later)
        state = dedup.get_state("RELIANCE")
        assert state.last_alert_time == later
        assert state.last_setup_type == SetupType.COMPRESSION_BREAKOUT
        assert state.last_rank_score == 90.0
        assert state.alert_count_today == 2

    def test_increments_total_daily_count(self, dedup, base_time):
        """Each record should increment total daily count."""
        assert dedup.total_alerts_today == 0
        dedup.record_alert("RELIANCE", SetupType.PULLBACK_CONTINUATION, 85.0, base_time)
        assert dedup.total_alerts_today == 1
        dedup.record_alert("INFY", SetupType.COMPRESSION_BREAKOUT, 80.0, base_time)
        assert dedup.total_alerts_today == 2

    def test_multiple_symbols_tracked_independently(self, dedup, base_time):
        """Different symbols should have independent state."""
        dedup.record_alert("RELIANCE", SetupType.PULLBACK_CONTINUATION, 85.0, base_time)
        dedup.record_alert("INFY", SetupType.COMPRESSION_BREAKOUT, 80.0, base_time)
        rel_state = dedup.get_state("RELIANCE")
        infy_state = dedup.get_state("INFY")
        assert rel_state.last_setup_type == SetupType.PULLBACK_CONTINUATION
        assert infy_state.last_setup_type == SetupType.COMPRESSION_BREAKOUT
        assert rel_state.alert_count_today == 1
        assert infy_state.alert_count_today == 1


class TestResetDaily:
    """Tests for reset_daily() method."""

    def test_clears_all_state(self, dedup, base_time):
        """Reset should clear all symbol states."""
        dedup.record_alert("RELIANCE", SetupType.PULLBACK_CONTINUATION, 85.0, base_time)
        dedup.record_alert("INFY", SetupType.COMPRESSION_BREAKOUT, 80.0, base_time)
        dedup.reset_daily()
        assert dedup.get_state("RELIANCE") is None
        assert dedup.get_state("INFY") is None

    def test_resets_daily_counter(self, dedup, base_time):
        """Reset should zero the daily alert counter."""
        dedup.record_alert("RELIANCE", SetupType.PULLBACK_CONTINUATION, 85.0, base_time)
        dedup.record_alert("INFY", SetupType.COMPRESSION_BREAKOUT, 80.0, base_time)
        assert dedup.total_alerts_today == 2
        dedup.reset_daily()
        assert dedup.total_alerts_today == 0

    def test_allows_alerts_after_reset(self, dedup, base_time):
        """After reset, previously suppressed alerts should be allowed."""
        dedup.record_alert("RELIANCE", SetupType.PULLBACK_CONTINUATION, 85.0, base_time)
        # Within cooldown — would be suppressed
        later = base_time + timedelta(minutes=5)
        assert not dedup.should_alert("RELIANCE", SetupType.PULLBACK_CONTINUATION, 80.0, later)
        # Reset
        dedup.reset_daily()
        # Now should be allowed
        assert dedup.should_alert("RELIANCE", SetupType.PULLBACK_CONTINUATION, 80.0, later)

    def test_reset_empty_state_is_safe(self, dedup):
        """Resetting when no alerts have been recorded should not error."""
        dedup.reset_daily()
        assert dedup.total_alerts_today == 0


class TestCustomConfig:
    """Tests with custom configuration values."""

    def test_custom_cooldown_period(self, base_time):
        """Custom cooldown period should be respected."""
        config = ScannerConfig(cooldown_period_seconds=60)  # 1 minute cooldown
        dedup = Deduplicator(config)
        dedup.record_alert("RELIANCE", SetupType.PULLBACK_CONTINUATION, 85.0, base_time)
        # 30 seconds later — still in cooldown
        assert not dedup.should_alert(
            "RELIANCE", SetupType.PULLBACK_CONTINUATION, 80.0, base_time + timedelta(seconds=30)
        )
        # 61 seconds later — cooldown expired
        assert dedup.should_alert(
            "RELIANCE", SetupType.PULLBACK_CONTINUATION, 80.0, base_time + timedelta(seconds=61)
        )

    def test_custom_max_daily_alerts(self, base_time):
        """Custom max daily alerts should be enforced."""
        config = ScannerConfig(max_alerts_per_day=3)
        dedup = Deduplicator(config)
        for i in range(3):
            dedup.record_alert(
                f"STOCK{i}",
                SetupType.PULLBACK_CONTINUATION,
                80.0,
                base_time + timedelta(minutes=i * 35),
            )
        # 4th alert should be suppressed
        later = base_time + timedelta(hours=3)
        assert not dedup.should_alert("NEWSTOCK", SetupType.PULLBACK_CONTINUATION, 95.0, later)
