"""Stage 2: Relative Strength ranking vs NIFTY across multiple windows.

Ranks stocks by their price performance relative to NIFTY across three
time windows (intraday, 1-day, 5-day) using configurable weights.
Stocks with higher weighted composite RS score rank higher.
"""

import logging
from typing import Dict, List, Tuple

import pandas as pd

from src.momentum.models import ScannerConfig

logger = logging.getLogger(__name__)


class Stage2RelativeStrength:
    """Ranks stocks by relative strength vs NIFTY across multiple windows.

    Relative Strength for a single window is defined as:
        RS = stock_pct_change - nifty_pct_change

    The composite RS is a weighted sum of three windows:
        composite = (intraday_RS * w_intraday) + (1day_RS * w_1day) + (5day_RS * w_5day)

    Default weights: intraday=0.5, 1day=0.3, 5day=0.2
    """

    def __init__(self, config: ScannerConfig):
        """Initialize with RS weights from config.

        Args:
            config: ScannerConfig containing rs_intraday_weight, rs_1day_weight, rs_5day_weight.
        """
        self.weights: Dict[str, float] = {
            "intraday": config.rs_intraday_weight,
            "1day": config.rs_1day_weight,
            "5day": config.rs_5day_weight,
        }

    def calculate_rs(
        self, stock_data: pd.DataFrame, nifty_data: pd.DataFrame, window: str
    ) -> float:
        """Calculate RS for a single window: stock_pct_change - nifty_pct_change.

        The percentage change is computed from the first to the last close price
        within the window's data.

        Args:
            stock_data: OHLCV DataFrame for the stock with 'close' column.
            nifty_data: OHLCV DataFrame for NIFTY with 'close' column.
            window: One of 'intraday', '1day', '5day' — determines how many
                    periods to look back for the percentage change calculation.

        Returns:
            RS value (stock_pct_change - nifty_pct_change) as a float.
            Returns 0.0 if data is insufficient for the calculation.
        """
        periods = self._window_to_periods(window)

        stock_pct = self._calculate_pct_change(stock_data, periods)
        nifty_pct = self._calculate_pct_change(nifty_data, periods)

        if stock_pct is None or nifty_pct is None:
            logger.debug(
                "Insufficient data for RS calculation (window=%s)", window
            )
            return 0.0

        return stock_pct - nifty_pct

    def rank(
        self,
        symbols: List[str],
        stocks_data: Dict[str, pd.DataFrame],
        nifty_data: pd.DataFrame,
    ) -> List[Tuple[str, float]]:
        """Rank stocks by weighted composite RS score, sorted descending.

        Computes the composite RS for each symbol:
            composite = (intraday_RS * w_intraday) + (1day_RS * w_1day) + (5day_RS * w_5day)

        Stocks with missing data are assigned a composite RS of 0.0.

        Args:
            symbols: List of stock symbols to rank.
            stocks_data: Dict mapping symbol to its OHLCV DataFrame.
            nifty_data: OHLCV DataFrame for NIFTY 50.

        Returns:
            List of (symbol, composite_rs) tuples sorted by composite_rs descending.
        """
        results: List[Tuple[str, float]] = []

        for symbol in symbols:
            stock_df = stocks_data.get(symbol)
            if stock_df is None or stock_df.empty:
                logger.debug("No data for %s, assigning RS=0.0", symbol)
                results.append((symbol, 0.0))
                continue

            composite_rs = self._compute_composite_rs(stock_df, nifty_data)
            results.append((symbol, composite_rs))

        # Sort descending by composite RS (higher = better)
        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def _compute_composite_rs(
        self, stock_data: pd.DataFrame, nifty_data: pd.DataFrame
    ) -> float:
        """Compute weighted composite RS across all three windows.

        Args:
            stock_data: OHLCV DataFrame for the stock.
            nifty_data: OHLCV DataFrame for NIFTY.

        Returns:
            Weighted composite RS score.
        """
        composite = 0.0
        for window, weight in self.weights.items():
            rs = self.calculate_rs(stock_data, nifty_data, window)
            composite += rs * weight
        return composite

    def _calculate_pct_change(
        self, data: pd.DataFrame, periods: int
    ) -> float | None:
        """Calculate percentage change over the given number of periods.

        Uses the close price from `periods` ago as the base and the latest
        close as the current value.

        When periods=0 (intraday window), uses the first available close as
        the base price and the latest close as the current price.

        Args:
            data: OHLCV DataFrame with 'close' column.
            periods: Number of periods to look back. 0 means use all available data.

        Returns:
            Percentage change as a float (e.g., 2.5 for 2.5%), or None if
            insufficient data.
        """
        if data is None or data.empty:
            return None

        if len(data) < 2:
            return None

        close = data["close"]
        if len(close) == 0 or close.empty:
            return None

        current_price = close.iloc[-1]

        if periods == 0:
            # Intraday: use first available close as base
            base_price = close.iloc[0]
        elif len(data) < periods + 1:
            # Not enough data for the requested lookback — use all available
            base_price = close.iloc[0]
        else:
            base_price = close.iloc[-(periods + 1)]

        if base_price == 0:
            return None

        return ((current_price - base_price) / base_price) * 100.0

    @staticmethod
    def _window_to_periods(window: str) -> int:
        """Map window name to number of periods for percentage change calculation.

        For intraday: use the data from market open to now (all available intraday candles).
        For 1day: use 1 daily candle lookback (or equivalent in intraday candles).
        For 5day: use 5 daily candle lookback (or equivalent in intraday candles).

        Since the scanner operates on 15m candles during market hours:
        - intraday: all candles today (~25 candles for a full day of 15m data)
        - 1day: 1 day of data (use last available daily close vs current)
        - 5day: 5 days of data

        For simplicity and flexibility, we use period counts that work with
        whatever timeframe data is provided:
        - intraday: use all available data in the DataFrame (periods = len - 1)
        - 1day: 1 period lookback
        - 5day: 5 periods lookback

        Args:
            window: One of 'intraday', '1day', '5day'.

        Returns:
            Number of periods to look back for pct change calculation.
        """
        mapping = {
            "intraday": 0,  # Special: use all available data
            "1day": 1,
            "5day": 5,
        }
        return mapping.get(window, 1)
