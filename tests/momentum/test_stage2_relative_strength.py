"""Unit tests for Stage2RelativeStrength class."""

import pandas as pd
import pytest

from src.momentum.models import ScannerConfig
from src.momentum.stage2_relative_strength import Stage2RelativeStrength


@pytest.fixture
def config():
    """Default scanner config."""
    return ScannerConfig()


@pytest.fixture
def rs(config):
    """Stage2RelativeStrength instance with default config."""
    return Stage2RelativeStrength(config)


def _make_ohlcv(closes: list[float]) -> pd.DataFrame:
    """Helper to create a minimal OHLCV DataFrame from close prices."""
    return pd.DataFrame(
        {
            "open": closes,
            "high": [c * 1.01 for c in closes],
            "low": [c * 0.99 for c in closes],
            "close": closes,
            "volume": [100000] * len(closes),
        }
    )


class TestCalculateRS:
    """Tests for calculate_rs() method."""

    def test_positive_rs_when_stock_outperforms(self, rs):
        """Stock gaining more than NIFTY should have positive RS."""
        # Stock goes from 100 to 110 (10% gain)
        stock_data = _make_ohlcv([100.0, 105.0, 110.0])
        # NIFTY goes from 100 to 105 (5% gain)
        nifty_data = _make_ohlcv([100.0, 102.0, 105.0])

        result = rs.calculate_rs(stock_data, nifty_data, "1day")
        # RS = 10% - 5% = 5%
        # With 1day window and 3 data points, base is close[-2] = 105 for stock, 102 for nifty
        # stock_pct = (110 - 105) / 105 * 100 = 4.76%
        # nifty_pct = (105 - 102) / 102 * 100 = 2.94%
        # RS = 4.76 - 2.94 = 1.82
        assert result > 0

    def test_negative_rs_when_stock_underperforms(self, rs):
        """Stock gaining less than NIFTY should have negative RS."""
        # Stock goes from 100 to 102 (2% gain)
        stock_data = _make_ohlcv([100.0, 101.0, 102.0])
        # NIFTY goes from 100 to 110 (10% gain)
        nifty_data = _make_ohlcv([100.0, 105.0, 110.0])

        result = rs.calculate_rs(stock_data, nifty_data, "1day")
        assert result < 0

    def test_zero_rs_when_equal_performance(self, rs):
        """Stock and NIFTY with same pct change should have RS = 0."""
        stock_data = _make_ohlcv([100.0, 105.0, 110.0])
        nifty_data = _make_ohlcv([200.0, 210.0, 220.0])

        result = rs.calculate_rs(stock_data, nifty_data, "1day")
        # stock_pct = (110 - 105) / 105 * 100 = 4.76%
        # nifty_pct = (220 - 210) / 210 * 100 = 4.76%
        assert abs(result) < 0.01

    def test_intraday_window_uses_all_data(self, rs):
        """Intraday window should use first to last close."""
        # Stock: 100 -> 120 (20% gain over full range)
        stock_data = _make_ohlcv([100.0, 105.0, 110.0, 115.0, 120.0])
        # NIFTY: 100 -> 110 (10% gain over full range)
        nifty_data = _make_ohlcv([100.0, 102.0, 105.0, 107.0, 110.0])

        result = rs.calculate_rs(stock_data, nifty_data, "intraday")
        # stock_pct = (120 - 100) / 100 * 100 = 20%
        # nifty_pct = (110 - 100) / 100 * 100 = 10%
        # RS = 20 - 10 = 10
        assert abs(result - 10.0) < 0.01

    def test_5day_window_lookback(self, rs):
        """5day window should look back 5 periods."""
        closes = [100.0, 101.0, 102.0, 103.0, 104.0, 110.0]
        stock_data = _make_ohlcv(closes)
        nifty_closes = [100.0, 100.5, 101.0, 101.5, 102.0, 105.0]
        nifty_data = _make_ohlcv(nifty_closes)

        result = rs.calculate_rs(stock_data, nifty_data, "5day")
        # stock_pct = (110 - 100) / 100 * 100 = 10%
        # nifty_pct = (105 - 100) / 100 * 100 = 5%
        # RS = 10 - 5 = 5
        assert abs(result - 5.0) < 0.01

    def test_insufficient_data_returns_zero(self, rs):
        """Should return 0.0 when data has fewer than 2 rows."""
        stock_data = _make_ohlcv([100.0])
        nifty_data = _make_ohlcv([100.0])

        result = rs.calculate_rs(stock_data, nifty_data, "1day")
        assert result == 0.0

    def test_empty_dataframe_returns_zero(self, rs):
        """Should return 0.0 for empty DataFrames."""
        stock_data = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        nifty_data = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        result = rs.calculate_rs(stock_data, nifty_data, "1day")
        assert result == 0.0

    def test_zero_base_price_returns_zero(self, rs):
        """Should return 0.0 when base price is zero (avoid division by zero)."""
        stock_data = _make_ohlcv([0.0, 100.0, 110.0])
        nifty_data = _make_ohlcv([100.0, 105.0, 110.0])

        # For intraday, base is first close = 0.0
        result = rs.calculate_rs(stock_data, nifty_data, "intraday")
        assert result == 0.0


