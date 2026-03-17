"""
NSE Trend Scanner Agent - Main Entry Point

Automated trading scanner that monitors NSE stocks during market hours
and detects potential uptrend starts based on EMA alignment and volume confirmation.
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Optional
import pandas as pd
import pytz

# Fix Windows console encoding for emoji support
if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data_fetcher import DataFetcher
from src.indicator_engine import IndicatorEngine
from src.trend_detector import TrendDetector
from src.alert_service import AlertService, MockAlertService
from src.scheduler import MarketScheduler
from src.volume_compression import scan_stocks as verc_scan_stocks, format_alert as verc_format_alert


# Configure logging
def setup_logging(log_level: str = "INFO", log_file: Optional[str] = None):
    """Setup logging configuration."""
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    handlers = [logging.StreamHandler()]
    
    # Fix for Windows console Unicode encoding issues
    for handler in handlers:
        handler.setFormatter(logging.Formatter(log_format))
        try:
            handler.stream.reconfigure(encoding='utf-8')
        except:
            pass
    
    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding='utf-8'))
    
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format=log_format,
        handlers=handlers
    )


logger = logging.getLogger(__name__)


class NSETrendScanner:
    """
    Main application class for the NSE Trend Scanner Agent.
    
    Handles:
    - Stock data fetching
    - Indicator calculation
    - Trend detection
    - Alert sending
    - Scheduling
    """
    
    def __init__(self, config_path: str = "config/stocks.json", 
                 telegram_token: Optional[str] = None,
                 telegram_chat_id: Optional[str] = None,
                 use_mock_alerts: bool = False):
        """
        Initialize the NSE Trend Scanner.
        
        Args:
            config_path: Path to stocks configuration file
            telegram_token: Telegram bot token (optional, or use config/settings.json)
            telegram_chat_id: Telegram chat ID (optional, or use config/settings.json)
            use_mock_alerts: Use mock alert service for testing
        """
        # Load settings from config file
        self.settings = self._load_settings()
        
        # Use provided args or fall back to config file
        telegram_token = telegram_token or self.settings.get('telegram', {}).get('bot_token')
        telegram_chat_id = telegram_chat_id or self.settings.get('telegram', {}).get('chat_id')
        
        # Load configuration
        self.config_path = config_path
        self.stocks = self._load_stocks()
        
        logger.info(f"Initialized with {len(self.stocks)} stocks")
        
        # Initialize components
        self.data_fetcher = DataFetcher()
        self.indicator_engine = IndicatorEngine()
        self.trend_detector = TrendDetector()
        
        # Initialize alert service
        if use_mock_alerts:
            self.alert_service = MockAlertService()
            logger.info("Using Mock Alert Service")
        elif telegram_token and telegram_chat_id:
            self.alert_service = AlertService(telegram_token, telegram_chat_id)
            logger.info("Using Telegram Alert Service")
        else:
            self.alert_service = MockAlertService()
            logger.warning("No Telegram credentials provided, using Mock Alert Service")
        
        # Initialize scheduler
        self.scheduler = MarketScheduler()
        self.scheduler.set_scan_callback(self.scan)
        
        # Track previous signals to prevent repeat alerts
        self.previous_signals = set()
        
        # Statistics
        self.total_scans = 0
        self.total_signals = 0
        self.last_scan_time = None
        
        logger.info("NSE Trend Scanner initialized successfully")
    
    def _load_settings(self) -> dict:
        """Load settings from configuration file."""
        default_settings = {
            'telegram': {
                'bot_token': None,
                'chat_id': None
            },
            'scanner': {
                'timeframe': '1D',
                'scan_interval_minutes': 15,
                'max_signals_per_strategy': 2
            },
            'stocks': {
                'config_file': 'config/stocks.json'
            }
        }
        
        try:
            settings_file = Path('config/settings.json')
            if settings_file.exists():
                with open(settings_file, 'r') as f:
                    settings = json.load(f)
                    logger.info("Loaded settings from config/settings.json")
                    return settings
        except Exception as e:
            logger.warning(f"Could not load settings: {str(e)}")
        
        return default_settings
    
    def _load_stocks(self) -> List[str]:
        """Load stock list from configuration file."""
        try:
            config_file = Path(self.config_path)
            
            # Try different paths
            paths_to_try = [
                config_file,
                Path(__file__).parent.parent / self.config_path,
                Path.cwd() / self.config_path,
            ]
            
            for path in paths_to_try:
                if path.exists():
                    with open(path, 'r') as f:
                        stocks = json.load(f)
                    logger.info(f"Loaded {len(stocks)} stocks from {path}")
                    return stocks
            
            logger.warning(f"Config file not found, using default NIFTY 50 stocks")
            return self._get_default_stocks()
            
        except Exception as e:
            logger.error(f"Error loading stocks: {str(e)}")
            return self._get_default_stocks()
    
    def _get_default_stocks(self) -> List[str]:
        """Get default NIFTY 50 stocks."""
        return [
            "RELIANCE.NS", "HDFCBANK.NS", "TCS.NS", "INFY.NS",
            "ICICIBANK.NS", "HINDUNILVR.NS", "ITC.NS", "SBIN.NS",
            "BAJFINANCE.NS", "BHARTIARTL.NS", "KOTAKBANK.NS", "LT.NS",
            "AXISBANK.NS", "HDFC.NS", "ASIANPAINT.NS", "MARUTI.NS",
            "TITAN.NS", "SUNPHARMA.NS", "TATASTEEL.NS", "WIPRO.NS"
        ]
    
    def scan(self):
        """
        Execute one complete scan cycle running both strategies.
        
        Steps:
        1. Fetch stock data
        2. Run Trend Detection and VERC strategies
        3. Send unified alerts with entry/stop loss/targets
        """
        self.total_scans += 1
        scan_start = datetime.now()
        
        logger.info(f"=== Starting scan cycle #{self.total_scans} ===")
        
        # Reset daily alerts if needed
        self.trend_detector.reset_daily()
        
        try:
            # Step 1: Fetch data for all stocks
            logger.info("Fetching stock data...")
            stocks_data = self.data_fetcher.fetch_multiple_stocks(self.stocks)
            
            if not stocks_data:
                logger.warning("No stock data fetched, skipping scan")
                return
            
            logger.info(f"Fetched data for {len(stocks_data)} stocks")
            
            # Step 2: Run both strategies
            self._run_all_strategies(stocks_data)
            
            # Update statistics
            self.last_scan_time = datetime.now()
            scan_duration = (self.last_scan_time - scan_start).total_seconds()
            
            logger.info(f"=== Scan cycle #{self.total_scans} completed in {scan_duration:.1f}s ===")
            
        except Exception as e:
            logger.error(f"Error during scan: {str(e)}", exc_info=True)
    
    def _run_all_strategies(self, stocks_data):
        """
        Run both strategies (Trend + VERC) and generate unified alerts.
        Filters out repeat signals.
        """
        all_alerts = []
        current_signals = set()
        
        logger.info("=== Running Both Strategies (Trend + VERC) ===")
        
        # Run trend detection
        trend_signals = self._get_trend_signals(stocks_data)
        
        # Limit to top 2 trend signals
        trend_signals = trend_signals[:2] if trend_signals else []
        
        for signal in trend_signals:
            signal_key = f"TREND:{signal.ticker}"
            current_signals.add(signal_key)
            
            # Only alert if new signal
            if signal_key not in self.previous_signals:
                try:
                    alert = self._format_trend_alert(signal, stocks_data.get(signal.ticker))
                    all_alerts.append(alert)
                except Exception as e:
                    logger.warning(f"Error formatting trend alert for {signal.ticker}: {str(e)}")
        
        # Run VERC
        verc_signals = self._get_verc_signals(stocks_data)
        
        # Limit to top 2 VERC signals
        verc_signals = verc_signals[:2] if verc_signals else []
        
        for signal in verc_signals:
            signal_key = f"VERC:{signal.stock_symbol}"
            current_signals.add(signal_key)
            
            # Only alert if new signal
            if signal_key not in self.previous_signals:
                try:
                    alert = self._format_verc_alert(signal, stocks_data.get(signal.stock_symbol))
                    all_alerts.append(alert)
                except Exception as e:
                    logger.warning(f"Error formatting VERC alert for {signal.stock_symbol}: {str(e)}")
        
        # Update previous signals
        self.previous_signals = current_signals
        
        # Send all alerts or no signals message
        if all_alerts:
            logger.info(f"Found {len(all_alerts)} new signals!")
            self._send_unified_alerts(all_alerts)
        else:
            logger.info("No new signals found (same as previous scan)")
    
    def _get_trend_signals(self, stocks_data):
        """Get trend detection signals."""
        logger.info("Running Trend Detection Strategy...")
        scan_result = self.trend_detector.analyze_multiple_stocks_with_scans(stocks_data)
        return scan_result.intersection
    
    def _get_verc_signals(self, stocks_data):
        """Get VERC signals."""
        logger.info("Running VERC Strategy...")
        return verc_scan_stocks(stocks_data)
    
    def _format_trend_alert(self, signal, df=None):
        """Format trend signal into detailed alert message."""
        indicators = signal.indicators
        
        # Get current time in IST
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)
        
        # Calculate entry, stop loss, and targets
        current_price = indicators.get('close', 0)
        ema20 = indicators.get('ema20', 0)
        ema50 = indicators.get('ema50', 0)
        
        # Entry: Current price or EMA20 breakout
        entry_min = current_price
        entry_max = ema20 if ema20 > current_price else current_price * 1.005
        
        # Stop Loss: Below EMA50 or 2% below entry
        stop_loss = min(ema50, current_price * 0.98)
        
        # Targets: 1:2 and 1:3 risk-reward
        risk = entry_min - stop_loss
        target_1 = entry_min + (risk * 2)
        target_2 = entry_min + (risk * 3)
        
        # Calculate ATR and time estimation
        atr = self._calculate_atr(df) if df is not None else None
        time_t1 = self._estimate_time_to_target(current_price, target_1, atr) if atr else "Unknown"
        time_t2 = self._estimate_time_to_target(current_price, target_2, atr) if atr else "Unknown"
        
        # Support and Resistance
        support, resistance = self._calculate_support_resistance(df) if df is not None else (None, None)
        
        # Calculate confidence based on EMA alignment
        confidence = 7  # Base confidence for trend signals
        if indicators.get('ema_alignment_score', 0) >= 3:
            confidence = 9
        elif indicators.get('ema_alignment_score', 0) >= 2:
            confidence = 8
        
        alert_lines = [
            "📈 TREND SIGNAL",
            "",
            f"Stock: {signal.ticker}",
            f"Time: {now.strftime('%Y-%m-%d %H:%M')} IST",
            f"Timeframe: 1D",
            "",
            f"💰 Price: ₹{current_price:.2f}",
            "",
            "🎯 Entry Zone:",
            f"  Buy Above: ₹{entry_max:.2f}",
            "",
            "🛡️ Stop Loss:",
            f"  SL: ₹{stop_loss:.2f} ({((stop_loss/current_price)-1)*100:.1f}%)",
            "",
            "🎯 Targets:",
            f"  Target 1: ₹{target_1:.2f} (+{((target_1/current_price)-1)*100:.1f}%) ETA: {time_t1}",
            f"  Target 2: ₹{target_2:.2f} (+{((target_2/current_price)-1)*100:.1f}%) ETA: {time_t2}",
            ""
        ]
        
        # Add S/R levels if available
        if support and resistance:
            alert_lines.extend([
                "📊 S/R Levels:",
                f"  Support: ₹{support:.2f}",
                f"  Resistance: ₹{resistance:.2f}",
                ""
            ])
        
        alert_lines.append(f"Confidence: {confidence}/10")
        
        return "\n".join(alert_lines)
    
    def _format_verc_alert(self, signal, df=None):
        """Format VERC signal into detailed alert message."""
        # Get current time in IST
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)
        
        # Calculate ATR and time estimation
        atr = self._calculate_atr(df) if df is not None else None
        time_t1 = self._estimate_time_to_target(signal.current_price, signal.target_1, atr) if atr else "Unknown"
        time_t2 = self._estimate_time_to_target(signal.current_price, signal.target_2, atr) if atr else "Unknown"
        
        # Support and Resistance
        support, resistance = self._calculate_support_resistance(df) if df is not None else (None, None)
        
        alert_lines = [
            "📊 VERC SIGNAL (Accumulation)",
            "",
            f"Stock: {signal.stock_symbol}",
            f"Time: {now.strftime('%Y-%m-%d %H:%M')} IST",
            f"Timeframe: 1D",
            "",
            f"💰 Current Price: ₹{signal.current_price:.2f}",
            "",
            "🔄 Compression Range:",
            f"  Range: ₹{signal.compression_low:.2f} - ₹{signal.compression_high:.2f}",
            f"  Range Width: ₹{signal.range_height:.2f}",
            "",
            "🎯 Entry Zone:",
            f"  Buy Above: ₹{signal.entry_min:.2f} - ₹{signal.entry_max:.2f}",
            "",
            "🛡️ Stop Loss:",
            f"  SL: ₹{signal.stop_loss:.2f} ({((signal.stop_loss/signal.current_price)-1)*100:.1f}%)",
            "",
            "🎯 Targets:",
            f"  Target 1: ₹{signal.target_1:.2f} (+{((signal.target_1/signal.current_price)-1)*100:.1f}%) ETA: {time_t1}",
            f"  Target 2: ₹{signal.target_2:.2f} (+{((signal.target_2/signal.current_price)-1)*100:.1f}%) ETA: {time_t2}",
            ""
        ]
        
        # Add S/R levels if available
        if support and resistance:
            alert_lines.extend([
                "📊 S/R Levels:",
                f"  Support: ₹{support:.2f}",
                f"  Resistance: ₹{resistance:.2f}",
                ""
            ])
        
        alert_lines.append(f"Confidence: {signal.confidence_score}/10")
        
        return "\n".join(alert_lines)
    
    def _send_unified_alerts(self, alerts):
        """Send all alerts as a single unified message."""
        # Send each alert separately for clarity
        for alert in alerts:
            self.alert_service.send_alert(alert)
            self.total_signals += 1
            logger.info(f"Alert sent: {alert[:50]}...")
    
    def _send_no_signals_message(self):
        """Send a message when no signals are found."""
        from datetime import datetime
        
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)
        
        message = (
            "📊 Daily Scan Complete\n"
            f"Time: {now.strftime('%Y-%m-%d %H:%M')}\n"
            f"Timeframe: 1D\n"
            "\n"
            "No signals today.\n"
            "Markets may be consolidating."
        )
        self.alert_service.send_alert(message)
    
    def _calculate_atr(self, df, period=14):
        """Calculate ATR for time estimation."""
        if df is None or len(df) < period:
            return None
        
        # Check if required columns exist
        required_cols = ['high', 'low', 'close']
        if not all(col in df.columns for col in required_cols):
            return None
        
        try:
            high = df['high']
            low = df['low']
            close = df['close']
            
            tr1 = high - low
            tr2 = abs(high - close.shift(1))
            tr3 = abs(low - close.shift(1))
            
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(window=period).mean().iloc[-1]
            
            return atr
        except Exception:
            return None
    
    def _calculate_support_resistance(self, df, lookback=20):
        """Calculate support and resistance levels."""
        if df is None or len(df) < lookback:
            return None, None
        
        # Check if required columns exist
        if 'high' not in df.columns or 'low' not in df.columns:
            return None, None
        
        try:
            recent_df = df.tail(lookback)
            support = recent_df['low'].min()
            resistance = recent_df['high'].max()
            
            return support, resistance
        except Exception:
            return None, None
    
    def _estimate_time_to_target(self, current_price, target_price, atr):
        """Estimate time to reach target based on ATR."""
        if atr is None or atr == 0:
            return "Unknown"
        
        price_diff = abs(target_price - current_price)
        days_estimate = price_diff / atr
        
        if days_estimate <= 1:
            return "< 1 day"
        elif days_estimate <= 3:
            return f"{int(days_estimate)} days"
        elif days_estimate <= 7:
            return f"~{int(days_estimate)} days"
        elif days_estimate <= 14:
            return f"~{int(days_estimate/7)} weeks"
        else:
            return f"~{int(days_estimate/30)} months"
    
    def start(self):
        """Start the scanner with scheduled execution."""
        logger.info("Starting NSE Trend Scanner Agent...")
        
        # Send startup notification
        self.alert_service.send_system_status(
            f"🚀 NSE Trend Scanner Agent Started\n"
            f"• Monitoring {len(self.stocks)} stocks\n"
            f"• Timeframe: 1D\n"
            f"• Scan Interval: Every 15 min\n"
            f"• Market Hours: 09:15 - 15:30 IST\n"
            f"• Strategies: Trend + VERC\n"
            f"• Max Signals: 2 per strategy"
        )
        
        # Start scheduler
        self.scheduler.start()
        
        logger.info("Scanner running. Press Ctrl+C to stop.")
        
        # Keep main thread alive
        try:
            while True:
                # Print status every hour
                import time
                time.sleep(3600)
                status = self.scheduler.get_status()
                logger.info(f"Status: {status}")
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
            self.stop()
    
    def stop(self):
        """Stop the scanner."""
        logger.info("Stopping NSE Trend Scanner...")
        self.scheduler.stop()
        
        # Send shutdown notification
        self.alert_service.send_system_status(
            f"🛑 NSE Trend Scanner Agent Stopped\n"
            f"• Total scans: {self.total_scans}\n"
            f"• Total signals: {self.total_signals}\n"
            f"• Alerted stocks: {self.trend_detector.get_alert_count()}"
        )
        
        logger.info("Scanner stopped")
    
    def run_once(self):
        """Run a single scan (for testing)."""
        logger.info("Running single scan (test mode)...")
        
        # Check market hours
        if not self.data_fetcher.is_market_open():
            logger.warning("Market is closed. Running scan anyway (test mode)...")
        
        self.scan()
        
        # Print results
        alerted = self.trend_detector.get_alerted_stocks()
        if alerted:
            logger.info(f"Alerted stocks: {alerted}")
    
    def test_telegram(self) -> bool:
        """Test Telegram connection."""
        logger.info("Testing Telegram connection...")
        return self.alert_service.test_connection()


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="NSE Trend Scanner Agent - Automated trading scanner for NSE stocks"
    )
    
    parser.add_argument(
        '--config', 
        default='config/stocks.json',
        help='Path to stocks configuration file'
    )
    
    parser.add_argument(
        '--telegram-token',
        default=os.environ.get('TELEGRAM_BOT_TOKEN'),
        help='Telegram bot token (or set TELEGRAM_BOT_TOKEN env var)'
    )
    
    parser.add_argument(
        '--telegram-chat-id',
        default=os.environ.get('TELEGRAM_CHAT_ID'),
        help='Telegram chat ID (or set TELEGRAM_CHAT_ID env var)'
    )
    
    parser.add_argument(
        '--test',
        action='store_true',
        help='Run a single test scan'
    )
    
    parser.add_argument(
        '--test-telegram',
        action='store_true',
        help='Test Telegram connection'
    )
    
    parser.add_argument(
        '--mock-alerts',
        action='store_true',
        help='Use mock alert service (for testing without Telegram)'
    )
    
    parser.add_argument(
        '--log-level',
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Logging level'
    )
    
    parser.add_argument(
        '--log-file',
        default='logs/scanner.log',
        help='Log file path'
    )
    
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_arguments()
    
# Setup logging
    import logging
    logging.getLogger('yfinance').setLevel(logging.ERROR)
    logging.getLogger('pandas').setLevel(logging.ERROR)
    setup_logging(args.log_level, args.log_file)
    
    logger.info("=" * 60)
    logger.info("NSE Trend Scanner Agent")
    logger.info("=" * 60)
    
    # Create scanner
    scanner = NSETrendScanner(
        config_path=args.config,
        telegram_token=args.telegram_token,
        telegram_chat_id=args.telegram_chat_id,
        use_mock_alerts=args.mock_alerts
    )
    
    # Handle test modes
    if args.test:
        scanner.run_once()
        return
    
    if args.test_telegram:
        success = scanner.test_telegram()
        if success:
            logger.info("Telegram test passed!")
        else:
            logger.error("Telegram test failed!")
        return
    
    # Start scanner
    scanner.start()


if __name__ == "__main__":
    main()
