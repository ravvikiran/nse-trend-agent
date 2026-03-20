"""
Trend Detector Module

Detects potential uptrend starts based on EMA alignment and volume confirmation.
"""

import pandas as pd
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)


class TrendSignal:
    """Data class for trend detection signals."""
    
    def __init__(self, ticker: str, timestamp: datetime, indicators: Dict[str, Any], 
                 signal_type: str = "TREND_START", message: str = ""):
        self.ticker = ticker
        self.timestamp = timestamp
        self.indicators = indicators
        self.signal_type = signal_type
        self.message = message
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'ticker': self.ticker,
            'timestamp': self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else str(self.timestamp),
            'signal_type': self.signal_type,
            'message': self.message,
            'indicators': self.indicators
        }
    
    def __repr__(self):
        return f"TrendSignal(ticker={self.ticker}, type={self.signal_type}, time={self.timestamp})"


class ScanResult:
    """Data class for scan results containing both scans and their intersection."""
    
    def __init__(self, scan_a: List[TrendSignal], scan_b: List[TrendSignal], intersection: List[TrendSignal]):
        self.scan_a = scan_a  # Trend Structure: Close > EMA20 > EMA50 > EMA100 > EMA200
        self.scan_b = scan_b  # Volume Expansion: Volume > SMA(Volume,30) AND Close > EMA20
        self.intersection = intersection  # Stocks passing both scans
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'scan_a_count': len(self.scan_a),
            'scan_b_count': len(self.scan_b),
            'intersection_count': len(self.intersection),
            'scan_a_tickers': [s.ticker for s in self.scan_a],
            'scan_b_tickers': [s.ticker for s in self.scan_b],
            'intersection_tickers': [s.ticker for s in self.intersection]
        }
    
    def __repr__(self):
        return f"ScanResult(ScanA={len(self.scan_a)}, ScanB={len(self.scan_b)}, Intersection={len(self.intersection)})"


