"""
Concrete DataProvider implementation using Dhan (DhanHQ) API.

Authenticates with Dhan using credentials from environment variables
and fetches OHLCV data for NSE stocks. Supports concurrent batch fetching
with configurable batch size and exponential backoff retry on failures.

Dhan API is free for all Dhan account holders — no separate subscription needed.

Environment variables required:
    DHAN_CLIENT_ID: Your Dhan client ID
    DHAN_ACCESS_TOKEN: Access token generated from Dhan app/developer portal

Install SDK:
    pip install dhanhq
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd

from src.momentum.data_provider import DataProvider

logger = logging.getLogger(__name__)

# Timeframe mapping: scanner timeframe -> Dhan exchange_segment + instrument_type
# Dhan uses intraday_minute_data for intraday and historical_daily_data for daily
_INTRADAY_TIMEFRAMES = {"15m", "1h"}
_DAILY_TIMEFRAMES = {"1d"}

# How many days of historical data to request per timeframe
_TIMEFRAME_LOOKBACK_DAYS: Dict[str, int] = {
    "15m": 5,    # Dhan intraday data limited to last 5 trading days
    "1h": 5,     # Same limit for intraday
    "1d": 365,   # Daily data available for longer periods
}

# Retry configuration
_MAX_RETRIES: int = 3
_INITIAL_BACKOFF_SECONDS: float = 1.0
_BACKOFF_FACTOR: float = 2.0

# Dhan exchange segment constants
_NSE_EQ = "NSE_EQ"
_IDX_I = "IDX_I"


class DhanDataProvider(DataProvider):
    """Dhan (DhanHQ) data provider for the momentum scanner.

    Fetches OHLCV data from Dhan's historical data API.
    Handles authentication, timeframe mapping, batch fetching with
    concurrency control, and exponential backoff retry on failures.

    Dhan provides:
    - intraday_minute_data(): 1-minute candles for last 5 trading days
    - historical_daily_data(): daily candles for up to 2 years

    For 15m and 1h timeframes, we fetch 1-minute data and resample.

    Attributes:
        connected: Whether the provider has an active authenticated session.
        batch_size: Number of symbols to fetch concurrently per batch.
    """

    def __init__(self, batch_size: int = 50):
        """Initialize the Dhan data provider.

        Args:
            batch_size: Maximum number of concurrent symbol fetches per batch.
                        Defaults to 50 to avoid API rate limits.
        """
        self.connected: bool = False
        self.batch_size: int = batch_size
        self._dhan = None  # dhanhq instance (lazy loaded)
        self._security_list: Dict[str, str] = {}  # symbol -> security_id cache

    async def connect(self) -> bool:
        """Authenticate with Dhan using environment credentials.

        Reads DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN from environment variables,
        creates a DhanHQ session, and validates the connection.

        Returns:
            True if authentication succeeded, False otherwise.
        """
        client_id = os.environ.get("DHAN_CLIENT_ID")
        access_token = os.environ.get("DHAN_ACCESS_TOKEN")

        if not client_id or not access_token:
            logger.error(
                "Missing Dhan credentials. "
                "Set DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN environment variables."
            )
            return False

        try:
            from dhanhq import DhanContext, dhanhq
        except ImportError:
            logger.error(
                "dhanhq package not installed. "
                "Install with: pip install dhanhq"
            )
            return False

        try:
            dhan_context = DhanContext(client_id, access_token)
            self._dhan = dhanhq(dhan_context)

            # Load security list for symbol -> security_id mapping
            await self._load_security_list()

            self.connected = True
            logger.info("Dhan API connected successfully (client_id: %s)", client_id)
            return True

        except Exception as e:
            logger.error("Dhan authentication failed: %s", e)
            self.connected = False
            return False

    async def disconnect(self) -> None:
        """Clean up Dhan resources.

        Safe to call multiple times.
        """
        self._dhan = None
        self._security_list.clear()
        self.connected = False
        logger.debug("DhanDataProvider disconnected")

    async def fetch_ohlcv(
        self, symbol: str, timeframe: str, periods: int
    ) -> Optional[pd.DataFrame]:
        """Fetch OHLCV data for a single symbol from Dhan.

        For intraday timeframes (15m, 1h): fetches 1-minute data and resamples.
        For daily timeframe: fetches daily candles directly.

        Args:
            symbol: NSE stock symbol (e.g., 'RELIANCE', 'TCS', 'NIFTY 50')
            timeframe: One of '15m', '1h', or '1d'
            periods: Number of candles to fetch

        Returns:
            DataFrame with columns [open, high, low, close, volume, timestamp]
            sorted by timestamp ascending, or None if data is unavailable.
        """
        if not self.connected or self._dhan is None:
            logger.warning("DhanDataProvider not connected. Call connect() first.")
            return None

        if timeframe not in _INTRADAY_TIMEFRAMES and timeframe not in _DAILY_TIMEFRAMES:
            logger.warning("Unsupported timeframe: '%s'", timeframe)
            return None

        security_id = self._get_security_id(symbol)
        if security_id is None:
            logger.debug("No security_id found for symbol: %s", symbol)
            return None

        try:
            if timeframe in _INTRADAY_TIMEFRAMES:
                df = await self._fetch_intraday(symbol, security_id, timeframe, periods)
            else:
                df = await self._fetch_daily(symbol, security_id, periods)

            return df

        except Exception as e:
            logger.debug("Failed to fetch OHLCV for %s (%s): %s", symbol, timeframe, e)
            return None

    async def fetch_batch(
        self, symbols: list[str], timeframe: str, periods: int
    ) -> Dict[str, pd.DataFrame]:
        """Fetch OHLCV data for multiple symbols concurrently with batching.

        Processes symbols in batches of `batch_size` to avoid rate limits.

        Args:
            symbols: List of NSE stock symbols
            timeframe: One of '15m', '1h', or '1d'
            periods: Number of candles to fetch per symbol

        Returns:
            Dictionary mapping symbol to its OHLCV DataFrame.
            Only symbols with valid data are included in the result.
        """
        results: Dict[str, pd.DataFrame] = {}

        for batch_start in range(0, len(symbols), self.batch_size):
            batch = symbols[batch_start: batch_start + self.batch_size]

            tasks = [
                self._fetch_single_safe(symbol, timeframe, periods)
                for symbol in batch
            ]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for symbol, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    logger.debug("Batch fetch failed for %s: %s", symbol, result)
                elif result is not None:
                    results[symbol] = result

            # Small delay between batches to respect rate limits
            if batch_start + self.batch_size < len(symbols):
                await asyncio.sleep(0.5)

        return results

    # -------------------------------------------------------------------------
    # Private methods
    # -------------------------------------------------------------------------

    async def _fetch_single_safe(
        self, symbol: str, timeframe: str, periods: int
    ) -> Optional[pd.DataFrame]:
        """Fetch a single symbol's data, catching exceptions for batch use."""
        try:
            return await self.fetch_ohlcv(symbol, timeframe, periods)
        except Exception as e:
            logger.debug("Error fetching %s in batch: %s", symbol, e)
            return None

    async def _fetch_intraday(
        self, symbol: str, security_id: str, timeframe: str, periods: int
    ) -> Optional[pd.DataFrame]:
        """Fetch intraday data and resample to the requested timeframe.

        Dhan provides 1-minute candle data for the last 5 trading days.
        We resample to 15m or 1h as needed.

        Args:
            symbol: Stock symbol for logging.
            security_id: Dhan security ID.
            timeframe: '15m' or '1h'.
            periods: Number of resampled candles needed.

        Returns:
            Resampled OHLCV DataFrame or None.
        """
        # Determine exchange segment and instrument type
        exchange_segment, instrument_type = self._get_segment_info(symbol)

        # Calculate date range (last 5 trading days for intraday)
        to_date = datetime.now().strftime("%Y-%m-%d")
        from_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

        # Fetch 1-minute data with retry
        data = await self._run_with_retry(
            self._dhan.intraday_minute_data,
            security_id,
            exchange_segment,
            instrument_type,
            from_date,
            to_date,
        )

        if data is None or data.get("status") != "success":
            logger.debug("Intraday data fetch failed for %s: %s", symbol, data)
            return None

        candles = data.get("data", [])
        if not candles:
            return None

        # Convert to DataFrame
        df = self._candles_to_dataframe(candles)
        if df is None or df.empty:
            return None

        # Resample to requested timeframe
        resample_rule = "15min" if timeframe == "15m" else "60min"
        df = self._resample_ohlcv(df, resample_rule)

        if df is None or df.empty:
            return None

        # Return only the requested number of periods
        if len(df) > periods:
            df = df.tail(periods).reset_index(drop=True)

        return df

    async def _fetch_daily(
        self, symbol: str, security_id: str, periods: int
    ) -> Optional[pd.DataFrame]:
        """Fetch daily OHLCV data.

        Args:
            symbol: Stock symbol for logging.
            security_id: Dhan security ID.
            periods: Number of daily candles needed.

        Returns:
            Daily OHLCV DataFrame or None.
        """
        exchange_segment, instrument_type = self._get_segment_info(symbol)

        # Calculate date range
        to_date = datetime.now().strftime("%Y-%m-%d")
        lookback_days = min(periods * 2, 730)  # Max ~2 years
        from_date = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

        data = await self._run_with_retry(
            self._dhan.historical_daily_data,
            security_id,
            exchange_segment,
            instrument_type,
            from_date,
            to_date,
        )

        if data is None or data.get("status") != "success":
            logger.debug("Daily data fetch failed for %s: %s", symbol, data)
            return None

        candles = data.get("data", [])
        if not candles:
            return None

        df = self._candles_to_dataframe(candles)
        if df is None or df.empty:
            return None

        # Return only the requested number of periods
        if len(df) > periods:
            df = df.tail(periods).reset_index(drop=True)

        return df

    async def _load_security_list(self) -> None:
        """Load and cache the security list from Dhan for symbol lookups.

        Maps trading symbols to Dhan security IDs.
        """
        try:
            # Dhan's fetch_security_list returns a CSV/dict of all instruments
            data = await self._run_with_retry(
                self._dhan.fetch_security_list, "compact"
            )

            if data is None:
                logger.warning("Failed to fetch Dhan security list")
                return

            # The response format depends on SDK version
            # For v2.2.0, it returns a dict with instrument data
            if isinstance(data, dict) and "data" in data:
                instruments = data["data"]
            elif isinstance(data, list):
                instruments = data
            else:
                # Try to use it as-is if it's a DataFrame or similar
                instruments = data

            # Build symbol -> security_id mapping for NSE equities
            if isinstance(instruments, list):
                for inst in instruments:
                    if isinstance(inst, dict):
                        sym = inst.get("tradingSymbol", "") or inst.get("SEM_TRADING_SYMBOL", "")
                        sec_id = str(inst.get("securityId", "") or inst.get("SEM_SMST_SECURITY_ID", ""))
                        exchange = inst.get("exchangeSegment", "") or inst.get("SEM_EXM_EXCH_ID", "")
                        if sym and sec_id and exchange in ("NSE_EQ", "NSE", "IDX_I"):
                            # Store without .NS suffix for matching
                            clean_sym = sym.replace(".NS", "").replace("-EQ", "")
                            self._security_list[clean_sym] = sec_id
                            self._security_list[sym] = sec_id

            # Add well-known index mappings
            self._security_list["NIFTY 50"] = "13"
            self._security_list["NIFTY BANK"] = "25"
            self._security_list["NIFTY IT"] = "10940"
            self._security_list["NIFTY PHARMA"] = "10944"
            self._security_list["NIFTY AUTO"] = "10945"
            self._security_list["NIFTY FMCG"] = "10946"
            self._security_list["NIFTY METAL"] = "10947"
            self._security_list["NIFTY ENERGY"] = "10948"
            self._security_list["NIFTY REALTY"] = "10949"

            logger.info("Loaded %d security mappings from Dhan", len(self._security_list))

        except Exception as e:
            logger.error("Failed to load Dhan security list: %s", e)
            # Add minimal hardcoded mappings as fallback
            self._add_fallback_mappings()

    def _add_fallback_mappings(self) -> None:
        """Add hardcoded security_id mappings for major NSE stocks as fallback."""
        fallback = {
            "RELIANCE": "2885",
            "TCS": "11536",
            "HDFCBANK": "1333",
            "INFY": "1594",
            "ICICIBANK": "4963",
            "HINDUNILVR": "1394",
            "ITC": "1660",
            "SBIN": "3045",
            "BHARTIARTL": "10604",
            "KOTAKBANK": "1922",
            "LT": "11483",
            "AXISBANK": "5900",
            "TATAMOTORS": "3456",
            "MARUTI": "10999",
            "SUNPHARMA": "3351",
            "TITAN": "3506",
            "BAJFINANCE": "317",
            "WIPRO": "3787",
            "ASIANPAINT": "236",
            "ULTRACEMCO": "11532",
            "TATASTEEL": "3499",
            "NTPC": "11630",
            "POWERGRID": "14977",
            "ONGC": "2475",
            "COALINDIA": "20374",
            "NIFTY 50": "13",
            "NIFTY BANK": "25",
            "NIFTY IT": "10940",
        }
        self._security_list.update(fallback)
        logger.info("Using fallback security mappings (%d entries)", len(fallback))

    def _get_security_id(self, symbol: str) -> Optional[str]:
        """Look up the Dhan security_id for a symbol.

        Tries multiple variations of the symbol name.

        Args:
            symbol: NSE stock or index symbol.

        Returns:
            Security ID string, or None if not found.
        """
        # Direct lookup
        if symbol in self._security_list:
            return self._security_list[symbol]

        # Try common variations
        variations = [
            symbol.upper(),
            symbol.replace(".NS", ""),
            symbol.replace("-EQ", ""),
            symbol.upper().replace(".NS", ""),
        ]

        for variant in variations:
            if variant in self._security_list:
                return self._security_list[variant]

        return None

    def _get_segment_info(self, symbol: str) -> tuple:
        """Determine exchange segment and instrument type for a symbol.

        Args:
            symbol: Stock or index symbol.

        Returns:
            Tuple of (exchange_segment, instrument_type).
        """
        # Index symbols
        if symbol.startswith("NIFTY") or symbol in ("BANKNIFTY", "FINNIFTY"):
            return _IDX_I, "INDEX"

        # Default: NSE equity
        return _NSE_EQ, "EQUITY"

    def _candles_to_dataframe(self, candles: list) -> Optional[pd.DataFrame]:
        """Convert Dhan candle data to a standardized DataFrame.

        Dhan returns candles as a list of dicts or list of lists depending
        on the endpoint. This handles both formats.

        Args:
            candles: Raw candle data from Dhan API.

        Returns:
            DataFrame with columns [open, high, low, close, volume, timestamp]
            sorted by timestamp ascending, or None if conversion fails.
        """
        if not candles:
            return None

        try:
            # Dhan intraday/historical returns dict format:
            # {"open": [...], "high": [...], "low": [...], "close": [...],
            #  "volume": [...], "timestamp": [...] or "start_Time": [...]}
            if isinstance(candles, dict):
                df = pd.DataFrame(candles)
            elif isinstance(candles, list) and isinstance(candles[0], dict):
                df = pd.DataFrame(candles)
            elif isinstance(candles, list) and isinstance(candles[0], list):
                # List of lists: [timestamp, open, high, low, close, volume]
                df = pd.DataFrame(
                    candles,
                    columns=["timestamp", "open", "high", "low", "close", "volume"],
                )
            else:
                logger.debug("Unexpected candle data format: %s", type(candles))
                return None

            # Normalize column names (Dhan uses various naming conventions)
            column_map = {
                "start_Time": "timestamp",
                "start_time": "timestamp",
                "startTime": "timestamp",
                "date": "timestamp",
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume",
            }
            df = df.rename(columns={k: v for k, v in column_map.items() if k in df.columns})

            # Ensure required columns exist
            required = {"open", "high", "low", "close", "volume"}
            if not required.issubset(df.columns):
                missing = required - set(df.columns)
                logger.debug("Missing columns in Dhan data: %s", missing)
                return None

            # Handle timestamp
            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"])
            else:
                # If no timestamp, create a synthetic one
                df["timestamp"] = pd.date_range(
                    end=datetime.now(), periods=len(df), freq="1min"
                )

            # Ensure numeric types
            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = pd.to_numeric(df[col], errors="coerce")

            # Drop rows with NaN values
            df = df.dropna(subset=["open", "high", "low", "close", "volume"])

            # Select and order columns
            df = df[["open", "high", "low", "close", "volume", "timestamp"]]

            # Sort by timestamp ascending
            df = df.sort_values("timestamp").reset_index(drop=True)

            return df if not df.empty else None

        except Exception as e:
            logger.debug("Error converting Dhan candles to DataFrame: %s", e)
            return None

    def _resample_ohlcv(self, df: pd.DataFrame, rule: str) -> Optional[pd.DataFrame]:
        """Resample 1-minute OHLCV data to a higher timeframe.

        Args:
            df: 1-minute OHLCV DataFrame with 'timestamp' column.
            rule: Pandas resample rule (e.g., '15min', '60min').

        Returns:
            Resampled DataFrame or None on failure.
        """
        try:
            df = df.set_index("timestamp")

            resampled = df.resample(rule).agg({
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            })

            # Drop incomplete candles (NaN from resample)
            resampled = resampled.dropna()

            if resampled.empty:
                return None

            # Reset index to get timestamp back as a column
            resampled = resampled.reset_index()
            resampled = resampled.rename(columns={"index": "timestamp"})

            # Ensure timestamp column name is correct after reset
            if "timestamp" not in resampled.columns and resampled.index.name == "timestamp":
                resampled = resampled.reset_index()

            return resampled

        except Exception as e:
            logger.debug("Error resampling OHLCV data: %s", e)
            return None

    async def _run_with_retry(self, func, *args, **kwargs):
        """Execute a Dhan API call with exponential backoff retry.

        Args:
            func: The Dhan API method to call.
            *args: Positional arguments for the method.
            **kwargs: Keyword arguments for the method.

        Returns:
            The result of the API call.

        Raises:
            The last exception if all retries are exhausted.
        """
        last_exception = None
        backoff = _INITIAL_BACKOFF_SECONDS

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None, lambda: func(*args, **kwargs)
                )
                return result

            except Exception as e:
                last_exception = e
                error_name = type(e).__name__

                if not self._is_retryable(e):
                    logger.debug(
                        "Non-retryable error (%s) on attempt %d: %s",
                        error_name, attempt, e,
                    )
                    raise

                if attempt < _MAX_RETRIES:
                    logger.debug(
                        "Retryable error (%s) on attempt %d/%d. Retrying in %.1fs...",
                        error_name, attempt, _MAX_RETRIES, backoff,
                    )
                    await asyncio.sleep(backoff)
                    backoff *= _BACKOFF_FACTOR
                else:
                    logger.warning(
                        "All %d retries exhausted for %s: %s",
                        _MAX_RETRIES, func.__name__, e,
                    )

        raise last_exception

    @staticmethod
    def _is_retryable(error: Exception) -> bool:
        """Determine if an error is retryable.

        Network errors and transient errors are retryable.
        Data/input errors are not.

        Args:
            error: The exception to evaluate.

        Returns:
            True if the error should be retried.
        """
        return isinstance(error, (ConnectionError, TimeoutError, OSError))
