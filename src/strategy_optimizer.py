"""
Strategy Performance Tracker
Tracks performance metrics per strategy (TREND, VERC, MTF).

FIXES APPLIED:
  - adapt_filters_based_on_performance(): new method that RELAXES filters
    when win rate improves, preventing permanent over-tightening.
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
        'atr_min': 0.1,
        'breakout_strength_min': 0.0
    }

    FILTER_DEFAULTS = {
        'volume_ratio_min': 1.5,
        'rsi_max': 65,
        'atr_min': 0.5,
        'breakout_strength_min': 0.0,
    }

    TIMEOUT_PENALTY_RR = -0.5
    
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
        
        self._load_weights()
        self._load_filters()
        
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
            except (ValueError, TypeError) as e:
                logger.debug(f"Error calculating holding time: {e}")
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
            score = stats.get('weighted_score', self._calculate_performance_score(stats))
            
            if trade_count < self.min_trades or score < self.score_threshold:
                continue
            
            current_weight = self.strategy_weights.get(strategy, 0.5)
            
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
        
        total = sum(self.strategy_weights.values())
        if total > 0:
            for k in self.strategy_weights:
                self.strategy_weights[k] /= total
        
        if changes:
            self._save_weights()
            logger.info(f"Auto-optimization changes: {changes}")
        
        return changes
    
    def evaluate(self) -> Dict[str, Any]:
        """
        Evaluate trade journal and auto-optimize.
        Alias for auto_optimize() to provide cleaner API.
        
        - If win_rate < 40%: decrease strategy weight, increase filter strictness
        - If win_rate > 60%: increase strategy weight, relax filters
        """
        return self.auto_optimize()
    
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
                    self.FILTER_FLOORS['rsi_max'],
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
                    self.FILTER_FLOORS.get('atr_min', 0.1),
                    current - 0.1
                )
                if new_value != current:
                    logger.info(f"Adaptive filter: atr_min {current} → {new_value}")
                    self.adaptive_filters['atr_min'] = new_value
        
        if issues:
            self._save_filters()
            logger.info(f"Adapted filters: {self.adaptive_filters}")
        
        return self.adaptive_filters.copy()

    def adapt_filters_based_on_performance(self) -> Dict[str, Any]:
        """
        NEW (FIX): Relax filters when overall win rate is healthy.
        Prevents permanent over-tightening after a bad market period.
        Relaxation moves each filter halfway back toward its default value.
        Only runs when enough trades are available.
        """
        all_stats = self.get_all_strategy_stats()
        closed_counts = [s.get('trades', 0) for s in all_stats.values()]
        if sum(closed_counts) < self.min_trades:
            return self.adaptive_filters.copy()

        win_rates = [s.get('win_rate', 0) for s in all_stats.values() if s.get('trades', 0) >= 5]
        if not win_rates:
            return self.adaptive_filters.copy()

        avg_win_rate = sum(win_rates) / len(win_rates)
        changes = []

        if avg_win_rate > 60:
            for key, default_val in self.FILTER_DEFAULTS.items():
                current = self.adaptive_filters.get(key, default_val)
                floor = self.FILTER_FLOORS.get(key, 0)
                if key == 'rsi_max':
                    if current < default_val:
                        new_val = round(min(default_val, current + (default_val - current) * 0.5), 2)
                        if new_val != current:
                            self.adaptive_filters[key] = new_val
                            changes.append(f"{key}: {current} → {new_val} (win_rate={avg_win_rate:.1f}%)")
                else:
                    if current > default_val:
                        new_val = round(max(floor, current - (current - default_val) * 0.5), 3)
                        if new_val != current:
                            self.adaptive_filters[key] = new_val
                            changes.append(f"{key}: {current} → {new_val} (win_rate={avg_win_rate:.1f}%)")

            if changes:
                self._save_filters()
                logger.info(f"Filter relaxation (win_rate={avg_win_rate:.1f}%): {changes}")

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
                    self.FILTER_FLOORS['rsi_max'],
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
        
        breakout_value = breakout_strength if breakout_strength > 1 else breakout_strength * 100
        breakout_min = self.adaptive_filters.get('breakout_strength_min', 0.0)
        if breakout_min > 0 and breakout_value < breakout_min:
            reasons.append(f"Breakout strength below threshold ({breakout_value:.1f}% < {breakout_min:.1f}%)")
        
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
    
    def _load_filters(self) -> None:
        """Load adaptive filters from file."""
        filepath = os.path.join(self.data_dir, 'adaptive_filters.json')
        try:
            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    data = json.load(f)
                    if 'filters' in data:
                        self.adaptive_filters.update(data['filters'])
                    logger.info(f"Loaded filters from {filepath}")
        except Exception as e:
            logger.error(f"Error loading filters: {e}")
    
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

    def get_failure_patterns(self) -> Dict[str, Any]:
        """
        Extract patterns from losing trades to identify what fails most.
        
        Returns:
            Dict with avg_rsi, avg_volume, avg_breakout_strength, etc.
        """
        closed = self.trade_journal.get_closed_trades(200)
        losses = [t for t in closed if t.get('outcome') in ['LOSS', 'TIMEOUT']]
        
        if not losses:
            return {
                'avg_rsi': 0,
                'avg_volume_ratio': 0,
                'avg_breakout_strength': 0,
                'atr_avg': 0,
                'loss_count': 0
            }
        
        rsi_values = [t.get('rsi', 0) for t in losses if t.get('rsi')]
        volume_values = [t.get('volume_ratio', 0) for t in losses if t.get('volume_ratio')]
        breakout_values = [t.get('breakout_strength', 0) for t in losses if t.get('breakout_strength')]
        atr_values = [t.get('atr', 0) for t in losses if t.get('atr')]
        
        return {
            'avg_rsi': round(sum(rsi_values) / len(rsi_values), 2) if rsi_values else 0,
            'avg_volume_ratio': round(sum(volume_values) / len(volume_values), 2) if volume_values else 0,
            'avg_breakout_strength': round(sum(breakout_values) / len(breakout_values), 3) if breakout_values else 0,
            'atr_avg': round(sum(atr_values) / len(atr_values), 2) if atr_values else 0,
            'loss_count': len(losses)
        }

    def detect_market_condition(
        self,
        ema_20: float,
        ema_50: float,
        atr: float,
        nifty_direction: Optional[str] = None
    ) -> str:
        """
        Auto-detect market condition using EMA spread and ATR.
        
        Args:
            ema_20: 20-period EMA
            ema_50: 50-period EMA
            atr: Average True Range
            nifty_direction: Optional NIFTY direction for confirmation
            
        Returns:
            'TRENDING' or 'SIDEWAYS'
        """
        if ema_20 <= 0 or ema_50 <= 0:
            return self._current_market_condition
        
        spread = abs(ema_20 - ema_50) / ema_50
        
        if spread > 0.02 and atr > 1.0:
            condition = 'TRENDING'
        else:
            condition = 'SIDEWAYS'
        
        if nifty_direction and nifty_direction != 'SIDEWAYS':
            if nifty_direction == 'BEARISH':
                condition = 'SIDEWAYS'
        
        self._current_market_condition = condition
        return condition

    def calculate_timeout_penalty_rr(self) -> float:
        """Get penalty RR for TIMEOUT trades."""
        return self.TIMEOUT_PENALTY_RR

    def adapt_filters_from_failure_patterns(self) -> Dict[str, Any]:
        """
        Automatically adapt filters based on failure patterns extracted from losing trades.
        
        Uses get_failure_patterns() to identify what parameters correlate with losses,
        then tightens/adjusts adaptive filters accordingly.
        
        Returns:
            Updated filter values with explanation of changes
        """
        patterns = self.get_failure_patterns()
        
        if patterns.get('loss_count', 0) < 10:
            return self.adaptive_filters.copy()
        
        changes = []
        
        avg_rsi = patterns.get('avg_rsi', 0)
        if avg_rsi > 65:
            current = self.adaptive_filters['rsi_max']
            new_value = max(self.FILTER_FLOORS['rsi_max'], current - 5)
            if new_value != current:
                self.adaptive_filters['rsi_max'] = new_value
                changes.append(f"rsi_max: {current} → {new_value} (avg_rsi in losses: {avg_rsi})")
        
        avg_volume = patterns.get('avg_volume_ratio', 0)
        if avg_volume < 1.8:
            current = self.adaptive_filters['volume_ratio_min']
            new_value = min(self.FILTER_CAPS['volume_ratio_min'], current + 0.2)
            if new_value != current:
                self.adaptive_filters['volume_ratio_min'] = new_value
                changes.append(f"volume_ratio_min: {current} → {new_value} (avg_volume in losses: {avg_volume})")
        
        avg_breakout = patterns.get('avg_breakout_strength', 0)
        if avg_breakout < 0.05:
            current = self.adaptive_filters['breakout_strength_min']
            new_value = min(self.FILTER_CAPS['breakout_strength_min'], current + 0.01)
            if new_value != current:
                self.adaptive_filters['breakout_strength_min'] = new_value
                changes.append(f"breakout_strength_min: {current} → {new_value} (avg_breakout in losses: {avg_breakout})")
        
        if changes:
            self._save_filters()
            logger.info(f"Failure pattern adaptations: {changes}")

        self.adapt_filters_based_on_performance()

        return self.adaptive_filters.copy()
    
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
            'filter_floors': self.FILTER_FLOORS,
            'filter_defaults': self.FILTER_DEFAULTS,
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


class StrategyOptimizer:
    """
    Auto-optimization based on journal learning.
    Evaluates recent trades and adjusts strategy weights and filters.
    """
    
    def __init__(self, trade_journal):
        self.trade_journal = trade_journal
    
    def evaluate(self):
        """
        Evaluate recent trades and auto-optimize.
        - If win_rate < 40%: decrease strategy weight, increase filter strictness
        - If win_rate > 60%: increase strategy weight, relax filters
        """
        closed_trades = self.trade_journal.get_closed_trades(limit=50)
        
        if len(closed_trades) < 20:
            return
        
        wins = [t for t in closed_trades if t.get('outcome') == 'WIN']
        losses = [t for t in closed_trades if t.get('outcome') in ['LOSS', 'TIMEOUT']]
        
        total = len(closed_trades)
        win_rate = (len(wins) / total * 100) if total > 0 else 0
        
        logger.info(f"Performance evaluation: {len(wins)} wins, {len(losses)} losses, win_rate: {win_rate:.1f}%")
        
        if win_rate < 40:
            logger.warning("Win rate below 40% - increasing filter strictness")
            self._increase_strictness()
        elif win_rate > 60:
            logger.info("Win rate above 60% - relaxing filters slightly")
            self._relax_filters()
    
    def _increase_strictness(self):
        """Increase filter strictness when performance is poor."""
        pass
    
    def _relax_filters(self):
        """Relax filters when performance is good."""
        pass