class TrendDetector:
    """
    Detects potential uptrend starts based on:
    1. EMA alignment (EMA20 > EMA50 > EMA100 > EMA200)
    2. Volume confirmation (Volume > Volume MA 30)
    3. Trend start detection (crossover of EMA20 over EMA50)
    """
    
    def __init__(self):
        """Initialize the TrendDetector."""
        self.alerted_today = set()
        self.last_reset_date = None
    
    def check_trend_conditions(self, indicators: Dict[str, Any]) -> Dict[str, bool]:
        """
        Check all trend conditions for a stock.
        
        Args:
            indicators: Dictionary with indicator values
            
        Returns:
            Dictionary with condition results
        """
        from src.indicator_engine import IndicatorEngine
        
        engine = IndicatorEngine()
        
        return {
            'ema_alignment': engine.check_ema_alignment(indicators),
            'volume_confirmation': engine.check_volume_confirmation(indicators),
            'trend_start': engine.check_trend_start(indicators)
        }
    
    def check_scan_conditions(self, indicators: Dict[str, Any]) -> Dict[str, bool]:
        """
        Check Scan A and Scan B conditions for a stock.
        
        Args:
            indicators: Dictionary with indicator values
            
        Returns:
            Dictionary with scan condition results
        """
        from src.indicator_engine import IndicatorEngine
        
        engine = IndicatorEngine()
        
        return {
            'scan_a_trend_structure': engine.check_trend_structure(indicators),
            'scan_b_volume_expansion': engine.check_volume_expansion(indicators)
        }
    
    def analyze_stock(self, df: pd.DataFrame, ticker: str) -> Optional[TrendSignal]:
        """
        Analyze a stock for potential trend signals.
        
        Args:
            df: DataFrame with OHLCV and calculated indicators
            ticker: Stock ticker symbol
            
        Returns:
            TrendSignal if conditions are met, None otherwise
        """
        if df is None or df.empty:
            return None
        
        try:
            from src.indicator_engine import IndicatorEngine
            
            engine = IndicatorEngine()
            
            # Calculate indicators
            df_with_indicators = engine.calculate_indicators(df)
            
            if df_with_indicators.empty or len(df_with_indicators) < 2:
                logger.debug(f"Insufficient data for {ticker}")
                return None
            
            # Get latest indicators
            indicators = engine.get_latest_indicators(df_with_indicators)
            
            if indicators is None:
                return None
            
            # Check if already alerted today
            if ticker in self.alerted_today:
                logger.debug(f"{ticker} already alerted today, skipping")
                return None
            
            # Check trend conditions
            conditions = self.check_trend_conditions(indicators)
            
            # Log the conditions for debugging
            logger.debug(f"{ticker} - EMA Alignment: {conditions['ema_alignment']}, "
                        f"Volume Conf: {conditions['volume_confirmation']}, "
                        f"Trend Start: {conditions['trend_start']}")
            
            # Determine signal type
            signal_type = None
            message = ""
            
            # Check for trend start (primary signal)
            if conditions['trend_start'] and conditions['ema_alignment'] and conditions['volume_confirmation']:
                signal_type = "TREND_START"
                message = "🎯 New Uptrend Starting"
            
            # Check for EMA alignment with volume (potential trend)
            elif conditions['ema_alignment'] and conditions['volume_confirmation']:
                signal_type = "EMA_ALIGNMENT"
                message = "📈 EMA Alignment Confirmed"
            
            # Check for volume spike (early warning)
            elif conditions['volume_confirmation']:
                signal_type = "VOLUME_SPIKE"
                message = "⚡ Volume Spike"
            
            if signal_type:
                # Add to alerted set
                self.alerted_today.add(ticker)
                
                return TrendSignal(
                    ticker=ticker,
                    timestamp=indicators['timestamp'],
                    indicators=indicators,
                    signal_type=signal_type,
                    message=message
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Error analyzing {ticker}: {str(e)}")
            return None
    
    def analyze_multiple_stocks(self, stocks_data: Dict[str, pd.DataFrame]) -> List[TrendSignal]:
        """
        Analyze multiple stocks for trend signals.
        
        Args:
            stocks_data: Dictionary mapping ticker to DataFrame
            
        Returns:
            List of TrendSignal objects
        """
        signals = []
        

        
        for ticker, df in stocks_data.items():
            try:
                signal = self.analyze_stock(df, ticker)
                if signal:
                    signals.append(signal)

            except Exception as e:
                logger.error(f"Error analyzing {ticker}: {str(e)}")
        

        return signals
    
    def analyze_multiple_stocks_with_scans(self, stocks_data: Dict[str, pd.DataFrame]) -> ScanResult:
        """
        Analyze multiple stocks using both Scan A and Scan B.
        
        Scan A - Trend Structure:
        Close > EMA20 > EMA50 > EMA100 > EMA200
        
        Scan B - Volume Expansion:
        Volume > SMA(Volume, 30) AND Close > EMA20
        
        Returns stocks that pass BOTH scans (intersection).
        
        Args:
            stocks_data: Dictionary mapping ticker to DataFrame
            
        Returns:
            ScanResult containing Scan A, Scan B, and Intersection lists
        """
        scan_a_signals = []
        scan_b_signals = []
        

        
        for ticker, df in stocks_data.items():
            try:
                if df is None or df.empty:
                    continue
                
                from src.indicator_engine import IndicatorEngine
                engine = IndicatorEngine()
                
                # Calculate indicators
                df_with_indicators = engine.calculate_indicators(df)
                
                if df_with_indicators.empty or len(df_with_indicators) < 2:
                    logger.debug(f"Insufficient data for {ticker}")
                    continue
                
                # Get latest indicators
                indicators = engine.get_latest_indicators(df_with_indicators)
                
                if indicators is None:
                    continue
                
                # Check scan conditions
                scan_conditions = self.check_scan_conditions(indicators)
                
                logger.debug(f"{ticker} - ScanA: {scan_conditions['scan_a_trend_structure']}, "
                           f"ScanB: {scan_conditions['scan_b_volume_expansion']}")
                
                # Check if already alerted today
                already_alerted = ticker in self.alerted_today
                
                # Scan A - Trend Structure
                if scan_conditions['scan_a_trend_structure']:
                    signal_type = "SCAN_A_TREND_STRUCTURE"
                    message = "📈 Trend Structure: Close > EMA20 > EMA50 > EMA100 > EMA200"
                    
                    scan_a_signals.append(TrendSignal(
                        ticker=ticker,
                        timestamp=indicators['timestamp'],
                        indicators=indicators,
                        signal_type=signal_type,
                        message=message
                    ))

                
                # Scan B - Volume Expansion
                if scan_conditions['scan_b_volume_expansion']:
                    signal_type = "SCAN_B_VOLUME_EXPANSION"
                    message = "📊 Volume Expansion: Volume > SMA30 & Close > EMA20"
                    
                    scan_b_signals.append(TrendSignal(
                        ticker=ticker,
                        timestamp=indicators['timestamp'],
                        indicators=indicators,
                        signal_type=signal_type,
                        message=message
                    ))

                
                # Intersection - both scans passed
                if scan_conditions['scan_a_trend_structure'] and scan_conditions['scan_b_volume_expansion']:
                    if not already_alerted:
                        self.alerted_today.add(ticker)
                    

                    
            except Exception as e:
                logger.error(f"Error analyzing {ticker}: {str(e)}")
        
        # Calculate intersection (stocks that pass both scans)
        scan_a_tickers = {s.ticker for s in scan_a_signals}
        scan_b_tickers = {s.ticker for s in scan_b_signals}
        intersection_tickers = scan_a_tickers & scan_b_tickers
        
        # Get the intersection signals
        all_signals = scan_a_signals + scan_b_signals
        intersection_signals = [s for s in all_signals if s.ticker in intersection_tickers]
        
        # Remove duplicates from intersection (keep one per ticker)
        seen = set()
        unique_intersection = []
        for s in intersection_signals:
            if s.ticker not in seen:
                seen.add(s.ticker)
                s.signal_type = "INTERSECTION"
                s.message = "🎯 INTERSECTION: Passes BOTH Trend Structure & Volume Expansion"
                unique_intersection.append(s)
        

        
        return ScanResult(
            scan_a=scan_a_signals,
            scan_b=scan_b_signals,
            intersection=unique_intersection
        )
    
    def should_alert(self, ticker: str) -> bool:
        """
        Check if we should send an alert for this ticker.
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            True if alert should be sent, False if already alerted today
        """
        return ticker not in self.alerted_today
    
    def reset_daily(self):
        """
        Reset the alerted set for a new trading day.
        """
        from datetime import date
        
        today = date.today()
        
        if self.last_reset_date != today:
            self.alerted_today.clear()
            self.last_reset_date = today

    
    def get_alert_count(self) -> int:
        """
        Get the count of stocks alerted today.
        
        Returns:
            Number of stocks alerted today
        """
        return len(self.alerted_today)
    
    def get_alerted_stocks(self) -> List[str]:
        """
        Get list of stocks alerted today.
        
        Returns:
            List of ticker symbols
        """
        return list(self.alerted_today)
