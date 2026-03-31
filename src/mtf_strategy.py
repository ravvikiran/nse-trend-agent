"""
Multi-Timeframe Strategy Engine

Implements the Trend + Pullback + Confirmation system:
- Step 1: Trend Identification (1D) - Price vs EMA200
- Step 2: Market Structure Confirmation (1H) - Higher Highs/Lower Lows
- Step 3: Pullback Detection (1H) - Price retraces to EMA50/100
- Step 4: Entry Trigger (15m) - Strong breakout candle
- Step 5: Volume Confirmation - Volume > MA30
- Step 6: EMA Alignment Filter - Valid trend conditions
- Step 7: Trade Validator Engine - Final decision layer
- Step 8: Stop Loss & Target Logic
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class MTFSignal:
    """Multi-timeframe trading signal"""
    # Basic info
    ticker: str
    signal_type: str  # BUY or SELL
    timestamp: datetime
    
    # Timeframe data
    trend_timeframe: str  # 1D
    structure_timeframe: str  # 1H
    entry_timeframe: str  # 15m
    
    # Entry parameters
    entry_price: float
    stop_loss: float
    target_1: float
    target_2: float
    
    # Analysis results
    trend_direction: str  # BULLISH or BEARISH
    trend_reason: str
    
    structure_status: str  # HIGHER_HIGHS, LOWER_LOWS, SIDEWAYS
    structure_reason: str
    
    pullback_level: Optional[float]  # EMA50 or EMA100
    pullback_status: str  # ACTIVE, COMPLETE, NONE
    
    breakout_confirmed: bool
    breakout_reason: str
    
    volume_confirmed: bool
    volume_ratio: float
    
    ema_alignment: str  # VALID, FLAT, TANGLED
    ema_alignment_reason: str
    
    # Confidence scoring
    confidence_score: int  # 0-10
    rejection_reason: Optional[str] = None
    
    # Trade details
    risk_reward_1: float = 0.0
    risk_reward_2: float = 0.0
    
    # Breakdown of why the signal triggered
    reasoning_breakdown: Dict[str, str] = field(default_factory=dict)
    
    def is_valid(self) -> bool:
        """Check if signal is valid (not rejected)"""
        return self.rejection_reason is None and self.confidence_score >= 7
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'ticker': self.ticker,
            'signal_type': self.signal_type,
            'timestamp': self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else str(self.timestamp),
            'entry_price': self.entry_price,
            'stop_loss': self.stop_loss,
            'target_1': self.target_1,
            'target_2': self.target_2,
            'confidence_score': self.confidence_score,
            'is_valid': self.is_valid(),
            'rejection_reason': self.rejection_reason,
            'trend_direction': self.trend_direction,
            'structure_status': self.structure_status,
            'pullback_status': self.pullback_status,
            'breakout_confirmed': self.breakout_confirmed,
            'volume_confirmed': self.volume_confirmed,
            'ema_alignment': self.ema_alignment
        }


@dataclass
class TrendAnalysis:
    """Results from 1D trend analysis"""
    direction: str  # BULLISH or BEARISH
    price_vs_ema200: float  # Positive if above, negative if below
    ema_alignment_score: int  # 0-4 based on EMA order
    

@dataclass
class StructureAnalysis:
    """Results from 1H structure analysis"""
    status: str  # HIGHER_HIGHS, LOWER_LOWS, SIDEWAYS
    recent_highs: List[float]
    recent_lows: List[float]
    swing_high: float
    swing_low: float
    

@dataclass
class PullbackAnalysis:
    """Results from pullback detection"""
    status: str  # ACTIVE, COMPLETE, NONE
    level: Optional[float]  # EMA50 or EMA100
    distance_to_pullback: float  # % distance
    

@dataclass  
class EntryAnalysis:
    """Results from 15m entry analysis"""
    breakout_detected: bool
    breakout_type: str  # CANDLE_CLOSE, WICK_ONLY, NONE
    resistance: float
    support: float


# ============================================================================
# EMA Alignment Validator
# ============================================================================

class EMAAlignmentValidator:
    """
    Validates EMA alignment for trend confirmation.
    
    Valid Bullish: EMA20 > EMA50 > EMA100 > EMA200
    Valid Bearish: EMA20 < EMA50 < EMA100 < EMA200
    Flat/Tangled: No clear direction -> SIDEWAYS -> NO TRADE
    """
    
    @staticmethod
    def check_alignment(indicators: Dict[str, float]) -> Tuple[str, str, int]:
        """
        Check EMA alignment and return status.
        
        Args:
            indicators: Dict with ema_20, ema_50, ema_100, ema_200
            
        Returns:
            Tuple of (alignment_status, reason, alignment_score)
            alignment_status: VALID_BULLISH, VALID_BEARISH, FLAT, TANGLED
        """
        ema_20 = indicators.get('ema_20', 0)
        ema_50 = indicators.get('ema_50', 0)
        ema_100 = indicators.get('ema_100', 0)
        ema_200 = indicators.get('ema_200', 0)
        
        if ema_20 <= 0 or ema_50 <= 0 or ema_100 <= 0 or ema_200 <= 0:
            return "TANGLED", "Insufficient EMA data", 0
        
        # Calculate alignment score (0-4)
        score = 0
        
        # Check bullish alignment
        if ema_20 > ema_50:
            score += 1
        if ema_50 > ema_100:
            score += 1
        if ema_100 > ema_200:
            score += 1
        if ema_20 > ema_200:
            score += 1
        
        # Determine status
        if score == 4:
            return "VALID_BULLISH", "EMA20 > EMA50 > EMA100 > EMA200", score
        elif score == 0:
            return "VALID_BEARISH", "EMA20 < EMA50 < EMA100 < EMA200", score
        elif score >= 2:
            # Check if mostly bullish or bearish
            if ema_20 > ema_200:
                return "VALID_BULLISH", "EMA alignment mostly bullish", score
            else:
                return "VALID_BEARISH", "EMA alignment mostly bearish", score
        else:
            return "TANGLED", f"EMA alignment unclear (score: {score})", score


# ============================================================================
# Structure Detection Module
# ============================================================================

class StructureDetector:
    """
    Identifies market structure patterns:
    - Higher Highs + Higher Lows (Bullish)
    - Lower Highs + Lower Lows (Bearish)
    - Sideways (unclear)
    """
    
    def __init__(self, lookback: int = 10):
        self.lookback = lookback
    
    def analyze(self, df: pd.DataFrame) -> StructureAnalysis:
        """
        Analyze market structure from price data.
        
        Args:
            df: DataFrame with 'high', 'low', 'close' columns
            
        Returns:
            StructureAnalysis with findings
        """
        if df is None or len(df) < self.lookback:
            return StructureAnalysis(
                status="SIDEWAYS",
                recent_highs=[],
                recent_lows=[],
                swing_high=0,
                swing_low=0
            )
        
        # Get recent price data
        recent = df.tail(self.lookback).copy()
        
        # Find local highs and lows
        highs = recent['high'].values
        lows = recent['low'].values
        
        # Find swing highs and lows
        swing_highs = []
        swing_lows = []
        
        for i in range(1, len(highs) - 1):
            if highs[i] > highs[i-1] and highs[i] > highs[i+1]:
                swing_highs.append(highs[i])
            if lows[i] < lows[i-1] and lows[i] < lows[i+1]:
                swing_lows.append(lows[i])
        
        # Get the last few swing points
        recent_highs = swing_highs[-3:] if len(swing_highs) >= 3 else swing_highs
        recent_lows = swing_lows[-3:] if len(swing_lows) >= 3 else swing_lows
        
        # Determine structure
        if len(recent_highs) >= 2 and len(recent_lows) >= 2:
            # Higher Highs + Higher Lows
            if recent_highs[-1] > recent_highs[-2] and recent_lows[-1] > recent_lows[-2]:
                status = "HIGHER_HIGHS"
            # Lower Highs + Lower Lows
            elif recent_highs[-1] < recent_highs[-2] and recent_lows[-1] < recent_lows[-2]:
                status = "LOWER_LOWS"
            else:
                status = "SIDEWAYS"
        else:
            status = "SIDEWAYS"
        
        # Get swing high/low for stop loss placement
        swing_high = max(highs[-5:]) if len(highs) >= 5 else highs[-1]
        swing_low = min(lows[-5:]) if len(lows) >= 5 else lows[-1]
        
        return StructureAnalysis(
            status=status,
            recent_highs=recent_highs,
            recent_lows=recent_lows,
            swing_high=swing_high,
            swing_low=swing_low
        )


# ============================================================================
# Pullback Detection Module
# ============================================================================

class PullbackDetector:
    """
    Detects pullback to EMA levels:
    - Bullish: Price retraces to EMA50 or EMA100
    - Bearish: Price retraces to EMA50 or EMA100
    """
    
    def __init__(self, pullback_threshold: float = 0.02):
        """
        Args:
            pullback_threshold: Max distance from EMA to consider as pullback (2%)
        """
        self.pullback_threshold = pullback_threshold
    
    def analyze(
        self, 
        df: pd.DataFrame, 
        indicators: Dict[str, float],
        trend_direction: str
    ) -> PullbackAnalysis:
        """
        Analyze pullback status.
        
        Args:
            df: DataFrame with price data
            indicators: Dict with EMA values
            trend_direction: BULLISH or BEARISH
            
        Returns:
            PullbackAnalysis with findings
        """
        current_price = df['close'].iloc[-1]
        ema_50 = indicators.get('ema_50', 0)
        ema_100 = indicators.get('ema_100', 0)
        
        if ema_50 <= 0 or ema_100 <= 0:
            return PullbackAnalysis(
                status="NONE",
                level=None,
                distance_to_pullback=0
            )
        
        # Calculate distance to each EMA level
        distance_50 = abs(current_price - ema_50) / current_price
        distance_100 = abs(current_price - ema_100) / current_price
        
        # Determine if price is at pullback level
        if distance_50 <= self.pullback_threshold:
            return PullbackAnalysis(
                status="COMPLETE",
                level=ema_50,
                distance_to_pullback=distance_50
            )
        elif distance_100 <= self.pullback_threshold:
            return PullbackAnalysis(
                status="COMPLETE",
                level=ema_100,
                distance_to_pullback=distance_100
            )
        else:
            # Check if price just pulled back (within recent candles)
            # For now, mark as COMPLETE if price is approaching EMAs
            if trend_direction == "BULLISH":
                # Price should be above EMAs but could be approaching
                if current_price > ema_50 and current_price > ema_100:
                    # Price has pulled back to EMAs and is moving up
                    if current_price < df['close'].iloc[-5] if len(df) >= 5 else current_price:
                        return PullbackAnalysis(
                            status="COMPLETE",
                            level=ema_50,
                            distance_to_pullback=distance_50
                        )
            
            return PullbackAnalysis(
                status="ACTIVE",
                level=ema_50 if distance_50 < distance_100 else ema_100,
                distance_to_pullback=min(distance_50, distance_100)
            )


# ============================================================================
# Volume Analyzer
# ============================================================================

class VolumeAnalyzer:
    """
    Analyzes volume for confirmation:
    - Current volume > Volume MA(30)
    - Flags volume spikes
    """
    
    def __init__(self, ma_period: int = 30):
        self.ma_period = ma_period
    
    def analyze(self, df: pd.DataFrame) -> Tuple[bool, float]:
        """
        Analyze volume confirmation.
        
        Args:
            df: DataFrame with 'volume' column
            
        Returns:
            Tuple of (volume_confirmed, volume_ratio)
        """
        if df is None or len(df) < self.ma_period:
            return False, 0.0
        
        current_volume = df['volume'].iloc[-1]
        
        # Calculate volume MA
        volume_ma = df['volume'].rolling(window=self.ma_period).mean().iloc[-1]
        
        if volume_ma <= 0:
            return False, 0.0
        
        volume_ratio = current_volume / volume_ma
        
        # Confirm if volume is above average
        volume_confirmed = volume_ratio > 1.0
        
        return volume_confirmed, volume_ratio


# ============================================================================
# Breakout Detector
# ============================================================================

class BreakoutDetector:
    """
    Detects entry triggers:
    - Strong breakout candle in trend direction
    - Candle closes above resistance (bullish) / below support (bearish)
    - No entry on wick-only breakout
    """
    
    def analyze(
        self, 
        df: pd.DataFrame, 
        swing_high: float,
        swing_low: float,
        trend_direction: str
    ) -> EntryAnalysis:
        """
        Analyze breakout status.
        
        Args:
            df: DataFrame with OHLC data
            swing_high: Recent swing high
            swing_low: Recent swing low
            trend_direction: BULLISH or BEARISH
            
        Returns:
            EntryAnalysis with findings
        """
        if df is None or len(df) < 2:
            return EntryAnalysis(
                breakout_detected=False,
                breakout_type="NONE",
                resistance=0,
                support=0
            )
        
        current = df.iloc[-1]
        current_close = current['close']
        current_high = current['high']
        current_low = current['low']
        
        if trend_direction == "BULLISH":
            # Check if price broke above resistance
            resistance = swing_high
            support = swing_low
            
            # Valid breakout: Close above resistance
            if current_close > resistance:
                # Confirm it's not just wick
                body_height = current_close - current['open']
                upper_wick = current_high - current_close
                
                # Strong candle: body > 50% of total range
                total_range = current_high - current_low
                if total_range > 0:
                    body_ratio = body_height / total_range
                    
                    if body_ratio >= 0.5:
                        return EntryAnalysis(
                            breakout_detected=True,
                            breakout_type="CANDLE_CLOSE",
                            resistance=resistance,
                            support=support
                        )
                    else:
                        return EntryAnalysis(
                            breakout_detected=True,
                            breakout_type="WEAK_CANDLE",
                            resistance=resistance,
                            support=support
                        )
            elif current_high > resistance and current_close <= resistance:
                # Wick-only breakout - reject
                return EntryAnalysis(
                    breakout_detected=False,
                    breakout_type="WICK_ONLY",
                    resistance=resistance,
                    support=support
                )
        else:  # BEARISH
            support = swing_high
            resistance = swing_low
            
            # Check if price broke below support
            if current_close < support:
                body_height = current['open'] - current_close
                total_range = current_high - current_low
                
                if total_range > 0:
                    body_ratio = body_height / total_range
                    
                    if body_ratio >= 0.5:
                        return EntryAnalysis(
                            breakout_detected=True,
                            breakout_type="CANDLE_CLOSE",
                            resistance=resistance,
                            support=support
                        )
                    else:
                        return EntryAnalysis(
                            breakout_detected=True,
                            breakout_type="WEAK_CANDLE",
                            resistance=resistance,
                            support=support
                        )
            elif current_low < support and current_close >= support:
                return EntryAnalysis(
                    breakout_detected=False,
                    breakout_type="WICK_ONLY",
                    resistance=resistance,
                    support=support
                )
        
        return EntryAnalysis(
            breakout_detected=False,
            breakout_type="NONE",
            resistance=swing_high,
            support=swing_low
        )


# ============================================================================
# Trade Validator Engine
# ============================================================================

class TradeValidator:
    """
    Final decision layer combining all rules.
    Outputs: VALID SIGNAL or REJECTED SIGNAL (with reason)
    """
    
    # Rejection reasons
    REJECT_EMA_FLAT = "EMAs flat or overlapping - sideways market"
    REJECT_EMA_TANGLED = "EMAs tangled - no clear trend"
    REJECT_VOLUME_LOW = "Volume below average - no confirmation"
    REJECT_NO_STRUCTURE = "No clear market structure"
    REJECT_AGAINST_TREND = "Trade against higher timeframe trend"
    REJECT_NO_BREAKOUT = "No confirmed breakout"
    REJECT_WICK_ONLY = "Breakout only on wick - no candle close"
    REJECT_NO_PULLBACK = "No pullback detected - waiting for pullback"
    
    def __init__(self):
        self.ema_validator = EMAAlignmentValidator()
        self.structure_detector = StructureDetector()
        self.pullback_detector = PullbackDetector()
        self.volume_analyzer = VolumeAnalyzer()
        self.breakout_detector = BreakoutDetector()
    
    def validate(
        self,
        ticker: str,
        mtf_data: Dict[str, pd.DataFrame],
        indicators_1d: Dict[str, float],
        indicators_1h: Dict[str, float],
        indicators_15m: Dict[str, float]
    ) -> MTFSignal:
        """
        Run complete validation of multi-timeframe data.
        
        Args:
            ticker: Stock symbol
            mtf_data: Dict with '1D', '1H', '15m' DataFrames
            indicators_1d: Indicators from 1D chart
            indicators_1h: Indicators from 1H chart
            indicators_15m: Indicators from 15m chart
            
        Returns:
            MTFSignal with validation results
        """
        timestamp = datetime.now()
        
        # Step 1: Trend Identification (1D)
        trend_direction, trend_reason = self._analyze_trend(indicators_1d)
        
        # Step 2: Market Structure Confirmation (1H)
        structure = self.structure_detector.analyze(mtf_data.get('1H'))
        structure_status = structure.status
        structure_reason = f"Swing High: {structure.swing_high:.2f}, Swing Low: {structure.swing_low:.2f}"
        
        # Step 3: EMA Alignment (1H)
        ema_alignment, ema_reason, ema_score = self.ema_validator.check_alignment(indicators_1h)
        
        # Step 4: Pullback Detection (1H)
        pullback = self.pullback_detector.analyze(
            mtf_data.get('1H'), 
            indicators_1h, 
            trend_direction
        )
        
        # Step 5: Volume Confirmation (15m)
        volume_confirmed, volume_ratio = self.volume_analyzer.analyze(mtf_data.get('15m'))
        
        # Step 6: Breakout Detection (15m)
        breakout = self.breakout_detector.analyze(
            mtf_data.get('15m'),
            structure.swing_high,
            structure.swing_low,
            trend_direction
        )
        
        # Now apply rejection rules
        rejection_reason = self._check_rejections(
            trend_direction=trend_direction,
            ema_alignment=ema_alignment,
            volume_confirmed=volume_confirmed,
            structure_status=structure_status,
            breakout=breakout,
            pullback=pullback
        )
        
        # Calculate confidence score
        confidence = self._calculate_confidence(
            trend_direction=trend_direction,
            ema_score=ema_score,
            volume_ratio=volume_ratio,
            structure_status=structure_status,
            breakout_confirmed=breakout.breakout_detected,
            pullback_status=pullback.status
        )
        
        # Calculate entry parameters
        current_price = indicators_15m.get('close', indicators_1h.get('close', indicators_1d.get('close', 0)))
        
        if trend_direction == "BULLISH":
            entry_price = current_price
            stop_loss = structure.swing_low
            risk = entry_price - stop_loss
            target_1 = entry_price + (risk * 2)
            target_2 = entry_price + (risk * 3)
            risk_reward_1 = 2.0
            risk_reward_2 = 3.0
            signal_type = "BUY"
        else:
            entry_price = current_price
            stop_loss = structure.swing_high
            risk = stop_loss - entry_price
            target_1 = entry_price - (risk * 2)
            target_2 = entry_price - (risk * 3)
            risk_reward_1 = 2.0
            risk_reward_2 = 3.0
            signal_type = "SELL"
        
        # Build reasoning breakdown
        reasoning_breakdown = {
            f"Trend ({trend_direction})": trend_reason,
            f"Structure ({structure_status})": structure_reason,
            f"EMA Alignment ({ema_alignment})": ema_reason,
            f"Pullback ({pullback.status})": f"Level: {pullback.level}",
            f"Volume ({'Confirmed' if volume_confirmed else 'Low'})": f"Ratio: {volume_ratio:.2f}",
            f"Breakout ({breakout.breakout_type})": "Confirmed" if breakout.breakout_detected else "Not confirmed"
        }
        
        signal = MTFSignal(
            ticker=ticker,
            signal_type=signal_type,
            timestamp=timestamp,
            trend_timeframe="1D",
            structure_timeframe="1H",
            entry_timeframe="15m",
            entry_price=entry_price,
            stop_loss=stop_loss,
            target_1=target_1,
            target_2=target_2,
            trend_direction=trend_direction,
            trend_reason=trend_reason,
            structure_status=structure_status,
            structure_reason=structure_reason,
            pullback_level=pullback.level,
            pullback_status=pullback.status,
            breakout_confirmed=breakout.breakout_detected,
            breakout_reason=breakout.breakout_type,
            volume_confirmed=volume_confirmed,
            volume_ratio=volume_ratio,
            ema_alignment=ema_alignment,
            ema_alignment_reason=ema_reason,
            confidence_score=confidence,
            rejection_reason=rejection_reason,
            risk_reward_1=risk_reward_1,
            risk_reward_2=risk_reward_2,
            reasoning_breakdown=reasoning_breakdown
        )
        
        return signal
    
    def _analyze_trend(self, indicators: Dict[str, float]) -> Tuple[str, str]:
        """Step 1: Determine trend from 1D data"""
        close = indicators.get('close', 0)
        ema_200 = indicators.get('ema_200', 0)
        
        if ema_200 <= 0:
            return "SIDEWAYS", "No EMA200 data"
        
        if close > ema_200:
            return "BULLISH", f"Price ₹{close:.2f} > EMA200 ₹{ema_200:.2f}"
        else:
            return "BEARISH", f"Price ₹{close:.2f} < EMA200 ₹{ema_200:.2f}"
    
    def _check_rejections(
        self,
        trend_direction: str,
        ema_alignment: str,
        volume_confirmed: bool,
        structure_status: str,
        breakout: EntryAnalysis,
        pullback: PullbackAnalysis
    ) -> Optional[str]:
        """
        Check all rejection conditions.
        Returns None if valid, rejection reason if rejected.
        """
        # Reject if EMAs flat or tangled
        if ema_alignment == "FLAT":
            return self.REJECT_EMA_FLAT
        if ema_alignment == "TANGLED":
            return self.REJECT_EMA_TANGLED
        
        # Reject if volume low
        if not volume_confirmed:
            return self.REJECT_VOLUME_LOW
        
        # Reject if no clear structure
        if structure_status == "SIDEWAYS":
            return self.REJECT_NO_STRUCTURE
        
        # Reject if trade against trend (optional - some traders take counter-trend)
        # For now, allow both directions but log the context
        
        # Reject if no breakout confirmed
        if not breakout.breakout_detected:
            return self.REJECT_NO_BREAKOUT
        
        # Reject wick-only breakout
        if breakout.breakout_type == "WICK_ONLY":
            return self.REJECT_WICK_ONLY
        
        return None
    
    def _calculate_confidence(
        self,
        trend_direction: str,
        ema_score: int,
        volume_ratio: float,
        structure_status: str,
        breakout_confirmed: bool,
        pullback_status: str
    ) -> int:
        """Calculate confidence score (0-10)"""
        score = 5  # Base score
        
        # EMA alignment (0-4)
        score += ema_score
        
        # Volume confirmation
        if volume_ratio > 1.5:
            score += 2
        elif volume_ratio > 1.0:
            score += 1
        
        # Structure
        if structure_status in ["HIGHER_HIGHS", "LOWER_LOWS"]:
            score += 2
        
        # Breakout
        if breakout_confirmed:
            score += 2
        
        # Pullback (validates entry timing)
        if pullback_status == "COMPLETE":
            score += 1
        
        return min(10, score)


# ============================================================================
# Main Strategy Scanner
# ============================================================================

class MTFStrategyScanner:
    """
    Main scanner that runs the multi-timeframe strategy.
    """
    
    def __init__(self):
        self.validator = TradeValidator()
        self.data_fetcher = None  # Will be set when integrated
    
    def set_data_fetcher(self, data_fetcher):
        """Set the data fetcher for multi-timeframe queries"""
        self.data_fetcher = data_fetcher
    
    def scan_stock(
        self, 
        ticker: str, 
        mtf_data: Dict[str, pd.DataFrame],
        indicators: Dict[str, Dict[str, float]]
    ) -> Optional[MTFSignal]:
        """
        Scan a single stock using multi-timeframe strategy.
        
        Args:
            ticker: Stock symbol
            mtf_data: Dict with '1D', '1H', '15m' DataFrames
            indicators: Dict with indicators for each timeframe
            
        Returns:
            MTFSignal if valid, None if rejected
        """
        # Check if we have all required timeframes
        df_1d = mtf_data.get('1D')
        df_1h = mtf_data.get('1H')
        df_15m = mtf_data.get('15m')
        
        if df_1d is None or df_1d.empty or df_1h is None or df_1h.empty or df_15m is None or df_15m.empty:
            logger.debug(f"Insufficient data for {ticker}")
            return None
        
        # Run validation
        signal = self.validator.validate(
            ticker=ticker,
            mtf_data=mtf_data,
            indicators_1d=indicators.get('1D', {}),
            indicators_1h=indicators.get('1H', {}),
            indicators_15m=indicators.get('15m', {})
        )
        
        # Only return valid signals
        if signal.is_valid():
            return signal
        
        logger.debug(f"Signal rejected for {ticker}: {signal.rejection_reason}")
        return None
    
    def scan_multiple_stocks(
        self,
        stocks_data: Dict[str, Dict[str, pd.DataFrame]],
        all_indicators: Dict[str, Dict[str, Dict[str, float]]]
    ) -> List[MTFSignal]:
        """
        Scan multiple stocks.
        
        Args:
            stocks_data: Dict of {ticker: {timeframe: DataFrame}}
            all_indicators: Dict of {ticker: {timeframe: indicators}}
            
        Returns:
            List of valid MTFSignals
        """
        signals = []
        
        for ticker, mtf_data in stocks_data.items():
            indicators = all_indicators.get(ticker, {})
            
            signal = self.scan_stock(ticker, mtf_data, indicators)
            if signal:
                signals.append(signal)
        
        # Sort by confidence
        signals.sort(key=lambda x: x.confidence_score, reverse=True)
        
        return signals


# ============================================================================
# Signal Formatter
# ============================================================================

def format_mtf_signal_alert(signal: MTFSignal) -> str:
    """
    Format the MTF signal as a detailed alert message.
    
    Standardized Signal Output Format:
    
    Type: BUY / SELL
    Symbol: NIFTY / BTC
    Entry:
    Stop Loss:
    Target:
    Timeframe:
    Reason:
    - Trend: Bullish (1D EMA 200)
    - Pullback: EMA 50
    - Breakout: Confirmed
    - Volume: Above Avg
    """
    from datetime import datetime
    import pytz
    
    # Get current time in IST
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist)
    
    emoji = "🟢" if signal.signal_type == "BUY" else "🔴"
    
    lines = [
        f"{emoji} {signal.signal_type} SIGNAL - {signal.ticker}",
        "",
        f"⏰ Time: {now.strftime('%Y-%m-%d %H:%M')} IST",
        f"📊 Timeframes: {signal.trend_timeframe} → {signal.structure_timeframe} → {signal.entry_timeframe}",
        "",
        "📈 TRADE PARAMETERS:",
        f"  Entry: ₹{signal.entry_price:.2f}",
        f"  Stop Loss: ₹{signal.stop_loss:.2f} ({((signal.stop_loss/signal.entry_price)-1)*100:.1f}%)",
        f"  Target 1: ₹{signal.target_1:.2f} (+{((signal.target_1/signal.entry_price)-1)*100:.1f}%) [R:R = 1:{signal.risk_reward_1}]",
        f"  Target 2: ₹{signal.target_2:.2f} (+{((signal.target_2/signal.entry_price)-1)*100:.1f}%) [R:R = 1:{signal.risk_reward_2}]",
        "",
        "🔍 ANALYSIS BREAKDOWN:"
    ]
    
    for key, value in signal.reasoning_breakdown.items():
        lines.append(f"  • {key}: {value}")
    
    lines.extend([
        "",
        f"🎯 Confidence: {signal.confidence_score}/10",
        f"📊 Signal ID: {signal.ticker}_{signal.timestamp.strftime('%Y%m%d%H%M%S')}",
        "",
        "⚠️ This signal is being tracked for outcome monitoring"
    ])
    
    return "\n".join(lines)


# ============================================================================
# Factory Functions
# ============================================================================

def create_mtf_scanner() -> MTFStrategyScanner:
    """Create and return a configured MTF scanner"""
    return MTFStrategyScanner()


def create_validator() -> TradeValidator:
    """Create and return a configured Trade Validator"""
    return TradeValidator()
