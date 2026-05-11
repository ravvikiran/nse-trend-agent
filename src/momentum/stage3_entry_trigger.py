"""
Stage 3 Entry Trigger Detection — 15-minute Timeframe

Detects entry setups on the 15-minute chart:
  - PULLBACK_CONTINUATION: price near EMA(20) + bullish candle + volume > 1.5x avg + breaks prev high
  - COMPRESSION_BREAKOUT: 3-6 tight candles + ATR contraction + volume expansion + strong breakout

Assigns exactly one SetupType per stock per scan cycle (mutual exclusivity).
If both patterns match, the one with higher breakout_strength wins.

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5
"""

import logging
from dataclasses import dataclass
from typing import Optional

import pandas as pd
from ta.trend import EMAIndicator
from ta.volatility import AverageTrueRange

from src.momentum.models import ScannerConfig, SetupType

logger = logging.getLogger(__name__)


@dataclass
class EntryTriggerResult:
    """Result of a detected entry trigger on 15m timeframe."""

    setup_type: SetupType
    breakout_strength: float  # 0-100 composite score
    trigger_candle_index: int  # Index of the trigger candle in the DataFrame
    entry_price: float  # Trigger/breakout candle high
    relative_volume: Optional[float] = None  # current_volume / SMA(volume, 30)


