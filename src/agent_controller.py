"""
Agent Controller - Makes the Scanner Agentic AI
Transforms the rule-based scanner into an autonomous agent that:
1. Reasons about market context using LLM
2. Decides actions autonomously (scan, analyze, wait)
3. Explains decisions in natural language
4. Self-corrects based on outcomes
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class AgentAction(Enum):
    """Actions the agent can take."""
    SCAN = "scan"
    ANALYZE = "analyze" 
    WAIT = "wait"
    ADJUST_STRATEGY = "adjust_strategy"
    SEND_ALERT = "send_alert"
    MONITOR = "monitor"


class MarketRegime(Enum):
    """Market regime classification."""
    BULLISH = "bullish"
    BEARISH = "bearish"
    SIDEWAYS = "sideways"
    VOLATILE = "volatile"
    UNKNOWN = "unknown"


@dataclass
class AgentDecision:
    """Agent's decision with reasoning."""
    action: AgentAction
    confidence: int
    reasoning: str
    market_regime: MarketRegime = MarketRegime.UNKNOWN
    recommended_strategies: List[str] = field(default_factory=list)
    scan_interval_minutes: int = 15
    parameters: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class AgentExplanation:
    """Natural language explanation for agent's decision."""
    decision: str
    market_analysis: str
    factors_considered: List[str]
    confidence: int
    natural_language: str
    
    def to_string(self) -> str:
        return self.natural_language


