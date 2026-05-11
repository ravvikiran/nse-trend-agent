"""Unit tests for UniverseManager class."""

import json
import tempfile
from pathlib import Path

import pytest

from src.momentum.models import ScannerConfig
from src.momentum.universe_manager import (
    DEFAULT_PENNY_STOCK_THRESHOLD,
    FilterResult,
    StockData,
    UniverseManager,
)


@pytest.fixture
def config():
    """Default scanner config."""
    return ScannerConfig()


@pytest.fixture
def universe_file(tmp_path):
    """Create a temporary universe config file with sample symbols."""
    data = {
        "description": "Test universe",
        "source": "Test",
        "last_updated": "2025-01-01",
        "penny_stock_threshold": 10.0,
        "symbols": [
            "RELIANCE.NS",
            "TCS.NS",
            "INFY.NS",
            "HDFCBANK.NS",
            "ICICIBANK.NS",
            "SBIN.NS",
            "BHARTIARTL.NS",
            "ITC.NS",
            "KOTAKBANK.NS",
            "LT.NS",
        ],
    }
    file_path = tmp_path / "test_universe.json"
    file_path.write_text(json.dumps(data), encoding="utf-8")
    return str(file_path)


@pytest.fixture
def flat_universe_file(tmp_path):
    """Create a universe config file with flat list format."""
    symbols = ["RELIANCE.NS", "TCS.NS", "INFY.NS"]
    file_path = tmp_path / "flat_universe.json"
    file_path.write_text(json.dumps(symbols), encoding="utf-8")
    return str(file_path)


@pytest.fixture
def manager(config, universe_file):
    """UniverseManager instance with test config."""
    return UniverseManager(config, universe_path=universe_file)


def _make_stock_data(
    symbol: str,
    avg_traded_value: float = 50_000_000.0,
    avg_volume: float = 500_000.0,
    last_price: float = 500.0,
    previous_close: float = 495.0,
    open_price: float = 498.0,
    is_suspended: bool = False,
    has_trading_data: bool = True,
) -> StockData:
    """Helper to create StockData with sensible defaults."""
    return StockData(
        symbol=symbol,
        avg_daily_traded_value=avg_traded_value,
        avg_daily_volume=avg_volume,
        last_price=last_price,
        previous_close=previous_close,
        open_price=open_price,
        is_suspended=is_suspended,
        has_trading_data=has_trading_data,
    )


