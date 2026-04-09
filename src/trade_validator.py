"""
Trade Validator Module
Validates signals against high-quality trade constraints:
- Minimum Risk:Reward = 1:2
- Minimum Target 1 = 5%
- Maximum Target 1 = 10%
- Stop Loss strictly between 2% - 3%
"""

import logging
from typing import Tuple, Dict, Any, Optional

logger = logging.getLogger(__name__)


class TradeValidator:
    """Validates trade setups against quality filters."""
    
    def __init__(self, settings: Dict[str, Any]):
        self.filters = settings.get("trade_filters", {
            "min_rr": 2.0,
            "min_target1_pct": 5.0,
            "max_target1_pct": 10.0,
            "min_sl_pct": 2.0,
            "max_sl_pct": 3.0,
            "min_breakout_strength": 5.0,
            "min_volume_ratio": 1.3,
            "max_rsi_buy": 70.0,
            "min_rsi_sell": 30.0,
            "min_confidence": 7.0,
            "max_recent_move": 8.0,
            "max_consolidation_range": 4.0,
            "min_distance_sr": 3.0
        })
    
    def validate(self, entry: float, stop_loss: float, target_1: float) -> Tuple[bool, str]:
        """
        Validate a trade setup.
        
        Args:
            entry: Entry price
            stop_loss: Stop loss price
            target_1: First target price
            
        Returns:
            Tuple of (is_valid, reason)
        """
        if entry <= 0 or stop_loss <= 0 or target_1 <= 0:
            return False, "Invalid price values"
        
        sl_pct = abs((entry - stop_loss) / entry) * 100
        target_pct = abs((target_1 - entry) / entry) * 100
        
        if sl_pct > 0:
            rr = target_pct / sl_pct
        else:
            return False, "Invalid SL calculation"
        
        if sl_pct < self.filters["min_sl_pct"]:
            return False, f"SL too tight: {sl_pct:.2f}%"
        
        if sl_pct > self.filters["max_sl_pct"]:
            return False, f"SL too wide: {sl_pct:.2f}%"
        
        if target_pct < self.filters["min_target1_pct"]:
            return False, f"Target too small: {target_pct:.2f}%"
        
        if target_pct > self.filters["max_target1_pct"]:
            return False, f"Target too large (late entry): {target_pct:.2f}%"
        
        if rr < self.filters["min_rr"]:
            return False, f"Low RR: {rr:.2f}"
        
        return True, "VALID"
    
    def validate_signal(self, signal: Any, strategy_type: str = "TREND") -> Tuple[bool, str]:
        """
        Validate a signal object.
        
        Args:
            signal: Signal object with entry, stop_loss, target_1 attributes
            strategy_type: Strategy type (TREND or VERC)
            
        Returns:
            Tuple of (is_valid, reason)
        """
        if strategy_type == "TREND":
            indicators = getattr(signal, 'indicators', {})
            entry = indicators.get('close', 0)
            stop_loss = getattr(signal, 'stop_loss', 0)
            target_1 = getattr(signal, 'target_1', 0)
            
            if entry <= 0 or stop_loss <= 0 or target_1 <= 0:
                return False, "Missing price values"
            
        else:
            entry = getattr(signal, 'entry_min', getattr(signal, 'current_price', 0))
            stop_loss = getattr(signal, 'stop_loss', 0)
            target_1 = getattr(signal, 'target_1', 0)
            
            if entry <= 0 or stop_loss <= 0 or target_1 <= 0:
                return False, "Missing price values"
        
        return self.validate(entry, stop_loss, target_1)
    
    def validate_with_indicators(self, signal: Any) -> Tuple[bool, str]:
        """
        Validate signal including breakout strength and volume ratio.
        
        Args:
            signal: Signal object
            
        Returns:
            Tuple of (is_valid, reason)
        """
        entry = getattr(signal, 'entry', 0) or getattr(signal, 'current_price', 0) or getattr(signal, 'close', 0)
        stop_loss = getattr(signal, 'stop_loss', 0)
        target_1 = getattr(signal, 'target_1', 0)
        direction = getattr(signal, 'direction', 'BUY').upper()
        
        if entry <= 0 or stop_loss <= 0 or target_1 <= 0:
            return False, "Missing price values"
        
        if direction == "BUY":
            if not (target_1 > entry and stop_loss < entry):
                return False, "Invalid BUY structure"
        elif direction == "SELL":
            if not (target_1 < entry and stop_loss > entry):
                return False, "Invalid SELL structure"
        
        breakout_strength = getattr(signal, 'breakout_strength', 0)
        if breakout_strength < self.filters["min_breakout_strength"]:
            return False, f"Weak breakout: {breakout_strength:.2f}%"
        
        volume_ratio = getattr(signal, 'volume_ratio', 0)
        if volume_ratio < self.filters["min_volume_ratio"]:
            return False, f"Low volume: {volume_ratio:.2f}x"
        
        rsi = getattr(signal, 'rsi', 50)
        if direction == "BUY" and rsi > self.filters["max_rsi_buy"]:
            return False, f"Overbought RSI: {rsi:.2f}"
        if direction == "SELL" and rsi < self.filters["min_rsi_sell"]:
            return False, f"Oversold RSI: {rsi:.2f}"
        
        ema_alignment = getattr(signal, 'ema_alignment', '')
        if direction == "BUY" and ema_alignment not in ["BULLISH", "STRONG_BULLISH"]:
            return False, "EMA not bullish"
        if direction == "SELL" and ema_alignment not in ["BEARISH", "STRONG_BEARISH"]:
            return False, "EMA not bearish"
        
        confidence = getattr(signal, 'confidence', 0)
        if confidence < self.filters["min_confidence"]:
            return False, "Low confidence"
        
        if getattr(signal, 'candle_quality', '') == 'WEAK':
            return False, "Weak breakout candle"
        
        recent_move_pct = getattr(signal, 'recent_move_pct', 0)
        if recent_move_pct and abs(recent_move_pct) > self.filters["max_recent_move"]:
            return False, f"Overextended move: {recent_move_pct:.2f}%"
        
        consolidation_range = getattr(signal, 'consolidation_range', 100)
        if consolidation_range > self.filters["max_consolidation_range"]:
            return False, f"No tight consolidation: {consolidation_range:.2f}%"
        
        distance_to_resistance = getattr(signal, 'distance_to_resistance', 100)
        distance_to_support = getattr(signal, 'distance_to_support', 100)
        
        if direction == "BUY" and distance_to_resistance < self.filters["min_distance_sr"]:
            return False, "Too close to resistance"
        
        if direction == "SELL" and distance_to_support < self.filters["min_distance_sr"]:
            return False, "Too close to support"
        
        trend = getattr(signal, 'trend', 'SIDEWAYS').upper()
        if trend == "SIDEWAYS":
            return False, "Market sideways"
        
        strategy_type = getattr(signal, 'strategy_type', 'TREND')
        
        return self.validate(entry, stop_loss, target_1)
    
    def validate_advanced(
        self,
        entry: float,
        stop_loss: float,
        target_1: float,
        direction: str,
        indicators: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, str]:
        """
        Advanced validation with technical filters.
        
        Args:
            entry: Entry price
            stop_loss: Stop loss price
            target_1: First target price
            direction: BUY or SELL
            indicators: Dict with resistance, support, recent_move_pct, consolidation_range
            
        Returns:
            Tuple of (is_valid, reason)
        """
        is_valid, reason = self.validate(entry, stop_loss, target_1)
        if not is_valid:
            return is_valid, reason
        
        if not indicators:
            return True, "VALID"
        
        is_sell = direction.upper() == 'SELL'
        
        if is_sell:
            if not (stop_loss > entry and target_1 < entry):
                return False, "Invalid SELL structure"
        else:
            if not (entry > stop_loss and target_1 > entry):
                return False, "Invalid BUY structure"
        
        resistance = indicators.get('resistance')
        support = indicators.get('support')
        
        if direction.upper() == 'BUY' and resistance and resistance > 0:
            dist_to_resistance = abs(resistance - entry) / entry
            if dist_to_resistance < 0.03:
                return False, "Too close to resistance"
        
        if direction.upper() == 'SELL' and support and support > 0:
            dist_to_support = abs(entry - support) / entry
            if dist_to_support < 0.03:
                return False, "Too close to support"
        
        recent_move_pct = indicators.get('recent_move_pct', 0)
        if recent_move_pct and abs(recent_move_pct) > 8:
            return False, f"Overextended move ({abs(recent_move_pct):.1f}%)"
        
        consolidation_range = indicators.get('consolidation_range', 0)
        if consolidation_range and consolidation_range > 4:
            return False, "No tight consolidation"
        
        return True, "VALID"


def create_trade_validator(settings: Dict[str, Any]) -> TradeValidator:
    """Factory function to create TradeValidator."""
    return TradeValidator(settings)