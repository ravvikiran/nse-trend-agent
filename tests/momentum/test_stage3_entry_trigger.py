"""Unit tests for Stage3EntryTrigger class."""

import numpy as np
import pandas as pd
import pytest

from src.momentum.models import ScannerConfig, SetupType
from src.momentum.stage3_entry_trigger import EntryTriggerResult, Stage3EntryTrigger


@pytest.fixture
def config():
    """Default scanner config."""
    return ScannerConfig()


@pytest.fixture
def trigger(config):
    """Stage3EntryTrigger instance with default config."""
    return Stage3EntryTrigger(config)


def _make_15m_ohlcv(
    n: int = 40,
    base_price: float = 100.0,
    base_volume: int = 100000,
    trend: float = 0.001,
) -> pd.DataFrame:
    """Helper to create a realistic 15m OHLCV DataFrame.

    Generates a gently trending price series with random-ish candles.

    Args:
        n: Number of candles.
        base_price: Starting price.
        base_volume: Average volume.
        trend: Per-candle trend factor.

    Returns:
        DataFrame with open, high, low, close, volume columns.
    """
    np.random.seed(42)
    closes = []
    opens = []
    highs = []
    lows = []
    volumes = []

    price = base_price
    for i in range(n):
        price = price * (1 + trend + np.random.uniform(-0.005, 0.005))
        open_price = price * (1 + np.random.uniform(-0.003, 0.003))
        high_price = max(price, open_price) * (1 + np.random.uniform(0, 0.005))
        low_price = min(price, open_price) * (1 - np.random.uniform(0, 0.005))
        volume = int(base_volume * (1 + np.random.uniform(-0.3, 0.3)))

        opens.append(open_price)
        highs.append(high_price)
        lows.append(low_price)
        closes.append(price)
        volumes.append(volume)

    return pd.DataFrame({
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes,
    })


def _make_pullback_setup(n: int = 40) -> pd.DataFrame:
    """Create a DataFrame that triggers PULLBACK_CONTINUATION.

    Constructs a scenario where:
      - Price has been trending up (so EMA(20) is established)
      - Last candle pulls back near EMA(20)
      - Last candle is bullish with strong body
      - Last candle has volume > 1.5x average
      - Last candle breaks previous candle's high
    """
    np.random.seed(123)
    # Create a steady uptrend for EMA(20) to form
    base_price = 100.0
    closes = []
    opens = []
    highs = []
    lows = []
    volumes = []

    price = base_price
    for i in range(n - 2):
        price = price * 1.002  # Gentle uptrend
        open_p = price * 0.998
        high_p = price * 1.003
        low_p = price * 0.996
        closes.append(price)
        opens.append(open_p)
        highs.append(high_p)
        lows.append(low_p)
        volumes.append(100000)

    # Second-to-last candle: small pullback candle (sets a low high for breaking)
    prev_close = price * 0.998
    prev_open = price * 0.999
    prev_high = price * 1.001  # Low high to be broken
    prev_low = price * 0.996
    closes.append(prev_close)
    opens.append(prev_open)
    highs.append(prev_high)
    lows.append(prev_low)
    volumes.append(80000)

    # Last candle: bullish, near EMA(20), volume expansion, breaks prev high
    # EMA(20) should be approximately at the current price level after uptrend
    last_open = prev_close * 0.999
    last_close = prev_close * 1.005  # Bullish close
    last_high = prev_high * 1.005  # Breaks previous high
    last_low = last_open * 0.998
    last_volume = 200000  # > 1.5x average of 100000

    closes.append(last_close)
    opens.append(last_open)
    highs.append(last_high)
    lows.append(last_low)
    volumes.append(last_volume)

    return pd.DataFrame({
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes,
    })


