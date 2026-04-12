"""
Notification Manager - Outcome Alerts & Reports
Handles Telegram notifications for signal outcomes and performance reports.
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import json

try:
    from .alert_service import AlertService
except ImportError:
    from alert_service import AlertService

logger = logging.getLogger(__name__)


class NotificationManager:
    """
    Manages notifications for signal outcomes and reports.
    Uses AlertService for Telegram messaging.
    """
    
    def __init__(self, alert_service: AlertService = None, history_manager=None, performance_tracker=None):
        """
        Initialize notification manager.
        
        Args:
            alert_service: Alert service for Telegram
            history_manager: History manager for data access
            performance_tracker: Performance tracker for reports
        """
        self.alert_service = alert_service or AlertService()
        self.history_manager = history_manager
        self.performance_tracker = performance_tracker
        self.last_report_time = {}
        
        logger.info("NotificationManager initialized")
    
    # ==================== Outcome Notifications ====================
    
    def notify_target_hit(self, signal: Dict[str, Any]) -> bool:
        """
        Send notification when target is hit.
        
        Args:
            signal: Signal data
            
        Returns:
            True if sent successfully
        """
        stock = signal.get('stock_symbol', 'Unknown')
        entry = signal.get('entry_price', 0)
        target = signal.get('target_price', 0)
        current = signal.get('current_price', 0)
        pnl = signal.get('pnl_percent', 0)
        
        message = f"""
🎯 TARGET HIT!

Stock: {stock}
Entry: ₹{entry:.2f}
Target: ₹{target:.2f}
Current: ₹{current:.2f}
P&L: +{pnl:.2f}%

Great profit locked! ✅
"""
        
        return self._send_notification(message, "TARGET_HIT")
    
    def notify_sl_hit(self, signal: Dict[str, Any]) -> bool:
        """
        Send notification when stop-loss is hit.
        
        Args:
            signal: Signal data
            
        Returns:
            True if sent successfully
        """
        stock = signal.get('stock_symbol', 'Unknown')
        entry = signal.get('entry_price', 0)
        sl = signal.get('sl_price', 0)
        current = signal.get('current_price', 0)
        pnl = signal.get('pnl_percent', 0)
        
        message = f"""
🛑 STOP-LOSS HIT

Stock: {stock}
Entry: ₹{entry:.2f}
SL: ₹{sl:.2f}
Current: ₹{current:.2f}
P&L: {pnl:.2f}%

Stop-loss triggered. Cut loss and move on. 📉
"""
        
        return self._send_notification(message, "SL_HIT")
    
    def notify_signal_completed(self, signal: Dict[str, Any]) -> bool:
        """
        Send notification for completed signal (generic).
        
        Args:
            signal: Signal data
            
        Returns:
            True if sent successfully
        """
        outcome = signal.get('outcome', 'UNKNOWN')
        
        if outcome == 'TARGET_HIT':
            return self.notify_target_hit(signal)
        elif outcome == 'SL_HIT':
            return self.notify_sl_hit(signal)
        else:
            return self._send_notification(f"Signal completed: {outcome}", "COMPLETED")
    
    def notify_new_signal(self, signal: Dict[str, Any]) -> bool:
        """
        Send formatted notification for a new trade signal.
        
        Args:
            signal: Signal data with setup details
            
        Returns:
            True if sent successfully
        """
        stock = signal.get('stock_symbol', 'Unknown')
        direction = signal.get('direction', 'BUY').upper()
        entry = signal.get('entry_price', 0)
        sl = signal.get('stop_loss', 0)
        t1 = signal.get('target_1', 0)
        t2 = signal.get('target_2', 0)
        rr1 = signal.get('risk_reward_1', 0)
        rr2 = signal.get('risk_reward_2', 0)
        
        emoji = "🔥" if direction == "BUY" else "📉"
        context = "BULLISH" if direction == "BUY" else "BEARISH"
        
        message = f"""
{emoji} {direction} TRADE ALERT

Stock: {stock}
Context: {context}
Entry: ₹{entry:.2f}
SL: ₹{sl:.2f}
Target 1: ₹{t1:.2f} (1:{rr1:.1f})
Target 2: ₹{t2:.2f} (1:{rr2:.1f})

