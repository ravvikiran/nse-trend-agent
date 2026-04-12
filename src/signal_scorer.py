"""
Signal Scorer - Multi-Factor Signal Ranking
Ranks signals based on: trend + volume + breakout + context + momentum
Only takes signals above threshold score.
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ScoredSignal:
    signal: Dict[str, Any]
    total_score: float
    breakdown: Dict[str, float]


class SignalScorer:
    """
    Multi-factor signal scorer for ranking.
    
    Score = trend_score * w_trend + volume_score * w_volume + 
            breakout_score * w_breakout + context_score * w_context + 
            momentum_score * w_momentum
    
    Only signals above threshold are selected.
    """
    
    DEFAULT_WEIGHTS = {
        'trend': 0.25,
        'volume': 0.20,
        'breakout': 0.20,
        'context': 0.20,
        'momentum': 0.15
    }
    
    DEFAULT_THRESHOLD = 65.0
    
    def __init__(self, weights: Dict[str, float] = None, threshold: float = None):
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()
        self.threshold = threshold or self.DEFAULT_THRESHOLD
        
        logger.info(f"SignalScorer initialized: threshold={self.threshold}, weights={self.weights}")
    
    def score_signal(self, signal: Dict[str, Any], market_data: Dict[str, Any] = None) -> ScoredSignal:
        """
        Score a single signal.
        
        Args:
            signal: Signal data dict
            market_data: Optional market context data
            
        Returns:
            ScoredSignal with total score and breakdown
        """
        breakdown = {}
        
        breakdown['trend'] = self._score_trend(signal)
        breakdown['volume'] = self._score_volume(signal, market_data)
        breakdown['breakout'] = self._score_breakout(signal)
        breakdown['context'] = self._score_context(signal, market_data)
        breakdown['momentum'] = self._score_momentum(signal)
        
        total = sum(breakdown[k] * self.weights.get(k, 0) for k in breakdown)
        
        return ScoredSignal(
            signal=signal,
            total_score=round(total, 2),
            breakdown=breakdown
        )
    
    def _score_trend(self, signal: Dict[str, Any]) -> float:
        """Score trend alignment (0-100)."""
        direction = signal.get('direction', '').upper()
        ema_aligned = signal.get('ema_aligned', '')
        trend = signal.get('trend', 'SIDEWAYS')
        
        score = 50.0
        
        if direction == 'BUY':
            if ema_aligned in ['BULLISH', 'STRONG_BULLISH']:
                score += 30
            elif ema_aligned == 'NEUTRAL':
                score += 15
            
            if trend == 'BULLISH':
                score += 20
            elif trend == 'SIDEWAYS':
                score += 5
            else:
                score -= 10
        
        elif direction == 'SELL':
            if ema_aligned in ['BEARISH', 'STRONG_BEARISH']:
                score += 30
            elif ema_aligned == 'NEUTRAL':
                score += 15
            
            if trend == 'BEARISH':
                score += 20
            elif trend == 'SIDEWAYS':
                score += 5
            else:
                score -= 10
        
        return max(0, min(100, score))
    
    def _score_volume(self, signal: Dict[str, Any], market_data: Optional[Dict[str, Any]] = None) -> float:
        """Score volume confirmation (0-100)."""
        volume_ratio = signal.get('volume_ratio', 0)
        
        score = 50.0
        
        if volume_ratio >= 2.0:
            score += 40
        elif volume_ratio >= 1.5:
            score += 25
        elif volume_ratio >= 1.3:
            score += 15
        elif volume_ratio >= 1.0:
            score += 5
        else:
            score -= 20
        
        if market_data:
            market_vol = market_data.get('volume_ratio', 0)
            if market_vol > volume_ratio:
                score += 10
        
        return max(0, min(100, score))
    
    def _score_breakout(self, signal: Dict[str, Any]) -> float:
        """Score breakout quality (0-100)."""
        breakout_strength = signal.get('breakout_strength', 0)
        signal_type = signal.get('signal_type', '')
        
        score = 50.0
        
        if breakout_strength >= 8:
            score += 40
        elif breakout_strength >= 5:
            score += 25
        elif breakout_strength >= 3:
            score += 15
        elif breakout_strength >= 1:
            score += 5
        else:
            score -= 15
        
        if signal_type == 'BREAKOUT':
            score += 10
        elif signal_type == 'PULLBACK':
            score += 5
        
        return max(0, min(100, score))
    
    def _score_context(self, signal: Dict[str, Any], market_data: Optional[Dict[str, Any]] = None) -> float:
        """Score market context alignment (0-100)."""
        score = 50.0
        
        if market_data:
            market_trend = market_data.get('trend', 'SIDEWAYS')
            signal_direction = signal.get('direction', '').upper()
            
            if signal_direction == 'BUY' and market_trend == 'BULLISH':
                score += 30
            elif signal_direction == 'SELL' and market_trend == 'BEARISH':
                score += 30
            elif market_trend == 'SIDEWAYS':
                score += 10
            
            market_structure = market_data.get('structure', 'SIDEWAYS')
            if market_structure == 'TRENDING':
                score += 15
            elif market_structure == 'RANGE_BOUND':
                score -= 10
        
        rsi = signal.get('rsi', 50)
        if rsi:
            if 40 <= rsi <= 60:
                score += 10
            elif rsi < 30:
                score += 15
            elif rsi > 70:
                score += 15
        
        return max(0, min(100, score))
    
    def _score_momentum(self, signal: Dict[str, Any]) -> float:
        """Score momentum indicators (0-100)."""
        score = 50.0
        
        rsi = signal.get('rsi', 50)
        if rsi:
            if 45 <= rsi <= 55:
                score += 15
            elif (rsi < 40 and signal.get('direction') == 'BUY') or \
                 (rsi > 60 and signal.get('direction') == 'SELL'):
                score += 25
            elif (rsi > 70 and signal.get('direction') == 'BUY') or \
                 (rsi < 30 and signal.get('direction') == 'SELL'):
                score -= 20
        
        macd = signal.get('macd', 0)
        if macd:
            if signal.get('direction') == 'BUY' and macd > 0:
                score += 15
            elif signal.get('direction') == 'SELL' and macd < 0:
                score += 15
        
        atr_percent = signal.get('atr_percent', 0)
        if atr_percent:
            if 1.5 <= atr_percent <= 4.0:
                score += 15
            elif atr_percent > 5:
                score -= 10
        
        return max(0, min(100, score))
    
    def rank_signals(self, signals: List[Dict[str, Any]], market_data: Dict[str, Any] = None) -> List[ScoredSignal]:
        """
        Rank a list of signals, returning only those above threshold.
        
        Args:
            signals: List of signal dicts
            market_data: Optional market context
            
        Returns:
            List of ScoredSignal above threshold, sorted by score (descending)
        """
        scored = []
        
        for signal in signals:
            result = self.score_signal(signal, market_data)
            
            if result.total_score >= self.threshold:
                scored.append(result)
        
        scored.sort(key=lambda x: x.total_score, reverse=True)
        
        logger.info(f"Ranked {len(signals)} signals -> {len(scored)} above threshold {self.threshold}")
        
        return scored
    
    def filter_and_rank(self, signals: List[Dict[str, Any]], market_data: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Filter signals by threshold and return sorted list of signal dicts.
        
        Args:
            signals: List of signal dicts
            market_data: Optional market context
            
        Returns:
            List of signal dicts with added score fields, above threshold
        """
        scored = self.rank_signals(signals, market_data)
        
        result = []
        for s in scored:
            s.signal['_score'] = s.total_score
            s.signal['_score_breakdown'] = s.breakdown
            result.append(s.signal)
        
        return result
    
    def set_threshold(self, threshold: float) -> None:
        """Update threshold."""
        self.threshold = threshold
        logger.info(f"Updated threshold to {threshold}")
    
    def set_weights(self, weights: Dict[str, float]) -> bool:
        """Update weights (must sum to 1.0)."""
        total = sum(weights.values())
        if abs(total - 1.0) > 0.01:
            logger.warning(f"Weights must sum to 1.0, got {total}")
            return False
        
        self.weights.update(weights)
        logger.info(f"Updated weights: {self.weights}")
        return True
    
    def get_top_signals(self, signals: List[Dict[str, Any]], market_data: Dict[str, Any] = None, top_n: int = 5) -> List[Dict[str, Any]]:
        """
        Get top N signals above threshold.
        
        Args:
            signals: List of signals
            market_data: Optional market context
            top_n: Number of top signals to return
            
        Returns:
            Top N signals with scores
        """
        ranked = self.filter_and_rank(signals, market_data)
        return ranked[:top_n]


def create_signal_scorer(weights: Dict[str, float] = None, threshold: float = None) -> SignalScorer:
    """Factory function to create SignalScorer."""
    return SignalScorer(weights, threshold)