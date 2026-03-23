"""
Performance Tracker - Signal Intelligence Quotient (SIQ) Calculation
Calculates accuracy metrics and learning feedback.
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict
import json
import math

logger = logging.getLogger(__name__)


class PerformanceTracker:
    """
    Tracks and calculates signal performance metrics.
    Implements SIQ (Signal Intelligence Quotient) scoring.
    """
    
    # Default weights for SIQ calculation
    DEFAULT_WEIGHTS = {
        'win_rate': 0.25,
        'avg_return': 0.20,
        'consistency': 0.15,
        'risk_reward': 0.15,
        'signal_quality': 0.15,
        'timing': 0.10
    }
    
    def __init__(self, history_manager):
        """
        Initialize performance tracker.
        
        Args:
            history_manager: History manager for data access
        """
        self.history_manager = history_manager
        self.weights = self.DEFAULT_WEIGHTS.copy()
        
        logger.info("PerformanceTracker initialized")
    
    def calculate_siq(self, lookback_days: int = 30) -> Dict[str, Any]:
        """
        Calculate Signal Intelligence Quotient.
        
        Args:
            lookback_days: Days to analyze
            
        Returns:
            SIQ score and breakdown
        """
        # Get completed signals
        signals = self.history_manager.get_completed_signals()
        
        # Filter by date
        cutoff = datetime.now() - timedelta(days=lookback_days)
        recent_signals = []
        
        for s in signals:
            try:
                if s.get('completed_at'):
                    completed = datetime.fromisoformat(s['completed_at'])
                    if completed >= cutoff:
                        recent_signals.append(s)
            except:
                pass
        
        if not recent_signals:
            return {
                'siq_score': 0,
                'signal_count': 0,
                'lookback_days': lookback_days,
                'message': 'No completed signals in the lookback period'
            }
        
        # Calculate individual metrics
        metrics = {
            'win_rate': self._calculate_win_rate(recent_signals),
            'avg_return': self._calculate_avg_return(recent_signals),
            'consistency': self._calculate_consistency(recent_signals),
            'risk_reward': self._calculate_risk_reward(recent_signals),
            'signal_quality': self._calculate_signal_quality(recent_signals),
            'timing': self._calculate_timing_score(recent_signals)
        }
        
        # Calculate weighted SIQ
        siq_score = sum(
            metrics[key] * self.weights.get(key, 0)
            for key in metrics
        )
        
        # Normalize to 0-100
        siq_score = max(0, min(100, siq_score * 100))
        
        return {
            'siq_score': round(siq_score, 2),
            'signal_count': len(recent_signals),
            'lookback_days': lookback_days,
            'metrics': metrics,
            'weights': self.weights,
            'calculated_at': datetime.now().isoformat()
        }
    
    def _calculate_win_rate(self, signals: List[Dict[str, Any]]) -> float:
        """Calculate win rate (0-1)."""
        if not signals:
            return 0
        
        wins = len([s for s in signals if s.get('outcome') == 'TARGET_HIT'])
        return wins / len(signals)
    
    def _calculate_avg_return(self, signals: List[Dict[str, Any]]) -> float:
        """Calculate average return (0-1 normalized)."""
        if not signals:
            return 0
        
        returns = [s.get('pnl_percent', 0) for s in signals if s.get('pnl_percent') is not None]
        
        if not returns:
            return 0
        
        avg = sum(returns) / len(returns)
        
        # Normalize: 10% avg return = 1.0, 0% = 0.5, -10% = 0
        normalized = (avg + 10) / 20
        return max(0, min(1, normalized))
    
    def _calculate_consistency(self, signals: List[Dict[str, Any]]) -> float:
        """Calculate consistency score based on variance (0-1)."""
        if not signals:
            return 0
        
        returns = [s.get('pnl_percent', 0) for s in signals if s.get('pnl_percent') is not None]
        
        if len(returns) < 2:
            return 0.5
        
        # Calculate standard deviation
        mean = sum(returns) / len(returns)
        variance = sum((x - mean) ** 2 for x in returns) / len(returns)
        std_dev = math.sqrt(variance)
        
        # Lower variance = higher consistency
        # Normalize: 0% std dev = 1.0, 20%+ std dev = 0
        consistency = 1 - (std_dev / 20)
        
        return max(0, min(1, consistency))
    
    def _calculate_risk_reward(self, signals: List[Dict[str, Any]]) -> float:
        """Calculate average risk-reward ratio (0-1)."""
        if not signals:
            return 0
        
        ratios = []
        
        for s in signals:
            entry = s.get('entry_price', 0)
            target = s.get('target_price', 0)
            sl = s.get('sl_price', 0)
            
            if entry and target and sl:
                reward = abs(target - entry)
                risk = abs(entry - sl)
                
                if risk > 0:
                    ratios.append(reward / risk)
        
        if not ratios:
            return 0
        
        avg_rr = sum(ratios) / len(ratios)
        
        # Normalize: 3:1 = 1.0, 1:1 = 0.5, <1:1 = 0
        normalized = (avg_rr - 1) / 2
        return max(0, min(1, normalized))
    
    def _calculate_signal_quality(self, signals: List[Dict[str, Any]]) -> float:
        """Calculate average signal quality based on confidence scores (0-1)."""
        if not signals:
            return 0
        
        # Look at original confidence if available
        scores = [s.get('confidence_score', s.get('signal_score', 50)) for s in signals]
        
        if not scores:
            return 0.5
        
        # Normalize to 0-1
        avg_score = sum(scores) / len(scores)
        return avg_score / 100
    
    def _calculate_timing_score(self, signals: List[Dict[str, Any]]) -> float:
        """Calculate how quickly signals hit targets (0-1)."""
        if not signals:
            return 0
        
        days_to_resolution = []
        
        for s in signals:
            added = s.get('added_at')
            completed = s.get('completed_at')
            
            if added and completed:
                try:
                    start = datetime.fromisoformat(added)
                    end = datetime.fromisoformat(completed)
                    days = (end - start).days
                    
                    if days >= 0:
                        days_to_resolution.append(days)
                except:
                    pass
        
        if not days_to_resolution:
            return 0.5
        
        avg_days = sum(days_to_resolution) / len(days_to_resolution)
        
        # Normalize: 0-3 days = 1.0, 30+ days = 0
        timing = 1 - (avg_days / 30)
        return max(0, min(1, timing))
    
    def get_accuracy_by_signal_type(self) -> Dict[str, Any]:
        """Get accuracy breakdown by signal type."""
        history = self.history_manager.get_completed_signals()
        
        by_type = defaultdict(lambda: {'total': 0, 'wins': 0, 'returns': []})
        
        for s in history:
            signal_type = s.get('signal_type', 'UNKNOWN')
            by_type[signal_type]['total'] += 1
            
            if s.get('outcome') == 'TARGET_HIT':
                by_type[signal_type]['wins'] += 1
            
            if s.get('pnl_percent'):
                by_type[signal_type]['returns'].append(s['pnl_percent'])
        
        result = {}
        for signal_type, data in by_type.items():
            win_rate = (data['wins'] / data['total'] * 100) if data['total'] > 0 else 0
            avg_return = sum(data['returns']) / len(data['returns']) if data['returns'] else 0
            
            result[signal_type] = {
                'total_signals': data['total'],
                'wins': data['wins'],
                'win_rate': round(win_rate, 2),
                'avg_return': round(avg_return, 2)
            }
        
        return result
    
    def get_accuracy_by_stock(self, min_signals: int = 3) -> Dict[str, Any]:
        """Get accuracy breakdown by stock symbol."""
        history = self.history_manager.get_completed_signals()
        
        by_stock = defaultdict(lambda: {'total': 0, 'wins': 0, 'returns': []})
        
        for s in history:
            stock = s.get('stock_symbol', 'UNKNOWN')
            by_stock[stock]['total'] += 1
            
            if s.get('outcome') == 'TARGET_HIT':
                by_stock[stock]['wins'] += 1
            
            if s.get('pnl_percent'):
                by_stock[stock]['returns'].append(s['pnl_percent'])
        
        # Filter stocks with minimum signals
        filtered = {
            stock: data for stock, data in by_stock.items()
            if data['total'] >= min_signals
        }
        
        result = {}
        for stock, data in filtered.items():
            win_rate = (data['wins'] / data['total'] * 100) if data['total'] > 0 else 0
            avg_return = sum(data['returns']) / len(data['returns']) if data['returns'] else 0
            
            result[stock] = {
                'total_signals': data['total'],
                'wins': data['wins'],
                'win_rate': round(win_rate, 2),
                'avg_return': round(avg_return, 2)
            }
        
        return result
    
    def get_performance_trend(self, periods: int = 4, period_days: int = 7) -> List[Dict[str, Any]]:
        """Get performance trend over time periods."""
        history = self.history_manager.get_completed_signals()
        
        trends = []
        
        for i in range(periods):
            end_date = datetime.now() - timedelta(days=i * period_days)
            start_date = end_date - timedelta(days=period_days)
            
            period_signals = []
            
            for s in history:
                try:
                    completed = datetime.fromisoformat(s.get('completed_at', ''))
                    if start_date <= completed < end_date:
                        period_signals.append(s)
                except:
                    pass
            
            if period_signals:
                wins = len([s for s in period_signals if s.get('outcome') == 'TARGET_HIT'])
                returns = [s.get('pnl_percent', 0) for s in period_signals if s.get('pnl_percent')]
                avg_return = sum(returns) / len(returns) if returns else 0
                
                trends.append({
                    'period': f"Week {periods - i}",
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'signals': len(period_signals),
                    'wins': wins,
                    'win_rate': round((wins / len(period_signals)) * 100, 2),
                    'avg_return': round(avg_return, 2)
                })
        
        return trends
    
    def update_weights(self, new_weights: Dict[str, float]) -> bool:
        """
        Update SIQ calculation weights.
        
        Args:
            new_weights: Dictionary of metric weights
            
        Returns:
            True if successful
        """
        # Validate weights sum to 1.0
        total = sum(new_weights.values())
        
        if abs(total - 1.0) > 0.01:
            logger.warning(f"Weights don't sum to 1.0: {total}")
            return False
        
        # Update weights
        self.weights.update(new_weights)
        
        # Save to history manager
        self.history_manager.save_weights_config({
            'weights': self.weights,
            'updated_at': datetime.now().isoformat()
        })
        
        logger.info(f"Updated SIQ weights: {self.weights}")
        
        return True
    
    def get_recommendations(self) -> List[str]:
        """Generate recommendations based on performance analysis."""
        siq = self.calculate_siq()
        recommendations = []
        
        if siq['signal_count'] < 5:
            recommendations.append("Need more signal data for meaningful recommendations")
            return recommendations
        
        metrics = siq.get('metrics', {})
        
        # Win rate recommendations
        win_rate = metrics.get('win_rate', 0)
        if win_rate < 0.4:
            recommendations.append("Low win rate - consider stricter entry criteria")
        elif win_rate > 0.7:
            recommendations.append("Excellent win rate - consider reducing position size for better risk management")
        
        # Return recommendations
        avg_return = metrics.get('avg_return', 0)
        if avg_return < 0.3:
            recommendations.append("Low average returns - review target levels")
        
        # Consistency recommendations
        consistency = metrics.get('consistency', 0)
        if consistency < 0.3:
            recommendations.append("Inconsistent results - signals may need more filtering")
        
        # Risk-reward recommendations
        rr = metrics.get('risk_reward', 0)
        if rr < 0.3:
            recommendations.append("Poor risk-reward ratio - review stop-loss and target settings")
        
        # Timing recommendations
        timing = metrics.get('timing', 0)
        if timing < 0.3:
            recommendations.append("Slow signal resolution - signals may be too early or targets too aggressive")
        
        return recommendations
    
    def generate_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report."""
        siq_30 = self.calculate_siq(lookback_days=30)
        siq_7 = self.calculate_siq(lookback_days=7)
        
        return {
            'generated_at': datetime.now().isoformat(),
            'siq_30_day': siq_30,
            'siq_7_day': siq_7,
            'accuracy_by_type': self.get_accuracy_by_signal_type(),
            'accuracy_by_stock': self.get_accuracy_by_stock(),
            'performance_trend': self.get_performance_trend(),
            'recommendations': self.get_recommendations()
        }


def create_performance_tracker(history_manager) -> PerformanceTracker:
    """Factory function to create performance tracker."""
    return PerformanceTracker(history_manager)