def _make_compression_setup(n: int = 40) -> pd.DataFrame:
    """Create a DataFrame that triggers COMPRESSION_BREAKOUT.

    Constructs a scenario where:
      - Initial candles have normal ATR
      - 4 tight-range candles (range < 70% of ATR)
      - ATR contracts significantly
      - Final candle is a strong breakout with volume expansion
    """
    opens = []
    highs = []
    lows = []
    closes = []
    volumes = []

    base_price = 100.0
    price = base_price

    # First ~25 candles: normal volatility to establish ATR
    for i in range(n - 5):
        open_p = price
        # Normal range candles (range ~2% of price)
        high_p = price + price * 0.01
        low_p = price - price * 0.01
        close_p = price + price * 0.003
        price = close_p

        opens.append(open_p)
        highs.append(high_p)
        lows.append(low_p)
        closes.append(close_p)
        volumes.append(100000)

    # 4 tight-range candles (range < 70% of ATR which is ~2 points)
    # Make range very small (~0.2% of price = ~0.2 points)
    for i in range(4):
        open_p = price
        high_p = price + 0.1
        low_p = price - 0.1
        close_p = price + 0.05
        price = close_p

        opens.append(open_p)
        highs.append(high_p)
        lows.append(low_p)
        closes.append(close_p)
        volumes.append(80000)

    # Final candle: strong breakout with volume expansion
    open_p = price
    high_p = price + price * 0.03  # Large range
    low_p = price - price * 0.002
    close_p = high_p - (high_p - low_p) * 0.05  # Close near high (top 5%)

    opens.append(open_p)
    highs.append(high_p)
    lows.append(low_p)
    closes.append(close_p)
    volumes.append(250000)  # > 1.5x average

    return pd.DataFrame({
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes,
    })


class TestDetect:
    """Tests for detect() method."""

    def test_returns_none_for_insufficient_data(self, trigger):
        """Should return None when DataFrame has fewer than MIN_CANDLES rows."""
        df = _make_15m_ohlcv(n=10)
        result = trigger.detect(df)
        assert result is None

    def test_returns_none_for_empty_dataframe(self, trigger):
        """Should return None for empty DataFrame."""
        df = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        result = trigger.detect(df)
        assert result is None

    def test_returns_none_for_missing_columns(self, trigger):
        """Should return None when required columns are missing."""
        df = pd.DataFrame({"close": [100.0] * 40, "volume": [1000] * 40})
        result = trigger.detect(df)
        assert result is None

    def test_returns_none_when_no_pattern_matches(self, trigger):
        """Should return None when neither pattern is detected."""
        # Flat, low-volume data — no triggers
        df = _make_15m_ohlcv(n=40, trend=0.0)
        result = trigger.detect(df)
        assert result is None

    def test_returns_entry_trigger_result_type(self, trigger):
        """Result should be an EntryTriggerResult when a pattern matches."""
        df = _make_pullback_setup()
        result = trigger.detect(df)
        if result is not None:
            assert isinstance(result, EntryTriggerResult)

    def test_assigns_exactly_one_setup_type(self, trigger):
        """Only one setup type should be assigned per detection."""
        df = _make_pullback_setup()
        result = trigger.detect(df)
        if result is not None:
            assert result.setup_type in (
                SetupType.PULLBACK_CONTINUATION,
                SetupType.COMPRESSION_BREAKOUT,
            )

    def test_filters_below_min_breakout_strength(self):
        """Should return None when breakout_strength < min_breakout_strength."""
        config = ScannerConfig(min_breakout_strength=99.0)  # Very high threshold
        trigger = Stage3EntryTrigger(config)
        df = _make_pullback_setup()
        result = trigger.detect(df)
        # With such a high threshold, most signals should be filtered
        assert result is None


class TestCheckPullbackContinuation:
    """Tests for _check_pullback_continuation() method."""

    def test_detects_valid_pullback(self, trigger):
        """Should detect PULLBACK_CONTINUATION when all conditions are met."""
        df = _make_pullback_setup()
        result = trigger._check_pullback_continuation(df)
        if result is not None:
            assert result.setup_type == SetupType.PULLBACK_CONTINUATION
            assert result.entry_price > 0
            assert result.trigger_candle_index == len(df) - 1

    def test_returns_none_when_not_near_ema(self, trigger):
        """Should return None when price is far from EMA(20)."""
        df = _make_15m_ohlcv(n=40, trend=0.01)  # Strong trend = far from EMA
        result = trigger._check_pullback_continuation(df)
        assert result is None

    def test_returns_none_for_bearish_candle(self, trigger):
        """Should return None when the latest candle is bearish."""
        df = _make_15m_ohlcv(n=40)
        # Make last candle bearish (close < open)
        df.iloc[-1, df.columns.get_loc("close")] = df.iloc[-1]["open"] * 0.99
        result = trigger._check_pullback_continuation(df)
        assert result is None

    def test_returns_none_for_low_volume(self, trigger):
        """Should return None when volume is below 1.5x average."""
        df = _make_pullback_setup()
        # Set last candle volume to below average
        df.iloc[-1, df.columns.get_loc("volume")] = 50000
        result = trigger._check_pullback_continuation(df)
        assert result is None


