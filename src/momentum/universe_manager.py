"""Stock universe management for the NSE Momentum Scanner.

Loads the stock universe from a configuration file, applies liquidity and
quality filters, and provides the active tradeable universe for scanning.
Refreshes daily at 09:00 IST during the pre-market phase.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.momentum.models import ScannerConfig

logger = logging.getLogger(__name__)

DEFAULT_UNIVERSE_PATH = "config/nifty500_universe.json"
DEFAULT_PENNY_STOCK_THRESHOLD = 10.0


@dataclass
class StockData:
    """Market data for a single stock used in filtering decisions."""

    symbol: str
    avg_daily_traded_value: float = 0.0  # Average daily turnover in INR
    avg_daily_volume: float = 0.0  # Average daily volume (shares)
    last_price: float = 0.0  # Last traded price
    previous_close: float = 0.0  # Previous day close
    open_price: float = 0.0  # Today's open price
    is_suspended: bool = False  # Whether trading is suspended
    has_trading_data: bool = True  # Whether any trading data is available


@dataclass
class FilterResult:
    """Result of applying filters to the stock universe."""

    active_symbols: List[str] = field(default_factory=list)
    excluded_symbols: Dict[str, str] = field(default_factory=dict)  # symbol -> reason
    total_loaded: int = 0
    last_refresh: Optional[datetime] = None


class UniverseManager:
    """Manages the stock universe for the momentum scanner.

    Responsibilities:
    - Load stock universe from config file (NIFTY 500 constituents)
    - Apply liquidity filter: exclude stocks below min daily traded value and volume
    - Exclude penny stocks, suspended stocks, abnormal gap stocks
    - Refresh filter daily at 09:00 IST pre-market phase
    """

    def __init__(
        self,
        config: ScannerConfig,
        universe_path: Optional[str] = None,
    ):
        """Initialize UniverseManager.

        Args:
            config: Scanner configuration with filter thresholds.
            universe_path: Path to the universe JSON config file.
        """
        self._config = config
        self._universe_path = universe_path or DEFAULT_UNIVERSE_PATH
        self._full_universe: List[str] = []
        self._active_universe: List[str] = []
        self._filter_result: FilterResult = FilterResult()
        self._penny_stock_threshold: float = DEFAULT_PENNY_STOCK_THRESHOLD

    @property
    def full_universe(self) -> List[str]:
        """Return the full unfiltered stock universe."""
        return list(self._full_universe)

    @property
    def active_universe(self) -> List[str]:
        """Return the current filtered active universe."""
        return list(self._active_universe)

    @property
    def filter_result(self) -> FilterResult:
        """Return the latest filter result with exclusion details."""
        return self._filter_result

    def load_universe(self) -> List[str]:
        """Load the full stock list from the config file.

        Returns:
            List of stock symbols loaded from the universe config file.
            Returns empty list if file is missing or unreadable.
        """
        universe_file = Path(self._universe_path)

        if not universe_file.exists():
            logger.warning(
                "Universe config file '%s' not found. Using empty universe.",
                self._universe_path,
            )
            self._full_universe = []
            return []

        try:
            with open(universe_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(
                "Failed to read universe config '%s': %s. Using empty universe.",
                self._universe_path,
                e,
            )
            self._full_universe = []
            return []

        # Support both flat list format and structured format with "symbols" key
        if isinstance(data, list):
            symbols = data
        elif isinstance(data, dict):
            symbols = data.get("symbols", [])
            # Load penny stock threshold from config if present
            if "penny_stock_threshold" in data:
                self._penny_stock_threshold = float(data["penny_stock_threshold"])
        else:
            logger.warning(
                "Unexpected format in universe config '%s'. Using empty universe.",
                self._universe_path,
            )
            self._full_universe = []
            return []

        # Validate symbols are strings and non-empty
        valid_symbols = [s for s in symbols if isinstance(s, str) and s.strip()]
        if len(valid_symbols) < len(symbols):
            invalid_count = len(symbols) - len(valid_symbols)
            logger.warning(
                "Skipped %d invalid entries in universe config.", invalid_count
            )

        self._full_universe = valid_symbols
        logger.info(
            "Loaded %d stocks from universe config '%s'.",
            len(valid_symbols),
            self._universe_path,
        )
        return list(valid_symbols)

    def apply_filters(self, stocks_data: Dict[str, StockData]) -> List[str]:
        """Apply all filters to the stock universe and return active symbols.

        Filters applied:
        1. Liquidity filter: exclude if avg_daily_traded_value < min_liquidity_value
        2. Volume filter: exclude if avg_daily_volume < min_daily_volume
        3. Penny stock filter: exclude if last_price < penny_stock_threshold
        4. Suspended stock filter: exclude if no trading data available
        5. Gap filter: exclude if today's opening gap > max_gap_pct

        Args:
            stocks_data: Dictionary mapping symbol to StockData with market metrics.

        Returns:
            List of symbols that pass all filters.
        """
        active_symbols: List[str] = []
        excluded: Dict[str, str] = {}

        for symbol in self._full_universe:
            stock = stocks_data.get(symbol)

            # If no data available for this stock, treat as suspended
            if stock is None:
                excluded[symbol] = "no_data_available"
                continue

            # Suspended stock filter
            if stock.is_suspended or not stock.has_trading_data:
                excluded[symbol] = "suspended_or_no_trading_data"
                continue

            # Penny stock filter
            if stock.last_price < self._penny_stock_threshold:
                excluded[symbol] = f"penny_stock (price={stock.last_price:.2f} < {self._penny_stock_threshold})"
                continue

            # Liquidity filter: average daily traded value
            if stock.avg_daily_traded_value < self._config.min_liquidity_value:
                excluded[symbol] = (
                    f"low_liquidity (traded_value={stock.avg_daily_traded_value:.0f} "
                    f"< {self._config.min_liquidity_value:.0f})"
                )
                continue

            # Volume filter: average daily volume
            if stock.avg_daily_volume < self._config.min_daily_volume:
                excluded[symbol] = (
                    f"low_volume (volume={stock.avg_daily_volume:.0f} "
                    f"< {self._config.min_daily_volume})"
                )
                continue

            # Gap filter: abnormal opening gap
            if stock.previous_close > 0 and stock.open_price > 0:
                gap_pct = abs(stock.open_price - stock.previous_close) / stock.previous_close * 100
                if gap_pct > self._config.max_gap_pct:
                    excluded[symbol] = (
                        f"abnormal_gap (gap={gap_pct:.2f}% > {self._config.max_gap_pct}%)"
                    )
                    continue

            active_symbols.append(symbol)

        self._active_universe = active_symbols
        self._filter_result = FilterResult(
            active_symbols=list(active_symbols),
            excluded_symbols=excluded,
            total_loaded=len(self._full_universe),
            last_refresh=datetime.now(),
        )

        logger.info(
            "Universe filter applied: %d/%d stocks active, %d excluded.",
            len(active_symbols),
            len(self._full_universe),
            len(excluded),
        )

        if excluded:
            # Log exclusion breakdown at DEBUG level
            reason_counts: Dict[str, int] = {}
            for reason in excluded.values():
                # Extract the reason category (before the parenthetical details)
                category = reason.split(" (")[0]
                reason_counts[category] = reason_counts.get(category, 0) + 1
            logger.debug("Exclusion breakdown: %s", reason_counts)

        return active_symbols

    def get_active_universe(self) -> List[str]:
        """Return the current filtered list of tradeable symbols.

        Returns:
            List of symbols that passed all filters in the last refresh.
            Returns the full universe if no filters have been applied yet.
        """
        if self._active_universe:
            return list(self._active_universe)

        # If no filters applied yet, return full universe
        if self._full_universe:
            return list(self._full_universe)

        # If nothing loaded yet, attempt to load
        return self.load_universe()

    def refresh(self, stocks_data: Optional[Dict[str, StockData]] = None) -> List[str]:
        """Reload the universe from config and re-apply filters.

        Called daily at 09:00 IST during the pre-market preparation phase.

        Args:
            stocks_data: Optional market data for filtering. If None, only
                reloads the universe without applying market-based filters.

        Returns:
            List of active symbols after refresh.
        """
        logger.info("Refreshing stock universe...")

        # Reload from config file (picks up any changes to constituents)
        self.load_universe()

        if stocks_data:
            # Apply all filters with fresh market data
            return self.apply_filters(stocks_data)
        else:
            # No market data available yet — return full universe
            # Filters will be applied once market data is fetched
            self._active_universe = list(self._full_universe)
            self._filter_result = FilterResult(
                active_symbols=list(self._full_universe),
                excluded_symbols={},
                total_loaded=len(self._full_universe),
                last_refresh=datetime.now(),
            )
            return list(self._full_universe)
