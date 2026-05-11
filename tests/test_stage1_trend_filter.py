"""
Unit tests for Stage1TrendFilter.

Tests cover:
- Bullish classification (all 3 conditions must hold)
- Rejection when any single condition fails
- EMA slope calculation correctness
- Trend quality score range [0, 100]
- Edge cases: empty data, insufficient data, NaN values
"""

import sys
import os

import numpy as np
import pandas as pd
import pytest

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.momentum.stage1_trend_filter import Stage1TrendFilter
from src.momentum.models import ScannerConfig


def _make_uptrending_df(n_rows: int = 250, base_price: float = 100.0) -> pd.DataFrame:
    """Create a DataFrame with a clear uptrend (all bullish conditions met).

    Generates a steadily rising price series that will produce:
    - Price > EMA(200)
    - EMA(20) > EMA(50)
    - EMA(200) slope > 0
    """
    # Steady uptrend with small noise
    np.random.seed(42)
    prices = base_price + np.arange(n_rows) * 0.5 + np.random.normal(0, 0.1, n_rows)
    volumes = np.random.randint(100000, 500000, n_rows)

    df = pd.DataFrame(
        {
            "open": prices - 0.2,
            "high": prices + 0.3,
            "low": prices - 0.4,
            "close": prices,
            "volume": volumes,
        }
    )
    return df


def _make_downtrending_df(n_rows: int = 250, base_price: float = 200.0) -> pd.DataFrame:
    """Create a DataFrame with a clear downtrend (fails bullish conditions)."""
    np.random.seed(42)
    prices = base_price - np.arange(n_rows) * 0.5 + np.random.normal(0, 0.1, n_rows)
    volumes = np.random.randint(100000, 500000, n_rows)

    df = pd.DataFrame(
        {
            "open": prices + 0.2,
            "high": prices + 0.3,
            "low": prices - 0.4,
            "close": prices,
            "volume": volumes,
        }
    )
    return df


def _make_flat_df(n_rows: int = 250, base_price: float = 100.0) -> pd.DataFrame:
    """Create a DataFrame with flat/sideways price action."""
    np.random.seed(42)
    prices = base_price + np.random.normal(0, 0.5, n_rows)
    volumes = np.random.randint(100000, 500000, n_rows)

    df = pd.DataFrame(
        {
            "open": prices - 0.1,
            "high": prices + 0.2,
            "low": prices - 0.2,
            "close": prices,
            "volume": volumes,
        }
    )
    return df


class TestStage1TrendFilterInit:
    """Test initialization and configuration."""

    def test_default_config(self):
        f = Stage1TrendFilter()
        assert f.ema_fast == 20
        assert f.ema_medium == 50
        assert f.ema_slow == 200
        assert f.slope_lookback == 5

    def test_custom_config(self):
        config = ScannerConfig(ema_fast=10, ema_medium=30, ema_slow=100, ema_slope_lookback=3)
        f = Stage1TrendFilter(config=config)
        assert f.ema_fast == 10
        assert f.ema_medium == 30
        assert f.ema_slow == 100
        assert f.slope_lookback == 3


class TestStage1Filter:
    """Test the filter() method."""

    def test_uptrending_stock_passes(self):
        """A stock in a clear uptrend should pass the filter."""
        f = Stage1TrendFilter()
        df = _make_uptrending_df()
        result = f.filter({"RELIANCE": df})
        assert "RELIANCE" in result

    def test_downtrending_stock_fails(self):
        """A stock in a clear downtrend should fail the filter."""
        f = Stage1TrendFilter()
        df = _make_downtrending_df()
        result = f.filter({"INFY": df})
        assert "INFY" not in result

    def test_multiple_stocks_mixed(self):
        """Filter correctly separates bullish from non-bullish stocks."""
        f = Stage1TrendFilter()
        stocks = {
            "BULL1": _make_uptrending_df(base_price=100),
            "BEAR1": _make_downtrending_df(base_price=200),
            "BULL2": _make_uptrending_df(base_price=150),
            "FLAT1": _make_flat_df(),
        }
        result = f.filter(stocks)
        assert "BULL1" in result
        assert "BULL2" in result
        assert "BEAR1" not in result

    def test_empty_input(self):
        """Empty input returns empty list."""
        f = Stage1TrendFilter()
        result = f.filter({})
        assert result == []

    def test_insufficient_data_skipped(self):
        """Stocks with insufficient data are skipped."""
        f = Stage1TrendFilter()
        short_df = pd.DataFrame(
            {"open": [100], "high": [101], "low": [99], "close": [100.5], "volume": [1000]}
        )
        result = f.filter({"SHORT": short_df})
        assert result == []

    def test_empty_dataframe_skipped(self):
        """Empty DataFrame is skipped."""
        f = Stage1TrendFilter()
        result = f.filter({"EMPTY": pd.DataFrame()})
        assert result == []

    def test_none_dataframe_skipped(self):
        """None DataFrame is skipped gracefully."""
        f = Stage1TrendFilter()
        result = f.filter({"NONE": None})
        assert result == []


