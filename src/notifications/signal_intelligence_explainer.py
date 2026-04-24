"""
Signal Intelligence Explainer (SIE)
Makes the agent UNDERSTAND what it's signaling through:
1. Detailed reasoning breakdown
2. Self-validation checks
3. Pattern recognition & learning
"""

import logging
import json
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class SignalValidationCheck:
    """Individual validation checkpoint."""
    check_name: str
    passed: bool
    score: float  # 0-10 scale
    reason: str
    critical: bool = False  # If failed, signal is rejected


@dataclass
class ReasoningChain:
    """Chain of reasoning: Why this signal was generated."""
    primary_reason: str  # Main factor causing the signal
    supporting_reasons: List[str] = field(default_factory=list)  # Secondary confirmations
    counter_indicators: List[str] = field(default_factory=list)  # Things working against it
    confidence_factors: Dict[str, float] = field(default_factory=dict)  # Individual confidence scores
    final_confidence: float = 0.0  # 0-100%


@dataclass
class PatternSignature:
    """Fingerprint of a signal type for learning."""
    pattern_type: str  # e.g., "TREND_ALIGNED_BULLISH", "BREAKOUT_ON_VOLUME"
    market_regime: str  # BULLISH, BEARISH, NEUTRAL, VOLATILE
    technical_setup: str  # e.g., "EMA_Perfect_Order + RSI_Bullish"
    momentum_level: str  # STRONG, MODERATE, WEAK
    volume_confirmation: bool
    ai_confidence: int  # 1-10


@dataclass
class SignalIntelligence:
    """Complete signal with full intelligence."""
    signal_id: str
    symbol: str
    timestamp: datetime
    
    # Core signal
    recommendation: str  # BUY/SELL/HOLD
    entry_price: float
    stop_loss: float
    targets: List[float]
    
    # Understanding layer
    reasoning_chain: ReasoningChain
    validation_checks: List[SignalValidationCheck] = field(default_factory=list)
    pattern_signature: Optional[PatternSignature] = None
    
    # Self-assessment
    agent_confidence: float = 0.0  # Agent's own confidence 0-100%
    signal_quality: str = "MEDIUM"  # LOW, MEDIUM, HIGH, VERY_HIGH
    explanation_text: str = ""  # Human-readable explanation
    
    # Learning-enabled
    signal_type: str = ""  # For pattern matching
    success_rate_for_pattern: float = 0.0  # Historical success of this pattern type
    
    is_valid: bool = True
    rejection_reason: str = ""


