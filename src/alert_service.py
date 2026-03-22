"""
Alert Service Module

Sends Telegram alerts when trend signals are detected.
Supports two-way communication for stock analysis requests.
"""

import logging
import requests
import threading
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime
from src.trend_detector import TrendSignal
from src.ai_stock_analyzer import create_analyzer, AIStockAnalyzer

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


class TelegramBotHandler:
    """
    Telegram Bot handler for two-way communication.
    Processes incoming messages and provides stock analysis.
    """
    
    def __init__(self, bot_token: str, chat_id: str, data_fetcher=None, ai_analyzer: AIStockAnalyzer = None):
        """
        Initialize the Telegram bot handler.
        
        Args:
            bot_token: Telegram bot token
            chat_id: Authorized chat ID for commands
            data_fetcher: DataFetcher instance for getting stock data
            ai_analyzer: AIStockAnalyzer instance for AI analysis
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{bot_token}"
        self.data_fetcher = data_fetcher
        self.ai_analyzer = ai_analyzer or create_analyzer()
        self.running = False
        
        # Command handlers
        self.commands = {
            '/start': self._cmd_start,
            '/help': self._cmd_help,
            '/analyze': self._cmd_analyze,
            '/ai': self._cmd_ai_analysis,
            '/trend': self._cmd_trend,
            '/status': self._cmd_status,
        }
    
    def _send_message(self, text: str, chat_id: str = None) -> bool:
        """Send a message to Telegram."""
        target_chat = chat_id or self.chat_id
        try:
            url = f"{self.api_url}/sendMessage"
            payload = {
                "chat_id": target_chat,
                "text": text,
                "parse_mode": "Markdown"
            }
            response = requests.post(url, json=payload, timeout=30)
            return response.status_code == 200
        except Exception as e:
            logging.error(f"Error sending message: {e}")
            return False
    
    def _cmd_start(self, chat_id: str) -> str:
        """Handle /start command."""
        return """🎉 *Welcome to NSE Trend Scanner Bot!*

I scan NSE stocks for trend and VERC signals.

*Available Commands:*
• /analyze [STOCK] - Get AI-powered stock analysis
• /trend [STOCK] - Get trend analysis
• /status - Check scanner status
• /help - Show this help message

