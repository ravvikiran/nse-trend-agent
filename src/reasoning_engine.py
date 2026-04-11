"""
Reasoning Engine - Hybrid Signal Generation
Combines rule-based algorithms, weighted scoring, and AI reasoning.
"""

import logging
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class FactorScore:
    """Individual factor score with breakdown."""
    factor_name: str
    raw_score: float
    weight: float
    contribution: float
    details: str = ""


@dataclass
class WeightedScore:
    """Combined weighted score result."""
    final_score: float
    strength: str
    factors: List[FactorScore] = field(default_factory=list)
    threshold_met: bool = True


@dataclass
class AIReasoning:
    """AI-powered reasoning result."""
    recommendation: str
    confidence: int
    reasoning: str
    risk_reward_ratio: str
    entry_zone: str
    stop_loss: str
    targets: List[str]
    market_context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SignalRejection:
    """Structured rejection with reason for learning."""
    rejected: bool = True
    reason: str = ""
    score: float = 0.0
    failed_factors: List[str] = field(default_factory=list)


@dataclass
class CombinedSignal:
    """Complete signal with all reasoning components."""
    signal_id: str
    stock_symbol: str
    timestamp: datetime
    
    rule_signals: Dict[str, Any]
    weighted_score: WeightedScore
    ai_reasoning: Optional[AIReasoning] = None
    
    recommendation: str = ""
    final_score: float = 0.0
    strength: str = ""
    explanation: str = ""
    
    entry_price: float = 0.0
    stop_loss: float = 0.0
    target_1: float = 0.0
    target_2: float = 0.0
    
    rejection: Optional[SignalRejection] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            'signal_id': self.signal_id,
            'stock_symbol': self.stock_symbol,
            'timestamp': self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else str(self.timestamp),
            'rule_signals': self.rule_signals,
            'weighted_score': {
                'final_score': self.weighted_score.final_score,
                'strength': self.weighted_score.strength,
                'threshold_met': self.weighted_score.threshold_met,
                'factors': [
                    {
                        'factor_name': f.factor_name,
                        'raw_score': f.raw_score,
                        'weight': f.weight,
                        'contribution': f.contribution,
                        'details': f.details
                    }
                    for f in self.weighted_score.factors
                ]
            },
            'ai_reasoning': {
                'recommendation': self.ai_reasoning.recommendation if self.ai_reasoning else None,
                'confidence': self.ai_reasoning.confidence if self.ai_reasoning else None,
                'reasoning': self.ai_reasoning.reasoning if self.ai_reasoning else None,
                'risk_reward_ratio': self.ai_reasoning.risk_reward_ratio if self.ai_reasoning else None,
                'entry_zone': self.ai_reasoning.entry_zone if self.ai_reasoning else None,
                'stop_loss': self.ai_reasoning.stop_loss if self.ai_reasoning else None,
                'targets': self.ai_reasoning.targets if self.ai_reasoning else None
            } if self.ai_reasoning else None,
            'combined_signal': {
                'recommendation': self.recommendation,
                'final_score': self.final_score,
                'strength': self.strength,
                'explanation': self.explanation
            },
            'trade_levels': {
                'entry_price': self.entry_price,
                'stop_loss': self.stop_loss,
                'target_1': self.target_1,
                'target_2': self.target_2
            }
        }
        
        if self.rejection:
            result['rejection'] = {
                'rejected': self.rejection.rejected,
                'reason': self.rejection.reason,
                'score': self.rejection.score,
                'failed_factors': self.rejection.failed_factors
            }
        
        return result


