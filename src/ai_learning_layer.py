"""
AI Learning Layer (Strict Mode)
Analyzes journal to detect failure patterns and suggest improvements.
IMPORTANT: AI does NOT control signals - it only provides insights.
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)

DATA_DIR = 'data'

MIN_TRADES_THRESHOLD = 20
MIN_LOSS_SAMPLE = 10
MIN_CONTEXT_SAMPLE = 5


class AILearningLayer:
    """
    AI Learning Layer (STRICT MODE).
    
    AI Role:
    - Analyze journal
    - Detect failure patterns
    - Suggest improvements
    
    AI does NOT control signals - only provides insights.
    """
    
    def __init__(self, trade_journal, strategy_performance, ai_analyzer=None):
        self.trade_journal = trade_journal
        self.strategy_performance = strategy_performance
        self.ai_analyzer = ai_analyzer
        
        logger.info("AILearningLayer initialized (Strict Mode)")
    
    def is_available(self) -> bool:
        """Check if AI is available."""
        return self.ai_analyzer is not None and hasattr(self.ai_analyzer, 'is_available') and self.ai_analyzer.is_available()
    
    def analyze_recent_trades(self, limit: int = 100) -> Dict[str, Any]:
        """
        Analyze last N trades to detect patterns.
        
        Args:
            limit: Number of recent trades to analyze
            
        Returns:
            Dict with insights and recommendations
        """
        recent_trades = self.trade_journal.get_closed_trades(limit=limit)
        open_trades = self.trade_journal.get_open_trades()
        
        if len(recent_trades) < MIN_TRADES_THRESHOLD:
            return {
                'insights': [],
                'issues': [],
                'recommendations': [],
                'status': 'insufficient_data',
                'trades_analyzed': len(recent_trades)
            }
        
        recent_trades = recent_trades[-50:]
        
        issues = []
        insights = []
        recommendations = []
        
        strategy_stats = self.strategy_performance.get_all_strategy_stats()
        
        for strategy, stats in strategy_stats.items():
            win_rate = stats.get('win_rate', 0)
            avg_rr = stats.get('avg_rr', 0)
            
            if win_rate < 40:
                issues.append(f"{strategy} failing: low win rate ({win_rate}%)")
                recommendations.append(f"Consider reducing {strategy} strategy weight")
            
            if avg_rr < 1.5:
                issues.append(f"{strategy} poor RR ({avg_rr})")
                recommendations.append(f"Review stop loss and target levels for {strategy}")
            
            if win_rate >= 60:
                insights.append(f"{strategy} performing well: {win_rate}% win rate")
        
        trades_by_strategy = defaultdict(list)
        for t in recent_trades:
            strategy_name = t.get('strategy', 'UNKNOWN')
            trades_by_strategy[strategy_name].append(t)
        
        for strategy_name, strategy_trades in trades_by_strategy.items():
            if len(strategy_trades) < 5:
                continue
            
            wins = [t for t in strategy_trades if t.get('outcome') == 'WIN']
            win_rate = len(wins) / len(strategy_trades) * 100
            
            if win_rate < 40:
                issues.append(f"{strategy_name} strategy failing: {win_rate:.1f}% win rate")
                recommendations.append(f"Review {strategy_name} entry signals")
        
        context_groups = {"BULLISH": [], "SIDEWAYS": [], "BEARISH": []}
        for t in recent_trades:
            ctx = t.get('market_context', 'SIDEWAYS')
            if ctx in context_groups:
                context_groups[ctx].append(t)
            else:
                continue
        
        for ctx, ctx_trades in context_groups.items():
            if len(ctx_trades) < MIN_CONTEXT_SAMPLE:
                continue
            
            wins = [t for t in ctx_trades if t.get('outcome') == 'WIN']
            win_rate = len(wins) / len(ctx_trades) * 100
            
            if win_rate < 40:
                issues.append(f"{ctx} market performing poorly ({win_rate:.1f}%)")
                recommendations.append(f"Avoid trading in {ctx} market conditions")
        
        quality_groups = {"A": [], "B": [], "C": []}
        for t in recent_trades:
            quality = t.get('quality', 'C')
            if quality in quality_groups:
                quality_groups[quality].append(t)
            else:
                quality_groups["C"].append(t)
        
        quality_performance = {}
        for quality, quality_trades in quality_groups.items():
            if len(quality_trades) >= 3:
                wins = [t for t in quality_trades if t.get('outcome') == 'WIN']
                quality_performance[quality] = {
                    'total': len(quality_trades),
                    'wins': len(wins),
                    'win_rate': len(wins) / len(quality_trades) * 100
                }
        
        a_win_rate = quality_performance.get('A', {}).get('win_rate', 0)
        c_trades = quality_groups.get('C', [])
        if a_win_rate >= 60 and len(c_trades) >= 3:
            c_wins = [t for t in c_trades if t.get('outcome') == 'WIN']
            c_win_rate = len(c_wins) / len(c_trades) * 100
            if c_win_rate < 40:
                issues.append(f"Quality C trades underperforming ({c_win_rate:.1f}%)")
                recommendations.append("Tighten quality filters to only allow A/B trades")
        
        loss_trades = [t for t in recent_trades if t.get('outcome') == 'LOSS']
        filters = getattr(self.strategy_performance, 'adaptive_filters', {}).copy()
        
        if len(loss_trades) >= MIN_LOSS_SAMPLE:
            low_volume_losses = [
                t for t in loss_trades 
                if t.get('volume_ratio', 0) < filters.get('volume_ratio_min', 1.5)
            ]
            if len(low_volume_losses) / len(loss_trades) > 0.6:
                issues.append("Low volume trades underperforming")
                recommendations.append(f"Increase volume threshold to {filters.get('volume_ratio_min', 1.5) + 0.3}x")
            
            high_rsi_losses = [
                t for t in loss_trades 
                if (t.get('rsi', 0) or 0) > filters.get('rsi_max', 65)
            ]
            if len(high_rsi_losses) / len(loss_trades) > 0.6:
                issues.append("Overbought entries leading to losses")
                recommendations.append(f"Tighten RSI filter to {filters.get('rsi_max', 65) - 5}")
            
            low_volume_high_rsi_combo = [
                t for t in loss_trades 
                if t.get('volume_ratio', 0) < filters.get('volume_ratio_min', 1.5) and (t.get('rsi', 0) or 0) > filters.get('rsi_max', 65)
            ]
            if len(low_volume_high_rsi_combo) / len(loss_trades) > 0.4:
                issues.append("Low volume + high RSI combo failing badly")
                recommendations.append("Avoid entries with low volume AND high RSI")
        
        timeout_trades = [t for t in recent_trades if t.get('outcome') == 'TIMEOUT']
        if len(timeout_trades) / len(recent_trades) > 0.3:
            issues.append("Too many trades timing out")
            recommendations.append("Review expiry settings (currently 15 days)")
        
        overall_win_rate = sum(1 for t in recent_trades if t.get('outcome') == 'WIN') / len(recent_trades) * 100
        if overall_win_rate < 50:
            recommendations.append("Reduce confidence scaling - win rate below 50%")
        
        issues = list(set(issues))
        recommendations = list(set(recommendations))
        
        return {
            'insights': insights,
            'issues': issues,
            'recommendations': recommendations,
            'status': 'analyzed',
            'trades_analyzed': len(recent_trades),
            'strategy_stats': strategy_stats,
            'quality_performance': quality_performance,
            'trades_by_strategy': {k: len(v) for k, v in trades_by_strategy.items()},
            'context_groups': {k: len(v) for k, v in context_groups.items()}
        }
    
    def generate_ai_insights(self) -> Dict[str, Any]:
        """
        Generate AI-powered insights using LLM.
        
        Returns:
            AI-generated insights
        """
        if not self.is_available():
            return {
                'ai_insights': [],
                'error': 'AI not available'
            }
        
        analysis = self.analyze_recent_trades(limit=100)
        
        prompt = self._create_analysis_prompt(analysis)
        
        try:
            ai = self.ai_analyzer
            if ai is None:
                return {
                    'ai_insights': [],
                    'error': 'AI analyzer not initialized'
                }
            response = ai.analyze(prompt, system_prompt=self._get_system_prompt())  # type: ignore
            return {
                'ai_insights': self._parse_ai_response(response),
                'raw_analysis': analysis
            }
        except Exception as e:
            logger.error(f"AI analysis error: {e}")
            return {
                'ai_insights': [],
                'error': str(e),
                'fallback_analysis': analysis
            }
    
    def _create_analysis_prompt(self, analysis: Dict[str, Any]) -> str:
        """Create prompt for AI analysis."""
        strategy_stats = analysis.get('strategy_stats', {})
        issues = analysis.get('issues', [])
        recommendations = analysis.get('recommendations', [])
        
        stats_text = ""
        for strategy, stats in strategy_stats.items():
            stats_text += f"""
{strategy}:
- Win Rate: {stats.get('win_rate', 0)}%
- Avg RR: {stats.get('avg_rr', 0)}
- Max Drawdown: {stats.get('max_drawdown', 0)}%
- Avg Holding: {stats.get('avg_holding_days', 0)} days
- Total Trades: {stats.get('trades', 0)}
"""
        
        prompt = f"""You are a trading system AI analyzing trade performance.

