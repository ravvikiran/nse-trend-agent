"""Unit tests for KiteDataProvider class."""

import asyncio
import os
from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.momentum.providers.kite_provider import (
    KiteDataProvider,
    _BACKOFF_FACTOR,
    _INITIAL_BACKOFF_SECONDS,
    _MAX_RETRIES,
    _TIMEFRAME_MAP,
)


@pytest.fixture
def provider():
    """KiteDataProvider instance with default batch size."""
    return KiteDataProvider(batch_size=50)


@pytest.fixture
def mock_kite():
    """Mock KiteConnect instance with common methods."""
    kite = MagicMock()
    kite.profile.return_value = {"user_name": "TestUser", "user_id": "AB1234"}
    kite.instruments.return_value = [
        {
            "tradingsymbol": "RELIANCE",
            "instrument_token": 738561,
            "exchange": "NSE",
            "segment": "NSE",
        },
        {
            "tradingsymbol": "TCS",
            "instrument_token": 2953217,
            "exchange": "NSE",
            "segment": "NSE",
        },
        {
            "tradingsymbol": "NIFTY 50",
            "instrument_token": 256265,
            "exchange": "NSE",
            "segment": "INDICES",
        },
    ]
    kite.historical_data.return_value = [
        {
            "date": datetime(2024, 3, 15, 9, 15),
            "open": 2450.0,
            "high": 2465.0,
            "low": 2445.0,
            "close": 2460.0,
            "volume": 150000,
        },
        {
            "date": datetime(2024, 3, 15, 9, 30),
            "open": 2460.0,
            "high": 2475.0,
            "low": 2455.0,
            "close": 2470.0,
            "volume": 180000,
        },
        {
            "date": datetime(2024, 3, 15, 9, 45),
            "open": 2470.0,
            "high": 2480.0,
            "low": 2465.0,
            "close": 2478.0,
            "volume": 120000,
        },
    ]
    return kite


@pytest.fixture
def env_vars():
    """Set required environment variables for Kite Connect."""
    with patch.dict(
        os.environ,
        {
            "KITE_API_KEY": "test_api_key",
            "KITE_API_SECRET": "test_api_secret",
            "KITE_ACCESS_TOKEN": "test_access_token",
        },
    ):
        yield


class TestInit:
    """Tests for KiteDataProvider initialization."""

    def test_default_batch_size(self):
        """Default batch size should be 50."""
        provider = KiteDataProvider()
        assert provider.batch_size == 50

    def test_custom_batch_size(self):
        """Custom batch size should be respected."""
        provider = KiteDataProvider(batch_size=25)
        assert provider.batch_size == 25

    def test_initial_state_disconnected(self, provider):
        """Provider should start disconnected."""
        assert provider.connected is False
        assert provider._kite is None
        assert provider._instruments == {}


