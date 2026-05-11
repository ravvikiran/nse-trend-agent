"""Unit tests for SectorAnalyzer class."""

import pandas as pd
import pytest

from src.momentum.models import ScannerConfig
from src.momentum.sector_analyzer import (
    SECTOR_INDICES,
    STOCK_SECTOR_MAP,
    SectorAnalyzer,
)


@pytest.fixture
def config():
    """Default scanner config with sector_boost_pct=5.0."""
    return ScannerConfig()


@pytest.fixture
def analyzer(config):
    """SectorAnalyzer instance with default config."""
    return SectorAnalyzer(config)


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


class TestGetSectorScores:
    """Tests for get_sector_scores() method."""

    def test_sector_outperforming_nifty(self, analyzer):
        """Sector gaining more than NIFTY should have positive RS."""
        # NIFTY goes from 100 to 102 (2% gain)
        nifty_data = _make_ohlcv([100.0, 101.0, 102.0])
        # NIFTY IT goes from 100 to 105 (5% gain)
        sector_data = {"NIFTY IT": _make_ohlcv([100.0, 103.0, 105.0])}

        scores = analyzer.get_sector_scores(sector_data, nifty_data)

        assert "NIFTY IT" in scores
        # RS = 5% - 2% = 3%
        assert scores["NIFTY IT"] == pytest.approx(3.0)

    def test_sector_underperforming_nifty(self, analyzer):
        """Sector gaining less than NIFTY should have negative RS."""
        # NIFTY goes from 100 to 105 (5% gain)
        nifty_data = _make_ohlcv([100.0, 103.0, 105.0])
        # NIFTY BANK goes from 100 to 101 (1% gain)
        sector_data = {"NIFTY BANK": _make_ohlcv([100.0, 100.5, 101.0])}

        scores = analyzer.get_sector_scores(sector_data, nifty_data)

        assert "NIFTY BANK" in scores
        # RS = 1% - 5% = -4%
        assert scores["NIFTY BANK"] == pytest.approx(-4.0)

    def test_multiple_sectors(self, analyzer):
        """Should calculate scores for all provided sectors."""
        nifty_data = _make_ohlcv([100.0, 101.0, 102.0])  # 2% gain
        sector_data = {
            "NIFTY IT": _make_ohlcv([100.0, 103.0, 106.0]),  # 6% gain
            "NIFTY BANK": _make_ohlcv([100.0, 100.5, 101.0]),  # 1% gain
            "NIFTY PHARMA": _make_ohlcv([100.0, 101.0, 102.0]),  # 2% gain
        }

        scores = analyzer.get_sector_scores(sector_data, nifty_data)

        assert len(scores) == 3
        assert scores["NIFTY IT"] == pytest.approx(4.0)  # 6% - 2%
        assert scores["NIFTY BANK"] == pytest.approx(-1.0)  # 1% - 2%
        assert scores["NIFTY PHARMA"] == pytest.approx(0.0)  # 2% - 2%

    def test_empty_nifty_data_returns_empty(self, analyzer):
        """Should return empty dict when NIFTY data is insufficient."""
        nifty_data = pd.DataFrame()
        sector_data = {"NIFTY IT": _make_ohlcv([100.0, 105.0])}

        scores = analyzer.get_sector_scores(sector_data, nifty_data)

        assert scores == {}

    def test_single_candle_nifty_returns_empty(self, analyzer):
        """Should return empty dict when NIFTY has only one candle."""
        nifty_data = _make_ohlcv([100.0])
        sector_data = {"NIFTY IT": _make_ohlcv([100.0, 105.0])}

        scores = analyzer.get_sector_scores(sector_data, nifty_data)

        assert scores == {}

    def test_sector_with_insufficient_data_skipped(self, analyzer):
        """Sectors with insufficient data should be excluded from results."""
        nifty_data = _make_ohlcv([100.0, 102.0])
        sector_data = {
            "NIFTY IT": _make_ohlcv([100.0, 105.0]),  # valid
            "NIFTY BANK": _make_ohlcv([100.0]),  # insufficient (1 candle)
        }

        scores = analyzer.get_sector_scores(sector_data, nifty_data)

        assert "NIFTY IT" in scores
        assert "NIFTY BANK" not in scores

    def test_sector_with_zero_base_price_skipped(self, analyzer):
        """Sectors with zero base price should be excluded."""
        nifty_data = _make_ohlcv([100.0, 102.0])
        sector_data = {
            "NIFTY IT": _make_ohlcv([0.0, 105.0]),  # zero base
        }

        scores = analyzer.get_sector_scores(sector_data, nifty_data)

        assert "NIFTY IT" not in scores

    def test_no_sector_data_returns_empty(self, analyzer):
        """Should return empty dict when no sector data provided."""
        nifty_data = _make_ohlcv([100.0, 102.0])

        scores = analyzer.get_sector_scores({}, nifty_data)

        assert scores == {}


