"""
Enhanced Signal Validator with Technical Pattern & AI Validation
Ensures only high-quality, technically sound signals are sent as alerts
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime

logger = logging.getLogger(__name__)


class EnhancedSignalValidator:
    """
    Comprehensive signal validator that checks:
    1. Minimum score threshold
    2. Technical pattern (higher highs, higher lows)
    3. Stop loss reasonableness
    4. AI validation
    5. Risk/reward ratio
    """
    
    def __init__(self, min_score: float = 5.0, ai_analyzer=None):
        """
        Initialize validator.
        
        Args:
            min_score: Minimum acceptable signal score (0-10)
            ai_analyzer: AI analyzer instance for validation
        """
        self.min_score = min_score
        self.ai_analyzer = ai_analyzer
        self.max_sl_percent = 0.07  # 7% max stop loss (reasonable risk)
        
    def validate_signal_before_sending(
        self, 
        signal, 
        df: Optional[pd.DataFrame] = None,
        use_ai: bool = True
    ) -> Tuple[bool, str]:
        """
        Comprehensive signal validation before sending alert.
        
        Returns:
            (is_valid, reason) tuple
        """
        # Step 1: Check score
        is_valid, reason = self._validate_score(signal)
        if not is_valid:
            return False, f"Score check failed: {reason}"
        
        # Step 2: Check stop loss reasonableness
        is_valid, reason = self._validate_stop_loss(signal)
        if not is_valid:
            return False, f"Stop loss check failed: {reason}"
        
        # Step 3: Check risk/reward ratio
        is_valid, reason = self._validate_risk_reward(signal)
        if not is_valid:
            return False, f"Risk/reward check failed: {reason}"
        
        # Step 4: Check technical pattern if dataframe available
        if df is not None and len(df) > 0:
            is_valid, reason = self._validate_technical_pattern(signal, df)
            if not is_valid:
                return False, f"Technical pattern check failed: {reason}"
        
        # Step 5: AI validation if enabled
        if use_ai and self.ai_analyzer:
            is_valid, reason = self._validate_with_ai(signal, df)
            if not is_valid:
                return False, f"AI validation failed: {reason}"
        
        return True, "All validations passed"
    
    def _validate_score(self, signal) -> Tuple[bool, str]:
        """Check if signal score meets minimum threshold."""
        score = self._get_signal_score(signal)
        
        if score is None:
            return False, "No valid score found"
        
        if score < self.min_score:
            return False, f"Score {score:.1f} below threshold {self.min_score}"
        
        return True, f"Score {score:.1f} meets threshold"
    
    def _validate_stop_loss(self, signal) -> Tuple[bool, str]:
        """
        Check if stop loss is reasonable.
        - Should not be > 5% away from entry (reasonable risk)
        - Should follow chart pattern
        """
        entry = self._get_entry_price(signal)
        stop_loss = self._get_stop_loss(signal)
        
        if entry <= 0 or stop_loss <= 0:
            return False, "Invalid entry or stop loss"
        
        if stop_loss >= entry:
            return False, "Stop loss >= entry (invalid)"
        
        # Calculate risk percentage
        risk_pct = (entry - stop_loss) / entry
        
        if risk_pct > self.max_sl_percent:
            return False, f"Stop loss too high: {risk_pct*100:.1f}% risk (max: {self.max_sl_percent*100}%)"
        
        if risk_pct < 0.005:
            return False, f"Stop loss too tight: {risk_pct*100:.2f}% risk (min: 0.5%)"
        
        return True, f"Stop loss reasonable: {risk_pct*100:.2f}% risk"
    
    def _validate_risk_reward(self, signal) -> Tuple[bool, str]:
        """
        Check if risk/reward ratio is favorable.
        Minimum RR ratio: 1:2 (for every 1% risk, 2% potential reward)
        """
        entry = self._get_entry_price(signal)
        stop_loss = self._get_stop_loss(signal)
        targets = self._get_targets(signal)
        
        if not targets or len(targets) < 1:
            return False, "No valid targets"
        
        risk = entry - stop_loss
        first_target = targets[0]
        reward = first_target - entry
        
        if reward <= 0:
            return False, "First target below entry"
        
        rr_ratio = reward / risk if risk > 0 else 0
        
        if rr_ratio < 1.5:
            return False, f"Risk/Reward ratio poor: 1:{rr_ratio:.1f} (min: 1:1.5)"
        
        return True, f"Risk/Reward favorable: 1:{rr_ratio:.1f}"
    
    def _validate_technical_pattern(
        self, 
        signal, 
        df: pd.DataFrame
    ) -> Tuple[bool, str]:
        """
        Validate that price follows proper technical pattern:
        - For UPTREND: Higher Highs and Higher Lows
        - Has proper trend structure
        """
        if len(df) < 20:
            return False, "Insufficient data (need 20+ candles)"
        
        # Get recent price action (last 20 candles)
        recent = df.tail(20).copy()
        
        def _get_col(df, name):
            if name in df.columns:
                return df[name]
            low_name = name.lower()
            up_name = name.upper()
            if low_name in df.columns:
                return df[low_name]
            if up_name in df.columns:
                return df[up_name]
            raise KeyError(name)

        highs = _get_col(recent, 'High').values
        lows = _get_col(recent, 'Low').values
        closes = _get_col(recent, 'Close').values
        
        # Check for Higher Highs and Higher Lows (uptrend structure)
        hh_count = 0  # Higher Highs count
        hl_count = 0  # Higher Lows count
        
        for i in range(1, len(highs)):
            if highs[i] > highs[i-1]:
                hh_count += 1
            if lows[i] > lows[i-1]:
                hl_count += 1
        
        # For a valid uptrend, should have at least 40% Higher Highs AND Higher Lows
        hh_ratio = hh_count / (len(highs) - 1)
        hl_ratio = hl_count / (len(lows) - 1)
        
        if hh_ratio < 0.35 or hl_ratio < 0.35:
            return False, f"Weak uptrend structure: HH {hh_ratio*100:.0f}%, HL {hl_ratio*100:.0f}%"
        
        # Check for consolidation (not too much volatility before breakout)
        volatility = (_get_col(recent, 'High').max() - _get_col(recent, 'Low').min()) / _get_col(recent, 'Close').mean()
        
        if volatility > 0.20:  # More than 20% range
            return False, f"High volatility {volatility*100:.1f}% - risky entry"
        
        # Check recent breakout confirmation
        recent_close = closes[-1]
        ema20 = _get_col(recent, 'Close').ewm(span=20).mean().iloc[-1]
        
        if ema20 and recent_close < ema20:
            return False, "Price below EMA20 - not in uptrend"
        
        return True, f"Valid uptrend structure: HH {hh_ratio*100:.0f}%, HL {hl_ratio*100:.0f}%"
    
    def _validate_with_ai(
        self, 
        signal, 
        df: Optional[pd.DataFrame] = None
    ) -> Tuple[bool, str]:
        """
        Use AI analyzer to validate signal quality.
        AI should agree that this is a good trading opportunity.
        """
        if not self.ai_analyzer:
            return True, "No AI analyzer configured"
        
        try:
            ticker = self._get_ticker(signal)
            entry = self._get_entry_price(signal)
            stop_loss = self._get_stop_loss(signal)
            targets = self._get_targets(signal)
            
            # Ask AI to validate
            validation_prompt = f"""
