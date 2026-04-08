"""
AI-Driven Rules Engine
Uses AI for decision making instead of hardcoded app logic.
Passes signal context and outcomes to AI for better signal generation.
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are an expert trading signal generation AI for NSE (National Stock Exchange of India) stocks.

Your role is to:
1. Analyze stocks for potential buy signals based on technical indicators and market conditions
2. Consider previous signal performance when making decisions
3. Apply trading rules to generate high-quality signals
4. Provide entry, stop loss, and targets for each signal

SIGNAL GENERATION RULES (you must apply these):

TREND Strategy:
- EMA alignment: EMA20 > EMA50 > EMA100 > EMA200 (bullish)
- Volume confirmation: Volume > Volume MA30
- Price above EMA50 confirms uptrend
- Confidence: 1-10 scale based on EMA alignment strength

VERC Strategy (Volume Expansion Range Compression):
- Range compression: (High - Low) / Price < 0.05 (5%)
- Volume expansion: Volume MA(5) > Volume MA(20)
- Relative volume > 1.3x
- Price breaking above compression
- Minimum confidence: 7/10

Risk Management:
- Stop loss: Below recent low or EMA50 (for trend), compression low (for VERC)
- Target 1: 1:2 risk-reward
- Target 2: 1:3 risk-reward

IMPORTANT - Signal Memory:
You have access to previous signal data. Use this to:
- AVOID generating signals for stocks with recent signals (within 30 days)
- Consider past performance when evaluating similar setups
- Adjust confidence based on historical win rate

Respond with structured JSON that can be parsed programmatically."""


def create_signal_evaluation_prompt(
    stock_data: Dict[str, Any],
    signal_context: Dict[str, Any]
) -> str:
    """
    Create prompt for AI to evaluate a stock signal.
    
    Args:
        stock_data: Stock technical data
        signal_context: Context from signal memory
        
    Returns:
        Formatted prompt for AI
    """
    symbol = stock_data.get('symbol', 'UNKNOWN')
    
    # Build previous signals info
    prev_signals = signal_context.get('previous_signals', [])
    active_signals = signal_context.get('active_signals', [])
    recent_outcomes = signal_context.get('recent_outcomes', [])
    win_rate = signal_context.get('overall_win_rate', 0)
    
    prompt = f"""Evaluate signal for {symbol}

CURRENT STOCK DATA:
- Price: ₹{stock_data.get('price', 0):.2f}
- EMA20: ₹{stock_data.get('ema20', 0):.2f}
- EMA50: ₹{stock_data.get('ema50', 0):.2f}
- EMA100: ₹{stock_data.get('ema100', 0):.2f}
- EMA200: ₹{stock_data.get('ema200', 0):.2f}
- RSI(14): {stock_data.get('rsi', 0):.1f}
- ATR(14): ₹{stock_data.get('atr', 0):.2f}
- Volume: {stock_data.get('volume', 0):,}
- Volume MA30: {stock_data.get('volume_ma30', 0):,}
- Volume Ratio: {stock_data.get('volume_ratio', 0):.2f}x

SIGNAL MEMORY CONTEXT:
- Stock has {len(active_signals)} active signal(s)
- Stock has {len(prev_signals)} previous signal(s)
- Overall win rate: {win_rate:.1f}%

RECENT OUTCOMES (use to adjust confidence):"""
    
    for outcome in recent_outcomes[:5]:
        prompt += f"\n- {outcome.get('outcome')}: {outcome.get('pnl_percent', 0):.1f}%"
    
    prompt += f"""

Evaluate if this stock qualifies for a BUY signal.

Consider:
1. Are there recent signals for this stock (check memory - if yes, DECLINE signal)
2. Do technical indicators meet criteria?
3. Does risk-reward ratio qualify (minimum 1:2)?
4. What's your confidence level (1-10)?

Respond in this JSON format:
{{
    "signal_recommended": true/false,
    "reason": "brief reasoning",
    "entry_price": 0.00,
    "stop_loss": 0.00,
    "target_1": 0.00,
    "target_2": 0.00,
    "confidence": 1-10,
    "risk_reward_ratio": "1:X",
    "strategy": "TREND/VERC/MTF",
    "reasoning_details": "detailed reasoning"
}}

If signal_recommended is false, you can omit other fields except reason."""
    
    return prompt


