"""
Trade Journal System
Logs every signal and tracks outcomes for learning.
"""

import os
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union, Tuple
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)

DATA_DIR = 'data'

BLACKLIST_DAYS = 5
MAX_CONSECUTIVE_LOSSES = 3


@dataclass
class Trade:
    trade_id: str
    symbol: str
    strategy: str  # TREND / VERC / MTF
    direction: str  # BUY or SELL
    entry: float
    stop_loss: float
    targets: List[float]
    timestamp: str
    outcome: str  # WIN / LOSS / OPEN / TIMEOUT
    rr_achieved: float = 0.0
    max_drawdown: float = 0.0
    max_profit: float = 0.0  # MFE - Max Favorable Excursion
    targets_hit: List[int] = field(default_factory=list)  # [1, 2] means T1 and T2 hit
    highest_target_hit: int = 0
    holding_days: float = 0.0
    volume_ratio: float = 0.0
    rsi: float = 0.0
    trend_score: float = 0.0
    verc_score: float = 0.0
    rank_score: float = 0.0
    quality: str = "B"  # A / B / C
    market_context: str = "BULLISH"  # BULLISH / SIDEWAYS / BEARISH
    entry_type: str = "BREAKOUT"  # BREAKOUT / PULLBACK
    candle_quality: str = "NORMAL"  # NORMAL / STRONG / WEAK
    breakout_strength: float = 0.0  # percentage


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
        self.blacklist = self._load_blacklist()
        
        self.filters = {
            "min_sl_pct": 2.0,
            "max_sl_pct": 3.0,
            "min_target_pct": 5.0,
            "max_target_pct": 10.0,
            "min_rr": 2.0,
            "min_distance_sr": 3.0,
            "max_recent_move": 8.0,
            "max_consolidation_range": 4.0
        }
        
        logger.info(f"TradeJournal initialized. Active trades: {len(self.get_open_trades())}")
    
    def _load_blacklist(self) -> Dict[str, Dict[str, Any]]:
        """Load blacklist from file."""
        filepath = os.path.join(self.data_dir, 'stock_blacklist.json')
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading blacklist: {e}")
                return {}
        return {}
    
    def _save_blacklist(self) -> None:
        """Save blacklist to file."""
        filepath = os.path.join(self.data_dir, 'stock_blacklist.json')
        try:
            with open(filepath, 'w') as f:
                json.dump(self.blacklist, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error saving blacklist: {e}")
    
    def is_blacklisted(self, symbol: str) -> bool:
        """Check if symbol is blacklisted."""
        if symbol not in self.blacklist:
            return False
        entry = self.blacklist[symbol]
        expires_at = entry.get('expires_at')
        if expires_at:
            expires_dt = datetime.fromisoformat(expires_at)
            if datetime.now() > expires_dt:
                del self.blacklist[symbol]
                self._save_blacklist()
                return False
        return True
    
    def _check_consecutive_losses(self, symbol: str) -> int:
        """Check consecutive losses for a symbol within 30 days."""
        cutoff = datetime.now() - timedelta(days=30)
        
        symbol_trades = [
            t for t in self.trades
            if t.get('symbol') == symbol and 
            datetime.fromisoformat(t.get('timestamp', '2000-01-01')) > cutoff
        ]
        symbol_trades.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        consecutive_losses = 0
        for t in symbol_trades:
            if t.get('outcome') == 'LOSS':
                consecutive_losses += 1
            else:
                break
        return consecutive_losses
    
    def _update_blacklist(self, symbol: str) -> None:
        """Update blacklist after trade closes."""
        consecutive_losses = self._check_consecutive_losses(symbol)
        if consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
            expires_at = datetime.now() + timedelta(days=BLACKLIST_DAYS)
            self.blacklist[symbol] = {
                'consecutive_losses': consecutive_losses,
                'expires_at': expires_at.isoformat(),
                'reason': f'{consecutive_losses} consecutive losses'
            }
            self._save_blacklist()
            logger.info(f"Blacklisted {symbol} for {BLACKLIST_DAYS} days ({consecutive_losses} losses)")

    @staticmethod
    def _calculate_percentages(entry: float, stop_loss: float, target: float):
        sl_pct = abs((entry - stop_loss) / entry) * 100
        target_pct = abs((target - entry) / entry) * 100
        rr = (target_pct / sl_pct) if sl_pct > 0 else 0
        return sl_pct, target_pct, rr

    @staticmethod
    def _validate_structure(entry: float, stop_loss: float, target: float, direction: str):
        direction = direction.upper()
        if direction == "BUY":
            return entry > stop_loss and target > entry
        elif direction == "SELL":
            return entry < stop_loss and target < entry
        return False
    
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
    
    def _get_file_path(self) -> str:
        """Get monthly rotated file path."""
        now = datetime.now()
        filename = f"trade_journal_{now.year}_{now.month:02d}.json"
        return os.path.join(self.data_dir, filename)
    
    def _save_trades(self) -> None:
        filepath = os.path.join(self.data_dir, self.TRADE_FILE)
        data = {
            'version': '1.0',
            'last_updated': datetime.now().isoformat(),
            'trades': self.trades
        }
        try:
            tmp_path = filepath + ".tmp"
            with open(tmp_path, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            os.replace(tmp_path, filepath)
        except Exception as e:
            logger.error(f"Error saving trades: {e}")
    
    def log_signal(
        self,
        symbol: str,
        strategy: str,
        direction: str,
        entry: float,
        stop_loss: float,
        targets: List[float],
        indicators: Optional[Dict[str, Any]] = None,
        quality: str = "B",
        market_context: str = "BULLISH",
        entry_type: str = "BREAKOUT",
        breakout_strength: float = 0.0
    ) -> str:
        """
        Log EVERY alert/signal.
        
        Args:
            symbol: Stock symbol
            strategy: TREND / VERC / MTF
            direction: BUY or SELL
            entry: Entry price
            stop_loss: Stop loss price
            targets: List of target prices
            indicators: Additional indicators (volume_ratio, rsi, scores)
            quality: A/B/C quality grade
            market_context: BULLISH/SIDEWAYS/BEARISH
            entry_type: BREAKOUT/PULLBACK
            breakout_strength: percentage breakout strength
            
        Returns:
            trade_id
        """
        trade_id = f"{strategy}_{symbol}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}"
        
        existing = self.check_signal_exists(symbol, strategy, entry)
        if existing:
            logger.info(f"Duplicate signal skipped: {symbol}")
            return existing.get('trade_id', '')
        
        trade = {
            'trade_id': trade_id,
            'symbol': symbol,
            'strategy': strategy,
            'direction': direction.upper(),
            'entry': entry,
            'stop_loss': stop_loss,
            'targets': targets,
            'timestamp': datetime.now().isoformat(),
            'outcome': self.OUTCOME_OPEN,
            'rr_achieved': 0.0,
            'max_drawdown': 0.0,
            'max_profit': 0.0,
            'targets_hit': [],
            'highest_target_hit': 0,
            'holding_days': 0.0,
            'volume_ratio': indicators.get('volume_ratio', 0) if indicators else 0,
            'rsi': indicators.get('rsi', 0) if indicators else 0,
            'trend_score': indicators.get('trend_score', 0) if indicators else 0,
            'verc_score': indicators.get('verc_score', 0) if indicators else 0,
            'rank_score': 0.0,
            'quality': quality,
            'market_context': market_context,
            'entry_type': entry_type,
            'candle_quality': indicators.get('candle_quality', 'NORMAL') if indicators else 'NORMAL',
            'breakout_strength': breakout_strength,
            'updated_at': datetime.now().isoformat()
        }
        
        trade['rank_score'] = self.calculate_rank_score(trade)
        
        self.trades.append(trade)
        self._save_trades()
        
        logger.info(f"Logged signal: {symbol} ({strategy}) - {trade_id}")
        
        return trade_id
    
    @staticmethod
    def calculate_quality(score: float, volume_ratio: float, breakout_strength: float) -> str:
        """
        Calculate trade quality grade.
        
        A: score >= 8, volume_ratio >= 1.8, breakout_strength >= 3%
        B: score 6-7
        C: score < 6
        
        Args:
            score: Signal score (0-10)
            volume_ratio: Volume ratio
            breakout_strength: Breakout strength percentage
            
        Returns:
            Quality grade: A, B, or C
        """
        breakout_pct = breakout_strength * 100 if breakout_strength <= 1 else breakout_strength
        
        if score >= 8 and volume_ratio >= 1.8 and breakout_pct >= 3:
            return 'A'
        elif score >= 6:
            return 'B'
        else:
            return 'C'
    
    def calculate_rank_score(self, trade: Dict[str, Any]) -> float:
        """
        Calculate rank score for a trade based on key metrics.
        
        Args:
            trade: Trade dictionary
            
        Returns:
            Rank score (0-100)
        """
        return (
            trade.get('trend_score', 0) * 0.4 +
            trade.get('volume_ratio', 0) * 2 +
            trade.get('breakout_strength', 0) * 10
        )
    
    def suggest_position_size(self, quality: str) -> float:
        """
        Suggest position size multiplier based on trade quality.
        
        Args:
            quality: Trade quality grade (A/B/C)
            
        Returns:
            Position size multiplier (0.0-1.0)
        """
        return {
            'A': 1.0,
            'B': 0.7,
            'C': 0.4
        }.get(quality, 0.5)
    
    def update_trade(
        self,
        trade_id: str,
        outcome: str,
        exit_price: float = 0,
        max_drawdown: float = 0,
        max_profit: float = 0,
        targets_hit: Optional[List[int]] = None,
        exit_time: Optional[str] = None
    ) -> bool:
        """
        Update trade when SL hit, Target hit, or Expiry.
        
        Args:
            trade_id: Trade ID to update
            outcome: WIN / LOSS / TIMEOUT
            exit_price: Price at exit
            max_drawdown: Maximum drawdown during trade
            max_profit: MFE - max favorable excursion during trade
            targets_hit: List of target numbers hit (e.g., [1, 2])
            exit_time: Exit timestamp for calculating holding days
            
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
                direction = trade.get('direction', 'BUY').upper()
                
                is_sell = direction == 'SELL'
                
                if entry > 0 and sl > 0:
                    risk = abs(entry - sl)
                    
                    if outcome == self.OUTCOME_WIN and exit_price > 0:
                        if is_sell:
                            reward = entry - exit_price
                        else:
                            reward = exit_price - entry
                        trade['rr_achieved'] = round(reward / risk, 2) if risk > 0 else 0
                    elif outcome == self.OUTCOME_LOSS and exit_price > 0:
                        if is_sell:
                            loss = exit_price - entry
                        else:
                            loss = entry - exit_price
                        trade['rr_achieved'] = round(-loss / risk, 2) if risk > 0 else 0
                    elif outcome == self.OUTCOME_TIMEOUT:
                        trade['rr_achieved'] = -0.5
                
                trade['max_drawdown'] = max_drawdown
                trade['max_profit'] = max_profit
                trade['targets_hit'] = targets_hit or []
                trade['highest_target_hit'] = max(targets_hit) if targets_hit else 0
                
                if exit_time:
                    try:
                        entry_time = datetime.fromisoformat(trade.get('timestamp', ''))
                        exit_dt = datetime.fromisoformat(exit_time)
                        holding_seconds = (exit_dt - entry_time).total_seconds()
                        trade['holding_days'] = round(holding_seconds / 86400, 2)
                    except Exception:
                        pass
                
                self._save_trades()
                
                if outcome == self.OUTCOME_LOSS:
                    symbol = trade.get('symbol', '')
                    if symbol:
                        self._update_blacklist(symbol)
                
                logger.info(f"Updated trade {trade_id}: {outcome}, RR: {trade.get('rr_achieved', 0)}")
                
                return True
        
        logger.warning(f"Trade not found: {trade_id}")
        return False
    
    def get_trade(self, trade_id: str) -> Optional[Dict[str, Any]]:
        for trade in self.trades:
            if trade.get('trade_id') == trade_id:
                return trade
        return None
    
    def check_signal_exists(self, symbol: str, strategy: str, entry: float = 0, tolerance: float = 0.5) -> Optional[Dict[str, Any]]:
        """
        Check if a signal already exists in the journal.
        
        Args:
            symbol: Stock symbol
            strategy: Strategy name
            entry: Entry price (for tolerance check)
            tolerance: Price tolerance percentage
            
        Returns:
            Existing trade if found, None otherwise
        """
        for trade in self.trades:
            if trade.get('symbol', '').upper() == symbol.upper() and trade.get('strategy', '') == strategy:
                if trade.get('outcome') == self.OUTCOME_OPEN:
                    if entry > 0 and trade.get('entry', 0) > 0:
                        price_diff_pct = abs(trade.get('entry', 0) - entry) / entry * 100
                        if price_diff_pct > tolerance:
                            continue
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
    
    def get_active_trades(self) -> List[Dict[str, Any]]:
        """Get all active (open) trades."""
        return [t for t in self.trades if t.get('outcome') == self.OUTCOME_OPEN]
    
    def get_all_symbols(self) -> set:
        """Get all unique symbols from the journal (for deduplication)."""
        symbols = set()
        for trade in self.trades:
            symbols.add(trade.get('symbol', '').upper())
        return symbols
    
    def update_trade_field(self, trade_id: str, field: str, value: Any) -> bool:
        """Update a specific field in a trade."""
        for trade in self.trades:
            if trade.get('trade_id') == trade_id:
                trade[field] = value
                trade['updated_at'] = datetime.now().isoformat()
                self._save_trades()
                return True
        return False
    
    def get_open_trades(self, limit: int = 100) -> List[Dict[str, Any]]:
        open_trades = [t for t in self.trades if t.get('outcome') == self.OUTCOME_OPEN]
        return open_trades[-limit:] if limit > 0 else open_trades
    
    def get_closed_trades(self, limit: int = 100) -> List[Dict[str, Any]]:
        closed = [t for t in self.trades if t.get('outcome') != self.OUTCOME_OPEN]
        return closed[-limit:] if limit > 0 else closed
    
    def get_trades_by_strategy(self, strategy: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get last N trades for a specific strategy."""
        strategy_trades = [t for t in self.trades if t.get('strategy') == strategy]
        return strategy_trades[-limit:] if limit > 0 else strategy_trades
    
    def get_recent_trades(self, days: int = 30, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get trades from the last N days.
        
        Args:
            days: Number of days to look back
            limit: Maximum number of trades to return
            
        Returns:
            List of trades from the specified period
        """
        cutoff = datetime.now() - timedelta(days=days)
        recent_trades = []
        
        for trade in self.trades:
            try:
                timestamp = datetime.fromisoformat(trade.get('timestamp', ''))
                if timestamp >= cutoff:
                    recent_trades.append(trade)
            except (ValueError, TypeError):
                continue
        
        recent_trades.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        return recent_trades[:limit] if limit > 0 else recent_trades
    
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
    
    def get_expectancy(self) -> float:
        """
        Calculate trade expectancy - the core AI feedback metric.
        
        Expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
        
        Returns:
            Expectancy value (positive = profitable system)
        """
        closed = self.get_closed_trades(limit=1000)
        
        wins = [t for t in closed if t.get('outcome') == self.OUTCOME_WIN]
        losses = [t for t in closed if t.get('outcome') == self.OUTCOME_LOSS]
        
        if not closed:
            return 0.0
        
        win_rate = len(wins) / len(closed)
        
        avg_win = sum([t.get('rr_achieved', 0) for t in wins]) / len(wins) if wins else 0
        avg_loss = abs(sum([t.get('rr_achieved', 0) for t in losses]) / len(losses)) if losses else 0
        
        return round((win_rate * avg_win) - ((1 - win_rate) * avg_loss), 2)
    
    def get_strategy_performance(self) -> Dict[str, Any]:
        """
        Get performance metrics by strategy.
        
        Returns:
            Dictionary with per-strategy performance (trades, win_rate, avg_rr)
        """
        result = {}
        
        for strategy in ['TREND', 'VERC', 'MTF']:
            trades = self.get_trades_by_strategy(strategy, limit=500)
            closed = [t for t in trades if t.get('outcome') != self.OUTCOME_OPEN]
            
            if not closed:
                continue
            
            wins = [t for t in closed if t.get('outcome') == self.OUTCOME_WIN]
            
            result[strategy] = {
                'trades': len(closed),
                'win_rate': round(len(wins) / len(closed) * 100, 2),
                'avg_rr': round(sum(t.get('rr_achieved', 0) for t in closed) / len(closed), 2)
            }
        
        return result
    
    def get_context_stats(self) -> Dict[str, Any]:
        """Get win rate statistics by market context."""
        closed_trades = self.get_closed_trades(limit=1000)
        
        contexts = ['BULLISH', 'SIDEWAYS', 'BEARISH']
        stats = {}
        
        for ctx in contexts:
            ctx_trades = [t for t in closed_trades if t.get('market_context', '').upper() == ctx]
            if not ctx_trades:
                stats[ctx] = {'trades': 0, 'wins': 0, 'losses': 0, 'win_rate': 0}
                continue
            
            wins = [t for t in ctx_trades if t.get('outcome') == self.OUTCOME_WIN]
            losses = [t for t in ctx_trades if t.get('outcome') == self.OUTCOME_LOSS]
            
            stats[ctx] = {
                'trades': len(ctx_trades),
                'wins': len(wins),
                'losses': len(losses),
                'win_rate': round(len(wins) / len(ctx_trades) * 100, 2) if ctx_trades else 0
            }
        
        return stats
    
    def validate_before_log(
        self,
        symbol: str,
        strategy: str,
        direction: str,
        entry: float,
        stop_loss: float,
        target_1: float,
        indicators: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, str]:
        """
        Validate trade before logging to journal.
        
        Args:
            symbol: Stock symbol
            strategy: Strategy name
            direction: BUY or SELL
            entry: Entry price
            stop_loss: Stop loss price
            target_1: First target price
            indicators: Optional dict with resistance, support, recent_move_pct, consolidation_range
            
        Returns:
            Tuple of (is_valid, reason)
        """
        if self.is_blacklisted(symbol):
            return False, f"Blacklisted: {symbol}"
        
        if entry <= 0 or stop_loss <= 0 or target_1 <= 0:
            return False, "Invalid price values"
        
        if self.blacklist.get(symbol) and self.blacklist[symbol].get('expires_at'):
            return False, f"Recently failed: {symbol}"
        
        is_sell = direction.upper() == 'SELL'
        
        if is_sell:
            if not (entry > stop_loss and target_1 < entry):
                return False, "Invalid SELL structure"
        else:
            if not (entry > stop_loss and target_1 > entry):
                return False, "Invalid BUY structure"
        
        sl_pct = abs((entry - stop_loss) / entry) * 100
        target_pct = abs((target_1 - entry) / entry) * 100
        
        if sl_pct < self.filters["min_sl_pct"]:
            return False, f"SL too tight: {sl_pct:.2f}%"
        if sl_pct > self.filters["max_sl_pct"]:
            return False, f"SL too wide: {sl_pct:.2f}%"
        
        if target_pct < self.filters["min_target_pct"]:
            return False, f"Target too small: {target_pct:.2f}%"
        
        if target_pct > self.filters["max_target_pct"]:
            return False, f"Target too large (late entry): {target_pct:.2f}%"
        
        if sl_pct > 0:
            rr = target_pct / sl_pct
            if rr < self.filters["min_rr"]:
                return False, f"Low RR: {rr:.2f}"
        
        if indicators:
            resistance = indicators.get('resistance')
            support = indicators.get('support')
            
            if direction.upper() == 'BUY' and resistance and resistance > 0:
                dist_to_resistance = abs(resistance - entry) / entry
                if dist_to_resistance < self.filters["min_distance_sr"] / 100:
                    return False, "Too close to resistance"
            
            if direction.upper() == 'SELL' and support and support > 0:
                dist_to_support = abs(entry - support) / entry
                if dist_to_support < self.filters["min_distance_sr"] / 100:
                    return False, "Too close to support"
            
            recent_move_pct = indicators.get('recent_move_pct', 0)
            if recent_move_pct and abs(recent_move_pct) > self.filters["max_recent_move"]:
                return False, f"Overextended move ({abs(recent_move_pct):.1f}%)"
            
            consolidation_range = indicators.get('consolidation_range', 0)
            if consolidation_range and consolidation_range > self.filters["max_consolidation_range"]:
                return False, "No tight consolidation"
        
        return True, "VALID"


def create_trade_journal(data_dir: str = DATA_DIR) -> TradeJournal:
    """Factory function to create trade journal."""
    return TradeJournal(data_dir)