class TestRank:
    """Tests for rank() method."""

    def test_ranks_descending_by_composite_rs(self, rs):
        """Stocks should be ranked by composite RS in descending order."""
        # Stock A: strong outperformer
        stock_a = _make_ohlcv([100.0, 105.0, 110.0, 115.0, 120.0, 130.0])
        # Stock B: moderate outperformer
        stock_b = _make_ohlcv([100.0, 102.0, 104.0, 106.0, 108.0, 112.0])
        # Stock C: underperformer
        stock_c = _make_ohlcv([100.0, 99.0, 98.0, 97.0, 96.0, 95.0])

        nifty_data = _make_ohlcv([100.0, 101.0, 102.0, 103.0, 104.0, 105.0])

        symbols = ["A", "B", "C"]
        stocks_data = {"A": stock_a, "B": stock_b, "C": stock_c}

        result = rs.rank(symbols, stocks_data, nifty_data)

        assert len(result) == 3
        assert result[0][0] == "A"  # Strongest RS first
        assert result[1][0] == "B"
        assert result[2][0] == "C"  # Weakest RS last

        # Verify descending order
        assert result[0][1] >= result[1][1] >= result[2][1]

    def test_missing_stock_data_gets_zero_rs(self, rs):
        """Stocks with no data should get RS=0.0."""
        stock_a = _make_ohlcv([100.0, 110.0, 120.0])
        nifty_data = _make_ohlcv([100.0, 102.0, 104.0])

        symbols = ["A", "B"]
        stocks_data = {"A": stock_a}  # B is missing

        result = rs.rank(symbols, stocks_data, nifty_data)

        assert len(result) == 2
        # Find B's score
        b_result = next(r for r in result if r[0] == "B")
        assert b_result[1] == 0.0

    def test_empty_symbols_returns_empty(self, rs):
        """Empty symbol list should return empty result."""
        nifty_data = _make_ohlcv([100.0, 105.0])
        result = rs.rank([], {}, nifty_data)
        assert result == []

    def test_single_stock(self, rs):
        """Single stock should return a list with one tuple."""
        stock_data = _make_ohlcv([100.0, 105.0, 110.0])
        nifty_data = _make_ohlcv([100.0, 101.0, 102.0])

        result = rs.rank(["X"], {"X": stock_data}, nifty_data)

        assert len(result) == 1
        assert result[0][0] == "X"
        assert result[0][1] > 0  # Stock outperforms NIFTY

    def test_composite_uses_configured_weights(self):
        """Composite RS should use the configured weights."""
        config = ScannerConfig(
            rs_intraday_weight=0.5,
            rs_1day_weight=0.3,
            rs_5day_weight=0.2,
        )
        rs_calc = Stage2RelativeStrength(config)

        # Create data where intraday RS is very high but 1day and 5day are low
        # This tests that intraday weight (0.5) dominates
        stock_data = _make_ohlcv([100.0, 100.0, 100.0, 100.0, 100.0, 120.0])
        nifty_data = _make_ohlcv([100.0, 100.0, 100.0, 100.0, 100.0, 100.0])

        result = rs_calc.rank(["X"], {"X": stock_data}, nifty_data)
        composite = result[0][1]

        # Manually compute expected composite
        # intraday: (120-100)/100*100 - (100-100)/100*100 = 20 - 0 = 20
        # 1day: (120-100)/100*100 - (100-100)/100*100 = 20 - 0 = 20
        # 5day: (120-100)/100*100 - (100-100)/100*100 = 20 - 0 = 20
        # composite = 20*0.5 + 20*0.3 + 20*0.2 = 10 + 6 + 4 = 20
        assert abs(composite - 20.0) < 0.01


class TestWeights:
    """Tests for weight configuration."""

    def test_default_weights(self, rs):
        """Default weights should be intraday=0.5, 1day=0.3, 5day=0.2."""
        assert rs.weights["intraday"] == 0.5
        assert rs.weights["1day"] == 0.3
        assert rs.weights["5day"] == 0.2

    def test_custom_weights(self):
        """Custom weights should be applied from config."""
        config = ScannerConfig(
            rs_intraday_weight=0.6,
            rs_1day_weight=0.25,
            rs_5day_weight=0.15,
        )
        rs_calc = Stage2RelativeStrength(config)

        assert rs_calc.weights["intraday"] == 0.6
        assert rs_calc.weights["1day"] == 0.25
        assert rs_calc.weights["5day"] == 0.15
