"""
Factor-Level Learning System
Analyzes trade journal at granular level to track performance per factor.
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)

DATA_DIR = 'data'


class FactorAnalyzer:
    """
    Analyzes trade outcomes at factor level.
    Tracks performance per factor for learning and optimization.
    """
    
    INSIGHTS_FILE = 'factor_insights.json'
    
    VOLUME_RATIO_BUCKETS = ['0.5-1.0', '1.0-1.5', '1.5-2.0', '2.0-2.5', '2.5+']
    RSI_RANGES = ['0-40', '40-45', '45-50', '50-55', '55-60', '60-65', '65-70', '70+']
    BREAKOUT_STRENGTH_BUCKETS = ['0-2%', '2-5%', '5%+']
    
    def __init__(self, trade_journal=None, data_dir: str = DATA_DIR):
        self.trade_journal = trade_journal
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        
        self.factor_stats = self._load_insights()
        
        logger.info("FactorAnalyzer initialized")
    
    def _load_insights(self) -> Dict[str, Any]:
        filepath = os.path.join(self.data_dir, self.INSIGHTS_FILE)
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading factor insights: {e}")
        return self._create_empty_insights()
    
    def _create_empty_insights(self) -> Dict[str, Any]:
        return {
            'volume_ratio_buckets': {bucket: {'wins': 0, 'total': 0, 'win_rate': 0.0} 
                                    for bucket in self.VOLUME_RATIO_BUCKETS},
            'rsi_ranges': {range_val: {'wins': 0, 'total': 0, 'win_rate': 0.0} 
                          for range_val in self.RSI_RANGES},
            'breakout_strength': {bucket: {'wins': 0, 'total': 0, 'win_rate': 0.0} 
                                for bucket in self.BREAKOUT_STRENGTH_BUCKETS},
            'ema_alignment': {'wins': 0, 'total': 0, 'win_rate': 0.0},
            'quality_grades': {'A': {'wins': 0, 'total': 0, 'win_rate': 0.0},
                             'B': {'wins': 0, 'total': 0, 'win_rate': 0.0},
                             'C': {'wins': 0, 'total': 0, 'win_rate': 0.0}},
            'market_context': {'BULLISH': {'wins': 0, 'total': 0, 'win_rate': 0.0},
                             'SIDEWAYS': {'wins': 0, 'total': 0, 'win_rate': 0.0},
                             'BEARISH': {'wins': 0, 'total': 0, 'win_rate': 0.0}},
            'entry_types': {'BREAKOUT': {'wins': 0, 'total': 0, 'win_rate': 0.0},
                          'PULLBACK': {'wins': 0, 'total': 0, 'win_rate': 0.0}},
            'last_updated': ''
        }
    
    def _save_insights(self) -> None:
        self.factor_stats['last_updated'] = datetime.now().isoformat()
        filepath = os.path.join(self.data_dir, self.INSIGHTS_FILE)
        try:
            with open(filepath, 'w') as f:
                json.dump(self.factor_stats, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving factor insights: {e}")
    
    def get_volume_bucket(self, volume_ratio: float) -> str:
        """Categorize volume ratio into buckets."""
        if volume_ratio < 1.0:
            return '0.5-1.0'
        elif volume_ratio < 1.5:
            return '1.0-1.5'
        elif volume_ratio < 2.0:
            return '1.5-2.0'
        elif volume_ratio < 2.5:
            return '2.0-2.5'
        else:
            return '2.5+'
    
    def get_rsi_range(self, rsi: float) -> str:
        """Categorize RSI into ranges."""
        if rsi < 40:
            return '0-40'
        elif rsi < 45:
            return '40-45'
        elif rsi < 50:
            return '45-50'
        elif rsi < 55:
            return '50-55'
        elif rsi < 60:
            return '55-60'
        elif rsi < 65:
            return '60-65'
        elif rsi < 70:
            return '65-70'
        else:
            return '70+'
    
    def get_breakout_bucket(self, breakout_strength: float) -> str:
        """Categorize breakout strength into buckets."""
        pct = breakout_strength * 100 if breakout_strength <= 1 else breakout_strength
        if pct < 2:
            return '0-2%'
        elif pct < 5:
            return '2-5%'
        else:
            return '5%+'
    
    def analyze_trade(self, trade: Dict[str, Any]) -> None:
        """
        Analyze a single trade and update factor stats.
        Called when trade is closed.
        """
        if not trade or trade.get('outcome') == 'OPEN':
            return
        
        is_win = trade.get('outcome') == 'WIN'
        
        volume_ratio = trade.get('volume_ratio', 0)
        rsi = trade.get('rsi', 0)
        breakout_strength = trade.get('breakout_strength', 0)
        quality = trade.get('quality', 'B')
        market_context = trade.get('market_context', 'BULLISH')
        entry_type = trade.get('entry_type', 'BREAKOUT')
        
        if volume_ratio > 0:
            bucket = self.get_volume_bucket(volume_ratio)
            self._update_factor('volume_ratio_buckets', bucket, is_win)
        
        if rsi > 0:
            rsi_range = self.get_rsi_range(rsi)
            self._update_factor('rsi_ranges', rsi_range, is_win)
        
        if breakout_strength > 0:
            bucket = self.get_breakout_bucket(breakout_strength)
            self._update_factor('breakout_strength', bucket, is_win)
        
        if quality:
            self._update_factor('quality_grades', quality, is_win)
        
        if market_context:
            self._update_factor('market_context', market_context, is_win)
        
        if entry_type:
            self._update_factor('entry_types', entry_type, is_win)
        
        self._save_insights()
    
    def _update_factor(self, category: str, key: str, is_win: bool) -> None:
        """Update stats for a specific factor."""
        if category in self.factor_stats and key in self.factor_stats[category]:
            stats = self.factor_stats[category][key]
            stats['total'] += 1
            if is_win:
                stats['wins'] += 1
            stats['win_rate'] = round((stats['wins'] / stats['total']) * 100, 2)
    
    def get_factor_report(self) -> Dict[str, Any]:
        """Get comprehensive factor performance report."""
        return self.factor_stats.copy()
    
    def get_underperforming_factors(self) -> Dict[str, List[str]]:
        """
        Identify underperforming factors for optimization.
        Returns factors with win_rate below threshold.
        """
        threshold = 40.0
        underperforming = {}
        
        for category, data in self.factor_stats.items():
            if category == 'last_updated':
                continue
            for key, stats in data.items():
                if stats.get('total', 0) >= 5 and stats.get('win_rate', 0) < threshold:
                    if category not in underperforming:
                        underperforming[category] = []
                    underperforming[category].append(key)
        
        return underperforming
    
    def get_optimization_recommendations(self) -> Dict[str, Any]:
        """
        Generate recommendations for adaptive filter optimization.
        """
        recommendations = {}
        
        volume_stats = self.factor_stats.get('volume_ratio_buckets', {})
        best_volume_bucket = None
        best_wr = 0
        worst_volume_bucket = None
        worst_wr = 100
        
        for bucket, stats in volume_stats.items():
            if stats['total'] >= 3:
                if stats['win_rate'] > best_wr:
                    best_wr = stats['win_rate']
                    best_volume_bucket = bucket
                if stats['win_rate'] < worst_wr:
                    worst_wr = stats['win_rate']
                    worst_volume_bucket = bucket
        
        if best_volume_bucket:
            recommendations['volume_ratio_min'] = f"Best performing: {best_volume_bucket} ({best_wr}% win rate)"
        if worst_volume_bucket and worst_wr < 40:
            recommendations['volume_ratio_warning'] = f"Underperforming: {worst_volume_bucket} ({worst_wr}% win rate)"
        
        rsi_stats = self.factor_stats.get('rsi_ranges', {})
        best_rsi_range = None
        best_rsi_wr = 0
        
        for range_val, stats in rsi_stats.items():
            if stats['total'] >= 3 and stats['win_rate'] > best_rsi_wr:
                best_rsi_wr = stats['win_rate']
                best_rsi_range = range_val
        
        if best_rsi_range:
            recommendations['rsi_optimal'] = f"Best RSI range: {best_rsi_range} ({best_rsi_wr}% win rate)"
        
        quality_stats = self.factor_stats.get('quality_grades', {})
        for grade, stats in quality_stats.items():
            if stats['total'] >= 3:
                recommendations[f'quality_{grade}_winrate'] = f"{stats['win_rate']}%"
        
        return recommendations
    
    def batch_analyze(self, trades: List[Dict[str, Any]]) -> None:
        """Analyze a batch of closed trades."""
        for trade in trades:
            self.analyze_trade(trade)
        logger.info(f"Batch analyzed {len(trades)} trades")
    
    def reset_insights(self) -> None:
        """Reset all factor insights."""
        self.factor_stats = self._create_empty_insights()
        self._save_insights()
        logger.info("Factor insights reset")


def create_factor_analyzer(trade_journal=None, data_dir: str = DATA_DIR) -> FactorAnalyzer:
    """Factory function to create FactorAnalyzer."""
    return FactorAnalyzer(trade_journal, data_dir)