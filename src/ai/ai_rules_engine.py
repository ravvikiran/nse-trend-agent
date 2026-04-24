"""
AI-Driven Rules Engine
AI role: RANKING, FILTERING, CONFIDENCE ADJUSTMENT ONLY.
AI does NOT generate exact entry/SL/targets - these are deterministic.
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

STOP_LOSS_PERCENT = 0.02
TARGET_1_RR = 2.0
TARGET_2_RR = 3.0


SIGNAL_GENERATION_PROMPT = """You are an expert trading signal FILTER and RANKER for NSE (National Stock Exchange of India) stocks.

IMPORTANT - Your role is ONLY:
1. RANK stocks by quality (1-10)
2. FILTER out weak signals
3. ADJUST confidence based on historical performance

YOU MUST NOT:
- Generate exact entry prices
- Generate exact stop loss values  
- Generate exact targets
- These are calculated DETERMINISTICALLY by the system

SIGNAL FILTERING RULES (you must apply):

TREND Strategy:
- EMA alignment: EMA20 > EMA50 > EMA100 > EMA200 (bullish)
- Volume confirmation: Volume > Volume MA30
- Price above EMA50 confirms uptrend

VERC Strategy (Volume Expansion Range Compression):
- Range compression: (High - Low) / Price < 0.05 (5%)
- Volume expansion: Volume MA(5) > Volume MA(20)
- Relative volume > 1.3x
- Price breaking above compression

Risk Management (system handles these - do not suggest values):
- Stop loss: 2% below entry
- Target 1: 4% (1:2 RR)
- Target 2: 6% (1:3 RR)

Respond with structured JSON that can be parsed programmatically."""

def validate_signal(signal: Dict[str, Any]) -> bool:
    """Hard validation layer - reject invalid signals."""
    if not isinstance(signal, dict):
        return False
    
    entry = signal.get("entry_price", 0)
    sl = signal.get("stop_loss", 0)
    t1 = signal.get("target_1", 0)
    t2 = signal.get("target_2", 0)
    confidence = signal.get("confidence", 0)
    
    if entry <= 0 or sl <= 0 or t1 <= 0 or t2 <= 0:
        return False
    
    if sl >= entry:
        logger.warning(f"Invalid signal: SL {sl} >= entry {entry}")
        return False
    
    if t1 <= entry:
        logger.warning(f"Invalid signal: T1 {t1} <= entry {entry}")
        return False
    
    if t2 <= t1:
        logger.warning(f"Invalid signal: T2 {t2} <= T1 {t1}")
        return False
    
    if confidence < 1 or confidence > 10:
        logger.warning(f"Invalid signal: confidence {confidence} out of range")
        return False
    
    return True


def calculate_signal_levels(
    entry_price: float,
    strategy: str,
    ema50: float = 0,
    low: float = 0,
    atr: float = 0
) -> Dict[str, float]:
    """Deterministic signal level calculation."""
    sl_price = entry_price * (1 - STOP_LOSS_PERCENT)
    
    if strategy == "TREND" and ema50 > 0:
        sl_price = min(sl_price, ema50)
    elif strategy == "VERC" and low > 0:
        sl_price = min(sl_price, low * 0.98)
    
    t1_price = entry_price * (1 + STOP_LOSS_PERCENT * TARGET_1_RR)
    t2_price = entry_price * (1 + STOP_LOSS_PERCENT * TARGET_2_RR)
    
    return {
        "entry_price": round(entry_price, 2),
        "stop_loss": round(sl_price, 2),
        "target_1": round(t1_price, 2),
        "target_2": round(t2_price, 2),
        "risk_reward_1": TARGET_1_RR,
        "risk_reward_2": TARGET_2_RR
    }


def create_signal_evaluation_prompt(
    stock_data: Dict[str, Any],
    signal_context: Dict[str, Any]
) -> str:
    """
    Create prompt for AI to RANK and FILTER a stock signal.
    AI does NOT generate entry/SL/target - system calculates those.
    
    Args:
        stock_data: Stock technical data
        signal_context: Context from signal memory
        
    Returns:
        Formatted prompt for AI
    """
    symbol = stock_data.get('symbol', 'UNKNOWN')
    
    prev_signals = signal_context.get('previous_signals', [])
    active_signals = signal_context.get('active_signals', [])
    recent_outcomes = signal_context.get('recent_outcomes', [])
    win_rate = signal_context.get('overall_win_rate', 0)
    
    prompt = f"""RANK and FILTER signal for {symbol}

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