class SignalIntelligenceExplainer:
    """
    Makes every signal UNDERSTANDABLE.
    
    Core functions:
    1. Break down REASONING: Why this signal was generated
    2. VALIDATE before sending: Does this make sense?
    3. LEARN from outcomes: Which patterns work?
    """
    
    def __init__(self, trade_journal=None, strategy_optimizer=None):
        self.trade_journal = trade_journal
        self.strategy_optimizer = strategy_optimizer
        
        # Pattern database: Track success rates by pattern type
        self.pattern_success_db: Dict[str, Dict[str, Any]] = {}
        self.load_pattern_database()
        
        logger.info("SignalIntelligenceExplainer initialized")
    
    def load_pattern_database(self):
        """Load pattern success rates from trade journal."""
        if not self.trade_journal:
            return
        
        try:
            closed_trades = self.trade_journal.get_closed_trades(limit=500)
            
            pattern_stats = defaultdict(lambda: {
                'total': 0,
                'wins': 0,
                'losses': 0,
                'avg_rr': 0,
                'win_rate': 0
            })
            
            for trade in closed_trades:
                signal_type = trade.get('signal_type', 'UNKNOWN')
                pattern_stats[signal_type]['total'] += 1
                
                if trade.get('outcome') == 'WIN':
                    pattern_stats[signal_type]['wins'] += 1
                else:
                    pattern_stats[signal_type]['losses'] += 1
                
                rr = trade.get('risk_reward_ratio', 0)
                stats = pattern_stats[signal_type]
                stats['avg_rr'] = (stats['avg_rr'] * (stats['total'] - 1) + rr) / stats['total']
                stats['win_rate'] = (stats['wins'] / stats['total'] * 100) if stats['total'] > 0 else 0
            
            self.pattern_success_db = dict(pattern_stats)
            logger.info(f"Loaded pattern database: {len(self.pattern_success_db)} patterns tracked")
            
        except Exception as e:
            logger.warning(f"Could not load pattern database: {e}")
    
    def explain_signal(
        self,
        combined_signal: Any,  # From reasoning_engine
        market_data: Dict[str, Any],
        signal_type: str = "TREND_ALIGNED"
    ) -> SignalIntelligence:
        """
        Convert a signal into an INTELLIGENT, EXPLAINED signal.
        
        This is where the agent explains what it's doing.
        """
        signal_id = combined_signal.signal_id
        
        # Step 1: Build reasoning chain
        reasoning_chain = self._build_reasoning_chain(
            combined_signal,
            market_data,
            signal_type
        )
        
        # Step 2: Create pattern signature
        pattern_sig = self._create_pattern_signature(
            combined_signal,
            market_data,
            signal_type
        )
        
        # Step 3: Run validation checks
        validation_checks = self._run_validation_checks(
            combined_signal,
            reasoning_chain,
            pattern_sig
        )
        
        # Step 4: Calculate agent confidence
        agent_confidence = self._calculate_agent_confidence(
            validation_checks,
            reasoning_chain,
            pattern_sig
        )
        
        # Step 5: Determine signal quality
        signal_quality = self._assess_signal_quality(
            agent_confidence,
            validation_checks
        )
        
        # Step 6: Get historical success rate for this pattern
        success_rate = self.pattern_success_db.get(
            signal_type, 
            {}
        ).get('win_rate', 0)
        
        # Step 7: Generate explanation text
        explanation_text = self._generate_explanation(
            combined_signal,
            reasoning_chain,
            validation_checks,
            pattern_sig,
            agent_confidence
        )
        
        # Step 8: Determine if signal is valid
        is_valid, rejection_reason = self._final_validation(
            validation_checks,
            agent_confidence,
            signal_quality
        )
        
        # Create intelligence object
        intelligence = SignalIntelligence(
            signal_id=signal_id,
            symbol=combined_signal.stock_symbol,
            timestamp=combined_signal.timestamp,
            
            recommendation=combined_signal.recommendation,
            entry_price=combined_signal.entry_price,
            stop_loss=combined_signal.stop_loss,
            targets=[combined_signal.target_1, combined_signal.target_2],
            
            reasoning_chain=reasoning_chain,
            validation_checks=validation_checks,
            pattern_signature=pattern_sig,
            
            agent_confidence=agent_confidence,
            signal_quality=signal_quality,
            explanation_text=explanation_text,
            
            signal_type=signal_type,
            success_rate_for_pattern=success_rate,
            
            is_valid=is_valid,
            rejection_reason=rejection_reason
        )
        
        logger.info(
            f"Signal {signal_id} explained: "
            f"Quality={signal_quality}, Confidence={agent_confidence:.1f}%, "
            f"Valid={is_valid}"
        )
        
        return intelligence
    
    def _build_reasoning_chain(
        self,
        combined_signal: Any,
        market_data: Dict[str, Any],
        signal_type: str
    ) -> ReasoningChain:
        """Build the chain of reasoning: why is this signal being generated?"""
        
        weighted_score = combined_signal.weighted_score
        ai_reasoning = combined_signal.ai_reasoning
        
        # Identify primary reason (highest scoring factor)
        primary_reason = "Unknown"
        supporting_reasons = []
        counter_indicators = []
        confidence_factors = {}
        
        if hasattr(weighted_score, 'factors') and weighted_score.factors:
            # Sort by contribution
            sorted_factors = sorted(
                weighted_score.factors,
                key=lambda x: x.contribution,
                reverse=True
            )
            
            if sorted_factors:
                primary = sorted_factors[0]
                primary_reason = f"{primary.factor_name} (score: {primary.raw_score:.1f})"
                confidence_factors[primary.factor_name] = primary.raw_score
                
                # Supporting factors
                for factor in sorted_factors[1:4]:
                    if factor.contribution > 0:
                        supporting_reasons.append(
                            f"{factor.factor_name} (+{factor.contribution:.1f})"
                        )
                        confidence_factors[factor.factor_name] = factor.raw_score
        
        # Check for counter-indicators
        nifty_trend = market_data.get('nifty_trend', 'UNKNOWN')
        if combined_signal.recommendation == 'BUY' and nifty_trend == 'BEARISH':
            counter_indicators.append("Buying against NIFTY downtrend (contrarian)")
        
        # AI reasoning integration
        if ai_reasoning:
            supporting_reasons.insert(
                0,
                f"AI validation: {ai_reasoning.confidence}/10 confidence"
            )
            confidence_factors['AI_Confidence'] = ai_reasoning.confidence
        
        # Market regime factor
        market_regime = market_data.get('market_regime', 'UNKNOWN')
        if market_regime == 'BULLISH' and combined_signal.recommendation == 'BUY':
            supporting_reasons.append("Aligned with BULLISH market regime")
            confidence_factors['Market_Alignment'] = 8.0
        
        # Calculate final confidence from components
        if confidence_factors:
            final_confidence = sum(confidence_factors.values()) / len(confidence_factors)
        else:
            final_confidence = weighted_score.final_score
        
        return ReasoningChain(
            primary_reason=primary_reason,
            supporting_reasons=supporting_reasons,
            counter_indicators=counter_indicators,
            confidence_factors=confidence_factors,
            final_confidence=min(final_confidence, 100)
        )
    
    def _create_pattern_signature(
        self,
        combined_signal: Any,
        market_data: Dict[str, Any],
        signal_type: str
    ) -> PatternSignature:
        """Create a fingerprint of this signal for pattern learning."""
        
        weighted_score = combined_signal.weighted_score
        
        # Determine technical setup from factors
        technical_setup = "Unknown"
        if hasattr(weighted_score, 'factors'):
            top_factors = [f.factor_name for f in weighted_score.factors[:3] if f.raw_score > 60]
            technical_setup = " + ".join(top_factors) if top_factors else "Mixed"
        
        # Momentum level
        momentum_level = "WEAK"
        if weighted_score.final_score >= 80:
            momentum_level = "STRONG"
        elif weighted_score.final_score >= 70:
            momentum_level = "MODERATE"
        
        # Volume confirmation
        volume_confirmation = weighted_score.final_score >= 70
        
        # AI confidence
        ai_confidence = 5
        if combined_signal.ai_reasoning:
            ai_confidence = combined_signal.ai_reasoning.confidence
        
        return PatternSignature(
            pattern_type=signal_type,
            market_regime=market_data.get('market_regime', 'UNKNOWN'),
            technical_setup=technical_setup,
            momentum_level=momentum_level,
            volume_confirmation=volume_confirmation,
            ai_confidence=ai_confidence
        )
    
    def _run_validation_checks(
        self,
        combined_signal: Any,
        reasoning_chain: ReasoningChain,
        pattern_sig: PatternSignature
    ) -> List[SignalValidationCheck]:
        """Run validation checks: does this signal make sense?"""
        
        checks = []
        
        # Check 1: Minimum score threshold
        min_score = 60
        checks.append(SignalValidationCheck(
            check_name="Minimum Score",
            passed=combined_signal.final_score >= min_score,
            score=combined_signal.final_score,
            reason=f"Score {combined_signal.final_score:.1f} vs threshold {min_score}",
            critical=True
        ))
        
        # Check 2: Risk-Reward Ratio
        try:
            risk = abs(combined_signal.entry_price - combined_signal.stop_loss)
            reward = abs(combined_signal.target_1 - combined_signal.entry_price)
            rr = reward / risk if risk > 0 else 0
            
            checks.append(SignalValidationCheck(
                check_name="Risk-Reward Ratio",
                passed=rr >= 1.5,
                score=min(rr * 10, 10),
                reason=f"R:R is 1:{rr:.2f} (min 1:1.5 required)",
                critical=True
            ))
        except Exception as e:
            logger.warning(f"Could not calculate R:R: {e}")
        
        # Check 3: AI Confidence (if available)
        if combined_signal.ai_reasoning:
            ai_conf = combined_signal.ai_reasoning.confidence
            checks.append(SignalValidationCheck(
                check_name="AI Confidence",
                passed=ai_conf >= 6,
                score=ai_conf,
                reason=f"AI confidence {ai_conf}/10",
                critical=False
            ))
        
        # Check 4: Pattern Success Rate
        if pattern_sig.pattern_type in self.pattern_success_db:
            success_rate = self.pattern_success_db[pattern_sig.pattern_type]['win_rate']
            checks.append(SignalValidationCheck(
                check_name="Pattern Success",
                passed=success_rate >= 40,  # At least 40% win rate
                score=success_rate,
                reason=f"This pattern wins {success_rate:.1f}% of the time",
                critical=False
            ))
        
        # Check 5: No contradicting counter-indicators
        counter_score = 10 - len(reasoning_chain.counter_indicators)
        checks.append(SignalValidationCheck(
            check_name="Counter-Indicators",
            passed=len(reasoning_chain.counter_indicators) <= 1,
            score=counter_score,
            reason=f"{len(reasoning_chain.counter_indicators)} counter-indicator(s)",
            critical=False
        ))
        
        # Check 6: Momentum alignment
        if pattern_sig.momentum_level == 'STRONG':
            score = 10
        elif pattern_sig.momentum_level == 'MODERATE':
            score = 7
        else:
            score = 5
        
        checks.append(SignalValidationCheck(
            check_name="Momentum Quality",
            passed=pattern_sig.momentum_level in ['STRONG', 'MODERATE'],
            score=score,
            reason=f"Momentum is {pattern_sig.momentum_level}",
            critical=False
        ))
        
        return checks
    
    def _calculate_agent_confidence(
        self,
        validation_checks: List[SignalValidationCheck],
        reasoning_chain: ReasoningChain,
        pattern_sig: PatternSignature
    ) -> float:
        """Calculate agent's own confidence in the signal."""
        
        # Weight components
        check_score = sum(c.score for c in validation_checks) / len(validation_checks) if validation_checks else 50
        reasoning_confidence = reasoning_chain.final_confidence
        pattern_factor = 5 if pattern_sig.pattern_type != 'Unknown' else 3
        
        # Weighted average
        agent_confidence = (
            check_score * 0.4 +
            reasoning_confidence * 0.4 +
            pattern_factor * 0.2
        )
        
        return min(max(agent_confidence, 0), 100)
    
    def _assess_signal_quality(
        self,
        agent_confidence: float,
        validation_checks: List[SignalValidationCheck]
    ) -> str:
        """Assess overall signal quality."""
        
        critical_failures = [c for c in validation_checks if c.critical and not c.passed]
        
        if critical_failures:
            return "LOW"
        
        if agent_confidence >= 85:
            return "VERY_HIGH"
        elif agent_confidence >= 75:
            return "HIGH"
        elif agent_confidence >= 60:
            return "MEDIUM"
        else:
            return "LOW"
    
    def _generate_explanation(
        self,
        combined_signal: Any,
        reasoning_chain: ReasoningChain,
        validation_checks: List[SignalValidationCheck],
        pattern_sig: PatternSignature,
        agent_confidence: float
    ) -> str:
        """Generate human-readable explanation of the signal."""
        
        lines = []
        
        # Header
        lines.append(f"🤖 SIGNAL INTELLIGENCE REPORT")
        lines.append(f"Signal: {combined_signal.recommendation} on {combined_signal.stock_symbol}")
        lines.append(f"Agent Confidence: {agent_confidence:.1f}%")
        lines.append("")
        
        # Why this signal
        lines.append("📊 WHY THIS SIGNAL:")
        lines.append(f"• Primary: {reasoning_chain.primary_reason}")
        for reason in reasoning_chain.supporting_reasons[:2]:
            lines.append(f"• Supporting: {reason}")
        
        if reasoning_chain.counter_indicators:
            lines.append("⚠️ CAUTIONS:")
            for counter in reasoning_chain.counter_indicators:
                lines.append(f"• {counter}")
        
        lines.append("")
        
        # Validation results
        lines.append("✅ VALIDATION CHECKS:")
        for check in validation_checks:
            status = "✓" if check.passed else "✗"
            lines.append(f"{status} {check.check_name}: {check.reason}")
        
        lines.append("")
        
        # Pattern analysis
        lines.append("🎯 PATTERN ANALYSIS:")
        lines.append(f"Type: {pattern_sig.pattern_type}")
        lines.append(f"Market: {pattern_sig.market_regime}")
        lines.append(f"Momentum: {pattern_sig.momentum_level}")
        
        lines.append("")
        lines.append(f"Entry: {combined_signal.entry_price:.2f}")
        lines.append(f"Stop Loss: {combined_signal.stop_loss:.2f}")
        lines.append(f"Target 1: {combined_signal.target_1:.2f}")
        
        return "\n".join(lines)
    
    def _final_validation(
        self,
        validation_checks: List[SignalValidationCheck],
        agent_confidence: float,
        signal_quality: str
    ) -> Tuple[bool, str]:
        """Final gatekeeper: should we send this signal?"""
        
        # Critical checks must pass
        critical_failures = [c for c in validation_checks if c.critical and not c.passed]
        if critical_failures:
            reason = f"Critical check failed: {critical_failures[0].check_name}"
            return False, reason
        
        # Very low confidence rejection
        if agent_confidence < 40:
            return False, "Agent confidence too low"
        
        # Signal quality must be at least MEDIUM
        if signal_quality == "LOW":
            return False, "Signal quality too low"
        
        return True, ""


def create_signal_intelligence_explainer(
    trade_journal=None,
    strategy_optimizer=None
) -> SignalIntelligenceExplainer:
    """Factory function."""
    return SignalIntelligenceExplainer(trade_journal, strategy_optimizer)
