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
        self.f = settings.get("trade_filters", {
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
    
    def _calc_metrics(self, entry, sl, t1):
        sl_pct = abs((entry - sl) / entry) * 100
        tgt_pct = abs((t1 - entry) / entry) * 100
        rr = tgt_pct / sl_pct if sl_pct > 0 else 0
        return sl_pct, tgt_pct, rr

    def _basic_structure(self, entry, sl, t1, direction):
        if entry <= 0 or sl <= 0 or t1 <= 0:
            return False, "Invalid price values"

        if direction == "BUY":
            if not (t1 > entry and sl < entry):
                return False, "Invalid BUY structure"
        else:
            if not (t1 < entry and sl > entry):
                return False, "Invalid SELL structure"

        return True, ""

    def validate(self, entry: float, sl: float, t1: float, direction="BUY") -> Tuple[bool, str]:

        ok, reason = self._basic_structure(entry, sl, t1, direction)
        if not ok:
            return ok, reason

        sl_pct, tgt_pct, rr = self._calc_metrics(entry, sl, t1)

        if sl_pct < self.f["min_sl_pct"]:
            return False, f"SL too tight {sl_pct:.2f}%"

        if sl_pct > self.f["max_sl_pct"]:
            return False, f"SL too wide {sl_pct:.2f}%"

        if tgt_pct < self.f["min_target1_pct"]:
            return False, f"Target too small {tgt_pct:.2f}%"

        if tgt_pct > self.f["max_target1_pct"]:
            return False, f"Late entry {tgt_pct:.2f}%"

        if rr < self.f["min_rr"]:
            return False, f"RR too low {rr:.2f}"

        return True, "VALID"

    def validate_signal(self, signal: Any) -> Tuple[bool, str]:

        entry = getattr(signal, 'entry', 0) or getattr(signal, 'current_price', 0)
        sl = getattr(signal, 'stop_loss', 0)
        t1 = getattr(signal, 'target_1', 0)
        direction = getattr(signal, 'direction', 'BUY').upper()

        ok, reason = self.validate(entry, sl, t1, direction)
        if not ok:
            return ok, reason

        if getattr(signal, 'trend', 'SIDEWAYS') == "SIDEWAYS":
            return False, "Sideways market"

        if getattr(signal, 'candle_quality', '') == "WEAK":
            return False, "Weak candle"

        if getattr(signal, 'confidence', 0) < self.f["min_confidence"]:
            return False, "Low confidence"

        if getattr(signal, 'volume_ratio', 0) < self.f["min_volume_ratio"]:
            return False, "Low volume"

        if getattr(signal, 'breakout_strength', 0) < self.f["min_breakout_strength"]:
            return False, "Weak breakout"

        rsi = getattr(signal, 'rsi', 50)

        if direction == "BUY" and rsi > self.f["max_rsi_buy"]:
            return False, "RSI overbought"

        if direction == "SELL" and rsi < self.f["min_rsi_sell"]:
            return False, "RSI oversold"

        ema = getattr(signal, 'ema_alignment', '')

        if direction == "BUY" and ema not in ["BULLISH", "STRONG_BULLISH"]:
            return False, "EMA not bullish"

        if direction == "SELL" and ema not in ["BEARISH", "STRONG_BEARISH"]:
            return False, "EMA not bearish"

        if abs(getattr(signal, 'recent_move_pct', 0)) > self.f["max_recent_move"]:
            return False, "Overextended move"

        if getattr(signal, 'consolidation_range', 100) > self.f["max_consolidation_range"]:
            return False, "Loose structure"

        if direction == "BUY":
            if getattr(signal, 'distance_to_resistance', 100) < self.f["min_distance_sr"]:
                return False, "Near resistance"
        else:
            if getattr(signal, 'distance_to_support', 100) < self.f["min_distance_sr"]:
                return False, "Near support"

        return True, "VALID"
    
    def validate_with_indicators(self, signal: Any) -> Tuple[bool, str]:
        """
        Legacy method - redirects to validate_signal.
        """
        return self.validate_signal(signal)


def create_trade_validator(settings: Dict[str, Any]) -> TradeValidator:
    """Factory function to create TradeValidator."""
    return TradeValidator(settings)