class TestLoadUniverse:
    """Tests for load_universe() method."""

    def test_loads_structured_format(self, manager, universe_file):
        """Should load symbols from structured JSON with 'symbols' key."""
        symbols = manager.load_universe()
        assert len(symbols) == 10
        assert "RELIANCE.NS" in symbols
        assert "TCS.NS" in symbols

    def test_loads_flat_list_format(self, config, flat_universe_file):
        """Should load symbols from a flat JSON array."""
        mgr = UniverseManager(config, universe_path=flat_universe_file)
        symbols = mgr.load_universe()
        assert len(symbols) == 3
        assert "RELIANCE.NS" in symbols

    def test_missing_file_returns_empty(self, config):
        """Should return empty list and log warning when file is missing."""
        mgr = UniverseManager(config, universe_path="nonexistent/path.json")
        symbols = mgr.load_universe()
        assert symbols == []

    def test_invalid_json_returns_empty(self, config, tmp_path):
        """Should return empty list when file contains invalid JSON."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not valid json {{{", encoding="utf-8")
        mgr = UniverseManager(config, universe_path=str(bad_file))
        symbols = mgr.load_universe()
        assert symbols == []

    def test_skips_invalid_entries(self, config, tmp_path):
        """Should skip non-string and empty entries."""
        data = {"symbols": ["RELIANCE.NS", "", None, 123, "TCS.NS"]}
        file_path = tmp_path / "mixed.json"
        file_path.write_text(json.dumps(data), encoding="utf-8")
        mgr = UniverseManager(config, universe_path=str(file_path))
        symbols = mgr.load_universe()
        assert symbols == ["RELIANCE.NS", "TCS.NS"]

    def test_loads_penny_stock_threshold_from_config(self, manager):
        """Should load penny_stock_threshold from universe config file."""
        manager.load_universe()
        assert manager._penny_stock_threshold == 10.0

    def test_full_universe_property(self, manager):
        """full_universe property should return loaded symbols."""
        manager.load_universe()
        assert len(manager.full_universe) == 10


class TestApplyFilters:
    """Tests for apply_filters() method."""

    def test_all_stocks_pass_with_good_data(self, manager):
        """All stocks should pass when they meet all criteria."""
        manager.load_universe()
        stocks_data = {
            symbol: _make_stock_data(symbol) for symbol in manager.full_universe
        }
        active = manager.apply_filters(stocks_data)
        assert len(active) == 10

    def test_excludes_low_liquidity(self, manager):
        """Should exclude stocks below min_liquidity_value."""
        manager.load_universe()
        stocks_data = {
            symbol: _make_stock_data(symbol) for symbol in manager.full_universe
        }
        # Set RELIANCE below liquidity threshold (1 Cr = 10,000,000)
        stocks_data["RELIANCE.NS"] = _make_stock_data(
            "RELIANCE.NS", avg_traded_value=5_000_000.0
        )
        active = manager.apply_filters(stocks_data)
        assert "RELIANCE.NS" not in active
        assert len(active) == 9

    def test_excludes_low_volume(self, manager):
        """Should exclude stocks below min_daily_volume."""
        manager.load_universe()
        stocks_data = {
            symbol: _make_stock_data(symbol) for symbol in manager.full_universe
        }
        # Set TCS below volume threshold (100,000)
        stocks_data["TCS.NS"] = _make_stock_data("TCS.NS", avg_volume=50_000.0)
        active = manager.apply_filters(stocks_data)
        assert "TCS.NS" not in active
        assert len(active) == 9

    def test_excludes_penny_stocks(self, manager):
        """Should exclude stocks with price below penny stock threshold."""
        manager.load_universe()
        stocks_data = {
            symbol: _make_stock_data(symbol) for symbol in manager.full_universe
        }
        # Set INFY as penny stock (price < 10)
        stocks_data["INFY.NS"] = _make_stock_data("INFY.NS", last_price=5.0)
        active = manager.apply_filters(stocks_data)
        assert "INFY.NS" not in active
        assert len(active) == 9

    def test_excludes_suspended_stocks(self, manager):
        """Should exclude suspended stocks."""
        manager.load_universe()
        stocks_data = {
            symbol: _make_stock_data(symbol) for symbol in manager.full_universe
        }
        stocks_data["HDFCBANK.NS"] = _make_stock_data(
            "HDFCBANK.NS", is_suspended=True
        )
        active = manager.apply_filters(stocks_data)
        assert "HDFCBANK.NS" not in active
        assert len(active) == 9

    def test_excludes_no_trading_data(self, manager):
        """Should exclude stocks with no trading data available."""
        manager.load_universe()
        stocks_data = {
            symbol: _make_stock_data(symbol) for symbol in manager.full_universe
        }
        stocks_data["ICICIBANK.NS"] = _make_stock_data(
            "ICICIBANK.NS", has_trading_data=False
        )
        active = manager.apply_filters(stocks_data)
        assert "ICICIBANK.NS" not in active
        assert len(active) == 9

    def test_excludes_abnormal_gap(self, manager):
        """Should exclude stocks with opening gap > max_gap_pct (5%)."""
        manager.load_universe()
        stocks_data = {
            symbol: _make_stock_data(symbol) for symbol in manager.full_universe
        }
        # 10% gap up (previous_close=100, open=110)
        stocks_data["SBIN.NS"] = _make_stock_data(
            "SBIN.NS", previous_close=100.0, open_price=110.0
        )
        active = manager.apply_filters(stocks_data)
        assert "SBIN.NS" not in active
        assert len(active) == 9

    def test_excludes_abnormal_gap_down(self, manager):
        """Should exclude stocks with large gap down too."""
        manager.load_universe()
        stocks_data = {
            symbol: _make_stock_data(symbol) for symbol in manager.full_universe
        }
        # 8% gap down (previous_close=100, open=92)
        stocks_data["BHARTIARTL.NS"] = _make_stock_data(
            "BHARTIARTL.NS", previous_close=100.0, open_price=92.0
        )
        active = manager.apply_filters(stocks_data)
        assert "BHARTIARTL.NS" not in active
        assert len(active) == 9

    def test_allows_normal_gap(self, manager):
        """Should allow stocks with gap within threshold."""
        manager.load_universe()
        stocks_data = {
            symbol: _make_stock_data(symbol) for symbol in manager.full_universe
        }
        # 3% gap (within 5% threshold)
        stocks_data["ITC.NS"] = _make_stock_data(
            "ITC.NS", previous_close=100.0, open_price=103.0
        )
        active = manager.apply_filters(stocks_data)
        assert "ITC.NS" in active

    def test_excludes_stock_with_no_data_entry(self, manager):
        """Should exclude stocks not present in stocks_data dict."""
        manager.load_universe()
        # Only provide data for 5 of 10 stocks
        stocks_data = {
            symbol: _make_stock_data(symbol)
            for symbol in manager.full_universe[:5]
        }
        active = manager.apply_filters(stocks_data)
        assert len(active) == 5

    def test_multiple_filters_applied(self, manager):
        """Should apply all filters cumulatively."""
        manager.load_universe()
        stocks_data = {
            symbol: _make_stock_data(symbol) for symbol in manager.full_universe
        }
        # Low liquidity
        stocks_data["RELIANCE.NS"] = _make_stock_data(
            "RELIANCE.NS", avg_traded_value=1_000_000.0
        )
        # Penny stock
        stocks_data["TCS.NS"] = _make_stock_data("TCS.NS", last_price=3.0)
        # Suspended
        stocks_data["INFY.NS"] = _make_stock_data("INFY.NS", is_suspended=True)
        active = manager.apply_filters(stocks_data)
        assert "RELIANCE.NS" not in active
        assert "TCS.NS" not in active
        assert "INFY.NS" not in active
        assert len(active) == 7

    def test_filter_result_populated(self, manager):
        """Should populate filter_result with exclusion details."""
        manager.load_universe()
        stocks_data = {
            symbol: _make_stock_data(symbol) for symbol in manager.full_universe
        }
        stocks_data["RELIANCE.NS"] = _make_stock_data(
            "RELIANCE.NS", avg_traded_value=1_000_000.0
        )
        manager.apply_filters(stocks_data)
        result = manager.filter_result
        assert result.total_loaded == 10
        assert len(result.active_symbols) == 9
        assert "RELIANCE.NS" in result.excluded_symbols
        assert "low_liquidity" in result.excluded_symbols["RELIANCE.NS"]
        assert result.last_refresh is not None

    def test_gap_filter_skipped_when_previous_close_zero(self, manager):
        """Should skip gap filter when previous_close is 0 (no data)."""
        manager.load_universe()
        stocks_data = {
            symbol: _make_stock_data(symbol) for symbol in manager.full_universe
        }
        # previous_close=0 means gap can't be calculated, should not exclude
        stocks_data["LT.NS"] = _make_stock_data(
            "LT.NS", previous_close=0.0, open_price=500.0
        )
        active = manager.apply_filters(stocks_data)
        assert "LT.NS" in active


class TestGetActiveUniverse:
    """Tests for get_active_universe() method."""

    def test_returns_filtered_universe_after_apply(self, manager):
        """Should return filtered list after apply_filters is called."""
        manager.load_universe()
        stocks_data = {
            symbol: _make_stock_data(symbol) for symbol in manager.full_universe
        }
        manager.apply_filters(stocks_data)
        active = manager.get_active_universe()
        assert len(active) == 10

    def test_returns_full_universe_if_no_filters_applied(self, manager):
        """Should return full universe if filters haven't been applied yet."""
        manager.load_universe()
        active = manager.get_active_universe()
        assert len(active) == 10

    def test_loads_universe_if_nothing_loaded(self, config, universe_file):
        """Should auto-load universe if nothing has been loaded yet."""
        mgr = UniverseManager(config, universe_path=universe_file)
        active = mgr.get_active_universe()
        assert len(active) == 10


