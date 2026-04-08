"""
Trade Journal System
Logs every signal and tracks outcomes for learning.
"""

import os
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)

DATA_DIR = 'data'


@dataclass
class Trade:
    trade_id: str
    symbol: str
    strategy: str  # TREND / VERC / MTF
    entry: float
    stop_loss: float
    targets: List[float]
    timestamp: str
    outcome: str  # WIN / LOSS / OPEN / TIMEOUT
    rr_achieved: float = 0.0
    max_drawdown: float = 0.0
    volume_ratio: float = 0.0
    rsi: float = 0.0
    trend_score: float = 0.0
    verc_score: float = 0.0
    rank_score: float = 0.0


class TradeJournal:
    """
    Trade Journal - Tracks every signal and builds feedback loop.
    Logs EVERY alert, updates on SL hit, Target hit, or Expiry (10-15 days).
    """
    
    TRADE_FILE = 'trade_journal.json'
    OUTCOME_WIN = 'WIN'
    OUTCOME_LOSS = 'LOSS'
    OUTCOME_OPEN = 'OPEN'
    OUTCOME_TIMEOUT = 'TIMEOUT'
    
    def __init__(self, data_dir: str = DATA_DIR):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        
        self.trades = self._load_trades()
        self.expiry_days = 15
        
        logger.info(f"TradeJournal initialized. Active trades: {len(self.get_open_trades())}")
    
    def _load_trades(self) -> List[Dict[str, Any]]:
        filepath = os.path.join(self.data_dir, self.TRADE_FILE)
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                    return data.get('trades', [])
            except Exception as e:
                logger.error(f"Error loading trades: {e}")
                return []
        return []
    
    def _save_trades(self) -> None:
        filepath = os.path.join(self.data_dir, self.TRADE_FILE)
        data = {
            'version': '1.0',
            'last_updated': datetime.now().isoformat(),
            'trades': self.trades
        }
        try:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error saving trades: {e}")
    
    def log_signal(
        self,
        symbol: str,
        strategy: str,
        entry: float,
        stop_loss: float,
        targets: List[float],
        indicators: Dict[str, Any] = None
    ) -> str:
        """
        Log EVERY alert/signal.
        
        Args:
            symbol: Stock symbol
            strategy: TREND / VERC / MTF
            entry: Entry price
            stop_loss: Stop loss price
            targets: List of target prices
            indicators: Additional indicators (volume_ratio, rsi, scores)
            
        Returns:
            trade_id
        """
        trade_id = f"{strategy}_{symbol}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}"
        
        trade = {
            'trade_id': trade_id,
            'symbol': symbol,
            'strategy': strategy,
            'entry': entry,
            'stop_loss': stop_loss,
            'targets': targets,
            'timestamp': datetime.now().isoformat(),
            'outcome': self.OUTCOME_OPEN,
            'rr_achieved': 0.0,
            'max_drawdown': 0.0,
            'volume_ratio': indicators.get('volume_ratio', 0) if indicators else 0,
            'rsi': indicators.get('rsi', 0) if indicators else 0,
            'trend_score': indicators.get('trend_score', 0) if indicators else 0,
            'verc_score': indicators.get('verc_score', 0) if indicators else 0,
            'rank_score': indicators.get('rank_score', 0) if indicators else 0,
            'updated_at': datetime.now().isoformat()
        }
        
        self.trades.append(trade)
        self._save_trades()
        
        logger.info(f"Logged signal: {symbol} ({strategy}) - {trade_id}")
        
        return trade_id
    
    def update_trade(
        self,
        trade_id: str,
        outcome: str,
        exit_price: float = 0,
        max_drawdown: float = 0
    ) -> bool:
        """
        Update trade when SL hit, Target hit, or Expiry.
        
        Args:
            trade_id: Trade ID to update
            outcome: WIN / LOSS / TIMEOUT
            exit_price: Price at exit
            max_drawdown: Maximum drawdown during trade
            
        Returns:
            True if updated
        """
        for trade in self.trades:
            if trade.get('trade_id') == trade_id:
                trade['outcome'] = outcome
                trade['exit_price'] = exit_price
                trade['updated_at'] = datetime.now().isoformat()
                
                entry = trade.get('entry', 0)
                sl = trade.get('stop_loss', 0)
                
                if entry > 0 and sl > 0:
                    risk = abs(entry - sl)
                    
                    if outcome == self.OUTCOME_WIN and exit_price > 0:
                        reward = exit_price - entry
                        trade['rr_achieved'] = round(reward / risk, 2) if risk > 0 else 0
                    elif outcome == self.OUTCOME_LOSS and exit_price > 0:
                        loss = entry - exit_price
                        trade['rr_achieved'] = round(-loss / risk, 2) if risk > 0 else 0
                
                trade['max_drawdown'] = max_drawdown
                
                self._save_trades()
                
                logger.info(f"Updated trade {trade_id}: {outcome}, RR: {trade.get('rr_achieved', 0)}")
                
                return True
        
        logger.warning(f"Trade not found: {trade_id}")
        return False
    
    def get_trade(self, trade_id: str) -> Optional[Dict[str, Any]]:
        for trade in self.trades:
            if trade.get('trade_id') == trade_id:
                return trade
        return None
    
    def check_signal_exists(self, symbol: str, strategy: str) -> Optional[Dict[str, Any]]:
        """Check if a signal already exists in the journal."""
        for trade in self.trades:
            if trade.get('symbol', '').upper() == symbol.upper() and trade.get('strategy', '') == strategy:
                if trade.get('outcome') == self.OUTCOME_OPEN:
                    return trade
        return None
    
    def update_trade_note(self, trade_id: str, note: str) -> bool:
        """Update trade notes."""
        for trade in self.trades:
            if trade.get('trade_id') == trade_id:
                existing_notes = trade.get('notes', '')
                new_notes = f"{existing_notes}\n{note}" if existing_notes else note
                trade['notes'] = new_notes
                trade['updated_at'] = datetime.now().isoformat()
                self._save_trades()
                return True
        return False
    
    def get_open_trades(self) -> List[Dict[str, Any]]:
        return [t for t in self.trades if t.get('outcome') == self.OUTCOME_OPEN]
    
    def get_closed_trades(self, limit: int = 100) -> List[Dict[str, Any]]:
        closed = [t for t in self.trades if t.get('outcome') != self.OUTCOME_OPEN]
        return closed[-limit:] if limit > 0 else closed
    
    def get_trades_by_strategy(self, strategy: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get last N trades for a specific strategy."""
        strategy_trades = [t for t in self.trades if t.get('strategy') == strategy]
        return strategy_trades[-limit:] if limit > 0 else strategy_trades
    
    def check_expired_trades(self) -> List[Dict[str, Any]]:
        """Check for trades that exceeded expiry (10-15 days)."""
        expired = []
        cutoff = datetime.now() - timedelta(days=self.expiry_days)
        
        for trade in self.trades:
            if trade.get('outcome') != self.OUTCOME_OPEN:
                continue
            
            try:
                timestamp = datetime.fromisoformat(trade.get('timestamp', ''))
                if timestamp < cutoff:
                    trade['outcome'] = self.OUTCOME_TIMEOUT
                    trade['updated_at'] = datetime.now().isoformat()
                    expired.append(trade)
                    logger.info(f"Trade expired: {trade.get('symbol')} ({trade.get('trade_id')})")
            except Exception as e:
                logger.error(f"Error checking expiry: {e}")
        
        if expired:
            self._save_trades()
        
        return expired
    
    def get_stats(self) -> Dict[str, Any]:
        """Get overall journal statistics."""
        all_trades = self.trades
        open_trades = self.get_open_trades()
        closed_trades = self.get_closed_trades(limit=1000)
        
        wins = [t for t in closed_trades if t.get('outcome') == self.OUTCOME_WIN]
        losses = [t for t in closed_trades if t.get('outcome') == self.OUTCOME_LOSS]
        timeouts = [t for t in closed_trades if t.get('outcome') == self.OUTCOME_TIMEOUT]
        
        total_closed = len(closed_trades)
        win_rate = (len(wins) / total_closed * 100) if total_closed > 0 else 0
        
        rr_values = [t.get('rr_achieved', 0) for t in closed_trades if t.get('rr_achieved', 0) != 0]
        avg_rr = sum(rr_values) / len(rr_values) if rr_values else 0
        
        return {
            'total_trades': len(all_trades),
            'open_trades': len(open_trades),
            'closed_trades': len(closed_trades),
            'wins': len(wins),
            'losses': len(losses),
            'timeouts': len(timeouts),
            'win_rate': round(win_rate, 2),
            'avg_rr': round(avg_rr, 2)
        }


def create_trade_journal(data_dir: str = DATA_DIR) -> TradeJournal:
    """Factory function to create trade journal."""
    return TradeJournal(data_dir)