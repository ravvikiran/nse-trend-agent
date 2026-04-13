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
        
        # Determine structure with 3 confirmations (more robust)
        if len(recent_highs) >= 3 and len(recent_lows) >= 3:
            # Higher Highs + Higher Lows (all 3 should trend up)
            if recent_highs[-1] > recent_highs[-2] > recent_highs[-3] and \
               recent_lows[-1] > recent_lows[-2] > recent_lows[-3]:
                status = "HIGHER_HIGHS"
            # Lower Highs + Lower Lows (all 3 should trend down)
            elif recent_highs[-1] < recent_highs[-2] < recent_highs[-3] and \
                 recent_lows[-1] < recent_lows[-2] < recent_lows[-3]:
                status = "LOWER_LOWS"
            # 2 confirmations (weaker but still valid)
            elif recent_highs[-1] > recent_highs[-2] and recent_lows[-1] > recent_lows[-2]:
                status = "HIGHER_HIGHS"
            elif recent_highs[-1] < recent_highs[-2] and recent_lows[-1] < recent_lows[-2]:
                status = "LOWER_LOWS"
            else:
                status = "SIDEWAYS"
        elif len(recent_highs) >= 2 and len(recent_lows) >= 2:
            # Fallback to 2 confirmations
            if recent_highs[-1] > recent_highs[-2] and recent_lows[-1] > recent_lows[-2]:
                status = "HIGHER_HIGHS"
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
        
        # Better pullback detection: Check if recent lows touched EMAs (traditional approach)
        # Check if any low in last 5 candles is within 1% of EMA
        recent_lows = df['low'].tail(5).values
        ema_touch_threshold = 0.01  # 1% tolerance
        
        for low in recent_lows:
            if abs(low - ema_50) / ema_50 < ema_touch_threshold:
                return PullbackAnalysis(
                    status="COMPLETE",
                    level=ema_50,
                    distance_to_pullback=distance_50
                )
            if abs(low - ema_100) / ema_100 < ema_touch_threshold:
                return PullbackAnalysis(
                    status="COMPLETE",
                    level=ema_100,
                    distance_to_pullback=distance_100
                )
        
        # Check if price just pulled back (within recent candles) - price approaching EMAs
        if trend_direction == "BULLISH":
            if current_price > ema_50 and current_price > ema_100:
                if current_price < df['close'].iloc[-5] if len(df) >= 5 else current_price:
                    return PullbackAnalysis(
                        status="COMPLETE",
                        level=ema_50,
                        distance_to_pullback=distance_50
                    )
        elif trend_direction == "BEARISH":
            if current_price < ema_50 and current_price < ema_100:
                if current_price > df['close'].iloc[-5] if len(df) >= 5 else current_price:
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
    Analyzes volume for confirmation with context:
    - Current volume > Volume MA(30)
    - Compare with last breakout volume
    - Check volume trend (rising/falling)
    """
    
    def __init__(self, ma_period: int = 30):
        self.ma_period = ma_period
    
    def get_volume_context(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Get additional volume context for confidence scoring"""
        if df is None or len(df) < self.ma_period:
            return {"trend": "unknown", "last_breakout_vol": 0, "volume_change": 0}
        
        volumes = df['volume'].tail(10).values
        current_vol = volumes[-1]
        
        # Volume trend (rising or falling)
        if len(volumes) >= 5:
            recent_avg = volumes[-5:].mean()
            older_avg = volumes[-10:-5].mean()
            if older_avg > 0:
                volume_change = (recent_avg - older_avg) / older_avg
                trend = "rising" if volume_change > 0.1 else "falling" if volume_change < -0.1 else "stable"
            else:
                trend = "unknown"
                volume_change = 0
        else:
            trend = "unknown"
            volume_change = 0
        
        # Find last significant breakout (high volume spike)
        vol_ma = df['volume'].rolling(window=20).mean()
        last_breakout_vol = 0
        for i in range(len(volumes) - 2, max(0, len(volumes) - 10), -1):
            if volumes[i] > vol_ma.iloc[i] * 1.5:
                last_breakout_vol = volumes[i]
                break
        
        return {
            "trend": trend,
            "last_breakout_vol": last_breakout_vol,
            "volume_change": volume_change
        }
    
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
        
        # Context-aware confirmation
        context = self.get_volume_context(df)
        
        # More lenient: volume confirmed if above average OR rising trend
        volume_confirmed = volume_ratio > 1.0 or context["trend"] == "rising"
        
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
            resistance = swing_high
            support = swing_low
            
            if current_close > resistance:
                min_breakout = resistance * 1.0015
                if current_close < min_breakout:
                    return EntryAnalysis(
                        breakout_detected=False,
                        breakout_type="WEAKCANDLE",
                        resistance=resistance,
                        support=support
                    )
                
                body_height = current_close - current['open']
                total_range = current_high - current_low
                if total_range > 0:
                    body_ratio = body_height / total_range
                    
                    if body_ratio >= 0.4:
                        return EntryAnalysis(
                            breakout_detected=True,
                            breakout_type="STRONG_BODY",
                            resistance=resistance,
                            support=support
                        )
                    else:
                        return EntryAnalysis(
                            breakout_detected=False,
                            breakout_type="WEAKCANDLE",
                            resistance=resistance,
                            support=support
                        )
            elif current_high > resistance and current_close <= resistance:
                return EntryAnalysis(
                    breakout_detected=False,
                    breakout_type="WICK_ONLY",
                    resistance=resistance,
                    support=support
                )
        else:  # BEARISH
            support = swing_high
            resistance = swing_low
            
            if current_close < support:
                max_breakout = support * 0.9985
                if current_close > max_breakout:
                    return EntryAnalysis(
                        breakout_detected=False,
                        breakout_type="WEAKCANDLE",
                        resistance=resistance,
                        support=support
                    )
                
                body_height = current['open'] - current_close
                total_range = current_high - current_low
                if total_range > 0:
                    body_ratio = body_height / total_range
                    
                    if body_ratio >= 0.4:
                        return EntryAnalysis(
                            breakout_detected=True,
                            breakout_type="STRONG_BODY",
                            resistance=resistance,
                            support=support
                        )
                    else:
                        return EntryAnalysis(
                            breakout_detected=False,
                            breakout_type="WEAKCANDLE",
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
    
    # Rejection reasons (standardized codes for logging)
    REJECT_EMA_FLAT = "EMAs flat or overlapping - sideways market"
    REJECT_EMA_TANGLED = "EMAs tangled - no clear trend"
    REJECT_VOLUME_LOW = "Volume below average - no confirmation"
    REJECT_NO_STRUCTURE = "No clear market structure"
    REJECT_AGAINST_TREND = "Trade against higher timeframe trend"
    REJECT_NO_BREAKOUT = "No confirmed breakout"
    REJECT_WICK_ONLY = "Breakout only on wick - no candle close"
    REJECT_NO_PULLBACK = "No pullback detected - waiting for pullback"
    
    # Hard rejection reasons (new)
    REJECT_LOW_VOLUME = "LOW_VOLUME"
    REJECT_WEAK_BREAKOUT = "WEAK_BREAKOUT"
    REJECT_LOW_ATR = "LOW_ATR"
    REJECT_MISSING_EMA200 = "MISSING_EMA200"
    REJECT_LOW_STOP_LOSS = "LOW_STOP_LOSS"
    REJECT_LOW_RISK_REWARD = "LOW_RISK_REWARD"
    REJECT_INVALID_TREND = "INVALID_TREND"
    REJECT_SIDEWAYS_MARKET = "SIDEWAYS_MARKET"
    REJECT_LOW_QUALITY = "LOW_QUALITY"
    
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
        
        # Calculate ATR for 15m timeframe
        atr_15m = self._calculate_atr_percent(mtf_data.get('15m'))
        
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
        
        # Calculate entry parameters FIRST (needed for rejection checks)
        current_price = indicators_15m.get('close', indicators_1h.get('close', indicators_1d.get('close', 0)))
        risk = 0
        risk_reward_1 = 2.0
        risk_reward_2 = 3.0
        
        if trend_direction == "BULLISH":
            entry_price = current_price
            stop_loss = structure.swing_low
            risk = entry_price - stop_loss
            signal_type = "BUY"
            
            # Structure-based targets (more adaptive than fixed RR)
            # Target 1: Next resistance / swing high
            if structure.swing_high > entry_price:
                next_resistance = structure.swing_high * 1.002
            else:
                next_resistance = entry_price * 1.02
            target_1 = next_resistance
            # Target 2: Next major structure (use RR as fallback)
            target_2 = entry_price + (risk * 3) if risk > 0 else entry_price * 1.03
            
            # Calculate actual risk/reward
            if risk > 0:
                risk_reward_1 = (target_1 - entry_price) / risk
                risk_reward_2 = (target_2 - entry_price) / risk
        else:
            entry_price = current_price
            stop_loss = structure.swing_high
            risk = stop_loss - entry_price
            signal_type = "SELL"
            
            # Structure-based targets
            # Target 1: Next support / swing low
            if structure.swing_low < entry_price:
                next_support = structure.swing_low * 0.998
            else:
                next_support = entry_price * 0.98
            target_1 = next_support
            # Target 2: Next major structure (use RR as fallback)
            target_2 = entry_price - (risk * 3) if risk > 0 else entry_price * 0.97
            
            # Calculate actual risk/reward
            if risk > 0:
                risk_reward_1 = (entry_price - target_1) / risk
                risk_reward_2 = (entry_price - target_2) / risk
        
        # Now apply rejection rules (with all required params)
        rejection_reason = self._check_rejections(
            trend_direction=trend_direction,
            ema_alignment=ema_alignment,
            volume_confirmed=volume_confirmed,
            structure_status=structure_status,
            breakout=breakout,
            pullback=pullback,
            volume_ratio=volume_ratio,
            atr_percent=atr_15m,
            indicators_1h=indicators_1h,
            signal_type=signal_type,
            entry_price=entry_price,
            stop_loss=stop_loss,
            risk_reward_1=risk_reward_1
        )
        
        # Calculate confidence score (with new caps)
        confidence = self._calculate_confidence(
            trend_direction=trend_direction,
            ema_score=ema_score,
            volume_ratio=volume_ratio,
            structure_status=structure_status,
            breakout_confirmed=breakout.breakout_detected,
            pullback_status=pullback.status,
            breakout_type=breakout.breakout_type,
            atr_percent=atr_15m
        )
        
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
    
    def _calculate_atr_percent(self, df: Optional[pd.DataFrame]) -> float:
        """Calculate ATR as percentage of current price"""
        if df is None or len(df) < 14:
            return 0.0
        
        try:
            current_close = df['close'].iloc[-1]
            high = df['high']
            low = df['low']
            close = df['close']
            
            tr1 = high - low
            tr2 = abs(high - close.shift(1))
            tr3 = abs(low - close.shift(1))
            
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(window=14).mean().iloc[-1]
            
            if current_close > 0:
                return (atr / current_close) * 100
            return 0.0
        except Exception:
            return 0.0
    
    def _check_trend_consistency(
        self,
        signal_type: str,
        indicators: Dict[str, float]
    ) -> Tuple[bool, str]:
        """
        Check strict EMA alignment consistency.
        BUY: EMA20 > EMA50 > EMA100 > EMA200
        SELL: EMA20 < EMA50 < EMA100 < EMA200
        """
        ema_20 = indicators.get('ema_20', 0)
        ema_50 = indicators.get('ema_50', 0)
        ema_100 = indicators.get('ema_100', 0)
        ema_200 = indicators.get('ema_200', 0)
        
        if ema_20 <= 0 or ema_50 <= 0 or ema_100 <= 0 or ema_200 <= 0:
            return False, "MISSING_EMA_DATA"
        
        if signal_type == "BUY":
            if ema_20 > ema_50 > ema_100 > ema_200:
                return True, "BULLISH_ALIGNMENT"
            else:
                return False, "INVALID_BULLISH_ALIGNMENT"
        else:  # SELL
            if ema_20 < ema_50 < ema_100 < ema_200:
                return True, "BEARISH_ALIGNMENT"
            else:
                return False, "INVALID_BEARISH_ALIGNMENT"
    
    def _calculate_stop_loss_percent(self, entry: float, stop_loss: float, signal_type: str) -> float:
        """Calculate stop loss percentage"""
        if entry <= 0 or stop_loss <= 0:
            return 0.0
        
        if signal_type == "BUY":
            return ((entry - stop_loss) / entry) * 100
        else:
            return ((stop_loss - entry) / entry) * 100
    
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
        pullback: PullbackAnalysis,
        volume_ratio: float = 0.0,
        atr_percent: float = 0.0,
        indicators_1h: Optional[Dict[str, float]] = None,
        signal_type: str = "BUY",
        entry_price: float = 0.0,
        stop_loss: float = 0.0,
        risk_reward_1: float = 0.0
    ) -> Optional[str]:
        """
        Check all rejection conditions including HARD REJECTION RULES.
        Returns None if valid, rejection reason if rejected.
        """
        # ========================================
        # HARD REJECTION RULES (MANDATORY) - Only 2-3 critical rejects
        # ========================================
        
        # 1. STRICT: EMA200 check (mandatory - cannot trade without it)
        if indicators_1h:
            ema_200 = indicators_1h.get('ema_200', 0)
            if ema_200 <= 0:
                logger.info("REJECT: MISSING_EMA200 - ema_200 is None or missing")
                return self.REJECT_MISSING_EMA200
        
        # 2. STRICT: Stop loss percentage check (minimum 0.5%)
        if entry_price > 0 and stop_loss > 0:
            sl_percent = self._calculate_stop_loss_percent(entry_price, stop_loss, signal_type)
            if sl_percent < 0.5:
                logger.info(f"REJECT: LOW_STOP_LOSS - sl_percent={sl_percent:.2f}% < 0.5%")
                return self.REJECT_LOW_STOP_LOSS
        
        # 3. STRICT: Sideways market (no structure)
        if structure_status == "SIDEWAYS":
            logger.info(f"REJECT: SIDEWAYS_MARKET - structure_status={structure_status}")
            return self.REJECT_SIDEWAYS_MARKET
        
        # ========================================
        # SOFT FILTERS (reduce confidence, don't reject)
        # ========================================
        
        # Volume: Will reduce score if low, but allow trading
        if volume_ratio < 1.3:
            logger.info(f"SOFT: LOW_VOLUME - volume_ratio={volume_ratio:.2f} < 1.3, score -= 2")
            # This is handled in _calculate_confidence via caps
        
        # ATR: Will reduce score if low
        if atr_percent < 0.5:
            logger.info(f"SOFT: LOW_ATR - atr_percent={atr_percent:.2f}% < 0.5%, score -= 2")
        
        # ========================================
        # TREND CONSISTENCY: Only strict check on 1D, flexible on 1H
        # ========================================
        # Using EMAAlignmentValidator (flexible) on 1H - don't duplicate with strict check
        
        # ========================================
        # SOFT VALIDATION RULES (reduce score, don't reject)
        # ========================================
        
        # Reject if EMAs flat or tangled (soft - reduces score)
        if ema_alignment == "FLAT":
            logger.info("SOFT: EMA_FLAT - no clear direction, score capped")
        if ema_alignment == "TANGLED":
            logger.info("SOFT: EMA_TANGLED - EMAs tangled, score capped")
        
        # Reject if no breakout confirmed (soft - reduces score)
        if not breakout.breakout_detected:
            logger.info("SOFT: NO_BREAKOUT - no confirmed breakout, score capped")
        
        # Breakout type weak candle check (soft)
        if breakout.breakout_type in ["WEAKCANDLE", "WICK_ONLY"]:
            logger.info(f"SOFT: WEAK_BREAKOUT - breakout_type={breakout.breakout_type}")
        
        # Risk/reward check (soft - don't reject, just note)
        if risk_reward_1 < 1.5:
            logger.info(f"SOFT: LOW_RR - risk_reward_1={risk_reward_1:.2f} < 1.5")
        
        return None
    
    def _calculate_confidence(
        self,
        trend_direction: str,
        ema_score: int,
        volume_ratio: float,
        structure_status: str,
        breakout_confirmed: bool,
        pullback_status: str,
        breakout_type: str = "NONE",
        atr_percent: float = 0.0
    ) -> int:
        """
        Calculate confidence score (0-10) with CAPS for weak conditions.
        - weak volume → max 6
        - sideways market → max 5
        - weak breakout → max 4
        """
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
        
        # ========================================
        # CAP CONFIDENCE FOR WEAK CONDITIONS
        # ========================================
        
        # Cap for weak volume (1.0x - 1.3x)
        if volume_ratio < 1.3:
            score = min(score, 6)
        
        # Cap for sideways market
        if structure_status == "SIDEWAYS":
            score = min(score, 5)
        
        # Cap for weak breakout
        if breakout_type in ["WEAK_CANDLE", "WICK_ONLY"]:
            score = min(score, 4)
        
        # Cap for low ATR
        if atr_percent < 0.5:
            score = min(score, 5)
        
        return min(10, max(1, score))


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
    
    Simplified format (v2.2):
    - Entry Zone
    - Stop Loss  
    - Targets with confidence
    - Time estimation
    - S/R Levels
    """
    emoji = "🟢" if signal.signal_type == "BUY" else "🔴"
    
    sl_pct = ((signal.entry_price - signal.stop_loss) / signal.entry_price) * 100
    t1_pct = ((signal.target_1 - signal.entry_price) / signal.entry_price) * 100
    t2_pct = ((signal.target_2 - signal.entry_price) / signal.entry_price) * 100
    
    lines = [
        f"{emoji} MTF SIGNAL",
        "",
        f"🎯 Entry Zone: ₹{signal.entry_price:.2f}",
        "",
        f"🛡️ Stop Loss: ₹{signal.stop_loss:.2f} ({sl_pct:.1f}%)",
        "",
        f"🎯 Targets (Conf: {signal.confidence_score}/10):",
        f"  T1: ₹{signal.target_1:.2f} (+{t1_pct:.1f}%)",
        f"  T2: ₹{signal.target_2:.2f} (+{t2_pct:.1f}%)",
        "",
        f"📊 {signal.trend_timeframe}→{signal.structure_timeframe}→{signal.entry_timeframe}"
    ]
    
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


# ============================================================================
# ICT-Based Structure Trading Modules
# ============================================================================


@dataclass
class SwingPoint:
    """Represents a swing high or low"""
    index: int
    price: float
    swing_type: str  # 'HIGH' or 'LOW'
    timestamp: Optional[datetime] = None


@dataclass
class LiquidityZone:
    """Represents a liquidity zone (equal highs/lows)"""
    zone_type: str  # 'BUY_SIDE' or 'SELL_SIDE'
    price: float
    tolerance: float  # 0.2% tolerance
    associated_swing: Optional[SwingPoint] = None
    swept: bool = False
    sweep_price: Optional[float] = None


@dataclass
class FVGCandle:
    """Candle data for FVG detection"""
    high: float
    low: float
    open: float
    close: float
    body: float
    index: int


@dataclass
class FVGZone:
    """Fair Value Gap zone"""
    zone_type: str  # 'BULLISH' or 'BEARISH'
    top: float
    bottom: float
    mid: float
    created_at: int  # candle index
    filled: bool = False
    fill_price: Optional[float] = None


@dataclass 
class DisplacementMove:
    """Strong displacement move"""
    detected: bool
    direction: str  # 'BULLISH' or 'BEARISH'
    candle_index: int
    body_ratio: float
    volume_ratio: float
    strength: float  # Combined score


@dataclass
class ICTSignal:
    """ICT-based trading signal"""
    ticker: str
    signal_type: str  # BUY or SELL
    timestamp: datetime
    
    entry_price: float
    stop_loss: float
    target_1: float
    target_2: float
    
    market_structure: str  # HH/HL or LH/LL
    structure_reason: str
    
    liquidity_type: str  # BUY_SIDE or SELL_SIDE
    liquidity_price: float
    liquidity_sweeped: bool
    
    fvg_zone: Optional[FVGZone]
    displacement: DisplacementMove
    
    risk_reward_1: float
    risk_reward_2: float
    
    confidence_score: int
    rejection_reason: Optional[str] = None
    
    reasoning_breakdown: Dict[str, str] = field(default_factory=dict)
    
    def is_valid(self) -> bool:
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
            'market_structure': self.market_structure,
            'liquidity_type': self.liquidity_type,
            'liquidity_price': self.liquidity_price,
            'fvg_zone': {
                'type': self.fvg_zone.zone_type if self.fvg_zone else None,
                'top': self.fvg_zone.top if self.fvg_zone else None,
                'bottom': self.fvg_zone.bottom if self.fvg_zone else None,
            } if self.fvg_zone else None,
            'displacement': {
                'detected': self.displacement.detected,
                'direction': self.displacement.direction,
                'strength': self.displacement.strength
            },
            'risk_reward_1': self.risk_reward_1,
            'risk_reward_2': self.risk_reward_2,
            'confidence_score': self.confidence_score,
            'is_valid': self.is_valid(),
            'rejection_reason': self.rejection_reason
        }


# ============================================================================
# ICT Market Structure Detector
# ============================================================================

class ICTMarketStructure:
    """
    ICT Market Structure Detection.
    Identifies swing highs/lows and determines structure:
    - Bullish: HH/HL (Higher Highs, Higher Lows)
    - Bearish: LH/LL (Lower Highs, Lower Lows)
    """
    
    def __init__(self, lookback: int = 50, swing_strength: int = 5):
        self.lookback = lookback
        self.swing_strength = swing_strength  # Sensitivity for swing detection
    
    def find_swing_points(self, df: pd.DataFrame) -> List[SwingPoint]:
        """Find all swing highs and lows"""
        if df is None or len(df) < self.swing_strength * 2:
            return []
        
        swings = []
        highs = df['high'].values
        lows = df['low'].values
        
        for i in range(self.swing_strength, len(highs) - self.swing_strength):
            # Check for swing high
            is_high = True
            for j in range(max(0, i - self.swing_strength), min(len(highs), i + self.swing_strength + 1)):
                if j != i and highs[i] <= highs[j]:
                    is_high = False
                    break
            if is_high:
                swings.append(SwingPoint(
                    index=i,
                    price=highs[i],
                    swing_type='HIGH'
                ))
            
            # Check for swing low
            is_low = True
            for j in range(max(0, i - self.swing_strength), min(len(lows), i + self.swing_strength + 1)):
                if j != i and lows[i] >= lows[j]:
                    is_low = False
                    break
            if is_low:
                swings.append(SwingPoint(
                    index=i,
                    price=lows[i],
                    swing_type='LOW'
                ))
        
        return swings
    
    def detect_structure(self, swings: List[SwingPoint]) -> Tuple[str, str]:
        """
        Detect market structure from swing points.
        Returns (structure, reason)
        """
        if len(swings) < 4:
            return "UNCLEAR", "Insufficient swing points"
        
        recent_swings = swings[-4:]
        
        highs = [s for s in recent_swings if s.swing_type == 'HIGH']
        lows = [s for s in recent_swings if s.swing_type == 'LOW']
        
        if len(highs) < 2 or len(lows) < 2:
            return "UNCLEAR", "Not enough highs/lows"
        
        highs_sorted = sorted(highs, key=lambda x: x.price, reverse=True)
        lows_sorted = sorted(lows, key=lambda x: x.price, reverse=True)
        
        # Bullish: Higher Highs and Higher Lows
        if highs_sorted[0].price > highs_sorted[1].price and lows_sorted[0].price > lows_sorted[1].price:
            return "HH_HL", f"Bullish: HH={highs_sorted[0].price:.2f}, HL={lows_sorted[0].price:.2f}"
        
        # Bearish: Lower Highs and Lower Lows
        if highs_sorted[0].price < highs_sorted[1].price and lows_sorted[0].price < lows_sorted[1].price:
            return "LH_LL", f"Bearish: LH={highs_sorted[0].price:.2f}, LL={lows_sorted[0].price:.2f}"
        
        return "UNCLEAR", "No clear HH/HL or LH/LL pattern"
    
    def analyze(self, df: pd.DataFrame) -> Tuple[str, str, List[SwingPoint]]:
        """Full market structure analysis"""
        swings = self.find_swing_points(df)
        structure, reason = self.detect_structure(swings)
        return structure, reason, swings


# ============================================================================
# Liquidity Detector
# ============================================================================

class LiquidityDetector:
    """
    Detects liquidity zones (equal highs/lows).
    Tolerance: 0.2% for equal highs/lows
    """
    
    TOLERANCE = 0.002  # 0.2%
    
    def __init__(self, lookback: int = 20):
        self.lookback = lookback
    
    def find_equal_highs(self, swings: List[SwingPoint]) -> List[LiquidityZone]:
        """Find equal highs (sell-side liquidity)"""
        highs = [s for s in swings if s.swing_type == 'HIGH']
        equal_zones = []
        
        for i, h1 in enumerate(highs):
            for h2 in highs[i+1:]:
                if h1.price == 0 or h2.price == 0:
                    continue
                    
                tolerance = (abs(h1.price - h2.price) / h1.price)
                
                if tolerance <= self.TOLERANCE:
                    avg_price = (h1.price + h2.price) / 2
                    zone = LiquidityZone(
                        zone_type='SELL_SIDE',
                        price=avg_price,
                        tolerance=tolerance,
                        associated_swing=h1,
                        swept=False
                    )
                    if zone not in equal_zones:
                        equal_zones.append(zone)
        
        return equal_zones
    
    def find_equal_lows(self, swings: List[SwingPoint]) -> List[LiquidityZone]:
        """Find equal lows (buy-side liquidity)"""
        lows = [s for s in swings if s.swing_type == 'LOW']
        equal_zones = []
        
        for i, l1 in enumerate(lows):
            for l2 in lows[i+1:]:
                if l1.price == 0 or l2.price == 0:
                    continue
                    
                tolerance = abs(l1.price - l2.price) / l1.price
                
                if tolerance <= self.TOLERANCE:
                    avg_price = (l1.price + l2.price) / 2
                    zone = LiquidityZone(
                        zone_type='BUY_SIDE',
                        price=avg_price,
                        tolerance=tolerance,
                        associated_swing=l1,
                        swept=False
                    )
                    if zone not in equal_zones:
                        equal_zones.append(zone)
        
        return equal_zones
    
    def check_sweep(self, zone: LiquidityZone, df: pd.DataFrame) -> Tuple[bool, Optional[float]]:
        """Check if liquidity zone was swept (wicks past)"""
        if zone.zone_type == 'SELL_SIDE':
            max_high = df['high'].max()
            if max_high > zone.price * 1.001:
                return True, max_high
        else:  # BUY_SIDE
            min_low = df['low'].min()
            if min_low < zone.price * 0.999:
                return True, min_low
        
        return False, None
    
    def analyze(self, df: pd.DataFrame, swings: List[SwingPoint]) -> Tuple[List[LiquidityZone], List[LiquidityZone]]:
        """Full liquidity analysis"""
        equal_highs = self.find_equal_highs(swings)
        equal_lows = self.find_equal_lows(swings)
        
        for zone in equal_highs:
            zone.swept, zone.sweep_price = self.check_sweep(zone, df)
        
        for zone in equal_lows:
            zone.swept, zone.sweep_price = self.check_sweep(zone, df)
        
        return equal_highs, equal_lows


# ============================================================================
# Displacement Detector
# ============================================================================

class DisplacementDetector:
    """
    Detects strong displacement moves.
    Requirements:
    - candle_body > average_body * 1.5
    - volume_ratio > 1.5
    """
    
    def __init__(self, lookback: int = 20):
        self.lookback = lookback
    
    def calculate_average_body(self, df: pd.DataFrame) -> float:
        """Calculate average candle body size"""
        if df is None or len(df) < 5:
            return 0
        
        bodies = abs(df['close'] - df['open'])
        return bodies.tail(self.lookback).mean()
    
    def analyze_displacement(self, df: pd.DataFrame, direction: str) -> DisplacementMove:
        """
        Detect displacement in given direction.
        """
        if df is None or len(df) < 5:
            return DisplacementMove(False, "NONE", -1, 0, 0, 0)
        
        avg_body = self.calculate_average_body(df)
        if avg_body <= 0:
            return DisplacementMove(False, "NONE", -1, 0, 0, 0)
        
        recent = df.tail(5)
        
        for idx, row in recent.iterrows():
            body = abs(row['close'] - row['open'])
            body_ratio = body / avg_body
            
            if len(df['volume']) > 30:
                vol_ma = df['volume'].tail(30).mean()
                vol_ratio = row['volume'] / vol_ma if vol_ma > 0 else 0
            else:
                vol_ratio = 1.0
            
            is_bullish = row['close'] > row['open']
            is_bearish = row['close'] < row['open']
            
            if direction == "BULLISH" and is_bullish and body_ratio > 1.5 and vol_ratio > 1.5:
                strength = (body_ratio - 1.5) + (vol_ratio - 1.5)
                return DisplacementMove(True, "BULLISH", idx, body_ratio, vol_ratio, strength)
            
            if direction == "BEARISH" and is_bearish and body_ratio > 1.5 and vol_ratio > 1.5:
                strength = (body_ratio - 1.5) + (vol_ratio - 1.5)
                return DisplacementMove(True, "BEARISH", idx, body_ratio, vol_ratio, strength)
        
        return DisplacementMove(False, "NONE", -1, 0, 0, 0)


# ============================================================================
# Fair Value Gap (FVG) Detector
# ============================================================================

class FVGDetector:
    """
    Detects Fair Value Gaps (3-candle imbalance).
    
    Bullish FVG: candle1.high < candle3.low
    Bearish FVG: candle1.low > candle3.high
    """
    
    def __init__(self, min_gap_percent: float = 0.1):
        self.min_gap_percent = min_gap_percent  # Minimum 0.1% gap
    
    def detect_fvg(self, candles: List[FVGCandle]) -> List[FVGZone]:
        """Detect FVGs from candle data"""
        fvgs = []
        
        for i in range(len(candles) - 2):
            c1 = candles[i]
            c2 = candles[i + 1]
            c3 = candles[i + 2]
            
            mid_price = (c1.high + c1.low + c3.high + c3.low) / 4
            
            bullish_gap = c1.high < c3.low
            bearish_gap = c1.low > c3.high
            
            if bullish_gap:
                gap_size = ((c3.low - c1.high) / mid_price) * 100
                if gap_size >= self.min_gap_percent:
                    fvgs.append(FVGZone(
                        zone_type='BULLISH',
                        top=c3.low,
                        bottom=c1.high,
                        mid=(c3.low + c1.high) / 2,
                        created_at=i
                    ))
            
            elif bearish_gap:
                gap_size = ((c1.low - c3.high) / mid_price) * 100
                if gap_size >= self.min_gap_percent:
                    fvgs.append(FVGZone(
                        zone_type='BEARISH',
                        top=c1.low,
                        bottom=c3.high,
                        mid=(c1.low + c3.high) / 2,
                        created_at=i
                    ))
        
        return fvgs
    
    def find_nearest_fvg(self, fvgs: List[FVGZone], price: float, direction: str) -> Optional[FVGZone]:
        """Find nearest unfilled FVG in direction of trade"""
        if direction == "BULLISH":
            candidate_fvgs = [f for f in fvgs if f.zone_type == 'BULLISH' and f.top < price]
        else:
            candidate_fvgs = [f for f in fvgs if f.zone_type == 'BEARISH' and f.bottom > price]
        
        if not candidate_fvgs:
            return None
        
        if direction == "BULLISH":
            candidate_fvgs.sort(key=lambda x: x.top, reverse=True)
        else:
            candidate_fvgs.sort(key=lambda x: x.bottom)
        
        return candidate_fvgs[0]
    
    def analyze(self, df: pd.DataFrame) -> List[FVGZone]:
        """Full FVG analysis"""
        if df is None or len(df) < 3:
            return []
        
        candles = []
        for idx, row in df.iterrows():
            candles.append(FVGCandle(
                high=row['high'],
                low=row['low'],
                open=row['open'],
                close=row['close'],
                body=abs(row['close'] - row['open']),
                index=idx
            ))
        
        return self.detect_fvg(candles)


# ============================================================================
# ICT Entry Engine
# ============================================================================

class ICTEntryEngine:
    """
    ICT Entry Logic.
    
    BUY Requirements:
    - sell-side liquidity taken (swept)
    - bullish structure shift (HH/HL)
    - bullish displacement
    - price returns to bullish FVG
    
    SELL Requirements:
    - buy-side liquidity taken (swept)
    - bearish structure shift (LH/LL)
    - bearish displacement
    - price returns to bearish FVG
    """
    
    def __init__(self):
        self.structure_detector = ICTMarketStructure()
        self.liquidity_detector = LiquidityDetector()
        self.displacement_detector = DisplacementDetector()
        self.fvg_detector = FVGDetector()
    
    def validate_entry_conditions(
        self,
        df: pd.DataFrame,
        swings: List[SwingPoint],
        structure: str,
        sell_side_liquidity: List[LiquidityZone],
        buy_side_liquidity: List[LiquidityZone],
        displacement: DisplacementMove,
        fvgs: List[FVGZone]
    ) -> Tuple[bool, str, str, Optional[LiquidityZone], Optional[FVGZone]]:
        """
        Validate ICT entry conditions.
        Returns: (valid, signal_type, reason, liquidity_zone, fvg_zone)
        """
        if df is None or len(df) < 3:
            return False, "NONE", "Insufficient data", None, None
        
        current_price = df['close'].iloc[-1]
        
        # ========================================
        # BULLISH SETUP VALIDATION
        # ========================================
        
        # Find swept sell-side liquidity (above current price)
        swept_sell_liq = [l for l in sell_side_liquidity if l.swept and l.price > current_price]
        
        if swept_sell_liq and structure == "HH_HL" and displacement.direction == "BULLISH":
            nearest_fvg = self.fvg_detector.find_nearest_fvg(fvgs, current_price, "BULLISH")
            if nearest_fvg:
                return True, "BUY", "Bullish ICT setup", swept_sell_liq[0], nearest_fvg
        
        # ========================================
        # BEARISH SETUP VALIDATION
        # ========================================
        
        # Find swept buy-side liquidity (below current price)
        swept_buy_liq = [l for l in buy_side_liquidity if l.swept and l.price < current_price]
        
        if swept_buy_liq and structure == "LH_LL" and displacement.direction == "BEARISH":
            nearest_fvg = self.fvg_detector.find_nearest_fvg(fvgs, current_price, "BEARISH")
            if nearest_fvg:
                return True, "SELL", "Bearish ICT setup", swept_buy_liq[0], nearest_fvg
        
        return False, "NONE", "No valid ICT setup", None, None
    
    def calculate_stop_loss(
        self,
        signal_type: str,
        entry_price: float,
        liquidity_zone: LiquidityZone,
        df: pd.DataFrame
    ) -> float:
        """
        Calculate stop loss below/above liquidity sweep point.
        """
        if liquidity_zone.sweep_price:
            sweep_price = liquidity_zone.sweep_price
        else:
            sweep_price = liquidity_zone.price
        
        if signal_type == "BUY":
            return sweep_price * 0.998  # Just below sweep
        else:
            return sweep_price * 1.002  # Just above sweep
    
    def calculate_targets(
        self,
        signal_type: str,
        entry_price: float,
        stop_loss: float,
        fvgs: List[FVGZone],
        liquidity_zones: List[LiquidityZone]
    ) -> Tuple[float, float, float]:
        """
        Calculate targets based on next liquidity zone.
        Minimum RR: 1:2
        """
        risk = abs(entry_price - stop_loss)
        
        target_1 = entry_price + (risk * 2) if signal_type == "BUY" else entry_price - (risk * 2)
        target_2 = entry_price + (risk * 3) if signal_type == "BUY" else entry_price - (risk * 3)
        
        return target_1, target_2, 2.0
    
    def analyze(
        self,
        df: pd.DataFrame,
        timeframe: str = "15m"
    ) -> Tuple[Optional[ICTSignal], Dict[str, Any]]:
        """
        Full ICT analysis.
        Returns: (ICTSignal or None, analysis_context)
        """
        if df is None or len(df) < 50:
            return None, {"error": "Insufficient data"}
        
        context = {}
        
        structure, structure_reason, swings = self.structure_detector.analyze(df)
        context['structure'] = structure
        context['structure_reason'] = structure_reason
        context['swing_count'] = len(swings)
        
        sell_liq, buy_liq = self.liquidity_detector.analyze(df, swings)
        context['sell_side_liquidity'] = len(sell_liq)
        context['buy_side_liquidity'] = len(buy_liq)
        
        trend_direction = "BULLISH" if structure == "HH_HL" else "BEARISH"
        displacement = self.displacement_detector.analyze_displacement(df, trend_direction)
        context['displacement'] = displacement.to_dict() if displacement.detected else None
        
        fvgs = self.fvg_detector.analyze(df)
        context['fvg_count'] = len(fvgs)
        
        valid, signal_type, reason, liq_zone, fvg_zone = self.validate_entry_conditions(
            df, swings, structure, sell_liq, buy_liq, displacement, fvgs
        )
        
        if not valid:
            return None, context
        
        current_price = df['close'].iloc[-1]
        
        stop_loss = self.calculate_stop_loss(signal_type, current_price, liq_zone, df)
        target_1, target_2, rr = self.calculate_targets(signal_type, current_price, stop_loss, fvgs, sell_liq + buy_liq)
        
        risk_reward_1 = (abs(target_1 - current_price) / abs(current_price - stop_loss)) if abs(current_price - stop_loss) > 0 else 0
        
        confidence = self._calculate_confidence(structure, displacement, len(fvgs), liq_zone.swept)
        
        signal = ICTSignal(
            ticker="NIFTY",
            signal_type=signal_type,
            timestamp=datetime.now(),
            entry_price=current_price,
            stop_loss=stop_loss,
            target_1=target_1,
            target_2=target_2,
            market_structure=structure,
            structure_reason=structure_reason,
            liquidity_type=liq_zone.zone_type,
            liquidity_price=liq_zone.price,
            liquidity_sweeped=liq_zone.swept,
            fvg_zone=fvg_zone,
            displacement=displacement,
            risk_reward_1=risk_reward_1,
            risk_reward_2=3.0,
            confidence_score=confidence,
            reasoning_breakdown={
                "Structure": structure_reason,
                "Setup": reason,
                "FVG": f"Filled at {fvg_zone.mid:.2f}" if fvg_zone else "No FVG",
                "Displacement": f"Strength {displacement.strength:.2f}" if displacement.detected else "No displacement"
            }
        )
        
        return signal, context
    
    def _calculate_confidence(
        self,
        structure: str,
        displacement: DisplacementMove,
        fvg_count: int,
        liquidity_swept: bool
    ) -> int:
        """Calculate confidence score for ICT signal"""
        score = 5
        
        if structure in ["HH_HL", "LH_LL"]:
            score += 2
        
        if displacement.detected:
            score += 2
        
        if fvg_count > 0:
            score += 1
        
        if liquidity_swept:
            score += 2
        
        if displacement.strength > 3:
            score += 1
        
        return min(10, max(1, score))


# ============================================================================
# ICT Scanner
# ============================================================================

class ICTScanner:
    """
    Main scanner for ICT-based trading signals.
    """
    
    def __init__(self):
        self.entry_engine = ICTEntryEngine()
    
    def scan(
        self,
        ticker: str,
        df: pd.DataFrame,
        timeframe: str = "15m"
    ) -> Optional[ICTSignal]:
        """
        Scan for ICT trading signals.
        """
        signal, context = self.entry_engine.analyze(df, timeframe)
        
        if signal:
            signal.ticker = ticker
            if signal.is_valid():
                logger.info(f"ICT Signal: {signal.signal_type} for {ticker} @ {signal.entry_price:.2f}")
                return signal
        
        if context.get('structure') == "UNCLEAR":
            logger.debug(f"ICT: No clear structure for {ticker}")
        else:
            logger.debug(f"ICT: No valid setup for {ticker}")
        
        return None


def create_ict_scanner() -> ICTScanner:
    """Create and return an ICT scanner"""
    return ICTScanner()

