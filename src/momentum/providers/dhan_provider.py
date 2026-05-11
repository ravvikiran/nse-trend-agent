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

    def __init__(self, batch_size: int = 10):
        """Initialize the Dhan data provider.

        Args:
            batch_size: Maximum number of concurrent symbol fetches per batch.
                        Defaults to 10 to match urllib3 connection pool size.
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

        For 15m timeframe: fetches intraday data with 15-min interval.
        For 1h timeframe: fetches intraday 60-min data (limited to ~5 days).
            If more periods are needed than intraday can provide, falls back
            to daily data as a proxy.
        For 1d timeframe: fetches daily candles directly.

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
        """Fetch OHLCV data for multiple symbols with sequential batching.

        Processes symbols in batches of `batch_size` to avoid rate limits
        and connection pool exhaustion.

        Args:
            symbols: List of NSE stock symbols
            timeframe: One of '15m', '1h', or '1d'
            periods: Number of candles to fetch per symbol

        Returns:
            Dictionary mapping symbol to its OHLCV DataFrame.
            Only symbols with valid data are included in the result.
        """
        results: Dict[str, pd.DataFrame] = {}
        failed_count = 0
        no_security_id_count = 0

        for batch_start in range(0, len(symbols), self.batch_size):
            batch = symbols[batch_start: batch_start + self.batch_size]

            # Process each symbol sequentially within a batch to avoid
            # overwhelming the connection pool
            for symbol in batch:
                # Quick check: does this symbol have a security_id?
                if self._get_security_id(symbol) is None:
                    no_security_id_count += 1
                    continue

                result = await self._fetch_single_safe(symbol, timeframe, periods)
                if result is not None:
                    results[symbol] = result
                else:
                    failed_count += 1

            # Small delay between batches to respect rate limits
            if batch_start + self.batch_size < len(symbols):
                await asyncio.sleep(0.5)

        if no_security_id_count > 0:
            logger.warning(
                "Batch fetch: %d/%d symbols had no security_id mapping",
                no_security_id_count, len(symbols)
            )
        if failed_count > 0:
            logger.warning(
                "Batch fetch: %d symbols failed to return data (timeframe=%s)",
                failed_count, timeframe
            )
        logger.info(
            "Batch fetch complete: %d/%d symbols returned data (timeframe=%s)",
            len(results), len(symbols), timeframe
        )

        return results

    # -------------------------------------------------------------------------
    # Private methods
    # -------------------------------------------------------------------------

    async def _fetch_single_safe(
        self, symbol: str, timeframe: str, periods: int
    ) -> Optional[pd.DataFrame]:
        """Fetch a single symbol's data, catching exceptions for batch use."""
        try:
            result = await self.fetch_ohlcv(symbol, timeframe, periods)
            if result is None:
                logger.debug("fetch_ohlcv returned None for %s (%s)", symbol, timeframe)
            return result
        except Exception as e:
            logger.debug("Error fetching %s in batch: %s", symbol, e)
            return None

    async def _fetch_intraday(
        self, symbol: str, security_id: str, timeframe: str, periods: int
    ) -> Optional[pd.DataFrame]:
        """Fetch intraday data at the requested timeframe directly.

        Dhan's intraday_minute_data supports interval parameter (1, 5, 15, 25, 60)
        for the last 5 trading days.

        Args:
            symbol: Stock symbol for logging.
            security_id: Dhan security ID.
            timeframe: '15m' or '1h'.
            periods: Number of candles needed.

        Returns:
            OHLCV DataFrame or None.
        """
        # Determine exchange segment and instrument type
        exchange_segment, instrument_type = self._get_segment_info(symbol)

        # Map timeframe to Dhan interval parameter
        interval = 60 if timeframe == "1h" else 15

        # Calculate date range
        # Dhan allows up to 90 days per request for intraday data
        # For 1h (210 periods): ~35 trading days = ~50 calendar days
        # For 15m (40 periods): ~2 trading days = ~4 calendar days
        if timeframe == "1h":
            lookback_days = min(90, max(50, periods // 6 * 2))
        else:
            lookback_days = 7  # 5 trading days for 15m

        to_date = datetime.now().strftime("%Y-%m-%d")
        from_date = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

        # Fetch data with the interval parameter
        data = await self._run_with_retry(
            self._dhan.intraday_minute_data,
            security_id,
            exchange_segment,
            instrument_type,
            from_date,
            to_date,
            interval,
        )

        if data is None:
            logger.debug("Intraday data fetch returned None for %s", symbol)
            return None

        # Handle different response formats from the SDK
        if isinstance(data, dict):
            if "status" in data and data.get("status") != "success":
                logger.debug("Intraday data fetch failed for %s: %s", symbol, data)
                return None
            candles = data.get("data", data)  # Use 'data' key if present, else use dict itself
        else:
            logger.debug("Unexpected intraday response type for %s: %s", symbol, type(data))
            return None

        if not candles:
            return None

        # Convert to DataFrame
        df = self._candles_to_dataframe(candles)
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

        if data is None:
            logger.debug("Daily data fetch returned None for %s", symbol)
            return None

        # Handle different response formats from the SDK
        # Some versions wrap in {"status": "success", "data": {...}}
        # Others return the data dict directly {"open": [...], "high": [...], ...}
        if isinstance(data, dict):
            if "status" in data and data.get("status") != "success":
                logger.debug("Daily data fetch failed for %s: %s", symbol, data)
                return None
            candles = data.get("data", data)  # Use 'data' key if present, else use dict itself
        else:
            logger.debug("Unexpected response type for %s: %s", symbol, type(data))
            return None

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
        Dhan's fetch_security_list is a static method that downloads a CSV
        and returns a pandas DataFrame.
        """
        try:
            # fetch_security_list is a static method that downloads CSV and returns DataFrame
            # It saves to 'security_id_list.csv' in the current directory
            loop = asyncio.get_event_loop()

            def _fetch():
                from dhanhq import dhanhq as DhanHQ
                try:
                    df = DhanHQ.fetch_security_list("compact")
                    return df
                except Exception as e:
                    logger.debug("SDK fetch_security_list failed: %s", e)
                    return None

            data = await loop.run_in_executor(None, _fetch)

            df = None

            if isinstance(data, pd.DataFrame) and not data.empty:
                df = data
                logger.debug(
                    "fetch_security_list returned DataFrame with %d rows, columns: %s",
                    len(df), list(df.columns)[:10]
                )
            else:
                # Try reading the CSV file that fetch_security_list may have saved
                import os
                csv_path = "security_id_list.csv"
                if os.path.isfile(csv_path):
                    try:
                        df = pd.read_csv(csv_path)
                        logger.debug("Read security list from saved CSV: %d rows", len(df))
                    except Exception as e:
                        logger.debug("Failed to read saved CSV: %s", e)

            # If SDK method didn't work, download directly
            if df is None or df.empty:
                logger.info("Trying direct CSV download from Dhan CDN...")
                df = await self._download_security_csv()

            if df is not None and not df.empty:
                logger.debug("Security DataFrame columns: %s", list(df.columns))
                self._parse_security_dataframe(df)
            else:
                logger.warning("Could not load security list, using fallback mappings")
                self._add_fallback_mappings()

            # Add well-known index mappings (always)
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
            self._add_fallback_mappings()

    async def _download_security_csv(self) -> Optional[pd.DataFrame]:
        """Download the Dhan security master CSV directly.

        Returns:
            DataFrame of instruments or None on failure.
        """
        import asyncio

        def _download():
            import urllib.request
            url = "https://images.dhan.co/api-data/api-scrip-master.csv"
            try:
                with urllib.request.urlopen(url, timeout=30) as response:
                    return pd.read_csv(response)
            except Exception as e:
                logger.debug("Direct CSV download failed: %s", e)
                return None

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _download)

    def _parse_security_dataframe(self, df: pd.DataFrame) -> None:
        """Parse a security list DataFrame into the symbol -> security_id mapping.

        Handles both compact and detailed CSV column naming conventions from Dhan.

        Args:
            df: DataFrame from Dhan's instrument CSV.
        """
        # Identify column names (Dhan uses different naming in compact vs detailed)
        # Compact CSV columns: SEM_SMST_SECURITY_ID, SEM_TRADING_SYMBOL,
        #                      SEM_EXM_EXCH_ID, SEM_SEGMENT, SM_SYMBOL_NAME, etc.
        # Also handle: securityId, tradingSymbol, exchangeSegment (SDK dict format)

        sec_id_col = None
        symbol_col = None
        exchange_col = None
        segment_col = None

        # Map possible column names
        for col in df.columns:
            col_lower = col.lower().replace(" ", "").replace("_", "")
            if col_lower in ("semsmst securityid", "semsmstsecurityid", "securityid", "security_id"):
                sec_id_col = col
            elif col in ("SEM_SMST_SECURITY_ID",):
                sec_id_col = col
            elif col in ("SEM_TRADING_SYMBOL", "tradingSymbol", "TRADING_SYMBOL"):
                symbol_col = col
            elif col_lower in ("semtradingsymbol",):
                symbol_col = col
            elif col in ("SEM_EXM_EXCH_ID", "exchangeSegment", "EXCH_ID", "EXCHANGE"):
                exchange_col = col
            elif col_lower in ("semexmexchid",):
                exchange_col = col
            elif col in ("SEM_SEGMENT", "SEGMENT"):
                segment_col = col
            elif col_lower in ("semsegment",):
                segment_col = col

        # Try common column name patterns if not found
        if sec_id_col is None:
            for col in df.columns:
                if "security" in col.lower() and "id" in col.lower():
                    sec_id_col = col
                    break

        if symbol_col is None:
            for col in df.columns:
                if "trading" in col.lower() and "symbol" in col.lower():
                    symbol_col = col
                    break
            if symbol_col is None:
                for col in df.columns:
                    if "symbol" in col.lower() and "name" not in col.lower():
                        symbol_col = col
                        break

        if exchange_col is None:
            for col in df.columns:
                if "exch" in col.lower() and ("id" in col.lower() or "segment" in col.lower()):
                    exchange_col = col
                    break

        if sec_id_col is None or symbol_col is None:
            logger.warning(
                "Could not identify required columns in security CSV. "
                "Columns found: %s", list(df.columns)[:10]
            )
            return

        logger.debug(
            "Security CSV columns: sec_id=%s, symbol=%s, exchange=%s, segment=%s",
            sec_id_col, symbol_col, exchange_col, segment_col,
        )

        # Filter for NSE equities only
        if exchange_col:
            nse_mask = df[exchange_col].astype(str).isin(["NSE", "NSE_EQ"])
            if segment_col:
                # Also include equity segment
                eq_mask = df[segment_col].astype(str).isin(["E", "EQ", "EQUITY"])
                filtered = df[nse_mask & eq_mask] if not eq_mask.all() else df[nse_mask]
            else:
                filtered = df[nse_mask]
        else:
            # No exchange column — use all rows
            filtered = df

        if filtered.empty:
            # If filtering removed everything, try without segment filter
            if exchange_col:
                filtered = df[df[exchange_col].astype(str).isin(["NSE", "NSE_EQ"])]
            if filtered.empty:
                filtered = df

        count = 0
        for _, row in filtered.iterrows():
            sym = str(row.get(symbol_col, "")).strip()
            sec_id = str(row.get(sec_id_col, "")).strip()

            if not sym or not sec_id or sec_id in ("", "nan", "None"):
                continue

            # Store multiple variations for flexible matching
            clean_sym = sym.replace("-EQ", "").replace(".NS", "").strip()
            if clean_sym:
                self._security_list[clean_sym] = sec_id
                self._security_list[f"{clean_sym}.NS"] = sec_id
                self._security_list[sym] = sec_id
                count += 1

        logger.debug("Parsed %d NSE equity symbols from security CSV", count)

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
                # Dhan returns epoch timestamps as integers (seconds since epoch)
                # Check if values look like epoch timestamps (large integers)
                sample = df["timestamp"].iloc[0] if len(df) > 0 else None
                if sample is not None and isinstance(sample, (int, float)) and sample > 1_000_000_000:
                    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
                else:
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