Why:
"""
        
        reasons = []
        if signal.get('ema_aligned') in ['BULLISH', 'STRONG_BULLISH'] and direction == 'BUY':
            reasons.append("✔ EMA aligned")
        elif signal.get('ema_aligned') in ['BEARISH', 'STRONG_BEARISH'] and direction == 'SELL':
            reasons.append("✔ EMA aligned")
        
        vol_ratio = signal.get('volume_ratio', 0)
        if vol_ratio >= 1.5:
            reasons.append(f"✔ Volume spike ({vol_ratio:.1f}x)")
        
        if signal.get('breakout_strength', 0) >= 5:
            reasons.append("✔ Breakout confirmed")
        
        if signal.get('signal_type') == 'BREAKOUT':
            reasons.append("✔ Strong breakout")
        
        if signal.get('trend') == 'BULLISH' and direction == 'BUY':
            reasons.append("✔ Market supportive")
        elif signal.get('trend') == 'BEARISH' and direction == 'SELL':
            reasons.append("✔ Market supportive")
        
        if reasons:
            message += "\n".join(reasons)
        else:
            message += "  • Setup identified"
        
        score = signal.get('score') or signal.get('confidence', 0)
        if score:
            message += f"\n\nConfidence: {score}%"
        
        return self._send_notification(message, "NEW_SIGNAL")
    
    def notify_outcome_batch(self, completed_signals: List[Dict[str, Any]]) -> bool:
        """
        Send batch notification for multiple completed signals.
        
        Args:
            completed_signals: List of completed signals
            
        Returns:
            True if sent successfully
        """
        if not completed_signals:
            return False
        
        targets = [s for s in completed_signals if s.get('outcome') == 'TARGET_HIT']
        sls = [s for s in completed_signals if s.get('outcome') == 'SL_HIT']
        
        message = "📊 SIGNAL OUTCOME SUMMARY\n\n"
        
        if targets:
            message += f"🎯 Targets Hit: {len(targets)}\n"
            for s in targets:
                pnl = s.get('pnl_percent', 0)
                message += f"  • {s.get('stock_symbol')}: +{pnl:.2f}%\n"
        
        if sls:
            message += f"\n🛑 SL Hit: {len(sls)}\n"
            for s in sls:
                pnl = s.get('pnl_percent', 0)
                message += f"  • {s.get('stock_symbol')}: {pnl:.2f}%\n"
        
        # Summary
        total = len(completed_signals)
        win_rate = (len(targets) / total * 100) if total > 0 else 0
        
        total_pnl = sum(s.get('pnl_percent', 0) for s in completed_signals)
        
        message += f"\n📈 Win Rate: {win_rate:.1f}%"
        message += f"\n💰 Total P&L: {total_pnl:.2f}%"
        
        return self._send_notification(message, "BATCH_OUTCOME")
    
    # ==================== Active Signal Updates ====================
    
    def notify_active_signals(self, active_signals: List[Dict[str, Any]]) -> bool:
        """
        Send notification about current active signals.
        
        Args:
            active_signals: List of active signals
            
        Returns:
            True if sent successfully
        """
        if not active_signals:
            return self._send_notification("No active signals.", "ACTIVE")
        
        message = "📊 ACTIVE SIGNALS\n\n"
        
        for s in active_signals[:10]:  # Limit to 10
            stock = s.get('stock_symbol', 'Unknown')
            pnl = s.get('pnl_percent', 0)
            current = s.get('current_price', 0)
            
            emoji = "🟢" if pnl > 0 else "🔴"
            message += f"{emoji} {stock}: ₹{current:.2f} ({pnl:+.2f}%)\n"
        
        if len(active_signals) > 10:
            message += f"\n...and {len(active_signals) - 10} more"
        
        return self._send_notification(message, "ACTIVE")
    
    # ==================== Performance Reports ====================
    
    def send_daily_report(self, performance_data: Dict[str, Any]) -> bool:
        """
        Send daily performance report.
        
        Args:
            performance_data: Performance metrics
            
        Returns:
            True if sent successfully
        """
        siq = performance_data.get('siq_7_day', {})
        siq_score = siq.get('siq_score', 0)
        
        message = f"""
📈 DAILY PERFORMANCE REPORT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 Signal Intelligence (SIQ): {siq_score}/100

Signals (7-day):
  • Total: {siq.get('signal_count', 0)}
  • Win Rate: {siq.get('metrics', {}).get('win_rate', 0) * 100:.1f}%
  • Avg Return: {siq.get('metrics', {}).get('avg_return', 0) * 100:.2f}%
  • Consistency: {siq.get('metrics', {}).get('consistency', 0) * 100:.1f}%
"""
        
        # Add recommendations
        recommendations = performance_data.get('recommendations', [])
        if recommendations:
            message += "\n💡 Recommendations:"
            for rec in recommendations[:3]:
                message += f"\n  • {rec}"
        
        return self._send_notification(message, "DAILY_REPORT")
    
    def send_weekly_report(self, performance_data: Dict[str, Any]) -> bool:
        """
        Send weekly performance report.
        
        Args:
            performance_data: Performance metrics
            
        Returns:
            True if sent successfully
        """
        siq_30 = performance_data.get('siq_30_day', {})
        siq_7 = performance_data.get('siq_7_day', {})
        trends = performance_data.get('performance_trend', [])
        
        message = f"""
📊 WEEKLY PERFORMANCE REPORT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 SIQ Score: {siq_7.get('siq_score', 0)}/100 (7-day)
📈 30-Day SIQ: {siq_30.get('siq_score', 0)}/100

