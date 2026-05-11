"""
Concrete DataProvider implementation using Zerodha Kite Connect API.

Authenticates with Kite Connect using credentials from environment variables
and fetches OHLCV data for NSE stocks. Supports concurrent batch fetching
with configurable batch size and exponential backoff retry on failures.

Environment variables required:
    KITE_API_KEY: Kite Connect API key
    KITE_API_SECRET: Kite Connect API secret (unused at runtime, needed for login flow)
    KITE_ACCESS_TOKEN: Valid access token (obtained via login flow)
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, Optional

import pandas as pd

from src.momentum.data_provider import DataProvider

logger = logging.getLogger(__name__)

# Timeframe mapping: scanner timeframe -> Kite Connect interval string
_TIMEFRAME_MAP: Dict[str, str] = {
    "15m": "15minute",
    "1h": "60minute",
    "1d": "day",
}

# How many days of historical data to request per timeframe
_TIMEFRAME_LOOKBACK_DAYS: Dict[str, int] = {
    "15m": 30,
    "1h": 90,
    "1d": 365,
}

# Retry configuration
_MAX_RETRIES: int = 3
_INITIAL_BACKOFF_SECONDS: float = 1.0
_BACKOFF_FACTOR: float = 2.0


class KiteDataProvider(DataProvider):
    """Zerodha Kite Connect data provider for the momentum scanner.

    Fetches OHLCV data from Kite Connect's historical data API.
    Handles authentication, timeframe mapping, batch fetching with
    concurrency control, and exponential backoff retry on failures.

    Attributes:
        connected: Whether the provider has an active authenticated session.
        batch_size: Number of symbols to fetch concurrently per batch.
    """

    def __init__(self, batch_size: int = 50):
        """Initialize the Kite data provider.

        Args:
            batch_size: Maximum number of concurrent symbol fetches per batch.
                        Defaults to 50 to avoid Kite API rate limits.
        """
        self.connected: bool = False
        self.batch_size: int = batch_size
        self._kite = None  # KiteConnect instance (lazy loaded)
        self._instruments: Dict[str, int] = {}  # symbol -> instrument_token cache

    async def connect(self) -> bool:
        """Authenticate with Kite Connect using environment credentials.

        Reads KITE_API_KEY and KITE_ACCESS_TOKEN from environment variables,
        creates a KiteConnect session, and validates the connection by
        fetching the user profile.

        Returns:
            True if authentication succeeded, False otherwise.
        """
        api_key = os.environ.get("KITE_API_KEY")
        access_token = os.environ.get("KITE_ACCESS_TOKEN")

        if not api_key or not access_token:
            logger.error(
                "Missing Kite Connect credentials. "
                "Set KITE_API_KEY and KITE_ACCESS_TOKEN environment variables."
            )
            return False

        try:
            from kiteconnect import KiteConnect
        except ImportError:
            logger.error(
                "kiteconnect package not installed. "
                "Install with: pip install kiteconnect"
            )
            return False

        try:
            self._kite = KiteConnect(api_key=api_key)
            self._kite.set_access_token(access_token)

            # Validate connection by fetching profile
            profile = await self._run_with_retry(self._kite.profile)
            logger.info(
                f"Kite Connect authenticated: {profile.get('user_name', 'unknown')}"
            )
            self.connected = True

            # Cache NSE instrument tokens for symbol lookup
            await self._load_instruments()

            return True

        except Exception as e:
            logger.error(f"Kite Connect authentication failed: {e}")
            self.connected = False
            return False

    async def disconnect(self) -> None:
        """Clean up Kite Connect resources.

        Invalidates the session and clears cached data.
        Safe to call multiple times.
        """
        if self._kite is not None:
            try:
                self._kite.invalidate_access_token()
            except Exception as e:
                logger.debug(f"Error invalidating Kite token: {e}")
            finally:
                self._kite = None
                self._instruments.clear()
                self.connected = False
                logger.debug("KiteDataProvider disconnected")

    async def fetch_ohlcv(
        self, symbol: str, timeframe: str, periods: int
    ) -> Optional[pd.DataFrame]:
        """Fetch OHLCV data for a single symbol from Kite Connect.

        Args:
            symbol: NSE stock symbol (e.g., 'RELIANCE', 'TCS', 'NIFTY 50')
            timeframe: One of '15m', '1h', or '1d'
            periods: Number of candles to fetch

        Returns:
            DataFrame with columns [open, high, low, close, volume, timestamp]
            sorted by timestamp ascending, or None if data is unavailable.
        """
        if not self.connected or self._kite is None:
            logger.warning("KiteDataProvider not connected. Call connect() first.")
            return None

        if timeframe not in _TIMEFRAME_MAP:
            logger.warning(f"Unsupported timeframe: '{timeframe}'")
            return None

        instrument_token = self._get_instrument_token(symbol)
        if instrument_token is None:
            logger.debug(f"No instrument token found for symbol: {symbol}")
            return None

        kite_interval = _TIMEFRAME_MAP[timeframe]
        lookback_days = _TIMEFRAME_LOOKBACK_DAYS.get(timeframe, 30)

        # Calculate date range
        to_date = datetime.now()
        from_date = to_date - timedelta(days=lookback_days)

        try:
            data = await self._run_with_retry(
                self._kite.historical_data,
                instrument_token,
                from_date,
                to_date,
                kite_interval,
            )

            if not data:
                logger.debug(f"No data returned for {symbol} ({timeframe})")
                return None

            df = self._to_dataframe(data)

            # Return only the requested number of periods
            if len(df) > periods:
                df = df.tail(periods).reset_index(drop=True)

            return df

        except Exception as e:
            logger.debug(f"Failed to fetch OHLCV for {symbol}: {e}")
            return None

    async def fetch_batch(
        self, symbols: list[str], timeframe: str, periods: int
    ) -> Dict[str, pd.DataFrame]:
        """Fetch OHLCV data for multiple symbols concurrently with batching.

        Processes symbols in batches of `batch_size` (default 50) to avoid
        overwhelming the Kite API rate limits. Within each batch, fetches
        are executed concurrently using asyncio.gather().

        Args:
            symbols: List of NSE stock symbols
            timeframe: One of '15m', '1h', or '1d'
            periods: Number of candles to fetch per symbol

        Returns:
            Dictionary mapping symbol to its OHLCV DataFrame.
            Only symbols with valid data are included in the result.
        """
        results: Dict[str, pd.DataFrame] = {}

        # Process in batches to respect rate limits
        for batch_start in range(0, len(symbols), self.batch_size):
            batch = symbols[batch_start : batch_start + self.batch_size]

            # Fetch all symbols in this batch concurrently
            tasks = [
                self._fetch_single_for_batch(symbol, timeframe, periods)
                for symbol in batch
            ]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for symbol, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    logger.debug(f"Batch fetch failed for {symbol}: {result}")
                elif result is not None:
                    results[symbol] = result

            # Small delay between batches to be respectful of rate limits
            if batch_start + self.batch_size < len(symbols):
                await asyncio.sleep(0.5)

        return results

    async def _fetch_single_for_batch(
        self, symbol: str, timeframe: str, periods: int
    ) -> Optional[pd.DataFrame]:
        """Fetch a single symbol's data, used within batch processing.

        Wraps fetch_ohlcv to catch exceptions so asyncio.gather doesn't
        short-circuit on individual failures.

        Args:
            symbol: NSE stock symbol
            timeframe: Candle timeframe
            periods: Number of candles

        Returns:
            DataFrame or None on failure.
        """
        try:
            return await self.fetch_ohlcv(symbol, timeframe, periods)
        except Exception as e:
            logger.debug(f"Error fetching {symbol} in batch: {e}")
            return None

    async def _run_with_retry(self, func, *args, **kwargs):
        """Execute a synchronous Kite API call with exponential backoff retry.

        Retries on network and token errors up to _MAX_RETRIES times.
        Backoff starts at _INITIAL_BACKOFF_SECONDS and doubles each attempt.

        Args:
            func: The Kite API method to call.
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
                # Run synchronous Kite API call in executor to avoid blocking
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None, lambda: func(*args, **kwargs)
                )
                return result

            except Exception as e:
                last_exception = e
                error_name = type(e).__name__

                # Check if it's a retryable error
                if not self._is_retryable(e):
                    logger.debug(
                        f"Non-retryable error ({error_name}) on attempt {attempt}: {e}"
                    )
                    raise

                if attempt < _MAX_RETRIES:
                    logger.debug(
                        f"Retryable error ({error_name}) on attempt {attempt}/{_MAX_RETRIES}. "
                        f"Retrying in {backoff}s..."
                    )
                    await asyncio.sleep(backoff)
                    backoff *= _BACKOFF_FACTOR
                else:
                    logger.warning(
                        f"All {_MAX_RETRIES} retries exhausted for {func.__name__}: {e}"
                    )

        raise last_exception

    def _is_retryable(self, error: Exception) -> bool:
        """Determine if an error is retryable.

        Network errors and transient token errors are retryable.
        Data errors and input errors are not.

        Args:
            error: The exception to evaluate.

        Returns:
            True if the error should be retried.
        """
        error_name = type(error).__name__

        # Kite Connect specific exceptions that are retryable
        retryable_types = {
            "NetworkException",
            "TokenException",
            "GeneralException",
            "ConnectionError",
            "TimeoutError",
            "OSError",
        }

        # Non-retryable Kite exceptions
        non_retryable_types = {
            "DataException",
            "InputException",
            "OrderException",
            "PermissionException",
        }

        if error_name in non_retryable_types:
            return False

        if error_name in retryable_types:
            return True

        # Default: retry on unknown exceptions (network issues, etc.)
        return isinstance(error, (ConnectionError, TimeoutError, OSError))

    async def _load_instruments(self) -> None:
        """Load and cache NSE instrument tokens from Kite Connect.

        Fetches the full instrument list for NSE exchange and builds
        a symbol -> instrument_token mapping for efficient lookups.
        """
        try:
            instruments = await self._run_with_retry(
                self._kite.instruments, "NSE"
            )

            self._instruments = {
                inst["tradingsymbol"]: inst["instrument_token"]
                for inst in instruments
                if inst.get("exchange") == "NSE"
            }

            # Also load NSE indices
            try:
                indices = await self._run_with_retry(
                    self._kite.instruments, "NSE"
                )
                for inst in indices:
                    if inst.get("segment") == "INDICES":
                        self._instruments[inst["tradingsymbol"]] = inst[
                            "instrument_token"
                        ]
            except Exception as e:
                logger.debug(f"Could not load index instruments: {e}")

            logger.info(f"Loaded {len(self._instruments)} NSE instrument tokens")

        except Exception as e:
            logger.error(f"Failed to load instruments: {e}")

    def _get_instrument_token(self, symbol: str) -> Optional[int]:
        """Look up the instrument token for a symbol.

        Handles common symbol variations (e.g., 'NIFTY 50' -> 'NIFTY 50').

        Args:
            symbol: NSE stock or index symbol.

        Returns:
            Instrument token integer, or None if not found.
        """
        # Direct lookup
        if symbol in self._instruments:
            return self._instruments[symbol]

        # Try common variations
        variations = [
            symbol.upper(),
            symbol.replace(" ", ""),
            f"NIFTY {symbol}" if not symbol.startswith("NIFTY") else symbol,
        ]

        for variant in variations:
            if variant in self._instruments:
                return self._instruments[variant]

        return None

    @staticmethod
    def _to_dataframe(data: list) -> pd.DataFrame:
        """Convert Kite Connect historical data response to a DataFrame.

        Kite returns a list of dicts with keys: date, open, high, low, close, volume.
        This normalizes it to the scanner's expected format.

        Args:
            data: List of candle dicts from Kite historical_data API.

        Returns:
            DataFrame with columns [open, high, low, close, volume, timestamp]
            sorted by timestamp ascending.
        """
        df = pd.DataFrame(data)

        # Kite returns 'date' column, rename to 'timestamp'
        if "date" in df.columns:
            df = df.rename(columns={"date": "timestamp"})

        # Ensure timestamp is datetime
        df["timestamp"] = pd.to_datetime(df["timestamp"])

        # Select and order columns
        expected_columns = ["open", "high", "low", "close", "volume", "timestamp"]
        available_columns = [col for col in expected_columns if col in df.columns]
        df = df[available_columns]

        # Sort by timestamp ascending
        df = df.sort_values("timestamp").reset_index(drop=True)

        return df
