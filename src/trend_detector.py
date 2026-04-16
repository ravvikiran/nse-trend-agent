"""
Trend Detector Module

Detects potential uptrend starts based on EMA alignment and volume confirmation.
Implements PRD v2.0 scoring system:
- EMA Alignment: +3
- Fresh Crossover: +2
- Price Breakout (20-day high): +2
- Volume Spike (>=1.5x): +2
- RSI Ideal Zone (50-65): +1

Signal threshold: score >= 6
"""

import pandas as pd
import logging
from typing import Optional, Dict, Any, List, Tuple
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
        self.trend_score = 0
        self.score_breakdown = {}
        self.strategy_type = ""
        self.strategy_score = 0
        self.volume_ratio = 0.0
        self.breakout_strength = 0.0
        self.rank_score = 0.0
        self.alert = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'ticker': self.ticker,
            'timestamp': self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else str(self.timestamp),
            'signal_type': self.signal_type,
            'message': self.message,
            'indicators': self.indicators,
            'trend_score': self.trend_score,
            'score_breakdown': self.score_breakdown
        }
    
    def __repr__(self):
        return f"TrendSignal(ticker={self.ticker}, type={self.signal_type}, score={self.trend_score}, time={self.timestamp})"


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
    Detects potential uptrend starts based on PRD v2.0 scoring:
    1. EMA alignment (EMA20 > EMA50 > EMA100 > EMA200): +3
    2. Fresh crossover (EMA20 crosses above EMA50): +2
    3. Price breakout (above 20-day high): +2
    4. Volume spike (>=1.5x average): +2
    5. RSI ideal zone (50-65): +1
    
    Signal threshold: score >= 6
    """
    
    MIN_SCORE = 6

    def __init__(self):
        """Initialize the TrendDetector."""
        from indicator_engine import IndicatorEngine
        from datetime import date
        self.engine = IndicatorEngine()
        self.alerted_today = set()
        self.last_reset_date = date.today()
    
    def _check_daily_reset(self):
        """Automatically reset if new day."""
        from datetime import date
        today = date.today()
        if self.last_reset_date != today:
            self.alerted_today.clear()
            self.last_reset_date = today
            logger.info("Reset alerted_today for new trading day")
    
    def calculate_trend_score(self, indicators: Dict[str, Any]) -> Tuple[int, Dict[str, int]]:
        """
        Calculate trend score based on PRD v2.0 criteria.
        
        Args:
            indicators: Dictionary with indicator values
            
        Returns:
            Tuple of (total_score, score_breakdown_dict)
        """
        score = 0
        breakdown = {}
        
        # EMA Alignment
        ema_alignment = self.engine.check_ema_alignment(indicators)
        breakdown['ema_alignment'] = 3 if ema_alignment else 0
        score += breakdown['ema_alignment']

        # Fresh Crossover
        prev_ema_20 = indicators.get('prev_ema_20', 0)
        prev_ema_50 = indicators.get('prev_ema_50', 0)
        curr_ema_20 = indicators.get('ema_20', 0)
        curr_ema_50 = indicators.get('ema_50', 0)

        fresh_cross = prev_ema_20 <= prev_ema_50 and curr_ema_20 > curr_ema_50
        breakdown['fresh_crossover'] = 2 if fresh_cross else 0
        score += breakdown['fresh_crossover']

        # Breakout
        breakout = self.engine.check_price_breakout(indicators)
        breakdown['breakout'] = 2 if breakout else 0
        score += breakdown['breakout']

        # Volume
        vol_ok, vol_ratio = self.engine.check_volume_ratio(indicators, min_ratio=1.5)
        indicators['volume_ratio'] = vol_ratio
        breakdown['volume'] = 2 if vol_ok else 0
        score += breakdown['volume']

        # RSI
        rsi_zone, rsi_val = self.engine.check_rsi_zone(indicators)
        indicators['rsi_zone'] = rsi_zone
        indicators['rsi_value'] = rsi_val

        if rsi_zone == 'ideal':
            breakdown['rsi'] = 1
            score += 1
        elif rsi_zone == 'overbought':
            breakdown['rsi'] = -1
            score -= 1
        else:
            breakdown['rsi'] = 0

        return max(score, 0), breakdown
    
    def _rank_signal(self, indicators: Dict[str, Any], score: int) -> float:
        """
        Stronger ranking than just score.
        """
        vol = indicators.get('volume_ratio', 1)
        rsi = indicators.get('rsi_value', 50)

        rank = score
        rank += min(vol, 3)
        rank += 1 if 50 <= rsi <= 60 else 0

        return round(rank, 2)

    def _validate_signal(self, indicators: Dict[str, Any]) -> bool:
        """
        Hard filter (VERY important).
        """
        price = indicators.get('close', 0)
        ema50 = indicators.get('ema_50', 0)
        vol = indicators.get('volume_ratio', 0)

        if price <= ema50:
            return False

        if vol < 1.3:
            return False

        return True
    
    def check_trend_conditions(self, indicators: Dict[str, Any]) -> Dict[str, bool]:
        """
        Check all trend conditions for a stock.
        
        Args:
            indicators: Dictionary with indicator values
            
        Returns:
            Dictionary with condition results
        """
        try:
            from indicator_engine import IndicatorEngine
        except ImportError:
            from indicator_engine import IndicatorEngine
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
        try:
            from indicator_engine import IndicatorEngine
        except ImportError:
            from indicator_engine import IndicatorEngine
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
        if df is None or len(df) < 50:
            return None

        try:
            self._check_daily_reset()
            
            df = self.engine.calculate_indicators(df)
            indicators = self.engine.get_latest_indicators(df)

            if not indicators:
                return None

            if ticker in self.alerted_today:
                return None

            score, breakdown = self.calculate_trend_score(indicators)

            if score < self.MIN_SCORE:
                return None

            if not self._validate_signal(indicators):
                return None

            signal = TrendSignal(
                ticker=ticker,
                timestamp=indicators['timestamp'],
                indicators=indicators,
                signal_type="TREND",
                message=f"TREND {score}/10"
            )

            signal.trend_score = score
            signal.score_breakdown = breakdown
            signal.rank_score = self._rank_signal(indicators, score)

            self.alerted_today.add(ticker)

            return signal

        except Exception as e:
            logger.error(f"{ticker} failed: {e}")
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
            signal = self.analyze_stock(df, ticker)
            if signal:
                signals.append(signal)

        # sort by rank, not just score
        signals.sort(key=lambda x: x.rank_score, reverse=True)

        return signals[:10]
    
    def analyze_multiple_stocks_with_scans(self, stocks_data: Dict[str, pd.DataFrame]) -> ScanResult:
        """
        Analyze multiple stocks using PRD v2.0 scoring system.
        
        Returns stocks sorted by trend score.
        
        Args:
            stocks_data: Dictionary mapping ticker to DataFrame
            
        Returns:
            ScanResult containing signals and their scores
        """
        self._check_daily_reset()
        
        scan_a_signals = []
        scan_b_signals = []
        scored_signals = []
        
        for ticker, df in stocks_data.items():
            try:
                if df is None or df.empty:
                    continue
                
                from indicator_engine import IndicatorEngine
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
                
                # Calculate trend score
                trend_score, score_breakdown = self.calculate_trend_score(indicators)
                indicators['trend_score'] = trend_score
                indicators['score_breakdown'] = score_breakdown
                
                # Get volume ratio
                _, volume_ratio = engine.check_volume_ratio(indicators, min_ratio=1.0)
                indicators['volume_ratio'] = volume_ratio
                
                # Get RSI zone
                rsi_zone, rsi_value = engine.check_rsi_zone(indicators)
                indicators['rsi_zone'] = rsi_zone
                indicators['rsi_value'] = rsi_value
                
                logger.debug(f"{ticker} - Score: {trend_score}/10, Breakdown: {score_breakdown}")
                
                # Check if already alerted today
                already_alerted = ticker in self.alerted_today
                
                # Score-based classification
                if trend_score >= 6:
                    signal_type = "TREND"
                    
                    signal = TrendSignal(
                        ticker=ticker,
                        timestamp=indicators['timestamp'],
                        indicators=indicators,
                        signal_type=signal_type,
                        message=f"TREND Signal - Score: {trend_score}/10"
                    )
                    signal.trend_score = trend_score
                    signal.score_breakdown = score_breakdown
                    
                    scored_signals.append(signal)
                    
                    # Also add to scan_a (for backward compat)
                    scan_a_signals.append(signal)
                    
                    # Track in alerted set
                    if not already_alerted:
                        self.alerted_today.add(ticker)
                elif trend_score >= 4:
                    # Potential but not strong enough
                    scan_b_signals.append(TrendSignal(
                        ticker=ticker,
                        timestamp=indicators['timestamp'],
                        indicators=indicators,
                        signal_type="POTENTIAL",
                        message=f"Potential - Score: {trend_score}/10"
                    ))
            
            except Exception as e:
                logger.error(f"Error analyzing {ticker}: {str(e)}")
        
        # Sort by trend score
        scored_signals.sort(key=lambda x: x.trend_score, reverse=True)
        scan_a_signals.sort(key=lambda x: x.trend_score, reverse=True)
        
        passing_signals = [s for s in scored_signals if s.trend_score >= self.MIN_SCORE]
        
        return ScanResult(
            scan_a=scan_a_signals,
            scan_b=scan_b_signals,
            intersection=passing_signals[:5]  # Top 5 with score >= 6
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
