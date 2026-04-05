"""
NSE Trend Scanner Agent - Main Entry Point
Monitors NSE stocks for trend and VERC (Volume Expansion Range Compression) signals.
"""

import os
import sys
import argparse
import logging
import threading
from pathlib import Path
from datetime import datetime
import pandas as pd
import pytz

# Configure logging
logger = logging.getLogger(__name__)

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_fetcher import DataFetcher
from indicator_engine import IndicatorEngine
from trend_detector import TrendDetector
from alert_service import AlertService, TelegramBotHandler
from scheduler import MarketScheduler
from volume_compression import scan_stocks as verc_scan_stocks
from ai_stock_analyzer import create_analyzer

# New modules for Reasoning + Learning
from reasoning_engine import create_reasoning_engine
from history_manager import create_history_manager
from signal_tracker import create_signal_tracker
from performance_tracker import create_performance_tracker
from notification_manager import create_notification_manager

# New MTF Strategy Module
from mtf_strategy import MTFStrategyScanner, format_mtf_signal_alert, create_mtf_scanner


def setup_logging(log_level='INFO', log_file='logs/scanner.log'):
    """Setup logging configuration."""
    # Create logs directory if it doesn't exist using Path
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    
    # Suppress verbose libraries
    logging.getLogger('yfinance').setLevel(logging.WARNING)
    logging.getLogger('pandas').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)


