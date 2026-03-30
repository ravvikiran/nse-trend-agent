"""
Signal Tracker - Active Signal Monitoring
Tracks active signals until stop-loss or target is hit.
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import json

from .data_fetcher import DataFetcher
from .history_manager import HistoryManager

logger = logging.getLogger(__name__)


class SignalTracker:
    """
    Tracks active signals and monitors them until completion.
    Checks prices against SL and target levels.
    """
    
    # Signal outcomes
    OUTCOME_TARGET_HIT = 'TARGET_HIT'
    OUTCOME_SL_HIT = 'SL_HIT'
    OUTCOME_TIMEOUT = 'TIMEOUT'
    OUTCOME_PARTIAL = 'PARTIAL'
    OUTCOME_ACTIVE = 'ACTIVE'
    
    def __init__(self, history_manager: HistoryManager, data_fetcher: DataFetcher = None):
        """
        Initialize signal tracker.
        
        Args:
            history_manager: History manager for persistence
            data_fetcher: Data fetcher for current prices
        """
        self.history_manager = history_manager
        self.data_fetcher = data_fetcher or DataFetcher()
        
        logger.info("SignalTracker initialized")
    
    def check_signal(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check if a signal has hit target or SL.
        
        Args:
            signal: Signal data with levels
            
        Returns:
            Updated signal with status and outcome
        """
        stock_symbol = signal.get('stock_symbol')
        entry_price = signal.get('entry_price', 0)
        target_price = signal.get('target_price', 0)
        sl_price = signal.get('sl_price', 0)
        signal_type = signal.get('signal_type', 'BUY')  # BUY or SELL
        quantity = signal.get('quantity', 0)
        
        if not entry_price or not (target_price or sl_price):
            logger.warning(f"Invalid signal levels for {stock_symbol}")
            return signal
        
        try:
            # Get current price
            current_price = self._get_current_price(stock_symbol)
            
            if current_price is None:
                logger.warning(f"Could not fetch current price for {stock_symbol}")
                signal['current_price'] = None
                signal['status'] = self.OUTCOME_ACTIVE
                return signal
            
            signal['current_price'] = current_price
            signal['last_checked'] = datetime.now().isoformat()
            
            # Calculate current P&L
            if signal_type == 'BUY':
                # Prevent division by zero
                if entry_price and entry_price > 0:
                    price_change = ((current_price - entry_price) / entry_price) * 100
                    target_distance = ((target_price - entry_price) / entry_price) * 100 if target_price else 0
                    sl_distance = ((sl_price - entry_price) / entry_price) * 100 if sl_price else 0
                else:
                    price_change = 0
                    target_distance = 0
                    sl_distance = 0
                
                # Check target hit
                if target_price and current_price >= target_price:
                    signal['outcome'] = self.OUTCOME_TARGET_HIT
                    signal['status'] = 'COMPLETED'
                    signal['pnl_percent'] = price_change
                    logger.info(f"TARGET HIT: {stock_symbol} @ {current_price} (target: {target_price})")
                
                # Check SL hit
                elif sl_price and current_price <= sl_price:
                    signal['outcome'] = self.OUTCOME_SL_HIT
                    signal['status'] = 'COMPLETED'
                    signal['pnl_percent'] = price_change
                    logger.info(f"SL HIT: {stock_symbol} @ {current_price} (sl: {sl_price})")
                
                else:
                    signal['status'] = self.OUTCOME_ACTIVE
                    signal['pnl_percent'] = price_change
                    logger.debug(f"Active: {stock_symbol} @ {current_price}, P&L: {price_change:.2f}%")
            
            elif signal_type == 'SELL':
                # Prevent division by zero
                if entry_price and entry_price > 0:
                    price_change = ((entry_price - current_price) / entry_price) * 100
                else:
                    price_change = 0
                
                # For SELL signals, target is lower, SL is higher
                if target_price and current_price <= target_price:
                    signal['outcome'] = self.OUTCOME_TARGET_HIT
                    signal['status'] = 'COMPLETED'
                    signal['pnl_percent'] = price_change
                    logger.info(f"TARGET HIT (SELL): {stock_symbol} @ {current_price}")
                
                elif sl_price and current_price >= sl_price:
                    signal['outcome'] = self.OUTCOME_SL_HIT
                    signal['status'] = 'COMPLETED'
                    signal['pnl_percent'] = price_change
                    logger.info(f"SL HIT (SELL): {stock_symbol} @ {current_price}")
                
                else:
                    signal['status'] = self.OUTCOME_ACTIVE
                    signal['pnl_percent'] = price_change
            
            return signal
            
        except Exception as e:
            logger.error(f"Error checking signal {stock_symbol}: {e}")
            signal['error'] = str(e)
            return signal
    
    def _get_current_price(self, stock_symbol: str) -> Optional[float]:
        """Get current price for a stock with retry logic."""
        max_retries = 3
        retry_delay = 1  # seconds
        
        for attempt in range(max_retries):
            try:
                # Try to get live data
                stock_data = self.data_fetcher.fetch_stock_data(stock_symbol, interval='1d', days=2)
                
                if stock_data is not None and len(stock_data) > 0:
                    latest = stock_data.iloc[-1]
                    return float(latest.get('close', latest.get('Close', 0)))
                
                # If no data, try again
                if attempt < max_retries - 1:
                    logger.warning(f"No data for {stock_symbol}, retrying ({attempt + 1}/{max_retries})")
                    import time
                    time.sleep(retry_delay)
                    continue
                
                return None
                
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Error fetching price for {stock_symbol}: {e}, retrying ({attempt + 1}/{max_retries})")
                    import time
                    time.sleep(retry_delay)
                else:
                    logger.error(f"Error fetching price for {stock_symbol} after {max_retries} attempts: {e}")
                    return None
        
        return None
    
    def check_all_active_signals(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Check all active signals and return status.
        
        Returns:
            Dict with 'completed', 'still_active' lists
        """
        active_signals = self.history_manager.get_all_active_signals()
        
        completed = []
        still_active = []
        
        for signal in active_signals:
            updated = self.check_signal(signal)
            
            if updated.get('status') == 'COMPLETED':
                # Update in history
                signal_id = updated.get('signal_id')
                self.history_manager.update_active_signal(signal_id, updated)
                completed.append(updated)
            else:
                still_active.append(updated)
        
        logger.info(f"Checked {len(active_signals)} signals. Completed: {len(completed)}, Active: {len(still_active)}")
        
        return {
            'completed': completed,
            'still_active': still_active
        }
    
    def get_signals_needing_check(self, check_interval_hours: int = 4) -> List[Dict[str, Any]]:
        """
        Get signals that need to be checked based on interval.
        
        Args:
            check_interval_hours: Hours between checks
            
        Returns:
            List of signals to check
        """
        signals = self.history_manager.get_all_active_signals()
        now = datetime.now()
        to_check = []
        
        for signal in signals:
            last_checked = signal.get('last_checked')
            
            if not last_checked:
                to_check.append(signal)
                continue
            
            try:
                last_time = datetime.fromisoformat(last_checked)
                if (now - last_time).total_seconds() >= check_interval_hours * 3600:
                    to_check.append(signal)
            except:
                to_check.append(signal)
        
        return to_check
    
    def get_pending_signals_report(self) -> Dict[str, Any]:
        """
        Generate a report of all pending signals.
        
        Returns:
            Report dict with signal summaries
        """
        active_signals = self.history_manager.get_all_active_signals()
        
        report = {
            'generated_at': datetime.now().isoformat(),
            'total_active': len(active_signals),
            'signals': []
        }
        
        for signal in active_signals:
            current = self.check_signal(signal.copy())
            
            report['signals'].append({
                'signal_id': signal.get('signal_id'),
                'stock_symbol': signal.get('stock_symbol'),
                'signal_type': signal.get('signal_type'),
                'entry_price': signal.get('entry_price'),
                'target_price': signal.get('target_price'),
                'sl_price': signal.get('sl_price'),
                'current_price': current.get('current_price'),
                'pnl_percent': current.get('pnl_percent', 0),
                'added_at': signal.get('added_at'),
                'days_active': (datetime.now() - datetime.fromisoformat(signal.get('added_at', datetime.now().isoformat()))).days
            })
        
        return report
    
    def force_close_signal(self, signal_id: str, outcome: str, current_price: float) -> bool:
        """
        Manually close a signal.
        
        Args:
            signal_id: Signal to close
            outcome: Outcome reason
            current_price: Current market price
            
        Returns:
            True if successful
        """
        signal = self.history_manager.get_active_signal(signal_id)
        
        if not signal:
            logger.warning(f"Signal not found: {signal_id}")
            return False
        
        # Update signal
        signal['outcome'] = outcome
        signal['status'] = 'COMPLETED'
        signal['closed_at'] = datetime.now().isoformat()
        signal['current_price'] = current_price
        
        # Calculate final P&L
        entry = signal.get('entry_price', 0)
        if entry and current_price:
            signal_type = signal.get('signal_type', 'BUY')
            if signal_type == 'BUY':
                signal['pnl_percent'] = ((current_price - entry) / entry) * 100
            else:
                signal['pnl_percent'] = ((entry - current_price) / entry) * 100
        
        # Move to history
        self.history_manager.remove_active_signal(signal_id)
        
        logger.info(f"Force closed signal {signal_id}: {outcome}")
        
        return True
    
    def get_signals_summary(self) -> Dict[str, Any]:
        """Get a summary of all tracked signals."""
        active = self.history_manager.get_all_active_signals()
        
        # Get recent completions
        history = self.history_manager.get_history(limit=100)
        completed = [s for s in history if s.get('status') == 'COMPLETED']
        
        # Calculate win rate
        if completed:
            wins = len([s for s in completed if s.get('outcome') == self.OUTCOME_TARGET_HIT])
            total = len(completed)
            win_rate = (wins / total) * 100 if total > 0 else 0
        else:
            win_rate = 0
        
        return {
            'active_count': len(active),
            'completed_count': len(completed),
            'win_rate': win_rate,
            'recent_signals': completed[-10:] if completed else []
        }


def create_signal_tracker(history_manager: HistoryManager = None, data_fetcher: DataFetcher = None) -> SignalTracker:
    """Factory function to create signal tracker."""
    if not history_manager:
        history_manager = HistoryManager()
    return SignalTracker(history_manager, data_fetcher)