class Stage3EntryTrigger:
    """Detects entry setups on the 15-minute timeframe.

    Evaluates two mutually exclusive patterns:
      1. PULLBACK_CONTINUATION: price pulls back near EMA(20), forms a bullish
         candle with volume expansion, and breaks the previous candle's high.
      2. COMPRESSION_BREAKOUT: 3-6 tight-range candles with ATR contraction,
         followed by a strong breakout candle with volume expansion.

    Only ONE setup type is assigned per stock per scan cycle. If both patterns
    match, the one with higher breakout_strength is selected.
    """

    # Minimum candles required for reliable detection
    MIN_CANDLES = 35  # Need enough for EMA(20) + volume SMA(30) + lookback

    def __init__(self, config: ScannerConfig | None = None):
        """Initialize with scanner configuration.

        Args:
            config: Scanner configuration. Uses defaults if None.
        """
        self.config = config or ScannerConfig()
        self.ema_period = self.config.ema_fast  # 20
        self.volume_ma_period = self.config.volume_ma_period  # 30
        self.volume_expansion_threshold = self.config.volume_expansion_threshold  # 1.5
        self.atr_period = self.config.atr_period  # 14
        self.min_breakout_strength = self.config.min_breakout_strength  # 40.0

    def detect(self, df_15m: pd.DataFrame) -> Optional[EntryTriggerResult]:
        """Detect entry trigger on 15m OHLCV data for a single stock.

        Checks for both PULLBACK_CONTINUATION and COMPRESSION_BREAKOUT patterns.
        Assigns exactly one setup type per stock per cycle. If both match,
        the pattern with higher breakout_strength wins.

        Args:
            df_15m: 15-minute OHLCV DataFrame with columns:
                    open, high, low, close, volume.
                    Must have at least MIN_CANDLES rows.

        Returns:
            EntryTriggerResult if a trigger is detected, None otherwise.
            Returns None if breakout_strength is below min_breakout_strength.
        """
        if not self._is_valid_dataframe(df_15m):
            return None

        # Check both patterns
        pullback_result = self._check_pullback_continuation(df_15m)
        compression_result = self._check_compression_breakout(df_15m)

        # If neither pattern matches, no trigger
        if pullback_result is None and compression_result is None:
            return None

        # If only one matches, use it
        if pullback_result is None:
            result = compression_result
        elif compression_result is None:
            result = pullback_result
        else:
            # Both match — pick the one with higher breakout_strength
            if compression_result.breakout_strength >= pullback_result.breakout_strength:
                result = compression_result
            else:
                result = pullback_result

        # Filter by minimum breakout strength threshold
        if result.breakout_strength < self.min_breakout_strength:
            logger.debug(
                "Breakout strength %.1f below threshold %.1f, excluding",
                result.breakout_strength,
                self.min_breakout_strength,
            )
            return None

        # Exclude stock if relative volume is unavailable (Requirement 6.4)
        if result.relative_volume is None:
            logger.debug(
                "Relative volume unavailable (volume SMA zero or insufficient data), excluding"
            )
            return None

        # RSI filter: RSI(14) must be between 50 and 80 (momentum zone, not overbought)
        rsi = self._calculate_rsi(df_15m)
        if rsi is not None:
            if rsi < 50 or rsi > 80:
                logger.debug(
                    "RSI %.1f outside momentum zone [50, 80], excluding", rsi
                )
                return None

        # ATR minimum filter: ATR(14) must be > 1% of price (avoid dead stocks)
        atr_pct = self._calculate_atr_percentage(df_15m)
        if atr_pct is not None and atr_pct < 1.0:
            logger.debug(
                "ATR %.2f%% below 1%% of price (dead stock), excluding", atr_pct
            )
            return None

        return result

    def _check_pullback_continuation(
        self, df: pd.DataFrame
    ) -> Optional[EntryTriggerResult]:
        """Check for PULLBACK_CONTINUATION pattern.

        Conditions (all must be true on the latest candle):
          1. Price is near EMA(20) — close within 1% of EMA(20)
          2. Bullish candle — close > open with body > 50% of range
          3. Volume > 1.5x average volume (30-period SMA)
          4. Price breaks previous candle's high — current high > previous high

        Args:
            df: 15m OHLCV DataFrame.

        Returns:
            EntryTriggerResult with PULLBACK_CONTINUATION if pattern matches,
            None otherwise.
        """
        # Calculate EMA(20)
        ema_indicator = EMAIndicator(close=df["close"], window=self.ema_period)
        ema_20 = ema_indicator.ema_indicator()

        # Calculate volume SMA(30)
        volume_sma = df["volume"].rolling(window=self.volume_ma_period).mean()

        # Get latest candle and previous candle
        latest_idx = len(df) - 1
        if latest_idx < 1:
            return None

        current = df.iloc[latest_idx]
        previous = df.iloc[latest_idx - 1]
        current_ema = ema_20.iloc[latest_idx]
        current_vol_sma = volume_sma.iloc[latest_idx]

        # Skip if EMA or volume SMA is NaN
        if pd.isna(current_ema) or pd.isna(current_vol_sma) or current_vol_sma == 0:
            return None

        # Condition 1: Price near EMA(20) — within 1% distance
        ema_distance_pct = abs(current["close"] - current_ema) / current_ema * 100
        near_ema = ema_distance_pct <= 1.0

        # Condition 2: Bullish candle — close > open, body > 50% of range
        candle_range = current["high"] - current["low"]
        if candle_range == 0:
            return None
        body = current["close"] - current["open"]
        is_bullish = body > 0 and (body / candle_range) > 0.5

        # Condition 3: Volume > 1.5x average
        relative_volume = current["volume"] / current_vol_sma
        has_volume_expansion = relative_volume >= self.volume_expansion_threshold

        # Condition 4: Breaks previous candle high
        breaks_prev_high = current["high"] > previous["high"]

        if near_ema and is_bullish and has_volume_expansion and breaks_prev_high:
            breakout_strength = self._calculate_breakout_strength(df)
            rv = self._calculate_relative_volume(df)
            return EntryTriggerResult(
                setup_type=SetupType.PULLBACK_CONTINUATION,
                breakout_strength=breakout_strength,
                trigger_candle_index=latest_idx,
                entry_price=current["high"],
                relative_volume=rv,
            )

        return None

    def _check_compression_breakout(
        self, df: pd.DataFrame
    ) -> Optional[EntryTriggerResult]:
        """Check for COMPRESSION_BREAKOUT pattern.

        Conditions:
          1. 3-6 tight-range candles preceding the breakout candle
             (range of each candle < 70% of ATR at that point)
          2. ATR contraction — ATR of the tight candles is less than 70% of
             the ATR from 10 candles prior
          3. Volume expansion on breakout candle — volume > 1.5x average
          4. Strong breakout candle — closes near its high (close in top 25% of range)

        Args:
            df: 15m OHLCV DataFrame.

        Returns:
            EntryTriggerResult with COMPRESSION_BREAKOUT if pattern matches,
            None otherwise.
        """
        # Calculate ATR(14)
        atr_indicator = AverageTrueRange(
            high=df["high"], low=df["low"], close=df["close"], window=self.atr_period
        )
        atr_series = atr_indicator.average_true_range()

        # Calculate volume SMA(30)
        volume_sma = df["volume"].rolling(window=self.volume_ma_period).mean()

        latest_idx = len(df) - 1
        if latest_idx < 7:  # Need at least 7 candles (6 tight + 1 breakout)
            return None

        current = df.iloc[latest_idx]
        current_atr = atr_series.iloc[latest_idx]
        current_vol_sma = volume_sma.iloc[latest_idx]

        # Skip if ATR or volume SMA is NaN/zero
        if pd.isna(current_atr) or current_atr == 0:
            return None
        if pd.isna(current_vol_sma) or current_vol_sma == 0:
            return None

        # Condition 4: Strong breakout candle — close near high (top 25% of range)
        breakout_range = current["high"] - current["low"]
        if breakout_range == 0:
            return None
        close_position = (current["close"] - current["low"]) / breakout_range
        is_strong_breakout = close_position >= 0.75

        if not is_strong_breakout:
            return None

        # Condition 3: Volume expansion on breakout candle
        relative_volume = current["volume"] / current_vol_sma
        has_volume_expansion = relative_volume >= self.volume_expansion_threshold

        if not has_volume_expansion:
            return None

        # Condition 1 & 2: Look for 3-6 tight-range candles before the breakout
        # Check windows of 3, 4, 5, 6 candles preceding the current candle
        found_compression = False
        for lookback in range(3, 7):  # 3 to 6 candles
            start_idx = latest_idx - lookback
            if start_idx < 0:
                continue

            tight_candles = df.iloc[start_idx:latest_idx]  # Exclude breakout candle

            # Check if all candles in the window are tight-range
            # Tight = range < 70% of ATR at that point
            all_tight = True
            for i in range(len(tight_candles)):
                candle = tight_candles.iloc[i]
                candle_range = candle["high"] - candle["low"]
                atr_at_point = atr_series.iloc[start_idx + i]
                if pd.isna(atr_at_point) or atr_at_point == 0:
                    all_tight = False
                    break
                if candle_range >= 0.7 * atr_at_point:
                    all_tight = False
                    break

            if not all_tight:
                continue

            # Condition 2: ATR contraction — current ATR < 70% of ATR from 10 candles ago
            atr_lookback_idx = latest_idx - 10
            if atr_lookback_idx < 0:
                atr_lookback_idx = 0
            prior_atr = atr_series.iloc[atr_lookback_idx]
            if pd.isna(prior_atr) or prior_atr == 0:
                continue

            has_atr_contraction = current_atr < 0.7 * prior_atr

            if has_atr_contraction:
                found_compression = True
                break

        if not found_compression:
            return None

        breakout_strength = self._calculate_breakout_strength(df)
        rv = self._calculate_relative_volume(df)
        return EntryTriggerResult(
            setup_type=SetupType.COMPRESSION_BREAKOUT,
            breakout_strength=breakout_strength,
            trigger_candle_index=latest_idx,
            entry_price=current["high"],
            relative_volume=rv,
        )

    def _calculate_breakout_strength(self, df: pd.DataFrame) -> float:
        """Calculate composite breakout strength score (0-100).

        Components (each normalized to 0-100, then averaged):
          1. Body/Range ratio: candle body size relative to total range (20% weight)
          2. Close/High proximity: how close the close is to the high (20% weight)
          3. Range expansion: current range vs average of previous 5 candles (20% weight)
          4. Volume strength: current volume vs 30-period SMA (20% weight)
          5. Momentum acceleration: current range vs previous candle range (20% weight)

        Args:
            df: 15m OHLCV DataFrame.

        Returns:
            Breakout strength score clamped to [0, 100].
        """
        latest_idx = len(df) - 1
        if latest_idx < 1:
            return 0.0

        current = df.iloc[latest_idx]
        previous = df.iloc[latest_idx - 1]

        # --- Component 1: Body/Range ratio (20%) ---
        candle_range = current["high"] - current["low"]
        if candle_range == 0:
            body_ratio_score = 0.0
        else:
            body = abs(current["close"] - current["open"])
            body_ratio = body / candle_range
            # Map 0-1 ratio to 0-100 score (higher body ratio = stronger)
            body_ratio_score = min(100.0, body_ratio * 100.0)

        # --- Component 2: Close/High proximity (20%) ---
        if candle_range == 0:
            close_high_score = 0.0
        else:
            # How close is close to high? 1.0 = close at high, 0.0 = close at low
            close_position = (current["close"] - current["low"]) / candle_range
            close_high_score = min(100.0, close_position * 100.0)

        # --- Component 3: Range expansion (20%) ---
        # Compare current range to average range of previous 5 candles
        lookback = min(5, latest_idx)
        if lookback > 0:
            prev_ranges = (
                df["high"].iloc[latest_idx - lookback : latest_idx]
                - df["low"].iloc[latest_idx - lookback : latest_idx]
            )
            avg_prev_range = prev_ranges.mean()
            if avg_prev_range > 0:
                range_expansion_ratio = candle_range / avg_prev_range
                # Map: 1.0 = no expansion (50 score), 2.0+ = strong expansion (100)
                range_expansion_score = min(100.0, range_expansion_ratio * 50.0)
            else:
                range_expansion_score = 50.0
        else:
            range_expansion_score = 50.0

        # --- Component 4: Volume strength (20%) ---
        volume_sma = df["volume"].rolling(window=self.volume_ma_period).mean()
        current_vol_sma = volume_sma.iloc[latest_idx]
        if pd.isna(current_vol_sma) or current_vol_sma == 0:
            volume_score = 0.0
        else:
            relative_volume = current["volume"] / current_vol_sma
            # Map: 1.0 = average (50 score), 2.0+ = strong (100)
            volume_score = min(100.0, relative_volume * 50.0)

        # --- Component 5: Momentum acceleration (20%) ---
        prev_range = previous["high"] - previous["low"]
        if prev_range > 0:
            momentum_ratio = candle_range / prev_range
            # Map: 1.0 = same (50 score), 2.0+ = strong acceleration (100)
            momentum_score = min(100.0, momentum_ratio * 50.0)
        else:
            momentum_score = 50.0

        # Weighted composite (equal weights of 20% each)
        composite = (
            body_ratio_score * 0.20
            + close_high_score * 0.20
            + range_expansion_score * 0.20
            + volume_score * 0.20
            + momentum_score * 0.20
        )

        # Clamp to [0, 100]
        return max(0.0, min(100.0, composite))

    def _calculate_relative_volume(self, df: pd.DataFrame) -> Optional[float]:
        """Calculate relative volume: current_volume / SMA(volume, 30).

        Args:
            df: 15m OHLCV DataFrame with a 'volume' column.

        Returns:
            Relative volume as a float, or None if the 30-period volume SMA
            is zero, NaN, or unavailable (insufficient data). Returning None
            means the stock should be excluded from the current scan cycle.

        Validates: Requirements 6.1, 6.4
        """
        if len(df) < self.volume_ma_period:
            return None

        volume_sma = df["volume"].rolling(window=self.volume_ma_period).mean()
        latest_idx = len(df) - 1
        current_vol_sma = volume_sma.iloc[latest_idx]

        if pd.isna(current_vol_sma) or current_vol_sma == 0:
            return None

        current_volume = df["volume"].iloc[latest_idx]
        if pd.isna(current_volume):
            return None

        return float(current_volume / current_vol_sma)

    def _is_valid_dataframe(self, df: pd.DataFrame) -> bool:
        """Check if DataFrame has enough data for Stage 3 detection.

        Requires at least MIN_CANDLES rows and the required columns.

        Args:
            df: DataFrame to validate.

        Returns:
            True if valid for processing.
        """
        if df is None or df.empty:
            return False

        required_columns = {"open", "high", "low", "close", "volume"}
        if not required_columns.issubset(df.columns):
            return False

        return len(df) >= self.MIN_CANDLES

    def _calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> Optional[float]:
        """Calculate RSI(14) for the latest candle.

        Args:
            df: OHLCV DataFrame with 'close' column.
            period: RSI period (default 14).

        Returns:
            RSI value (0-100), or None if insufficient data.
        """
        if len(df) < period + 1:
            return None

        try:
            close = df["close"]
            delta = close.diff()
            gain = delta.where(delta > 0, 0.0).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0.0)).rolling(window=period).mean()

            latest_gain = gain.iloc[-1]
            latest_loss = loss.iloc[-1]

            if pd.isna(latest_gain) or pd.isna(latest_loss):
                return None

            if latest_loss == 0:
                return 100.0

            rs = latest_gain / latest_loss
            rsi = 100.0 - (100.0 / (1.0 + rs))
            return float(rsi)

        except Exception:
            return None

    def _calculate_atr_percentage(self, df: pd.DataFrame) -> Optional[float]:
        """Calculate ATR(14) as a percentage of the current price.

        Used to filter out "dead stocks" that barely move.
        ATR% = (ATR / current_price) × 100

        Args:
            df: OHLCV DataFrame with high, low, close columns.

        Returns:
            ATR as percentage of price, or None if insufficient data.
        """
        if len(df) < self.atr_period + 1:
            return None

        try:
            atr_indicator = AverageTrueRange(
                high=df["high"], low=df["low"], close=df["close"],
                window=self.atr_period,
            )
            atr_series = atr_indicator.average_true_range()
            atr_value = atr_series.iloc[-1]

            if pd.isna(atr_value) or atr_value <= 0:
                return None

            current_price = df["close"].iloc[-1]
            if current_price <= 0:
                return None

            return float((atr_value / current_price) * 100.0)

        except Exception:
            return None