SIGNAL MEMORY:
- Active signals: {len(active_signals)}
- Previous signals: {len(prev_signals)}
- Overall win rate: {win_rate:.1f}%"""

    for outcome in recent_outcomes[:5]:
        prompt += f"\n- {outcome.get('outcome')}: {outcome.get('pnl_percent', 0):.1f}%"
    
    prompt += f"""

YOUR TASK: RANK and FILTER (NOT generate values)

Check:
1. Has recent signal? If YES → reject
2. Technical criteria met?
3. Risk-reward acceptable?

Respond JSON (system calculates entry/SL/target):
{{
    "signal_recommended": true/false,
    "confidence": 1-10,
    "strategy": "TREND/VERC/MTF/NONE",
    "reason": "brief reasoning",
    "adjust_confidence": -2 to +2 adjustment based on historical performance
}}

adjust_confidence: How much to adjust confidence based on this stock's historical performance."""


def create_batch_evaluation_prompt(
    stocks_data: List[Dict[str, Any]],
    excluded_stocks: List[str],
    signal_context: Dict[str, Any],
    max_signals: int = 5
) -> str:
    """
    Create prompt for AI to RANK and FILTER stocks (NOT generate signals).
    AI role: RANK stocks by quality, FILTER out weak ones.
    System calculates entry/SL/target deterministically.
    
    Args:
        stocks_data: List of stock technical data
        excluded_stocks: Stocks to exclude (recent signals)
        signal_context: Context from signal memory
        max_signals: Maximum signals to return
        
    Returns:
        Formatted prompt for AI
    """
    win_rate = signal_context.get('overall_win_rate', 0)
    recent_outcomes = signal_context.get('recent_outcomes', [])
    
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
    
    prompt = f"""RANK and FILTER {len(stocks_json)} NSE stocks. 
AI role: RANK by quality, FILTER weak signals.
DO NOT generate entry/SL/target - system calculates those DETERMINISTICALLY.

EXCLUDED STOCKS (has recent signals - SKIP these):
{', '.join(excluded_stocks) if excluded_stocks else 'None'}

OVERALL WIN RATE: {win_rate:.1f}%

RECENT OUTCOMES:
{recent_outcomes_text if recent_outcomes_text else 'No recent outcomes'}

STOCKS DATA:
{json.dumps(stocks_json, indent=2)}

TASK:
1. SKIP stocks in excluded_stocks
2. RANK stocks by quality (highest confidence first)
3. FILTER out weak signals (low confidence, poor indicators)
4. Return TOP {max_signals} ranked stocks

Response JSON (system calculates entry/SL/target):
[
    {{
        "rank": 1,
        "symbol": "STOCK",
        "signal_recommended": true/false,
        "strategy": "TREND/VERC/MTF/NONE",
        "confidence": 1-10,
        "reason": "brief reasoning"
    }},
    ... max {max_signals} items
]"""

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
    AI role: RANK, FILTER, CONFIDENCE ADJUSTMENT only.
    Entry/SL/target calculated deterministically.
    """
    
    def __init__(self, ai_analyzer=None, learning_layer=None):
        self.ai_analyzer = ai_analyzer
        self.system_prompt = SIGNAL_GENERATION_PROMPT
        self.learning_layer = learning_layer
        self._adaptive_filters = {}
    
    def set_learning_layer(self, learning_layer):
        """Connect learning layer for feedback loop."""
        self.learning_layer = learning_layer
        self._load_adaptive_filters()
    
    def _load_adaptive_filters(self):
        """Load filters from learning layer if available."""
        if self.learning_layer and hasattr(self.learning_layer, 'apply_recommended_filters'):
            try:
                result = self.learning_layer.apply_recommended_filters()
                self._adaptive_filters = result.get('new_filters', {})
                logger.info(f"Loaded adaptive filters: {self._adaptive_filters}")
            except Exception as e:
                logger.warning(f"Could not load adaptive filters: {e}")
    
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
        AI role: RANK and FILTER only.
        Entry/SL/target calculated deterministically.
        
        Args:
            stock_data: Stock technical data
            signal_context: Context from signal memory
            
        Returns:
            Signal recommendation dict
        """
        if self._apply_adaptive_filters(stock_data):
            logger.info(f"Stock {stock_data.get('symbol')} rejected by adaptive filters")
            return {
                'signal_recommended': False,
                'reason': 'Rejected by adaptive filters from learning',
                'confidence': 0
            }
        
        if not self.is_available():
            return self._basic_evaluation(stock_data)
        
        prompt = create_signal_evaluation_prompt(stock_data, signal_context)
        
        try:
            response = self.ai_analyzer.analyze(prompt, system_prompt=self.system_prompt)
            ranking = self._parse_ranking_response(response)
            
            if not ranking.get('signal_recommended', False):
                return {
                    'signal_recommended': False,
                    'reason': ranking.get('reason', 'AI filtered out'),
                    'confidence': ranking.get('confidence', 0),
                    'strategy': ranking.get('strategy', 'NONE')
                }
            
            base_confidence = ranking.get('confidence', 5)
            adjust = ranking.get('adjust_confidence', 0)
            final_confidence = max(1, min(10, base_confidence + adjust))
            
            strategy = ranking.get('strategy', 'TREND')
            entry_price = stock_data.get('price', 0)
            ema50 = stock_data.get('ema50', 0)
            low = stock_data.get('low', 0)
            
            levels = calculate_signal_levels(entry_price, strategy, ema50, low)
            
            signal = {
                'signal_recommended': True,
                'symbol': stock_data.get('symbol'),
                'strategy': strategy,
                'confidence': final_confidence,
                'reason': ranking.get('reason', f'{strategy} signal from AI ranking'),
                'entry_price': levels['entry_price'],
                'stop_loss': levels['stop_loss'],
                'target_1': levels['target_1'],
                'target_2': levels['target_2'],
                'risk_reward_ratio': f"1:{levels['risk_reward_1']}"
            }
            
            if not validate_signal(signal):
                logger.warning("Generated signal failed validation, using basic evaluation")
                return self._basic_evaluation(stock_data)
            
            return signal
            
        except Exception as e:
            logger.error(f"AI evaluation error: {e}")
            return self._basic_evaluation(stock_data)
    
    def _apply_adaptive_filters(self, stock_data: Dict[str, Any]) -> bool:
        """Apply adaptive filters from learning layer."""
        if not self._adaptive_filters:
            return False
        
        breakout = stock_data.get('breakout_strength', 0)
        volume = stock_data.get('volume_ratio', 0)
        
        min_breakout = self._adaptive_filters.get('breakout_strength_min', 0)
        min_volume = self._adaptive_filters.get('volume_ratio_min', 0)
        
        if min_breakout > 0 and breakout < min_breakout:
            return True
        if min_volume > 0 and volume < min_volume:
            return True
        
        return False
    
    def refresh_adaptive_filters(self):
        """Refresh adaptive filters from learning layer."""
        self._load_adaptive_filters()
    
    def evaluate_batch(
        self,
        stocks_data: List[Dict[str, Any]],
        excluded_stocks: List[str],
        signal_context: Dict[str, Any],
        max_signals: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Evaluate multiple stocks and return top signals.
        AI role: RANK and FILTER only.
        Entry/SL/target calculated deterministically.
        
        Args:
            stocks_data: List of stock data
            excluded_stocks: Stocks to exclude
            signal_context: Context from memory
            max_signals: Maximum signals to return
            
        Returns:
            List of signal recommendations
        """
        filtered_stocks = [s for s in stocks_data if not self._apply_adaptive_filters(s)]
        
        if not filtered_stocks:
            logger.info("All stocks filtered by adaptive filters")
            return []
        
        if not self.is_available():
            return self._basic_batch_filter(filtered_stocks, excluded_stocks, max_signals)
        
        prompt = create_batch_evaluation_prompt(
            filtered_stocks, excluded_stocks, signal_context, max_signals
        )
        
        try:
            response = self.ai_analyzer.analyze(prompt, system_prompt=self.system_prompt)
            rankings = self._parse_batch_ranking_response(response, max_signals)
            
            if not rankings:
                logger.warning("No rankings from AI, using basic filter")
                return self._basic_batch_filter(filtered_stocks, excluded_stocks, max_signals)
            
            signals = []
            for rank_data in rankings:
                if not rank_data.get('signal_recommended', False):
                    continue
                
                symbol = rank_data.get('symbol')
                stock = next((s for s in filtered_stocks if s.get('symbol') == symbol), None)
                
                if not stock:
                    continue
                
                base_confidence = rank_data.get('confidence', 5)
                final_confidence = max(1, min(10, base_confidence))
                
                strategy = rank_data.get('strategy', 'TREND')
                entry_price = stock.get('price', 0)
                ema50 = stock.get('ema50', 0)
                low = stock.get('low', 0)
                
                levels = calculate_signal_levels(entry_price, strategy, ema50, low)
                
                signal = {
                    'symbol': symbol,
                    'strategy': strategy,
                    'signal_recommended': True,
                    'confidence': final_confidence,
                    'reason': rank_data.get('reason', f'{strategy} from AI ranking'),
                    'entry_price': levels['entry_price'],
                    'stop_loss': levels['stop_loss'],
                    'target_1': levels['target_1'],
                    'target_2': levels['target_2'],
                    'risk_reward_ratio': f"1:{levels['risk_reward_1']}",
                    'rank': rank_data.get('rank', 0)
                }
                
                if validate_signal(signal):
                    signals.append(signal)
            
            if not signals:
                logger.warning("No signals passed validation, using basic filter")
                return self._basic_batch_filter(filtered_stocks, excluded_stocks, max_signals)
            
            return signals[:max_signals]
            
        except Exception as e:
            logger.error(f"AI batch evaluation error: {e}")
            return self._basic_batch_filter(filtered_stocks, excluded_stocks, max_signals)
    
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
                price = stock.get('price', 0) or 0
                signals.append({
                    'symbol': stock.get('symbol'),
                    'strategy': 'TREND',
                    'signal_recommended': True,
                    'reason': 'EMA alignment detected',
                    'confidence': 7,
                    'entry_price': price,
                    'stop_loss': ema50,
                    'target_1': price * 1.06,
                    'target_2': price * 1.10,
                    'risk_reward_ratio': '1:2'
                })
            
            if len(signals) >= max_signals:
                break
        
        return signals
    
    def _validate_signal(self, signal: Dict[str, Any]) -> bool:
        """Validate AI-generated signal for sanity."""
        if not isinstance(signal, dict):
            return False
        if signal.get("entry_price", 0) <= 0:
            return False
        if signal.get("stop_loss", 0) <= 0:
            return False
        if signal.get("target_1", 0) <= signal.get("entry_price", 0):
            return False
        confidence = signal.get("confidence", 0)
        if confidence < 1 or confidence > 10:
            return False
        return True
    
    def _parse_response(self, response: str) -> Dict[str, Any]:
        """Parse AI response to dict (legacy - for backward compat)."""
        try:
            import json
            start = response.find('{')
            end = response.rfind('}') + 1
            if start >= 0 and end > start:
                json_str = response[start:end]
                return json.loads(json_str)
        except Exception as e:
            logger.error(f"Error parsing response: {e}")
        
        return {'signal_recommended': False, 'reason': 'Parse error'}
    
    def _parse_ranking_response(self, response: str) -> Dict[str, Any]:
        """Parse AI ranking response for single stock."""
        try:
            import json
            start = response.find('{')
            end = response.rfind('}') + 1
            if start >= 0 and end > start:
                json_str = response[start:end]
                data = json.loads(json_str)
                return {
                    'signal_recommended': data.get('signal_recommended', False),
                    'confidence': data.get('confidence', 5),
                    'strategy': data.get('strategy', 'NONE'),
                    'reason': data.get('reason', ''),
                    'adjust_confidence': data.get('adjust_confidence', 0)
                }
        except Exception as e:
            logger.error(f"Error parsing ranking response: {e}")
        
        return {'signal_recommended': False, 'reason': 'Parse error', 'confidence': 0}
    
    def _parse_batch_response(
        self,
        response: str,
        max_signals: int
    ) -> List[Dict[str, Any]]:
        """Parse AI batch response to list (legacy - for backward compat)."""
        try:
            import json
            start = response.find('[')
            end = response.rfind(']') + 1
            if start >= 0 and end > start:
                json_str = response[start:end]
                signals = json.loads(json_str)
                return signals[:max_signals]
        except Exception as e:
            logger.error(f"Error parsing batch response: {e}")
        
        return []
    
    def _parse_batch_ranking_response(
        self,
        response: str,
        max_signals: int
    ) -> List[Dict[str, Any]]:
        """Parse AI batch ranking response."""
        try:
            import json
            start = response.find('[')
            end = response.rfind(']') + 1
            if start >= 0 and end > start:
                json_str = response[start:end]
                rankings = json.loads(json_str)
                return rankings[:max_signals]
        except Exception as e:
            logger.error(f"Error parsing batch ranking response: {e}")
        
        return []


def create_ai_rules_engine(ai_analyzer=None, learning_layer=None) -> AIRulesEngine:
    """Factory to create AI rules engine."""
    return AIRulesEngine(ai_analyzer, learning_layer)