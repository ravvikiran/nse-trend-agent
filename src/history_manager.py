"""
History Manager - Signal Data Persistence
Manages storage of active signals and signal history for learning.
"""

import os
import json
import logging
import shutil
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)

# Data directory
DATA_DIR = 'data'


class HistoryManager:
    """
    Manages signal data persistence.
    Handles active signals and historical signal records.
    """
    
    # File names
    ACTIVE_SIGNALS_FILE = 'signals_active.json'
    HISTORY_FILE = 'signals_history.json'
    PERFORMANCE_FILE = 'performance_metrics.json'
    WEIGHTS_FILE = 'weight_config.json'
    
    def __init__(self, data_dir: str = DATA_DIR):
        """
        Initialize history manager.
        
        Args:
            data_dir: Directory for data files
        """
        self.data_dir = data_dir
        self._ensure_data_dir()
        
        # Thread lock for file operations
        self._lock = threading.Lock()
        
        # Load existing data
        self.active_signals = self._load_active_signals()
        self.history = self._load_history()
        
        logger.info(f"HistoryManager initialized. Active: {len(self.active_signals)}, History: {len(self.history)}")
    
    def _ensure_data_dir(self) -> None:
        """Create data directory if it doesn't exist."""
        os.makedirs(self.data_dir, exist_ok=True)
        logger.debug(f"Data directory ensured: {self.data_dir}")
    
    def _load_active_signals(self) -> Dict[str, Any]:
        """Load active signals from file."""
        filepath = os.path.join(self.data_dir, self.ACTIVE_SIGNALS_FILE)
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                    logger.debug(f"Loaded {len(data.get('signals', {}))} active signals")
                    return data.get('signals', {})
            except Exception as e:
                logger.error(f"Error loading active signals: {e}")
                return {}
        return {}
    
    def _save_active_signals(self) -> None:
        """Save active signals to file (thread-safe)."""
        filepath = os.path.join(self.data_dir, self.ACTIVE_SIGNALS_FILE)
        data = {
            'version': '1.0',
            'last_updated': datetime.now().isoformat(),
            'signals': self.active_signals
        }
        try:
            with self._lock:
                with open(filepath, 'w') as f:
                    json.dump(data, f, indent=2, default=str)
            logger.debug(f"Saved {len(self.active_signals)} active signals")
        except Exception as e:
            logger.error(f"Error saving active signals: {e}")
    
    def _load_history(self) -> Dict[str, Any]:
        """Load signal history from file."""
        filepath = os.path.join(self.data_dir, self.HISTORY_FILE)
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                    logger.debug(f"Loaded {len(data.get('signals', []))} historical signals")
                    return data
            except Exception as e:
                logger.error(f"Error loading history: {e}")
                return {'version': '1.0', 'signals': []}
        return {'version': '1.0', 'signals': []}
    
    def _save_history(self) -> None:
        """Save signal history to file (thread-safe)."""
        filepath = os.path.join(self.data_dir, self.HISTORY_FILE)
        self.history['last_updated'] = datetime.now().isoformat()
        try:
            with self._lock:
                with open(filepath, 'w') as f:
                    json.dump(self.history, f, indent=2, default=str)
            logger.debug(f"Saved {len(self.history.get('signals', []))} historical signals")
        except Exception as e:
            logger.error(f"Error saving history: {e}")
    
    # ==================== Active Signal Management ====================
    
    def add_active_signal(self, signal_data: Dict[str, Any]) -> str:
        """
        Add a new active signal for tracking (thread-safe).
        
        Args:
            signal_data: Signal information including stock, levels, etc.
            
        Returns:
            Signal ID
        """
        signal_id = signal_data.get('signal_id')
        
        with self._lock:
            # Store signal data
            self.active_signals[signal_id] = {
                **signal_data,
                'status': 'ACTIVE',
                'added_at': datetime.now().isoformat(),
                'last_checked': datetime.now().isoformat()
            }
            
            self._save_active_signals()
        
        logger.info(f"Added active signal: {signal_data.get('stock_symbol')} ({signal_id})")
        
        return signal_id
    
    def update_active_signal(self, signal_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update an active signal.
        
        Args:
            signal_id: Signal to update
            updates: Fields to update
            
        Returns:
            True if updated, False if not found
        """
        if signal_id not in self.active_signals:
            logger.warning(f"Signal not found for update: {signal_id}")
            return False
        
        self.active_signals[signal_id].update(updates)
        self.active_signals[signal_id]['last_checked'] = datetime.now().isoformat()
        
        self._save_active_signals()
        
        return True
    
    def remove_active_signal(self, signal_id: str) -> bool:
        """
        Remove an active signal (moves to history).
        
        Args:
            signal_id: Signal to remove
            
        Returns:
            True if removed
        """
        if signal_id not in self.active_signals:
            logger.warning(f"Signal not found for removal: {signal_id}")
            return False
        
        # Get signal data before removal
        signal_data = self.active_signals[signal_id]
        
        # Add to history
        self.add_to_history(signal_data)
        
        # Remove from active
        del self.active_signals[signal_id]
        self._save_active_signals()
        
        logger.info(f"Removed active signal: {signal_id}")
        
        return True
    
    def get_active_signal(self, signal_id: str) -> Optional[Dict[str, Any]]:
        """Get an active signal by ID."""
        return self.active_signals.get(signal_id)
    
    def get_active_signals_for_stock(self, stock_symbol: str) -> List[Dict[str, Any]]:
        """Get all active signals for a specific stock."""
        return [
            s for s in self.active_signals.values()
            if s.get('stock_symbol') == stock_symbol
        ]
    
    def get_all_active_signals(self) -> List[Dict[str, Any]]:
        """Get all active signals."""
        return list(self.active_signals.values())
    
    def get_active_count(self) -> int:
        """Get count of active signals."""
        return len(self.active_signals)
    
    # ==================== History Management ====================
    
    def add_to_history(self, signal_data: Dict[str, Any]) -> None:
        """
        Add completed signal to history.
        
        Args:
            signal_data: Completed signal data
        """
        if 'signals' not in self.history:
            self.history['signals'] = []
        
        # Add completion metadata
        signal_data['completed_at'] = datetime.now().isoformat()
        
        self.history['signals'].append(signal_data)
        
        # Keep only last 1000 signals for performance
        if len(self.history['signals']) > 1000:
            self.history['signals'] = self.history['signals'][-1000:]
        
        self._save_history()
        
        logger.info(f"Added to history: {signal_data.get('stock_symbol')} - {signal_data.get('outcome')}")
    
    def get_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent signal history."""
        signals = self.history.get('signals', [])
        return signals[-limit:] if limit > 0 else signals
    
    def get_history_for_stock(self, stock_symbol: str) -> List[Dict[str, Any]]:
        """Get history for a specific stock."""
        return [
            s for s in self.history.get('signals', [])
            if s.get('stock_symbol') == stock_symbol
        ]
    
    def get_completed_signals(self) -> List[Dict[str, Any]]:
        """Get all signals that have been completed."""
        return [
            s for s in self.history.get('signals', [])
            if s.get('status') == 'COMPLETED'
        ]
    
    # ==================== Cleanup & Maintenance ====================
    
    def cleanup_expired_signals(self, expiry_days: int = 30) -> List[Dict[str, Any]]:
        """
        Remove signals that have exceeded expiry time.
        
        Args:
            expiry_days: Days after which signal expires
            
        Returns:
            List of expired signals
        """
        expired = []
        cutoff = datetime.now() - timedelta(days=expiry_days)
        
        for signal_id, signal in list(self.active_signals.items()):
            try:
                added_at = datetime.fromisoformat(signal.get('added_at', ''))
                if added_at < cutoff:
                    signal['status'] = 'EXPIRED'
                    signal['outcome'] = 'TIMEOUT'
                    self.add_to_history(signal)
                    del self.active_signals[signal_id]
                    expired.append(signal)
                    logger.info(f"Expired signal: {signal.get('stock_symbol')} ({signal_id})")
            except Exception as e:
                logger.error(f"Error checking signal expiry: {e}")
        
        if expired:
            self._save_active_signals()
        
        return expired
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current statistics."""
        total_active = len(self.active_signals)
        total_history = len(self.history.get('signals', []))
        
        completed = self.get_completed_signals()
        
        return {
            'active_signals': total_active,
            'historical_signals': total_history,
            'completed_signals': len(completed)
        }
    
    # ==================== Performance Metrics ====================
    
    def get_performance_data(self) -> Dict[str, Any]:
        """Get performance data for analytics."""
        return self._load_performance_file()
    
    def save_performance_data(self, data: Dict[str, Any]) -> None:
        """Save performance data (thread-safe)."""
        filepath = os.path.join(self.data_dir, self.PERFORMANCE_FILE)
        data['last_updated'] = datetime.now().isoformat()
        
        try:
            with self._lock:
                with open(filepath, 'w') as f:
                    json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error saving performance data: {e}")
    
    def _load_performance_file(self) -> Dict[str, Any]:
        """Load performance metrics from file."""
        filepath = os.path.join(self.data_dir, self.PERFORMANCE_FILE)
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading performance data: {e}")
                return {}
        return {}
    
    # ==================== Weight Configuration ====================
    
    def get_weights_config(self) -> Dict[str, Any]:
        """Get scoring weights configuration."""
        filepath = os.path.join(self.data_dir, self.WEIGHTS_FILE)
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading weights config: {e}")
        return {}
    
    def save_weights_config(self, weights: Dict[str, Any]) -> None:
        """Save scoring weights configuration (thread-safe)."""
        filepath = os.path.join(self.data_dir, self.WEIGHTS_FILE)
        
        try:
            with self._lock:
                with open(filepath, 'w') as f:
                    json.dump(weights, f, indent=2)
            logger.info("Saved weights configuration")
        except Exception as e:
            logger.error(f"Error saving weights config: {e}")
    
    # ==================== Export ====================
    
    def export_history_csv(self, filepath: str) -> bool:
        """Export history to CSV format."""
        try:
            import csv
            
            signals = self.history.get('signals', [])
            
            if not signals:
                logger.warning("No history to export")
                return False
            
            # Get all possible keys
            keys = set()
            for s in signals:
                keys.update(s.keys())
            
            with open(filepath, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=sorted(list(keys)))
                writer.writeheader()
                writer.writerows(signals)
            
            logger.info(f"Exported {len(signals)} signals to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Error exporting to CSV: {e}")
            return False


def create_history_manager(data_dir: str = DATA_DIR) -> HistoryManager:
    """Factory function to create history manager."""
    return HistoryManager(data_dir)