class TestRefresh:
    """Tests for refresh() method."""

    def test_refresh_without_data_returns_full_universe(self, manager):
        """Refresh without stocks_data should return full universe."""
        manager.load_universe()
        result = manager.refresh()
        assert len(result) == 10

    def test_refresh_with_data_applies_filters(self, manager):
        """Refresh with stocks_data should apply filters."""
        manager.load_universe()
        stocks_data = {
            symbol: _make_stock_data(symbol) for symbol in manager.full_universe
        }
        stocks_data["RELIANCE.NS"] = _make_stock_data(
            "RELIANCE.NS", avg_traded_value=1_000_000.0
        )
        result = manager.refresh(stocks_data)
        assert "RELIANCE.NS" not in result
        assert len(result) == 9

    def test_refresh_reloads_from_file(self, config, tmp_path):
        """Refresh should reload from file, picking up changes."""
        data = {"symbols": ["RELIANCE.NS", "TCS.NS"]}
        file_path = tmp_path / "dynamic_universe.json"
        file_path.write_text(json.dumps(data), encoding="utf-8")

        mgr = UniverseManager(config, universe_path=str(file_path))
        mgr.load_universe()
        assert len(mgr.full_universe) == 2

        # Update the file
        data["symbols"].append("INFY.NS")
        file_path.write_text(json.dumps(data), encoding="utf-8")

        mgr.refresh()
        assert len(mgr.full_universe) == 3
        assert "INFY.NS" in mgr.full_universe
