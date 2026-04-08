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
from typing import Optional, Dict, Any, Tuple
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)


class IndicatorEngine:
    """
    Calculates technical indicators for stock data analysis.
    
    Indicators:
        - EMA 20, 50, 100, 200
        - Volume Moving Average (MA 5, 20, 30)
        - RSI (14)
        - ATR (14)
        - 20-day High / Low
    """
    
    def __init__(self):
        """Initialize the IndicatorEngine."""
        self.ema_periods = [20, 50, 100, 200]
        self.volume_ma_periods = [5, 20, 30]
        self.high_low_period = 20
    
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
            
            # Volume Moving Average (5, 20, 30)
            for period in [5, 20, 30]:
                volume_sma = SMAIndicator(close=result_df['volume'], window=period)
                result_df[f'volume_ma_{period}'] = volume_sma.sma_indicator()
            
            # Also keep old name for backward compatibility
            result_df['volume_ma'] = result_df['volume_ma_30']
            
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
            
            # 20-day High / Low
            result_df['high_20'] = result_df['high'].rolling(window=20).max()
            result_df['low_20'] = result_df['low'].rolling(window=20).min()
            
            # Average volume 20 and 30
            result_df['avg_volume_20'] = result_df['volume'].rolling(window=20).mean()
            result_df['avg_volume_30'] = result_df['volume'].rolling(window=30).mean()
            
            # For scoring, we only need the latest row to be valid for key indicators
            # Don't drop all NaN - instead, fill with method that allows partial data
            # Keep rows that have at least the essential indicators (EMA20, EMA50, RSI, volume)
            essential_cols = ['ema_20', 'ema_50', 'rsi', 'volume_ma']
            result_df = result_df.dropna(subset=essential_cols)
            
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
                'volume_ma_5': latest.get('volume_ma_5'),
                'volume_ma_20': latest.get('volume_ma_20'),
                'volume_ma_30': latest.get('volume_ma_30'),
                'avg_volume_20': latest.get('avg_volume_20'),
                'avg_volume_30': latest.get('avg_volume_30'),
                'rsi': latest.get('rsi'),
                'atr': latest.get('atr'),
                'macd': latest.get('macd'),
                'macd_signal': latest.get('macd_signal'),
                'macd_hist': latest.get('macd_hist'),
                'high_20': latest.get('high_20'),
                'low_20': latest.get('low_20'),
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
    
    def check_price_breakout(self, indicators: Dict[str, Any]) -> bool:
        """
        Check if price has broken above 20-day high.
        
        Rule: close > highest_high(last 20 days)
        
        Args:
            indicators: Dictionary with indicator values
            
        Returns:
            True if price breakout detected, False otherwise
        """
        try:
            close = indicators.get('close', 0)
            high_20 = indicators.get('high_20')
            
            if high_20 is None:
                return False
            
            return close > high_20
            
        except Exception as e:
            logger.error(f"Error checking price breakout: {str(e)}")
            return False
    
    def check_volume_ratio(self, indicators: Dict[str, Any], min_ratio: float = 1.5) -> Tuple[bool, float]:
        """
        Check if volume ratio meets threshold.
        
        Rule: volume_ratio = current_volume / avg_volume_20 >= min_ratio
        
        Args:
            indicators: Dictionary with indicator values
            min_ratio: Minimum volume ratio (default 1.5)
            
        Returns:
            Tuple of (meets_threshold, volume_ratio)
        """
        try:
            volume = indicators.get('volume', 0)
            avg_volume_20 = indicators.get('avg_volume_20')
            
            if avg_volume_20 is None or avg_volume_20 == 0:
                return False, 0.0
            
            volume_ratio = volume / avg_volume_20
            return volume_ratio >= min_ratio, volume_ratio
            
        except Exception as e:
            logger.error(f"Error checking volume ratio: {str(e)}")
            return False, 0.0
    
    def check_rsi_zone(self, indicators: Dict[str, Any]) -> Tuple[str, float]:
        """
        Check RSI zone for the signal.
        
        Returns:
            Tuple of (zone, rsi_value)
            zone: 'ideal' (50-65), 'overbought' (>75), 'weak' (<45), or 'neutral'
        """
        try:
            rsi = indicators.get('rsi')
            
            if rsi is None:
                return 'unknown', 0.0
            
            if rsi > 75:
                return 'overbought', rsi
            elif rsi >= 50 and rsi <= 65:
                return 'ideal', rsi
            elif rsi < 45:
                return 'weak', rsi
            else:
                return 'neutral', rsi
                
        except Exception as e:
            logger.error(f"Error checking RSI zone: {str(e)}")
            return 'unknown', 0.0