class ReasoningEngine:
    """
    Hybrid reasoning engine that combines:
    1. Rule-based algorithms (existing)
    2. Weighted scoring with dynamic weights
    3. AI reasoning (gated, not blended)
    """
    
    DEFAULT_WEIGHTS = {
        'ema_alignment': 0.15,
        'volume_confirmation': 0.15,
        'rsi_position': 0.10,
        'atr_volatility': 0.10,
        'verc_score': 0.20,
        'rsi_divergence': 0.10,
        'market_context': 0.10,
        'price_momentum': 0.10
    }
    
    STRATEGY_THRESHOLDS = {
        'TREND': 65,
        'VERC': 60,
        'MTF': 70
    }
    
    THRESHOLDS = {
        'min_signal_score': 60,
        'strong_buy_min': 80,
        'neutral_max': 59,
        'sell_max': 39
    }
    
    AI_CONFIDENCE_GATE = 6
    AI_OVERRIDE_THRESHOLD = 75
    
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        strategy_tracker: Optional[Any] = None
    ):
        """
        Initialize the reasoning engine.
        
        Args:
            config: Optional configuration dict with weights and thresholds
            strategy_tracker: Optional StrategyPerformanceTracker for dynamic weights
        """
        self.config = config or {}
        self.strategy_tracker = strategy_tracker
        self.current_strategy = self.config.get('strategy', 'TREND')
        
        weights_config = self.config.get('weights', {})
        self.weights = weights_config if weights_config else self.DEFAULT_WEIGHTS.copy()
        
        threshold_config = self.config.get('thresholds', {})
        self.thresholds = {**self.THRESHOLDS, **threshold_config}
        
        self._validate_weights()
        
        logger.info(f"ReasoningEngine initialized with weights: {self.weights}")
    
    def _validate_weights(self) -> None:
        """Validate that weights sum to 1.0."""
        total = sum(self.weights.values())
        if abs(total - 1.0) > 0.01:
            logger.warning(f"Weights sum to {total}, normalizing to 1.0")
            for key in self.weights:
                self.weights[key] /= total
    
    def _get_dynamic_weight(self, factor: str, market_condition: str = 'TRENDING') -> float:
        """
        Get dynamic weight using strategy performance tracker.
        
        Args:
            factor: Factor name to get weight for
            market_condition: Current market condition
            
        Returns:
            Adjusted weight
        """
        base_weight = self.weights.get(factor, 0.1)
        
        if self.strategy_tracker:
            try:
                context_weight = self.strategy_tracker.get_context_weight(
                    self.current_strategy,
                    market_condition
                )
                return base_weight * context_weight
            except Exception as e:
                logger.warning(f"Could not get dynamic weight: {e}")
        
        return base_weight
    
    def set_strategy_tracker(self, tracker: Any) -> None:
        """Set strategy tracker for dynamic weights."""
        self.strategy_tracker = tracker
    
    def set_strategy(self, strategy: str) -> None:
        """Set current strategy for threshold selection."""
        self.current_strategy = strategy
    
    def calculate_weighted_score(
        self,
        indicators: Dict[str, Any],
        rule_signals: Dict[str, Any],
        verc_data: Optional[Dict[str, Any]] = None,
        market_context: Optional[Dict[str, Any]] = None,
        market_condition: str = 'TRENDING'
    ) -> WeightedScore:
        """
        Calculate weighted score from various factors.
        
        Args:
            indicators: Technical indicator values
            rule_signals: Rule-based signal outputs
            verc_data: VERC strategy data
            market_context: Enhanced market context
            market_condition: Current market condition
            
        Returns:
            WeightedScore object
        """
        factors = []
        total_score = 0.0
        
        mkt_context = self._parse_market_context(market_context)
        
        ema_score, ema_details = self._score_ema_alignment(indicators, mkt_context)
        ema_weight = self._get_dynamic_weight('ema_alignment', market_condition)
        ema_factor = FactorScore(
            factor_name='ema_alignment',
            raw_score=ema_score,
            weight=ema_weight,
            contribution=ema_score * ema_weight,
            details=ema_details
        )
        factors.append(ema_factor)
        total_score += ema_factor.contribution
        
        volume_score, volume_details = self._score_volume_confirmation(indicators)
        volume_weight = self._get_dynamic_weight('volume_confirmation', market_condition)
        volume_factor = FactorScore(
            factor_name='volume_confirmation',
            raw_score=volume_score,
            weight=volume_weight,
            contribution=volume_score * volume_weight,
            details=volume_details
        )
        factors.append(volume_factor)
        total_score += volume_factor.contribution
        
        rsi_score, rsi_details = self._score_rsi_position(indicators)
        rsi_weight = self._get_dynamic_weight('rsi_position', market_condition)
        rsi_factor = FactorScore(
            factor_name='rsi_position',
            raw_score=rsi_score,
            weight=rsi_weight,
            contribution=rsi_score * rsi_weight,
            details=rsi_details
        )
        factors.append(rsi_factor)
        total_score += rsi_factor.contribution
        
        atr_score, atr_details = self._score_atr_volatility(indicators)
        atr_weight = self._get_dynamic_weight('atr_volatility', market_condition)
        atr_factor = FactorScore(
            factor_name='atr_volatility',
            raw_score=atr_score,
            weight=atr_weight,
            contribution=atr_score * atr_weight,
            details=atr_details
        )
        factors.append(atr_factor)
        total_score += atr_factor.contribution
        
        verc_score, verc_details = self._score_verc(verc_data)
        verc_weight = self._get_dynamic_weight('verc_score', market_condition)
        verc_factor = FactorScore(
            factor_name='verc_score',
            raw_score=verc_score,
            weight=verc_weight,
            contribution=verc_score * verc_weight,
            details=verc_details
        )
        factors.append(verc_factor)
        total_score += verc_factor.contribution
        
        div_score, div_details = self._score_rsi_divergence(indicators, rule_signals)
        div_weight = self._get_dynamic_weight('rsi_divergence', market_condition)
        div_factor = FactorScore(
            factor_name='rsi_divergence',
            raw_score=div_score,
            weight=div_weight,
            contribution=div_score * div_weight,
            details=div_details
        )
        factors.append(div_factor)
        total_score += div_factor.contribution
        
        market_score, market_details = self._score_market_context(market_context, mkt_context)
        market_weight = self._get_dynamic_weight('market_context', market_condition)
        market_factor = FactorScore(
            factor_name='market_context',
            raw_score=market_score,
            weight=market_weight,
            contribution=market_score * market_weight,
            details=market_details
        )
        factors.append(market_factor)
        total_score += market_factor.contribution
        
        momentum_score, momentum_details = self._score_price_momentum(indicators)
        momentum_weight = self._get_dynamic_weight('price_momentum', market_condition)
        momentum_factor = FactorScore(
            factor_name='price_momentum',
            raw_score=momentum_score,
            weight=momentum_weight,
            contribution=momentum_score * momentum_weight,
            details=momentum_details
        )
        factors.append(momentum_factor)
        total_score += momentum_factor.contribution
        
        min_threshold = self._get_strategy_threshold()
        strength = self._get_strength(total_score)
        threshold_met = total_score >= min_threshold
        
        return WeightedScore(
            final_score=round(total_score, 2),
            strength=strength,
            factors=factors,
            threshold_met=threshold_met
        )
    
    def _get_strategy_threshold(self) -> float:
        """Get threshold for current strategy."""
        return self.STRATEGY_THRESHOLDS.get(self.current_strategy, 60)
    
    def _parse_market_context(
        self,
        market_context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Parse market context into structured format.
        
        Args:
            market_context: Raw market context
            
        Returns:
            Structured market context
        """
        default_context = {
            'trend': 'SIDEWAYS',
            'volatility': 'MODERATE',
            'sector_strength': 'NEUTRAL',
            'index_alignment': False
        }
        
        if not market_context:
            return default_context
        
        return {
            'trend': market_context.get('trend', 'SIDEWAYS').upper(),
            'volatility': market_context.get('volatility', 'MODERATE').upper(),
            'sector_strength': market_context.get('sector_strength', 'NEUTRAL').upper(),
            'index_alignment': market_context.get('index_alignment', False)
        }
    
    def _score_ema_alignment(
        self,
        indicators: Dict[str, Any],
        market_context: Dict[str, Any]
    ) -> Tuple[float, str]:
        """Score EMA alignment with context override."""
        ema_20 = indicators.get('ema_20', 0)
        ema_50 = indicators.get('ema_50', 0)
        ema_100 = indicators.get('ema_100', 0)
        ema_200 = indicators.get('ema_200', 0)
        
        if ema_20 == 0 or ema_50 == 0:
            return 50, "Insufficient EMA data"
        
        score = 50
        
        if ema_20 > ema_50:
            score += 15
        if ema_50 > ema_100:
            score += 15
        if ema_100 > ema_200:
            score += 20
        
        trend = market_context.get('trend', 'SIDEWAYS')
        if trend == 'TRENDING':
            score = min(score + 10, 100)
        elif trend == 'SIDEWAYS':
            score = max(score - 10, 20)
        
        details = f"EMA: {ema_20:.2f}>{ema_50:.2f}>{ema_100:.2f}>{ema_200:.2f}, Trend: {trend}"
        
        return min(score, 100), details
    
    def _score_volume_confirmation(self, indicators: Dict[str, Any]) -> Tuple[float, str]:
        """Score volume confirmation."""
        volume = indicators.get('volume', 0)
        volume_ma = indicators.get('volume_ma', 0)
        
        if volume_ma == 0:
            return 50, "Insufficient volume data"
        
        volume_ratio = volume / volume_ma
        
        if volume_ratio >= 2.0:
            score = 100
        elif volume_ratio >= 1.5:
            score = 80
        elif volume_ratio >= 1.2:
            score = 60
        elif volume_ratio >= 1.0:
            score = 50
        else:
            score = 30
        
        details = f"Volume: {volume_ratio:.2f}x"
        
        return score, details
    
    def _score_rsi_position(self, indicators: Dict[str, Any]) -> Tuple[float, str]:
        """Score RSI position."""
        rsi = indicators.get('rsi', 50)
        
        if rsi == 0:
            return 50, "Insufficient RSI data"
        
        if 40 <= rsi <= 70:
            if 50 <= rsi <= 65:
                score = 100
            else:
                score = 80
        elif rsi < 30:
            score = 70
        elif rsi > 70:
            score = 40
        elif rsi < 40:
            score = 60
        else:
            score = 50
        
        zone = 'Oversold' if rsi < 40 else 'Overbought' if rsi > 70 else 'Optimal'
        details = f"RSI: {rsi:.2f} - {zone}"
        
        return score, details
    
    def _score_atr_volatility(self, indicators: Dict[str, Any]) -> Tuple[float, str]:
        """
        Score ATR volatility: Moderate is BEST, not low.
        
        Low ATR = dead stock
        Moderate ATR = best (controlled volatility)
        High ATR = risky
        """
        atr = indicators.get('atr', 0)
        close = indicators.get('close', 0)
        
        if atr == 0 or close == 0:
            return 50, "Insufficient ATR data"
        
        atr_percent = (atr / close) * 100
        
        if 1.0 < atr_percent < 2.5:
            score = 100
        elif atr_percent <= 1.0:
            score = 40
        elif atr_percent <= 2.0:
            score = 80
        elif atr_percent <= 3.0:
            score = 60
        elif atr_percent > 3.0:
            score = 50
        else:
            score = 50
        
        zone = 'DEAD' if atr_percent < 1.0 else 'OPTIMAL' if atr_percent < 2.5 else 'HIGH' if atr_percent > 3.0 else 'MODERATE'
        details = f"ATR: {atr_percent:.2f}% - {zone}"
        
        return score, details
    
    def _score_verc(self, verc_data: Optional[Dict[str, Any]]) -> Tuple[float, str]:
        """Score VERC signal if available."""
        if not verc_data:
            return 50, "No VERC data"
        
        confidence = verc_data.get('confidence_score', 50)
        
        details = f"VERC Confidence: {confidence}%"
        
        return float(confidence), details
    
    def _score_rsi_divergence(
        self,
        indicators: Dict[str, Any],
        rule_signals: Dict[str, Any]
    ) -> Tuple[float, str]:
        """Score RSI divergence."""
        rsi = indicators.get('rsi', 50)
        
        has_divergence = rule_signals.get('bullish_divergence', False)
        
        if has_divergence:
            score = 90
            details = "Bullish RSI divergence detected"
        else:
            score = 50
            details = "No divergence detected"
        
        return score, details
    
    def _score_market_context(
        self,
        market_context: Optional[Dict[str, Any]],
        parsed_context: Dict[str, Any]
    ) -> Tuple[float, str]:
        """
        Score enhanced market context.
        
        Context should override signals, not just contribute.
        """
        if not market_context:
            return 50, "No market context"
        
        score = 50
        
        trend = parsed_context.get('trend', 'SIDEWAYS')
        if trend == 'TRENDING':
            score += 20
        elif trend == 'SIDEWAYS':
            score -= 20
        
        volatility = parsed_context.get('volatility', 'MODERATE')
        if volatility == 'HIGH':
            score -= 10
        elif volatility == 'LOW':
            score += 5
        
        sector = parsed_context.get('sector_strength', 'NEUTRAL')
        if sector == 'STRONG':
            score += 15
        elif sector == 'WEAK':
            score -= 15
        
        index_aligned = parsed_context.get('index_alignment', False)
        if index_aligned:
            score += 15
        
        score = max(0, min(100, score))
        
        details = f"Trend: {trend}, Vol: {volatility}, Sector: {sector}, NiftyAligned: {index_aligned}"
        
        return score, details
    
    def _score_price_momentum(self, indicators: Dict[str, Any]) -> Tuple[float, str]:
        """
        Score price momentum using slope + separation.
        
        Momentum = slope + separation, not just position.
        """
        close = indicators.get('close', 0)
        ema_20 = indicators.get('ema_20', 0)
        ema_50 = indicators.get('ema_50', 0)
        
        if close == 0 or ema_20 == 0 or ema_50 == 0:
            return 50, "Insufficient data"
        
        momentum_20 = (close - ema_20) / ema_20
        momentum_50 = (ema_20 - ema_50) / ema_50
        
        combined = momentum_20 + momentum_50
        
        score = self._normalize_momentum(combined)
        
        details = f"Momentum: {momentum_20*100:.2f}% (20) + {momentum_50*100:.2f}% (50) = {combined*100:.2f}%"
        
        return score, details
    
    def _normalize_momentum(self, momentum: float) -> float:
        """
        Normalize momentum to 0-100 score.
        
        Momentum typically ranges from -5% to +5%.
        """
        normalized = (momentum + 0.05) / 0.10 * 100
        return max(0, min(100, normalized))
    
    def _get_strength(self, score: float) -> str:
        """Determine signal strength from score."""
        if score >= self.thresholds['strong_buy_min']:
            return 'STRONG_BUY'
        elif score >= self.thresholds['min_signal_score']:
            return 'BUY'
        elif score <= self.thresholds['sell_max']:
            return 'SELL'
        elif score <= self.thresholds['neutral_max']:
            return 'NEUTRAL'
        else:
            return 'BUY'
    
    def create_combined_signal(
        self,
        stock_symbol: str,
        indicators: Dict[str, Any],
        rule_signals: Dict[str, Any],
        ai_analysis: Optional[Dict[str, Any]] = None,
        verc_data: Optional[Dict[str, Any]] = None,
        market_context: Optional[Dict[str, Any]] = None,
        market_condition: str = 'TRENDING'
    ) -> Optional[CombinedSignal]:
        """
        Create a complete combined signal.
        
        Returns:
            CombinedSignal with rejection info or None
        """
        weighted_score = self.calculate_weighted_score(
            indicators, rule_signals, verc_data, market_context, market_condition
        )
        
        min_threshold = self._get_strategy_threshold()
        
        if not weighted_score.threshold_met:
            failed = self._identify_failed_factors(weighted_score.factors, min_threshold)
            rejection = SignalRejection(
                rejected=True,
                reason=f"Low base score: {weighted_score.final_score} < {min_threshold}",
                score=weighted_score.final_score,
                failed_factors=failed
            )
            logger.debug(f"Signal for {stock_symbol} rejected: {rejection.reason}")
            
            return CombinedSignal(
                signal_id=str(uuid.uuid4()),
                stock_symbol=stock_symbol,
                timestamp=datetime.now(),
                rule_signals=rule_signals,
                weighted_score=weighted_score,
                rejection=rejection
            )
        
        ai_reasoning = None
        if ai_analysis:
            ai_reasoning = AIReasoning(
                recommendation=ai_analysis.get('recommendation', 'HOLD'),
                confidence=ai_analysis.get('confidence', 5),
                reasoning=ai_analysis.get('reasoning', ''),
                risk_reward_ratio=ai_analysis.get('risk_reward_ratio', '1:2'),
                entry_zone=ai_analysis.get('entry_zone', ''),
                stop_loss=ai_analysis.get('stop_loss', ''),
                targets=ai_analysis.get('targets', [])
            )
        
        recommendation, final_score, explanation = self._combine_signals(
            weighted_score, ai_reasoning
        )
        
        entry_price = indicators.get('close', 0)
        stop_loss, target_1, target_2 = self._calculate_trade_levels(
            indicators, ai_reasoning
        )
        
        signal = CombinedSignal(
            signal_id=str(uuid.uuid4()),
            stock_symbol=stock_symbol,
            timestamp=datetime.now(),
            rule_signals=rule_signals,
            weighted_score=weighted_score,
            ai_reasoning=ai_reasoning,
            recommendation=recommendation,
            final_score=final_score,
            strength=weighted_score.strength,
            explanation=explanation,
            entry_price=entry_price,
            stop_loss=stop_loss,
            target_1=target_1,
            target_2=target_2
        )
        
        final_check = self._final_gatekeeper(signal, indicators, market_context)
        if not final_check['approved']:
            signal.rejection = SignalRejection(
                rejected=True,
                reason=final_check['reason'],
                score=final_score,
                failed_factors=final_check.get('failed_checks', [])
            )
            logger.info(f"Signal for {stock_symbol} rejected by gatekeeper: {final_check['reason']}")
            return signal
        
        logger.info(f"Generated signal: {stock_symbol} - {recommendation} ({final_score})")
        
        return signal
    
    def _identify_failed_factors(
        self,
        factors: List[FactorScore],
        threshold: float
    ) -> List[str]:
        """Identify which factors failed to meet threshold."""
        failed = []
        cumulative = 0.0
        for factor in sorted(factors, key=lambda x: x.contribution, reverse=True):
            cumulative += factor.contribution
            if cumulative < threshold * factor.weight:
                failed.append(factor.factor_name)
        return failed[:3]
    
    def _calculate_trade_levels(
        self,
        indicators: Dict[str, Any],
        ai_reasoning: Optional[AIReasoning]
    ) -> Tuple[float, float, float]:
        """Calculate trade levels from AI or indicators."""
        entry_price = indicators.get('close', 0)
        
        if ai_reasoning and ai_reasoning.stop_loss:
            try:
                stop_loss = float(
                    str(ai_reasoning.stop_loss)
                    .replace('₹', '')
                    .replace(',', '')
                )
                target_1 = float(
                    str(ai_reasoning.targets[0])
                    .replace('₹', '')
                    .replace(',', '')
                ) if ai_reasoning.targets else entry_price * 1.1
                target_2 = float(
                    str(ai_reasoning.targets[1])
                    .replace('₹', '')
                    .replace(',', '')
                ) if len(ai_reasoning.targets) > 1 else entry_price * 1.15
                return stop_loss, target_1, target_2
            except (ValueError, IndexError):
                pass
        
        atr = indicators.get('atr', entry_price * 0.02)
        stop_loss = entry_price - (atr * 2)
        target_1 = entry_price + (atr * 4)
        target_2 = entry_price + (atr * 6)
        
        return stop_loss, target_1, target_2
    
    def _combine_signals(
        self,
        weighted_score: WeightedScore,
        ai_reasoning: Optional[AIReasoning]
    ) -> Tuple[str, float, str]:
        """
        Combine weighted score and AI reasoning.
        
        AI gates instead of blindly blending.
        """
        base_score = weighted_score.final_score
        
        if not ai_reasoning:
            return (
                weighted_score.strength.replace('STRONG_', ''),
                base_score,
                f"Rule-based score: {base_score}"
            )
        
        if ai_reasoning.confidence < self.AI_CONFIDENCE_GATE:
            return (
                weighted_score.strength.replace('STRONG_', ''),
                base_score,
                f"AI confidence too low ({ai_reasoning.confidence}), using rule-based"
            )
        
        final_score = base_score
        recommendation = weighted_score.strength.replace('STRONG_', '')
        
        ai_sell = ai_reasoning.recommendation in ('SELL', 'STRONG_SELL')
        
        if ai_sell:
            if base_score >= self.AI_OVERRIDE_THRESHOLD:
                final_score = 50
                recommendation = 'NEUTRAL'
                explanation = f"Downgraded: AI SELL but strong technical ({base_score})"
            else:
                return (
                    'REJECTED',
                    base_score,
                    f"AI SELL + weak technical ({base_score})"
                )
        
        if ai_reasoning.recommendation == 'BUY' or ai_reasoning.recommendation == 'STRONG_BUY':
            if ai_reasoning.confidence >= 8:
                final_score = min(final_score + 10, 100)
        
        top_factors = sorted(
            weighted_score.factors,
            key=lambda x: x.contribution,
            reverse=True
        )[:3]
        
        explanation = f"Base: {weighted_score.strength}. "
        explanation += f"Top: {', '.join([f.factor_name for f in top_factors])}. "
        explanation += f"AI: {ai_reasoning.recommendation}({ai_reasoning.confidence})"
        
        return recommendation, round(final_score, 2), explanation
    
    def _final_gatekeeper(
        self,
        signal: CombinedSignal,
        indicators: Dict[str, Any],
        market_context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Final gatekeeper layer - where money is made.
        
        Checks:
        - Final score threshold
        - Risk-reward ratio
        - Volume ratio
        - Market condition alignment
        """
        failed_checks = []
        
        if signal.final_score < 65:
            failed_checks.append('low_score')
        
        try:
            risk = abs(signal.entry_price - signal.stop_loss)
            reward = abs(signal.target_1 - signal.entry_price)
            rr = reward / risk if risk > 0 else 0
            if rr < 1.5:
                failed_checks.append('low_rr')
        except:
            pass
        
        volume = indicators.get('volume', 0)
        volume_ma = indicators.get('volume_ma', 1)
        vol_ratio = volume / volume_ma if volume_ma > 0 else 0
        
        if self.strategy_tracker:
            adaptive_vol = getattr(
                self.strategy_tracker,
                'adaptive_filters',
                {}
            ).get('volume_ratio_min', 1.5)
            if vol_ratio < adaptive_vol:
                failed_checks.append('low_volume')
        else:
            if vol_ratio < 1.5:
                failed_checks.append('low_volume')
        
        mkt_ctx = self._parse_market_context(market_context)
        trend = mkt_ctx.get('trend', 'SIDEWAYS')
        
        if self.current_strategy == 'TREND' and trend == 'SIDEWAYS':
            failed_checks.append('wrong_market')
        elif self.current_strategy == 'VERC' and trend == 'SIDEWAYS':
            failed_checks.append('wrong_market')
        
        if failed_checks:
            return {
                'approved': False,
                'reason': f"Gatekeeper: {', '.join(failed_checks)}",
                'failed_checks': failed_checks
            }
        
        return {
            'approved': True,
            'reason': 'Approved',
            'failed_checks': []
        }


def create_reasoning_engine(
    config: Optional[Dict[str, Any]] = None,
    strategy_tracker: Optional[Any] = None
) -> ReasoningEngine:
    """Factory function to create reasoning engine."""
    return ReasoningEngine(config, strategy_tracker)