class TestConnect:
    """Tests for connect() method."""

    def test_connect_missing_api_key(self, provider):
        """Connect should fail if KITE_API_KEY is missing."""
        with patch.dict(os.environ, {}, clear=True):
            result = asyncio.run(provider.connect())
            assert result is False
            assert provider.connected is False

    def test_connect_missing_access_token(self, provider):
        """Connect should fail if KITE_ACCESS_TOKEN is missing."""
        with patch.dict(os.environ, {"KITE_API_KEY": "key"}, clear=True):
            result = asyncio.run(provider.connect())
            assert result is False
            assert provider.connected is False

    def test_connect_success(self, provider, env_vars):
        """Connect should succeed with valid credentials."""
        mock_instance = MagicMock()
        mock_instance.profile.return_value = {"user_name": "TestUser"}
        mock_instance.instruments.return_value = [
            {
                "tradingsymbol": "RELIANCE",
                "instrument_token": 738561,
                "exchange": "NSE",
                "segment": "NSE",
            }
        ]

        mock_kite_module = MagicMock()
        mock_kite_module.KiteConnect.return_value = mock_instance

        with patch.dict("sys.modules", {"kiteconnect": mock_kite_module}):
            result = asyncio.run(provider.connect())
            assert result is True
            assert provider.connected is True

    def test_connect_auth_failure(self, provider, env_vars):
        """Connect should return False on authentication failure."""
        mock_instance = MagicMock()
        mock_instance.profile.side_effect = Exception("Invalid token")

        mock_kite_module = MagicMock()
        mock_kite_module.KiteConnect.return_value = mock_instance

        with patch.dict("sys.modules", {"kiteconnect": mock_kite_module}):
            result = asyncio.run(provider.connect())
            assert result is False
            assert provider.connected is False

    def test_connect_kiteconnect_not_installed(self, provider, env_vars):
        """Connect should fail gracefully if kiteconnect package is missing."""
        with patch.dict("sys.modules", {"kiteconnect": None}):
            # Simulate ImportError by patching builtins
            import builtins

            original_import = builtins.__import__

            def mock_import(name, *args, **kwargs):
                if name == "kiteconnect":
                    raise ImportError("No module named 'kiteconnect'")
                return original_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=mock_import):
                result = asyncio.run(provider.connect())
                assert result is False


class TestDisconnect:
    """Tests for disconnect() method."""

    def test_disconnect_when_not_connected(self, provider):
        """Disconnect should be safe to call when not connected."""
        asyncio.run(provider.disconnect())
        assert provider.connected is False

    def test_disconnect_clears_state(self, provider):
        """Disconnect should clear kite instance and instruments cache."""
        provider._kite = MagicMock()
        provider._instruments = {"RELIANCE": 738561}
        provider.connected = True

        asyncio.run(provider.disconnect())

        assert provider._kite is None
        assert provider._instruments == {}
        assert provider.connected is False

    def test_disconnect_handles_invalidation_error(self, provider):
        """Disconnect should handle errors during token invalidation."""
        mock_kite = MagicMock()
        mock_kite.invalidate_access_token.side_effect = Exception("Network error")
        provider._kite = mock_kite
        provider.connected = True

        # Should not raise
        asyncio.run(provider.disconnect())
        assert provider.connected is False


class TestFetchOhlcv:
    """Tests for fetch_ohlcv() method."""

    def test_fetch_when_not_connected(self, provider):
        """Should return None when not connected."""
        result = asyncio.run(provider.fetch_ohlcv("RELIANCE", "15m", 10))
        assert result is None

    def test_fetch_unsupported_timeframe(self, provider):
        """Should return None for unsupported timeframe."""
        provider.connected = True
        provider._kite = MagicMock()
        result = asyncio.run(provider.fetch_ohlcv("RELIANCE", "5m", 10))
        assert result is None

    def test_fetch_unknown_symbol(self, provider):
        """Should return None for symbol not in instruments cache."""
        provider.connected = True
        provider._kite = MagicMock()
        provider._instruments = {"RELIANCE": 738561}

        result = asyncio.run(provider.fetch_ohlcv("UNKNOWN_STOCK", "15m", 10))
        assert result is None

    def test_fetch_success_returns_dataframe(self, provider, mock_kite):
        """Should return properly formatted DataFrame on success."""
        provider.connected = True
        provider._kite = mock_kite
        provider._instruments = {"RELIANCE": 738561}

        result = asyncio.run(provider.fetch_ohlcv("RELIANCE", "15m", 10))

        assert result is not None
        assert isinstance(result, pd.DataFrame)
        assert list(result.columns) == [
            "open",
            "high",
            "low",
            "close",
            "volume",
            "timestamp",
        ]
        assert len(result) == 3  # mock returns 3 candles

    def test_fetch_limits_to_requested_periods(self, provider, mock_kite):
        """Should return only the requested number of periods."""
        provider.connected = True
        provider._kite = mock_kite
        provider._instruments = {"RELIANCE": 738561}

        result = asyncio.run(provider.fetch_ohlcv("RELIANCE", "15m", 2))

        assert result is not None
        assert len(result) == 2  # Requested 2, mock has 3

    def test_fetch_empty_data_returns_none(self, provider):
        """Should return None when API returns empty data."""
        mock_kite = MagicMock()
        mock_kite.historical_data.return_value = []
        provider.connected = True
        provider._kite = mock_kite
        provider._instruments = {"RELIANCE": 738561}

        result = asyncio.run(provider.fetch_ohlcv("RELIANCE", "15m", 10))
        assert result is None

    def test_fetch_api_error_returns_none(self, provider):
        """Should return None on API error without raising."""
        mock_kite = MagicMock()
        mock_kite.historical_data.side_effect = Exception("API Error")
        provider.connected = True
        provider._kite = mock_kite
        provider._instruments = {"RELIANCE": 738561}

        result = asyncio.run(provider.fetch_ohlcv("RELIANCE", "15m", 10))
        assert result is None


