"""
Pattern Learning Recognizer (PLR)
Tracks signal patterns and learns what works best.
Answers: "What types of signals should we prioritize?"
"""

import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class PatternPerformance:
    """Performance metrics for a signal pattern."""
    pattern_id: str
    pattern_name: str
    
    total_signals: int = 0
    winning_signals: int = 0
    losing_signals: int = 0
    
    win_rate: float = 0.0
    avg_risk_reward: float = 0.0
    avg_hold_time_hours: float = 0.0
    
    profit_factor: float = 0.0  # Total gains / total losses
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    
    last_updated: datetime = field(default_factory=datetime.now)
    
    # Market context when signal worked best
    best_market_regime: str = ""
    worst_market_regime: str = ""


@dataclass
class ContextualPattern:
    """Pattern plus the context in which it works."""
    pattern_type: str  # e.g., "TREND_ALIGNED_BULLISH"
    market_regime: str  # BULLISH, BEARISH, NEUTRAL, VOLATILE
    timeframe: str  # e.g., "1h", "daily"
    
    success_rate: float  # In this specific context
    avg_profit: float
    probability_of_win: float
    
    last_signal_count: int  # How many signals recently
    consistency_score: float  # 0-10: Is it consistently good or just lucky?


@dataclass
class LearningInsight:
    """What the system learned."""
    insight_type: str  # e.g., "EMERGING_PATTERN", "DECLINING_PATTERN", "CONTEXT_DISCOVERY"
    title: str
    description: str
    impact: str  # e.g., "Increase signal weight from 1.0 to 1.2"
    confidence: float  # 0-100%
    recommended_action: str


