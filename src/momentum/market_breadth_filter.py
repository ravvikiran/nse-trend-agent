"""Market breadth filter for the NSE Momentum Scanner.

Suppresses long signals when market breadth is weak. Market is considered
unhealthy (signals suppressed) when BOTH conditions are true:
1. Declining stocks / Advancing stocks > breadth_decline_ratio (default 1.5)
2. NIFTY current price < NIFTY intraday EMA(20)
"""

import logging

import pandas as pd

from src.momentum.models import ScannerConfig

logger = logging.getLogger(__name__)


class MarketBreadthFilter:
    """Suppresses long signals when market breadth is weak.

    Market health is determined by two conditions that must BOTH be true
    for the market to be considered unhealthy:
    1. Declining stocks exceed advancing stocks by the configured ratio
    2. NIFTY is trading below its intraday EMA(20)

    When both conditions are met, all new long signals are suppressed for
    that scan cycle.
    """

    def __init__(self, config: ScannerConfig):
        """Initialize with scanner configuration.

        Args:
            config: ScannerConfig containing breadth_decline_ratio threshold.
        """
        self.decline_ratio_threshold: float = config.breadth_decline_ratio

    def is_market_healthy(
        self,
        advancing_count: int,
        declining_count: int,
        nifty_15m_data: pd.DataFrame,
    ) -> bool:
        """Determine if market conditions are healthy enough for long signals.

        Market is UNHEALTHY (returns False) when BOTH conditions are true:
        1. declining_count / advancing_count > decline_ratio_threshold
        2. NIFTY current price < NIFTY intraday EMA(20)

        If either condition is not met, market is considered healthy.

        Args:
            advancing_count: Number of stocks advancing in the NIFTY 500 universe.
            declining_count: Number of stocks declining in the NIFTY 500 universe.
            nifty_15m_data: DataFrame with NIFTY 15-minute OHLCV data containing
                at least a 'close' column. Must have enough rows for EMA(20)
                calculation.

        Returns:
            True if market is healthy (signals allowed),
            False if market is unhealthy (signals suppressed).
        """
        # Check condition 1: Declining ratio exceeds threshold
        breadth_weak = self._is_breadth_weak(advancing_count, declining_count)

        # Check condition 2: NIFTY below intraday EMA(20)
        nifty_below_ema = self._is_nifty_below_ema(nifty_15m_data)

        # Market is unhealthy only when BOTH conditions are true
        if breadth_weak and nifty_below_ema:
            logger.warning(
                "Market breadth WEAK — signals suppressed. "
                "Decline ratio: %.2f (threshold: %.2f), "
                "NIFTY below intraday EMA(20). "
                "Advancing: %d, Declining: %d",
                declining_count / max(advancing_count, 1),
                self.decline_ratio_threshold,
                advancing_count,
                declining_count,
            )
            return False

        return True

    def _is_breadth_weak(self, advancing_count: int, declining_count: int) -> bool:
        """Check if declining stocks exceed advancing stocks by the configured ratio.

        Args:
            advancing_count: Number of advancing stocks.
            declining_count: Number of declining stocks.

        Returns:
            True if decline ratio exceeds threshold.
        """
        if advancing_count <= 0:
            # If no advancing stocks, breadth is definitely weak
            return declining_count > 0

        decline_ratio = declining_count / advancing_count
        return decline_ratio > self.decline_ratio_threshold

    def _is_nifty_below_ema(self, nifty_15m_data: pd.DataFrame) -> bool:
        """Check if NIFTY current price is below its intraday EMA(20).

        Args:
            nifty_15m_data: DataFrame with at least a 'close' column.

        Returns:
            True if NIFTY current price < EMA(20), False otherwise.
            Returns False (healthy) if insufficient data for EMA calculation.
        """
        if nifty_15m_data is None or nifty_15m_data.empty:
            # Cannot determine — assume healthy
            return False

        if "close" not in nifty_15m_data.columns:
            logger.warning("NIFTY 15m data missing 'close' column. Assuming healthy.")
            return False

        if len(nifty_15m_data) < 2:
            # Not enough data for meaningful EMA — assume healthy
            return False

        # Calculate EMA(20) on the close prices
        ema_20 = nifty_15m_data["close"].ewm(span=20, adjust=False).mean()

        current_price = nifty_15m_data["close"].iloc[-1]
        current_ema = ema_20.iloc[-1]

        return current_price < current_ema