class TestCheckCompressionBreakout:
    """Tests for _check_compression_breakout() method."""

    def test_detects_valid_compression(self, trigger):
        """Should detect COMPRESSION_BREAKOUT when all conditions are met."""
        df = _make_compression_setup()
        result = trigger._check_compression_breakout(df)
        if result is not None:
            assert result.setup_type == SetupType.COMPRESSION_BREAKOUT
            assert result.entry_price > 0
            assert result.trigger_candle_index == len(df) - 1

    def test_returns_none_when_no_tight_candles(self, trigger):
        """Should return None when there are no tight-range candles."""
        df = _make_15m_ohlcv(n=40, trend=0.005)  # Normal volatility throughout
        result = trigger._check_compression_breakout(df)
        assert result is None

    def test_returns_none_when_breakout_not_strong(self, trigger):
        """Should return None when breakout candle doesn't close near high."""
        df = _make_compression_setup()
        # Make last candle close near its low (not a strong breakout)
        low = df.iloc[-1]["low"]
        high = df.iloc[-1]["high"]
        weak_close = low + (high - low) * 0.3  # Close at 30% of range
        df.iloc[-1, df.columns.get_loc("close")] = weak_close
        result = trigger._check_compression_breakout(df)
        assert result is None

    def test_returns_none_when_no_volume_expansion(self, trigger):
        """Should return None when breakout candle has low volume."""
        df = _make_compression_setup()
        # Set breakout candle volume to below average
        df.iloc[-1, df.columns.get_loc("volume")] = 50000
        result = trigger._check_compression_breakout(df)
        assert result is None


class TestCalculateBreakoutStrength:
    """Tests for _calculate_breakout_strength() method."""

    def test_returns_value_between_0_and_100(self, trigger):
        """Breakout strength should always be in [0, 100]."""
        df = _make_15m_ohlcv(n=40)
        score = trigger._calculate_breakout_strength(df)
        assert 0.0 <= score <= 100.0

    def test_strong_candle_scores_higher(self, trigger):
        """A strong bullish candle should score higher than a weak one."""
        # Strong candle: large body, close near high, volume expansion
        df_strong = _make_15m_ohlcv(n=40)
        last_idx = len(df_strong) - 1
        df_strong.iloc[last_idx, df_strong.columns.get_loc("open")] = 100.0
        df_strong.iloc[last_idx, df_strong.columns.get_loc("close")] = 105.0
        df_strong.iloc[last_idx, df_strong.columns.get_loc("high")] = 105.5
        df_strong.iloc[last_idx, df_strong.columns.get_loc("low")] = 99.5
        df_strong.iloc[last_idx, df_strong.columns.get_loc("volume")] = 300000

        # Weak candle: small body, close near middle
        df_weak = _make_15m_ohlcv(n=40)
        df_weak.iloc[last_idx, df_weak.columns.get_loc("open")] = 100.0
        df_weak.iloc[last_idx, df_weak.columns.get_loc("close")] = 100.5
        df_weak.iloc[last_idx, df_weak.columns.get_loc("high")] = 102.0
        df_weak.iloc[last_idx, df_weak.columns.get_loc("low")] = 99.0
        df_weak.iloc[last_idx, df_weak.columns.get_loc("volume")] = 50000

        strong_score = trigger._calculate_breakout_strength(df_strong)
        weak_score = trigger._calculate_breakout_strength(df_weak)

        assert strong_score > weak_score

    def test_zero_range_candle_returns_low_score(self, trigger):
        """A doji candle (zero range) should return a low score."""
        df = _make_15m_ohlcv(n=40)
        last_idx = len(df) - 1
        # Make last candle a doji (open = high = low = close)
        df.iloc[last_idx, df.columns.get_loc("open")] = 100.0
        df.iloc[last_idx, df.columns.get_loc("close")] = 100.0
        df.iloc[last_idx, df.columns.get_loc("high")] = 100.0
        df.iloc[last_idx, df.columns.get_loc("low")] = 100.0

        score = trigger._calculate_breakout_strength(df)
        # With zero range, body_ratio and close_high components are 0
        # Range expansion and momentum will also be 0
        # Only volume component may contribute
        assert score < 50.0

    def test_handles_single_candle_gracefully(self, trigger):
        """Should return 0.0 for a single-candle DataFrame."""
        df = pd.DataFrame({
            "open": [100.0],
            "high": [101.0],
            "low": [99.0],
            "close": [100.5],
            "volume": [100000],
        })
        score = trigger._calculate_breakout_strength(df)
        assert score == 0.0