class AgentController:
    """
    Agent Controller - Makes the scanner Agentic.
    
    Transforms rule-based execution into autonomous decision-making:
    1. LLM-powered market analysis
    2. Dynamic action selection
    3. Natural language explanations
    4. Self-correction from feedback
    """
    
    SYSTEM_PROMPT = """You are an Expert Stock Trading Agent that monitors Indian stock markets (NSE).
Your role is to:
1. Analyze market conditions in real-time
2. Decide whether to scan for signals, wait, or adjust strategy
3. Provide clear reasoning for your decisions
4. Explain your thinking in plain English

You have access to:
- Market data (NIFTY 50, sector performance)
- Technical indicators (EMA, RSI, Volume, ATR)
- Historical signal performance
- Trade outcomes

Your decisions should be:
- Based on probability of success
- Risk-aware
- Transparent in reasoning

Respond in JSON format for system parsing."""

    def __init__(
        self,
        ai_analyzer,
        market_context_engine=None,
        strategy_optimizer=None,
        trade_journal=None
    ):
        self.ai_analyzer = ai_analyzer
        self.market_context_engine = market_context_engine
        self.strategy_optimizer = strategy_optimizer
        self.trade_journal = trade_journal
        
        self._decision_history: List[AgentDecision] = []
        self._last_decision: Optional[AgentDecision] = None
        self._consecutive_no_signals = 0
        self._consecutive_wins = 0
        self._consecutive_losses = 0
        
        logger.info("AgentController initialized - Scanner is now Agentic")
    
    def is_available(self) -> bool:
        """Check if agent can make decisions."""
        return self.ai_analyzer is not None and hasattr(self.ai_analyzer, 'is_available') and self.ai_analyzer.is_available()
    
    def analyze_and_decide(
        self,
        market_data: Dict[str, Any],
        active_signals: List[Dict[str, Any]] = None
    ) -> AgentDecision:
        """
        Main agent decision loop.
        
        Args:
            market_data: Current market data
            active_signals: Currently active signals/trades
            
        Returns:
            AgentDecision with action and reasoning
        """
        if not self.is_available():
            return self._default_decision()
        
        try:
            nifty_data = market_data.get('nifty', {})
            sector_data = market_data.get('sectors', {})
            
            decision = self._llm_decide(market_data, active_signals or [])
            
            self._decision_history.append(decision)
            self._last_decision = decision
            
            self._track_outcomes(active_signals or [])
            
            return decision
            
        except Exception as e:
            logger.error(f"Agent decision error: {e}")
            return self._default_decision()
    
    def _default_decision(self) -> AgentDecision:
        """Default decision when agent unavailable."""
        return AgentDecision(
            action=AgentAction.SCAN,
            confidence=5,
            reasoning="Default mode - no LLM available",
            market_regime=MarketRegime.UNKNOWN,
            recommended_strategies=['TREND', 'VERC'],
            scan_interval_minutes=15
        )
    
    def _llm_decide(
        self,
        market_data: Dict[str, Any],
        active_signals: List[Dict[str, Any]]
    ) -> AgentDecision:
        """Use LLM to make decisions."""
        prompt = self._create_decision_prompt(market_data, active_signals)
        
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]
        
        try:
            response = self.ai_analyzer.analyze_stock(
                symbol="MARKET_ANALYSIS",
                market_data=market_data
            )
            
            decision = self._parse_llm_response(response, market_data)
            
            logger.info(f"Agent decision: {decision.action.value} - {decision.reasoning}")
            
            return decision
            
        except Exception as e:
            logger.error(f"LLM decision error: {e}")
            
            return AgentDecision(
                action=AgentAction.SCAN,
                confidence=6,
                reasoning="Fallback to rule-based decision",
                market_regime=self._detect_regime_fallback(market_data),
                recommended_strategies=['TREND', 'VERC'],
                scan_interval_minutes=15
            )
    
    def _create_decision_prompt(
        self,
        market_data: Dict[str, Any],
        active_signals: List[Dict[str, Any]]
    ) -> str:
        """Create prompt for LLM decision."""
        nifty = market_data.get('nifty', {})
        
        nifty_price = nifty.get('price', 0)
        nifty_change = nifty.get('change_pct', 0)
        
        active_count = len(active_signals)
        win_streak = self._consecutive_wins
        loss_streak = self._consecutive_losses
        
        recent_decisions = ""
        if self._decision_history:
            recent = self._decision_history[-3:]
            recent_decisions = "Recent decisions:\n"
            for d in recent:
                recent_decisions += f"- {d.action.value}: {d.reasoning[:50]}\n"
        
        return f"""Analyze current market conditions and decide what action to take.

CURRENT MARKET:
- NIFTY 50: ₹{nifty_price} ({nifty_change:+.2f}%)
- Active signals: {active_count}
- Win streak: {win_streak}
- Loss streak: {loss_streak}

{recent_decisions}

Market regime: {self._last_decision.market_regime.value if self._last_decision else 'unknown'}
Consecutive no-signals: {self._consecutive_no_signals}

What action should the agent take?
- SCAN: Scan for new signals
- ANALYZE: Analyze existing signals in detail
- WAIT: Don't scan yet (market not favorable)
- ADJUST_STRATEGY: Modify strategy parameters
- MONITOR: Just monitor active trades

Respond in JSON:
{{
    "action": "SCAN",
    "confidence": 1-10,
    "reasoning": "why you chose this action",
    "market_regime": "bullish/bearish/sideways/volatile",
    "recommended_strategies": ["TREND", "VERC"],
    "scan_interval_minutes": 15,
    "parameters": {{}}
}}"""
    
    def _parse_llm_response(
        self,
        response: str,
        market_data: Dict[str, Any]
    ) -> AgentDecision:
        """Parse LLM response to AgentDecision."""
        try:
            data = json.loads(response)
            
            action_str = data.get('action', 'SCAN').upper()
            action = AgentAction(action_str) if action_str in [a.value for a in AgentAction] else AgentAction.SCAN
            
            regime_str = data.get('market_regime', 'unknown').upper()
            regime = MarketRegime(regime_str) if regime_str in [r.value for r in MarketRegime] else MarketRegime.UNKNOWN
            
            return AgentDecision(
                action=action,
                confidence=int(data.get('confidence', 5)),
                reasoning=data.get('reasoning', 'No reasoning provided'),
                market_regime=regime,
                recommended_strategies=data.get('recommended_strategies', ['TREND', 'VERC']),
                scan_interval_minutes=int(data.get('scan_interval_minutes', 15)),
                parameters=data.get('parameters', {})
            )
            
        except json.JSONDecodeError:
            return self._default_decision()
    
    def _detect_regime_fallback(self, market_data: Dict[str, Any]) -> MarketRegime:
        """Fallback regime detection."""
        nifty = market_data.get('nifty', {})
        change = nifty.get('change_pct', 0)
        
        if change > 0.5:
            return MarketRegime.BULLISH
        elif change < -0.5:
            return MarketRegime.BEARISH
        elif abs(change) < 0.3:
            return MarketRegime.SIDEWAYS
        else:
            return MarketRegime.VOLATILE
    
    def _track_outcomes(self, active_signals: List[Dict[str, Any]]) -> None:
        """Track outcomes for self-correction."""
        if not active_signals:
            self._consecutive_no_signals += 1
        else:
            self._consecutive_no_signals = 0
    
    def explain_signal(
        self,
        signal: Any,
        market_data: Dict[str, Any]
    ) -> AgentExplanation:
        """
        Generate natural language explanation for a signal.
        
        Args:
            signal: The signal to explain
            market_data: Current market context
            
        Returns:
            AgentExplanation with natural language reasoning
        """
        if not self.is_available():
            return self._rule_based_explanation(signal)
        
        try:
            prompt = self._create_explanation_prompt(signal, market_data)
            
            ticker = signal.ticker if hasattr(signal, 'ticker') else signal.stock_symbol
            
            explanation_response = self.ai_analyzer.quick_analyze(
                symbol=ticker,
                price=signal.indicators.get('close', 0) if hasattr(signal, 'indicators') else 0,
                ema20=signal.indicators.get('ema20', 0) if hasattr(signal, 'indicators') else 0,
                ema50=signal.indicators.get('ema50', 0) if hasattr(signal, 'indicators') else 0,
                ema100=signal.indicators.get('ema100', 0) if hasattr(signal, 'indicators') else 0,
                ema200=signal.indicators.get('ema200', 0) if hasattr(signal, 'indicators') else 0,
                vol_ratio=signal.volume_ratio if hasattr(signal, 'volume_ratio') else 0,
                rsi=signal.indicators.get('rsi', 50) if hasattr(signal, 'indicators') else 50
            )
            
            return AgentExplanation(
                decision=f"{signal.strategy_type} SIGNAL for {ticker}",
                market_analysis=f"Market regime: {self._last_decision.market_regime.value if self._last_decision else 'unknown'}",
                factors_considered=[
                    f"Strategy Score: {signal.strategy_score:.1f}" if hasattr(signal, 'strategy_score') else "N/A",
                    f"Volume Ratio: {signal.volume_ratio:.1f}x" if hasattr(signal, 'volume_ratio') else "N/A",
                    f"Quality: {signal.quality}" if hasattr(signal, 'quality') else "N/A"
                ],
                confidence=int(getattr(signal, 'final_score', 5)),
                natural_language=explanation_response
            )
            
        except Exception as e:
            logger.error(f"Explanation error: {e}")
            return self._rule_based_explanation(signal)
    
    def _create_explanation_prompt(
        self,
        signal: Any,
        market_data: Dict[str, Any]
    ) -> str:
        """Create explanation prompt."""
        ticker = signal.ticker if hasattr(signal, 'ticker') else signal.stock_symbol
        
        return f"""Explain why {ticker} generated a {signal.strategy_type} signal.
        
Signal details:
- Strategy Score: {signal.strategy_score if hasattr(signal, 'strategy_score') else 'N/A'}
- Volume Ratio: {signal.volume_ratio if hasattr(signal, 'volume_ratio') else 'N/A'}
- Quality: {signal.quality if hasattr(signal, 'quality') else 'N/A'}
- Market Context: {signal.market_context if hasattr(signal, 'market_context') else 'N/A'}

Explain in 1-2 sentences why this is a good opportunity."""
    
    def _rule_based_explanation(self, signal: Any) -> AgentExplanation:
        """Rule-based explanation fallback."""
        ticker = signal.ticker if hasattr(signal, 'ticker') else signal.stock_symbol
        strategy = signal.strategy_type if hasattr(signal, 'strategy_type') else 'UNKNOWN'
        
        factors = []
        if hasattr(signal, 'strategy_score'):
            factors.append(f"Strategy Score: {signal.strategy_score:.1f}")
        if hasattr(signal, 'volume_ratio'):
            factors.append(f"Volume Ratio: {signal.volume_ratio:.1f}x")
        if hasattr(signal, 'quality'):
            factors.append(f"Quality: {signal.quality}")
        
        nl = f"{ticker} generated {strategy} signal"
        if factors:
            nl += f". Key factors: {', '.join(factors)}"
        
        return AgentExplanation(
            decision=f"{strategy} SIGNAL for {ticker}",
            market_analysis=f"Market context: {getattr(signal, 'market_context', 'N/A')}",
            factors_considered=factors,
            confidence=int(getattr(signal, 'final_score', 5)),
            natural_language=nl
        )
    
    def self_correct(
        self,
        trade_outcome: str,
        trade_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Self-correct based on trade outcome.
        
        Args:
            trade_outcome: WIN, LOSS, or TIMEOUT
            trade_data: Trade details
            
        Returns:
            Corrections/adjustments to apply
        """
        if trade_outcome == 'WIN':
            self._consecutive_wins += 1
            self._consecutive_losses = 0
        elif trade_outcome == 'LOSS':
            self._consecutive_losses += 1
            self._consecutive_wins = 0
        else:
            self._consecutive_wins = 0
            self._consecutive_losses = 0
        
        corrections = {
            'win_streak': self._consecutive_wins,
            'loss_streak': self._consecutive_losses,
            'adjustments': []
        }
        
        if self._consecutive_losses >= 3:
            corrections['adjustments'].append({
                'type': 'increase_strictness',
                'reason': '3+ consecutive losses detected'
            })
        
        if self._consecutive_wins >= 5:
            corrections['adjustments'].append({
                'type': 'maintain_current_strategy',
                'reason': '5+ consecutive wins - strategy working'
            })
        
        return corrections
    
    def get_agent_state(self) -> Dict[str, Any]:
        """Get current agent state."""
        return {
            'available': self.is_available(),
            'last_decision': {
                'action': self._last_decision.action.value if self._last_decision else None,
                'confidence': self._last_decision.confidence if self._last_decision else None,
                'reasoning': self._last_decision.reasoning if self._last_decision else None,
                'market_regime': self._last_decision.market_regime.value if self._last_decision else None
            } if self._last_decision else None,
            'win_streak': self._consecutive_wins,
            'loss_streak': self._consecutive_losses,
            'total_decisions': len(self._decision_history)
        }


def create_agent_controller(
    ai_analyzer,
    market_context_engine=None,
    strategy_optimizer=None,
    trade_journal=None
) -> AgentController:
    """Factory function to create Agent Controller."""
    return AgentController(
        ai_analyzer=ai_analyzer,
        market_context_engine=market_context_engine,
        strategy_optimizer=strategy_optimizer,
        trade_journal=trade_journal
    )