class TestBullishConditions:
    """Test individual bullish conditions."""

    def test_price_below_ema200_fails(self):
        """If price < EMA(200), stock should fail even if other conditions hold."""
        # Create a series that rises then drops at the end
        np.random.seed(42)
        n = 250
        prices = np.concatenate([
            100 + np.arange(230) * 0.5,  # uptrend
            100 + 230 * 0.5 - np.arange(20) * 5,  # sharp drop at end
        ])
        df = pd.DataFrame({
            "open": prices - 0.2,
            "high": prices + 0.3,
            "low": prices - 0.4,
            "close": prices,
            "volume": np.random.randint(100000, 500000, n),
        })
        f = Stage1TrendFilter()
        result = f.filter({"DROP": df})
        # After a sharp drop, price should be below EMA(200)
        assert "DROP" not in result


class TestEMASlopeCalculation:
    """Test EMA(200) slope calculation."""

    def test_positive_slope_in_uptrend(self):
        """Uptrending data should produce positive EMA(200) slope."""
        f = Stage1TrendFilter()
        df = _make_uptrending_df()
        _, _, ema_200 = f._calculate_emas(df)
        slope = f._calculate_ema_slope(ema_200)
        assert slope > 0

    def test_negative_slope_in_downtrend(self):
        """Downtrending data should produce negative EMA(200) slope."""
        f = Stage1TrendFilter()
        df = _make_downtrending_df()
        _, _, ema_200 = f._calculate_emas(df)
        slope = f._calculate_ema_slope(ema_200)
        assert slope < 0

    def test_slope_formula_correctness(self):
        """Verify slope = (EMA200_current - EMA200_5_ago) / 5."""
        f = Stage1TrendFilter()
        df = _make_uptrending_df()
        _, _, ema_200 = f._calculate_emas(df)

        expected_slope = (ema_200.iloc[-1] - ema_200.iloc[-6]) / 5
        actual_slope = f._calculate_ema_slope(ema_200)
        assert abs(actual_slope - expected_slope) < 1e-10


class TestTrendQualityScore:
    """Test calculate_trend_quality_score() method."""

    def test_score_in_range(self):
        """Score should always be between 0 and 100."""
        f = Stage1TrendFilter()
        df = _make_uptrending_df()
        score = f.calculate_trend_quality_score(df)
        assert 0 <= score <= 100

    def test_uptrend_has_positive_score(self):
        """A clear uptrend should have a meaningful positive score."""
        f = Stage1TrendFilter()
        df = _make_uptrending_df()
        score = f.calculate_trend_quality_score(df)
        assert score > 0

    def test_downtrend_has_low_score(self):
        """A downtrend should have a low score (alignment and slope are negative)."""
        f = Stage1TrendFilter()
        df = _make_downtrending_df()
        score = f.calculate_trend_quality_score(df)
        # Downtrend: negative spreads get clamped to 0, so score should be very low
        assert score < 20

    def test_stronger_uptrend_scores_higher(self):
        """A steeper uptrend should score higher than a mild one."""
        f = Stage1TrendFilter()

        # Mild uptrend
        np.random.seed(42)
        mild_prices = 100 + np.arange(250) * 0.1
        mild_df = pd.DataFrame({
            "open": mild_prices - 0.1,
            "high": mild_prices + 0.2,
            "low": mild_prices - 0.2,
            "close": mild_prices,
            "volume": np.random.randint(100000, 500000, 250),
        })

        # Strong uptrend
        np.random.seed(42)
        strong_prices = 100 + np.arange(250) * 1.0
        strong_df = pd.DataFrame({
            "open": strong_prices - 0.1,
            "high": strong_prices + 0.2,
            "low": strong_prices - 0.2,
            "close": strong_prices,
            "volume": np.random.randint(100000, 500000, 250),
        })

        mild_score = f.calculate_trend_quality_score(mild_df)
        strong_score = f.calculate_trend_quality_score(strong_df)
        assert strong_score > mild_score

    def test_insufficient_data_returns_zero(self):
        """Insufficient data should return 0."""
        f = Stage1TrendFilter()
        short_df = pd.DataFrame({"close": [100, 101, 102]})
        score = f.calculate_trend_quality_score(short_df)
        assert score == 0.0

    def test_empty_dataframe_returns_zero(self):
        """Empty DataFrame should return 0."""
        f = Stage1TrendFilter()
        score = f.calculate_trend_quality_score(pd.DataFrame())
        assert score == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
