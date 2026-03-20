"""
Indicator Engine Module

Calculates technical indicators (EMA, Volume MA) for trend analysis.
"""

import pandas as pd
import ta
from ta.trend import EMAIndicator, SMAIndicator, MACD
from ta.volatility import AverageTrueRange
from ta.momentum import RSIIndicator
import logging
from typing import Optional, Dict, Any
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)


class IndicatorEngine:
    """
    Calculates technical indicators for stock data analysis.
    
    Indicators:
        - EMA 20, 50, 100, 200
        - Volume Moving Average (MA 30)
    """
    
    def __init__(self):
        """Initialize the IndicatorEngine."""
        self.ema_periods = [20, 50, 100, 200]
        self.volume_ma_period = 30
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate all required indicators for the DataFrame.
        
        Args:
            df: DataFrame with OHLCV data
            
        Returns:
            DataFrame with added indicator columns
        """
        if df is None or df.empty:
            logger.debug("Empty DataFrame passed to calculate_indicators")
            return df
        
        try:
            # Create a copy to avoid modifying original
            result_df = df.copy()
            
            # Calculate EMAs using ta
            # EMA 20
            ema_20 = EMAIndicator(close=result_df['close'], window=20)
            result_df['ema_20'] = ema_20.ema_indicator()
            
            # EMA 50
            ema_50 = EMAIndicator(close=result_df['close'], window=50)
            result_df['ema_50'] = ema_50.ema_indicator()
            
            # EMA 100
            ema_100 = EMAIndicator(close=result_df['close'], window=100)
            result_df['ema_100'] = ema_100.ema_indicator()
            
            # EMA 200
            ema_200 = EMAIndicator(close=result_df['close'], window=200)
            result_df['ema_200'] = ema_200.ema_indicator()
            
            # Volume Moving Average
            volume_sma = SMAIndicator(close=result_df['volume'], window=30)
            result_df['volume_ma'] = volume_sma.sma_indicator()
            
            # Additional useful indicators
            # RSI
            rsi = RSIIndicator(close=result_df['close'], window=14)
            result_df['rsi'] = rsi.rsi()
            
            # ATR (Average True Range) for volatility
            atr = AverageTrueRange(high=result_df['high'], low=result_df['low'], close=result_df['close'], window=14)
            result_df['atr'] = atr.average_true_range()
            
            # MACD for momentum confirmation
            macd = MACD(close=result_df['close'])
            result_df['MACD'] = macd.macd()
            result_df['MACD_Signal'] = macd.macd_signal()
            result_df['MACD_Hist'] = macd.macd_diff()
            
            # Drop NaN values that may result from indicator calculations
            result_df.dropna(inplace=True)
            
            logger.debug(f"Calculated indicators for {len(result_df)} candles")
            return result_df
            
        except Exception as e:
            logger.error(f"Error calculating indicators: {str(e)}")
            return df
    
    def get_latest_indicators(self, df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """
        Get the latest indicator values from the DataFrame.
        
        Args:
            df: DataFrame with calculated indicators
            
        Returns:
            Dictionary with latest indicator values
        """
        if df is None or df.empty or len(df) < 2:
            return None
        
        try:
            # Get the latest candle
            latest = df.iloc[-1]
            previous = df.iloc[-2]
            
            return {
                'ticker': latest.get('ticker', 'Unknown'),
                'timestamp': latest.name,
                # Current candle values
                'close': latest['close'],
                'volume': latest['volume'],
                'ema_20': latest['ema_20'],
                'ema_50': latest['ema_50'],
                'ema_100': latest['ema_100'],
                'ema_200': latest['ema_200'],
                'volume_ma': latest['volume_ma'],
                'rsi': latest.get('rsi'),
                'atr': latest.get('atr'),
                'macd': latest.get('macd'),
                'macd_signal': latest.get('macd_signal'),
                'macd_hist': latest.get('macd_hist'),
                # Previous candle values for trend detection
                'prev_ema_20': previous['ema_20'],
                'prev_ema_50': previous['ema_50'],
                'prev_ema_100': previous['ema_100'],
                'prev_ema_200': previous['ema_200'],
                # Price info
                'open': latest['open'],
                'high': latest['high'],
                'low': latest['low'],
            }
            
        except Exception as e:
            logger.error(f"Error getting latest indicators: {str(e)}")
            return None
    
    def check_ema_alignment(self, indicators: Dict[str, Any]) -> bool:
        """
        Check if EMAs are in bullish alignment.
        
        EMA Alignment Rule:
        EMA20 > EMA50 > EMA100 > EMA200
        
        Args:
            indicators: Dictionary with indicator values
            
        Returns:
            True if EMAs are in alignment, False otherwise
        """
        try:
            ema_20 = indicators['ema_20']
            ema_50 = indicators['ema_50']
            ema_100 = indicators['ema_100']
            ema_200 = indicators['ema_200']
            
            # Check bullish alignment
            return (ema_20 > ema_50 > ema_100 > ema_200)
            
        except Exception as e:
            logger.error(f"Error checking EMA alignment: {str(e)}")
            return False
    
    def check_volume_confirmation(self, indicators: Dict[str, Any]) -> bool:
        """
        Check if volume confirms the trend.
        
        Volume Confirmation Rule:
        Current Volume > Volume MA 30
        
        Args:
            indicators: Dictionary with indicator values
            
        Returns:
            True if volume confirms, False otherwise
        """
        try:
            volume = indicators['volume']
            volume_ma = indicators['volume_ma']
            
            if volume_ma is None or volume_ma == 0:
                return False
            
            return volume > volume_ma
            
        except Exception as e:
            logger.error(f"Error checking volume confirmation: {str(e)}")
            return False
    
    def check_trend_start(self, indicators: Dict[str, Any]) -> bool:
        """
        Check if a new uptrend is starting.
        
        Trend Start Detection Rule:
        - Previous candle: EMA20 <= EMA50
        - Current candle: EMA20 > EMA50
        
        Args:
            indicators: Dictionary with indicator values
            
        Returns:
            True if trend is starting, False otherwise
        """
        try:
            current_ema_20 = indicators['ema_20']
            current_ema_50 = indicators['ema_50']
            prev_ema_20 = indicators['prev_ema_20']
            prev_ema_50 = indicators['prev_ema_50']
            
            # Previous candle: EMA20 <= EMA50
            # Current candle: EMA20 > EMA50
            return (prev_ema_20 <= prev_ema_50) and (current_ema_20 > current_ema_50)
            
        except Exception as e:
            logger.error(f"Error checking trend start: {str(e)}")
            return False
    
    def get_alignment_string(self, indicators: Dict[str, Any]) -> str:
        """
        Get a string representation of EMA alignment.
        
        Args:
            indicators: Dictionary with indicator values
            
        Returns:
            String showing EMA relationship (e.g., "20 > 50 > 100 > 200")
        """
        try:
            ema_20 = indicators['ema_20']
            ema_50 = indicators['ema_50']
            ema_100 = indicators['ema_100']
            ema_200 = indicators['ema_200']
            
            # Determine relationship
            parts = []
            if ema_20 > ema_50:
                parts.append("20 > 50")
            else:
                parts.append("20 < 50")
            
            if ema_50 > ema_100:
                parts.append("50 > 100")
            else:
                parts.append("50 < 100")
            
            if ema_100 > ema_200:
                parts.append("100 > 200")
            else:
                parts.append("100 < 200")
            
            return " > ".join([p.split(' > ')[0] for p in parts]) + " > " + str(int(ema_200))
            
        except Exception as e:
            logger.error(f"Error getting alignment string: {str(e)}")
            return "Unknown"
    
    def check_trend_structure(self, indicators: Dict[str, Any]) -> bool:
        """
        Check if stock meets Scan A - Trend Structure criteria.
        
        Scan A - Trend Structure Rule:
        Close > EMA20 > EMA50 > EMA100 > EMA200
        
        Args:
            indicators: Dictionary with indicator values
            
        Returns:
            True if trend structure is valid, False otherwise
        """
        try:
            close = indicators['close']
            ema_20 = indicators['ema_20']
            ema_50 = indicators['ema_50']
            ema_100 = indicators['ema_100']
            ema_200 = indicators['ema_200']
            
            # Check: Close > EMA20 > EMA50 > EMA100 > EMA200
            return (close > ema_20 > ema_50 > ema_100 > ema_200)
            
        except Exception as e:
            logger.error(f"Error checking trend structure: {str(e)}")
            return False
    
    def check_volume_expansion(self, indicators: Dict[str, Any]) -> bool:
        """
        Check if stock meets Scan B - Volume Expansion criteria.
        
        Scan B - Volume Expansion Rule:
        Volume > SMA(Volume, 30) AND Close > EMA20
        
        Args:
            indicators: Dictionary with indicator values
            
        Returns:
            True if volume expansion criteria met, False otherwise
        """
        try:
            volume = indicators['volume']
            volume_ma = indicators['volume_ma']
            close = indicators['close']
            ema_20 = indicators['ema_20']
            
            # Check: Volume > Volume_MA AND Close > EMA20
            if volume_ma is None or volume_ma == 0:
                return False
            
            return (volume > volume_ma) and (close > ema_20)
            
        except Exception as e:
            logger.error(f"Error checking volume expansion: {str(e)}")
            return False