📈 Week Performance:
"""
        
        for trend in trends[:4]:
            message += f"  • {trend.get('period')}: {trend.get('win_rate', 0):.1f}% win rate, {trend.get('avg_return', 0):.2f}% avg\n"
        
        # Top performing stocks
        by_stock = performance_data.get('accuracy_by_stock', {})
        if by_stock:
            top_stocks = sorted(by_stock.items(), key=lambda x: x[1].get('win_rate', 0), reverse=True)[:3]
            message += "\n🏆 Top Performing Stocks:\n"
            for stock, data in top_stocks:
                message += f"  • {stock}: {data.get('win_rate', 0):.1f}% ({data.get('total_signals')} signals)\n"
        
        return self._send_notification(message, "WEEKLY_REPORT")
    
    def send_performance_alert(self, metric_name: str, value: float, threshold: float) -> bool:
        """
        Send alert for performance metrics hitting thresholds.
        
        Args:
            metric_name: Name of metric
            value: Current value
            threshold: Threshold value
            
        Returns:
            True if sent successfully
        """
        message = f"""
⚠️ PERFORMANCE ALERT

{metric_name} has reached {value:.2f}%
Threshold: {threshold:.2f}%
"""
        
        return self._send_notification(message, "ALERT")
    
    # ==================== Scheduled Notifications ====================
    
    def check_and_send_scheduled_reports(self, force: bool = False) -> Dict[str, bool]:
        """
        Check and send scheduled reports if due.
        
        Args:
            force: Force send regardless of schedule
            
        Returns:
            Dict of sent report types
        """
        results = {}
        now = datetime.now()
        
        # Daily report (9 AM)
        if force or self._is_due_for_report('daily', hours=24):
            try:
                # Get performance data
                if self.performance_tracker:
                    perf_data = self.performance_tracker.generate_performance_report()
                    success = self.send_daily_report(perf_data)
                    results['daily'] = success
                    
                    if success:
                        self.last_report_time['daily'] = now
                else:
                    logger.warning("No performance tracker available for daily report")
                    results['daily'] = False
                    
            except Exception as e:
                logger.error(f"Error sending daily report: {e}")
                results['daily'] = False
        
        # Weekly report (Sunday 10 AM)
        if force or (now.weekday() == 6 and now.hour >= 10):
            if force or self._is_due_for_report('weekly', hours=168):  # 7 days
                try:
                    if self.performance_tracker:
                        perf_data = self.performance_tracker.generate_performance_report()
                        success = self.send_weekly_report(perf_data)
                        results['weekly'] = success
                        
                        if success:
                            self.last_report_time['weekly'] = now
                    else:
                        logger.warning("No performance tracker available for weekly report")
                        results['weekly'] = False
                        
                except Exception as e:
                    logger.error(f"Error sending weekly report: {e}")
                    results['weekly'] = False
        
        return results
    
    def _is_due_for_report(self, report_type: str, hours: int) -> bool:
        """Check if report is due based on last sent time."""
        last_time = self.last_report_time.get(report_type)
        
        if not last_time:
            return True
        
        return (datetime.now() - last_time).total_seconds() >= hours * 3600
    
    # ==================== Helper Methods ====================
    
    def _send_notification(self, message: str, notification_type: str) -> bool:
        """
        Send notification via alert service.
        
        Args:
            message: Message to send
            notification_type: Type for logging
            
        Returns:
            True if sent successfully
        """
        try:
            success = self.alert_service.send_alert(message)
            
            if success:
                logger.info(f"Sent {notification_type} notification")
            else:
                logger.warning(f"Failed to send {notification_type} notification")
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
            return False
    
    def test_notification(self) -> bool:
        """Send a test notification."""
        message = "🔔 Test notification from NSE Trend Agent\n\nThis is a test to verify notifications are working."
        return self._send_notification(message, "TEST")
    
    # ==================== User Preferences ====================
    
    def get_user_preferences(self) -> Dict[str, Any]:
        """Get notification preferences."""
        return {
            'daily_reports': True,
            'weekly_reports': True,
            'target_alerts': True,
            'sl_alerts': True,
            'active_signals': True
        }
    
    def update_preferences(self, preferences: Dict[str, Any]) -> bool:
        """
        Update notification preferences.
        
        Args:
            preferences: New preferences
            
        Returns:
            True if successful
        """
        # Save preferences
        try:
            # Use data directory from project root
            data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
            prefs_file = os.path.join(data_dir, 'notification_preferences.json')
            os.makedirs(data_dir, exist_ok=True)
            
            with open(prefs_file, 'w') as f:
                json.dump(preferences, f, indent=2)
            
            logger.info("Updated notification preferences")
            return True
            
        except Exception as e:
            logger.error(f"Error updating preferences: {e}")
            return False


def create_notification_manager(alert_service: AlertService = None, history_manager=None, performance_tracker=None) -> NotificationManager:
    """Factory function to create notification manager."""
    return NotificationManager(alert_service, history_manager, performance_tracker)