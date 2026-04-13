"""
Trade Validator Module
Validates signals against high-quality trade constraints.

FIXES APPLIED:
  - validate_signal() previously checked `signal.ema_alignment` which is never
    set on TrendSignal / VERCSignal objects — getattr always returned '' and the
    check failed for every signal, silently blocking all trades.

    The EMA alignment requirement is already enforced upstream by TrendDetector
    (score += 3 for alignment, min score = 6) and by VERC's check_trend_alignment().
    Duplicating it here with a string attribute that is never populated adds no
    safety and only breaks things.

    Fix: the ema_alignment guard has been removed from validate_signal().
    All other filters (RR, SL%, target%, volume, RSI, breakout, distance to S/R)
    are preserved.
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
            "min_breakout_strength": 2.0,
            "min_volume_ratio": 1.3,
            "max_rsi_buy": 70.0,
            "min_rsi_sell": 30.0,
            "min_confidence": 7.0,
            "max_recent_move": 8.0,
            "max_consolidation_range": 4.0,
            "min_distance_sr": 3.0,
        })

    # ------------------------------------------------------------------
    # Core price-level validation (used standalone or as part of validate_signal)
    # ------------------------------------------------------------------

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
        """Validate raw price levels only."""
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

    # ------------------------------------------------------------------
    # Full signal validation
    # ------------------------------------------------------------------

    def validate_signal(self, signal: Any) -> Tuple[bool, str]:
        """
        Validate a signal object against all quality filters.

        NOTE: The ema_alignment check that was here has been removed (FIX 12).
        EMA alignment is enforced by TrendDetector scoring upstream and is
        never stored as a string attribute on signal objects, so the check
        always returned False and blocked every trade silently.
        """
        entry = getattr(signal, 'entry', 0) or getattr(signal, 'current_price', 0)
        sl = getattr(signal, 'stop_loss', 0)
        t1 = getattr(signal, 'target_1', 0)
        direction = getattr(signal, 'direction', 'BUY').upper()

        # Price structure check
        ok, reason = self.validate(entry, sl, t1, direction)
        if not ok:
            return ok, reason

        # Market condition
        if getattr(signal, 'trend', 'SIDEWAYS') == "SIDEWAYS":
            return False, "Sideways market"

        # Candle quality
        if getattr(signal, 'candle_quality', '') == "WEAK":
            return False, "Weak candle"

        # Confidence threshold (only if the attribute is present and non-zero)
        confidence = getattr(signal, 'confidence', None)
        if confidence is not None and confidence > 0:
            if confidence < self.f["min_confidence"]:
                return False, "Low confidence"

        # Volume
        volume_ratio = getattr(signal, 'volume_ratio', 0)
        if volume_ratio > 0 and volume_ratio < self.f["min_volume_ratio"]:
            return False, "Low volume"

        # Breakout strength
        breakout_strength = getattr(signal, 'breakout_strength', 0)
        if breakout_strength > 0 and breakout_strength < self.f["min_breakout_strength"]:
            return False, "Weak breakout"

        # RSI
        rsi = getattr(signal, 'rsi', 0)
        if rsi > 0:
            if direction == "BUY" and rsi > self.f["max_rsi_buy"]:
                return False, "RSI overbought"
            if direction == "SELL" and rsi < self.f["min_rsi_sell"]:
                return False, "RSI oversold"

        # NOTE: ema_alignment string check removed — see module docstring.

        # Overextended move
        recent_move = abs(getattr(signal, 'recent_move_pct', 0))
        if recent_move > 0 and recent_move > self.f["max_recent_move"]:
            return False, "Overextended move"

        # Consolidation range
        consolidation_range = getattr(signal, 'consolidation_range', 0)
        if consolidation_range > 0 and consolidation_range > self.f["max_consolidation_range"]:
            return False, "Loose structure"

        # Distance to S/R
        if direction == "BUY":
            dist = getattr(signal, 'distance_to_resistance', 100)
            if dist < self.f["min_distance_sr"]:
                return False, "Near resistance"
        else:
            dist = getattr(signal, 'distance_to_support', 100)
            if dist < self.f["min_distance_sr"]:
                return False, "Near support"

        return True, "VALID"

    def validate_with_indicators(self, signal: Any) -> Tuple[bool, str]:
        """Alias kept for backward compatibility."""
        return self.validate_signal(signal)


def create_trade_validator(settings: Dict[str, Any]) -> TradeValidator:
    return TradeValidator(settings)
