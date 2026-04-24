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
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    is_valid: bool
    reason: str
    score: float
    details: Dict[str, Any]


class TradeValidator:
    """Validates trade setups against quality filters."""
    
    def __init__(self, settings: Optional[Dict[str, Any]] = None):
        default_filters = {
            "min_rr": 1.5,
            "min_target1_pct": 3.0,
            "max_target1_pct": 15.0,
            "min_sl_pct": 1.0,
            "max_sl_pct": 5.0,
            "min_breakout_strength": 1.0,
            "min_volume_ratio": 1.1,
            "max_rsi_buy": 75.0,
            "min_rsi_sell": 25.0,
            "min_confidence": 5.0,
            "max_recent_move": 10.0,
            "max_consolidation_range": 6.0,
            "min_distance_sr": 2.5,
        }
        
        if settings:
            self.f = settings.get("trade_filters", default_filters)
        else:
            self.f = default_filters
    
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

        ok, reason = self.validate(entry, sl, t1, direction)
        if not ok:
            return ok, reason

        if getattr(signal, 'trend', 'SIDEWAYS') == "SIDEWAYS":
            return False, "Sideways market"

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

        if getattr(signal, 'breakout_strength', 0) < self.f["min_breakout_strength"]:
            return False, "Weak breakout"

        rsi = getattr(signal, 'rsi', 50)

        if direction == "BUY" and rsi > self.f["max_rsi_buy"]:
            return False, "RSI overbought"

        if direction == "SELL" and rsi < self.f["min_rsi_sell"]:
            return False, "RSI oversold"

        # NOTE: ema_alignment string check removed — see module docstring.

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
    
    def validate_complete(self, signal: Any, stock_data: Optional[Dict[str, Any]] = None) -> ValidationResult:
        """
        Complete validation with full details and scoring.

        NOTE: ema_alignment check removed (same issue as validate_signal).
        
        Args:
            signal: Signal object/dict
            stock_data: Optional stock data for additional checks
            
        Returns:
            ValidationResult with validity status, reason, score, details
        """
        details = {}
        score = 100.0
        
        entry = getattr(signal, 'entry_price', 0) or getattr(signal, 'current_price', 0)
        sl = getattr(signal, 'stop_loss', 0)
        t1 = getattr(signal, 'target_1', 0)
        direction = getattr(signal, 'direction', 'BUY').upper()
        
        ok, reason = self.validate(entry, sl, t1, direction)
        details['structure'] = {'valid': ok, 'reason': reason}
        if not ok:
            score -= 40
            return ValidationResult(False, reason, score, details)
        
        trend = getattr(signal, 'trend', 'SIDEWAYS')
        if trend == "SIDEWAYS":
            score -= 15
            details['trend'] = 'sideways'
        
        candle = getattr(signal, 'candle_quality', '')
        if candle == "WEAK":
            score -= 10
            details['candle'] = 'weak'
        
        confidence = getattr(signal, 'confidence', getattr(signal, 'score', 0))
        if confidence < self.f["min_confidence"]:
            score -= 15
            details['low_confidence'] = True
        
        volume_ratio = getattr(signal, 'volume_ratio', 0)
        if stock_data:
            stock_vol = stock_data.get('volume_ratio', 0)
            if stock_vol > volume_ratio:
                volume_ratio = stock_vol
        
        if volume_ratio > 0 and volume_ratio < self.f["min_volume_ratio"]:
            score -= 15
            details['low_volume'] = True
        elif volume_ratio >= self.f["min_volume_ratio"]:
            details['volume_spike'] = True
        
        breakout = getattr(signal, 'breakout_strength', 0)
        if breakout < self.f["min_breakout_strength"]:
            score -= 10
            details['weak_breakout'] = True
        
        rsi = getattr(signal, 'rsi', 50)
        if direction == "BUY" and rsi > self.f["max_rsi_buy"]:
            score -= 10
            details['rsi_overbought'] = True
        elif direction == "SELL" and rsi < self.f["min_rsi_sell"]:
            score -= 10
            details['rsi_oversold'] = True

        # EMA alignment check removed — handled upstream

        recent_move = abs(getattr(signal, 'recent_move_pct', 0))
        if recent_move > self.f["max_recent_move"]:
            score -= 10
            details['overextended'] = True
        
        final_valid = score >= 60
        final_reason = "PASSED" if final_valid else f"Low score: {score}"
        
        return ValidationResult(final_valid, final_reason, max(0, score), details)
    
    def filter_signals(self, signals: list, stock_data_map: Optional[Dict[str, Dict[str, Any]]] = None) -> list:
        """
        Filter a list of signals, returning only valid ones.
        
        Args:
            signals: List of signal dicts/objects
            stock_data_map: Optional map of stock_symbol -> stock_data
            
        Returns:
            List of valid signals
        """
        valid_signals = []
        
        for signal in signals:
            stock = getattr(signal, 'stock_symbol', '') or signal.get('stock_symbol', '')
            stock_data = stock_data_map.get(stock) if stock_data_map and stock_data_map.get(stock) else None
            
            result = self.validate_complete(signal, stock_data)
            
            if result.is_valid:
                if hasattr(signal, '_validation_score'):
                    signal._validation_score = result.score
                else:
                    signal['_validation_score'] = result.score
                valid_signals.append(signal)
            else:
                logger.info(f"Signal filtered: {stock} - {result.reason}")
        
        logger.info(f"Filtered {len(signals)} signals -> {len(valid_signals)} valid")
        return valid_signals


def create_trade_validator(settings: Optional[Dict[str, Any]] = None) -> TradeValidator:
    """Factory function to create TradeValidator."""
    return TradeValidator(settings)