class PatternLearningRecognizer:
    """
    Learns from signal outcomes to understand which patterns work.
    
    Questions it answers:
    1. What signal types have highest win rate?
    2. Which patterns work best in which market regimes?
    3. Are we improving or declining?
    4. Should we emphasize or de-emphasize certain patterns?
    """
    
    def __init__(self, trade_journal=None, strategy_optimizer=None):
        self.trade_journal = trade_journal
        self.strategy_optimizer = strategy_optimizer
        
        # Pattern database
        self.pattern_performance: Dict[str, PatternPerformance] = {}
        self.contextual_patterns: Dict[str, ContextualPattern] = {}
        self.learning_insights: List[LearningInsight] = []
        
        self.load_learning_data()
        logger.info("PatternLearningRecognizer initialized")
    
    def load_learning_data(self):
        """Load existing pattern data from trade journal."""
        if not self.trade_journal:
            return
        
        try:
            closed_trades = self.trade_journal.get_closed_trades(limit=1000)
            
            # Group by signal type
            pattern_stats = defaultdict(lambda: {
                'total': 0,
                'wins': 0,
                'losses': 0,
                'returns': [],
                'hold_times': [],
                'market_regimes': defaultdict(lambda: {'wins': 0, 'total': 0}),
                'rr_ratios': []
            })
            
            for trade in closed_trades:
                signal_type = trade.get('signal_type', 'UNKNOWN')
                stats = pattern_stats[signal_type]
                
                stats['total'] += 1
                
                outcome = trade.get('outcome', 'UNKNOWN')
                if outcome == 'WIN':
                    stats['wins'] += 1
                else:
                    stats['losses'] += 1
                
                # Track market regime performance
                regime = trade.get('market_regime', 'UNKNOWN')
                stats['market_regimes'][regime]['total'] += 1
                if outcome == 'WIN':
                    stats['market_regimes'][regime]['wins'] += 1
                
                # Track returns and hold times
                ret = trade.get('return_percent', 0)
                stats['returns'].append(ret)
                
                hold_time = trade.get('hold_time_hours', 0)
                stats['hold_times'].append(hold_time)
                
                rr = trade.get('risk_reward_ratio', 0)
                stats['rr_ratios'].append(rr)
            
            # Convert to PatternPerformance objects
            for pattern_name, stats in pattern_stats.items():
                perf = PatternPerformance(
                    pattern_id=pattern_name,
                    pattern_name=pattern_name,
                    total_signals=stats['total'],
                    winning_signals=stats['wins'],
                    losing_signals=stats['losses'],
                    win_rate=stats['wins'] / stats['total'] * 100 if stats['total'] > 0 else 0,
                    avg_risk_reward=sum(stats['rr_ratios']) / len(stats['rr_ratios']) if stats['rr_ratios'] else 0,
                    avg_hold_time_hours=sum(stats['hold_times']) / len(stats['hold_times']) if stats['hold_times'] else 0
                )
                
                # Best/worst regimes
                if stats['market_regimes']:
                    regime_wins = {r: s['wins']/s['total']*100 if s['total'] > 0 else 0 
                                  for r, s in stats['market_regimes'].items()}
                    perf.best_market_regime = max(regime_wins, key=regime_wins.get) if regime_wins else ""
                    perf.worst_market_regime = min(regime_wins, key=regime_wins.get) if regime_wins else ""
                
                self.pattern_performance[pattern_name] = perf
            
            logger.info(f"Loaded {len(self.pattern_performance)} patterns from trade journal")
            
            # Analyze patterns and generate insights
            self._analyze_patterns()
            
        except Exception as e:
            logger.warning(f"Could not load learning data: {e}")
    
    def _analyze_patterns(self):
        """Analyze patterns to generate learning insights."""
        self.learning_insights = []
        
        if not self.pattern_performance:
            return
        
        # Find best performing pattern
        best_pattern = max(
            self.pattern_performance.values(),
            key=lambda x: x.win_rate if x.total_signals >= 5 else -100
        )
        
        if best_pattern.win_rate >= 55 and best_pattern.total_signals >= 5:
            self.learning_insights.append(LearningInsight(
                insight_type="BEST_PERFORMER",
                title=f"Excellent Pattern: {best_pattern.pattern_name}",
                description=f"{best_pattern.pattern_name} is performing exceptionally with {best_pattern.win_rate:.1f}% win rate ({best_pattern.total_signals} signals)",
                impact=f"Increase weight for {best_pattern.pattern_name} signals",
                confidence=85.0,
                recommended_action=f"Prioritize {best_pattern.pattern_name} in next 30 days"
            ))
        
        # Find worst performing pattern
        worst_pattern = min(
            (p for p in self.pattern_performance.values() if p.total_signals >= 5),
            key=lambda x: x.win_rate,
            default=None
        )
        
        if worst_pattern and worst_pattern.win_rate < 40 and worst_pattern.total_signals >= 5:
            self.learning_insights.append(LearningInsight(
                insight_type="DECLINING_PATTERN",
                title=f"Underperforming: {worst_pattern.pattern_name}",
                description=f"{worst_pattern.pattern_name} has poor win rate of {worst_pattern.win_rate:.1f}%",
                impact=f"Reduce weight or suspend {worst_pattern.pattern_name}",
                confidence=80.0,
                recommended_action=f"Review or suspend {worst_pattern.pattern_name}"
            ))
        
        # Trend analysis
        patterns_by_performance = sorted(
            self.pattern_performance.values(),
            key=lambda x: x.win_rate,
            reverse=True
        )
        
        if patterns_by_performance:
            top_3 = patterns_by_performance[:3]
            top_3_avg = sum(p.win_rate for p in top_3) / len(top_3)
            bottom_3 = patterns_by_performance[-3:]
            bottom_3_avg = sum(p.win_rate for p in bottom_3) / len(bottom_3)
            
            if top_3_avg - bottom_3_avg > 20:
                self.learning_insights.append(LearningInsight(
                    insight_type="PERFORMANCE_DIVERGENCE",
                    title="Large performance gap detected",
                    description=f"Top performers avg {top_3_avg:.1f}% vs bottom {bottom_3_avg:.1f}%",
                    impact="Rebalance signal weights towards top performers",
                    confidence=75.0,
                    recommended_action="Implement weight rebalancing in next scan cycle"
                ))
    
    def record_signal_outcome(self, signal: Dict[str, Any], outcome: str, metadata: Dict[str, Any]):
        """Record outcome of a signal for learning."""
        
        signal_type = signal.get('signal_type', 'UNKNOWN')
        
        if signal_type not in self.pattern_performance:
            self.pattern_performance[signal_type] = PatternPerformance(
                pattern_id=signal_type,
                pattern_name=signal_type
            )
        
        perf = self.pattern_performance[signal_type]
        
        perf.total_signals += 1
        if outcome == 'WIN':
            perf.winning_signals += 1
        else:
            perf.losing_signals += 1
        
        perf.win_rate = perf.winning_signals / perf.total_signals * 100
        
        # Update metadata
        rr = metadata.get('risk_reward_ratio', 0)
        perf.avg_risk_reward = (
            (perf.avg_risk_reward * (perf.total_signals - 1) + rr) / perf.total_signals
        )
        
        hold_time = metadata.get('hold_time_hours', 0)
        perf.avg_hold_time_hours = (
            (perf.avg_hold_time_hours * (perf.total_signals - 1) + hold_time) / perf.total_signals
        )
        
        perf.last_updated = datetime.now()
        
        logger.info(f"Recorded outcome for {signal_type}: {outcome}")
    
    def get_pattern_insights(self, pattern_type: str) -> Dict[str, Any]:
        """Get insights about a specific pattern."""
        
        if pattern_type not in self.pattern_performance:
            return {'status': 'no_data'}
        
        perf = self.pattern_performance[pattern_type]
        
        return {
            'pattern': pattern_type,
            'total_signals': perf.total_signals,
            'win_rate': perf.win_rate,
            'avg_risk_reward': perf.avg_risk_reward,
            'avg_hold_time': perf.avg_hold_time_hours,
            'best_in_regime': perf.best_market_regime,
            'worst_in_regime': perf.worst_market_regime,
            'recommendation': self._get_pattern_recommendation(perf)
        }
    
    def _get_pattern_recommendation(self, perf: PatternPerformance) -> str:
        """Get recommendation for a pattern."""
        
        if perf.total_signals < 5:
            return "INSUFFICIENT_DATA"
        
        if perf.win_rate >= 60:
            return "PRIORITIZE"
        elif perf.win_rate >= 50:
            return "NORMAL"
        elif perf.win_rate >= 40:
            return "CAUTION"
        else:
            return "AVOID"
    
    def get_all_patterns(self) -> List[PatternPerformance]:
        """Get all patterns sorted by win rate."""
        return sorted(
            self.pattern_performance.values(),
            key=lambda x: x.win_rate,
            reverse=True
        )
    
    def get_best_patterns(self, limit: int = 5) -> List[PatternPerformance]:
        """Get top N best performing patterns."""
        return self.get_all_patterns()[:limit]
    
    def get_learning_report(self) -> Dict[str, Any]:
        """Generate a comprehensive learning report."""
        
        if not self.pattern_performance:
            return {'status': 'no_data'}
        
        all_patterns = self.get_all_patterns()
        
        return {
            'timestamp': datetime.now().isoformat(),
            'total_patterns_tracked': len(self.pattern_performance),
            'total_signals_analyzed': sum(p.total_signals for p in all_patterns),
            'overall_win_rate': sum(p.winning_signals for p in all_patterns) / sum(p.total_signals for p in all_patterns) * 100 if sum(p.total_signals for p in all_patterns) > 0 else 0,
            
            'top_performers': [
                {
                    'pattern': p.pattern_name,
                    'win_rate': p.win_rate,
                    'signals': p.total_signals,
                    'avg_rr': p.avg_risk_reward,
                    'best_regime': p.best_market_regime
                }
                for p in all_patterns[:5]
            ],
            
            'bottom_performers': [
                {
                    'pattern': p.pattern_name,
                    'win_rate': p.win_rate,
                    'signals': p.total_signals,
                    'worst_regime': p.worst_market_regime
                }
                for p in all_patterns[-5:] if p.total_signals >= 5
            ],
            
            'insights': [
                {
                    'type': i.insight_type,
                    'title': i.title,
                    'description': i.description,
                    'confidence': i.confidence,
                    'action': i.recommended_action
                }
                for i in self.learning_insights
            ]
        }
    
    def format_pattern_explanation(self, pattern_perf: PatternPerformance) -> str:
        """Format pattern performance as human-readable explanation."""
        
        lines = [
            f"📊 PATTERN ANALYSIS: {pattern_perf.pattern_name}",
            f"Signals: {pattern_perf.total_signals} (W:{pattern_perf.winning_signals} L:{pattern_perf.losing_signals})",
            f"Win Rate: {pattern_perf.win_rate:.1f}%",
            f"Avg R:R: 1:{pattern_perf.avg_risk_reward:.2f}",
            f"Avg Hold: {pattern_perf.avg_hold_time_hours:.1f}h",
            f"Best in: {pattern_perf.best_market_regime}",
            f"Recommendation: {self._get_pattern_recommendation(pattern_perf)}"
        ]
        
        return "\n".join(lines)


def create_pattern_learning_recognizer(
    trade_journal=None,
    strategy_optimizer=None
) -> PatternLearningRecognizer:
    """Factory function."""
    return PatternLearningRecognizer(trade_journal, strategy_optimizer)