def create_batch_evaluation_prompt(
    stocks_data: List[Dict[str, Any]],
    excluded_stocks: List[str],
    signal_context: Dict[str, Any],
    max_signals: int = 5
) -> str:
    """
    Create prompt for AI to evaluate multiple stocks and rank them.
    
    Args:
        stocks_data: List of stock technical data
        excluded_stocks: Stocks to exclude (recent signals)
        signal_context: Context from signal memory
        max_signals: Maximum signals to recommend
        
    Returns:
        Formatted prompt for AI
    """
    win_rate = signal_context.get('overall_win_rate', 0)
    recent_outcomes = signal_context.get('recent_outcomes', [])
    
    # Format stocks data
    stocks_json = []
    for stock in stocks_data:
        if stock.get('symbol') in excluded_stocks:
            continue
        stocks_json.append({
            'symbol': stock.get('symbol'),
            'price': stock.get('price', 0),
            'ema20': stock.get('ema20', 0),
            'ema50': stock.get('ema50', 0),
            'ema100': stock.get('ema100', 0),
            'ema200': stock.get('ema200', 0),
            'rsi': stock.get('rsi', 0),
            'volume_ratio': stock.get('volume_ratio', 0),
            'atr': stock.get('atr', 0)
        })
    
    recent_outcomes_text = ""
    for outcome in recent_outcomes[:10]:
        recent_outcomes_text += f"- {outcome.get('symbol')}: {outcome.get('outcome')} ({outcome.get('pnl_percent', 0):.1f}%)\n"
    
    prompt = f"""You are evaluating {len(stocks_json)} NSE stocks to generate the best {max_signals} trading signals.

EXCLUDED STOCKS (these have recent signals - DO NOT recommend):
{', '.join(excluded_stocks) if excluded_stocks else 'None'}

OVERALL WIN RATE: {win_rate:.1f}%

RECENT SIGNAL OUTCOMES:
{recent_outcomes_text if recent_outcomes_text else 'No recent outcomes available'}

STOCKS DATA (JSON format):
{json.dumps(stocks_json, indent=2)}

Your task:
1. SKIP any stock in excluded_stocks list
2. Apply signal generation rules:
   - TREND: EMA alignment (EMA20>EMA50>EMA100>EMA200), Volume > Volume MA30
   - VERC: Range compression <5%, Volume expansion >1.3x
3. Rank stocks by confidence and signal quality
4. Return TOP {max_signals} signals only

Respond as JSON array:
[
    {{
        "rank": 1,
        "symbol": "STOCK",
        "signal_recommended": true/false,
        "strategy": "TREND/VERC/MTF",
        "reason": "brief reasoning",
        "entry_price": 0.00,
        "stop_loss": 0.00,
        "target_1": 0.00,
        "target_2": 0.00,
        "confidence": 1-10,
        "risk_reward_ratio": "1:X"
    }},
    ... max {max_signals} items
]

If fewer than {max_signals} qualify, return only those that do. If none qualify, return empty array."""
    
    return prompt


def create_signal_summary_prompt(
    signals: List[Dict[str, Any]],
    active_count: int,
    performance: Dict[str, Any]
) -> str:
    """
    Create summary of generated signals for notification.
    
    Args:
        signals: List of signals to summarize
        active_count: Number of active signals
        performance: Performance metrics
        
    Returns:
        Formatted message
    """
    win_rate = performance.get('win_rate', 0)
    avg_pnl = performance.get('avg_pnl', 0)
    
    if not signals:
        return "No signals met criteria today. AI evaluated all stocks against rules and memory."
    
    message = f"📊 AI-Driven Signal Summary\n"
    message += f"• Active Signals: {active_count}\n"
    message += f"• Win Rate: {win_rate:.1f}%\n"
    message += f"• Avg P&L: {avg_pnl:.1f}%\n"
    message += f"• New Signals: {len(signals)}\n\n"
    
    for i, sig in enumerate(signals, 1):
        message += f"{i}. {sig.get('symbol')} - {sig.get('strategy')} @ ₹{sig.get('entry_price', 0):.2f}\n"
        message += f"   SL: ₹{sig.get('stop_loss', 0):.2f} | T1: ₹{sig.get('target_1', 0):.2f}\n"
        message += f"   Confidence: {sig.get('confidence', 0)}/10 | {sig.get('risk_reward_ratio', 'N/A')}\n\n"
    
    return message