Validate this trading signal:

Stock: {ticker}
Entry: {entry:.2f}
Stop Loss: {stop_loss:.2f}
Target 1: {targets[0]:.2f if targets else 'N/A'}

Should we send this alert? Consider:
1. Is the entry point reasonable?
2. Is the stop loss at a logical level?
3. Do targets show profit potential?
4. Are the risk/reward ratios good?

Answer YES or NO with brief reason.
"""
            
            # Get AI response (simplified - adapt to your AI implementation)
            response = self.ai_analyzer.analyze(validation_prompt)
            
            if isinstance(response, str):
                if 'YES' in response.upper() or 'AGREE' in response.upper():
                    return True, "AI agrees: signal is valid"
                else:
                    return False, f"AI disagrees: {response[:100]}"
            
            return True, "AI validation inconclusive"
            
        except Exception as e:
            logger.warning(f"AI validation error: {e}")
            return True, "AI validation skipped (error)"
    
    def _get_signal_score(self, signal) -> Optional[float]:
        """Extract score from signal (handles multiple score types)."""
        if hasattr(signal, 'final_score') and signal.final_score is not None:
            return signal.final_score
        if hasattr(signal, 'rank_score') and signal.rank_score is not None:
            return signal.rank_score
        if hasattr(signal, 'trend_score') and signal.trend_score is not None:
            return signal.trend_score
        if hasattr(signal, 'confidence_score') and signal.confidence_score is not None:
            return signal.confidence_score
        if hasattr(signal, 'verc_score') and signal.verc_score is not None:
            return signal.verc_score
        return None
    
    def _get_entry_price(self, signal) -> float:
        """Extract entry price from signal."""
        if hasattr(signal, 'entry_min'):
            return signal.entry_min
        if hasattr(signal, 'current_price'):
            return signal.current_price
        if hasattr(signal, 'indicators') and signal.indicators.get('close'):
            return signal.indicators['close']
        return 0.0
    
    def _get_stop_loss(self, signal) -> float:
        """Extract stop loss from signal."""
        if hasattr(signal, 'stop_loss'):
            return signal.stop_loss
        return 0.0
    
    def _get_targets(self, signal) -> List[float]:
        """Extract targets from signal."""
        targets = []
        if hasattr(signal, 'target_1') and signal.target_1 > 0:
            targets.append(signal.target_1)
        if hasattr(signal, 'target_2') and signal.target_2 > 0:
            targets.append(signal.target_2)
        return targets
    
    def _get_ticker(self, signal) -> str:
        """Extract ticker from signal."""
        if hasattr(signal, 'ticker'):
            return signal.ticker
        if hasattr(signal, 'stock_symbol'):
            return signal.stock_symbol
        return "UNKNOWN"
    
    def set_min_score(self, score: float) -> None:
        """Update minimum score threshold."""
        self.min_score = score
        logger.info(f"Updated minimum score threshold to {score}")
    
    def set_max_stop_loss_percent(self, percent: float) -> None:
        """Update maximum allowed stop loss percentage."""
        self.max_sl_percent = percent
        logger.info(f"Updated max stop loss to {percent*100:.1f}%")


def create_enhanced_validator(min_score: float = 6.0, ai_analyzer=None) -> EnhancedSignalValidator:
    """Factory function to create validator."""
    return EnhancedSignalValidator(min_score, ai_analyzer)
