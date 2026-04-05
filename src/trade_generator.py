"""
Trade Setup Generator Module
Generates actionable trade setups with entry, stop loss, targets, and risk management.
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class TradeSetup:
    """Complete trade setup with entry, risk management, and targets."""
    stock_symbol: str
    signal_type: str
    timestamp: datetime
    
    current_price: float
    
    entry_min: float
    entry_max: float
    entry_strategy: str
    
    stop_loss: float
    stop_loss_pct: float
    risk_level: str
    
    target_1: float
    target_1_pct: float
    target_1_rr: float
    target_1_distance: float
    
    target_2: float
    target_2_pct: float
    target_2_rr: float
    target_2_distance: float
    
    target_3: Optional[float] = None
    target_3_pct: Optional[float] = None
    target_3_rr: Optional[float] = None
    target_3_distance: Optional[float] = None
    
    range_low: float = 0.0
    range_high: float = 0.0
    range_height: float = 0.0
    
    support_level: float = 0.0
    resistance_level: float = 0.0
    
    near_breakout: bool = False
    breakout_distance_pct: float = 0.0
    
    expected_duration: str = ""
    
    confidence: int = 0
    
    positive_factors: List[str] = field(default_factory=list)
    negative_factors: List[str] = field(default_factory=list)
    
    ai_reasoning: str = ""
    sector: str = "Unknown"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'stock_symbol': self.stock_symbol,
            'signal_type': self.signal_type,
            'timestamp': self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else str(self.timestamp),
            'current_price': self.current_price,
            'entry': {
                'min': self.entry_min,
                'max': self.entry_max,
                'strategy': self.entry_strategy
            },
            'stop_loss': {
                'price': self.stop_loss,
                'percentage': self.stop_loss_pct,
                'risk_level': self.risk_level
            },
            'targets': {
                'target_1': {
                    'price': self.target_1,
                    'percentage': self.target_1_pct,
                    'rr_ratio': self.target_1_rr,
                    'distance': self.target_1_distance
                },
                'target_2': {
                    'price': self.target_2,
                    'percentage': self.target_2_pct,
                    'rr_ratio': self.target_2_rr,
                    'distance': self.target_2_distance
                },
                'target_3': {
                    'price': self.target_3,
                    'percentage': self.target_3_pct,
                    'rr_ratio': self.target_3_rr,
                    'distance': self.target_3_distance
                } if self.target_3 else None
            },
            'range': {
                'low': self.range_low,
                'high': self.range_high,
                'height': self.range_height
            },
            'levels': {
                'support': self.support_level,
                'resistance': self.resistance_level
            },
            'breakout': {
                'near_breakout': self.near_breakout,
                'distance_pct': self.breakout_distance_pct
            },
            'expected_duration': self.expected_duration,
            'confidence': self.confidence,
            'positive_factors': self.positive_factors,
            'negative_factors': self.negative_factors,
            'ai_reasoning': self.ai_reasoning,
            'sector': self.sector
        }


class TradeSetupGenerator:
    """
    Generates actionable trade setups from signals.
    
    Features:
    - Breakout entry and early accumulation entry strategies
    - Dynamic stop loss calculation
    - Multiple target levels with R:R ratios
    - Risk level classification
    - Time estimates based on ATR
    """
    
    DEFAULT_STOP_LOSS_PCT = 2.0
    BREAKOUT_THRESHOLD = 0.5
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.default_sl_pct = self.config.get('default_stop_loss_pct', self.DEFAULT_STOP_LOSS_PCT)
    
    def generate_from_signal(self, signal: Any, price_data: Dict[str, Any]) -> TradeSetup:
        """
        Generate a trade setup from a signal.
        
        Args:
            signal: Signal object (VERCSignal, TrendSignal, CombinedSignal)
            price_data: Dictionary with price and indicator data
            
        Returns:
            TradeSetup object
        """
        stock_symbol = getattr(signal, 'stock_symbol', getattr(signal, 'ticker', 'UNKNOWN'))
        signal_type = getattr(signal, 'signal_type', getattr(signal, 'type', 'GENERAL'))
        
        current_price = price_data.get('current_price', price_data.get('close', 0))
        atr = price_data.get('atr', 0)
        ema50 = price_data.get('ema50', price_data.get('ema_50', current_price))
        ema20 = price_data.get('ema20', price_data.get('ema_20', current_price))
        
        range_low = price_data.get('range_low', current_price * 0.98)
        range_high = price_data.get('range_high', current_price * 1.02)
        
        support_level = self._calculate_support(current_price, range_low, ema50)
        resistance_level = self._calculate_resistance(current_price, range_high)
        
        near_breakout, breakout_dist = self._check_breakout(current_price, resistance_level)
        
        entry_strategy, entry_min, entry_max = self._calculate_entry(
            current_price, resistance_level, range_low, near_breakout
        )
        
        stop_loss, sl_pct, risk_level = self._calculate_stop_loss(
            current_price, support_level, price_data
        )
        
        range_height = range_high - range_low
        
        target_1, t1_pct, t1_rr, t1_dist = self._calculate_target(
            current_price, stop_loss, range_height, 1.0
        )
        
        target_2, t2_pct, t2_rr, t2_dist = self._calculate_target(
            current_price, stop_loss, range_height, 1.5
        )
        
        target_3, t3_pct, t3_rr, t3_dist = self._calculate_target(
            current_price, stop_loss, resistance_level - current_price, 1.0, is_swing=True
        )
        
        expected_duration = self._estimate_duration(atr, current_price)
        
        confidence = self._calculate_confidence(signal, price_data)
        
        positive_factors, negative_factors = self._analyze_factors(
            price_data, near_breakout, range_height, current_price
        )
        
        return TradeSetup(
            stock_symbol=stock_symbol,
            signal_type=signal_type,
            timestamp=datetime.now(),
            current_price=current_price,
            entry_min=entry_min,
            entry_max=entry_max,
            entry_strategy=entry_strategy,
            stop_loss=stop_loss,
            stop_loss_pct=sl_pct,
            risk_level=risk_level,
            target_1=target_1,
            target_1_pct=t1_pct,
            target_1_rr=t1_rr,
            target_1_distance=t1_dist,
            target_2=target_2,
            target_2_pct=t2_pct,
            target_2_rr=t2_rr,
            target_2_distance=t2_dist,
            target_3=target_3,
            target_3_pct=t3_pct,
            target_3_rr=t3_rr,
            target_3_distance=t3_dist,
            range_low=range_low,
            range_high=range_high,
            range_height=range_height,
            support_level=support_level,
            resistance_level=resistance_level,
            near_breakout=near_breakout,
            breakout_distance_pct=breakout_dist,
            expected_duration=expected_duration,
            confidence=confidence,
            positive_factors=positive_factors,
            negative_factors=negative_factors
        )
    
    def _calculate_support(self, current_price: float, range_low: float, ema50: float) -> float:
        """Calculate support level."""
        return min(range_low, ema50 * 0.98)
    
    def _calculate_resistance(self, current_price: float, range_high: float) -> float:
        """Calculate resistance level."""
        return range_high
    
    def _check_breakout(self, current_price: float, resistance: float) -> tuple:
        """Check if price is near breakout."""
        if resistance <= 0:
            return False, 0.0
        distance = resistance - current_price
        distance_pct = (distance / current_price) * 100
        near = distance_pct <= self.BREAKOUT_THRESHOLD
        return near, distance_pct
    
    def _calculate_entry(self, current_price: float, resistance: float, 
                         range_low: float, near_breakout: bool) -> tuple:
        """Calculate entry zone and strategy."""
        if near_breakout:
            entry_strategy = "Breakout Entry"
            entry_min = resistance
            entry_max = resistance * 1.005
        else:
            entry_strategy = "Early Accumulation Entry"
            entry_min = current_price
            entry_max = current_price * 1.01
        
        return entry_strategy, entry_min, entry_max
    
    def _calculate_stop_loss(self, current_price: float, support: float, 
                             price_data: Dict[str, Any]) -> tuple:
        """Calculate stop loss and risk level."""
        calculated_sl = support * 0.98
        
        sl_pct = ((current_price - calculated_sl) / current_price) * 100
        
        if sl_pct <= 1.5:
            risk_level = "Low"
        elif sl_pct <= 3.0:
            risk_level = "Moderate"
        else:
            risk_level = "High"
        
        return calculated_sl, round(sl_pct, 2), risk_level
    
    def _calculate_target(self, current_price: float, stop_loss: float, 
                          distance: float, multiplier: float, is_swing: bool = False) -> tuple:
        """Calculate target price, percentage, R:R ratio, and distance."""
        if is_swing:
            target = current_price + distance
        else:
            target = current_price + (distance * multiplier)
        
        target_pct = ((target - current_price) / current_price) * 100
        
        risk = current_price - stop_loss
        reward = target - current_price
        rr = round(reward / risk, 2) if risk > 0 else 0
        
        distance_points = round(target - current_price, 2)
        
        return round(target, 2), round(target_pct, 2), rr, distance_points
    
    def _estimate_duration(self, atr: float, current_price: float) -> str:
        """Estimate expected duration based on ATR."""
        if atr <= 0:
            return "Unknown"
        
        atr_pct = (atr / current_price) * 100
        
        if atr_pct < 1.0:
            return "short_term"
        elif atr_pct < 2.0:
            return "medium_term"
        else:
            return "long_term"
    
    def _calculate_confidence(self, signal: Any, price_data: Dict[str, Any]) -> int:
        """Calculate confidence score."""
        base_confidence = getattr(signal, 'confidence', 7)
        
        volume_ratio = price_data.get('volume_ratio', 1.0)
        if volume_ratio > 1.5:
            base_confidence += 1
        
        near_breakout = price_data.get('near_breakout', False)
        if near_breakout:
            base_confidence += 1
        
        return min(10, base_confidence)
    
    def _analyze_factors(self, price_data: Dict[str, Any], near_breakout: bool,
                         range_height: float, current_price: float) -> tuple:
        """Analyze positive and negative factors."""
        positive = []
        negative = []
        
        volume_ratio = price_data.get('volume_ratio', 1.0)
        if volume_ratio > 1.3:
            positive.append("Volume expansion detected")
        elif volume_ratio < 0.8:
            negative.append("Low volume")
        
        if near_breakout:
            positive.append("Near breakout")
        
        ema_alignment = price_data.get('ema_alignment_score', 0)
        if ema_alignment >= 3:
            positive.append("Strong EMA alignment")
        elif ema_alignment <= 1:
            negative.append("Weak EMA alignment")
        
        rsi = price_data.get('rsi', 50)
        if 40 <= rsi <= 70:
            positive.append("RSI in optimal zone")
        elif rsi > 70:
            negative.append("RSI overbought")
        elif rsi < 30:
            positive.append("RSI oversold")
        
        range_compression = (range_height / current_price) * 100
        if range_compression < 3:
            positive.append("Tight range compression")
        elif range_compression > 8:
            negative.append("Wide range")
        
        return positive, negative
    
    def format_alert_message(self, trade_setup: TradeSetup) -> str:
        """Format trade setup as Telegram alert message."""
        msg = f"📊 *{trade_setup.signal_type} SIGNAL*\n\n"
        msg += f"Stock: *{trade_setup.stock_symbol}*\n"
        msg += f"Price: ₹{trade_setup.current_price:.2f}\n\n"
        
        msg += f"🎯 *Entry:*\n"
        msg += f"  Strategy: {trade_setup.entry_strategy}\n"
        msg += f"  Zone: ₹{trade_setup.entry_min:.2f} - ₹{trade_setup.entry_max:.2f}\n\n"
        
        msg += f"🛡️ *Stop Loss:*\n"
        msg += f"  SL: ₹{trade_setup.stop_loss:.2f} ({trade_setup.stop_loss_pct:.1f}%)\n"
        msg += f"  Risk Level: {trade_setup.risk_level}\n\n"
        
        msg += f"🎯 *Targets:*\n"
        msg += f"  T1: ₹{trade_setup.target_1:.2f} (+{trade_setup.target_1_pct:.1f}%) R:R {trade_setup.target_1_rr}\n"
        msg += f"  T2: ₹{trade_setup.target_2:.2f} (+{trade_setup.target_2_pct:.1f}%) R:R {trade_setup.target_2_rr}\n"
        if trade_setup.target_3:
            msg += f"  T3: ₹{trade_setup.target_3:.2f} (+{trade_setup.target_3_pct:.1f}%) R:R {trade_setup.target_3_rr}\n"
        msg += "\n"
        
        msg += f"📈 *Technical Levels:*\n"
        msg += f"  Support: ₹{trade_setup.support_level:.2f}\n"
        msg += f"  Resistance: ₹{trade_setup.resistance_level:.2f}\n"
        msg += f"  Range: ₹{trade_setup.range_low:.2f} - ₹{trade_setup.range_high:.2f}\n"
        
        if trade_setup.near_breakout:
            msg += f"\n⚡ Near Breakout: {trade_setup.breakout_distance_pct:.1f}% away\n"
        
        msg += f"\n⏱️ Expected: {trade_setup.expected_duration}\n"
        msg += f"Confidence: {trade_setup.confidence}/10\n"
        
        if trade_setup.positive_factors:
            msg += f"\n✅ *Positives:*\n"
            for factor in trade_setup.positive_factors[:3]:
                msg += f"  • {factor}\n"
        
        if trade_setup.negative_factors:
            msg += f"\n⚠️ *Negatives:*\n"
            for factor in trade_setup.negative_factors[:3]:
                msg += f"  • {factor}\n"
        
        if trade_setup.ai_reasoning:
            msg += f"\n💡 *AI Insight:*\n{trade_setup.ai_reasoning[:200]}..."
        
        return msg


def create_trade_generator(config: Optional[Dict[str, Any]] = None) -> TradeSetupGenerator:
    """Factory function to create TradeSetupGenerator."""
    return TradeSetupGenerator(config)