class TestFetchBatch:
    """Tests for fetch_batch() method."""

    def test_batch_returns_dict_of_dataframes(self, provider, mock_kite):
        """Should return dict mapping symbols to DataFrames."""
        provider.connected = True
        provider._kite = mock_kite
        provider._instruments = {"RELIANCE": 738561, "TCS": 2953217}

        result = asyncio.run(
            provider.fetch_batch(["RELIANCE", "TCS"], "15m", 10)
        )

        assert isinstance(result, dict)
        assert "RELIANCE" in result
        assert "TCS" in result
        assert isinstance(result["RELIANCE"], pd.DataFrame)

    def test_batch_skips_failed_symbols(self, provider):
        """Should skip symbols that fail and return others."""
        mock_kite = MagicMock()
        # RELIANCE succeeds, TCS fails
        mock_kite.historical_data.side_effect = [
            [
                {
                    "date": datetime(2024, 3, 15, 9, 15),
                    "open": 2450.0,
                    "high": 2465.0,
                    "low": 2445.0,
                    "close": 2460.0,
                    "volume": 150000,
                }
            ],
            Exception("API Error for TCS"),
        ]
        provider.connected = True
        provider._kite = mock_kite
        provider._instruments = {"RELIANCE": 738561, "TCS": 2953217}

        result = asyncio.run(
            provider.fetch_batch(["RELIANCE", "TCS"], "15m", 10)
        )

        assert "RELIANCE" in result
        assert "TCS" not in result

    def test_batch_empty_symbols_returns_empty_dict(self, provider, mock_kite):
        """Should return empty dict for empty symbol list."""
        provider.connected = True
        provider._kite = mock_kite

        result = asyncio.run(provider.fetch_batch([], "15m", 10))
        assert result == {}

    def test_batch_respects_batch_size(self, provider, mock_kite):
        """Should process symbols in batches of batch_size."""
        provider.connected = True
        provider._kite = mock_kite
        provider.batch_size = 2

        # Create 5 symbols
        symbols = ["SYM1", "SYM2", "SYM3", "SYM4", "SYM5"]
        provider._instruments = {s: i for i, s in enumerate(symbols)}

        result = asyncio.run(provider.fetch_batch(symbols, "15m", 10))

        # All symbols should be attempted (mock returns same data for all)
        assert len(result) == 5


class TestTimeframeMapping:
    """Tests for timeframe mapping constants."""

    def test_15m_maps_to_15minute(self):
        """15m should map to Kite's '15minute' interval."""
        assert _TIMEFRAME_MAP["15m"] == "15minute"

    def test_1h_maps_to_60minute(self):
        """1h should map to Kite's '60minute' interval."""
        assert _TIMEFRAME_MAP["1h"] == "60minute"

    def test_1d_maps_to_day(self):
        """1d should map to Kite's 'day' interval."""
        assert _TIMEFRAME_MAP["1d"] == "day"


