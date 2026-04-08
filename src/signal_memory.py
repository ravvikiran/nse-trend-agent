"""
Signal Memory - Deduplication and Outcome Tracking
Stores all signals and checks for duplicates before generating new ones.
Tracks signal outcomes and passes context to AI for better decision making.
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field, asdict
from collections import defaultdict

logger = logging.getLogger(__name__)

DATA_DIR = 'data'


@dataclass
class SignalOutcome:
    """Outcome of a completed signal."""
    signal_id: str
    stock_symbol: str
    signal_type: str
    entry_price: float
    target_price: float
    sl_price: float
    outcome: str  # TARGET_HIT, SL_HIT, TIMEOUT, ACTIVE
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


class SignalMemory:
    """
    Memory system for signals:
    - Stores all generated signals
    - Checks for duplicates
    - Tracks outcomes for learning
    - Provides context to AI for decision making
    """
    
    STOCK_DEDUP_DAYS = 30  # Don't generate signal for same stock within 30 days
    
    def __init__(self, data_dir: str = DATA_DIR):
        self.data_dir = data_dir
        self._ensure_data_dir()
        
        self.all_signals = self._load_all_signals()
        self.active_signals = self._load_active_signals()
        self.outcomes = self._load_outcomes()
        
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
        """Save all signals to memory."""
        filepath = self._get_all_signals_path()
        data = {
            'version': '1.0',
            'last_updated': datetime.now().isoformat(),
            'signals': self.all_signals
        }
        try:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2, default=str)
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
    
    def is_duplicate(self, stock_symbol: str, signal_type: str = 'TREND') -> bool:
        """
        Check if signal is duplicate within deduplication window.
        
        Args:
            stock_symbol: Stock symbol
            signal_type: Type of signal (TREND, VERC, MTF)
            
        Returns:
            True if duplicate, False if new signal
        """
        cutoff = datetime.now() - timedelta(days=self.STOCK_DEDUP_DAYS)
        
        # Check active signals
        for sig in self.active_signals.values():
            if sig.get('stock_symbol') == stock_symbol:
                try:
                    added_at = datetime.fromisoformat(sig.get('added_at', ''))
                    if added_at > cutoff:
                        logger.debug(f"Duplicate signal for {stock_symbol}: active signal exists")
                        return True
                except:
                    pass
        
        # Check completed signals in memory
        for sig in self.all_signals:
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
        cutoff = datetime.now() - timedelta(days=self.STOCK_DEDUP_DAYS)
        
        status = {
            'is_duplicate': False,
            'has_active_signal': False,
            'recent_outcome': None,
            'days_since_last_signal': None
        }
        
        # Check active
        for sig in self.active_signals.values():
            if sig.get('stock_symbol') == stock_symbol:
                status['has_active_signal'] = True
                status['is_duplicate'] = True
                return status
        
        # Check history
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
    
    def add_signal(self, signal_data: Dict[str, Any]) -> str:
        """
        Add a new signal to memory.
        
        Args:
            signal_data: Signal dict with stock_symbol, signal_type, etc.
            
        Returns:
            Signal ID
        """
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
    
    def update_signal_outcome(self, signal_id: str, outcome: str, pnl_percent: float = 0.0):
        """
        Update signal outcome when completed.
        
        Args:
            signal_id: Signal ID
            outcome: Outcome (TARGET_HIT, SL_HIT, TIMEOUT)
            pnl_percent: P&L percentage
        """
        # Update in all_signals
        for sig in self.all_signals:
            if sig.get('signal_id') == signal_id:
                sig['outcome'] = outcome
                sig['pnl_percent'] = pnl_percent
                sig['completed_at'] = datetime.now().isoformat()
                break
        
        self._save_all_signals()
        
        # Add to outcomes
        outcome_record = {
            'signal_id': signal_id,
            'outcome': outcome,
            'pnl_percent': pnl_percent,
            'completed_at': datetime.now().isoformat()
        }
        self.outcomes.append(outcome_record)
        
        # Keep only last 1000 outcomes
        if len(self.outcomes) > 1000:
            self.outcomes = self.outcomes[-1000:]
        
        self._save_outcomes()
        
        logger.info(f"Updated outcome for {signal_id}: {outcome} ({pnl_percent:.2f}%)")
    
    def get_signal_context(self, stock_symbol: str = None) -> SignalContext:
        """
        Get signal context for AI decision making.
        
        Args:
            stock_symbol: Optional stock to get context for
            
        Returns:
            SignalContext object with all relevant info
        """
        context = SignalContext(stock_symbol=stock_symbol or 'ALL')
        
        cutoff = datetime.now() - timedelta(days=30)
        
        # Collect previous signals for stock
        if stock_symbol:
            context.previous_signals = [
                s for s in self.all_signals
                if s.get('stock_symbol') == stock_symbol
            ]
            
            context.active_signals = [
                s for s in self.active_signals.values()
                if s.get('stock_symbol') == stock_symbol
            ]
        
        # Recent outcomes
        for outcome in self.outcomes[-50:]:
            try:
                completed_at = datetime.fromisoformat(outcome.get('completed_at', ''))
                if completed_at > cutoff:
                    context.recent_outcomes.append(outcome)
            except:
                pass
        
        # Calculate overall win rate
        completed = [o for o in self.outcomes if o.get('outcome') == 'TARGET_HIT']
        total = len(self.outcomes)
        if total > 0:
            context.overall_win_rate = (len(completed) / total) * 100
        
        return context
    
    def get_excluded_stocks(self, signal_type: str = None) -> Set[str]:
        """
        Get set of stocks that should be excluded from new signals (duplicates).
        
        Args:
            signal_type: Optional filter by signal type
            
        Returns:
            Set of stock symbols to exclude
        """
        excluded = set()
        cutoff = datetime.now() - timedelta(days=self.STOCK_DEDUP_DAYS)
        
        # Check active signals
        for sig in self.active_signals.values():
            stock = sig.get('stock_symbol')
            if stock:
                try:
                    added_at = datetime.fromisoformat(sig.get('added_at', ''))
                    if added_at > cutoff:
                        excluded.add(stock)
                except:
                    pass
        
        # Check signals in memory
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
        """
        Sync memory with history manager (import existing signals).
        
        Args:
            history_manager: HistoryManager instance
        """
        # Import active signals
        active = history_manager.get_all_active_signals()
        for sig in active:
            sig_id = sig.get('signal_id')
            if sig_id and sig_id not in self.active_signals:
                self.active_signals[sig_id] = sig
        
        # Import history
        history = history_manager.get_history(limit=500)
        for sig in history:
            if sig not in self.all_signals:
                self.all_signals.append(sig)
        
        self._save_all_signals()
        
        logger.info(f"Synced {len(active)} active and {len(history)} historical signals")


def create_signal_memory(data_dir: str = DATA_DIR) -> SignalMemory:
    """Factory function to create signal memory."""
    return SignalMemory(data_dir)