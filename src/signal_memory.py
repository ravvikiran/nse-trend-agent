"""
Signal Memory - Deduplication and Outcome Tracking
Stores all signals and checks for duplicates before generating new ones.
Tracks signal outcomes and passes context to AI for better decision making.
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Set, Tuple
from dataclasses import dataclass, field, asdict
from collections import defaultdict
import math

logger = logging.getLogger(__name__)

DATA_DIR = 'data'

DEFAULT_CAPITAL = 100000
RISK_PER_TRADE = 0.01


@dataclass
class SignalOutcome:
    """Outcome of a completed signal."""
    signal_id: str
    stock_symbol: str
    signal_type: str
    entry_price: float
    target_price: float
    sl_price: float
    outcome: str
    pnl_percent: float
    days_active: int
    generated_at: str
    completed_at: Optional[str] = None


@dataclass
class SignalContext:
    """Context passed to AI for signal generation."""
    stock_symbol: str
    previous_signals: List[Dict[str, Any]] = field(default_factory=list)
    active_signals: List[Dict[str, Any]] = field(default_factory=list)
    recent_outcomes: List[Dict[str, Any]] = field(default_factory=list)
    overall_win_rate: float = 0.0
    ai_reasoning_enabled: bool = True
    trade_journal_insights: List[Dict[str, Any]] = field(default_factory=list)
    factor_performance: Dict[str, float] = field(default_factory=dict)
    failed_factors: List[str] = field(default_factory=list)
    success_factors: List[str] = field(default_factory=list)


@dataclass
class TradeSetup:
    """Complete trade setup with entry, target, stop loss, and position size."""
    stock_symbol: str
    signal_type: str
    entry_price: float
    target_price: float
    stop_loss: float
    position_size: int
    risk_amount: float
    risk_percent: float
    reward_risk: float
    quality_score: float
    strategy_weight: float


class SignalMemory:
    """
    Memory system for signals:
    - Stores all generated signals
    - Checks for duplicates with outcome-based cooldown
    - Tracks outcomes for learning
    - Provides context to AI for decision making
    """
    
    STOCK_DEDUP_DAYS = 7
    PHASE_BASED_DEDUP = True
    
    COOLDOWN_BY_OUTCOME = {
        'TARGET_HIT': 5,
        'SL_HIT': 15,
        'TIMEOUT': 10,
        'CANCELLED': 5,
    }
    
    STRATEGY_MIN_SCORES = {
        'TREND': 7,
        'VERC': 6,
        'MTF': 6,
        'Momentum': 7,
    }
    
    DEFAULT_STRATEGY_WEIGHTS = {
        'TREND': 1.0,
        'VERC': 0.8,
        'MTF': 0.7,
        'Momentum': 0.9,
    }

    def __init__(self, data_dir: str = DATA_DIR, capital: float = DEFAULT_CAPITAL):
        self.data_dir = data_dir
        self.capital = capital
        self._ensure_data_dir()
        
        self.all_signals = self._load_all_signals()
        self.active_signals = self._load_active_signals()
        self.outcomes = self._load_outcomes()
        self.strategy_weights = self.DEFAULT_STRATEGY_WEIGHTS.copy()
        
        logger.info(f"SignalMemory initialized. Total signals: {len(self.all_signals)}, Active: {len(self.active_signals)}")
    
    def _ensure_data_dir(self):
        os.makedirs(self.data_dir, exist_ok=True)
    
    def _get_all_signals_path(self):
        return os.path.join(self.data_dir, 'memory_all_signals.json')
    
    def _get_active_signals_path(self):
        return os.path.join(self.data_dir, 'signals_active.json')
    
    def _get_outcomes_path(self):
        return os.path.join(self.data_dir, 'memory_outcomes.json')
    
    def _load_all_signals(self) -> List[Dict[str, Any]]:
        """Load all signals from memory."""
        filepath = self._get_all_signals_path()
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                    return data.get('signals', [])
            except Exception as e:
                logger.error(f"Error loading all signals: {e}")
                return []
        return []
    
    def _save_all_signals(self):
        """Save all signals to memory (atomic write)."""
        filepath = self._get_all_signals_path()
        data = {
            'version': '1.0',
            'last_updated': datetime.now().isoformat(),
            'signals': self.all_signals
        }
        try:
            tmp_path = filepath + ".tmp"
            with open(tmp_path, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            os.replace(tmp_path, filepath)
        except Exception as e:
            logger.error(f"Error saving all signals: {e}")
    
    def _load_active_signals(self) -> Dict[str, Dict[str, Any]]:
        """Load active signals."""
        filepath = self._get_active_signals_path()
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                    return data.get('signals', {})
            except Exception as e:
                logger.error(f"Error loading active signals: {e}")
                return {}
        return {}
    
    def _load_outcomes(self) -> List[Dict[str, Any]]:
        """Load completed signal outcomes."""
        filepath = self._get_outcomes_path()
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                    return data.get('outcomes', [])
            except Exception as e:
                logger.error(f"Error loading outcomes: {e}")
                return []
        return []
    
    def _save_outcomes(self):
        """Save outcomes."""
        filepath = self._get_outcomes_path()
        data = {
            'version': '1.0',
            'last_updated': datetime.now().isoformat(),
            'outcomes': self.outcomes
        }
        try:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error saving outcomes: {e}")
    
    def get_outcome_based_cooldown(self, stock_symbol: str) -> int:
        """
        Get cooldown days based on last outcome.
        
        Returns:
            Cooldown days based on outcome (winners repeat, losers wait longer)
        """
        for sig in reversed(self.all_signals):
            if sig.get('stock_symbol') == stock_symbol:
                outcome = sig.get('outcome')
                if outcome in self.COOLDOWN_BY_OUTCOME:
                    logger.debug(f"Cooldown for {stock_symbol}: {self.COOLDOWN_BY_OUTCOME[outcome]} days (last: {outcome})")
                    return self.COOLDOWN_BY_OUTCOME[outcome]
                break
        return self.STOCK_DEDUP_DAYS
    
    def is_duplicate(self, stock_symbol: str, signal_type: str = 'TREND', trend_phase: str = 'BREAKOUT') -> bool:
        """
        Check if signal is duplicate within deduplication window.
        
        Args:
            stock_symbol: Stock symbol
            signal_type: Type of signal (TREND, VERC, MTF)
            trend_phase: Phase of trend (BREAKOUT, PULLBACK, CONSOLIDATION)
            
        Returns:
            True if duplicate, False if new signal
        """
        cooldown = self.get_outcome_based_cooldown(stock_symbol)
        cutoff = datetime.now() - timedelta(days=cooldown)
        
        setup_key = f"{stock_symbol}_{signal_type}_{trend_phase}"
        
        for sig in self.active_signals.values():
            if self.PHASE_BASED_DEDUP:
                sig_key = f"{sig.get('stock_symbol')}_{sig.get('signal_type')}_{sig.get('trend_phase', 'BREAKOUT')}"
                if sig_key == setup_key:
                    try:
                        added_at = datetime.fromisoformat(sig.get('added_at', ''))
                        if added_at > cutoff:
                            logger.debug(f"Duplicate signal for {setup_key}: active signal exists")
                            return True
                    except:
                        pass
            else:
                if sig.get('stock_symbol') == stock_symbol:
                    try:
                        added_at = datetime.fromisoformat(sig.get('added_at', ''))
                        if added_at > cutoff:
                            logger.debug(f"Duplicate signal for {stock_symbol}: active signal exists")
                            return True
                    except:
                        pass
        
        for sig in self.all_signals:
            if self.PHASE_BASED_DEDUP:
                sig_key = f"{sig.get('stock_symbol')}_{sig.get('signal_type')}_{sig.get('trend_phase', 'BREAKOUT')}"
                if sig_key == setup_key:
                    try:
                        generated_at = datetime.fromisoformat(sig.get('generated_at', ''))
                        if generated_at > cutoff:
                            logger.debug(f"Duplicate signal for {setup_key}: recent signal in memory")
                            return True
                    except:
                        pass
            else:
                if sig.get('stock_symbol') == stock_symbol and sig.get('signal_type') == signal_type:
                    try:
                        generated_at = datetime.fromisoformat(sig.get('generated_at', ''))
                        if generated_at > cutoff:
                            logger.debug(f"Duplicate signal for {stock_symbol}: recent signal in memory")
                            return True
                    except:
                        pass
        
        return False
    
    def get_duplicate_status(self, stock_symbol: str) -> Dict[str, Any]:
        """
        Get detailed duplicate status for a stock.
        
        Returns:
            Dict with duplicate info
        """
        cooldown = self.get_outcome_based_cooldown(stock_symbol)
        cutoff = datetime.now() - timedelta(days=cooldown)
        
        status = {
            'is_duplicate': False,
            'has_active_signal': False,
            'recent_outcome': None,
            'days_since_last_signal': None,
            'cooldown_days': cooldown,
        }
        
        for sig in self.active_signals.values():
            if sig.get('stock_symbol') == stock_symbol:
                status['has_active_signal'] = True
                status['is_duplicate'] = True
                return status
        
        for sig in reversed(self.all_signals):
            if sig.get('stock_symbol') == stock_symbol:
                try:
                    generated_at = datetime.fromisoformat(sig.get('generated_at', ''))
                    if generated_at > cutoff:
                        status['is_duplicate'] = True
                        return status
                    
                    days_since = (datetime.now() - generated_at).days
                    status['days_since_last_signal'] = days_since
                    status['recent_outcome'] = sig.get('outcome')
                except:
                    pass
        
        return status
    
    def check_signal_quality(self, signal_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check signal quality before trade creation.
        
        Args:
            signal_data: Signal data to check
            
        Returns:
            Dict with 'passed' bool and 'score' and 'reasons'
        """
        score = 0
        reasons = []
        
        stock = signal_data.get('stock_symbol')
        
        if stock:
            dup_status = self.get_duplicate_status(stock)
            active = dup_status.get('has_active_signal', False)
            if active:
                score -= 30
                reasons.append(f"Active signal exists for {stock}")
        
        trend_quality = signal_data.get('trend_quality', 0)
        if trend_quality >= 8:
            score += 25
            reasons.append("Strong trend quality")
        elif trend_quality >= 5:
            score += 15
            reasons.append("Moderate trend quality")
        elif trend_quality >= 3:
            score += 5
            reasons.append("Weak trend quality")
        
        volume_confirm = signal_data.get('volume_confirm', False)
        if volume_confirm:
            score += 15
            reasons.append("Volume confirmed")
        else:
            score -= 10
            reasons.append("No volume confirmation")
        
        signal_type = signal_data.get('signal_type', 'TREND')
        min_score = self.STRATEGY_MIN_SCORES.get(signal_type, 6)
        
        passed = score >= min_score
        
        return {
            'passed': passed,
            'score': score,
            'min_required': min_score,
            'reasons': reasons,
        }
    
    def check_no_trade_conditions(self, signal_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check no-trade conditions before trade generation.
        
        Args:
            signal_data: Signal data to check
            
        Returns:
            Dict with 'allowed' bool and 'reasons'
        """
        reasons = []
        allowed = True
        
        if self.is_kill_switch_active():
            allowed = False
            reasons.append("Trade kill switch is active")
        
        regime = self.detect_market_regime(signal_data.get('ohlcv_data'))
        if regime == 'SIDEWAYS':
            signal_type = signal_data.get('signal_type', 'TREND')
            if signal_type in ['TREND', 'Momentum']:
                allowed = False
                reasons.append(f"Strategy {signal_type} not allowed in SIDEWAYS market")
        
        recent = self.get_recent_win_rate()
        if recent is not None and recent < 30:
            allowed = False
            reasons.append(f"Win rate too low: {recent:.1f}%")
        
        return {
            'allowed': allowed,
            'reasons': reasons,
        }
    
    def is_kill_switch_active(self) -> bool:
        """Check if trade kill switch is active (low win rate)."""
        if len(self.outcomes) < 5:
            return False
        
        last_5 = self.outcomes[-5:]
        wins = sum(1 for o in last_5 if o.get('outcome') == 'TARGET_HIT')
        win_rate = (wins / len(last_5)) * 100
        
        if win_rate < 30:
            logger.warning(f"Kill switch activated: {wins}/5 wins ({win_rate:.1f}%)")
            return True
        
        return False
    
    def detect_market_regime(self, ohlcv_data: Optional[Dict] = None) -> str:
        """
        Detect current market regime.
        
        Args:
            ohlcv_data: Optional OHLCV data with ema values
            
        Returns:
            'TRENDING' or 'SIDEWAYS'
        """
        if ohlcv_data:
            ema20 = ohlcv_data.get('ema20')
            ema50 = ohlcv_data.get('ema50')
            ema100 = ohlcv_data.get('ema100')
            
            if ema20 and ema50 and ema100:
                if ema20 > ema50 > ema100:
                    return 'TRENDING'
                
                current = ohlcv_data.get('close')
                high = ohlcv_data.get('high', 0)
                low = ohlcv_data.get('low', float('inf'))
                range_pct = ((high - low) / current * 100) if current else 0
                
                if range_pct < 3:
                    return 'SIDEWAYS'
        
        return 'TRENDING'
    
    def get_recent_win_rate(self) -> Optional[float]:
        """Get win rate from recent outcomes."""
        if len(self.outcomes) < 3:
            return None
        
        recent = self.outcomes[-10:]
        wins = sum(1 for o in recent if o.get('outcome') == 'TARGET_HIT')
        return (wins / len(recent)) * 100
    
    def calculate_resistance_level(self, current_price: float, ohlcv_data: Optional[Dict] = None) -> float:
        """
        Calculate resistance level for target.
        
        Args:
            current_price: Current stock price
            ohlcv_data: Optional OHLCV data with swing highs
            
        Returns:
            Resistance level (swing high or math-based fallback)
        """
        if ohlcv_data:
            swing_high = ohlcv_data.get('swing_high')
            if swing_high and swing_high > current_price:
                return swing_high
        
        fib_1618 = current_price * 1.0618
        fib_1272 = current_price * 1.0272
        
        return min(fib_1618, fib_1272 * 1.02)
    
    def calculate_target_with_resistance(
        self,
        current_price: float,
        distance: float,
        multiplier: float = 1.5,
        ohlcv_data: Optional[Dict] = None
    ) -> float:
        """
        Calculate target respecting resistance levels.
        
        Args:
            current_price: Current price
            distance: Support distance
            multiplier: Risk-reward multiplier
            ohlcv_data: Optional OHLCV data
            
        Returns:
            Target price (resistance or math-based)
        """
        math_target = current_price + (distance * multiplier)
        
        resistance = self.calculate_resistance_level(current_price, ohlcv_data)
        
        target = min(resistance, math_target)
        
        return round(target, 2)
    
    def calculate_atr_stop_loss(
        self,
        current_price: float,
        support: float,
        atr: float = 0,
        atr_multiplier: float = 1.2
    ) -> float:
        """
        Calculate stop loss with ATR for volatility adjustment.
        
        Args:
            current_price: Current price
            support: Support level
            atr: ATR value (optional)
            atr_multiplier: ATR multiplier for SL
            
        Returns:
            Stop loss price
        """
        percent_sl = support * 0.98
        
        if atr > 0:
            atr_sl = current_price - (atr * atr_multiplier)
            return round(min(percent_sl, atr_sl), 2)
        
        return round(percent_sl, 2)
    
    def calculate_position_size(
        self,
        entry_price: float,
        stop_loss: float,
        risk_percent: float = RISK_PER_TRADE
    ) -> Tuple[int, float]:
        """
        Calculate position size based on risk.
        
        Args:
            entry_price: Entry price
            stop_loss: Stop loss price
            risk_percent: Risk percent (default 1%)
            
        Returns:
            Tuple of (position_size, risk_amount)
        """
        risk_amount = self.capital * risk_percent
        
        risk_per_share = abs(entry_price - stop_loss)
        
        if risk_per_share <= 0:
            return 0, 0
        
        position_size = int(risk_amount / risk_per_share)
        
        max_position = int(self.capital * 0.1 / entry_price)
        position_size = min(position_size, max_position)
        
        actual_risk = position_size * risk_per_share
        actual_percent = (actual_risk / self.capital) * 100
        
        return position_size, round(actual_risk, 2)
    
    def calculate_reward_risk(
        self,
        entry_price: float,
        target_price: float,
        stop_loss: float
    ) -> float:
        """Calculate reward-risk ratio."""
        reward = abs(target_price - entry_price)
        risk = abs(entry_price - stop_loss)
        
        if risk <= 0:
            return 0
        
        return round(reward / risk, 2)
    
    def generate_trade_setup(
        self,
        signal_data: Dict[str, Any],
        ohlcv_data: Optional[Dict] = None
    ) -> Optional[TradeSetup]:
        """
        Generate complete trade setup with quality gating.
        
        Args:
            signal_data: Signal data
            ohlcv_data: Optional OHLCV data for calculations
            
        Returns:
            TradeSetup or None if Quality Gating fails
        """
        quality = self.check_signal_quality(signal_data)
        if not quality['passed']:
            logger.info(f"Signal quality failed for {signal_data.get('stock_symbol')}: {quality['reasons']}")
            return None
        
        no_trade = self.check_no_trade_conditions(signal_data)
        if not no_trade['allowed']:
            logger.info(f"No-trade conditions triggered for {signal_data.get('stock_symbol')}: {no_trade['reasons']}")
            return None
        
        stock = signal_data['stock_symbol']
        signal_type = signal_data.get('signal_type', 'TREND')
        
        if self.is_duplicate(stock, signal_type):
            logger.info(f"Duplicate signal blocked for {stock}")
            return None
        
        current = signal_data.get('current_price')
        support = signal_data.get('support')
        atr = signal_data.get('atr', 0)
        
        if not current or not support:
            return None
        
        target = self.calculate_target_with_resistance(
            current,
            current - support,
            signal_data.get('rr_multiplier', 1.5),
            ohlcv_data
        )
        
        stop_loss = self.calculate_atr_stop_loss(current, support, atr)
        
        position_size, risk_amount = self.calculate_position_size(current, stop_loss)
        
        if position_size <= 0:
            return None
        
        rr = self.calculate_reward_risk(current, target, stop_loss)
        
        strategy_weight = self.strategy_weights.get(signal_type, 1.0)
        
        final_score = quality['score'] * strategy_weight
        
        if signal_type == 'TREND' and final_score < 7:
            logger.info(f"Final score too low for TREND: {final_score} < 7")
            return None
        
        return TradeSetup(
            stock_symbol=stock,
            signal_type=signal_type,
            entry_price=current,
            target_price=target,
            stop_loss=stop_loss,
            position_size=position_size,
            risk_amount=risk_amount,
            risk_percent=round((risk_amount / self.capital) * 100, 2),
            reward_risk=rr,
            quality_score=quality['score'],
            strategy_weight=strategy_weight,
        )
    
    def rank_signals(
        self,
        signals: List[Dict[str, Any]],
        ohlcv_data_map: Optional[Dict[str, Dict]] = None
    ) -> List[Dict[str, Any]]:
        """
        Rank signals using strategy weights.
        
        Args:
            signals: List of signals to rank
            ohlcv_data_map: Optional map of stock to OHLCV data
            
        Returns:
            Ranked signals with final_score
        """
        ranked = []
        
        for sig in signals:
            signal_type = sig.get('signal_type', 'TREND')
            
            quality = self.check_signal_quality(sig)
            
            rank_score = quality['score']
            
            weight = self.strategy_weights.get(signal_type, 1.0)
            final_score = rank_score * weight
            
            ohlcv = ohlcv_data_map.get(sig.get('stock_symbol')) if ohlcv_data_map else None
            
            min_score = self.STRATEGY_MIN_SCORES.get(signal_type, 6)
            if final_score >= min_score:
                ranked.append({
                    **sig,
                    'quality_score': quality['score'],
                    'strategy_weight': weight,
                    'final_score': final_score,
                    'passed': True,
                })
            else:
                ranked.append({
                    **sig,
                    'quality_score': quality['score'],
                    'strategy_weight': weight,
                    'final_score': final_score,
                    'passed': False,
                })
        
        ranked.sort(key=lambda x: x['final_score'], reverse=True)
        
        return ranked
    
    def update_signal_outcome(self, signal_id: str, outcome: str, pnl_percent: float = 0.0):
        """Update signal outcome when completed."""
        for sig in self.all_signals:
            if sig.get('signal_id') == signal_id:
                sig['outcome'] = outcome
                sig['pnl_percent'] = pnl_percent
                sig['completed_at'] = datetime.now().isoformat()
                break
        
        self._save_all_signals()
        
        outcome_record = {
            'signal_id': signal_id,
            'outcome': outcome,
            'pnl_percent': pnl_percent,
            'completed_at': datetime.now().isoformat()
        }
        self.outcomes.append(outcome_record)
        
        if len(self.outcomes) > 1000:
            self.outcomes = self.outcomes[-1000:]
        
        self._save_outcomes()
        
        logger.info(f"Updated outcome for {signal_id}: {outcome} ({pnl_percent:.2f}%)")
    
    def check_partial_exit(self, signal: Dict[str, Any], current_pnl: float) -> Optional[str]:
        """
        Check if partial exit should be triggered.
        
        Args:
            signal: Signal data
            current_pnl: Current P&L percent
            
        Returns:
            'partial_exit' or None
        """
        if current_pnl > 2:
            return 'partial_exit'
        return None
    
    def check_trailing_sl(self, signal: Dict[str, Any], current_price: float, ema20: float) -> Optional[float]:
        """
        Check if trailing stop loss should be activated.
        
        Args:
            signal: Signal data
            current_price: Current price
            ema20: 20-period EMA
            
        Returns:
            New stop loss price or None
        """
        entry = signal.get('entry_price', 0)
        if ema20 > entry:
            return ema20
        return None
    
    def check_time_decay(self, signal: Dict[str, Any]) -> Optional[str]:
        """
        Check if time decay logic applies.
        
        Args:
            signal: Signal data
            
        Returns:
            'timeout' or None
        """
        try:
            generated = datetime.fromisoformat(signal.get('generated_at', ''))
            days_active = (datetime.now() - generated).days
            
            if days_active > 10:
                return 'timeout'
        except:
            pass
        return None
    
    def add_signal(self, signal_data: Dict[str, Any]) -> str:
        """Add a new signal to memory."""
        import uuid
        signal_id = signal_data.get('signal_id') or f"{signal_data.get('signal_type', 'SIGNAL')}_{signal_data.get('stock_symbol', 'UNKNOWN')}_{uuid.uuid4().hex[:8]}"
        
        signal_record = {
            **signal_data,
            'signal_id': signal_id,
            'generated_at': datetime.now().isoformat()
        }
        
        self.all_signals.append(signal_record)
        self._save_all_signals()
        
        logger.info(f"Added signal to memory: {signal_id}")
        
        return signal_id
    
    def get_signal_context(self, stock_symbol: str = None, trade_journal=None) -> SignalContext:
        """Get signal context for AI decision making with journal insights."""
        context = SignalContext(stock_symbol=stock_symbol or 'ALL')
        
        cutoff = datetime.now() - timedelta(days=30)
        
        if stock_symbol:
            context.previous_signals = [
                s for s in self.all_signals
                if s.get('stock_symbol') == stock_symbol
            ]
            
            context.active_signals = [
                s for s in self.active_signals.values()
                if s.get('stock_symbol') == stock_symbol
            ]
        
        for outcome in self.outcomes[-50:]:
            try:
                completed_at = datetime.fromisoformat(outcome.get('completed_at', ''))
                if completed_at > cutoff:
                    context.recent_outcomes.append(outcome)
            except:
                pass
        
        completed = [o for o in self.outcomes if o.get('outcome') == 'TARGET_HIT']
        total = len(self.outcomes)
        if total > 0:
            context.overall_win_rate = (len(completed) / total) * 100
        
        if trade_journal:
            self._enrich_context_from_journal(context, trade_journal)
        
        return context
    
    def _enrich_context_from_journal(self, context: SignalContext, trade_journal) -> None:
        """Enrich signal context with trade journal learnings."""
        try:
            recent_trades = trade_journal.get_recent_trades(days=30)
            
            if not recent_trades:
                return
            
            wins = [t for t in recent_trades if t.get('outcome') == 'WIN']
            losses = [t for t in recent_trades if t.get('outcome') == 'LOSS']
            
            context.trade_journal_insights = []
            
            if wins:
                win_factors = defaultdict(int)
                for t in wins:
                    for factor in t.get('positive_factors', []):
                        win_factors[factor] += 1
                context.success_factors = [f for f, _ in sorted(win_factors.items(), key=lambda x: x[1], reverse=True)[:5]]
            
            if losses:
                loss_factors = defaultdict(int)
                for t in losses:
                    for factor in t.get('negative_factors', []):
                        loss_factors[factor] += 1
                context.failed_factors = [f for f, _ in sorted(loss_factors.items(), key=lambda x: x[1], reverse=True)[:5]]
            
            context.trade_journal_insights = [
                {
                    'total_trades': len(recent_trades),
                    'wins': len(wins),
                    'losses': len(losses),
                    'win_rate': len(wins) / len(recent_trades) if recent_trades else 0,
                    'avg_rr_achieved': sum(t.get('rr_achieved', 0) for t in wins) / len(wins) if wins else 0
                }
            ]
            
            logger.debug(f"Journal insights: {len(wins)} wins, {len(losses)} losses")
            
        except Exception as e:
            logger.error(f"Error enriching context from journal: {e}")
    
    def get_excluded_stocks(self, signal_type: str = None) -> Set[str]:
        """Get set of stocks excluded from new signals."""
        excluded = set()
        cutoff = datetime.now() - timedelta(days=self.STOCK_DEDUP_DAYS)
        
        for sig in self.active_signals.values():
            stock = sig.get('stock_symbol')
            if stock:
                try:
                    added_at = datetime.fromisoformat(sig.get('added_at', ''))
                    if added_at > cutoff:
                        excluded.add(stock)
                except:
                    pass
        
        for sig in self.all_signals:
            if signal_type and sig.get('signal_type') != signal_type:
                continue
            stock = sig.get('stock_symbol')
            if stock:
                try:
                    generated_at = datetime.fromisoformat(sig.get('generated_at', ''))
                    if generated_at > cutoff:
                        excluded.add(stock)
                except:
                    pass
        
        return excluded
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary for all signals."""
        if not self.outcomes:
            return {
                'total_signals': len(self.all_signals),
                'active_signals': len(self.active_signals),
                'completed_signals': 0,
                'win_rate': 0.0,
                'avg_pnl': 0.0,
                'recent_outcomes': []
            }
        
        completed = [o for o in self.outcomes if o.get('outcome') in ['TARGET_HIT', 'SL_HIT']]
        wins = [o for o in completed if o.get('outcome') == 'TARGET_HIT']
        
        win_rate = (len(wins) / len(completed)) * 100 if completed else 0
        avg_pnl = sum(o.get('pnl_percent', 0) for o in completed) / len(completed) if completed else 0
        
        return {
            'total_signals': len(self.all_signals),
            'active_signals': len(self.active_signals),
            'completed_signals': len(completed),
            'win_rate': win_rate,
            'avg_pnl': avg_pnl,
            'recent_outcomes': self.outcomes[-10:]
        }
    
    def sync_with_history_manager(self, history_manager):
        """Sync memory with history manager."""
        active = history_manager.get_all_active_signals()
        for sig in active:
            sig_id = sig.get('signal_id')
            if sig_id and sig_id not in self.active_signals:
                self.active_signals[sig_id] = sig
        
        history = history_manager.get_history(limit=500)
        for sig in history:
            if sig not in self.all_signals:
                self.all_signals.append(sig)
        
        self._save_all_signals()
        
        logger.info(f"Synced {len(active)} active and {len(history)} historical signals")
    
    def update_strategy_weight(self, signal_type: str, weight: float):
        """Update strategy weight for learning."""
        if signal_type in self.strategy_weights:
            old = self.strategy_weights[signal_type]
            self.strategy_weights[signal_type] = weight
            logger.info(f"Updated strategy weight for {signal_type}: {old} -> {weight}")
    
    def adjust_strategy_weights_from_outcomes(self):
        """Adjust strategy weights based on performance."""
        if len(self.outcomes) < 10:
            return
        
        for signal_type in self.strategy_weights:
            type_outcomes = [
                o for o in self.outcomes[-50:]
                if o.get('signal_type') == signal_type
            ]
            
            if type_outcomes:
                wins = sum(1 for o in type_outcomes if o.get('outcome') == 'TARGET_HIT')
                rate = wins / len(type_outcomes)
                
                if rate >= 0.6:
                    self.strategy_weights[signal_type] = min(1.5, self.strategy_weights[signal_type] * 1.1)
                elif rate < 0.4:
                    self.strategy_weights[signal_type] = max(0.5, self.strategy_weights[signal_type] * 0.9)
        
        logger.info(f"Adjusted strategy weights: {self.strategy_weights}")


def create_signal_memory(data_dir: str = DATA_DIR, capital: float = DEFAULT_CAPITAL) -> SignalMemory:
    """Factory function to create signal memory."""
    return SignalMemory(data_dir, capital)