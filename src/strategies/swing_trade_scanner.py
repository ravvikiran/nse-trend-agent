"""
Swing Trade Scanner

Focus: Clean trends, Swing trades
Timeframes: Trend → Daily, Entry → 1H

Core Logic:
- EMA 50/200 alignment
- Volume delivery spike
- Structure (HH/HL)

Extra Data:
- Sector strength
- NIFTY alignment
- Delivery %

Strategies:
- Trend continuation
- Breakout after consolidation

Avoid:
- Low volume stocks
- News spikes
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class SwingSignal:
    """Swing trading signal"""
    ticker: str
    signal_type: str  # BUY or SELL
    timestamp: datetime
    
    # Timeframes
    trend_timeframe: str = "1D"
    entry_timeframe: str = "1H"
    
    # Entry parameters
    entry_price: float = 0.0
    stop_loss: float = 0.0
    target_1: float = 0.0
    target_2: float = 0.0
    
    # Trend analysis
    trend_direction: str = "UNKNOWN"
    ema_50_200_alignment: bool = False
    
    # Structure
    structure_status: str = "SIDEWAYS"
    hh_hl_confirmed: bool = False
    
    # Volume
    volume_spike: bool = False
    volume_ratio: float = 0.0
    
    # Extra data
    sector_strength: str = "NEUTRAL"
    nifty_aligned: bool = False
    delivery_percent: float = 0.0
    
    # Strategy
    strategy_type: str = "TREND_CONTINUATION"  # or BREAKOUT_CONSOLIDATION
    
    # Confidence
    confidence_score: int = 0
    rejection_reason: Optional[str] = None
    
    # Risk
    risk_reward_1: float = 0.0
    risk_reward_2: float = 0.0
    
    # Reasoning
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
            'trend_direction': self.trend_direction,
            'structure_status': self.structure_status,
            'ema_50_200_alignment': self.ema_50_200_alignment,
            'volume_spike': self.volume_spike,
            'confidence_score': self.confidence_score,
            'is_valid': self.is_valid(),
            'rejection_reason': self.rejection_reason,
            'strategy_type': self.strategy_type
        }


class SwingTradeScanner:
    """
    Scanner for swing trades with clean trends.
    
    Timeframe Setup:
    - Trend: 1D (Daily) - For EMA alignment and overall direction
    - Entry: 1H (Hourly) - For entry timing
    
    Requirements:
    - EMA 50 > EMA 200 (bullish alignment)
    - Volume spike (>1.5x average)
    - HH/HL structure confirmed
    """
    
    MIN_CONFIDENCE = 7
    MIN_VOLUME_RATIO = 1.5
    MIN_DELIVERY_PERCENT = 30.0
    
    def __init__(self):
        self.alerted_today = set()
        self.last_reset_date = None
    
    def check_ema_50_200_alignment(self, indicators: Dict[str, float]) -> Tuple[bool, str]:
        """
        Check EMA 50/200 alignment.
        Bullish: EMA50 > EMA200
        Bearish: EMA50 < EMA200
        """
        ema_50 = indicators.get('ema_50', 0)
        ema_200 = indicators.get('ema_200', 0)
        
        if ema_50 <= 0 or ema_200 <= 0:
            return False, "Missing EMA data"
        
        if ema_50 > ema_200:
            return True, f"EMA50 ₹{ema_50:.2f} > EMA200 ₹{ema_200:.2f}"
        else:
            return False, f"EMA50 ₹{ema_50:.2f} < EMA200 ₹{ema_200:.2f}"
    
    def check_volume_spike(self, indicators: Dict[str, float], min_ratio: float = 1.5) -> Tuple[bool, float]:
        """Check if volume is spiking"""
        volume_ratio = indicators.get('volume_ratio', 0)
        
        if volume_ratio >= min_ratio:
            return True, volume_ratio
        return False, volume_ratio
    
    def detect_structure_1h(self, df: pd.DataFrame) -> Tuple[str, bool]:
        """
        Detect HH/HL structure on 1H timeframe.
        Returns (structure_status, is_bullish)
        """
        if df is None or len(df) < 20:
            return "SIDEWAYS", False
        
        recent = df.tail(20).copy()
        
        highs = recent['high'].values
        lows = recent['low'].values
        
        swing_highs = []
        swing_lows = []
        
        for i in range(2, len(highs) - 2):
            if highs[i] > highs[i-1] and highs[i] > highs[i+1] and \
               highs[i] > highs[i-2] and highs[i] > highs[i+2]:
                swing_highs.append(highs[i])
            if lows[i] < lows[i-1] and lows[i] < lows[i+1] and \
               lows[i] < lows[i-2] and lows[i] < lows[i+2]:
                swing_lows.append(lows[i])
        
        if len(swing_highs) >= 2 and len(swing_lows) >= 2:
            recent_highs = swing_highs[-2:]
            recent_lows = swing_lows[-2:]
            
            if recent_highs[-1] > recent_highs[-2] and recent_lows[-1] > recent_lows[-2]:
                return "HH_HL", True
            elif recent_highs[-1] < recent_highs[-2] and recent_lows[-1] < recent_lows[-2]:
                return "LH_LL", False
        
        return "SIDEWAYS", False
    
    def check_breakout_consolidation(self, df_1h: pd.DataFrame, indicators_1h: Dict[str, float]) -> Tuple[bool, str]:
        """
        Check if price is breaking out of consolidation or continuing trend.
        """
        if df_1h is None or len(df_1h) < 20:
            return False, "INSUFFICIENT_DATA"
        
        recent = df_1h.tail(20)
        
        current_close = recent['close'].iloc[-1]
        high_20 = recent['high'].max()
        low_20 = recent['low'].min()
        
        range_pct = (high_20 - low_20) / low_20
        
        if range_pct < 0.05:
            if current_close >= high_20 * 0.99:
                return True, "BREAKOUT_CONSOLIDATION"
        elif current_close > recent['close'].iloc[-5]:
            return True, "TREND_CONTINUATION"
        
        return False, "NO_BREAKOUT"
    
    def check_nifty_alignment(self, nifty_data: Optional[Dict[str, Any]]) -> bool:
        """Check if NIFTY is aligned with the trade direction"""
        if nifty_data is None:
            return True
        
        try:
            close = nifty_data.get('close', 0)
            ema_200 = nifty_data.get('ema_200', 0)
            
            if close > ema_200:
                return True
            return False
        except Exception as e:
            logger.warning(f"Error checking NIFTY EMA trend: {e}")
            return True
    
    def get_delivery_percent(self, ticker: str) -> float:
        """Get delivery percentage for the stock"""
        try:
            import yfinance as yf
            ticker_clean = ticker.replace('.NS', '')
            nse_ticker = f"{ticker_clean}.NS"
            
            stock = yf.Ticker(nse_ticker)
            info = stock.info
            
            return info.get('deliveryToChartRatio', 0) * 100
        except Exception as e:
            logger.warning(f"Error fetching delivery percent for {ticker}: {e}")
            return 50.0
    
    def scan_stock(
        self,
        ticker: str,
        df_daily: pd.DataFrame,
        df_hourly: pd.DataFrame,
        indicators_daily: Dict[str, float],
        indicators_hourly: Dict[str, float],
        nifty_data: Optional[Dict[str, Any]] = None,
        sector_data: Optional[Dict[str, Any]] = None
    ) -> Optional[SwingSignal]:
        """
        Scan a single stock for swing trade opportunities.
        
        Args:
            ticker: Stock symbol
            df_daily: Daily timeframe data
            df_hourly: Hourly timeframe data
            indicators_daily: Indicators from daily
            indicators_hourly: Indicators from hourly
            nifty_data: NIFTY data for alignment check
            sector_data: Sector performance data
            
        Returns:
            SwingSignal if valid, None if rejected
        """
        if df_daily is None or df_hourly is None:
            return None
        
        timestamp = datetime.now()
        
        # Step 1: Check EMA 50/200 alignment on daily
        ema_aligned, ema_reason = self.check_ema_50_200_alignment(indicators_daily)
        
        if not ema_aligned:
            logger.debug(f"{ticker} - EMA 50/200 not aligned")
            return None
        
        # Step 2: Check volume spike on daily
        vol_spike, vol_ratio = self.check_volume_spike(indicators_daily, self.MIN_VOLUME_RATIO)
        
        if not vol_spike:
            logger.debug(f"{ticker} - No volume spike")
            return None
        
        # Step 3: Check structure on hourly
        structure_status, is_bullish = self.detect_structure_1h(df_hourly)
        
        if structure_status == "SIDEWAYS":
            logger.debug(f"{ticker} - No clear structure")
            return None
        
        # Step 4: Check breakout/consolidation
        breakout_detected, strategy = self.check_breakout_consolidation(df_hourly, indicators_hourly)
        
        if not breakout_detected:
            return None
        
        # Step 5: NIFTY alignment
        nifty_aligned = self.check_nifty_alignment(nifty_data)
        
        # Step 6: Get delivery percentage
        delivery_pct = self.get_delivery_percent(ticker)
        
        # Determine signal type
        signal_type = "BUY" if is_bullish else "SELL"
        
        # Calculate entry parameters
        current_price = indicators_hourly.get('close', indicators_daily.get('close', 0))
        
        if is_bullish:
            entry_price = current_price
            recent_low = df_hourly['low'].tail(10).min()
            stop_loss = recent_low * 0.99
            risk = entry_price - stop_loss
            
            target_1 = entry_price + (risk * 2)
            target_2 = entry_price + (risk * 3)
        else:
            entry_price = current_price
            recent_high = df_hourly['high'].tail(10).max()
            stop_loss = recent_high * 1.01
            risk = stop_loss - entry_price
            
            target_1 = entry_price - (risk * 2)
            target_2 = entry_price - (risk * 3)
        
        rr_1 = (target_1 - entry_price) / risk if risk > 0 else 0
        rr_2 = (target_2 - entry_price) / risk if risk > 0 else 0
        
        # Calculate confidence
        confidence = self._calculate_confidence(
            ema_aligned=ema_aligned,
            vol_spike=vol_spike,
            vol_ratio=vol_ratio,
            structure_status=structure_status,
            is_bullish=is_bullish,
            delivery_pct=delivery_pct,
            nifty_aligned=nifty_aligned
        )
        
        # Build reasoning
        reasoning = {
            "EMA Alignment": ema_reason,
            "Volume": f"Spike: {vol_ratio:.2f}x",
            "Structure": structure_status,
            "Strategy": strategy,
            "Delivery %": f"{delivery_pct:.1f}%"
        }
        
        signal = SwingSignal(
            ticker=ticker,
            signal_type=signal_type,
            timestamp=timestamp,
            entry_price=entry_price,
            stop_loss=stop_loss,
            target_1=target_1,
            target_2=target_2,
            trend_direction="BULLISH" if is_bullish else "BEARISH",
            ema_50_200_alignment=ema_aligned,
            structure_status=structure_status,
            hh_hl_confirmed=(structure_status in ["HH_HL", "LH_LL"]),
            volume_spike=vol_spike,
            volume_ratio=vol_ratio,
            nifty_aligned=nifty_aligned,
            delivery_percent=delivery_pct,
            strategy_type=strategy,
            confidence_score=confidence,
            risk_reward_1=rr_1,
            risk_reward_2=rr_2,
            reasoning_breakdown=reasoning
        )
        
        if confidence >= self.MIN_CONFIDENCE:
            return signal
        
        return None
    
    def _calculate_confidence(
        self,
        ema_aligned: bool,
        vol_spike: bool,
        vol_ratio: float,
        structure_status: str,
        is_bullish: bool,
        delivery_pct: float,
        nifty_aligned: bool
    ) -> int:
        """Calculate confidence score (0-10)"""
        score = 5
        
        # EMA alignment
        if ema_aligned:
            score += 3
        
        # Volume
        if vol_spike:
            score += 2
        elif vol_ratio > 1.3:
            score += 1
        
        # Structure
        if structure_status in ["HH_HL", "LH_LL"]:
            score += 2
        
        # Delivery percentage
        if delivery_pct >= 50:
            score += 1
        elif delivery_pct < 30:
            score = min(score, 6)
        
        # NIFTY alignment
        if nifty_aligned:
            score += 1
        
        return min(10, max(1, score))
    
    def scan_multiple_stocks(
        self,
        stocks_data: Dict[str, Dict[str, pd.DataFrame]],
        all_indicators: Dict[str, Dict[str, Dict[str, float]]],
        nifty_data: Optional[Dict[str, Any]] = None
    ) -> List[SwingSignal]:
        """Scan multiple stocks"""
        signals = []
        
        for ticker, mtf_data in stocks_data.items():
            df_daily = mtf_data.get('1D')
            df_hourly = mtf_data.get('1H')
            
            indicators_daily = all_indicators.get(ticker, {}).get('1D', {})
            indicators_hourly = all_indicators.get(ticker, {}).get('1H', {})
            
            signal = self.scan_stock(
                ticker=ticker,
                df_daily=df_daily,
                df_hourly=df_hourly,
                indicators_daily=indicators_daily,
                indicators_hourly=indicators_hourly,
                nifty_data=nifty_data
            )
            
            if signal:
                signals.append(signal)
        
        signals.sort(key=lambda x: x.confidence_score, reverse=True)
        return signals
    
    def reset_daily(self):
        """Reset alerted stocks for new day"""
        from datetime import date
        today = date.today()
        
        if self.last_reset_date != today:
            self.alerted_today.clear()
            self.last_reset_date = today


def format_swing_signal_alert(signal: SwingSignal) -> str:
    """Format swing signal as alert message"""
    emoji = "🟢" if signal.signal_type == "BUY" else "🔴"
    
    sl_pct = ((signal.entry_price - signal.stop_loss) / signal.entry_price) * 100
    t1_pct = ((signal.target_1 - signal.entry_price) / signal.entry_price) * 100
    t2_pct = ((signal.target_2 - signal.entry_price) / signal.entry_price) * 100
    
    lines = [
        f"{emoji} SWING TRADE",
        "",
        f"📈 Entry: ₹{signal.entry_price:.2f}",
        f"🛡️ SL: ₹{signal.stop_loss:.2f} ({sl_pct:.1f}%)",
        f"🎯 T1: ₹{signal.target_1:.2f} (+{t1_pct:.1f}%)",
        f"🎯 T2: ₹{signal.target_2:.2f} (+{t2_pct:.1f}%)",
        "",
        f"📊 {signal.trend_timeframe} → {signal.entry_timeframe}",
        f"🔗 Structure: {signal.structure_status}",
        f"📦 Volume: {signal.volume_ratio:.2f}x",
        f"📦 Delivery: {signal.delivery_percent:.1f}%",
        f"📈 Conf: {signal.confidence_score}/10"
    ]
    
    return "\n".join(lines)


def create_swing_scanner() -> SwingTradeScanner:
    """Create and return a configured swing scanner"""
    return SwingTradeScanner()
