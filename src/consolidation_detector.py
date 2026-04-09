"""
Consolidation Detector Module
Detects tight consolidation patterns followed by clean breakouts.
"""

import logging
from typing import Optional

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


def calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
    """Calculate Average True Range for volatility analysis."""
    if df is None or len(df) < period + 1:
        return 0.0
    
    required_cols = ['high', 'low']
    if not all(col in df.columns for col in required_cols):
        return 0.0
    
    high = df['high']
    low = df['low']
    close = df['close']
    
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(period).mean().iloc[-1]
    
    return atr if not pd.isna(atr) else 0.0


def is_tight_consolidation(
    df: Optional[pd.DataFrame],
    lookback: int = 10,
    max_range_pct: float = 4.0,
    max_atr_pct: float = 2.0,
    require_consistency: bool = True
) -> bool:
    """
    Check if price was in tight consolidation over the lookback period.
    
    Real consolidation = tight + flat + low volatility
    
    Args:
        df: DataFrame with OHLC data (can be None)
        lookback: Number of periods to look back
        max_range_pct: Maximum allowed range as percentage (default 4%)
        max_atr_pct: Maximum ATR as percentage of price (default 2%)
        require_consistency: Require last N candles to also be tight
    
    Returns:
        True if in tight consolidation, False otherwise
    """
    if df is None or len(df) < lookback:
        return False
    
    required_cols = ['high', 'low', 'close']
    if not all(col in df.columns for col in required_cols):
        return False
    
    close = df['close'].iloc[-1]
    if close <= 0:
        return False
    
    recent = df.tail(lookback)
    
    high = recent["high"].max()
    low = recent["low"].min()
    
    if low <= 0:
        return False
    
    range_pct = ((high - low) / low) * 100
    
    if range_pct > max_range_pct:
        logger.debug(f"Range too wide: {range_pct:.2f}%")
        return False
    
    atr = calculate_atr(df.tail(lookback + 14))
    atr_pct = (atr / close) * 100
    
    if atr_pct > max_atr_pct:
        logger.debug(f"ATR too high: {atr_pct:.2f}%")
        return False
    
    if require_consistency:
        last_5_ranges = []
        for i in range(-min(5, lookback), 0):
            window = df.iloc[i-5:i] if i > -5 else df.iloc[i:]
            if len(window) < 5:
                continue
            h = window["high"].max()
            l = window["low"].min()
            if l > 0:
                r = ((h - l) / l) * 100
                last_5_ranges.append(r)
        
        if last_5_ranges and any(r > max_range_pct * 1.5 for r in last_5_ranges):
            logger.debug(f"Inconsistent range: {last_5_ranges}")
            return False
    
    return True


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