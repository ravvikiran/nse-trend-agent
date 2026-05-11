"""Sector Analyzer: Tracks sector index performance vs NIFTY.

Calculates relative strength of sector indices against NIFTY and provides
a configurable ranking boost for stocks belonging to outperforming sectors.
Sector performance uses the same RS formula as Stage 2:
    sector_RS = sector_index_pct_change - nifty_pct_change

A sector is "outperforming" if its RS vs NIFTY is positive.
"""

import logging
from typing import Dict, Optional

import pandas as pd

from src.momentum.models import ScannerConfig

logger = logging.getLogger(__name__)

# Sector indices tracked by the scanner
SECTOR_INDICES = [
    "NIFTY BANK",
    "NIFTY IT",
    "NIFTY PHARMA",
    "NIFTY AUTO",
    "NIFTY FMCG",
    "NIFTY METAL",
    "NIFTY ENERGY",
    "NIFTY REALTY",
]

# Default mapping of NSE stocks to their sector index.
# This covers major constituents across all tracked sectors.
STOCK_SECTOR_MAP: Dict[str, str] = {
    # Banking / NIFTY BANK
    "HDFCBANK": "NIFTY BANK",
    "ICICIBANK": "NIFTY BANK",
    "KOTAKBANK": "NIFTY BANK",
    "SBIN": "NIFTY BANK",
    "AXISBANK": "NIFTY BANK",
    "INDUSINDBK": "NIFTY BANK",
    "BANKBARODA": "NIFTY BANK",
    "PNB": "NIFTY BANK",
    "FEDERALBNK": "NIFTY BANK",
    "IDFCFIRSTB": "NIFTY BANK",
    "BANDHANBNK": "NIFTY BANK",
    "AUBANK": "NIFTY BANK",
    "CANBK": "NIFTY BANK",
    "UNIONBANK": "NIFTY BANK",
    "INDIANB": "NIFTY BANK",
    # IT / NIFTY IT
    "TCS": "NIFTY IT",
    "INFY": "NIFTY IT",
    "HCLTECH": "NIFTY IT",
    "WIPRO": "NIFTY IT",
    "TECHM": "NIFTY IT",
    "LTIM": "NIFTY IT",
    "PERSISTENT": "NIFTY IT",
    "COFORGE": "NIFTY IT",
    "MPHASIS": "NIFTY IT",
    "LTTS": "NIFTY IT",
    # Pharma / NIFTY PHARMA
    "SUNPHARMA": "NIFTY PHARMA",
    "DRREDDY": "NIFTY PHARMA",
    "CIPLA": "NIFTY PHARMA",
    "DIVISLAB": "NIFTY PHARMA",
    "APOLLOHOSP": "NIFTY PHARMA",
    "LUPIN": "NIFTY PHARMA",
    "AUROPHARMA": "NIFTY PHARMA",
    "BIOCON": "NIFTY PHARMA",
    "TORNTPHARM": "NIFTY PHARMA",
    "ALKEM": "NIFTY PHARMA",
    # Auto / NIFTY AUTO
    "TATAMOTORS": "NIFTY AUTO",
    "M&M": "NIFTY AUTO",
    "MARUTI": "NIFTY AUTO",
    "BAJAJ-AUTO": "NIFTY AUTO",
    "HEROMOTOCO": "NIFTY AUTO",
    "EICHERMOT": "NIFTY AUTO",
    "ASHOKLEY": "NIFTY AUTO",
    "TVSMOTOR": "NIFTY AUTO",
    "BALKRISIND": "NIFTY AUTO",
    "MOTHERSON": "NIFTY AUTO",
    # FMCG / NIFTY FMCG
    "HINDUNILVR": "NIFTY FMCG",
    "ITC": "NIFTY FMCG",
    "NESTLEIND": "NIFTY FMCG",
    "BRITANNIA": "NIFTY FMCG",
    "DABUR": "NIFTY FMCG",
    "GODREJCP": "NIFTY FMCG",
    "MARICO": "NIFTY FMCG",
    "COLPAL": "NIFTY FMCG",
    "TATACONSUM": "NIFTY FMCG",
    "VBL": "NIFTY FMCG",
    # Metal / NIFTY METAL
    "TATASTEEL": "NIFTY METAL",
    "JSWSTEEL": "NIFTY METAL",
    "HINDALCO": "NIFTY METAL",
    "VEDL": "NIFTY METAL",
    "COALINDIA": "NIFTY METAL",
    "NMDC": "NIFTY METAL",
    "SAIL": "NIFTY METAL",
    "NATIONALUM": "NIFTY METAL",
    "JINDALSTEL": "NIFTY METAL",
    "APLAPOLLO": "NIFTY METAL",
    # Energy / NIFTY ENERGY
    "RELIANCE": "NIFTY ENERGY",
    "ONGC": "NIFTY ENERGY",
    "NTPC": "NIFTY ENERGY",
    "POWERGRID": "NIFTY ENERGY",
    "ADANIGREEN": "NIFTY ENERGY",
    "BPCL": "NIFTY ENERGY",
    "IOC": "NIFTY ENERGY",
    "GAIL": "NIFTY ENERGY",
    "TATAPOWER": "NIFTY ENERGY",
    "ADANIENT": "NIFTY ENERGY",
    # Realty / NIFTY REALTY
    "DLF": "NIFTY REALTY",
    "GODREJPROP": "NIFTY REALTY",
    "OBEROIRLTY": "NIFTY REALTY",
    "PRESTIGE": "NIFTY REALTY",
    "PHOENIXLTD": "NIFTY REALTY",
    "BRIGADE": "NIFTY REALTY",
    "SOBHA": "NIFTY REALTY",
    "LODHA": "NIFTY REALTY",
    "SUNTECK": "NIFTY REALTY",
    "MAHLIFE": "NIFTY REALTY",
}


