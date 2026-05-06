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

try:
    from src.core.trend_detector import TrendSignal
except ImportError:
    from core.trend_detector import TrendSignal

try:
    from src.ai.ai_stock_analyzer import create_analyzer, AIStockAnalyzer
except ImportError:
    from ai.ai_stock_analyzer import create_analyzer, AIStockAnalyzer

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

    def __init__(self, bot_token: str, chat_id: str, channel_chat_id: str = None):
        """
        Initialize the AlertService.

        Args:
            bot_token: Telegram Bot API token
            chat_id: Target chat ID for alerts
            channel_chat_id: Channel chat ID for sending signals to channels (e.g., -1003801351128)
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.channel_chat_id = channel_chat_id
        self.api_url = f"https://api.telegram.org/bot{bot_token}"
        self.enabled = bool(bot_token and (chat_id or channel_chat_id))

        if self.enabled:
            logger.debug("AlertService initialized with Telegram enabled")
            if channel_chat_id:
                logger.debug(f"Channel mode enabled: {channel_chat_id}")
        else:
            logger.debug(
                "AlertService initialized with Telegram DISABLED (no credentials)"
            )

    def send_message(
        self, text: str, parse_mode: str = "Markdown", target_chat_id: str = None
    ) -> bool:
        """
        Send a message via Telegram.

        Args:
            text: Message text to send
            parse_mode: Message parse mode (Markdown or HTML)
            target_chat_id: Override target chat ID (for channel support)

        Returns:
            True if message sent successfully, False otherwise
        """
        if not self.enabled:
            logger.debug(f"Telegram disabled, would have sent: {text[:50]}...")
            return True  # Return True in test mode

        # Determine which chat ID to use: channel_chat_id > target_chat_id > chat_id
        chat_id = target_chat_id or self.channel_chat_id or self.chat_id

        if not chat_id:
            logger.error("No chat ID configured")
            return False

        try:
            url = f"{self.api_url}/sendMessage"
            payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}

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

        current_price = ind.get("close", 0)

        entry_zone = current_price * 1.005
        stop_loss = current_price * 0.98
        target_1 = current_price * 1.061
        target_2 = current_price * 1.122

        sl_pct = ((stop_loss / current_price) - 1) * 100
        t1_pct = ((target_1 / current_price) - 1) * 100
        t2_pct = ((target_2 / current_price) - 1) * 100

        score = signal.trend_score if signal.trend_score else 0

        message = f"Stock: {ind.get('ticker', signal.ticker)}\n\n"
        message += f"💰 Price: ₹{current_price:.2f}\n\n"
        message += f"🎯 Entry Zone:\n"
        message += f"  Buy Above: ₹{entry_zone:.2f}\n\n"
        message += f"🛡️ Stop Loss:\n"
        message += f"  SL: ₹{stop_loss:.2f} ({sl_pct:.1f}%)\n\n"
        message += f"🎯 Targets (RR ≥ 2:1):\n"
        message += f"  Target 1: ₹{target_1:.2f} ({t1_pct:.1f}%)\n"
        message += f"  Target 2: ₹{target_2:.2f} ({t2_pct:.1f}%)\n\n"
        message += f"📊 Signal Metrics:\n"
        message += f"  Score: {score}/10"

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
            ema_20 = indicators.get("ema_20", 0)
            ema_50 = indicators.get("ema_50", 0)
            ema_100 = indicators.get("ema_100", 0)
            ema_200 = indicators.get("ema_200", 0)

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

    def send_to_channel(self, text: str) -> bool:
        """
        Send a message to the Telegram channel.

        Args:
            text: Message text to send

        Returns:
            True if message sent successfully, False otherwise
        """
        if not self.channel_chat_id:
            logger.debug("Channel chat ID not configured, falling back to default chat")
            return self.send_message(text)

        return self.send_message(text, target_chat_id=self.channel_chat_id)

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
            if bot_info.get("ok"):
                logger.debug(
                    f"Telegram bot connected: @{bot_info['result']['username']}"
                )
                return True
            return False

        except Exception as e:
            logger.error(f"Telegram connection test failed: {str(e)}")
            return False

    def send_daily_summary(
        self, total_scanned: int, signals_found: int, alerted_stocks: List[str]
    ) -> bool:
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

        return self.send_message(message)

    def send_no_signal_message(self) -> bool:
        """
        Send a 'No Signal Today' message when no valid signals are found.

        Returns:
            True if message sent successfully
        """
        from datetime import datetime
        import pytz

        ist = pytz.timezone("Asia/Kolkata")
        now = datetime.now(ist)

        message = f"""📊 DAILY SCAN UPDATE