*Quick Analysis:*
Just send me a stock symbol (e.g., `RELIANCE` or `RELIANCE.NS`) and I'll analyze it!"""

    def _cmd_help(self, chat_id: str) -> str:
        """Handle /help command."""
        return """📖 *Help*

*Commands:*
• `/analyze RELIANCE` - AI analysis of a stock
• `/trend HDFCBANK` - Technical trend analysis
• `/status` - Scanner status

*Quick Usage:*
Just type a stock symbol to get instant analysis!"""

    def _cmd_status(self, chat_id: str) -> str:
        """Handle /status command."""
        ai_status = "✅ Available" if self.ai_analyzer.is_available() else "❌ Not configured"
        data_status = "✅ Connected" if self.data_fetcher else "❌ Not available"
        
        return f"""📊 *Scanner Status*

AI Analysis: {ai_status}
Data Feed: {data_status}
Bot: Running"""

    async def _cmd_analyze(self, args: str, chat_id: str) -> str:
        """Handle /analyze command - AI-powered stock analysis."""
        symbol = args.strip().upper() if args else None
        
        if not symbol:
            return "⚠️ Please provide a stock symbol. Example: `/analyze RELIANCE`"
        
        # Normalize symbol
        if not symbol.endswith('.NS'):
            symbol = f"{symbol}.NS"
        
        # Send thinking message
        self._send_message("🤔 Analyzing...", chat_id)
        
        # Get stock data
        try:
            if self.data_fetcher:
                df = self.data_fetcher.fetch_stock_data(symbol, period="3mo")
                if df is None or df.empty:
                    return f"❌ Could not fetch data for {symbol}"
                
                # Prepare market data
                market_data = self._prepare_market_data(df, symbol)
                
                # Get AI analysis
                if self.ai_analyzer.is_available():
                    analysis = self.ai_analyzer.analyze_stock(symbol.replace('.NS', ''), market_data)
                    return f"📈 *AI Analysis: {symbol.replace('.NS', '')}*\n\n{analysis}"
                else:
                    # Fall back to basic analysis
                    return self._basic_analysis(df, symbol.replace('.NS', ''))
            else:
                return "❌ Data fetcher not available"
                
        except Exception as e:
            logging.error(f"Error analyzing stock {symbol}: {e}")
            return f"❌ Error analyzing {symbol}: {str(e)}"

    async def _cmd_ai_analysis(self, args: str, chat_id: str) -> str:
        """Alias for /analyze command."""
        return await self._cmd_analyze(args, chat_id)

    def _cmd_trend(self, args: str, chat_id: str) -> str:
        """Handle /trend command - Basic trend analysis."""
        symbol = args.strip().upper() if args else None
        
        if not symbol:
            return "⚠️ Please provide a stock symbol. Example: `/trend RELIANCE`"
        
        # Normalize symbol
        if not symbol.endswith('.NS'):
            symbol = f"{symbol}.NS"
        
        try:
            if self.data_fetcher:
                df = self.data_fetcher.fetch_stock_data(symbol, period="1mo")
                if df is None or df.empty:
                    return f"❌ Could not fetch data for {symbol}"
                
                return self._basic_analysis(df, symbol.replace('.NS', ''))
            else:
                return "❌ Data fetcher not available"
                
        except Exception as e:
            return f"❌ Error: {str(e)}"

    def _prepare_market_data(self, df, symbol: str) -> Dict[str, Any]:
        """Prepare market data for AI analysis."""
        import pandas as pd
        import pytz
        
        # Get latest data
        latest = df.iloc[-1]
        
        # Calculate EMAs
        ema20 = df['close'].ewm(span=20).mean().iloc[-1]
        ema50 = df['close'].ewm(span=50).mean().iloc[-1]
        ema100 = df['close'].ewm(span=100).mean().iloc[-1]
        ema200 = df['close'].ewm(span=200).mean().iloc[-1] if len(df) >= 200 else ema100
        
        # Calculate RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = (100 - (100 / (1 + rs))).iloc[-1]
        
        # Calculate ATR
        high_low = df['high'] - df['low']
        high_close = abs(df['high'] - df['close'].shift())
        low_close = abs(df['low'] - df['close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(14).mean().iloc[-1]
        
        # Volume analysis
        volume_ma30 = df['volume'].rolling(30).mean().iloc[-1]
        volume_ratio = latest['volume'] / volume_30 if volume_30 > 0 else 0
        
        # EMA alignment score
        ema_alignment_score = 0
        if ema20 > ema50: ema_alignment_score += 1
        if ema50 > ema100: ema_alignment_score += 1
        if ema100 > ema200: ema_alignment_score += 1
        
        # Trend direction
        if ema_alignment_score >= 3:
            trend = "Strong Uptrend"
        elif ema_alignment_score >= 2:
            trend = "Weak Uptrend"
        elif ema_alignment_score <= 1:
            trend = "Downtrend"
        else:
            trend = "Sideways"
        
        # Recent candles
        recent_candles = []
        for i, row in df.tail(5).iterrows():
            recent_candles.append({
                'open': row['open'],
                'high': row['high'],
                'low': row['low'],
                'close': row['close'],
                'volume': row['volume']
            })
        
        return {
            'current_price': latest['close'],
            'open': latest['open'],
            'high': latest['high'],
            'low': latest['low'],
            'volume': latest['volume'],
            'ema20': ema20,
            'ema50': ema50,
            'ema100': ema100,
            'ema200': ema200,
            'rsi': rsi,
            'atr': atr,
            'volume_ma30': volume_ma30,
            'volume_ratio': volume_ratio,
            'ema_alignment_score': ema_alignment_score,
            'trend_direction': trend,
            'recent_candles': recent_candles,
            'nifty_trend': 'Sideways',  # Default - would need Nifty data
            'sector_performance': 'Unknown'
        }

    def _basic_analysis(self, df, symbol: str) -> str:
        """Basic technical analysis without AI."""
        import pandas as pd
        
        latest = df.iloc[-1]
        
        # Calculate EMAs
        ema20 = df['close'].ewm(span=20).mean().iloc[-1]
        ema50 = df['close'].ewm(span=50).mean().iloc[-1]
        ema100 = df['close'].ewm(span=100).mean().iloc[-1]
        
        # Calculate RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = (100 - (100 / (1 + rs))).iloc[-1]
        
        # Determine trend
        if ema20 > ema50 > ema100:
            trend = "🟢 Bullish"
            rec = "BUY"
        elif ema20 < ema50 < ema100:
            trend = "🔴 Bearish"
            rec = "SELL"
        else:
            trend = "🟡 Sideways"
            rec = "HOLD"
        
        # RSI interpretation
        if rsi > 70:
            rsi_status = "Overbought"
        elif rsi < 30:
            rsi_status = "Oversold"
        else:
            rsi_status = "Neutral"
        
        return f"""📊 *Trend Analysis: {symbol}*

*Price:* ₹{latest['close']:.2f}
*Trend:* {trend}
*RSI (14):* {rsi:.1f} ({rsi_status})

*EMAs:*
• EMA 20: ₹{ema20:.2f}
• EMA 50: ₹{ema50:.2f}
• EMA 100: ₹{ema100:.2f}

*Recommendation:* {rec}"""

    def process_message(self, message: Dict) -> Optional[str]:
        """
        Process incoming Telegram message.
        
        Args:
            message: Telegram message dict
            
        Returns:
            Response message or None
        """
        try:
            # Extract message details
            if 'message' not in message:
                return None
            
            msg = message['message']
            chat_id = str(msg['chat']['id'])
            text = msg.get('text', '').strip()
            
            # Check authorization (only respond to authorized chat_id)
            if chat_id != self.chat_id:
                return None
            
            # Handle commands
            if text.startswith('/'):
                parts = text.split(' ', 1)
                cmd = parts[0].lower()
                args = parts[1] if len(parts) > 1 else ''
                
                if cmd in self.commands:
                    # Handle async commands
                    import asyncio
                    if asyncio.iscoroutinefunction(self.commands[cmd]):
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            return loop.run_until_complete(self.commands[cmd](args, chat_id))
                        finally:
                            loop.close()
                    else:
                        return self.commands[cmd](args, chat_id)
                else:
                    return f"Unknown command: {cmd}. Type /help for available commands."
            
            # Handle plain text (stock symbol)
            else:
                # Treat as stock symbol
                return self._handle_stock_query(text, chat_id)
                
        except Exception as e:
            logging.error(f"Error processing message: {e}")
            return f"Error processing request: {str(e)}"
    
    def _handle_stock_query(self, text: str, chat_id: str) -> str:
        """Handle plain text as stock symbol query."""
        symbol = text.strip().upper()
        
        # Run analysis
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self._cmd_analyze(symbol, chat_id))
        finally:
            loop.close()

    def start_polling(self):
        """Start polling for messages (simple implementation)."""
        self.running = True
        last_update_id = 0
        
        while self.running:
            try:
                # Get updates
                url = f"{self.api_url}/getUpdates"
                params = {
                    'timeout': 30,
                    'offset': last_update_id + 1
                }
                
                response = requests.get(url, params=params, timeout=35)
                if response.status_code == 200:
                    updates = response.json().get('result', [])
                    
                    for update in updates:
                        last_update_id = update['update_id']
                        
                        if 'message' in update:
                            response_text = self.process_message(update)
                            if response_text:
                                self._send_message(response_text)
                                
            except Exception as e:
                logging.error(f"Polling error: {e}")
                import time
                time.sleep(5)
    
    def start_background(self):
        """Start polling in background thread."""
        thread = threading.Thread(target=self.start_polling, daemon=True)
        thread.start()
        logging.info("Telegram bot handler started in background")
    
    def stop(self):
        """Stop the bot."""
        self.running = False
