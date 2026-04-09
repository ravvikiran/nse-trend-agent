"""
Trade Validator Module
Validates signals against high-quality trade constraints:
- Minimum Risk:Reward = 1:2
- Minimum Target 1 = 5%
- Maximum Target 1 = 10%
- Stop Loss strictly between 2% - 3%
- Minimum breakout strength = 5%
- Minimum volume ratio = 2.5x
- Maximum RSI = 70
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
            "min_volume_ratio": 2.5,
            "max_rsi": 70.0
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
            ema50 = indicators.get('ema50', 0)
            atr = indicators.get('atr', 0)
            
            if entry <= 0:
                return False, "No entry price"
            
            stop_loss = min(ema50, entry * 0.98) if ema50 > 0 else entry * 0.98
            if atr > 0:
                stop_loss = min(stop_loss, entry - (2 * atr))
            
            risk = entry - stop_loss
            if risk <= 0:
                return False, "Invalid risk calculation"
            
            target_1 = entry + (risk * 2)
            
        else:
            entry = getattr(signal, 'entry_min', getattr(signal, 'current_price', 0))
            stop_loss = getattr(signal, 'stop_loss', 0)
            target_1 = getattr(signal, 'target_1', 0)
            
            if entry <= 0 or stop_loss <= 0 or target_1 <= 0:
                return False, "Missing price values"
        
        return self.validate(entry, stop_loss, target_1)
    
    def validate_with_indicators(self, signal: Any) -> Tuple[bool, str]:
        """
        Validate signal including breakout strength, volume ratio, and RSI.
        
        Args:
            signal: Signal object
            
        Returns:
            Tuple of (is_valid, reason)
        """
        breakout_strength = getattr(signal, 'breakout_strength', 0) * 100
        volume_ratio = getattr(signal, 'volume_ratio', 0)
        rsi = getattr(signal, 'rsi', 50)
        
        if breakout_strength < self.filters["min_breakout_strength"]:
            return False, f"Weak breakout: {breakout_strength:.2f}%"
        
        if volume_ratio < self.filters["min_volume_ratio"]:
            return False, f"Low volume: {volume_ratio:.2f}x"
        
        if rsi > self.filters["max_rsi"]:
            return False, f"Overbought RSI: {rsi:.2f}"
        
        strategy_type = getattr(signal, 'strategy_type', 'TREND')
        return self.validate_signal(signal, strategy_type)


def create_trade_validator(settings: Dict[str, Any]) -> TradeValidator:
    """Factory function to create TradeValidator."""
    return TradeValidator(settings)