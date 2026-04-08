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

logger = logging.getLogger(__name__)

DATA_DIR = 'data'


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
        
        if not recent_trades:
            return {
                'insights': [],
                'issues': [],
                'recommendations': [],
                'status': 'insufficient_data'
            }
        
        issues = []
        insights = []
        recommendations = []
        
        strategy_stats = self.strategy_performance.get_all_strategy_stats()
        
        for strategy, stats in strategy_stats.items():
            win_rate = stats.get('win_rate', 0)
            avg_rr = stats.get('avg_rr', 0)
            
            if win_rate < 40:
                issues.append(f"{strategy} failing: low win_rate ({win_rate}%)")
                recommendations.append(f"Consider reducing {strategy} strategy weight")
            
            if avg_rr < 1.5:
                issues.append(f"{strategy} poor RR ({avg_rr})")
                recommendations.append(f"Review stop loss and target levels for {strategy}")
            
            if win_rate >= 60:
                insights.append(f"{strategy} performing well: {win_rate}% win rate")
        
        loss_trades = [t for t in recent_trades if t.get('outcome') == 'LOSS']
        if loss_trades:
            low_volume_losses = [t for t in loss_trades if t.get('volume_ratio', 0) < 1.5]
            if len(low_volume_losses) / len(loss_trades) > 0.5:
                issues.append("TREND failing in low volume stocks")
                recommendations.append("Increase volume threshold to 1.8x")
            
            high_rsi_losses = [t for t in loss_trades if (t.get('rsi', 0) or 0) > 65]
            if len(high_rsi_losses) / len(loss_trades) > 0.5:
                issues.append("Overbought entries leading to losses")
                recommendations.append("Tighten RSI filter to 60")
        
        timeout_trades = [t for t in recent_trades if t.get('outcome') == 'TIMEOUT']
        if len(timeout_trades) / len(recent_trades) > 0.3:
            issues.append("Too many trades timing out")
            recommendations.append("Review expiry settings (currently 15 days)")
        
        return {
            'insights': insights,
            'issues': issues,
            'recommendations': recommendations,
            'status': 'analyzed',
            'trades_analyzed': len(recent_trades),
            'strategy_stats': strategy_stats
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
            response = self.ai_analyzer.analyze(prompt, system_prompt=self._get_system_prompt())
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
            start = response.find('{')
            end = response.rfind('}') + 1
            if start >= 0 and end > start:
                json_str = response[start:end]
                data = json.loads(json_str)
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
            Applied changes
        """
        analysis = self.analyze_recent_trades(limit=100)
        
        return self.strategy_performance.adapt_filters(analysis)
    
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


def create_ai_learning_layer(trade_journal, strategy_performance, ai_analyzer=None) -> AILearningLayer:
    """Factory function to create AI learning layer."""
    return AILearningLayer(trade_journal, strategy_performance, ai_analyzer)