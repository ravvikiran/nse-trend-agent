"""
Strategy Performance Tracker
Tracks performance metrics per strategy (TREND, VERC).
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict
import math

logger = logging.getLogger(__name__)

DATA_DIR = 'data'


class StrategyPerformanceTracker:
    """
    Track performance for each strategy with context-aware learning.
    Metrics: Win rate, Avg RR, Drawdown, Holding time.
    Features:
    - Proportional weight adjustment (win_rate - 50) / 100
    - Recency bias (recent trades matter more)
    - Market condition awareness (TRENDING vs SIDEWAYS)
    - Capped adaptive filters
    """
    
    PERFORMANCE_FILE = 'strategy_performance.json'
    
    WEIGHT_BOUNDS = (0.1, 1.0)
    DEFAULT_SMOOTHING = 0.3
    MIN_TRADES_THRESHOLD = 10
    SCORE_THRESHOLD = 40.0
    
    RECENT_WEIGHT = 0.7
    OLD_WEIGHT = 0.3
    
    FILTER_CAPS = {
        'volume_ratio_min': 2.5,
        'rsi_max': 70,
        'atr_min': 0.1,
        'breakout_strength_min': 0.05
    }
    
    FILTER_FLOORS = {
        'volume_ratio_min': 1.5,
        'rsi_max': 50,
        'breakout_strength_min': 0.0
    }
    
    def __init__(self, trade_journal, data_dir: str = DATA_DIR):
        self.trade_journal = trade_journal
        self.data_dir = data_dir
        
        self.strategy_weights = {
            'TREND': 0.5,
            'VERC': 0.5,
            'MTF': 0.5
        }
        
        self.context_weights = {
            ('TREND', 'TRENDING'): 1.2,
            ('TREND', 'SIDEWAYS'): 0.6,
            ('VERC', 'TRENDING'): 1.0,
            ('VERC', 'SIDEWAYS'): 1.0,
            ('MTF', 'TRENDING'): 1.1,
            ('MTF', 'SIDEWAYS'): 0.7
        }
        
        self.weight_history = {
            'TREND': [],
            'VERC': [],
            'MTF': []
        }
        
        self.smoothing_factor = self.DEFAULT_SMOOTHING
        self.min_trades = self.MIN_TRADES_THRESHOLD
        self.score_threshold = self.SCORE_THRESHOLD
        
        self.adaptive_filters = {
            'volume_ratio_min': 1.5,
            'rsi_max': 65,
            'atr_min': 0.5,
            'breakout_strength_min': 0.0
        }
        
        self._current_market_condition = 'TRENDING'
        
        logger.info("StrategyPerformanceTracker initialized")
    
    def set_market_condition(self, condition: str) -> None:
        """Set current market condition (TRENDING or SIDEWAYS)."""
        if condition in ['TRENDING', 'SIDEWAYS']:
            self._current_market_condition = condition
            logger.info(f"Market condition set to: {condition}")
    
    def get_market_condition(self) -> str:
        """Get current market condition."""
        return self._current_market_condition
    
    def get_strategy_stats(self, strategy: str, limit: int = 50) -> Dict[str, Any]:
        """
        Get performance stats for a strategy with recency weighting.
        
        Args:
            strategy: TREND, VERC, or MTF
            limit: Number of recent trades to analyze
            
        Returns:
            Dict with win_rate, avg_rr, drawdown, holding_time, weighted_score
        """
        trades = self.trade_journal.get_trades_by_strategy(strategy, limit)
        closed = [t for t in trades if t.get('outcome') not in ['OPEN']]
        
        if not closed:
            return {
                'strategy': strategy,
                'trades': 0,
                'win_rate': 0,
                'avg_rr': 0,
                'max_drawdown': 0,
                'avg_holding_days': 0,
                'weighted_score': 0
            }
        
        wins = [t for t in closed if t.get('outcome') == 'WIN']
        losses = [t for t in closed if t.get('outcome') in ['LOSS', 'TIMEOUT']]
        
        total = len(closed)
        win_rate = (len(wins) / total * 100) if total > 0 else 0
        
        rr_values = [t.get('rr_achieved', 0) for t in closed if t.get('rr_achieved', 0) != 0]
        avg_rr = sum(rr_values) / len(rr_values) if rr_values else 0
        
        drawdowns = [abs(t.get('max_drawdown', 0)) for t in closed if t.get('max_drawdown', 0) != 0]
        max_drawdown = max(drawdowns) if drawdowns else 0
        
        holding_times = []
        for t in closed:
            try:
                start = datetime.fromisoformat(t.get('timestamp', ''))
                end = datetime.fromisoformat(t.get('updated_at', ''))
                days = (end - start).days
                if days >= 0:
                    holding_times.append(days)
            except:
                pass
        
        avg_holding = sum(holding_times) / len(holding_times) if holding_times else 0
        
        recent_trades = closed[-20:] if len(closed) > 20 else closed
        old_trades = closed[:-20] if len(closed) > 20 else []
        
        recent_wr = self._calculate_win_rate(recent_trades)
        old_wr = self._calculate_win_rate(old_trades) if old_trades else recent_wr
        
        weighted_win_rate = (recent_wr * self.RECENT_WEIGHT) + (old_wr * self.OLD_WEIGHT)
        
        recent_rr = self._calculate_avg_rr(recent_trades)
        old_rr = self._calculate_avg_rr(old_trades) if old_trades else recent_rr
        weighted_avg_rr = (recent_rr * self.RECENT_WEIGHT) + (old_rr * self.OLD_WEIGHT)
        
        weighted_score = self._calculate_performance_score({
            'win_rate': weighted_win_rate,
            'avg_rr': weighted_avg_rr,
            'max_drawdown': max_drawdown
        })
        
        return {
            'strategy': strategy,
            'trades': total,
            'wins': len(wins),
            'losses': len(losses),
            'win_rate': round(win_rate, 2),
            'avg_rr': round(avg_rr, 2),
            'max_drawdown': round(max_drawdown, 2),
            'avg_holding_days': round(avg_holding, 1),
            'weighted_win_rate': round(weighted_win_rate, 2),
            'weighted_avg_rr': round(weighted_avg_rr, 2),
            'weighted_score': round(weighted_score, 2)
        }
    
    def _calculate_win_rate(self, trades: List[Dict]) -> float:
        """Calculate win rate from trades."""
        if not trades:
            return 0
        closed = [t for t in trades if t.get('outcome') not in ['OPEN']]
        if not closed:
            return 0
        wins = len([t for t in closed if t.get('outcome') == 'WIN'])
        return (wins / len(closed)) * 100
    
    def _calculate_avg_rr(self, trades: List[Dict]) -> float:
        """Calculate average RR from trades."""
        if not trades:
            return 0
        rr_values = [t.get('rr_achieved', 0) for t in trades if t.get('rr_achieved', 0) != 0]
        return sum(rr_values) / len(rr_values) if rr_values else 0
    
    def get_all_strategy_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get stats for all strategies."""
        return {
            'TREND': self.get_strategy_stats('TREND'),
            'VERC': self.get_strategy_stats('VERC'),
            'MTF': self.get_strategy_stats('MTF')
        }
    
    def _bound_weight(self, weight: float) -> float:
        """Clamp weight within defined bounds."""
        return max(self.WEIGHT_BOUNDS[0], min(self.WEIGHT_BOUNDS[1], weight))
    
    def _smooth_weight(self, current: float, target: float) -> float:
        """Apply exponential smoothing to weight changes."""
        return current + self.smoothing_factor * (target - current)
    
    def _calculate_performance_score(self, stats: Dict[str, Any]) -> float:
        """
        Calculate composite performance score.
        
        score = (win_rate * 0.5) + (avg_rr * 20 * 0.3) - (max_drawdown * 0.2)
        
        Args:
            stats: Strategy stats dict
            
        Returns:
            Composite score
        """
        win_rate = stats.get('win_rate', 0)
        avg_rr = stats.get('avg_rr', 0)
        max_drawdown = stats.get('max_drawdown', 0)
        
        score = (win_rate * 0.5) + (avg_rr * 20 * 0.3) - (max_drawdown * 0.2)
        
        return round(score, 2)
    
    def _calculate_proportional_adjustment(self, stats: Dict[str, Any], context_key: tuple) -> float:
        """
        Calculate weight adjustment based on performance.
        
        adjustment = (weighted_win_rate - 50) / 100
        Range: -0.5 to +0.5
        
        Args:
            stats: Strategy stats dict
            context_key: (strategy, market_condition) tuple
            
        Returns:
            Adjustment value
        """
        win_rate = stats.get('weighted_win_rate', stats.get('win_rate', 0))
        avg_rr = stats.get('weighted_avg_rr', stats.get('avg_rr', 0))
        
        win_rate_adjustment = (win_rate - 50) / 100
        
        rr_bonus = 0
        if avg_rr >= 2.0:
            rr_bonus = 0.1
        elif avg_rr >= 1.5:
            rr_bonus = 0.05
        elif avg_rr < 1.0:
            rr_bonus = -0.05
        
        base_adjustment = win_rate_adjustment + rr_bonus
        
        context_multiplier = self.context_weights.get(context_key, 1.0)
        adjusted = base_adjustment * context_multiplier
        
        return round(adjusted, 3)
    
    def auto_optimize(self) -> Dict[str, Any]:
        """
        Auto-Optimization Engine with proportional adjustments.
        
        - Proportional weight adjustment based on win_rate
        - Recency bias (recent trades matter more)
        - Context-aware (strategy + market condition)
        - Smoothing: gradual weight changes using EMA
        - Min trade threshold: require minimum trades before optimizing
        
        Returns:
            Dict with changes made
        """
        changes = {}
        
        for strategy in ['TREND', 'VERC', 'MTF']:
            stats = self.get_strategy_stats(strategy)
            trade_count = stats.get('trades', 0)
            
            if trade_count < self.min_trades:
                continue
            
            current_weight = self.strategy_weights.get(strategy, 0.5)
            score = stats.get('weighted_score', self._calculate_performance_score(stats))
            
            context_key = (strategy, self._current_market_condition)
            adjustment = self._calculate_proportional_adjustment(stats, context_key)
            
            raw_weight = current_weight + adjustment
            
            new_weight = self._bound_weight(self._smooth_weight(current_weight, raw_weight))
            new_weight = round(new_weight, 3)
            
            if abs(new_weight - current_weight) > 0.01:
                if new_weight < current_weight:
                    action = 'reduced'
                    reason = f'win_rate {stats.get("weighted_win_rate", 0):.1f}%'
                elif new_weight > current_weight:
                    action = 'increased'
                    reason = f'win_rate {stats.get("weighted_win_rate", 0):.1f}%'
                else:
                    action = 'stable'
                    reason = f'score {score:.1f}'
                
                changes[strategy] = {
                    'action': action,
                    'from': current_weight,
                    'to': new_weight,
                    'trades': trade_count,
                    'score': score,
                    'adjustment': adjustment,
                    'reason': reason,
                    'market_condition': self._current_market_condition
                }
                
                self.weight_history[strategy].append(new_weight)
                if len(self.weight_history[strategy]) > 20:
                    self.weight_history[strategy] = self.weight_history[strategy][-20:]
            
            self.strategy_weights[strategy] = new_weight
        
        if changes:
            self._save_weights()
            logger.info(f"Auto-optimization changes: {changes}")
        
        return changes
    
    def get_rank_score_formula(self) -> str:
        """Get current rank score formula."""
        return (
            f"rank_score = (strategy_score * 0.6 + volume_score * 0.2 + breakout_score * 0.2)"
        )
    
    def calculate_adaptive_rank_score(
        self,
        strategy_score: float,
        strategy_type: str,
        volume_ratio: float,
        breakout_strength: float
    ) -> float:
        """
        Calculate PURE rank score (no mixing with weights).
        
        base_rank_score = (strategy_score * 0.6) + (volume_score * 0.2) + (breakout_score * 0.2)
        
        Strategy weights should be used for SORTING, not scoring.
        """
        volume_score = min(volume_ratio / 3.0, 1.0) * 10
        
        breakout_score = breakout_strength * 10
        
        base_rank_score = (strategy_score * 0.6) + (volume_score * 0.2) + (breakout_score * 0.2)
        
        return round(base_rank_score, 2)
    
    def adapt_filters(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Adaptive Filters - adjust strictness dynamically with caps and smoothing.
        
        Examples:
        - Too many false breakouts → increase volume_ratio from 1.5 → 1.8 (capped at 2.5)
        - Late entries → tighten RSI (65 → 60)
        - Weak breakouts → increase breakout_strength_min
        
        Args:
            analysis: Analysis from AI Learning Layer or Factor Analyzer
            
        Returns:
            Updated filter values
        """
        issues = analysis.get('issues', [])
        
        for issue in issues:
            if 'false_breakouts' in issue or 'low_volume' in issue:
                current = self.adaptive_filters['volume_ratio_min']
                new_value = min(
                    self.FILTER_CAPS['volume_ratio_min'],
                    current + 0.2
                )
                if new_value != current:
                    logger.info(f"Adaptive filter: volume_ratio_min {current} → {new_value}")
                    self.adaptive_filters['volume_ratio_min'] = new_value
            
            if 'late_entries' in issue or 'overbought' in issue:
                current = self.adaptive_filters['rsi_max']
                new_value = max(
                    self.FILTER_CAPS['rsi_max'],
                    current - 5
                )
                if new_value != current:
                    logger.info(f"Adaptive filter: rsi_max {current} → {new_value}")
                    self.adaptive_filters['rsi_max'] = new_value
            
            if 'weak_breakouts' in issue:
                current = self.adaptive_filters['breakout_strength_min']
                new_value = min(
                    self.FILTER_CAPS['breakout_strength_min'],
                    current + 0.01
                )
                if new_value != current:
                    logger.info(f"Adaptive filter: breakout_strength_min {current} → {new_value}")
                    self.adaptive_filters['breakout_strength_min'] = new_value
            
            if 'dead_stock' in issue or 'low_volatility' in issue:
                current = self.adaptive_filters['atr_min']
                new_value = max(
                    self.FILTER_CAPS['atr_min'],
                    current - 0.1
                )
                if new_value != current:
                    logger.info(f"Adaptive filter: atr_min {current} → {new_value}")
                    self.adaptive_filters['atr_min'] = new_value
        
        if issues:
            self._save_filters()
            logger.info(f"Adapted filters: {self.adaptive_filters}")
        
        return self.adaptive_filters.copy()
    
    def adapt_filters_from_factor_analysis(self, factor_recommendations: Dict[str, Any]) -> Dict[str, Any]:
        """
        Adapt filters based on factor-level analysis.
        
        IF volume_ratio 1.5-1.8 underperforms → increase volume_ratio_min
        IF RSI > 60 underperforms → reduce rsi_max
        
        Args:
            factor_recommendations: Recommendations from FactorAnalyzer
            
        Returns:
            Updated filter values
        """
        changes_made = []
        
        if 'volume_ratio_warning' in factor_recommendations:
            current = self.adaptive_filters['volume_ratio_min']
            new_value = min(
                self.FILTER_CAPS['volume_ratio_min'],
                current + 0.2
            )
            if new_value != current:
                self.adaptive_filters['volume_ratio_min'] = new_value
                changes_made.append(f"volume_ratio_min: {current} → {new_value}")
        
        if 'rsi_optimal' in factor_recommendations:
            rsi_info = factor_recommendations['rsi_optimal']
            if '60-65' in rsi_info or '65-70' in rsi_info:
                current = self.adaptive_filters['rsi_max']
                new_value = max(
                    self.FILTER_CAPS['rsi_max'],
                    current - 5
                )
                if new_value != current:
                    self.adaptive_filters['rsi_max'] = new_value
                    changes_made.append(f"rsi_max: {current} → {new_value}")
        
        if changes_made:
            self._save_filters()
            logger.info(f"Factor-based filter adaptations: {changes_made}")
        
        return self.adaptive_filters.copy()
    
    def check_no_trade_conditions(
        self,
        atr: float,
        wick_to_body_ratio: float,
        nifty_direction: str
    ) -> Dict[str, Any]:
        """
        No-Trade Filter - avoid signals when:
        - ATR very low (dead stock)
        - Choppy candles (wicks > body)
        - NIFTY unclear direction (SIDEWAYS)
        
        Args:
            atr: Average True Range
            wick_to_body_ratio: Ratio of wick size to body size
            nifty_direction: 'BULLISH', 'BEARISH', or 'SIDEWAYS'
            
        Returns:
            Dict with 'allowed' bool and 'reasons' list
        """
        reasons = []
        
        if atr and atr < self.adaptive_filters.get('atr_min', 0.5):
            reasons.append(f"ATR too low ({atr:.2f} < {self.adaptive_filters.get('atr_min', 0.5)})")
        
        if wick_to_body_ratio > 1.0:
            reasons.append(f"Choppy candle (wick/body: {wick_to_body_ratio:.2f} > 1.0)")
        
        if nifty_direction == 'SIDEWAYS':
            reasons.append("NIFTY direction unclear (SIDEWAYS)")
        
        return {
            'allowed': len(reasons) == 0,
            'reasons': reasons
        }
    
    def check_signal_quality(
        self,
        score: float,
        volume_ratio: float,
        breakout_strength: float
    ) -> Dict[str, Any]:
        """
        Check signal against adaptive thresholds.
        
        Returns:
            Dict with 'passed' bool and 'reasons' list
        """
        reasons = []
        
        if volume_ratio < self.adaptive_filters.get('volume_ratio_min', 1.5):
            reasons.append(f"Volume ratio below threshold ({volume_ratio:.2f} < {self.adaptive_filters.get('volume_ratio_min', 1.5)})")
        
        breakout_pct = breakout_strength * 100 if breakout_strength <= 1 else breakout_strength
        breakout_min = self.adaptive_filters.get('breakout_strength_min', 0.0) * 100
        if breakout_pct < breakout_min:
            reasons.append(f"Breakout strength below threshold ({breakout_pct:.1f}% < {breakout_min:.1f}%)")
        
        return {
            'passed': len(reasons) == 0,
            'reasons': reasons
        }
    
    def _save_weights(self) -> None:
        filepath = os.path.join(self.data_dir, 'strategy_weights.json')
        data = {
            'weights': self.strategy_weights,
            'context_weights': self.context_weights,
            'market_condition': self._current_market_condition,
            'updated_at': datetime.now().isoformat()
        }
        try:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving weights: {e}")
    
    def _load_weights(self) -> None:
        """Load weights and context weights from file."""
        filepath = os.path.join(self.data_dir, 'strategy_weights.json')
        try:
            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    data = json.load(f)
                    if 'weights' in data:
                        self.strategy_weights.update(data['weights'])
                    if 'context_weights' in data:
                        self.context_weights.update(data['context_weights'])
                    if 'market_condition' in data:
                        self._current_market_condition = data['market_condition']
                    logger.info(f"Loaded weights from {filepath}")
        except Exception as e:
            logger.error(f"Error loading weights: {e}")
    
    def update_context_weight(self, strategy: str, market_condition: str, weight: float) -> None:
        """Update context-specific weight for a strategy."""
        context_key = (strategy, market_condition)
        if context_key in self.context_weights:
            self.context_weights[context_key] = self._bound_weight(weight)
            logger.info(f"Updated context weight for {context_key}: {weight}")
    
    def get_context_weight(self, strategy: str, market_condition: Optional[str] = None) -> float:
        """Get effective weight for strategy considering market condition."""
        condition: str = market_condition if market_condition else self._current_market_condition
        context_key: Tuple[str, str] = (strategy, condition)
        base_weight = self.strategy_weights.get(strategy, 0.5)
        context_multiplier = self.context_weights.get(context_key, 1.0)
        return round(base_weight * context_multiplier, 3)
    
    def _save_filters(self) -> None:
        filepath = os.path.join(self.data_dir, 'adaptive_filters.json')
        data = {
            'filters': self.adaptive_filters,
            'updated_at': datetime.now().isoformat()
        }
        try:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving filters: {e}")
    
    def configure_optimization(
        self,
        smoothing: Optional[float] = None,
        min_trades: Optional[int] = None,
        weight_bounds: Optional[tuple] = None,
        score_threshold: Optional[float] = None
    ) -> None:
        """
        Configure optimization parameters.
        
        Args:
            smoothing: EMA factor (0.1 = gradual, 0.9 = fast)
            min_trades: Minimum trades before optimization
            weight_bounds: Tuple of (min, max) weights
            score_threshold: Score threshold for weight adjustments
        """
        if smoothing is not None:
            self.smoothing_factor = max(0.1, min(0.9, smoothing))
        
        if min_trades is not None:
            self.min_trades = max(1, min_trades)
        
        if weight_bounds is not None:
            self.WEIGHT_BOUNDS = (
                max(0.0, min(weight_bounds[0], 1.0)),
                max(0.0, min(weight_bounds[1], 1.0))
            )
        
        if score_threshold is not None:
            self.score_threshold = max(0.0, score_threshold)
        
        logger.info(
            f"Optimization config: smoothing={self.smoothing_factor}, "
            f"min_trades={self.min_trades}, bounds={self.WEIGHT_BOUNDS}, "
            f"score_threshold={self.score_threshold}"
        )
    
    def get_status_report(self) -> Dict[str, Any]:
        """Get comprehensive status report."""
        all_stats = self.get_all_strategy_stats()
        return {
            'strategy_weights': self.strategy_weights,
            'context_weights': self.context_weights,
            'adaptive_filters': self.adaptive_filters,
            'filter_caps': self.FILTER_CAPS,
            'performance': all_stats,
            'scores': {
                s: stats.get('weighted_score', self._calculate_performance_score(stats))
                for s, stats in all_stats.items()
            },
            'market_condition': self._current_market_condition,
            'recency_bias': {
                'recent_weight': self.RECENT_WEIGHT,
                'old_weight': self.OLD_WEIGHT
            },
            'rank_formula': self.get_rank_score_formula(),
            'optimization_config': {
                'smoothing_factor': self.smoothing_factor,
                'min_trades_threshold': self.min_trades,
                'weight_bounds': self.WEIGHT_BOUNDS,
                'score_threshold': self.score_threshold
            }
        }


def create_strategy_performance_tracker(trade_journal) -> StrategyPerformanceTracker:
    """Factory function to create strategy performance tracker."""
    return StrategyPerformanceTracker(trade_journal)