class TestGetStockSectorBoost:
    """Tests for get_stock_sector_boost() method."""

    def test_boost_applied_for_outperforming_sector(self, analyzer):
        """Stock in outperforming sector should get boost."""
        sector_scores = {"NIFTY IT": 3.0}  # positive = outperforming

        boost = analyzer.get_stock_sector_boost("TCS", sector_scores)

        assert boost == 5.0  # default sector_boost_pct

    def test_no_boost_for_underperforming_sector(self, analyzer):
        """Stock in underperforming sector should get zero boost."""
        sector_scores = {"NIFTY BANK": -2.0}  # negative = underperforming

        boost = analyzer.get_stock_sector_boost("HDFCBANK", sector_scores)

        assert boost == 0.0

    def test_no_boost_for_neutral_sector(self, analyzer):
        """Stock in sector with exactly zero RS should get zero boost."""
        sector_scores = {"NIFTY PHARMA": 0.0}  # exactly zero

        boost = analyzer.get_stock_sector_boost("SUNPHARMA", sector_scores)

        assert boost == 0.0

    def test_no_boost_for_unknown_stock(self, analyzer):
        """Stock not in sector mapping should get zero boost."""
        sector_scores = {"NIFTY IT": 3.0}

        boost = analyzer.get_stock_sector_boost("UNKNOWNSTOCK", sector_scores)

        assert boost == 0.0

    def test_no_boost_when_sector_score_missing(self, analyzer):
        """Stock whose sector has no score data should get zero boost."""
        sector_scores = {"NIFTY BANK": 2.0}  # Only bank has score

        # TCS is in NIFTY IT, which has no score
        boost = analyzer.get_stock_sector_boost("TCS", sector_scores)

        assert boost == 0.0

    def test_custom_boost_percentage(self):
        """Should use the configured sector_boost_pct value."""
        config = ScannerConfig(sector_boost_pct=10.0)
        analyzer = SectorAnalyzer(config)
        sector_scores = {"NIFTY IT": 1.5}

        boost = analyzer.get_stock_sector_boost("INFY", sector_scores)

        assert boost == 10.0

    def test_various_sectors_boost(self, analyzer):
        """Verify boost works across different sectors."""
        sector_scores = {
            "NIFTY IT": 2.0,
            "NIFTY BANK": -1.0,
            "NIFTY METAL": 0.5,
            "NIFTY ENERGY": -0.3,
        }

        assert analyzer.get_stock_sector_boost("TCS", sector_scores) == 5.0
        assert analyzer.get_stock_sector_boost("HDFCBANK", sector_scores) == 0.0
        assert analyzer.get_stock_sector_boost("TATASTEEL", sector_scores) == 5.0
        assert analyzer.get_stock_sector_boost("RELIANCE", sector_scores) == 0.0


class TestCustomSectorMap:
    """Tests for custom stock-to-sector mapping."""

    def test_custom_mapping_overrides_default(self):
        """Custom mapping should be used instead of default."""
        custom_map = {"MYSTOCK": "NIFTY IT"}
        config = ScannerConfig()
        analyzer = SectorAnalyzer(config, stock_sector_map=custom_map)
        sector_scores = {"NIFTY IT": 2.0}

        # Custom stock gets boost
        assert analyzer.get_stock_sector_boost("MYSTOCK", sector_scores) == 5.0
        # Default stock not in custom map gets no boost
        assert analyzer.get_stock_sector_boost("TCS", sector_scores) == 0.0

    def test_empty_custom_mapping(self):
        """Empty custom mapping means no stock gets a boost."""
        config = ScannerConfig()
        analyzer = SectorAnalyzer(config, stock_sector_map={})
        sector_scores = {"NIFTY IT": 5.0}

        assert analyzer.get_stock_sector_boost("TCS", sector_scores) == 0.0


class TestStockSectorMapCoverage:
    """Tests for the default STOCK_SECTOR_MAP completeness."""

    def test_all_sector_indices_have_stocks(self):
        """Every sector index should have at least one stock mapped to it."""
        sectors_with_stocks = set(STOCK_SECTOR_MAP.values())
        for sector in SECTOR_INDICES:
            assert sector in sectors_with_stocks, (
                f"Sector '{sector}' has no stocks mapped"
            )

    def test_all_mapped_sectors_are_valid(self):
        """Every sector in the mapping should be a known sector index."""
        for stock, sector in STOCK_SECTOR_MAP.items():
            assert sector in SECTOR_INDICES, (
                f"Stock '{stock}' mapped to unknown sector '{sector}'"
            )