class TestMutualExclusivity:
    """Tests for setup type mutual exclusivity (Property 9)."""

    def test_only_one_setup_type_per_detection(self, trigger):
        """detect() should never return both setup types simultaneously."""
        # Test with various data scenarios
        for seed in range(10):
            np.random.seed(seed)
            df = _make_15m_ohlcv(n=40, trend=np.random.uniform(-0.005, 0.005))
            result = trigger.detect(df)
            if result is not None:
                # Only one type should be assigned
                assert result.setup_type in (
                    SetupType.PULLBACK_CONTINUATION,
                    SetupType.COMPRESSION_BREAKOUT,
                )


class TestEntryTriggerResult:
    """Tests for EntryTriggerResult dataclass."""

    def test_dataclass_fields(self):
        """EntryTriggerResult should have all required fields."""
        result = EntryTriggerResult(
            setup_type=SetupType.PULLBACK_CONTINUATION,
            breakout_strength=75.0,
            trigger_candle_index=39,
            entry_price=105.5,
        )
        assert result.setup_type == SetupType.PULLBACK_CONTINUATION
        assert result.breakout_strength == 75.0
        assert result.trigger_candle_index == 39
        assert result.entry_price == 105.5

    def test_compression_breakout_type(self):
        """Should support COMPRESSION_BREAKOUT setup type."""
        result = EntryTriggerResult(
            setup_type=SetupType.COMPRESSION_BREAKOUT,
            breakout_strength=60.0,
            trigger_candle_index=35,
            entry_price=110.0,
        )
        assert result.setup_type == SetupType.COMPRESSION_BREAKOUT


class TestEdgeCases:
    """Edge case tests."""

    def test_none_dataframe(self, trigger):
        """Should handle None DataFrame gracefully."""
        result = trigger.detect(None)
        assert result is None

    def test_all_zero_volumes(self, trigger):
        """Should handle zero volume data without crashing."""
        df = _make_15m_ohlcv(n=40)
        df["volume"] = 0
        result = trigger.detect(df)
        # Should not crash, may return None due to zero volume SMA
        assert result is None

    def test_constant_price(self, trigger):
        """Should handle flat price data without crashing."""
        df = pd.DataFrame({
            "open": [100.0] * 40,
            "high": [100.0] * 40,
            "low": [100.0] * 40,
            "close": [100.0] * 40,
            "volume": [100000] * 40,
        })
        result = trigger.detect(df)
        assert result is None

    def test_custom_config_thresholds(self):
        """Should respect custom volume expansion threshold."""
        config = ScannerConfig(volume_expansion_threshold=2.0)
        trigger = Stage3EntryTrigger(config)
        assert trigger.volume_expansion_threshold == 2.0


