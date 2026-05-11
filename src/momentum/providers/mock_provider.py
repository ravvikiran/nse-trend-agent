"""
Mock DataProvider for testing the momentum scanner pipeline.

Generates realistic OHLCV DataFrames with configurable behavior:
- Trending data (for testing Stage 1 bullish detection)
- Volume expansion patterns (for testing Stage 3 triggers)
- Missing data simulation (for testing graceful skip behavior)
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from src.momentum.data_provider import DataProvider

logger = logging.getLogger(__name__)


class MockDataProvider(DataProvider):
    """Mock data provider for testing that returns realistic OHLCV DataFrames.

    Generates synthetic market data with configurable patterns:
    - Uptrending stocks (price above EMAs, positive slope)
    - Consolidating stocks (tight range candles)
    - Volume expansion events
    - Configurable failures for error handling tests

    Attributes:
        connected: Whether the provider is currently connected.
        symbols_to_fail: Set of symbols that will return None (simulating API failures).
        base_prices: Dictionary of base prices per symbol for consistent generation.
    """

    # Realistic NSE stock base prices
    DEFAULT_BASE_PRICES: Dict[str, float] = {
        "RELIANCE": 2450.0,
        "TCS": 3800.0,
        "HDFCBANK": 1650.0,
        "INFY": 1480.0,
        "ICICIBANK": 1050.0,
        "HINDUNILVR": 2550.0,
        "ITC": 440.0,
        "SBIN": 620.0,
        "BHARTIARTL": 1350.0,
        "KOTAKBANK": 1750.0,
        "LT": 3400.0,
        "AXISBANK": 1100.0,
        "TATAMOTORS": 950.0,
        "MARUTI": 11500.0,
        "SUNPHARMA": 1200.0,
        "TITAN": 3200.0,
        "BAJFINANCE": 6800.0,
        "WIPRO": 450.0,
        "ASIANPAINT": 2900.0,
        "ULTRACEMCO": 9500.0,
        "NIFTY 50": 22500.0,
    }

    # Timeframe to candle duration mapping
    TIMEFRAME_MINUTES: Dict[str, int] = {
        "15m": 15,
        "1h": 60,
        "1d": 375,  # NSE trading day ~6.25 hours
    }

    def __init__(
        self,
        base_prices: Optional[Dict[str, float]] = None,
        symbols_to_fail: Optional[set] = None,
        trend_bias: float = 0.6,
        volatility: float = 0.015,
        seed: Optional[int] = None,
    ):
        """Initialize the mock data provider.

        Args:
            base_prices: Custom base prices per symbol. Falls back to defaults.
            symbols_to_fail: Symbols that will return None (simulating failures).
            trend_bias: Probability of upward movement per candle (0.5 = neutral).
            volatility: Base volatility as fraction of price (0.015 = 1.5%).
            seed: Random seed for reproducible test data.
        """
        self.connected = False
        self.base_prices = base_prices or self.DEFAULT_BASE_PRICES.copy()
        self.symbols_to_fail = symbols_to_fail or set()
        self.trend_bias = trend_bias
        self.volatility = volatility
        self._rng = np.random.default_rng(seed)

    async def connect(self) -> bool:
        """Simulate successful connection."""
        self.connected = True
        logger.debug("MockDataProvider connected")
        return True

    async def disconnect(self) -> None:
        """Simulate disconnection."""
        self.connected = False
        logger.debug("MockDataProvider disconnected")

    async def fetch_ohlcv(
        self, symbol: str, timeframe: str, periods: int
    ) -> Optional[pd.DataFrame]:
        """Generate realistic OHLCV data for a single symbol.

        Args:
            symbol: NSE stock symbol
            timeframe: One of '15m', '1h', or '1d'
            periods: Number of candles to generate

        Returns:
            DataFrame with columns [open, high, low, close, volume, timestamp]
            or None if symbol is in the failure set.
        """
        if symbol in self.symbols_to_fail:
            logger.debug(f"MockDataProvider: simulating failure for {symbol}")
            return None

        if timeframe not in self.TIMEFRAME_MINUTES:
            logger.warning(f"MockDataProvider: unsupported timeframe '{timeframe}'")
            return None

        base_price = self.base_prices.get(symbol, 1000.0)
        return self._generate_ohlcv(symbol, timeframe, periods, base_price)

    async def fetch_batch(
        self, symbols: list[str], timeframe: str, periods: int
    ) -> Dict[str, pd.DataFrame]:
        """Generate OHLCV data for multiple symbols.

        Skips symbols that are in the failure set.

        Args:
            symbols: List of NSE stock symbols
            timeframe: One of '15m', '1h', or '1d'
            periods: Number of candles per symbol

        Returns:
            Dictionary mapping symbol to OHLCV DataFrame.
        """
        results: Dict[str, pd.DataFrame] = {}

        for symbol in symbols:
            df = await self.fetch_ohlcv(symbol, timeframe, periods)
            if df is not None:
                results[symbol] = df

        return results

    def _generate_ohlcv(
        self, symbol: str, timeframe: str, periods: int, base_price: float
    ) -> pd.DataFrame:
        """Generate a realistic OHLCV DataFrame.

        Uses a random walk with trend bias to create price series that
        resemble real market data with proper OHLC relationships.

        Args:
            symbol: Stock symbol (used for volume scaling)
            timeframe: Candle timeframe
            periods: Number of candles
            base_price: Starting price level

        Returns:
            DataFrame with columns [open, high, low, close, volume, timestamp]
        """
        candle_minutes = self.TIMEFRAME_MINUTES[timeframe]

        # Generate timestamps (working backwards from now)
        end_time = datetime(2024, 3, 15, 15, 30)  # Fixed end for reproducibility
        timestamps = []
        current_time = end_time
        for _ in range(periods):
            timestamps.append(current_time)
            current_time -= timedelta(minutes=candle_minutes)
        timestamps.reverse()

        # Generate price series using random walk with trend bias
        opens = []
        highs = []
        lows = []
        closes = []
        volumes = []

        price = base_price
        base_volume = self._get_base_volume(symbol, timeframe)

        for i in range(periods):
            open_price = price

            # Direction based on trend bias
            direction = 1 if self._rng.random() < self.trend_bias else -1

            # Candle body size (0.2% to 1.5% of price)
            body_pct = self._rng.uniform(0.002, 0.015) * self.volatility / 0.015
            body = price * body_pct * direction

            close_price = open_price + body

            # Wicks extend beyond body
            upper_wick = price * self._rng.uniform(0.001, 0.008)
            lower_wick = price * self._rng.uniform(0.001, 0.008)

            high_price = max(open_price, close_price) + upper_wick
            low_price = min(open_price, close_price) - lower_wick

            # Volume with some randomness and occasional spikes
            vol_multiplier = self._rng.lognormal(0, 0.4)
            # Occasional volume spike (10% chance)
            if self._rng.random() < 0.10:
                vol_multiplier *= self._rng.uniform(2.0, 4.0)
            volume = int(base_volume * vol_multiplier)

            opens.append(round(open_price, 2))
            highs.append(round(high_price, 2))
            lows.append(round(low_price, 2))
            closes.append(round(close_price, 2))
            volumes.append(volume)

            # Next candle opens near this close (small gap)
            gap = price * self._rng.uniform(-0.002, 0.002)
            price = close_price + gap

        df = pd.DataFrame(
            {
                "open": opens,
                "high": highs,
                "low": lows,
                "close": closes,
                "volume": volumes,
                "timestamp": timestamps,
            }
        )

        return df

    def _get_base_volume(self, symbol: str, timeframe: str) -> int:
        """Get realistic base volume for a symbol and timeframe.

        Large-cap stocks have higher volume. Shorter timeframes have
        proportionally less volume per candle.

        Args:
            symbol: Stock symbol
            timeframe: Candle timeframe

        Returns:
            Base volume for the symbol/timeframe combination.
        """
        # Base daily volumes (approximate realistic values)
        daily_volumes: Dict[str, int] = {
            "RELIANCE": 8_000_000,
            "TCS": 3_000_000,
            "HDFCBANK": 10_000_000,
            "INFY": 6_000_000,
            "ICICIBANK": 12_000_000,
            "SBIN": 20_000_000,
            "ITC": 15_000_000,
            "TATAMOTORS": 18_000_000,
            "NIFTY 50": 50_000_000,
        }

        daily_vol = daily_volumes.get(symbol, 5_000_000)

        # Scale by timeframe (approximate candles per day)
        candles_per_day = {
            "15m": 25,  # 6.25 hours / 15 min
            "1h": 6,    # 6.25 hours / 1 hour
            "1d": 1,
        }

        n_candles = candles_per_day.get(timeframe, 1)
        return daily_vol // n_candles

    # --- Convenience methods for test scenarios ---

    def set_symbols_to_fail(self, symbols: set) -> None:
        """Configure which symbols should return None (simulating API failures).

        Args:
            symbols: Set of symbol names that will fail.
        """
        self.symbols_to_fail = symbols

    def set_base_price(self, symbol: str, price: float) -> None:
        """Set a custom base price for a symbol.

        Args:
            symbol: Stock symbol
            price: Base price to use for data generation
        """
        self.base_prices[symbol] = price