class SectorAnalyzer:
    """Tracks sector index performance vs NIFTY and provides sector boost.

    Sector performance is calculated as:
        sector_RS = sector_index_pct_change - nifty_pct_change

    A sector is considered "outperforming" when its RS vs NIFTY is positive.
    Stocks in outperforming sectors receive a configurable boost (sector_boost_pct)
    to their final ranking score.
    """

    def __init__(
        self,
        config: ScannerConfig,
        stock_sector_map: Optional[Dict[str, str]] = None,
    ):
        """Initialize SectorAnalyzer.

        Args:
            config: ScannerConfig containing sector_boost_pct.
            stock_sector_map: Optional custom stock-to-sector mapping.
                              Defaults to STOCK_SECTOR_MAP if not provided.
        """
        self.sector_boost_pct: float = config.sector_boost_pct
        self.stock_sector_map: Dict[str, str] = (
            stock_sector_map if stock_sector_map is not None else STOCK_SECTOR_MAP
        )

    def get_sector_scores(
        self,
        sector_data: Dict[str, pd.DataFrame],
        nifty_data: pd.DataFrame,
    ) -> Dict[str, float]:
        """Calculate each sector index's relative performance vs NIFTY.

        Sector RS = sector_index_pct_change - nifty_pct_change
        Uses the same formula as Stage 2 relative strength.

        Percentage change is calculated from the first to the last close price
        in the provided data (intraday performance).

        Args:
            sector_data: Dict mapping sector index name (e.g., "NIFTY IT") to
                         its OHLCV DataFrame with at least a 'close' column.
            nifty_data: OHLCV DataFrame for NIFTY 50 with a 'close' column.

        Returns:
            Dict mapping sector index name to its RS score vs NIFTY.
            Positive values indicate outperformance.
            Sectors with insufficient data are excluded from the result.
        """
        nifty_pct = self._calculate_pct_change(nifty_data)
        if nifty_pct is None:
            logger.warning(
                "Cannot calculate sector scores: insufficient NIFTY data"
            )
            return {}

        sector_scores: Dict[str, float] = {}

        for sector_name, sector_df in sector_data.items():
            sector_pct = self._calculate_pct_change(sector_df)
            if sector_pct is None:
                logger.debug(
                    "Insufficient data for sector '%s', skipping", sector_name
                )
                continue

            # RS = sector_pct_change - nifty_pct_change
            sector_scores[sector_name] = sector_pct - nifty_pct

        return sector_scores

    def get_stock_sector_boost(
        self, symbol: str, sector_scores: Dict[str, float]
    ) -> float:
        """Return the sector boost for a stock if its sector is outperforming NIFTY.

        A sector is "outperforming" if its RS vs NIFTY is positive (> 0).
        If the stock's sector is outperforming, returns sector_boost_pct.
        Otherwise returns 0.0.

        Args:
            symbol: NSE stock symbol (e.g., 'TCS').
            sector_scores: Dict of sector RS scores from get_sector_scores().

        Returns:
            sector_boost_pct if the stock's sector is outperforming, else 0.0.
        """
        sector = self.stock_sector_map.get(symbol)
        if sector is None:
            logger.debug(
                "Stock '%s' not found in sector mapping, no boost applied",
                symbol,
            )
            return 0.0

        sector_rs = sector_scores.get(sector)
        if sector_rs is None:
            logger.debug(
                "Sector '%s' for stock '%s' has no score data, no boost applied",
                sector,
                symbol,
            )
            return 0.0

        if sector_rs > 0:
            return self.sector_boost_pct

        return 0.0

    @staticmethod
    def _calculate_pct_change(data: pd.DataFrame) -> Optional[float]:
        """Calculate percentage change from first to last close price.

        This represents intraday performance when the DataFrame contains
        today's candles.

        Args:
            data: OHLCV DataFrame with a 'close' column.

        Returns:
            Percentage change as a float (e.g., 2.5 for 2.5% gain),
            or None if data is insufficient.
        """
        if data is None or data.empty:
            return None

        if len(data) < 2:
            return None

        close = data["close"]
        base_price = close.iloc[0]
        current_price = close.iloc[-1]

        if base_price == 0:
            return None

        return ((current_price - base_price) / base_price) * 100.0