CURRENT PERFORMANCE STATISTICS:
{stats_text}

DETECTED ISSUES:
{chr(10).join(f"- {issue}" for issue in issues) if issues else "None"}

EXISTING RECOMMENDATIONS:
{chr(10).join(f"- {rec}" for rec in recommendations) if recommendations else "None"}

Constraints:
- Risk-Reward ratio (RR) must remain >= 2
- Stop loss must remain between 2-3%
- Do NOT suggest loosening risk rules
- Focus only on improving signal quality
- Do NOT recommend increasing position size

Your task:
1. Analyze these patterns and identify root causes
2. Suggest specific parameter adjustments
3. Identify market conditions where strategies work/don't work

Respond in JSON format:
{{
    "pattern_analysis": "detailed analysis of what's working and not working",
    "specific_adjustments": ["list of specific changes to try"],
    "market_conditions": {{"favorable": [], "unfavorable": []}},
    "confidence": "high/medium/low based on data quality"
}}

If insufficient data (< 20 trades), return empty analysis."""
        
        return prompt
    
    def _get_system_prompt(self) -> str:
        """Get system prompt for AI."""
        return """You are an expert trading system analyst. 
You analyze trade performance data to identify patterns and suggest improvements.
You do NOT generate trading signals - you only provide insights for system optimization.
Be specific and actionable in your recommendations."""
    
    def _parse_ai_response(self, response: str) -> List[str]:
        """Parse AI response to extract insights."""
        try:
            data = json.loads(response)
            return [
                data.get('pattern_analysis', ''),
                f"Specific adjustments: {', '.join(data.get('specific_adjustments', []))}"
            ]
        except Exception as e:
            logger.error(f"Error parsing AI response: {e}")
        
        return []
    
    def apply_recommended_filters(self) -> Dict[str, Any]:
        """
        Apply recommended filter changes based on analysis.
        
        Returns:
            Applied changes including previous and new filter values
        """
        analysis = self.analyze_recent_trades(limit=100)
        
        old_filters = getattr(self.strategy_performance, 'adaptive_filters', {}).copy()
        if hasattr(self.strategy_performance, 'get_current_filters'):
            try:
                current = self.strategy_performance.get_current_filters()
                if current:
                    old_filters = current
            except Exception as e:
                logger.debug(f"Error getting current filters: {e}")
                pass
        
        new_filters = self.strategy_performance.adapt_filters(analysis)
        
        changes = []
        if old_filters and new_filters:
            for key in set(list(old_filters.keys()) + list(new_filters.keys())):
                old_val = old_filters.get(key)
                new_val = new_filters.get(key)
                if old_val != new_val:
                    changes.append(f"{key}: {old_val} -> {new_val}")
        
        return {
            "previous_filters": old_filters,
            "new_filters": new_filters,
            "changes": changes,
            "analysis_summary": {
                "issues_found": len(analysis.get('issues', [])),
                "recommendations": len(analysis.get('recommendations', []))
            }
        }
    
    def get_learning_report(self) -> Dict[str, Any]:
        """Generate comprehensive learning report."""
        analysis = self.analyze_recent_trades(limit=100)
        
        report = {
            'generated_at': datetime.now().isoformat(),
            'basic_analysis': analysis
        }
        
        if self.is_available():
            ai_results = self.generate_ai_insights()
            report['ai_analysis'] = ai_results
        
        return report
    
    def get_feature_isolation_stats(self, limit: int = 100) -> Dict[str, Any]:
        """
        Get win rate stats broken down by features.
        
        Returns:
            Dict with win_rate_by for breakout_strength, volume_ratio, consolidation_range
        """
        recent_trades = self.trade_journal.get_closed_trades(limit=limit)
        
        if len(recent_trades) < MIN_TRADES_THRESHOLD:
            return {'status': 'insufficient_data'}
        
        breakout_groups = {
            'high': [],      # >= 6
            'medium': [],    # 4-6
            'low': []       # < 4
        }
        
        volume_groups = {
            'high': [],     # >= 2.0
            'medium': [],   # 1.5-2.0
            'low': []      # < 1.5
        }
        
        consolidation_groups = {
            'tight': [],      # <= 2
            'medium': [],    # 2-4
            'wide': []       # > 4
        }
        
        for t in recent_trades:
            bs = t.get('breakout_strength', 0)
            if bs >= 6:
                breakout_groups['high'].append(t)
            elif bs >= 4:
                breakout_groups['medium'].append(t)
            else:
                breakout_groups['low'].append(t)
            
            vr = t.get('volume_ratio', 0)
            if vr >= 2.0:
                volume_groups['high'].append(t)
            elif vr >= 1.5:
                volume_groups['medium'].append(t)
            else:
                volume_groups['low'].append(t)
            
            cr = t.get('consolidation_range', 100)
            if cr <= 2:
                consolidation_groups['tight'].append(t)
            elif cr <= 4:
                consolidation_groups['medium'].append(t)
            else:
                consolidation_groups['wide'].append(t)
        
        def calc_stats(trades):
            if not trades:
                return {'trades': 0, 'win_rate': 0, 'median_rr': 0, 'max_drawdown': 0}
            wins = [t for t in trades if t.get('outcome') == 'WIN']
            rr_values = sorted([t.get('rr_achieved', 0) for t in trades if t.get('rr_achieved', 0) != 0])
            median_rr = rr_values[len(rr_values) // 2] if rr_values else 0
            max_dd = max([abs(t.get('max_drawdown', 0)) for t in trades], default=0)
            return {
                'trades': len(trades),
                'win_rate': round(len(wins) / len(trades) * 100, 1) if trades else 0,
                'median_rr': round(median_rr, 2),
                'max_drawdown': round(max_dd, 2)
            }
        
        return {
            'status': 'analyzed',
            'win_rate_by_breakout_strength': {k: calc_stats(v) for k, v in breakout_groups.items()},
            'win_rate_by_volume_ratio': {k: calc_stats(v) for k, v in volume_groups.items()},
            'win_rate_by_consolidation': {k: calc_stats(v) for k, v in consolidation_groups.items()}
        }
    
    def get_optimal_filter_value(self, filter_name: str, limit: int = 100) -> float:
        """
        Get optimal filter value based on historical win rate.
        
        Args:
            filter_name: 'breakout_strength', 'volume_ratio', etc.
            
        Returns:
            Optimal value to use for filtering
        """
        stats = self.get_feature_isolation_stats(limit=limit)
        
        if stats.get('status') == 'insufficient_data':
            return 0.0
        
        if filter_name == 'breakout_strength':
            groups = stats.get('win_rate_by_breakout_strength', {})
            for tier in ['high', 'medium']:
                if groups.get(tier, {}).get('win_rate', 0) >= 50:
                    return 6.0 if tier == 'high' else 4.0
            return 4.0
        
        if filter_name == 'volume_ratio':
            groups = stats.get('win_rate_by_volume_ratio', {})
            for tier in ['high', 'medium']:
                if groups.get(tier, {}).get('win_rate', 0) >= 50:
                    return 2.0 if tier == 'high' else 1.5
            return 1.5
        
        return 0.0
    
    def should_reject_trade(self, breakout_strength: float, volume_ratio: float, limit: int = 100) -> bool:
        """
        Determine if trade should be rejected based on historical performance.
        
        Args:
            breakout_strength: Signal breakout strength
            volume_ratio: Signal volume ratio
            
        Returns:
            True if trade should be rejected
        """
        stats = self.get_feature_isolation_stats(limit=limit)
        
        if stats.get('status') == 'insufficient_data':
            return False
        
        bs_groups = stats.get('win_rate_by_breakout_strength', {})
        if breakout_strength < 4:
            low_bs = bs_groups.get('low', {})
            if low_bs.get('trades', 0) >= 5 and low_bs.get('win_rate', 0) < 35:
                return True
        
        vr_groups = stats.get('win_rate_by_volume_ratio', {})
        if volume_ratio < 1.5:
            low_vr = vr_groups.get('low', {})
            if low_vr.get('trades', 0) >= 5 and low_vr.get('win_rate', 0) < 35:
                return True
        
        return False
    
    def score_trade(self, breakout_strength: float, volume_ratio: float, rr_achieved: float = 0) -> int:
        """
        Score a trade based on quality features.
        
        Args:
            breakout_strength: Signal breakout strength
            volume_ratio: Signal volume ratio
            rr_achieved: Risk:reward ratio
            
        Returns:
            Score (0-10)
        """
        score = 0
        
        if breakout_strength >= 6:
            score += 3
        elif breakout_strength >= 4:
            score += 2
        
        if volume_ratio >= 2.0:
            score += 3
        elif volume_ratio >= 1.5:
            score += 2
        
        if rr_achieved >= 2.5:
            score += 4
        elif rr_achieved >= 2.0:
            score += 2
        
        if volume_ratio >= 2.0 and breakout_strength >= 5:
            score += 1
        
        return min(score, 10)


def create_ai_learning_layer(trade_journal, strategy_performance, ai_analyzer=None) -> AILearningLayer:
    """Factory function to create AI learning layer."""
    return AILearningLayer(trade_journal, strategy_performance, ai_analyzer)