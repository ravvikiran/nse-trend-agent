"""
Concrete DataProvider implementation using Yahoo Finance (yfinance).

Free, no API key required. Fetches OHLCV data for NSE stocks using
the .NS suffix convention (e.g., RELIANCE.NS, TCS.NS).

Supports all timeframes needed by the scanner: 15m, 1h, 1d.

Note: Yahoo Finance has rate limits for high-frequency requests.
This provider uses sequential fetching with small delays to stay
within limits.

Install:
    pip install yfinance
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd

from src.momentum.data_provider import DataProvider

logger = logging.getLogger(__name__)

# Timeframe mapping: scanner timeframe -> yfinance interval string
_TIMEFRAME_MAP = {
    "15m": "15m",
    "1h": "1h",
    "1d": "1d",
}

# How far back to look for each timeframe
# yfinance limits: 15m/1h = max 730 days, 1d = max ~20 years
_TIMEFRAME_LOOKBACK = {
    "15m": 7,      # 7 days (yfinance limit for <1d intervals on some tickers)
    "1h": 730,     # Up to 730 days for hourly
    "1d": 730,     # ~2 years for daily
}

# Batch size for sequential fetching
_DEFAULT_BATCH_SIZE = 10


class YahooFinanceProvider(DataProvider):
    """Yahoo Finance data provider for the momentum scanner.

    Fetches OHLCV data using the yfinance library. Free, no authentication
    required. Symbols must use the .NS suffix for NSE stocks.

    Attributes:
        connected: Whether the provider is ready to fetch data.
        batch_size: Number of symbols to process per batch.
    """

    def __init__(self, batch_size: int = _DEFAULT_BATCH_SIZE):
        """Initialize the Yahoo Finance data provider.

        Args:
            batch_size: Number of symbols to fetch per batch before pausing.
        """
        self.connected: bool = False
        self.batch_size: int = batch_size
        self._yf = None  # yfinance module (lazy loaded)

    async def connect(self) -> bool:
        """Verify yfinance is available and ready.

        No authentication needed — just checks the library is installed.

        Returns:
            True if yfinance is available, False otherwise.
        """
        try:
            import yfinance as yf
            self._yf = yf
            self.connected = True
            logger.info("Yahoo Finance provider ready (no API key required)")
            return True
        except ImportError:
            logger.error(
                "yfinance package not installed. Install with: pip install yfinance"
            )
            return False

    async def disconnect(self) -> None:
        """Clean up resources. No-op for Yahoo Finance."""
        self._yf = None
        self.connected = False
        logger.debug("YahooFinanceProvider disconnected")

    async def fetch_ohlcv(
        self, symbol: str, timeframe: str, periods: int
    ) -> Optional[pd.DataFrame]:
        """Fetch OHLCV data for a single symbol from Yahoo Finance.

        Args:
            symbol: NSE stock symbol with .NS suffix (e.g., 'RELIANCE.NS')
                    or index symbol (e.g., 'NIFTY 50' -> '^NSEI')
            timeframe: One of '15m', '1h', or '1d'
            periods: Number of candles to fetch

        Returns:
            DataFrame with columns [open, high, low, close, volume, timestamp]
            sorted by timestamp ascending, or None if data is unavailable.
        """
        if not self.connected or self._yf is None:
            logger.warning("YahooFinanceProvider not connected. Call connect() first.")
            return None

        if timeframe not in _TIMEFRAME_MAP:
            logger.warning("Unsupported timeframe: '%s'", timeframe)
            return None

        # Map scanner symbols to Yahoo Finance symbols
        yf_symbol = self._map_symbol(symbol)
        yf_interval = _TIMEFRAME_MAP[timeframe]

        # Calculate the date range
        lookback_days = self._calculate_lookback(timeframe, periods)

        try:
            loop = asyncio.get_event_loop()
            df = await loop.run_in_executor(
                None,
                self._download_data,
                yf_symbol, yf_interval, lookback_days,
            )

            if df is None or df.empty:
                logger.debug("No data returned for %s (%s)", symbol, timeframe)
                return None

            # Trim to requested periods
            if len(df) > periods:
                df = df.tail(periods).reset_index(drop=True)

            return df

        except Exception as e:
            logger.debug("Failed to fetch %s (%s): %s", symbol, timeframe, e)
            return None

    async def fetch_batch(
        self, symbols: List[str], timeframe: str, periods: int
    ) -> Dict[str, pd.DataFrame]:
        """Fetch OHLCV data for multiple symbols sequentially.

        Processes symbols in batches with small delays to respect
        Yahoo Finance rate limits.

        Args:
            symbols: List of NSE stock symbols
            timeframe: One of '15m', '1h', or '1d'
            periods: Number of candles to fetch per symbol

        Returns:
            Dictionary mapping symbol to its OHLCV DataFrame.
            Only symbols with valid data are included.
        """
        results: Dict[str, pd.DataFrame] = {}
        failed_count = 0
        first_failure_logged = False

        for batch_start in range(0, len(symbols), self.batch_size):
            batch = symbols[batch_start: batch_start + self.batch_size]

            for symbol in batch:
                try:
                    df = await self.fetch_ohlcv(symbol, timeframe, periods)
                    if df is not None and not df.empty:
                        results[symbol] = df
                    else:
                        failed_count += 1
                        if not first_failure_logged:
                            logger.warning(
                                "First fetch failure: %s (%s) returned no data",
                                symbol, timeframe,
                            )
                            first_failure_logged = True
                except Exception as e:
                    failed_count += 1
                    if not first_failure_logged:
                        logger.warning("First fetch exception: %s — %s", symbol, e)
                        first_failure_logged = True

            # Small delay between batches to respect rate limits
            if batch_start + self.batch_size < len(symbols):
                await asyncio.sleep(1.0)

        if failed_count > 0:
            logger.warning(
                "Batch fetch: %d/%d symbols failed (timeframe=%s)",
                failed_count, len(symbols), timeframe,
            )
        logger.info(
            "Batch fetch complete: %d/%d symbols returned data (timeframe=%s)",
            len(results), len(symbols), timeframe,
        )

        return results

    # -------------------------------------------------------------------------
    # Private methods
    # -------------------------------------------------------------------------

    def _map_symbol(self, symbol: str) -> str:
        """Map scanner symbol to Yahoo Finance symbol.

        Handles index symbols and ensures .NS suffix for NSE stocks.

        Args:
            symbol: Scanner symbol (e.g., 'RELIANCE.NS', 'NIFTY 50')

        Returns:
            Yahoo Finance compatible symbol.
        """
        # Index mappings
        index_map = {
            "NIFTY 50": "^NSEI",
            "NIFTY BANK": "^NSEBANK",
            "NIFTY IT": "^CNXIT",
            "NIFTY PHARMA": "^CNXPHARMA",
            "NIFTY AUTO": "^CNXAUTO",
            "NIFTY FMCG": "^CNXFMCG",
            "NIFTY METAL": "^CNXMETAL",
            "NIFTY ENERGY": "^CNXENERGY",
            "NIFTY REALTY": "^CNXREALTY",
        }

        if symbol in index_map:
            return index_map[symbol]

        # Already has .NS suffix
        if symbol.endswith(".NS"):
            return symbol

        # Add .NS suffix for NSE stocks
        return f"{symbol}.NS"

    def _calculate_lookback(self, timeframe: str, periods: int) -> int:
        """Calculate how many calendar days to look back for the requested periods.

        Args:
            timeframe: The candle timeframe.
            periods: Number of candles needed.

        Returns:
            Number of calendar days to look back.
        """
        if timeframe == "1d":
            # ~1.5x periods to account for weekends/holidays
            return min(periods * 2, _TIMEFRAME_LOOKBACK["1d"])
        elif timeframe == "1h":
            # ~6 hourly candles per trading day, 1.5x for weekends
            days_needed = (periods // 6) * 2 + 5
            return min(days_needed, _TIMEFRAME_LOOKBACK["1h"])
        elif timeframe == "15m":
            # ~25 candles per trading day (9:15-15:30 = 6.25h = 25 x 15m)
            days_needed = (periods // 25) * 2 + 3
            return min(days_needed, _TIMEFRAME_LOOKBACK["15m"])
        else:
            return 30

    def _download_data(
        self, symbol: str, interval: str, lookback_days: int
    ) -> Optional[pd.DataFrame]:
        """Download OHLCV data from Yahoo Finance (runs in thread executor).

        Args:
            symbol: Yahoo Finance symbol.
            interval: yfinance interval string (15m, 1h, 1d).
            lookback_days: Number of days to look back.

        Returns:
            Standardized DataFrame or None.
        """
        try:
            ticker = self._yf.Ticker(symbol)

            end_date = datetime.now()
            start_date = end_date - timedelta(days=lookback_days)

            df = ticker.history(
                start=start_date.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d"),
                interval=interval,
                auto_adjust=True,
            )

            if df is None or df.empty:
                return None

            # Standardize column names (yfinance uses Title Case)
            df = df.rename(columns={
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume",
            })

            # Add timestamp column from index
            df["timestamp"] = df.index
            df["timestamp"] = pd.to_datetime(df["timestamp"])

            # Ensure numeric types
            for col in ["open", "high", "low", "close", "volume"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            # Drop rows with NaN
            df = df.dropna(subset=["open", "high", "low", "close", "volume"])

            # Select only needed columns
            df = df[["open", "high", "low", "close", "volume", "timestamp"]]

            # Sort by timestamp ascending and reset index
            df = df.sort_values("timestamp").reset_index(drop=True)

            return df if not df.empty else None

        except Exception as e:
            logger.debug("yfinance download failed for %s: %s", symbol, e)
            return None
