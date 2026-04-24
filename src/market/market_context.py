"""
Market Context Engine
Detects NIFTY trend (BULLISH/BEARISH/SIDEWAYS) for context-aware filtering.
Enhanced with ATR-based detection, structure analysis, and regime classification.
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple, List

logger = logging.getLogger(__name__)

DATA_DIR = 'data'


class MarketContextEngine:
    """
    Market Context Detection Engine.
    Analyzes NIFTY to determine market regime.
    """
    
    CONTEXT_FILE = 'market_context.json'
    NIFTY_SYMBOL = '^NSEI'
    
    CONTEXT_TTL_MINUTES = 15
    VOLATILITY_LOW_MULTIPLIER = 0.5
    VOLATILITY_HIGH_MULTIPLIER = 1.5
    
    def __init__(self, data_fetcher=None, data_dir: str = DATA_DIR):
        self.data_fetcher = data_fetcher
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        
        self.current_context = 'SIDEWAYS'
        self.context_history = []
        self.last_context_update = None
        self.volatility_regime = 'NORMAL'
        self._load_context()
        
        logger.info("MarketContextEngine initialized")
    
    def _load_context(self) -> None:
        filepath = os.path.join(self.data_dir, self.CONTEXT_FILE)
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                    self.current_context = data.get('current_context', 'SIDEWAYS')
                    self.context_history = data.get('history', [])
                    self.last_context_update = data.get('last_updated')
                    self.volatility_regime = data.get('volatility_regime', 'NORMAL')
            except Exception as e:
                logger.error(f"Error loading market context: {e}")
    
    def _save_context(self) -> None:
        filepath = os.path.join(self.data_dir, self.CONTEXT_FILE)
        data = {
            'current_context': self.current_context,
            'history': self.context_history[-30:],
            'last_updated': datetime.now().isoformat(),
            'volatility_regime': self.volatility_regime
        }
        try:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving market context: {e}")
    
    def _fetch_nifty_data(self) -> Optional[Dict[str, Any]]:
        """Fetch NIFTY data for context analysis."""
        if not self.data_fetcher:
            logger.warning("No data fetcher available for market context")
            return None
        
        try:
            import pandas as pd
            ticker = self.data_fetcher.tickers.get('NIFTY', self.NIFTY_SYMBOL)
            df = self.data_fetcher.fetch_data(ticker, period='3mo', interval='1d')
            
            if df is None or df.empty:
                return None
            
            close = df['close'].iloc[-1]
            ema50 = df['close'].ewm(span=50).mean().iloc[-1]
            ema20 = df['close'].ewm(span=20).mean().iloc[-1]
            atr = self._calculate_atr(df)
            atr_percent = atr / close * 100 if close > 0 else 0
            
            high_20 = df['high'].tail(20).max()
            low_20 = df['low'].tail(20).min()
            
            ema_slope = ((ema50 - ema20) / ema20 * 100) if ema20 > 0 else 0
            
            avg_atr = self._calculate_avg_atr(df, lookback=20)
            volatility_regime = self._classify_volatility_regime(atr_percent, avg_atr)
            
            return {
                'close': close,
                'ema50': ema50,
                'ema20': ema20,
                'atr': atr,
                'atr_percent': atr_percent,
                'high_20': high_20,
                'low_20': low_20,
                'ema_slope': ema_slope,
                'volatility_regime': volatility_regime
            }
        except Exception as e:
            logger.error(f"Error fetching NIFTY data: {e}")
            return None
    
    def _calculate_atr(self, df, period: int = 14) -> float:
        """Calculate ATR for NIFTY."""
        try:
            import pandas as pd
            high = df['high']
            low = df['low']
            close = df['close']
            
            tr1 = high - low
            tr2 = abs(high - close.shift(1))
            tr3 = abs(low - close.shift(1))
            
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(window=period).mean().iloc[-1]
            
            return float(atr)
        except Exception:
            return 0.0
    
    def _calculate_avg_atr(self, df, lookback: int = 20) -> float:
        """Calculate average ATR over lookback period."""
        try:
            import pandas as pd
            high = df['high']
            low = df['low']
            close = df['close']
            
            tr1 = high - low
            tr2 = abs(high - close.shift(1))
            tr3 = abs(low - close.shift(1))
            
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            avg_tr = tr.rolling(window=lookback).mean().iloc[-1]
            
            return float(avg_tr)
        except Exception:
            return 0.0
    
    def _classify_volatility_regime(self, current_atr_percent: float, avg_atr_percent: float) -> str:
        """Classify volatility regime based on ATR."""
        if avg_atr_percent == 0:
            return 'NORMAL'
        
        ratio = current_atr_percent / avg_atr_percent if avg_atr_percent > 0 else 1.0
        
        if ratio < self.VOLATILITY_LOW_MULTIPLIER:
            return 'LOW'
        elif ratio > self.VOLATILITY_HIGH_MULTIPLIER:
            return 'HIGH'
        else:
            return 'NORMAL'
    
    def _detect_context_with_structure(self, nifty_data: Dict[str, Any]) -> Tuple[str, str]:
        """
        Detect market context using ATR-based detection and structure analysis.
        
        Returns:
            Tuple of (context, strength)
        """
        close = nifty_data.get('close', 0)
        ema50 = nifty_data.get('ema50', 0)
        atr = nifty_data.get('atr', 1)
        high_20 = nifty_data.get('high_20', 0)
        low_20 = nifty_data.get('low_20', 0)
        ema_slope = nifty_data.get('ema_slope', 0)
        volatility_regime = nifty_data.get('volatility_regime', 'NORMAL')
        
        if ema50 <= 0 or atr <= 0:
            return 'SIDEWAYS', 'WEAK'
        
        upper_bound = ema50 + (1.5 * atr)
        lower_bound = ema50 - (1.5 * atr)
        
        breakout_above = close > high_20 * 1.01
        breakout_below = close < low_20 * 0.99
        
        if breakout_above and close > ema50:
            context = 'STRONG_BULLISH'
            strength = 'STRONG'
        elif breakout_below and close < ema50:
            context = 'STRONG_BEARISH'
            strength = 'STRONG'
        elif close > upper_bound:
            context = 'BULLISH'
            strength = 'MODERATE'
        elif close < lower_bound:
            context = 'BEARISH'
            strength = 'MODERATE'
        elif volatility_regime == 'LOW':
            context = 'SIDEWAYS'
            strength = 'WEAK'
        else:
            if ema_slope > 0.5:
                context = 'BULLISH'
                strength = 'WEAK'
            elif ema_slope < -0.5:
                context = 'BEARISH'
                strength = 'WEAK'
            else:
                context = 'SIDEWAYS'
                strength = 'MODERATE'
        
        return context, strength
    
    def _get_context_persistence(self) -> int:
        """Get number of consecutive periods with same context."""
        if not self.context_history:
            return 1
        
        count = 1
        current = self.current_context
        
        for i in range(len(self.context_history) - 1, -1, -1):
            if self.context_history[i].get('to') == current:
                count += 1
            else:
                break
        
        return count
    
    def _detect_context_flip(self) -> bool:
        """Detect if context recently flipped (whipsaw)."""
        if len(self.context_history) < 2:
            return False
        
        last_two = self.context_history[-2:]
        if len(last_two) < 2:
            return False
        
        return last_two[0].get('from') == last_two[1].get('to')
    
    def _needs_update(self) -> bool:
        """Check if context needsupdate based on TTL."""
        if not self.last_context_update:
            return True
        
        try:
            last_update = datetime.fromisoformat(self.last_context_update)
            elapsed = datetime.now() - last_update
            return elapsed > timedelta(minutes=self.CONTEXT_TTL_MINUTES)
        except Exception:
            return True
    
    def detect_context(self, force_update: bool = False) -> str:
        """
        Detect current market context based on NIFTY.
        
        Uses ATR-based detection + structure analysis + volatility regime.
        
        Returns:
            Context string: STRONG_BULLISH, BULLISH, STRONG_BEARISH, BEARISH, or SIDEWAYS
        """
        if not force_update and not self._needs_update():
            return self.current_context
        
        nifty_data = self._fetch_nifty_data()
        
        if not nifty_data:
            logger.warning("Could not fetch NIFTY data, defaulting to SIDEWAYS")
            return 'SIDEWAYS'
        
        context, strength = self._detect_context_with_structure(nifty_data)
        self.volatility_regime = nifty_data.get('volatility_regime', 'NORMAL')
        
        base_context = context.split('_')[0] if '_' in context else context
        
        persistence = self._get_context_persistence()
        recent_flip = self._detect_context_flip()
        
        if recent_flip and persistence < 3:
            context = 'SIDEWAYS'
            logger.info(f"Context flip detected - defaulting to SIDEWAYS (whipsaw filter)")
        
        if context != self.current_context:
            self.context_history.append({
                'from': self.current_context,
                'to': context,
                'strength': strength,
                'persistence': persistence,
                'volatility': self.volatility_regime,
                'price': nifty_data.get('close', 0),
                'ema50': nifty_data.get('ema50', 0),
                'atr': nifty_data.get('atr', 0),
                'timestamp': datetime.now().isoformat()
            })
            self.current_context = context
            self.last_context_update = datetime.now().isoformat()
            self._save_context()
            logger.info(f"Market context changed: {context} (strength: {strength}, persistence: {persistence})")
        
        return context
    
    def get_context(self) -> str:
        """Get current market context."""
        return self.current_context
    
    def get_base_context(self) -> str:
        """Get base context without strength prefix."""
        if '_' in self.current_context:
            return self.current_context.split('_')[0]
        return self.current_context
    
    def apply_context_rules(self, signal: Any, base_score: float) -> Tuple[float, str]:
        """
        Apply market context rules to signal scoring.
        
        Rules:
        - IF SIDEWAYS and TREND strategy: reduce score
        - IF BEARISH: reduce LONG signals more
        - IF BULLISH: reduce SHORT signals more
        - IF STRONG contexts: apply stronger adjustments
        
        Returns:
            Tuple of (adjusted_score, rejection_reason)
        """
        context = self.get_context()
        base_ctx = self.get_base_context()
        adjusted_score = base_score
        rejection_reason = ""
        
        strategy_type = getattr(signal, 'strategy_type', 'TREND')
        signal_direction = getattr(signal, 'direction', 'LONG')
        
        is_strong = context.startswith('STRONG')
        strength_multiplier = 2.0 if is_strong else 1.0
        
        if base_ctx == 'SIDEWAYS':
            if strategy_type == 'TREND':
                return 0, "Hard reject - sideways market"
            else:
                adjusted_score -= 0.5
                rejection_reason = "NIFTY sideways - mean reversion allowed"
        
        elif base_ctx == 'BEARISH':
            if signal_direction == 'LONG':
                adjusted_score -= 2.0 * strength_multiplier
                rejection_reason = "NIFTY bearish - long signals penalized"
            elif signal_direction == 'SHORT':
                adjusted_score += 1.0 * strength_multiplier
                rejection_reason = "NIFTY bearish - short signals boosted"
            else:
                adjusted_score -= 2.0 * strength_multiplier
                rejection_reason = "NIFTY bearish - all directions penalized"
        
        elif base_ctx == 'BULLISH':
            if signal_direction == 'SHORT':
                adjusted_score -= 2.0 * strength_multiplier
                rejection_reason = "NIFTY bullish - short signals penalized"
            elif signal_direction == 'LONG':
                adjusted_score += 1.0 * strength_multiplier
                rejection_reason = "NIFTY bullish - long signals boosted"
            else:
                adjusted_score -= 2.0 * strength_multiplier
                rejection_reason = "NIFTY bullish - all directions penalized"
        
        if self.volatility_regime == 'HIGH':
            adjusted_score *= 0.6
            rejection_reason += " (HIGH volatility - score heavily reduced)"
        
        persistence = self._get_context_persistence()
        if persistence >= 5:
            adjusted_score *= 1.1
            rejection_reason += f" (context persistent {persistence} periods - score boosted)"
        
        return max(0, adjusted_score), rejection_reason
    
    def should_reject_signal(self, context: str) -> Tuple[bool, str]:
        """
        Determine if signal should be rejected based on market context.
        
        Returns:
            Tuple of (should_reject, reason)
        """
        base_ctx = self.get_base_context()
        
        if base_ctx == 'SIDEWAYS':
            return True, "SIDEWAYS market - capital destruction zone"
        
        return False, ""
    
    def get_context_stats(self) -> Dict[str, Any]:
        """Get context statistics."""
        recent_contexts = [h.get('to') for h in self.context_history[-5:]]
        return {
            'current_context': self.current_context,
            'base_context': self.get_base_context(),
            'history_count': len(self.context_history),
            'recent_contexts': recent_contexts,
            'persistence': self._get_context_persistence(),
            'volatility_regime': self.volatility_regime,
            'recent_flip': self._detect_context_flip()
        }
    
    def force_context(self, context: str) -> None:
        """Manually set market context (for testing)."""
        valid_contexts = ['STRONG_BULLISH', 'BULLISH', 'STRONG_BEARISH', 'BEARISH', 'SIDEWAYS']
        if context in valid_contexts:
            self.current_context = context
            self._save_context()
            logger.info(f"Market context manually set to: {context}")
    
    def get_nifty_indicators(self) -> Dict[str, Any]:
        """Get current NIFTY technical indicators."""
        nifty_data = self._fetch_nifty_data()
        
        if not nifty_data:
            return {'context': 'UNKNOWN'}
        
        return {
            'context': self.current_context,
            'base_context': self.get_base_context(),
            'close': nifty_data.get('close', 0),
            'ema50': nifty_data.get('ema50', 0),
            'ema20': nifty_data.get('ema20', 0),
            'atr': nifty_data.get('atr', 0),
            'atr_percent': nifty_data.get('atr_percent', 0),
            'high_20': nifty_data.get('high_20', 0),
            'low_20': nifty_data.get('low_20', 0),
            'ema_slope': nifty_data.get('ema_slope', 0),
            'volatility_regime': self.volatility_regime,
            'persistence': self._get_context_persistence()
        }


def create_market_context_engine(data_fetcher=None, data_dir: str = DATA_DIR) -> MarketContextEngine:
    """Factory function to create MarketContextEngine."""
    return MarketContextEngine(data_fetcher, data_dir)