class AIRulesEngine:
    """
    AI-driven rules engine for signal generation.
    Uses AI instead of hardcoded logic.
    """
    
    def __init__(self, ai_analyzer=None):
        self.ai_analyzer = ai_analyzer
        self.system_prompt = SYSTEM_PROMPT
    
    def is_available(self) -> bool:
        """Check if AI is available."""
        return self.ai_analyzer is not None and hasattr(self.ai_analyzer, 'is_available') and self.ai_analyzer.is_available()
    
    def evaluate_stock(
        self,
        stock_data: Dict[str, Any],
        signal_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Evaluate a single stock for signal.
        
        Args:
            stock_data: Stock technical data
            signal_context: Context from signal memory
            
        Returns:
            Signal recommendation dict
        """
        if not self.is_available():
            # Fallback to basic logic if AI unavailable
            return self._basic_evaluation(stock_data)
        
        prompt = create_signal_evaluation_prompt(stock_data, signal_context)
        
        try:
            response = self.ai_analyzer.analyze(prompt, system_prompt=self.system_prompt)
            return self._parse_response(response)
        except Exception as e:
            logger.error(f"AI evaluation error: {e}")
            return self._basic_evaluation(stock_data)
    
    def evaluate_batch(
        self,
        stocks_data: List[Dict[str, Any]],
        excluded_stocks: List[str],
        signal_context: Dict[str, Any],
        max_signals: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Evaluate multiple stocks and return top signals.
        
        Args:
            stocks_data: List of stock data
            excluded_stocks: Stocks to exclude
            signal_context: Context from memory
            max_signals: Maximum signals to return
            
        Returns:
            List of signal recommendations
        """
        if not self.is_available():
            # Fallback to basic filtering
            return self._basic_batch_filter(stocks_data, excluded_stocks, max_signals)
        
        prompt = create_batch_evaluation_prompt(
            stocks_data, excluded_stocks, signal_context, max_signals
        )
        
        try:
            response = self.ai_analyzer.analyze(prompt, system_prompt=self.system_prompt)
            return self._parse_batch_response(response, max_signals)
        except Exception as e:
            logger.error(f"AI batch evaluation error: {e}")
            return self._basic_batch_filter(stocks_data, excluded_stocks, max_signals)
    
    def _basic_evaluation(self, stock_data: Dict[str, Any]) -> Dict[str, Any]:
        """Basic fallback evaluation."""
        return {
            'signal_recommended': False,
            'reason': 'AI unavailable, using basic rules',
            'confidence': 0
        }
    
    def _basic_batch_filter(
        self,
        stocks_data: List[Dict[str, Any]],
        excluded_stocks: List[str],
        max_signals: int
    ) -> List[Dict[str, Any]]:
        """Basic fallback batch filtering."""
        signals = []
        for stock in stocks_data:
            if stock.get('symbol') in excluded_stocks:
                continue
            # Simple scoring based on EMA alignment
            ema20 = stock.get('ema20', 0)
            ema50 = stock.get('ema50', 0)
            ema100 = stock.get('ema100', 0)
            ema200 = stock.get('ema200', 0)
            
            if ema20 > ema50 > ema100 > ema200:
                signals.append({
                    'symbol': stock.get('symbol'),
                    'strategy': 'TREND',
                    'signal_recommended': True,
                    'reason': 'EMA alignment detected',
                    'confidence': 7,
                    'entry_price': stock.get('price'),
                    'stop_loss': ema50,
                    'target_1': stock.get('price') * 1.06,
                    'target_2': stock.get('price') * 1.10,
                    'risk_reward_ratio': '1:2'
                })
            
            if len(signals) >= max_signals:
                break
        
        return signals
    
    def _parse_response(self, response: str) -> Dict[str, Any]:
        """Parse AI response to dict."""
        try:
            import json
            # Try to find JSON in response
            start = response.find('{')
            end = response.rfind('}') + 1
            if start >= 0 and end > start:
                json_str = response[start:end]
                return json.loads(json_str)
        except Exception as e:
            logger.error(f"Error parsing response: {e}")
        
        return {'signal_recommended': False, 'reason': 'Parse error'}
    
    def _parse_batch_response(
        self,
        response: str,
        max_signals: int
    ) -> List[Dict[str, Any]]:
        """Parse AI batch response to list."""
        try:
            import json
            # Try to find JSON array
            start = response.find('[')
            end = response.rfind(']') + 1
            if start >= 0 and end > start:
                json_str = response[start:end]
                signals = json.loads(json_str)
                return signals[:max_signals]
        except Exception as e:
            logger.error(f"Error parsing batch response: {e}")
        
        return []


def create_ai_rules_engine(ai_analyzer=None) -> AIRulesEngine:
    """Factory to create AI rules engine."""
    return AIRulesEngine(ai_analyzer)