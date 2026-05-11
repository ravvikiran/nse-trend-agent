"""Unit tests for MarketBreadthFilter class."""

import pandas as pd
import pytest

from src.momentum.market_breadth_filter import MarketBreadthFilter
from src.momentum.models import ScannerConfig


@pytest.fixture
def config():
    """Default scanner config with breadth_decline_ratio=1.5."""
    return ScannerConfig()


@pytest.fixture
def breadth_filter(config):
    """MarketBreadthFilter instance with default config."""
    return MarketBreadthFilter(config)


def _make_nifty_15m(closes: list[float]) -> pd.DataFrame:
    """Helper to create a NIFTY 15m DataFrame from close prices."""
    return pd.DataFrame(
        {
            "open": closes,
            "high": [c * 1.005 for c in closes],
            "low": [c * 0.995 for c in closes],
            "close": closes,
            "volume": [1000000] * len(closes),
        }
    )


class TestIsMarketHealthy:
    """Tests for is_market_healthy() method."""

    def test_healthy_when_breadth_strong_and_nifty_above_ema(self, breadth_filter):
        """Market is healthy when advancing > declining and NIFTY > EMA(20)."""
        # Advancing dominates — ratio = 100/300 = 0.33 < 1.5
        advancing = 300
        declining = 100

        # NIFTY trending up — current price above EMA(20)
        closes = [100.0 + i * 0.5 for i in range(25)]  # Uptrend
        nifty_data = _make_nifty_15m(closes)

        result = breadth_filter.is_market_healthy(advancing, declining, nifty_data)
        assert result is True

    def test_unhealthy_when_both_conditions_met(self, breadth_filter):
        """Market is unhealthy when decline ratio > 1.5 AND NIFTY < EMA(20)."""
        # Declining dominates — ratio = 400/100 = 4.0 > 1.5
        advancing = 100
        declining = 400

        # NIFTY trending down — current price below EMA(20)
        closes = [120.0 - i * 1.0 for i in range(25)]  # Downtrend
        nifty_data = _make_nifty_15m(closes)

        result = breadth_filter.is_market_healthy(advancing, declining, nifty_data)
        assert result is False

    def test_healthy_when_only_breadth_weak(self, breadth_filter):
        """Market is healthy if only breadth is weak but NIFTY is above EMA."""
        # Declining dominates — ratio = 300/100 = 3.0 > 1.5
        advancing = 100
        declining = 300

        # NIFTY trending up — current price above EMA(20)
        closes = [100.0 + i * 0.5 for i in range(25)]  # Uptrend
        nifty_data = _make_nifty_15m(closes)

        result = breadth_filter.is_market_healthy(advancing, declining, nifty_data)
        assert result is True

    def test_healthy_when_only_nifty_below_ema(self, breadth_filter):
        """Market is healthy if only NIFTY is below EMA but breadth is strong."""
        # Advancing dominates — ratio = 50/300 = 0.17 < 1.5
        advancing = 300
        declining = 50

        # NIFTY trending down — current price below EMA(20)
        closes = [120.0 - i * 1.0 for i in range(25)]  # Downtrend
        nifty_data = _make_nifty_15m(closes)

        result = breadth_filter.is_market_healthy(advancing, declining, nifty_data)
        assert result is True

    def test_healthy_when_decline_ratio_exactly_at_threshold(self, breadth_filter):
        """Market is healthy when decline ratio equals threshold (not exceeded)."""
        # Ratio = 150/100 = 1.5 — exactly at threshold, NOT exceeding
        advancing = 100
        declining = 150

        # NIFTY trending down
        closes = [120.0 - i * 1.0 for i in range(25)]
        nifty_data = _make_nifty_15m(closes)

        # Ratio must be > threshold (strictly greater), so this is healthy
        result = breadth_filter.is_market_healthy(advancing, declining, nifty_data)
        assert result is True

    def test_unhealthy_when_decline_ratio_just_above_threshold(self, breadth_filter):
        """Market is unhealthy when decline ratio just exceeds threshold."""
        # Ratio = 151/100 = 1.51 > 1.5
        advancing = 100
        declining = 151

        # NIFTY trending down
        closes = [120.0 - i * 1.0 for i in range(25)]
        nifty_data = _make_nifty_15m(closes)

        result = breadth_filter.is_market_healthy(advancing, declining, nifty_data)
        assert result is False


