"""
Stage 1 Trend Filter — Higher-Timeframe Trend Structure (1H)

Filters stocks for bullish trend alignment on the 1-hour timeframe.
A stock is classified as bullish ONLY when ALL conditions hold:
  1. Price > EMA(200)
  2. EMA(20) > EMA(50)
  3. EMA(200) slope > 0

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5
"""

import logging
from typing import Dict, List, Tuple

import pandas as pd
from ta.trend import EMAIndicator

from src.momentum.models import ScannerConfig

logger = logging.getLogger(__name__)


class Stage1TrendFilter:
    """Filters stocks for bullish 1H trend structure.

    Uses EMA(20), EMA(50), EMA(200) alignment and EMA(200) slope
    to determine if a stock is in a higher-timeframe uptrend.
    """

    def __init__(self, config: ScannerConfig | None = None):
        """Initialize with scanner configuration.

        Args:
            config: Scanner configuration. Uses defaults if None.
        """
        self.config = config or ScannerConfig()
        self.ema_fast = self.config.ema_fast  # 20
        self.ema_medium = self.config.ema_medium  # 50
        self.ema_slow = self.config.ema_slow  # 200
        self.slope_lookback = self.config.ema_slope_lookback  # 5

    def filter(self, stocks_1h_data: Dict[str, pd.DataFrame]) -> List[str]:
        """Filter stocks passing all bullish trend conditions on 1H data.

        Evaluates each stock's 1H OHLCV DataFrame for:
          - Price > EMA(200)
          - EMA(20) > EMA(50)
          - EMA(200) slope positive (diff over slope_lookback periods / slope_lookback > 0)

        Args:
            stocks_1h_data: Mapping of symbol -> 1H OHLCV DataFrame.
                Each DataFrame must have columns: open, high, low, close, volume.

        Returns:
            List of symbols that pass all bullish conditions.
        """
        passed_symbols: List[str] = []

        for symbol, df in stocks_1h_data.items():
            try:
                if not self._is_valid_dataframe(df):
                    logger.debug(f"{symbol}: insufficient data for Stage 1 filter")
                    continue

                is_bullish = self._evaluate_bullish(df)
                if is_bullish:
                    passed_symbols.append(symbol)
                else:
                    logger.debug(f"{symbol}: failed Stage 1 trend filter")

            except Exception as e:
                logger.error(f"{symbol}: error in Stage 1 filter — {e}")
                continue

        logger.info(
            f"Stage 1 Trend Filter: {len(passed_symbols)}/{len(stocks_1h_data)} stocks passed"
        )
        return passed_symbols

    def calculate_trend_quality_score(self, df: pd.DataFrame) -> float:
        """Calculate trend quality score (0-100) for a stock's 1H data.

        Score is based on:
          - EMA alignment strength: how far apart the EMAs are (relative spread)
          - EMA(200) slope magnitude: steeper positive slope = higher score

        The score combines:
          - Alignment component (60% weight): measures EMA separation relative to price
          - Slope component (40% weight): measures EMA(200) slope magnitude

        Args:
            df: 1H OHLCV DataFrame with columns: open, high, low, close, volume.

        Returns:
            Score between 0 and 100. Returns 0 if data is insufficient.
        """
        if not self._is_valid_dataframe(df):
            return 0.0

        try:
            ema_20, ema_50, ema_200 = self._calculate_emas(df)

            # Get latest values
            current_close = df["close"].iloc[-1]
            current_ema_20 = ema_20.iloc[-1]
            current_ema_50 = ema_50.iloc[-1]
            current_ema_200 = ema_200.iloc[-1]

            # --- Alignment component (60% weight) ---
            alignment_score = self._calculate_alignment_score(
                current_close, current_ema_20, current_ema_50, current_ema_200
            )

            # --- Slope component (40% weight) ---
            slope = self._calculate_ema_slope(ema_200)
            slope_score = self._calculate_slope_score(slope, current_ema_200)

            # Weighted combination
            total_score = (alignment_score * 0.6) + (slope_score * 0.4)

            # Clamp to [0, 100]
            return max(0.0, min(100.0, total_score))

        except Exception as e:
            logger.error(f"Error calculating trend quality score: {e}")
            return 0.0

    def _is_valid_dataframe(self, df: pd.DataFrame) -> bool:
        """Check if DataFrame has enough data for EMA(200) + slope lookback."""
        if df is None or df.empty:
            return False

        required_columns = {"close"}
        if not required_columns.issubset(df.columns):
            return False

        # Need at least ema_slow + slope_lookback rows for valid calculation
        min_rows = self.ema_slow + self.slope_lookback
        return len(df) >= min_rows

    def _calculate_emas(
        self, df: pd.DataFrame
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate EMA(20), EMA(50), EMA(200) for the given DataFrame.

        Returns:
            Tuple of (ema_20_series, ema_50_series, ema_200_series)
        """
        ema_20_indicator = EMAIndicator(close=df["close"], window=self.ema_fast)
        ema_50_indicator = EMAIndicator(close=df["close"], window=self.ema_medium)
        ema_200_indicator = EMAIndicator(close=df["close"], window=self.ema_slow)

        return (
            ema_20_indicator.ema_indicator(),
            ema_50_indicator.ema_indicator(),
            ema_200_indicator.ema_indicator(),
        )

    def _calculate_ema_slope(self, ema_200: pd.Series) -> float:
        """Calculate EMA(200) slope as per requirement 3.4.

        Slope = (EMA200_current - EMA200_N_periods_ago) / N
        where N = ema_slope_lookback (default 5).

        Args:
            ema_200: Full EMA(200) series.

        Returns:
            Slope value (positive = uptrend, negative = downtrend).
        """
        current_ema = ema_200.iloc[-1]
        past_ema = ema_200.iloc[-(self.slope_lookback + 1)]
        return (current_ema - past_ema) / self.slope_lookback

    def _evaluate_bullish(self, df: pd.DataFrame) -> bool:
        """Evaluate all three bullish conditions for a stock.

        Conditions (all must be true):
          1. Price (close) > EMA(200)
          2. EMA(20) > EMA(50)
          3. EMA(200) slope > 0

        Args:
            df: 1H OHLCV DataFrame.

        Returns:
            True if all conditions are met.
        """
        ema_20, ema_50, ema_200 = self._calculate_emas(df)

        current_close = df["close"].iloc[-1]
        current_ema_20 = ema_20.iloc[-1]
        current_ema_50 = ema_50.iloc[-1]
        current_ema_200 = ema_200.iloc[-1]

        # Check for NaN values (insufficient data for EMA calculation)
        if pd.isna(current_ema_20) or pd.isna(current_ema_50) or pd.isna(current_ema_200):
            return False

        # Condition 1: Price > EMA(200)
        price_above_ema200 = current_close > current_ema_200

        # Condition 2: EMA(20) > EMA(50)
        ema_alignment = current_ema_20 > current_ema_50

        # Condition 3: EMA(200) slope > 0
        slope = self._calculate_ema_slope(ema_200)
        positive_slope = slope > 0

        return price_above_ema200 and ema_alignment and positive_slope

    def _calculate_alignment_score(
        self,
        close: float,
        ema_20: float,
        ema_50: float,
        ema_200: float,
    ) -> float:
        """Calculate EMA alignment strength score (0-100).

        Measures how well-separated the EMAs are in bullish order.
        Higher separation (relative to price) = stronger trend.

        The score considers:
          - Price distance above EMA(200) (normalized)
          - EMA(20) distance above EMA(50) (normalized)
          - EMA(50) distance above EMA(200) (normalized)

        Args:
            close: Current close price.
            ema_20: Current EMA(20) value.
            ema_50: Current EMA(50) value.
            ema_200: Current EMA(200) value.

        Returns:
            Alignment score 0-100.
        """
        if ema_200 <= 0:
            return 0.0

        # Normalize distances as percentage of EMA(200)
        price_spread = (close - ema_200) / ema_200 * 100  # % above EMA200
        ema20_50_spread = (ema_20 - ema_50) / ema_200 * 100  # EMA20-50 gap
        ema50_200_spread = (ema_50 - ema_200) / ema_200 * 100  # EMA50-200 gap

        # Only score positive spreads (bullish alignment)
        price_spread = max(0.0, price_spread)
        ema20_50_spread = max(0.0, ema20_50_spread)
        ema50_200_spread = max(0.0, ema50_200_spread)

        # Map spreads to 0-100 using reasonable thresholds
        # A 10% spread above EMA200 is considered very strong
        price_component = min(100.0, price_spread / 10.0 * 100.0)
        # A 2% EMA20-50 spread is considered strong
        ema20_50_component = min(100.0, ema20_50_spread / 2.0 * 100.0)
        # A 5% EMA50-200 spread is considered strong
        ema50_200_component = min(100.0, ema50_200_spread / 5.0 * 100.0)

        # Weighted average of components
        alignment_score = (
            price_component * 0.4
            + ema20_50_component * 0.3
            + ema50_200_component * 0.3
        )

        return min(100.0, alignment_score)

    def _calculate_slope_score(self, slope: float, ema_200: float) -> float:
        """Calculate slope magnitude score (0-100).

        Normalizes the raw slope relative to the EMA(200) value to get
        a percentage-based slope, then maps to 0-100.

        Args:
            slope: Raw EMA(200) slope value.
            ema_200: Current EMA(200) value for normalization.

        Returns:
            Slope score 0-100.
        """
        if ema_200 <= 0:
            return 0.0

        # Normalize slope as percentage of EMA(200)
        # slope is per-period change, so this gives % change per period
        normalized_slope = (slope / ema_200) * 100

        # Only positive slopes contribute to score
        if normalized_slope <= 0:
            return 0.0

        # Map to 0-100: a 0.5% per-period slope is considered very strong
        slope_score = min(100.0, normalized_slope / 0.5 * 100.0)

        return slope_score
