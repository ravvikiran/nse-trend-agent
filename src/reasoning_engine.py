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
    raw_score: float  # 0-100
    weight: float  # 0-1
    contribution: float  # raw_score * weight
    details: str = ""


@dataclass
class WeightedScore:
    """Combined weighted score result."""
    final_score: float  # 0-100
    strength: str  # STRONG_BUY, BUY, NEUTRAL, SELL, STRONG_SELL
    factors: List[FactorScore] = field(default_factory=list)
    threshold_met: bool = True


@dataclass
class AIReasoning:
    """AI-powered reasoning result."""
    recommendation: str  # BUY, SELL, HOLD
    confidence: int  # 1-10
    reasoning: str
    risk_reward_ratio: str
    entry_zone: str
    stop_loss: str
    targets: List[str]
    market_context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CombinedSignal:
    """Complete signal with all reasoning components."""
    signal_id: str
    stock_symbol: str
    timestamp: datetime
    
    # Rule-based signals (existing)
    rule_signals: Dict[str, Any]
    
    # Weighted scoring
    weighted_score: WeightedScore
    
    # AI reasoning
    ai_reasoning: Optional[AIReasoning] = None
    
    # Combined output
    recommendation: str = ""
    final_score: float = 0.0
    strength: str = ""
    explanation: str = ""
    
    # Additional data
    entry_price: float = 0.0
    stop_loss: float = 0.0
    target_1: float = 0.0
    target_2: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
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