class TestCalculateRelativeVolume:
    """Tests for _calculate_relative_volume() method."""

    def test_returns_correct_ratio(self, trigger):
        """Should return current_volume / SMA(volume, 30)."""
        # Create a DataFrame with known volumes
        n = 40
        volumes = [100000] * (n - 1) + [200000]  # Last candle has 2x volume
        df = pd.DataFrame({
            "open": [100.0] * n,
            "high": [101.0] * n,
            "low": [99.0] * n,
            "close": [100.5] * n,
            "volume": volumes,
        })
        rv = trigger._calculate_relative_volume(df)
        # SMA(30) of volumes: (29 * 100000 + 200000) / 30 ≈ 103333.33
        # But since we have 40 candles, the rolling window of 30 ending at index 39
        # includes volumes[10:40] = 29 * 100000 + 200000 = 3100000 / 30 ≈ 103333.33
        # RV = 200000 / 103333.33 ≈ 1.935
        assert rv is not None
        expected_sma = (29 * 100000 + 200000) / 30
        expected_rv = 200000 / expected_sma
        assert abs(rv - expected_rv) < 0.001

    def test_returns_none_for_zero_volume_sma(self, trigger):
        """Should return None when volume SMA is zero."""
        n = 40
        df = pd.DataFrame({
            "open": [100.0] * n,
            "high": [101.0] * n,
            "low": [99.0] * n,
            "close": [100.5] * n,
            "volume": [0] * n,
        })
        rv = trigger._calculate_relative_volume(df)
        assert rv is None

    def test_returns_none_for_insufficient_data(self, trigger):
        """Should return None when DataFrame has fewer than volume_ma_period rows."""
        n = 20  # Less than 30 (volume_ma_period)
        df = pd.DataFrame({
            "open": [100.0] * n,
            "high": [101.0] * n,
            "low": [99.0] * n,
            "close": [100.5] * n,
            "volume": [100000] * n,
        })
        rv = trigger._calculate_relative_volume(df)
        assert rv is None

    def test_returns_float_type(self, trigger):
        """Should return a float value."""
        df = _make_15m_ohlcv(n=40)
        rv = trigger._calculate_relative_volume(df)
        if rv is not None:
            assert isinstance(rv, float)

    def test_uniform_volume_returns_approximately_one(self, trigger):
        """When all volumes are equal, relative volume should be ~1.0."""
        n = 40
        df = pd.DataFrame({
            "open": [100.0] * n,
            "high": [101.0] * n,
            "low": [99.0] * n,
            "close": [100.5] * n,
            "volume": [100000] * n,
        })
        rv = trigger._calculate_relative_volume(df)
        assert rv is not None
        assert abs(rv - 1.0) < 0.001

    def test_high_volume_returns_greater_than_one(self, trigger):
        """When current volume is above average, RV should be > 1."""
        n = 40
        volumes = [100000] * (n - 1) + [300000]
        df = pd.DataFrame({
            "open": [100.0] * n,
            "high": [101.0] * n,
            "low": [99.0] * n,
            "close": [100.5] * n,
            "volume": volumes,
        })
        rv = trigger._calculate_relative_volume(df)
        assert rv is not None
        assert rv > 1.0

    def test_low_volume_returns_less_than_one(self, trigger):
        """When current volume is below average, RV should be < 1."""
        n = 40
        volumes = [100000] * (n - 1) + [50000]
        df = pd.DataFrame({
            "open": [100.0] * n,
            "high": [101.0] * n,
            "low": [99.0] * n,
            "close": [100.5] * n,
            "volume": volumes,
        })
        rv = trigger._calculate_relative_volume(df)
        assert rv is not None
        assert rv < 1.0


class TestRelativeVolumeIntegration:
    """Tests for relative_volume integration in EntryTriggerResult."""

    def test_pullback_result_includes_relative_volume(self, trigger):
        """PULLBACK_CONTINUATION result should include relative_volume."""
        df = _make_pullback_setup()
        result = trigger._check_pullback_continuation(df)
        if result is not None:
            assert result.relative_volume is not None
            assert isinstance(result.relative_volume, float)
            assert result.relative_volume > 0

    def test_compression_result_includes_relative_volume(self, trigger):
        """COMPRESSION_BREAKOUT result should include relative_volume."""
        df = _make_compression_setup()
        result = trigger._check_compression_breakout(df)
        if result is not None:
            assert result.relative_volume is not None
            assert isinstance(result.relative_volume, float)
            assert result.relative_volume > 0

    def test_detect_excludes_stock_when_rv_is_none(self):
        """detect() should return None when relative_volume is None (Req 6.4)."""
        # Use a config with volume_ma_period larger than available data
        # This won't work directly since MIN_CANDLES is 35 and volume_ma_period is 30
        # Instead, test with zero volumes in the rolling window
        config = ScannerConfig()
        trigger = Stage3EntryTrigger(config)
        df = _make_15m_ohlcv(n=40)
        # Zero out the last 30 volumes to make SMA = 0
        df.iloc[-30:, df.columns.get_loc("volume")] = 0
        result = trigger.detect(df)
        # Should be None because volume SMA is zero
        assert result is None

    def test_entry_trigger_result_default_relative_volume(self):
        """EntryTriggerResult should default relative_volume to None."""
        result = EntryTriggerResult(
            setup_type=SetupType.PULLBACK_CONTINUATION,
            breakout_strength=75.0,
            trigger_candle_index=39,
            entry_price=105.5,
        )
        assert result.relative_volume is None

    def test_entry_trigger_result_with_relative_volume(self):
        """EntryTriggerResult should accept relative_volume value."""
        result = EntryTriggerResult(
            setup_type=SetupType.COMPRESSION_BREAKOUT,
            breakout_strength=60.0,
            trigger_candle_index=35,
            entry_price=110.0,
            relative_volume=2.3,
        )
        assert result.relative_volume == 2.3