class NSETrendScanner:
    """Main scanner class that coordinates all components."""
    
    def __init__(self, config_path='config/stocks.json', telegram_token=None, 
                 telegram_chat_id=None, use_mock_alerts=False, strategy='all',
                 enable_telegram_bot=False):
        """Initialize the scanner with all components."""
        # Load configuration
        self.config_path = config_path
        self.strategy = strategy
        self.telegram_token = telegram_token
        self.telegram_chat_id = telegram_chat_id
        self._load_config()
        self._load_settings()
        
        # Initialize components
        self.data_fetcher = DataFetcher()
        self.indicator_engine = IndicatorEngine()
        self.trend_detector = TrendDetector()
        
        # Initialize alert service
        if use_mock_alerts:
            from alert_service import MockAlertService
            self.alert_service = MockAlertService()
        else:
            self.alert_service = AlertService(telegram_token, telegram_chat_id)
        
        # Initialize AI analyzer
        self.ai_analyzer = create_analyzer()
        
        # Initialize Telegram bot handler for two-way communication
        self.telegram_bot = None
        if enable_telegram_bot and telegram_token and telegram_chat_id:
            self.telegram_bot = TelegramBotHandler(
                bot_token=telegram_token,
                chat_id=telegram_chat_id,
                data_fetcher=self.data_fetcher,
                ai_analyzer=self.ai_analyzer
            )
            logger.info("Telegram bot handler initialized for two-way communication")
        
        # Initialize scheduler
        self.scheduler = MarketScheduler()
        self.scheduler.scan_callback = self.scan
        
        # ==================== NEW: Reasoning + Learning Components ====================
        # History Manager - stores signal data
        self.history_manager = create_history_manager()
        
        # Signal Tracker - monitors active signals
        self.signal_tracker = create_signal_tracker(self.history_manager, self.data_fetcher)
        
        # Performance Tracker - calculates SIQ scores
        self.performance_tracker = create_performance_tracker(self.history_manager)
        
        # Reasoning Engine - hybrid rule-based + AI reasoning
        self.reasoning_engine = create_reasoning_engine()
        
        # Notification Manager - handles outcome alerts and reports
        self.notification_manager = create_notification_manager(self.alert_service, self.history_manager, self.performance_tracker)
        
        # ==================== MTF Strategy Scanner ====================
        # Multi-timeframe strategy (Trend + Pullback + Confirmation)
        self.mtf_scanner = create_mtf_scanner()
        self.mtf_scanner.set_data_fetcher(self.data_fetcher)
        
        # Signal tracking interval (check every N scans)
        self.signal_check_interval = self.settings.get('learning', {}).get('signal_tracking', {}).get('check_interval_scans', 4)
        self.scan_count = 0
        
        # Statistics
        self.total_scans = 0
        self.total_signals = 0
        self.last_scan_time = None
        self.previous_signals = set()
        
        # Suppress yfinance
        import warnings
        warnings.filterwarnings('ignore')
    
    def _load_config(self):
        """Load stock configuration from JSON file."""
        import json
        
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            self.config_path
        )
        
        if not os.path.exists(config_path):
            # Default to Nifty 50 if config doesn't exist
            self.stocks = [
                'RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'ICICIBANK',
                'SBIN', 'BHARTIARTL', 'LT', 'BAJFINANCE', 'HINDUNILVR'
            ]
            return
        
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        # Config can be a list of stocks or a dict with 'stocks' key
        if isinstance(config, list):
            self.stocks = config
        else:
            # Get stock list from config
            self.stocks = config.get('stocks', [])
            
            # Also check for groups
            if 'groups' in config:
                for group in config['groups'].values():
                    self.stocks.extend(group)
        
        # Remove duplicates
        self.stocks = list(set(self.stocks))
    
    def _load_settings(self):
        """Load settings from JSON file."""
        import json
        
        settings_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'config/settings.json'
        )
        
        if os.path.exists(settings_path):
            try:
                with open(settings_path, 'r') as f:
                    self.settings = json.load(f)
                logger.info("Settings loaded from config/settings.json")
            except Exception as e:
                logger.error(f"Error loading settings: {e}")
                self.settings = {}
        else:
            self.settings = {}
    
    def scan(self):
        """
        Main scan method that runs on schedule.
        
        Steps:
        1. Fetch stock data (single and multi-timeframe)
        2. Run Trend Detection and VERC strategies
        3. Run MTF Strategy (NEW)
        4. Send unified alerts with entry/stop loss/targets
        5. Track signals for learning
        """
        self.total_scans += 1
        self.scan_count += 1
        scan_start = datetime.now()
        
        try:
            # Step 1a: Fetch data for all stocks (single timeframe for existing strategies)
            stocks_data = self.data_fetcher.fetch_multiple_stocks(self.stocks)
            
            if not stocks_data:
                return
            
            # Step 2: Run existing strategies with Reasoning Engine
            self._run_all_strategies(stocks_data)
            
            # Step 3: Run NEW MTF Strategy
            self._run_mtf_strategy()
            
            # Step 4: Check active signals periodically
            if self.scan_count % self.signal_check_interval == 0:
                self._check_active_signals()
            
            # Update statistics
            self.last_scan_time = datetime.now()
            scan_duration = (self.last_scan_time - scan_start).total_seconds()
            
        except Exception as e:
            # Silently handle errors to keep scanner running
            pass
    
    def _run_mtf_strategy(self):
        """
        Run the Multi-Timeframe Strategy.
        Fetches 1D, 1H, 15m data and validates all conditions.
        """
        try:
            # Get strategy setting
            use_mtf = self.settings.get('scanner', {}).get('enable_mtf_strategy', True)
            if not use_mtf:
                return
            
            logger.info("Running MTF Strategy scan...")
            
            # Fetch multi-timeframe data for all stocks
            mtf_stocks_data = self.data_fetcher.fetch_multiple_stocks_multi_timeframe(
                self.stocks,
                max_workers=3
            )
            
            if not mtf_stocks_data:
                return
            
            # Calculate indicators for each timeframe
            from indicator_engine import IndicatorEngine
            engine = IndicatorEngine()
            
            all_indicators = {}
            for ticker, mtf_data in mtf_stocks_data.items():
                indicators = {}
                for tf, df in mtf_data.items():
                    if df is not None and not df.empty:
                        df_with_ind = engine.calculate_indicators(df)
                        if df_with_ind is not None and not df_with_ind.empty:
                            indicators[tf] = engine.get_latest_indicators(df_with_ind)
                if indicators:
                    all_indicators[ticker] = indicators
            
            # Run MTF scanner
            mtf_signals = self.mtf_scanner.scan_multiple_stocks(mtf_stocks_data, all_indicators)
            
            # Limit signals
            max_signals = self.settings.get('scanner', {}).get('max_signals_per_strategy', 2)
            mtf_signals = mtf_signals[:max_signals] if mtf_signals else []
            
            # Send alerts for valid MTF signals
            current_signals = set()
            for signal in mtf_signals:
                signal_key = f"MTF:{signal.ticker}"
                current_signals.add(signal_key)
                
                if signal_key not in self.previous_signals:
                    try:
                        alert = format_mtf_signal_alert(signal)
                        self.alert_service.send_alert(alert)
                        self.total_signals += 1
                    except Exception as e:
                        logger.error(f"Error sending MTF alert: {e}")
            
            # Update previous signals for MTF to prevent duplicate alerts
            self.previous_signals = self.previous_signals.union(current_signals)
            
        except Exception as e:
            logger.error(f"Error in MTF strategy: {e}")
    
    def _run_all_strategies(self, stocks_data):
        """
        Run strategy based on configuration (Trend, VERC, or both).
        Filters out repeat signals.
        """
        all_alerts = []
        current_signals = set()
        
        # Run Trend Detection if strategy is 'trend' or 'all'
        if self.strategy in ['trend', 'all']:
            trend_signals = self._get_trend_signals(stocks_data)
            
            # Limit to top N trend signals
            max_signals = self.settings.get('scanner', {}).get('max_signals_per_strategy', 2)
            trend_signals = trend_signals[:max_signals] if trend_signals else []
            
            for signal in trend_signals:
                signal_key = f"TREND:{signal.ticker}"
                current_signals.add(signal_key)
                
                # Only alert if new signal
                if signal_key not in self.previous_signals:
                    try:
                        alert = self._format_trend_alert(signal, stocks_data.get(signal.ticker))
                        all_alerts.append(alert)
                        
                        # Track signal for learning system
                        self._track_trend_signal(signal)
                    except Exception:
                        pass
        
        # Run VERC if strategy is 'verc' or 'all'
        if self.strategy in ['verc', 'all']:
            verc_signals = self._get_verc_signals(stocks_data)
            
            # Limit to top N VERC signals
            max_signals = self.settings.get('scanner', {}).get('max_signals_per_strategy', 2)
            verc_signals = verc_signals[:max_signals] if verc_signals else []
            
            for signal in verc_signals:
                signal_key = f"VERC:{signal.stock_symbol}"
                current_signals.add(signal_key)
                
                # Only alert if new signal
                if signal_key not in self.previous_signals:
                    try:
                        alert = self._format_verc_alert(signal, stocks_data.get(signal.stock_symbol))
                        all_alerts.append(alert)
                        
                        # Track signal for learning system
                        self._track_verc_signal(signal)
                    except Exception:
                        pass
        
        # Update previous signals
        self.previous_signals = current_signals
        
        # Send all alerts or no signals message
        if all_alerts:
            self._send_unified_alerts(all_alerts)
    
    def _get_trend_signals(self, stocks_data):
        """Get trend detection signals."""
        scan_result = self.trend_detector.analyze_multiple_stocks_with_scans(stocks_data)
        return scan_result.intersection
    
    def _get_verc_signals(self, stocks_data):
        """Get VERC signals."""
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
        
        # Add reasoning info if available
        reasoning_info = signal.reasoning if hasattr(signal, 'reasoning') else {}
        if reasoning_info:
            alert_lines.extend([
                "",
                "🧠 AI Reasoning:",
                f"  Score: {reasoning_info.get('weighted_score', 'N/A')}",
                f"  Factors: {', '.join(reasoning_info.get('factor_scores', {}).keys())}"
            ])
        
        # Add tracking info
        alert_lines.extend([
            "",
            f"📊 Signal ID: {signal.ticker}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            "(This signal is now being tracked for outcome monitoring)"
        ])
        
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
        
        # Add VERC-specific scoring
        if hasattr(signal, 'verc_score'):
            alert_lines.extend([
                "",
                f"📈 VERC Score: {signal.verc_score}/100"
            ])
        
        # Add tracking info
        alert_lines.extend([
            "",
            f"📊 Signal ID: {signal.stock_symbol}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            "(This signal is now being tracked for outcome monitoring)"
        ])
        
        return "\n".join(alert_lines)
    
    def _send_unified_alerts(self, alerts):
        """Send all alerts as a single unified message."""
        # Send each alert separately for clarity
        for alert in alerts:
            self.alert_service.send_alert(alert)
            self.total_signals += 1
    
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
        if atr is None or atr <= 0 or current_price <= 0:
            return "Unknown"
        
        price_diff = abs(target_price - current_price)
        if price_diff == 0:
            return "Already at target"
        
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
    
    # ==================== NEW: Signal Tracking & Learning ====================
    
    def _check_active_signals(self):
        """
        Check all active signals for target/SL hits.
        Sends notifications for completed signals.
        """
        try:
            # Check all active signals
            result = self.signal_tracker.check_all_active_signals()
            
            completed = result.get('completed', [])
            still_active = result.get('still_active', [])
            
            if completed:
                # Notify for each completed signal
                for signal in completed:
                    self.notification_manager.notify_signal_completed(signal)
                
                # Also send batch summary
                self.notification_manager.notify_outcome_batch(completed)
                
                logger.info(f"Completed signals: {len(completed)}")
            
            # Log active signal status
            if still_active:
                logger.debug(f"Active signals: {len(still_active)}")
                
        except Exception as e:
            logger.error(f"Error checking active signals: {e}")
    
    def _track_signal(self, signal_data: dict, signal_type: str):
        """
        Track a new signal in the learning system.
        
        Args:
            signal_data: Signal information dict
            signal_type: Type of signal (TREND, VERC, etc.)
        """
        try:
            # Generate signal ID
            import uuid
            signal_id = f"{signal_type}_{signal_data.get('stock_symbol', 'UNKNOWN')}_{uuid.uuid4().hex[:8]}"
            
            # Build tracking data
            tracking_data = {
                'signal_id': signal_id,
                'stock_symbol': signal_data.get('stock_symbol'),
                'signal_type': signal_type,
                'entry_price': signal_data.get('entry_price'),
                'target_price': signal_data.get('target_price'),
                'sl_price': signal_data.get('sl_price'),
                'confidence_score': signal_data.get('confidence_score', 50),
                'reasoning_data': signal_data.get('reasoning', {})
            }
            
            # Add to active tracking
            self.history_manager.add_active_signal(tracking_data)
            
            logger.info(f"Tracking signal: {signal_id} for {tracking_data.get('stock_symbol')}")
            
        except Exception as e:
            logger.error(f"Error tracking signal: {e}")
    
    def _track_trend_signal(self, signal):
        """
        Track a Trend signal in the learning system.
        
        Args:
            signal: TrendSignal object
        """
        try:
            # Extract indicators from signal
            indicators = signal.indicators if hasattr(signal, 'indicators') else {}
            
            # Build signal data for tracking
            signal_data = {
                'stock_symbol': signal.ticker,
                'entry_price': indicators.get('close', 0),
                'target_price': indicators.get('target_price', 0),
                'sl_price': indicators.get('stop_loss', 0),
                'confidence_score': 50,  # Default, will be enhanced with reasoning
                'signal_type': 'TREND',
                'reasoning': {
                    'signal_indicators': indicators
                }
            }
            
            self._track_signal(signal_data, 'TREND')
            
        except Exception as e:
            logger.error(f"Error tracking trend signal: {e}")
    
    def _track_verc_signal(self, signal):
        """
        Track a VERC signal in the learning system.
        
        Args:
            signal: VERCSignal object
        """
        try:
            # Build signal data for tracking
            signal_data = {
                'stock_symbol': signal.stock_symbol,
                'entry_price': signal.entry_min,
                'target_price': signal.target_1,
                'sl_price': signal.stop_loss,
                'confidence_score': signal.confidence_score,
                'signal_type': 'VERC',
                'reasoning': {
                    'verc_score': signal.confidence_score,
                    'volume_ratio': signal.volume_ratio
                }
            }
            
            self._track_signal(signal_data, 'VERC')
            
        except Exception as e:
            logger.error(f"Error tracking VERC signal: {e}")
    
    def get_performance_stats(self) -> dict:
        """
        Get current performance statistics including SIQ.
        
        Returns:
            Performance metrics dict
        """
        try:
            return self.performance_tracker.generate_performance_report()
        except Exception as e:
            logger.error(f"Error getting performance stats: {e}")
            return {}
    
    # ==================== END NEW ====================
    
    def start(self):
        """Start the scanner with scheduled execution."""
        
        # Check AI availability
        ai_status = "✅" if self.ai_analyzer.is_available() else "❌"
        
        # Send startup notification
        active_signals = self.history_manager.get_active_count()
        startup_msg = (
            f"🚀 NSE Trend Scanner Agent Started\n"
            f"• Monitoring {len(self.stocks)} stocks\n"
            f"• Timeframe: 1D\n"
            f"• Scan Interval: Every 15 min\n"
            f"• Market Hours: 09:15 - 15:30 IST\n"
            f"• Strategies: Trend + VERC\n"
            f"• Max Signals: 2 per strategy\n"
            f"• AI Analysis: {ai_status}\n"
            f"• Telegram Bot: {'✅ Enabled' if self.telegram_bot else '❌ Disabled'}\n"
            f"──────────────────────\n"
            f"🧠 REASONING + LEARNING:\n"
            f"• Signal Tracking: ✅ Active\n"
            f"• Active Signals: {active_signals}\n"
            f"• SIQ Scoring: ✅ Enabled\n"
            f"• Outcome Notifications: ✅ Enabled"
        )
        self.alert_service.send_system_status(startup_msg)
        
        # Start Telegram bot handler for two-way communication
        if self.telegram_bot:
            self.telegram_bot.start_background()
            self.alert_service.send_message(
                "✅ *Telegram Bot Active!*\n\n"
                "You can now:\n"
                "• Send me a stock symbol (e.g., `RELIANCE`)\n"
                "• Use /analyze RELIANCE for AI analysis\n"
                "• Use /trend HDFCBANK for trend analysis\n"
                "• Use /status to check scanner status"
            )
        
        # Start scheduler
        self.scheduler.start()
        
        # Keep main thread alive
        try:
            while True:
                import time
                time.sleep(3600)
                status = self.scheduler.get_status()
        except KeyboardInterrupt:
            self.stop()
    
    def stop(self):
        """Stop the scanner."""
        self.scheduler.stop()
        
        # Send shutdown notification
        self.alert_service.send_system_status(
            f"🛑 NSE Trend Scanner Agent Stopped\n"
            f"• Total scans: {self.total_scans}\n"
            f"• Total signals: {self.total_signals}\n"
            f"• Alerted stocks: {self.trend_detector.get_alert_count()}"
        )
    
    def run_once(self):
        """Run a single scan (for testing)."""
        # Check market hours
        if not self.data_fetcher.is_market_open():
            logger.info("Market is currently closed. Scan will run but may not have live data.")
        
        self.scan()
        
        # Print results
        alerted = self.trend_detector.get_alerted_stocks()
        if alerted:
            pass
    
    def test_telegram(self) -> bool:
        """Test Telegram connection."""
        if not self.telegram_token or not self.telegram_chat_id:
            logger.warning("Telegram credentials not configured. Use --telegram-token and --telegram-chat-id or set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables.")
            print("ERROR: Telegram credentials not configured!")
            print("Please set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables")
            print("Or pass them as command line arguments: --telegram-token TOKEN --telegram-chat-id ID")
            return False
        return self.alert_service.test_connection()


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="NSE Trend Scanner Agent - Automated trading scanner for NSE stocks"
    )
    
    parser.add_argument(
        '--strategy',
        default='all',
        choices=['trend', 'verc', 'all'],
        help='Strategy to run: trend, verc, or all (default: all)'
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
        '--enable-telegram-bot',
        action='store_true',
        help='Enable two-way Telegram bot for stock analysis requests'
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
    
    parser.add_argument(
        '--schedule',
        action='store_true',
        help='Run with scheduler (daily at 3 PM Mon-Fri) + Telegram bot'
    )
    
    return parser.parse_args()


def run_scheduled(config: dict, logger):
    """
    Run the scanner with scheduler and Telegram bot (both running together)
    """
    logger.info("Initializing scheduler and Telegram bot...")
    
    # Import here to avoid circular imports
    from scheduler.scanner_scheduler import ScannerScheduler
    
    # Check if telegram_bot exists, otherwise use alert_service
    TelegramBot = None
    try:
        from notifications.telegram_bot import TelegramBot
    except (ImportError, ModuleNotFoundError):
        pass
    
    # Create scanner
    scanner = NSETrendScanner(
        config_path='config/stocks.json',
        telegram_token=config.get('telegram', {}).get('bot_token') or os.environ.get('TELEGRAM_BOT_TOKEN'),
        telegram_chat_id=config.get('telegram', {}).get('chat_id') or os.environ.get('TELEGRAM_CHAT_ID'),
        use_mock_alerts=False,
        strategy='all',
        enable_telegram_bot=False
    )
    
    # Create scheduler
    scheduler = ScannerScheduler(config)
    
    # Add the scan job
    def scan_job():
        scanner.scan()
    
    scheduler.add_job(scan_job)
    
    # Add signal monitoring job if enabled
    signal_tracking = config.get('learning', {}).get('signal_tracking', {})
    if signal_tracking.get('enabled', True):
        def monitor_job():
            scanner._check_active_signals()
        
        from apscheduler.triggers.interval import IntervalTrigger
        check_interval = signal_tracking.get('check_interval_scans', 4)
        # Convert scans to minutes (assuming one scan per 15 min)
        monitor_minutes = max(15, check_interval * 15)
        
        from apscheduler.executors.pool import ThreadPoolExecutor
        executors = {'default': ThreadPoolExecutor(max_workers=1)}
        
        # Add monitor job directly to scheduler
        scheduler.scheduler.add_job(
            monitor_job,
            trigger=IntervalTrigger(minutes=monitor_minutes, timezone=config.get('scheduler', {}).get('timezone', 'Asia/Kolkata')),
            id='monitor_job',
            name='Signal Monitor',
            replace_existing=True,
            executor='default'
        )
        logger.info(f"Signal monitoring job scheduled: every {monitor_minutes} minutes")
    
    # Start scheduler
    scheduler.start()
    
    logger.info(f"Scheduler running. Next scan: {scheduler.get_next_run()}")
    
    # Start Telegram bot in polling mode (in a separate thread)
    bot = None
    bot_thread = None
    
    if TelegramBot:
        try:
            bot = TelegramBot(config)
            if bot.is_configured():
                logger.info("Starting Telegram bot in polling mode...")
                bot_thread = threading.Thread(target=bot.start_polling, daemon=True)
                bot_thread.start()
            else:
                logger.warning("Telegram bot not configured - polling not started")
        except Exception as e:
            logger.warning(f"Could not start Telegram bot: {e}")
    else:
        logger.warning("TelegramBot not available - polling not started")
    
    logger.info("System running. Scanner at 3 PM Mon-Fri, bot responding to commands.")
    logger.info("Press Ctrl+C to stop")
    
    try:
        import time
        while True:
            time.sleep(60)
            logger.debug(f"Next scan: {scheduler.get_next_run()}")
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        scheduler.stop()


def main():
    """Main entry point."""
    args = parse_arguments()
    
    # Setup logging
    import logging
    logging.getLogger('yfinance').setLevel(logging.ERROR)
    logging.getLogger('pandas').setLevel(logging.ERROR)
    setup_logging(args.log_level, args.log_file)
    
    # Handle --schedule mode (new combined scheduler + bot mode)
    if args.schedule:
        # Load full config
        import json
        settings_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'config/settings.json'
        )
        with open(settings_path, 'r') as f:
            config = json.load(f)
        
        logger = logging.getLogger(__name__)
        run_scheduled(config, logger)
        return
    
    # Create scanner
    scanner = NSETrendScanner(
        config_path=args.config,
        telegram_token=args.telegram_token,
        telegram_chat_id=args.telegram_chat_id,
        use_mock_alerts=args.mock_alerts,
        strategy=args.strategy,
        enable_telegram_bot=args.enable_telegram_bot
    )
    
    # Handle test modes
    if args.test:
        scanner.run_once()
        return
    
    if args.test_telegram:
        success = scanner.test_telegram()
        if success:
            print("Telegram test successful!")
        else:
            print("Telegram test failed!")
        return
    
    # Start scanner
    scanner.start()


if __name__ == "__main__":
    main()
