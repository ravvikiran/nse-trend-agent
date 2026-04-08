"""
Market Context Engine
Detects NIFTY trend (BULLISH/BEARISH/SIDEWAYS) for context-aware filtering.
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

DATA_DIR = 'data'


class MarketContextEngine:
    """
    Market Context Detection Engine.
    Analyzes NIFTY to determine market regime.
    """
    
    CONTEXT_FILE = 'market_context.json'
    NIFTY_SYMBOL = '^NSEI'
    
    def __init__(self, data_fetcher=None, data_dir: str = DATA_DIR):
        self.data_fetcher = data_fetcher
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        
        self.current_context = 'SIDEWAYS'
        self.context_history = []
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
            except Exception as e:
                logger.error(f"Error loading market context: {e}")
    
    def _save_context(self) -> None:
        filepath = os.path.join(self.data_dir, self.CONTEXT_FILE)
        data = {
            'current_context': self.current_context,
            'history': self.context_history[-30:],
            'last_updated': datetime.now().isoformat()
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
            
            return {
                'close': df['close'].iloc[-1],
                'ema50': df['close'].ewm(span=50).mean().iloc[-1],
                'high': df['high'].tail(20).max(),
                'low': df['low'].tail(20).min(),
                'atr': self._calculate_atr(df)
            }
        except Exception as e:
            logger.error(f"Error fetching NIFTY data: {e}")
            return None
    
    def _calculate_atr(self, df, period: int = 14) -> float:
        """Calculate ATR for NIFTY."""
        try:
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
    
    def detect_context(self) -> str:
        """
        Detect current market context based on NIFTY.
        
        BULLISH: price > EMA50
        BEARISH: price < EMA50  
        SIDEWAYS: otherwise (price near EMA50 within range)
        
        Returns:
            Context string: BULLISH, BEARISH, or SIDEWAYS
        """
        nifty_data = self._fetch_nifty_data()
        
        if not nifty_data:
            logger.warning("Could not fetch NIFTY data, defaulting to SIDEWAYS")
            return 'SIDEWAYS'
        
        close = nifty_data.get('close', 0)
        ema50 = nifty_data.get('ema50', 0)
        atr = nifty_data.get('atr', 1)
        
        if ema50 <= 0:
            return 'SIDEWAYS'
        
        price_deviation = abs(close - ema50) / ema50 * 100
        
        if close > ema50 * 1.02:
            context = 'BULLISH'
        elif close < ema50 * 0.98:
            context = 'BEARISH'
        else:
            context = 'SIDEWAYS'
        
        if context != self.current_context:
            self.context_history.append({
                'from': self.current_context,
                'to': context,
                'price': close,
                'ema50': ema50,
                'timestamp': datetime.now().isoformat()
            })
            self.current_context = context
            self._save_context()
            logger.info(f"Market context changed: {context} (price: {close:.2f}, EMA50: {ema50:.2f})")
        
        return context
    
    def get_context(self) -> str:
        """Get current market context."""
        return self.current_context
    
    def apply_context_rules(self, signal: Any, base_score: float) -> Tuple[float, str]:
        """
        Apply market context rules to signal scoring.
        
        Rules:
        - IF NIFTY SIDEWAYS: reduce TREND score by -1
        - IF NIFTY BEARISH: reduce all bullish signals by -2
        
        Returns:
            Tuple of (adjusted_score, rejection_reason)
        """
        context = self.get_context()
        adjusted_score = base_score
        rejection_reason = ""
        
        strategy_type = getattr(signal, 'strategy_type', 'TREND')
        
        if context == 'SIDEWAYS' and strategy_type == 'TREND':
            adjusted_score -= 1.0
            rejection_reason = "NIFTY sideways - trend signals weakened"
        
        elif context == 'BEARISH':
            adjusted_score -= 2.0
            rejection_reason = "NIFTY bearish - all bullish signals reduced"
        
        return max(0, adjusted_score), rejection_reason
    
    def should_reject_signal(self, context: str) -> Tuple[bool, str]:
        """
        Determine if signal should be rejected based on market context.
        
        Returns:
            Tuple of (should_reject, reason)
        """
        if context == 'SIDEWAYS':
            return True, "NIFTY SIDEWAYS - no-trade zone"
        return False, ""
    
    def get_context_stats(self) -> Dict[str, Any]:
        """Get context statistics."""
        return {
            'current_context': self.current_context,
            'history_count': len(self.context_history),
            'recent_contexts': [h.get('to') for h in self.context_history[-5:]]
        }
    
    def force_context(self, context: str) -> None:
        """Manually set market context (for testing)."""
        if context in ['BULLISH', 'BEARISH', 'SIDEWAYS']:
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
            'close': nifty_data.get('close', 0),
            'ema50': nifty_data.get('ema50', 0),
            'atr': nifty_data.get('atr', 0),
            'high_20': nifty_data.get('high', 0),
            'low_20': nifty_data.get('low', 0)
        }


def create_market_context_engine(data_fetcher=None, data_dir: str = DATA_DIR) -> MarketContextEngine:
    """Factory function to create MarketContextEngine."""
    return MarketContextEngine(data_fetcher, data_dir)