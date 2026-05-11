"""
Abstract DataProvider interface for broker API data fetching.

Defines the contract for all concrete data provider implementations
(Zerodha Kite, Angel One, Fyers, Upstox). The scanner uses this interface
to fetch OHLCV data without coupling to any specific broker.
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional

import pandas as pd


class DataProvider(ABC):
    """Abstract interface for broker API data fetching.

    All concrete data providers must implement these methods to supply
    OHLCV market data to the momentum scanner pipeline.

    Supported timeframes: '15m', '1h', '1d'
    DataFrame columns: open, high, low, close, volume, timestamp
    """

    @abstractmethod
    async def fetch_ohlcv(
        self, symbol: str, timeframe: str, periods: int
    ) -> Optional[pd.DataFrame]:
        """Fetch OHLCV data for a single symbol.

        Args:
            symbol: NSE stock symbol (e.g., 'RELIANCE', 'TCS', 'NIFTY 50')
            timeframe: One of '15m', '1h', or '1d'
            periods: Number of candles to fetch

        Returns:
            DataFrame with columns [open, high, low, close, volume, timestamp]
            sorted by timestamp ascending, or None if data is unavailable.
        """
        pass

    @abstractmethod
    async def fetch_batch(
        self, symbols: list[str], timeframe: str, periods: int
    ) -> Dict[str, pd.DataFrame]:
        """Fetch OHLCV data for multiple symbols concurrently.

        Skips symbols that return no data without raising errors.

        Args:
            symbols: List of NSE stock symbols
            timeframe: One of '15m', '1h', or '1d'
            periods: Number of candles to fetch per symbol

        Returns:
            Dictionary mapping symbol to its OHLCV DataFrame.
            Only symbols with valid data are included in the result.
        """
        pass

    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection / authenticate with broker API.

        Returns:
            True if connection was successful, False otherwise.
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Clean up connection resources.

        Should be safe to call multiple times.
        """
        pass
