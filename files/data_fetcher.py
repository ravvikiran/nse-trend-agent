"""
Data Fetcher Module

Fetches OHLCV data from Yahoo Finance for NSE stocks.

FIXES APPLIED:
  - fetch_stock_data() now retries up to 3 times with exponential backoff
    (1s, 2s, 4s) instead of silently returning None on the first failure.
    This prevents yfinance rate-limit bursts from silently dropping stocks.
"""

import time
import yfinance as yf
import pandas as pd
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class DataFetcher:
    """
    Fetches historical stock data from Yahoo Finance.

    Attributes:
        period: Number of days of historical data to fetch
        interval: Timeframe for the data (default: 1D)
    """

    TIMEFRAMES = ['1D', '1H', '15m']

    def __init__(self, period: int = 200, interval: str = "1D"):
        self.period = max(period, 200)
        self.interval = interval
        self._mtf_cache = {}

    def fetch_stock_data(self, ticker: str, interval: Optional[str] = None,
                         days: Optional[int] = None) -> Optional[pd.DataFrame]:
        """
        Fetch historical data for a single stock.
        Retries up to 3 times with exponential backoff on failure.

        Args:
            ticker: Stock ticker symbol (e.g., 'RELIANCE')
            interval: Data interval (optional, uses default if not specified)
            days: Number of days (optional, uses default if not specified)

        Returns:
            DataFrame with OHLCV data or None if all retries fail
        """
        actual_interval = interval if interval else self.interval
        actual_days = days if days else self.period
        nse_ticker = f"{ticker}.NS" if not ticker.endswith('.NS') else ticker

        min_candles = {
            '1D': 20, '1d': 20,
            '1H': 30, '1h': 30,
            '15m': 30, '15M': 30,
        }.get(actual_interval, 50)

        last_exception = None
        for attempt in range(3):
            try:
                stock = yf.Ticker(nse_ticker)
                df = stock.history(
                    period=f"{actual_days}d",
                    interval=actual_interval,
                    auto_adjust=False,
                )

                if df.empty:
                    # Empty result is not an error worth retrying
                    return None

                if len(df) < min_candles:
                    return None

                df.columns = df.columns.str.lower()
                df['ticker'] = ticker
                logger.debug(f"Fetched {len(df)} candles for {nse_ticker} ({actual_interval})")
                return df

            except Exception as e:
                last_exception = e
                if attempt < 2:
                    wait = 2 ** attempt  # 1s, 2s, 4s
                    logger.warning(
                        f"Fetch failed for {nse_ticker} (attempt {attempt + 1}/3): {e}. "
                        f"Retrying in {wait}s..."
                    )
                    time.sleep(wait)

        logger.error(f"All 3 fetch attempts failed for {nse_ticker}: {last_exception}")
        return None

    def fetch_multiple_stocks(self, tickers: list, max_workers: int = 3) -> Dict[str, pd.DataFrame]:
        """
        Fetch data for multiple stocks in parallel.

        Args:
            tickers: List of stock ticker symbols
            max_workers: Maximum number of parallel downloads

        Returns:
            Dictionary mapping ticker to DataFrame
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        results = {}
        logger.debug(f"Fetching data for {len(tickers)} stocks...")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_ticker = {
                executor.submit(self.fetch_stock_data, ticker): ticker
                for ticker in tickers
            }
            for future in as_completed(future_to_ticker):
                ticker = future_to_ticker[future]
                try:
                    df = future.result()
                    if df is not None:
                        results[ticker] = df
                except Exception as e:
                    logger.error(f"Error processing {ticker}: {e}")

        logger.debug(f"Successfully fetched {len(results)}/{len(tickers)} stocks")
        return results

    def is_market_open(self) -> bool:
        """
        Check if NSE market is currently open.

        Returns:
            True if market is open, False otherwise
        """
        import pytz
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)
        market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
        market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
        is_weekday = now.weekday() < 5
        is_market_hours = market_open <= now <= market_close
        return is_weekday and is_market_hours

    def get_live_data(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Get live/recent data for a ticker."""
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            return {
                'ticker': ticker,
                'current_price': info.get('currentPrice', info.get('regularMarketPrice')),
                'open': info.get('open'),
                'high': info.get('dayHigh'),
                'low': info.get('dayLow'),
                'volume': info.get('volume'),
                'market_cap': info.get('marketCap'),
                'timestamp': datetime.now(),
            }
        except Exception as e:
            logger.error(f"Error fetching live data for {ticker}: {e}")
            return None

    def fetch_multi_timeframe(self, ticker: str, days: int = 30) -> Dict[str, pd.DataFrame]:
        """Fetch 1D, 1H, and 15m data for a single stock."""
        results = {}
        timeframe_configs = {
            '1D': {'interval': '1D', 'days': days},
            '1H': {'interval': '1h', 'days': days},
            '15m': {'interval': '15m', 'days': 5},
        }
        for tf_name, config in timeframe_configs.items():
            df = self.fetch_stock_data(ticker, interval=config['interval'], days=config['days'])
            if df is not None and not df.empty:
                results[tf_name] = df
        return results

    def fetch_multiple_stocks_multi_timeframe(
        self, tickers: list, max_workers: int = 3
    ) -> Dict[str, Dict[str, pd.DataFrame]]:
        """Fetch multi-timeframe data for multiple stocks."""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        results = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_ticker = {
                executor.submit(self.fetch_multi_timeframe, ticker): ticker
                for ticker in tickers
            }
            for future in as_completed(future_to_ticker):
                ticker = future_to_ticker[future]
                try:
                    mtf_data = future.result()
                    if mtf_data:
                        results[ticker] = mtf_data
                except Exception as e:
                    logger.error(f"Error fetching MTF data for {ticker}: {e}")
        return results