class ReasoningEngine:
    """
    Hybrid reasoning engine that combines:
    1. Rule-based algorithms (existing)
    2. Weighted scoring
    3. AI reasoning
    """
    
    # Default weights (can be loaded from config)
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
    
    # Score thresholds
    THRESHOLDS = {
        'min_signal_score': 60,
        'strong_buy_min': 80,
        'neutral_max': 59,
        'sell_max': 39
    }
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the reasoning engine.
        
        Args:
            config: Optional configuration dict with weights and thresholds
        """
        self.config = config or {}
        
        # Load weights from config or use defaults
        weights_config = self.config.get('weights', {})
        self.weights = weights_config if weights_config else self.DEFAULT_WEIGHTS
        
        # Load thresholds
        threshold_config = self.config.get('thresholds', {})
        self.thresholds = {**self.THRESHOLDS, **threshold_config}
        
        # Validate weights sum to 1.0
        self._validate_weights()
        
        logger.info(f"ReasoningEngine initialized with weights: {self.weights}")
    
    def _validate_weights(self) -> None:
        """Validate that weights sum to 1.0."""
        total = sum(self.weights.values())
        if abs(total - 1.0) > 0.01:
            logger.warning(f"Weights sum to {total}, normalizing to 1.0")
            for key in self.weights:
                self.weights[key] /= total
    
    def calculate_weighted_score(
        self,
        indicators: Dict[str, Any],
        rule_signals: Dict[str, Any],
        verc_data: Optional[Dict[str, Any]] = None,
        market_context: Optional[Dict[str, Any]] = None
    ) -> WeightedScore:
        """
        Calculate weighted score from various factors.
        
        Args:
            indicators: Technical indicator values
            rule_signals: Rule-based signal outputs
            verc_data: VERC strategy data
            market_context: Market context (nifty trend, etc.)
            
        Returns:
            WeightedScore object
        """
        factors = []
        total_score = 0.0
        
        # 1. EMA Alignment Score (15%)
        ema_score, ema_details = self._score_ema_alignment(indicators)
        ema_factor = FactorScore(
            factor_name='ema_alignment',
            raw_score=ema_score,
            weight=self.weights['ema_alignment'],
            contribution=ema_score * self.weights['ema_alignment'],
            details=ema_details
        )
        factors.append(ema_factor)
        total_score += ema_factor.contribution
        
        # 2. Volume Confirmation Score (15%)
        volume_score, volume_details = self._score_volume_confirmation(indicators)
        volume_factor = FactorScore(
            factor_name='volume_confirmation',
            raw_score=volume_score,
            weight=self.weights['volume_confirmation'],
            contribution=volume_score * self.weights['volume_confirmation'],
            details=volume_details
        )
        factors.append(volume_factor)
        total_score += volume_factor.contribution
        
        # 3. RSI Position Score (10%)
        rsi_score, rsi_details = self._score_rsi_position(indicators)
        rsi_factor = FactorScore(
            factor_name='rsi_position',
            raw_score=rsi_score,
            weight=self.weights['rsi_position'],
            contribution=rsi_score * self.weights['rsi_position'],
            details=rsi_details
        )
        factors.append(rsi_factor)
        total_score += rsi_factor.contribution
        
        # 4. ATR Volatility Score (10%)
        atr_score, atr_details = self._score_atr_volatility(indicators)
        atr_factor = FactorScore(
            factor_name='atr_volatility',
            raw_score=atr_score,
            weight=self.weights['atr_volatility'],
            contribution=atr_score * self.weights['atr_volatility'],
            details=atr_details
        )
        factors.append(atr_factor)
        total_score += atr_factor.contribution
        
        # 5. VERC Score (20%)
        verc_score, verc_details = self._score_verc(verc_data)
        verc_factor = FactorScore(
            factor_name='verc_score',
            raw_score=verc_score,
            weight=self.weights['verc_score'],
            contribution=verc_score * self.weights['verc_score'],
            details=verc_details
        )
        factors.append(verc_factor)
        total_score += verc_factor.contribution
        
        # 6. RSI Divergence Score (10%)
        div_score, div_details = self._score_rsi_divergence(indicators, rule_signals)
        div_factor = FactorScore(
            factor_name='rsi_divergence',
            raw_score=div_score,
            weight=self.weights['rsi_divergence'],
            contribution=div_score * self.weights['rsi_divergence'],
            details=div_details
        )
        factors.append(div_factor)
        total_score += div_factor.contribution
        
        # 7. Market Context Score (10%)
        market_score, market_details = self._score_market_context(market_context)
        market_factor = FactorScore(
            factor_name='market_context',
            raw_score=market_score,
            weight=self.weights['market_context'],
            contribution=market_score * self.weights['market_context'],
            details=market_details
        )
        factors.append(market_factor)
        total_score += market_factor.contribution
        
        # 8. Price Momentum Score (10%)
        momentum_score, momentum_details = self._score_price_momentum(indicators)
        momentum_factor = FactorScore(
            factor_name='price_momentum',
            raw_score=momentum_score,
            weight=self.weights['price_momentum'],
            contribution=momentum_score * self.weights['price_momentum'],
            details=momentum_details
        )
        factors.append(momentum_factor)
        total_score += momentum_factor.contribution
        
        # Determine strength category
        strength = self._get_strength(total_score)
        threshold_met = total_score >= self.thresholds['min_signal_score']
        
        return WeightedScore(
            final_score=round(total_score, 2),
            strength=strength,
            factors=factors,
            threshold_met=threshold_met
        )
    
    def _score_ema_alignment(self, indicators: Dict[str, Any]) -> Tuple[float, str]:
        """Score EMA alignment: 20 > 50 > 100 > 200"""
        ema_20 = indicators.get('ema_20', 0)
        ema_50 = indicators.get('ema_50', 0)
        ema_100 = indicators.get('ema_100', 0)
        ema_200 = indicators.get('ema_200', 0)
        
        if ema_20 == 0 or ema_50 == 0:
            return 50, "Insufficient EMA data"
        
        # Perfect alignment: 20 > 50 > 100 > 200
        score = 50  # Base score
        
        if ema_20 > ema_50:
            score += 15
        if ema_50 > ema_100:
            score += 15
        if ema_100 > ema_200:
            score += 20
        
        details = f"EMA20>{ema_20:.2f} > EMA50>{ema_50:.2f} > EMA100>{ema_100:.2f} > EMA200>{ema_200:.2f}"
        
        return min(score, 100), details
    
    def _score_volume_confirmation(self, indicators: Dict[str, Any]) -> Tuple[float, str]:
        """Score volume confirmation: Volume > Volume MA"""
        volume = indicators.get('volume', 0)
        volume_ma = indicators.get('volume_ma', 0)
        
        if volume_ma == 0:
            return 50, "Insufficient volume data"
        
        volume_ratio = volume / volume_ma
        
        # Score based on volume ratio
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
        
        details = f"Volume: {volume_ratio:.2f}x (Vol={volume:,}, MA30={volume_ma:,})"
        
        return score, details
    
    def _score_rsi_position(self, indicators: Dict[str, Any]) -> Tuple[float, str]:
        """Score RSI position: Optimal 40-70 for buy"""
        rsi = indicators.get('rsi', 50)
        
        if rsi == 0:
            return 50, "Insufficient RSI data"
        
        # Optimal buy zone: 40-70
        if 40 <= rsi <= 70:
            # Best in 50-65 range
            if 50 <= rsi <= 65:
                score = 100
            else:
                score = 80
        elif rsi < 30:
            # Oversold - potential reversal
            score = 70
        elif rsi > 70:
            # Overbought
            score = 40
        elif rsi < 40:
            score = 60
        else:
            score = 50
        
        details = f"RSI(14): {rsi:.2f} - {'Oversold' if rsi < 40 else 'Overbought' if rsi > 70 else 'Neutral' if rsi > 30 and rsi < 70 else 'Neutral'}"
        
        return score, details
    
    def _score_atr_volatility(self, indicators: Dict[str, Any]) -> Tuple[float, str]:
        """Score ATR volatility: Lower is better (more stable)"""
        atr = indicators.get('atr', 0)
        close = indicators.get('close', 0)
        
        if atr == 0 or close == 0:
            return 50, "Insufficient ATR data"
        
        atr_percent = (atr / close) * 100
        
        # Lower ATR% = higher score (stable price)
        if atr_percent <= 1.5:
            score = 100
        elif atr_percent <= 2.0:
            score = 80
        elif atr_percent <= 2.5:
            score = 60
        elif atr_percent <= 3.5:
            score = 40
        else:
            score = 20
        
        details = f"ATR: {atr_percent:.2f}% ({atr:.2f})"
        
        return score, details
    
    def _score_verc(self, verc_data: Optional[Dict[str, Any]]) -> Tuple[float, str]:
        """Score VERC signal if available"""
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
        """Score RSI divergence (price vs RSI)"""
        rsi = indicators.get('rsi', 50)
        
        # Check if trend detector found bullish divergence
        has_divergence = rule_signals.get('bullish_divergence', False)
        
        if has_divergence:
            score = 90
            details = "Bullish RSI divergence detected"
        else:
            # Default neutral
            score = 50
            details = "No divergence detected"
        
        return score, details
    
    def _score_market_context(self, market_context: Optional[Dict[str, Any]]) -> Tuple[float, str]:
        """Score market context alignment"""
        if not market_context:
            return 50, "No market context"
        
        nifty_trend = market_context.get('nifty_trend', 'UNKNOWN')
        
        if nifty_trend == 'BULLISH':
            score = 100
        elif nifty_trend == 'NEUTRAL':
            score = 60
        elif nifty_trend == 'BEARISH':
            score = 30
        else:
            score = 50
        
        details = f"Nifty 50 Trend: {nifty_trend}"
        
        return score, details
    
    def _score_price_momentum(self, indicators: Dict[str, Any]) -> Tuple[float, str]:
        """Score recent price momentum"""
        # Calculate from recent price changes if available
        close = indicators.get('close', 0)
        # This would need more historical data - simplified for now
        
        # Check if price is above EMA 20 (immediate momentum)
        ema_20 = indicators.get('ema_20', 0)
        
        if close > ema_20 > 0:
            score = 80
            details = f"Price above EMA20 (Momentum: +{((close-ema_20)/ema_20*100):.2f}%)"
        elif close > 0:
            score = 50
            details = "Price below EMA20"
        else:
            score = 50
            details = "Insufficient price data"
        
        return score, details
    
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
            return 'BUY'  # Default to BUY for scores 40-59
    
    def create_combined_signal(
        self,
        stock_symbol: str,
        indicators: Dict[str, Any],
        rule_signals: Dict[str, Any],
        ai_analysis: Optional[Dict[str, Any]] = None,
        verc_data: Optional[Dict[str, Any]] = None,
        market_context: Optional[Dict[str, Any]] = None
    ) -> Optional[CombinedSignal]:
        """
        Create a complete combined signal.
        
        Args:
            stock_symbol: Stock ticker
            indicators: Technical indicators
            rule_signals: Rule-based signals
            ai_analysis: AI analysis result (if available)
            verc_data: VERC data (if available)
            market_context: Market context
            
        Returns:
            CombinedSignal or None if signal doesn't meet threshold
        """
        # Calculate weighted score
        weighted_score = self.calculate_weighted_score(
            indicators, rule_signals, verc_data, market_context
        )
        
        # Check threshold
        if not weighted_score.threshold_met:
            logger.debug(f"Signal for {stock_symbol} below threshold ({weighted_score.final_score})")
            return None
        
        # Parse AI analysis if available
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
        
        # Determine final recommendation
        recommendation, final_score, explanation = self._combine_signals(
            weighted_score, ai_reasoning
        )
        
        # Get trade levels from AI or calculate from indicators
        entry_price = indicators.get('close', 0)
        if ai_reasoning and ai_reasoning.stop_loss:
            try:
                stop_loss = float(ai_reasoning.stop_loss.replace('₹', '').replace(',', ''))
                target_1 = float(ai_reasoning.targets[0].replace('₹', '').replace(',', '')) if ai_reasoning.targets else entry_price * 1.1
                target_2 = float(ai_reasoning.targets[1].replace('₹', '').replace(',', '')) if len(ai_reasoning.targets) > 1 else entry_price * 1.15
            except (ValueError, IndexError):
                # Calculate from ATR if AI values not parseable
                atr = indicators.get('atr', entry_price * 0.02)
                stop_loss = entry_price - (atr * 2)
                target_1 = entry_price + (atr * 4)
                target_2 = entry_price + (atr * 6)
        else:
            # Calculate from ATR
            atr = indicators.get('atr', entry_price * 0.02)
            stop_loss = entry_price - (atr * 2)
            target_1 = entry_price + (atr * 4)
            target_2 = entry_price + (atr * 6)
        
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
        
        logger.info(f"Generated signal: {stock_symbol} - {recommendation} ({final_score})")
        
        return signal
    
    def _combine_signals(
        self,
        weighted_score: WeightedScore,
        ai_reasoning: Optional[AIReasoning]
    ) -> Tuple[str, float, str]:
        """
        Combine weighted score and AI reasoning into final recommendation.
        
        Returns:
            Tuple of (recommendation, final_score, explanation)
        """
        # Get weights from config - support rule_based vs ai_reasoning percentages
        # If weights config has rule_based and ai_reasoning, use them directly
        rule_weight = self.config.get('weights', {}).get('rule_based', 70) / 100.0
        ai_weight = self.config.get('weights', {}).get('ai_reasoning', 30) / 100.0
        
        # Normalize if needed
        total = rule_weight + ai_weight
        if total > 0:
            rule_weight = rule_weight / total
            ai_weight = ai_weight / total
        
        # Start with weighted score
        base_score = weighted_score.final_score
        
        # Adjust with AI confidence if available
        if ai_reasoning:
            ai_score = ai_reasoning.confidence * 10  # Convert 1-10 to 10-100
            final_score = (base_score * rule_weight) + (ai_score * ai_weight)
            
            # AI recommendation alignment
            if ai_reasoning.recommendation == 'SELL' or ai_reasoning.recommendation == 'STRONG_SELL':
                final_score = min(final_score, 40)
                recommendation = 'SELL'
            elif ai_reasoning.recommendation == 'HOLD':
                # Keep weighted score but cap at neutral
                final_score = min(final_score, 60)
                recommendation = 'BUY' if final_score >= 60 else 'NEUTRAL'
            else:
                recommendation = weighted_score.strength.replace('STRONG_', '')
        else:
            final_score = base_score
            recommendation = weighted_score.strength.replace('STRONG_', '')
        
        # Generate explanation
        top_factors = sorted(
            weighted_score.factors,
            key=lambda x: x.contribution,
            reverse=True
        )[:3]
        
        explanation = f"Signal strength: {weighted_score.strength}. "
        explanation += f"Top factors: {', '.join([f.factor_name for f in top_factors])}. "
        
        if ai_reasoning:
            explanation += f"AI assessment: {ai_reasoning.recommendation} (confidence: {ai_reasoning.confidence}/10). "
        
        explanation += f"Risk-reward: {ai_reasoning.risk_reward_ratio if ai_reasoning else '1:2'}"
        
        return recommendation, round(final_score, 2), explanation


def create_reasoning_engine(config: Optional[Dict[str, Any]] = None) -> ReasoningEngine:
    """Factory function to create reasoning engine."""
    return ReasoningEngine(config)