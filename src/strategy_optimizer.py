"""
Strategy Performance Tracker
Tracks performance metrics per strategy (TREND, VERC).
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from collections import defaultdict
import math

logger = logging.getLogger(__name__)

DATA_DIR = 'data'


class StrategyPerformanceTracker:
    """
    Track performance for each strategy (last 50 trades).
    Metrics: Win rate, Avg RR, Drawdown, Holding time.
    """
    
    PERFORMANCE_FILE = 'strategy_performance.json'
    
    WEIGHT_BOUNDS = (0.1, 1.0)
    DEFAULT_SMOOTHING = 0.3
    MIN_TRADES_THRESHOLD = 10
    SCORE_THRESHOLD = 40.0
    
    def __init__(self, trade_journal, data_dir: str = DATA_DIR):
        self.trade_journal = trade_journal
        self.data_dir = data_dir
        
        self.strategy_weights = {
            'TREND': 0.5,
            'VERC': 0.5,
            'MTF': 0.5
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
            'atr_min': 0.5
        }
        
        logger.info("StrategyPerformanceTracker initialized")
    
    def get_strategy_stats(self, strategy: str, limit: int = 50) -> Dict[str, Any]:
        """
        Get performance stats for a strategy (last N trades).
        
        Args:
            strategy: TREND, VERC, or MTF
            limit: Number of recent trades to analyze
            
        Returns:
            Dict with win_rate, avg_rr, drawdown, holding_time
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
                'avg_holding_days': 0
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
        
        return {
            'strategy': strategy,
            'trades': total,
            'wins': len(wins),
            'losses': len(losses),
            'win_rate': round(win_rate, 2),
            'avg_rr': round(avg_rr, 2),
            'max_drawdown': round(max_drawdown, 2),
            'avg_holding_days': round(avg_holding, 1)
        }
    
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
    
    def auto_optimize(self) -> Dict[str, Any]:
        """
        Auto-Optimization Engine.
        Adjust strategy weights based on composite performance score:
        - Smoothing: gradual weight changes using EMA
        - Min trade threshold: require minimum trades before optimizing
        - Bounded weights: keep weights within defined range
        
        Score formula:
            score = (win_rate * 0.5) + (avg_rr * 20 * 0.3) - (max_drawdown * 0.2)
        
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
            score = self._calculate_performance_score(stats)
            
            raw_weight = current_weight
            
            if score < self.score_threshold - 10:
                raw_weight = max(self.WEIGHT_BOUNDS[0], current_weight - 0.1)
            elif score > self.score_threshold + 10:
                raw_weight = min(self.WEIGHT_BOUNDS[1], current_weight + 0.1)
            
            new_weight = self._bound_weight(self._smooth_weight(current_weight, raw_weight))
            new_weight = round(new_weight, 3)
            
            if abs(new_weight - current_weight) > 0.01:
                if score < self.score_threshold - 10:
                    action = 'reduced'
                    reason = f'score ({score}) < {self.score_threshold - 10}'
                elif score > self.score_threshold + 10:
                    action = 'increased'
                    reason = f'score ({score}) > {self.score_threshold + 10}'
                else:
                    action = 'stable'
                    reason = f'score ({score}) in range'
                
                changes[strategy] = {
                    'action': action,
                    'from': current_weight,
                    'to': new_weight,
                    'trades': trade_count,
                    'score': score,
                    'reason': reason
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
            f"rank_score = (strategy_score * strategy_weight * 0.6) + "
            f"(volume_score * 0.2) + (breakout_strength * 0.2)"
        )
    
    def calculate_adaptive_rank_score(
        self,
        strategy_score: float,
        strategy_type: str,
        volume_ratio: float,
        breakout_strength: float
    ) -> float:
        """
        Calculate rank score with adaptive weights.
        
        rank_score = strategy_score * strategy_weight * 0.6 + volume_score * 0.2 + breakout_strength * 0.2
        """
        strategy_weight = self.strategy_weights.get(strategy_type, 0.5)
        
        volume_score = min(volume_ratio / 3.0, 1.0) * 10
        
        breakout_score = breakout_strength * 10
        
        rank_score = (strategy_score * strategy_weight * 0.6) + (volume_score * 0.2) + (breakout_score * 0.2)
        
        return round(rank_score, 2)
    
    def adapt_filters(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Adaptive Filters - adjust strictness dynamically.
        
        Examples:
        - Too many false breakouts → increase volume_ratio from 1.5 → 1.8
        - Late entries → tighten RSI (65 → 60)
        
        Args:
            analysis: Analysis from AI Learning Layer
            
        Returns:
            Updated filter values
        """
        issues = analysis.get('issues', [])
        
        for issue in issues:
            if 'false_breakouts' in issue or 'low_volume' in issue:
                self.adaptive_filters['volume_ratio_min'] = min(3.0, self.adaptive_filters['volume_ratio_min'] + 0.3)
            
            if 'late_entries' in issue or 'overbought' in issue:
                self.adaptive_filters['rsi_max'] = max(40, self.adaptive_filters['rsi_max'] - 5)
            
            if 'dead_stock' in issue or 'low_volatility' in issue:
                self.adaptive_filters['atr_min'] = max(0.1, self.adaptive_filters['atr_min'] - 0.2)
        
        if issues:
            self._save_filters()
            logger.info(f"Adapted filters: {self.adaptive_filters}")
        
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
        - NIFTY unclear direction
        
        Args:
            atr: Average True Range
            wick_to_body_ratio: Ratio of wick size to body size
            nifty_direction: 'UP', 'DOWN', or 'SIDEWAYS'
            
        Returns:
            Dict with 'allowed' bool and 'reasons' list
        """
        reasons = []
        
        if atr and atr < self.adaptive_filters['atr_min']:
            reasons.append(f"ATR too low ({atr:.2f} < {self.adaptive_filters['atr_min']})")
        
        if wick_to_body_ratio > 1.0:
            reasons.append(f"Choppy candle (wick/body: {wick_to_body_ratio:.2f} > 1.0)")
        
        if nifty_direction == 'SIDEWAYS':
            reasons.append("NIFTY direction unclear (SIDEWAYS)")
        
        return {
            'allowed': len(reasons) == 0,
            'reasons': reasons
        }
    
    def _save_weights(self) -> None:
        filepath = os.path.join(self.data_dir, 'strategy_weights.json')
        data = {
            'weights': self.strategy_weights,
            'updated_at': datetime.now().isoformat()
        }
        try:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving weights: {e}")
    
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
            'adaptive_filters': self.adaptive_filters,
            'performance': all_stats,
            'scores': {
                s: self._calculate_performance_score(stats)
                for s, stats in all_stats.items()
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