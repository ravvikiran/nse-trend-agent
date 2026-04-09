"""
Consolidation Detector Module
Detects tight consolidation patterns followed by clean breakouts.
"""

import logging
from typing import Optional

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


def is_tight_consolidation(df: Optional[pd.DataFrame], lookback: int = 10, max_range_pct: float = 4.0) -> bool:
    """
    Check if price was in tight consolidation over the lookback period.
    
    Args:
        df: DataFrame with OHLC data (can be None)
        lookback: Number of periods to look back
        max_range_pct: Maximum allowed range as percentage (default 4%)
    
    Returns:
        True if in tight consolidation, False otherwise
    """
    if df is None or len(df) < lookback:
        return False
    
    required_cols = ['high', 'low']
    if not all(col in df.columns for col in required_cols):
        return False
    
    recent = df.tail(lookback)
    
    high = recent["high"].max()
    low = recent["low"].min()
    
    if low <= 0:
        return False
    
    range_pct = ((high - low) / low) * 100
    
    return range_pct <= max_range_pct


def is_valid_breakout(df: Optional[pd.DataFrame], lookback: int = 10) -> Optional[str]:
    """
    Check if there's a valid breakout from consolidation.
    
    Args:
        df: DataFrame with OHLC data (can be None)
        lookback: Number of periods for S/R calculation
    
    Returns:
        "BUY" for bullish breakout, "SELL" for bearish breakdown, None for no breakout
    """
    if df is None or len(df) < lookback:
        return None
    
    required_cols = ['high', 'low', 'close']
    if not all(col in df.columns for col in required_cols):
        return None
    
    recent = df.tail(lookback)
    
    resistance = recent["high"].max()
    support = recent["low"].min()
    
    last_close = df["close"].iloc[-1]
    
    if last_close > resistance:
        return "BUY"
    
    if last_close < support:
        return "SELL"
    
    return None


def is_strong_breakout(df: Optional[pd.DataFrame]) -> bool:
    """
    Check if breakout is strong (body ratio > 60% and strength > 1.5%).
    
    Args:
        df: DataFrame with OHLC data (can be None)
    
    Returns:
        True if strong breakout, False otherwise
    """
    if df is None or len(df) < 21:
        return False
    
    required_cols = ['open', 'high', 'low', 'close']
    if not all(col in df.columns for col in required_cols):
        return False
    
    candle = df.iloc[-1]
    
    body = abs(candle["close"] - candle["open"])
    candle_range = candle["high"] - candle["low"]
    
    if candle_range <= 0:
        return False
    
    body_ratio = body / candle_range
    
    high_20 = df["high"].rolling(20).max().iloc[-2]
    if high_20 <= 0:
        return False
    
    breakout_strength = ((candle["close"] - high_20) / candle["close"]) * 100
    
    is_strong = body_ratio > 0.6 and breakout_strength > 1.5
    
    if not is_strong:
        logger.debug(f"Weak breakout: body_ratio={body_ratio:.2f}, strength={breakout_strength:.2f}")
    
    return is_strong