❌ No high-quality signals found today.

System Status: ✅ Running
Market Condition: Possibly sideways / low momentum

⏰ Next scan: Tomorrow 3:00 PM IST"""

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

    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        data_fetcher=None,
        ai_analyzer: AIStockAnalyzer = None,
    ):
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
            "/start": self._cmd_start,
            "/help": self._cmd_help,
            "/analyze": self._cmd_analyze,
            "/ai": self._cmd_ai_analysis,
            "/trend": self._cmd_trend,
            "/status": self._cmd_status,
            "/signals": self._cmd_signals,
            "/next": self._cmd_next,
            "/prev": self._cmd_prev,
            "/refresh": self._cmd_refresh,
            "/stop": self._cmd_stop,
        }

        # Signals storage and pagination
        self._signals_cache = []
        self._current_page = 0
        self._signals_per_page = 5
        self._last_scan_time = None

    def _send_message(self, text: str, chat_id: str = None) -> bool:
        """Send a message to Telegram."""
        target_chat = chat_id or self.chat_id
        try:
            url = f"{self.api_url}/sendMessage"
            payload = {"chat_id": target_chat, "text": text, "parse_mode": "Markdown"}
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
• `/analyze [STOCK]` - Get AI-powered stock analysis
• `/trend [STOCK]` - Get trend analysis
• `/signals` - View paginated signals list
• `/next` / `/prev` - Navigate signals
• `/status` - Check scanner status
• `/refresh` - Run new scan instructions
• `/stop` - Stop the bot
• `/help` - Show help message

*Quick Analysis:*
Just send me a stock symbol (e.g., `RELIANCE`) and I'll analyze it!"""

    def _cmd_help(self, chat_id: str) -> str:
        """Handle /help command."""
        return """📖 *Help*

*Commands:*
• `/analyze RELIANCE` - AI analysis of a stock
• `/trend HDFCBANK` - Technical trend analysis
• `/signals` - View paginated signals (5 per page)
• `/next` - Next page of signals
• `/prev` - Previous page of signals
• `/refresh` - Instructions to run new scan
• `/stop` - Stop the bot
• `/status` - Scanner status

*Quick Usage:*
Just type a stock symbol to get instant analysis!"""

    def _cmd_status(self, chat_id: str) -> str:
        """Handle /status command."""
        ai_status = (
            "✅ Available" if self.ai_analyzer.is_available() else "❌ Not configured"
        )
        data_status = "✅ Connected" if self.data_fetcher else "❌ Not available"

        return f"""📊 *Scanner Status*

AI Analysis: {ai_status}
Data Feed: {data_status}
Bot: Running"""

    def _cmd_signals(self, args: str, chat_id: str) -> str:
        """Handle /signals command - Show paginated signals list."""
        if not self._signals_cache:
            return "📊 *No Signals*\n\nNo signals available. Run a scan to generate signals.\n\nUse /refresh to run a new scan."

        total_pages = (
            len(self._signals_cache) + self._signals_per_page - 1
        ) // self._signals_per_page
        self._current_page = 0

        return self._format_signals_page()

    def _cmd_next(self, args: str, chat_id: str) -> str:
        """Handle /next command - Navigate to next page of signals."""
        if not self._signals_cache:
            return "📊 *No Signals*\n\nNo signals available. Use /signals to view available signals."

        total_pages = (
            len(self._signals_cache) + self._signals_per_page - 1
        ) // self._signals_per_page
        self._current_page = (self._current_page + 1) % total_pages

        return self._format_signals_page()

    def _cmd_prev(self, args: str, chat_id: str) -> str:
        """Handle /prev command - Navigate to previous page of signals."""
        if not self._signals_cache:
            return "📊 *No Signals*\n\nNo signals available. Use /signals to view available signals."

        total_pages = (
            len(self._signals_cache) + self._signals_per_page - 1
        ) // self._signals_per_page
        self._current_page = (self._current_page - 1) % total_pages

        return self._format_signals_page()

    def _cmd_refresh(self, args: str, chat_id: str) -> str:
        """Handle /refresh command - Instructions to run new scan."""
        return """🔄 *Refresh Scanner*

To run a new scan, restart the scanner:
```bash
python -m src.main
```

The scanner runs every 15 minutes during market hours (9:15 AM - 3:30 PM IST)."""

    def _cmd_stop(self, args: str, chat_id: str) -> str:
        """Handle /stop command - Stop the bot."""
        self.running = False
        return "🛑 *Bot Stopped*\n\nThe scanner continues running in the background. Restart the bot to enable interactive commands again."

    def _format_signals_page(self) -> str:
        """Format the current page of signals."""
        start_idx = self._current_page * self._signals_per_page
        end_idx = min(start_idx + self._signals_per_page, len(self._signals_cache))
        page_signals = self._signals_cache[start_idx:end_idx]

        total_pages = (
            len(self._signals_cache) + self._signals_per_page - 1
        ) // self._signals_per_page

        message = f"📊 *Signals List* (Page {self._current_page + 1}/{total_pages})\n\n"

        for i, signal in enumerate(page_signals, start=start_idx + 1):
            stock = signal.get("stock_symbol", signal.get("ticker", "N/A"))
            signal_type = signal.get("signal_type", signal.get("type", "N/A"))
            confidence = signal.get("confidence", signal.get("score", "N/A"))
            price = signal.get("current_price", signal.get("price", 0))

            message += f"{i}. *{stock}*\n"
            message += f"   Type: {signal_type} | Conf: {confidence}/10\n"
            message += f"   Price: ₹{price:.2f}\n\n"

        message += "_Use /next or /prev to navigate_"

        return message

    def update_signals_cache(self, signals: List[Dict]):
        """Update the signals cache with new scan results."""
        self._signals_cache = signals
        self._current_page = 0
        self._last_scan_time = datetime.now()

    def add_signal(self, signal: Dict):
        """Add a single signal to the cache."""
        self._signals_cache.append(signal)

    async def _cmd_analyze(self, args: str, chat_id: str) -> str:
        """Handle /analyze command - AI-powered stock analysis."""
        symbol = args.strip().upper() if args else None

        if not symbol:
            return "⚠️ Please provide a stock symbol. Example: `/analyze RELIANCE`"

        # Normalize symbol
        if not symbol.endswith(".NS"):
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
                    analysis = self.ai_analyzer.analyze_stock(
                        symbol.replace(".NS", ""), market_data
                    )
                    return (
                        f"📈 *AI Analysis: {symbol.replace('.NS', '')}*\n\n{analysis}"
                    )
                else:
                    # Fall back to basic analysis
                    return self._basic_analysis(df, symbol.replace(".NS", ""))
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
        if not symbol.endswith(".NS"):
            symbol = f"{symbol}.NS"

        try:
            if self.data_fetcher:
                df = self.data_fetcher.fetch_stock_data(symbol, period="1mo")
                if df is None or df.empty:
                    return f"❌ Could not fetch data for {symbol}"

                return self._basic_analysis(df, symbol.replace(".NS", ""))
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
        ema20 = df["close"].ewm(span=20).mean().iloc[-1]
        ema50 = df["close"].ewm(span=50).mean().iloc[-1]
        ema100 = df["close"].ewm(span=100).mean().iloc[-1]
        ema200 = df["close"].ewm(span=200).mean().iloc[-1] if len(df) >= 200 else ema100

        # Calculate RSI
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = (100 - (100 / (1 + rs))).iloc[-1]

        # Calculate ATR
        high_low = df["high"] - df["low"]
        high_close = abs(df["high"] - df["close"].shift())
        low_close = abs(df["low"] - df["close"].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(14).mean().iloc[-1]

        # Volume analysis
        volume_ma30 = df["volume"].rolling(30).mean().iloc[-1]
        volume_ratio = latest["volume"] / volume_ma30 if volume_ma30 > 0 else 0

        # EMA alignment score
        ema_alignment_score = 0
        if ema20 > ema50:
            ema_alignment_score += 1
        if ema50 > ema100:
            ema_alignment_score += 1
        if ema100 > ema200:
            ema_alignment_score += 1

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
            recent_candles.append(
                {
                    "open": row["open"],
                    "high": row["high"],
                    "low": row["low"],
                    "close": row["close"],
                    "volume": row["volume"],
                }
            )

        return {
            "current_price": latest["close"],
            "open": latest["open"],
            "high": latest["high"],
            "low": latest["low"],
            "volume": latest["volume"],
            "ema20": ema20,
            "ema50": ema50,
            "ema100": ema100,
            "ema200": ema200,
            "rsi": rsi,
            "atr": atr,
            "volume_ma30": volume_ma30,
            "volume_ratio": volume_ratio,
            "ema_alignment_score": ema_alignment_score,
            "trend_direction": trend,
            "recent_candles": recent_candles,
            "nifty_trend": "Sideways",  # Default - would need Nifty data
            "sector_performance": "Unknown",
        }

    def _basic_analysis(self, df, symbol: str) -> str:
        """Basic technical analysis without AI."""
        import pandas as pd

        latest = df.iloc[-1]

        # Calculate EMAs
        ema20 = df["close"].ewm(span=20).mean().iloc[-1]
        ema50 = df["close"].ewm(span=50).mean().iloc[-1]
        ema100 = df["close"].ewm(span=100).mean().iloc[-1]

        # Calculate RSI
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss.replace(0, float("nan"))
        rsi = (100 - (100 / (1 + rs))).iloc[-1]
        if pd.isna(rsi):
            rsi = 50  # Default to neutral when no losses

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

*Price:* ₹{latest["close"]:.2f}
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
            if "message" not in message:
                return None

            msg = message["message"]
            chat_id = str(msg["chat"]["id"])
            text = msg.get("text", "").strip()

            # Check authorization (only respond to authorized chat_id)
            if chat_id != self.chat_id:
                return None

            # Handle commands
            if text.startswith("/"):
                parts = text.split(" ", 1)
                cmd = parts[0].lower()
                args = parts[1] if len(parts) > 1 else ""

                if cmd in self.commands:
                    # Handle async commands
                    import asyncio

                    if asyncio.iscoroutinefunction(self.commands[cmd]):
                        return asyncio.run(self.commands[cmd](args, chat_id))
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
        
        # Run analysis using asyncio.run (cleaner approach)
        import asyncio
        return asyncio.run(self._cmd_analyze(symbol, chat_id))

    def start_polling(self):
        """Start polling for messages (simple implementation)."""
        self.running = True
        last_update_id = 0

        while self.running:
            try:
                # Get updates
                url = f"{self.api_url}/getUpdates"
                params = {"timeout": 30, "offset": last_update_id + 1}

                response = requests.get(url, params=params, timeout=35)
                if response.status_code == 200:
                    updates = response.json().get("result", [])

                    for update in updates:
                        last_update_id = update["update_id"]

                        if "message" in update:
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