class TestRetryConfig:
    """Tests for retry configuration constants."""

    def test_max_retries_is_3(self):
        """Should retry up to 3 times."""
        assert _MAX_RETRIES == 3

    def test_initial_backoff_is_1_second(self):
        """Initial backoff should be 1 second."""
        assert _INITIAL_BACKOFF_SECONDS == 1.0

    def test_backoff_factor_is_2(self):
        """Backoff factor should be 2x (exponential)."""
        assert _BACKOFF_FACTOR == 2.0


class TestRetryBehavior:
    """Tests for exponential backoff retry logic."""

    def test_retries_on_network_error(self, provider):
        """Should retry on ConnectionError."""
        mock_kite = MagicMock()
        call_count = 0

        def failing_then_success(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Network unreachable")
            return {"user_name": "TestUser"}

        mock_kite.profile = failing_then_success
        provider._kite = mock_kite
        provider.connected = True

        result = asyncio.run(provider._run_with_retry(mock_kite.profile))
        assert result == {"user_name": "TestUser"}
        assert call_count == 3

    def test_does_not_retry_on_data_exception(self, provider):
        """Should not retry on DataException (non-retryable)."""
        provider.connected = True

        class DataException(Exception):
            pass

        call_count = 0

        def always_fails(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise DataException("Invalid instrument")

        with pytest.raises(DataException):
            asyncio.run(provider._run_with_retry(always_fails))

        assert call_count == 1  # No retries


class TestIsRetryable:
    """Tests for _is_retryable() method."""

    def test_connection_error_is_retryable(self, provider):
        """ConnectionError should be retryable."""
        assert provider._is_retryable(ConnectionError("timeout")) is True

    def test_timeout_error_is_retryable(self, provider):
        """TimeoutError should be retryable."""
        assert provider._is_retryable(TimeoutError("timed out")) is True

    def test_os_error_is_retryable(self, provider):
        """OSError should be retryable."""
        assert provider._is_retryable(OSError("network down")) is True

    def test_value_error_is_not_retryable(self, provider):
        """Generic ValueError should not be retryable."""
        assert provider._is_retryable(ValueError("bad input")) is False


class TestToDataframe:
    """Tests for _to_dataframe() static method."""

    def test_converts_kite_response_to_dataframe(self):
        """Should convert Kite historical data format to expected DataFrame."""
        data = [
            {
                "date": datetime(2024, 3, 15, 9, 15),
                "open": 100.0,
                "high": 105.0,
                "low": 98.0,
                "close": 103.0,
                "volume": 50000,
            },
            {
                "date": datetime(2024, 3, 15, 9, 30),
                "open": 103.0,
                "high": 108.0,
                "low": 101.0,
                "close": 107.0,
                "volume": 60000,
            },
        ]

        df = KiteDataProvider._to_dataframe(data)

        assert list(df.columns) == [
            "open",
            "high",
            "low",
            "close",
            "volume",
            "timestamp",
        ]
        assert len(df) == 2
        assert df.iloc[0]["open"] == 100.0
        assert df.iloc[1]["close"] == 107.0
        assert df.iloc[0]["timestamp"] == pd.Timestamp("2024-03-15 09:15:00")

    def test_sorts_by_timestamp_ascending(self):
        """Should sort data by timestamp in ascending order."""
        data = [
            {
                "date": datetime(2024, 3, 15, 10, 0),
                "open": 110.0,
                "high": 115.0,
                "low": 108.0,
                "close": 113.0,
                "volume": 70000,
            },
            {
                "date": datetime(2024, 3, 15, 9, 15),
                "open": 100.0,
                "high": 105.0,
                "low": 98.0,
                "close": 103.0,
                "volume": 50000,
            },
        ]

        df = KiteDataProvider._to_dataframe(data)

        # First row should be the earlier timestamp
        assert df.iloc[0]["timestamp"] == pd.Timestamp("2024-03-15 09:15:00")
        assert df.iloc[1]["timestamp"] == pd.Timestamp("2024-03-15 10:00:00")
