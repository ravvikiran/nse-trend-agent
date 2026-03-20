"""
Data Fetcher Module

Fetches OHLCV data from Yahoo Finance for NSE stocks.
"""

import yfinance as yf
import pandas as pd
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

# Configure logging
logger = logging.getLogger(__name__)


class DataFetcher:
    """
    Fetches historical stock data from Yahoo Finance.
    
    Attributes:
        period: Number of days of historical data to fetch
        interval: Timeframe for the data (default: 15 minutes)
    """
    
    def __init__(self, period: int = 16, interval: str = "1D"):
        """
        Initialize the DataFetcher.
        
        Args:
            period: Number of days of historical data (default: 16 days for ~250 candles)
            interval: Data interval (default: 15 minutes)
        """
        self.period = period
        self.interval = interval
    
    def fetch_stock_data(self, ticker: str) -> Optional[pd.DataFrame]:
        """
        Fetch historical data for a single stock.
        
        Args:
            ticker: Stock ticker symbol (e.g., 'RELIANCE')
            
        Returns:
            DataFrame with OHLCV data or None if fetch fails
        """
        # Add .NS suffix for NSE stocks
        nse_ticker = f"{ticker}.NS" if not ticker.endswith('.NS') else ticker
        
        try:
            stock = yf.Ticker(nse_ticker)
            df = stock.history(
                period=f"{self.period}d",
                interval=self.interval,
                auto_adjust=False
            )
            
            if df.empty:
                return None
            
            # Ensure we have enough data points
            if len(df) < 50:
                return None
            
            # Normalize column names to lowercase
            df.columns = df.columns.str.lower()
            
            # Add ticker column for reference
            df['ticker'] = ticker
            
            logger.debug(f"Fetched {len(df)} candles for {nse_ticker}")
            return df
            
        except Exception as e:
            # Silently handle errors to avoid logging noise
            return None
    
    def fetch_multiple_stocks(self, tickers: list, max_workers: int = 3) -> Dict[str, pd.DataFrame]:
        """
        Fetch data for multiple stocks.
        
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
                    logger.error(f"Error processing {ticker}: {str(e)}")
        
        logger.debug(f"Successfully fetched data for {len(results)}/{len(tickers)} stocks")
        return results
    
    def is_market_open(self) -> bool:
        """
        Check if NSE market is currently open.
        
        Returns:
            True if market is open, False otherwise
        """
        import pytz
        
        # Get current time in IST
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)
        
        # Market hours: 09:15 - 15:30 IST
        market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
        market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
        
        # Check if weekday (Monday=0, Sunday=6)
        is_weekday = now.weekday() < 5
        is_market_hours = market_open <= now <= market_close
        
        return is_weekday and is_market_hours
    
    def get_live_data(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Get live/recent data for a ticker.
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            Dictionary with latest price data or None
        """
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
                'timestamp': datetime.now()
            }
        except Exception as e:
            logger.error(f"Error fetching live data for {ticker}: {str(e)}")
            return None