class TestBreadthWeakEdgeCases:
    """Tests for edge cases in breadth calculation."""

    def test_zero_advancing_with_declining(self, breadth_filter):
        """Zero advancing stocks with some declining should be weak breadth."""
        advancing = 0
        declining = 100

        # NIFTY below EMA
        closes = [120.0 - i * 1.0 for i in range(25)]
        nifty_data = _make_nifty_15m(closes)

        result = breadth_filter.is_market_healthy(advancing, declining, nifty_data)
        assert result is False

    def test_zero_advancing_zero_declining(self, breadth_filter):
        """Zero advancing and zero declining — breadth is not weak."""
        advancing = 0
        declining = 0

        # NIFTY below EMA
        closes = [120.0 - i * 1.0 for i in range(25)]
        nifty_data = _make_nifty_15m(closes)

        # No declining stocks means breadth is not weak
        result = breadth_filter.is_market_healthy(advancing, declining, nifty_data)
        assert result is True

    def test_equal_advancing_declining(self, breadth_filter):
        """Equal advancing and declining — ratio = 1.0 < 1.5, healthy."""
        advancing = 200
        declining = 200

        # NIFTY below EMA
        closes = [120.0 - i * 1.0 for i in range(25)]
        nifty_data = _make_nifty_15m(closes)

        result = breadth_filter.is_market_healthy(advancing, declining, nifty_data)
        assert result is True


class TestNiftyEMAEdgeCases:
    """Tests for edge cases in NIFTY EMA calculation."""

    def test_empty_nifty_data_assumes_healthy(self, breadth_filter):
        """Empty NIFTY data should assume healthy (cannot determine)."""
        advancing = 100
        declining = 400

        nifty_data = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        result = breadth_filter.is_market_healthy(advancing, declining, nifty_data)
        assert result is True

    def test_none_nifty_data_assumes_healthy(self, breadth_filter):
        """None NIFTY data should assume healthy."""
        advancing = 100
        declining = 400

        result = breadth_filter.is_market_healthy(advancing, declining, None)
        assert result is True

    def test_single_row_nifty_data_assumes_healthy(self, breadth_filter):
        """Single row of NIFTY data is insufficient — assume healthy."""
        advancing = 100
        declining = 400

        nifty_data = _make_nifty_15m([100.0])

        result = breadth_filter.is_market_healthy(advancing, declining, nifty_data)
        assert result is True

    def test_missing_close_column_assumes_healthy(self, breadth_filter):
        """NIFTY data without 'close' column should assume healthy."""
        advancing = 100
        declining = 400

        nifty_data = pd.DataFrame({"open": [100.0, 101.0], "volume": [1000, 1000]})

        result = breadth_filter.is_market_healthy(advancing, declining, nifty_data)
        assert result is True

    def test_nifty_flat_at_ema(self, breadth_filter):
        """NIFTY exactly at EMA(20) — not below, so healthy."""
        advancing = 100
        declining = 400

        # Flat prices — EMA(20) converges to the constant value
        closes = [100.0] * 25
        nifty_data = _make_nifty_15m(closes)

        # When price == EMA, current_price < current_ema is False
        result = breadth_filter.is_market_healthy(advancing, declining, nifty_data)
        assert result is True


class TestCustomConfig:
    """Tests for custom configuration values."""

    def test_custom_decline_ratio_threshold(self):
        """Custom decline ratio threshold should be respected."""
        config = ScannerConfig(breadth_decline_ratio=2.0)
        bf = MarketBreadthFilter(config)

        # Ratio = 180/100 = 1.8 — below custom threshold of 2.0
        advancing = 100
        declining = 180

        # NIFTY below EMA
        closes = [120.0 - i * 1.0 for i in range(25)]
        nifty_data = _make_nifty_15m(closes)

        # With threshold 2.0, ratio 1.8 is not weak
        result = bf.is_market_healthy(advancing, declining, nifty_data)
        assert result is True

    def test_custom_threshold_triggers_unhealthy(self):
        """Custom threshold should trigger unhealthy when exceeded."""
        config = ScannerConfig(breadth_decline_ratio=2.0)
        bf = MarketBreadthFilter(config)

        # Ratio = 250/100 = 2.5 > 2.0
        advancing = 100
        declining = 250

        # NIFTY below EMA
        closes = [120.0 - i * 1.0 for i in range(25)]
        nifty_data = _make_nifty_15m(closes)

        result = bf.is_market_healthy(advancing, declining, nifty_data)
        assert result is False


class TestLogging:
    """Tests for logging behavior."""

    def test_logs_warning_when_signals_suppressed(self, breadth_filter, caplog):
        """Should log a warning when market is unhealthy."""
        advancing = 100
        declining = 400

        closes = [120.0 - i * 1.0 for i in range(25)]
        nifty_data = _make_nifty_15m(closes)

        with caplog.at_level("WARNING", logger="src.momentum.market_breadth_filter"):
            breadth_filter.is_market_healthy(advancing, declining, nifty_data)

        assert "signals suppressed" in caplog.text.lower()

    def test_no_warning_when_healthy(self, breadth_filter, caplog):
        """Should not log a warning when market is healthy."""
        advancing = 300
        declining = 100

        closes = [100.0 + i * 0.5 for i in range(25)]
        nifty_data = _make_nifty_15m(closes)

        with caplog.at_level("WARNING", logger="src.momentum.market_breadth_filter"):
            breadth_filter.is_market_healthy(advancing, declining, nifty_data)

        assert "signals suppressed" not in caplog.text.lower()
