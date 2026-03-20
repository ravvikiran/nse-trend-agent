"""
Alert Service Module

Sends Telegram alerts when trend signals are detected.
"""

import logging
import requests
from typing import Optional, Dict, Any, List
from datetime import datetime
from src.trend_detector import TrendSignal

# Configure logging
logger = logging.getLogger(__name__)


class AlertService:
    """
    Handles sending alerts via Telegram Bot.
    
    Alert Message Format:
    ```
    TREND ALERT
    
    Stock: HDFCBANK
    Timeframe: 1D
    
    EMA Alignment:
    20 > 50 > 100 > 200
    
    Volume Spike Confirmed
    
    Possible Uptrend Starting
    ```
    """
    
    def __init__(self, bot_token: str, chat_id: str):
        """
        Initialize the AlertService.
        
        Args:
            bot_token: Telegram Bot API token
            chat_id: Target chat ID for alerts
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{bot_token}"
        self.enabled = bool(bot_token and chat_id)
        
        if self.enabled:
            logger.debug("AlertService initialized with Telegram enabled")
        else:
            logger.debug("AlertService initialized with Telegram DISABLED (no credentials)")
    
    def send_message(self, text: str, parse_mode: str = "Markdown") -> bool:
        """
        Send a message via Telegram.
        
        Args:
            text: Message text to send
            parse_mode: Message parse mode (Markdown or HTML)
            
        Returns:
            True if message sent successfully, False otherwise
        """
        if not self.enabled:
            logger.debug(f"Telegram disabled, would have sent: {text[:50]}...")
            return True  # Return True in test mode
        
        try:
            url = f"{self.api_url}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": parse_mode
            }
            
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            
            logger.debug(f"Alert sent successfully")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send Telegram alert: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending alert: {str(e)}")
            return False
    
    def format_alert_message(self, signal: TrendSignal) -> str:
        """
        Format a trend signal as a Telegram alert message.
        
        Args:
            signal: TrendSignal object
            
        Returns:
            Formatted message string
        """
        ind = signal.indicators
        
        # Format timestamp
        if isinstance(signal.timestamp, datetime):
            timestamp_str = signal.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        else:
            timestamp_str = str(signal.timestamp)
        
        # Get EMA alignment string
        ema_alignment = self._get_ema_alignment(ind)
        
        # Calculate volume ratio
        volume_ratio = ind.get('volume', 0) / ind.get('volume_ma', 1) if ind.get('volume_ma') else 0
        
        # Build message
        message = f"🚨 *TREND ALERT*\n\n"
        message += f"📌 *Stock:* `{ind.get('ticker', signal.ticker)}`\n"
        message += f"⏰ *Time:* {timestamp_str}\n"
        message += f"📊 *Timeframe:* 1D\n\n"
        message += f"*Signal Type:* {signal.message}\n\n"
        message += f"*Price:* ₹{ind.get('close', 0):.2f}\n"
        message += f"*EMA Alignment:*\n"
        message += f"  • EMA 20: ₹{ind.get('ema_20', 0):.2f}\n"
        message += f"  • EMA 50: ₹{ind.get('ema_50', 0):.2f}\n"
        message += f"  • EMA 100: ₹{ind.get('ema_100', 0):.2f}\n"
        message += f"  • EMA 200: ₹{ind.get('ema_200', 0):.2f}\n\n"
        message += f"*Volume:*\n"
        message += f"  • Current: {ind.get('volume', 0):,}\n"
        message += f"  • MA 30: {ind.get('volume_ma', 0):,.0f}\n"
        message += f"  • Ratio: {volume_ratio:.2f}x\n\n"
        
        # Add RSI if available
        if ind.get('rsi'):
            message += f"*RSI (14):* {ind.get('rsi', 0):.1f}\n"
        
        # Add MACD if available
        if ind.get('macd'):
            message += f"*MACD:* {ind.get('macd', 0):.4f}\n"
        
        message += f"\n_EMA Alignment: {ema_alignment}_"
        
        return message
    
    def _get_ema_alignment(self, indicators: Dict[str, Any]) -> str:
        """
        Get a visual representation of EMA alignment.
        
        Args:
            indicators: Dictionary with indicator values
            
        Returns:
            String like "20 > 50 > 100 > 200" or "20 < 50 < 100 < 200"
        """
        try:
            ema_20 = indicators.get('ema_20', 0)
            ema_50 = indicators.get('ema_50', 0)
            ema_100 = indicators.get('ema_100', 0)
            ema_200 = indicators.get('ema_200', 0)
            
            parts = []
            for a, b in [(ema_20, ema_50), (ema_50, ema_100), (ema_100, ema_200)]:
                if a > b:
                    parts.append(">")
                else:
                    parts.append("<")
            
            return f"20 {parts[0]} 50 {parts[1]} 100 {parts[2]} 200"
            
        except Exception as e:
            logger.error(f"Error getting EMA alignment: {str(e)}")
            return "Unknown"
    
    def send_alert(self, signal) -> bool:
        """
        Send an alert for a trend signal.
        
        Args:
            signal: TrendSignal object or string message
            
        Returns:
            True if alert sent successfully, False otherwise
        """
        # If already a string, send directly
        if isinstance(signal, str):
            return self.send_message(signal)
        
        # Otherwise format as TrendSignal
        message = self.format_alert_message(signal)
        return self.send_message(message)
    
    def send_batch_alerts(self, signals: List[TrendSignal]) -> int:
        """
        Send alerts for multiple trend signals.
        
        Args:
            signals: List of TrendSignal objects
            
        Returns:
            Number of alerts sent successfully
        """
        success_count = 0
        
        for signal in signals:
            if self.send_alert(signal):
                success_count += 1
        
        logger.debug(f"Sent {success_count}/{len(signals)} batch alerts")
        return success_count
    
    def send_system_status(self, message: str) -> bool:
        """
        Send a system status message.
        
        Args:
            message: Status message to send
            
        Returns:
            True if message sent successfully
        """
        status_message = f"📡 *System Status*\n\n{message}"
        return self.send_message(status_message)
    
    def test_connection(self) -> bool:
        """
        Test the Telegram bot connection.
        
        Returns:
            True if connection successful, False otherwise
        """
        if not self.enabled:
            logger.debug("Cannot test Telegram connection - credentials not configured")
            return False
        
        try:
            url = f"{self.api_url}/getMe"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            bot_info = response.json()
            if bot_info.get('ok'):
                logger.debug(f"Telegram bot connected: @{bot_info['result']['username']}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Telegram connection test failed: {str(e)}")
            return False
    
    def send_daily_summary(self, total_scanned: int, signals_found: int, 
                          alerted_stocks: List[str]) -> bool:
        """
        Send a daily summary message.
        
        Args:
            total_scanned: Total stocks scanned
            signals_found: Total signals found
            alerted_stocks: List of stocks that were alerted
            
        Returns:
            True if message sent successfully
        """
        message = f"📊 *Daily Summary*\n\n"
        message += f"• Stocks Scanned: {total_scanned}\n"
        message += f"• Signals Found: {signals_found}\n"
        message += f"• Stocks Alerted: {len(alerted_stocks)}\n\n"
        
        if alerted_stocks:
            message += f"*Alerted Stocks:*\n"
            for stock in alerted_stocks[:10]:  # Show max 10
                message += f"  • {stock}\n"
            
            if len(alerted_stocks) > 10:
                message += f"  • ... and {len(alerted_stocks) - 10} more"
        
        return self.send_message(message)


class MockAlertService(AlertService):
    """
    Mock AlertService for testing without Telegram credentials.
    """
    
    def __init__(self):
        """Initialize mock alert service."""
        super().__init__(bot_token="", chat_id="")
        self.sent_messages = []
        self.enabled = True  # Enable for testing
    
    def send_message(self, text: str, parse_mode: str = "Markdown") -> bool:
        """Store message instead of sending."""
        self.sent_messages.append(text)
        logger.debug(f"[MOCK] Would send alert: {text[:100]}...")
        return True
    
    def get_sent_messages(self) -> List[str]:
        """Get list of sent messages."""
        return self.sent_messages
    
    def clear_messages(self):
        """Clear sent messages."""
        self.sent_messages.clear()
