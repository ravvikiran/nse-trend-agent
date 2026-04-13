"""
NSE Trend Scanner Agent - Main Entry Point
Monitors NSE stocks for trend and VERC (Volume Expansion Range Compression) signals.

FIXES APPLIED:
  1. Duplicate scheduler job: _run_periodic_scan now uses distinct job_id 'periodic_scan'
  2. SignalTracker now receives trade_journal (was missing, breaking outcome updates)
  3. Double journal writes: _track_trend_signal / _track_verc_signal no longer call
     log_signal() — that responsibility belongs solely to _process_signal()
  4. Pure rank score: strategy_weight no longer added to numeric rank_score;
     weights are used only in the sort key
  5. MTF signals now checked against signal_memory + trade_journal before sending
  6. Credential warning added when bot_token found in settings.json
  7. Weekend gap risk warning added to Friday signal alerts
"""

import os
import sys
import argparse
import logging
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
import pandas as pd
import pytz

logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_fetcher import DataFetcher
from indicator_engine import IndicatorEngine
from trend_detector import TrendDetector
from alert_service import AlertService, TelegramBotHandler
from market_scheduler import MarketScheduler
from volume_compression import scan_stocks as verc_scan_stocks
from ai_stock_analyzer import create_analyzer

from reasoning_engine import create_reasoning_engine
from history_manager import create_history_manager
from signal_tracker import create_signal_tracker
from performance_tracker import create_performance_tracker
from notification_manager import create_notification_manager

from signal_memory import create_signal_memory
from ai_rules_engine import create_ai_rules_engine

from mtf_strategy import MTFStrategyScanner, format_mtf_signal_alert, create_mtf_scanner

from trade_journal import create_trade_journal
from strategy_optimizer import create_strategy_performance_tracker
from ai_learning_layer import create_ai_learning_layer

from factor_analyzer import create_factor_analyzer
from market_context import create_market_context_engine

from trade_validator import create_trade_validator
from consolidation_detector import is_tight_consolidation, is_valid_breakout, is_strong_breakout


def setup_logging(log_level='INFO', log_file='logs/scanner.log'):
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    logging.getLogger('yfinance').setLevel(logging.WARNING)
    logging.getLogger('pandas').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)


class NSETrendScanner:
    """Main scanner class that coordinates all components."""

    def __init__(self, config_path='config/stocks.json', telegram_token=None,
                 telegram_chat_id=None, telegram_channel_chat_id=None,
                 use_mock_alerts=False, strategy='all', enable_telegram_bot=False):

        self.config_path = config_path
        self.strategy = strategy
        self.telegram_token = telegram_token
        self.telegram_chat_id = telegram_chat_id
        self.telegram_channel_chat_id = telegram_channel_chat_id
        self._load_config()
        self._load_settings()

        self.data_fetcher = DataFetcher()
        self.indicator_engine = IndicatorEngine()
        self.trend_detector = TrendDetector()

        if use_mock_alerts:
            from alert_service import MockAlertService
            self.alert_service = MockAlertService()
        else:
            target_chat_id = telegram_channel_chat_id or telegram_chat_id
            self.alert_service = AlertService(telegram_token, target_chat_id, telegram_channel_chat_id)

        self.ai_analyzer = create_analyzer()

        self.telegram_bot = None
        if enable_telegram_bot and telegram_token and telegram_chat_id:
            self.telegram_bot = TelegramBotHandler(
                bot_token=telegram_token,
                chat_id=telegram_chat_id,
                data_fetcher=self.data_fetcher,
                ai_analyzer=self.ai_analyzer
            )

        self.scheduler = MarketScheduler()
        self.scheduler.scan_callback = self.run_cycle
        self.scheduler.pm_update_callback = self.run_signal_generation
        self.scheduler.am_update_callback = self.run_signal_generation

        # --- Trade Journal must be created BEFORE SignalTracker ---
        self.trade_journal = create_trade_journal()

        self.scheduler.set_scanner_components(
            data_fetcher=self.data_fetcher,
            get_trend_signals_fn=self._get_trend_signals,
            get_verc_signals_fn=self._get_verc_signals,
            process_signal_fn=self._process_signal,
            strategy=self.strategy,
            stocks=self.stocks
        )
        self.scheduler.set_trade_journal(self.trade_journal)
        self.scheduler.set_alert_service(self.alert_service)

        self.history_manager = create_history_manager()

        # FIX 2: Pass trade_journal so completed signals update the journal
        self.signal_tracker = create_signal_tracker(
            self.history_manager, self.data_fetcher, self.trade_journal
        )

        self.performance_tracker = create_performance_tracker(self.history_manager)
        self.reasoning_engine = create_reasoning_engine()
        self.notification_manager = create_notification_manager(
            self.alert_service, self.history_manager, self.performance_tracker
        )

        self.signal_memory = create_signal_memory()
        self.signal_memory.sync_with_history_manager(self.history_manager)

        self.strategy_optimizer = create_strategy_performance_tracker(self.trade_journal)
        self.ai_learning_layer = create_ai_learning_layer(
            self.trade_journal, self.strategy_optimizer, self.ai_analyzer
        )
        self.ai_rules_engine = create_ai_rules_engine(self.ai_analyzer, self.ai_learning_layer)

        self.mtf_scanner = create_mtf_scanner()
        self.mtf_scanner.set_data_fetcher(self.data_fetcher)

        self.factor_analyzer = create_factor_analyzer(self.trade_journal)
        self.market_context_engine = create_market_context_engine(self.data_fetcher)
        self.trade_validator = create_trade_validator(self.settings)

        signal_mode = self.settings.get('signal_mode', {})
        self.daily_signal_hour = signal_mode.get('daily_signal_hour', 15)
        self.max_signals_per_day = signal_mode.get('max_signals_per_day', 5)
        self.confidence_threshold = signal_mode.get('confidence_threshold', 7)
        self.deduplication_days = signal_mode.get('deduplication_days', 5)
        self._signals_sent_today = 0
        self._last_signal_date = None
        self._top5_candidates = []

        self.signal_check_interval = (
            self.settings.get('learning', {})
                .get('signal_tracking', {})
                .get('check_interval_scans', 4)
        )
        self.scan_count = 0
        self.total_scans = 0
        self.total_signals = 0
        self.last_scan_time = None
        self.previous_signals = set()

        import warnings
        warnings.filterwarnings('ignore')

    # ------------------------------------------------------------------
    # Config loading
    # ------------------------------------------------------------------

    def _load_config(self):
        import json
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            self.config_path
        )
        if not os.path.exists(config_path):
            self.stocks = [
                'RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'ICICIBANK',
                'SBIN', 'BHARTIARTL', 'LT', 'BAJFINANCE', 'HINDUNILVR'
            ]
            return
        with open(config_path, 'r') as f:
            config = json.load(f)
        if isinstance(config, list):
            self.stocks = config
        else:
            self.stocks = config.get('stocks', [])
            if 'groups' in config:
                for group in config['groups'].values():
                    self.stocks.extend(group)
        self.stocks = list(set(self.stocks))

    def _load_settings(self):
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

                # FIX 6: Warn when credentials are stored in the config file
                token_in_file = self.settings.get('telegram', {}).get('bot_token', '')
                if token_in_file and token_in_file != os.environ.get('TELEGRAM_BOT_TOKEN', ''):
                    logger.warning(
                        "Telegram bot_token found in config/settings.json. "
                        "Prefer the TELEGRAM_BOT_TOKEN environment variable to avoid "
                        "accidentally committing credentials to version control."
                    )
            except Exception as e:
                logger.error(f"Error loading settings: {e}")
                self.settings = {}
        else:
            self.settings = {}

        env_channel_id = os.environ.get('TELEGRAM_CHANNEL_ID')
        if env_channel_id and 'telegram' in self.settings:
            self.settings['telegram']['channel_chat_id'] = env_channel_id

    # ------------------------------------------------------------------
    # Core cycle methods
    # ------------------------------------------------------------------

    def scan(self):
        self.total_scans += 1
        self.scan_count += 1
        scan_start = datetime.now()
        try:
            market_context = self.market_context_engine.detect_context()
            logger.debug(f"Market context: {market_context}")
            stocks_data = self.data_fetcher.fetch_multiple_stocks(self.stocks)
            if not stocks_data:
                return
            self._run_all_strategies(stocks_data)
            self._run_mtf_strategy()
            if self.scan_count % self.signal_check_interval == 0:
                self._check_active_signals()
            self.last_scan_time = datetime.now()
        except Exception as e:
            logger.error(f"Error in scan: {e}")

    def run_cycle(self):
        ist = pytz.timezone('Asia/Kolkata')
        current_time = datetime.now(ist)
        self.monitor_active_trades()
        if current_time.hour == 15 and current_time.minute == 0:
            self.run_signal_generation()

    def monitor_active_trades(self):
        try:
            active_trades = self.trade_journal.get_active_trades()
            if not active_trades:
                return
            logger.info(f"Monitoring {len(active_trades)} active trades")
            for trade in active_trades:
                self._check_trade_levels(trade)
        except Exception as e:
            logger.error(f"Error monitoring active trades: {e}")

    def _check_trade_levels(self, trade):
        symbol = trade.get('symbol')
        entry = trade.get('entry', 0)
        targets = trade.get('targets', [])
        stop_loss = trade.get('stop_loss', 0)
        if not targets or len(targets) < 3:
            return
        try:
            current_price = self._get_current_price(symbol)
            if not current_price:
                return
            t1_hit = trade.get('t1_hit', False)
            t2_hit = trade.get('t2_hit', False)
            if not t1_hit and current_price >= targets[0]:
                self._send_target_hit_alert(trade, 1, current_price)
                self.trade_journal.update_trade_field(trade.get('trade_id'), 't1_hit', True)
            if not t2_hit and current_price >= targets[1]:
                self._send_target_hit_alert(trade, 2, current_price)
                self.trade_journal.update_trade_field(trade.get('trade_id'), 't2_hit', True)
            if current_price >= targets[2]:
                self._send_target_hit_alert(trade, 3, current_price)
                self._close_trade(trade, "WIN", current_price)
                return
            if current_price <= stop_loss:
                self._send_sl_hit_alert(trade, current_price)
                self._close_trade(trade, "LOSS", current_price)
        except Exception as e:
            logger.error(f"Error checking trade levels for {symbol}: {e}")

    def _get_current_price(self, symbol: str) -> Optional[float]:
        try:
            stock_data = self.data_fetcher.fetch_stock_data(
                f"{symbol}.NS", interval='1d', days=2
            )
            if stock_data is not None and len(stock_data) > 0:
                return float(stock_data.iloc[-1].get('close', 0))
            return None
        except Exception as e:
            logger.error(f"Error fetching price for {symbol}: {e}")
            return None

    def _send_target_hit_alert(self, trade, target_num: int, current_price: float):
        symbol = trade.get('symbol')
        entry = trade.get('entry', 0)
        profit_pct = ((current_price - entry) / entry) * 100 if entry else 0
        if target_num == 3:
            message = (
                f"🎯 TARGET 3 HIT - {symbol}\n\n"
                f"Entry: ₹{entry:.2f}\nCurrent: ₹{current_price:.2f}\n"
                f"Profit: +{profit_pct:.1f}%\n\n✅ TRADE CLOSED WITH PROFIT"
            )
        else:
            message = (
                f"🎯 TARGET {target_num} HIT - {symbol}\n\n"
                f"Entry: ₹{entry:.2f}\nCurrent: ₹{current_price:.2f}\n"
                f"Profit: +{profit_pct:.1f}%\n\n📊 Trade remains active"
            )
        target_method = (
            self.alert_service.send_to_channel
            if self.alert_service.channel_chat_id
            else self.alert_service.send_alert
        )
        target_method(message)

    def _send_sl_hit_alert(self, trade, current_price: float):
        symbol = trade.get('symbol')
        entry = trade.get('entry', 0)
        loss_pct = ((entry - current_price) / entry) * 100 if entry else 0
        message = (
            f"🛑 STOP LOSS HIT - {symbol}\n\n"
            f"Entry: ₹{entry:.2f}\nExit: ₹{current_price:.2f}\n"
            f"Loss: -{loss_pct:.1f}%\n\n❌ TRADE CLOSED"
        )
        target_method = (
            self.alert_service.send_to_channel
            if self.alert_service.channel_chat_id
            else self.alert_service.send_alert
        )
        target_method(message)

    def _close_trade(self, trade, outcome: str, exit_price: float):
        trade_id = trade.get('trade_id')
        self.trade_journal.update_trade(trade_id, outcome, exit_price)
        self.strategy_optimizer.evaluate()

    def run_continuous_monitoring(self):
        try:
            self.monitor_active_trades()
        except Exception as e:
            logger.error(f"Error in continuous monitoring: {e}")

    def run_signal_generation(self):
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)
        today = now.date()

        if self._last_signal_date != today:
            self._signals_sent_today = 0
            self._last_signal_date = today
            self._top5_candidates = []

        logger.info(
            f"Running signal generation — sent today: "
            f"{self._signals_sent_today}/{self.max_signals_per_day}"
        )

        signals_to_send = []

        if self._top5_candidates:
            for signal in self._top5_candidates:
                if self._signals_sent_today >= self.max_signals_per_day:
                    break
                ticker = signal.ticker if hasattr(signal, 'ticker') else signal.stock_symbol
                if self.trade_journal.check_signal_exists(ticker, signal.strategy_type):
                    continue
                if self.signal_memory.is_duplicate(ticker):
                    continue
                confidence = getattr(signal, 'final_score', 0)
                if confidence < self.confidence_threshold:
                    continue
                signals_to_send.append(signal)
                self._signals_sent_today += 1
        else:
            signals_to_send = self._fresh_scan_for_signals()

        if not signals_to_send:
            self._send_no_signals_message()
            return

        target_method = (
            self.alert_service.send_to_channel
            if self.alert_service.channel_chat_id
            else self.alert_service.send_alert
        )

        for signal in signals_to_send:
            self._send_new_signal_alert(signal, target_method, now)

        self._top5_candidates = []
        logger.info(f"Signal generation complete — sent {len(signals_to_send)} signals")

    def _fresh_scan_for_signals(self) -> list:
        """Run a fresh scan and return signals that meet quality criteria."""
        from trade_journal import TradeJournal
        try:
            stocks_data = self.data_fetcher.fetch_multiple_stocks(self.stocks)
            if not stocks_data:
                return []
            all_signals = []
            if self.strategy in ['trend', 'all']:
                for signal in self._get_trend_signals(stocks_data):
                    signal = self._enrich_signal(signal, 'TREND', stocks_data)
                    if signal:
                        all_signals.append(signal)
            if self.strategy in ['verc', 'all']:
                for signal in self._get_verc_signals(stocks_data):
                    signal = self._enrich_verc_signal(signal, stocks_data)
                    if signal:
                        all_signals.append(signal)
            all_signals.sort(key=lambda x: getattr(x, 'final_score', 0), reverse=True)
            result = []
            for signal in all_signals:
                if self._signals_sent_today >= self.max_signals_per_day:
                    break
                ticker = signal.ticker if hasattr(signal, 'ticker') else signal.stock_symbol
                if self.trade_journal.check_signal_exists(ticker, signal.strategy_type):
                    continue
                if self.signal_memory.is_duplicate(ticker):
                    continue
                if getattr(signal, 'final_score', 0) < self.confidence_threshold:
                    continue
                result.append(signal)
            return result
        except Exception as e:
            logger.error(f"Error in fresh scan: {e}")
            return []

    def _enrich_signal(self, signal, strategy_type: str, stocks_data: dict):
        """Validate and enrich a TREND signal. Returns None if rejected."""
        from trade_journal import TradeJournal
        signal.strategy_type = strategy_type
        signal.strategy_score = getattr(signal, 'trend_score', 0)
        signal.volume_ratio = signal.indicators.get('volume_ratio', 0)
        signal.breakout_strength = self._calculate_breakout_strength(signal.indicators)
        is_valid, reason = self.trade_validator.validate_with_indicators(signal)
        if not is_valid:
            return None
        df = stocks_data.get(signal.ticker)
        if not is_tight_consolidation(df):
            return None
        if not is_strong_breakout(df):
            return None
        if is_valid_breakout(df) != 'BUY':
            return None
        signal.base_rank_score = self._calculate_base_rank_score(signal)
        signal.rank_score = signal.base_rank_score  # FIX 4: pure score only
        signal.market_context = self.market_context_engine.get_context()
        signal.quality = TradeJournal.calculate_quality(
            signal.strategy_score, signal.volume_ratio, signal.breakout_strength
        )
        signal.final_score = self._calculate_final_score(signal)
        return signal

    def _enrich_verc_signal(self, signal, stocks_data: dict):
        """Validate and enrich a VERC signal. Returns None if rejected."""
        from trade_journal import TradeJournal
        signal.strategy_type = 'VERC'
        signal.strategy_score = getattr(signal, 'confidence_score', 0)
        signal.volume_ratio = getattr(signal, 'relative_volume', 0)
        signal.breakout_strength = 0
        is_valid, reason = self.trade_validator.validate_with_indicators(signal)
        if not is_valid:
            return None
        df = stocks_data.get(signal.stock_symbol)
        if not is_tight_consolidation(df):
            return None
        if not is_strong_breakout(df):
            return None
        if is_valid_breakout(df) != 'BUY':
            return None
        signal.base_rank_score = self._calculate_base_rank_score(signal)
        signal.rank_score = signal.base_rank_score  # FIX 4: pure score only
        signal.market_context = self.market_context_engine.get_context()
        signal.quality = TradeJournal.calculate_quality(
            signal.strategy_score, signal.volume_ratio, 0
        )
        signal.final_score = self._calculate_final_score(signal)
        return signal

    # ------------------------------------------------------------------
    # MTF strategy — FIX 5: proper deduplication
    # ------------------------------------------------------------------

    def _run_mtf_strategy(self):
        try:
            use_mtf = self.settings.get('scanner', {}).get('enable_mtf_strategy', True)
            if not use_mtf:
                return
            mtf_stocks_data = self.data_fetcher.fetch_multiple_stocks_multi_timeframe(
                self.stocks, max_workers=3
            )
            if not mtf_stocks_data:
                return
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
            mtf_signals = self.mtf_scanner.scan_multiple_stocks(mtf_stocks_data, all_indicators)
            max_signals = self.settings.get('scanner', {}).get('max_signals_per_strategy', 2)
            mtf_signals = (mtf_signals or [])[:max_signals]
            current_signals = set()
            target_method = (
                self.alert_service.send_to_channel
                if self.alert_service.channel_chat_id
                else self.alert_service.send_alert
            )
            for signal in mtf_signals:
                signal_key = f"MTF:{signal.ticker}"
                current_signals.add(signal_key)
                if signal_key in self.previous_signals:
                    continue
                # FIX 5: also check signal_memory and trade_journal
                if self.signal_memory.is_duplicate(signal.ticker, 'MTF'):
                    logger.info(f"MTF signal for {signal.ticker} skipped — in signal_memory")
                    continue
                if self.trade_journal.check_signal_exists(signal.ticker, 'MTF'):
                    logger.info(f"MTF signal for {signal.ticker} skipped — in trade_journal")
                    continue
                try:
                    alert = format_mtf_signal_alert(signal)
                    target_method(alert)
                    self.total_signals += 1
                    # Track in memory so restarts don't re-send
                    self._track_signal_to_memory(signal, 'MTF')
                except Exception as e:
                    logger.error(f"Error sending MTF alert: {e}")
            self.previous_signals = self.previous_signals.union(current_signals)
        except Exception as e:
            logger.error(f"Error in MTF strategy: {e}")

    # ------------------------------------------------------------------
    # Unified strategy runner
    # ------------------------------------------------------------------

    def _run_all_strategies(self, stocks_data):
        from trade_journal import TradeJournal
        excluded_stocks = self.signal_memory.get_excluded_stocks()
        market_context = self.market_context_engine.get_context()
        all_signals = []
        current_signals = set()

        if self.strategy in ['trend', 'all']:
            for signal in self._get_trend_signals(stocks_data):
                if signal.ticker in excluded_stocks:
                    continue
                enriched = self._enrich_signal(signal, 'TREND', stocks_data)
                if not enriched:
                    continue
                if market_context == 'SIDEWAYS' and enriched.base_rank_score < 6:
                    continue
                if market_context == 'BEARISH':
                    enriched.rank_score = enriched.base_rank_score - 1
                if self._check_no_trade_zone(enriched, stocks_data.get(signal.ticker), market_context):
                    continue
                all_signals.append(enriched)

        if self.strategy in ['verc', 'all']:
            for signal in self._get_verc_signals(stocks_data):
                if signal.stock_symbol in excluded_stocks:
                    continue
                enriched = self._enrich_verc_signal(signal, stocks_data)
                if not enriched:
                    continue
                if self._check_no_trade_zone(enriched, stocks_data.get(signal.stock_symbol), market_context):
                    continue
                all_signals.append(enriched)

        # FIX 4: sort by (strategy_weight, pure rank_score) — weight not baked into score
        all_signals.sort(
            key=lambda x: (
                self.strategy_optimizer.strategy_weights.get(x.strategy_type, 0.5),
                x.rank_score
            ),
            reverse=True
        )

        final_signals = []
        seen_tickers = set()
        for signal in all_signals:
            ticker = signal.ticker if hasattr(signal, 'ticker') else signal.stock_symbol
            if ticker in seen_tickers:
                continue
            seen_tickers.add(ticker)
            signal_key = f"{signal.strategy_type}:{ticker}"
            if not self.signal_memory.is_duplicate(ticker, signal.strategy_type):
                final_signals.append(signal)
                current_signals.add(signal_key)
                try:
                    if signal.strategy_type == 'TREND':
                        alert = self._format_trend_alert(signal, stocks_data.get(ticker))
                        signal.alert = alert
                        self._track_signal_to_memory(signal, 'TREND')
                        # FIX 3: only track in memory/factor_analyzer — NO log_signal() here
                        self._track_trend_signal_learning_only(signal)
                    else:
                        alert = self._format_verc_alert(signal, stocks_data.get(ticker))
                        signal.alert = alert
                        self._track_signal_to_memory(signal, 'VERC')
                        self._track_verc_signal_learning_only(signal)
                except Exception as e:
                    logger.error(f"Error formatting/tracking signal for {ticker}: {e}")

        final_signals = final_signals[:5]
        self.previous_signals = current_signals

        if final_signals:
            self._send_unified_alerts([s.alert for s in final_signals if hasattr(s, 'alert')])

    # ------------------------------------------------------------------
    # FIX 3: Separate learning-only trackers (no log_signal calls)
    # ------------------------------------------------------------------

    def _track_trend_signal_learning_only(self, signal):
        """
        Update factor analyzer and signal tracker WITHOUT writing to trade_journal.
        log_signal() is called only from _process_signal() to avoid double-writes.
        """
        try:
            indicators = signal.indicators if hasattr(signal, 'indicators') else {}
            self.factor_analyzer.analyze_trade({
                'symbol': signal.ticker,
                'strategy': 'TREND',
                'outcome': 'OPEN',
                'volume_ratio': getattr(signal, 'volume_ratio', indicators.get('volume_ratio', 0)),
                'rsi': indicators.get('rsi_value', 0) or indicators.get('rsi', 0),
                'breakout_strength': getattr(signal, 'breakout_strength', 0),
                'quality': getattr(signal, 'quality', 'B'),
                'market_context': getattr(signal, 'market_context', 'BULLISH'),
                'entry_type': 'BREAKOUT',
            })
        except Exception as e:
            logger.error(f"Error in trend learning tracker: {e}")

    def _track_verc_signal_learning_only(self, signal):
        """
        Update factor analyzer WITHOUT writing to trade_journal.
        """
        try:
            self.factor_analyzer.analyze_trade({
                'symbol': signal.stock_symbol,
                'strategy': 'VERC',
                'outcome': 'OPEN',
                'volume_ratio': getattr(signal, 'relative_volume', 0),
                'rsi': 0,
                'breakout_strength': 0,
                'quality': getattr(signal, 'quality', 'B'),
                'market_context': getattr(signal, 'market_context', 'BULLISH'),
                'entry_type': 'BREAKOUT',
            })
        except Exception as e:
            logger.error(f"Error in VERC learning tracker: {e}")

    # ------------------------------------------------------------------
    # Scoring helpers
    # ------------------------------------------------------------------

    def _calculate_final_score(self, signal) -> float:
        strategy_score = signal.strategy_score
        volume_score = min(signal.volume_ratio / 3.0, 1.0) * 10
        breakout_score = signal.breakout_strength * 10
        base_score = (strategy_score * 0.6) + (volume_score * 0.2) + (breakout_score * 0.2)
        quality_bonus = {'A': 2, 'B': 1}.get(getattr(signal, 'quality', 'C'), 0)
        return round(base_score + quality_bonus, 2)

    def _calculate_base_rank_score(self, signal) -> float:
        """Pure rank score — strategy weight is NOT included here (FIX 4)."""
        strategy_score = signal.strategy_score
        volume_score = min(signal.volume_ratio / 3.0, 1.0) * 10
        breakout_score = signal.breakout_strength * 10
        return round((strategy_score * 0.6) + (volume_score * 0.2) + (breakout_score * 0.2), 2)

    def _calculate_rank_score(self, signal) -> float:
        """
        FIX 4: Returns the pure base score only.
        Strategy weight is applied in sort key, not baked into the number.
        """
        return self._calculate_base_rank_score(signal)

    def _calculate_breakout_strength(self, indicators) -> float:
        close = indicators.get('close', 0)
        high_20 = indicators.get('high_20')
        if high_20 and high_20 > 0:
            return (close - high_20) / high_20
        return 0.0

    def _check_no_trade_zone(self, signal, df, market_context) -> bool:
        if df is None:
            return False
        strategy_type = getattr(signal, 'strategy_type', 'TREND')
        if strategy_type == 'VERC':
            return False
        if strategy_type == 'TREND' and market_context == 'SIDEWAYS':
            return False
        try:
            atr = df['close'].diff().abs().rolling(14).mean().iloc[-1] if len(df) >= 14 else 0
            current_price = df['close'].iloc[-1]
            high = df['high'].iloc[-1]
            low = df['low'].iloc[-1]
            open_price = df['open'].iloc[-1]
            body = abs(current_price - open_price)
            upper_wick = high - max(current_price, open_price)
            lower_wick = min(current_price, open_price) - low
            wick_to_body = (upper_wick + lower_wick) / body if body > 0 else 0
            no_trade = self.strategy_optimizer.check_no_trade_conditions(
                atr=atr, wick_to_body_ratio=wick_to_body, nifty_direction=market_context
            )
            if not no_trade['allowed']:
                signal.rejection_reason = no_trade['reasons']
                return True
            quality_check = self.strategy_optimizer.check_signal_quality(
                score=signal.strategy_score,
                volume_ratio=signal.volume_ratio,
                breakout_strength=signal.breakout_strength
            )
            if not quality_check['passed']:
                signal.rejection_reason = quality_check['reasons']
                return True
            return False
        except Exception as e:
            logger.debug(f"Error in no-trade zone check: {e}")
            return False

    # ------------------------------------------------------------------
    # Signal sending — FIX 7: weekend gap warning
    # ------------------------------------------------------------------

    def _send_new_signal_alert(self, signal, target_method, now=None):
        ticker = signal.ticker if hasattr(signal, 'ticker') else signal.stock_symbol
        strategy = signal.strategy_type

        if strategy == 'TREND':
            indicators = signal.indicators
            entry = indicators.get('close', 0)
            ema50 = indicators.get('ema50', 0)
            atr = indicators.get('atr', 0)
            stop_loss = min(ema50, entry * 0.98) if ema50 > 0 else entry * 0.98
            if atr > 0:
                stop_loss = min(stop_loss, entry - (2 * atr))
            risk = entry - stop_loss
            t1 = entry + (risk * 2)
            t2 = entry + (risk * 3)
            t3 = entry + (risk * 4)
        else:
            entry = getattr(signal, 'entry_min', getattr(signal, 'current_price', 0))
            stop_loss = signal.stop_loss
            t1 = getattr(signal, 'target_1', 0)
            t2 = getattr(signal, 'target_2', 0)
            t3 = getattr(signal, 'target_3', 0)

        quality = getattr(signal, 'quality', 'B')
        context = getattr(signal, 'market_context', 'TRENDING')
        score = getattr(signal, 'final_score', 0)

        alert = (
            f"🚀 STOCK: {ticker}\n\n"
            f"💰 Entry: ₹{entry:.2f}\n"
            f"🛑 Stop: ₹{stop_loss:.2f}\n\n"
            f"🎯 Targets:\n{t1:.2f} / {t2:.2f} / {t3:.2f}\n\n"
            f"⭐ Quality: {quality}\n"
            f"🔥 Context: {context}\n"
            f"⚡ Score: {score}"
        )

        # FIX 7: add weekend gap warning on Friday signals
        if now is None:
            now = datetime.now(pytz.timezone('Asia/Kolkata'))
        if now.weekday() == 4:  # Friday
            alert += (
                "\n\n⚠️ Weekend gap risk: SL may not trigger until Monday open. "
                "Consider tighter position sizing."
            )

        target_method(alert)

        # Single authoritative journal write
        self.trade_journal.log_signal(
            symbol=ticker,
            strategy=strategy,
            direction="BUY",
            entry=entry,
            stop_loss=stop_loss,
            targets=[t1, t2, t3],
            indicators={
                'volume_ratio': getattr(signal, 'volume_ratio', 0),
                'final_score': score,
            },
            quality=quality,
            market_context=context,
            entry_type='BREAKOUT',
            breakout_strength=getattr(signal, 'breakout_strength', 0),
        )
        logger.info(f"New signal sent and journaled: {ticker} ({strategy})")

    def _send_unified_alerts(self, alerts):
        if not alerts:
            logger.info("No signals found in this scan")
            return
        target_method = (
            self.alert_service.send_to_channel
            if self.alert_service.channel_chat_id
            else self.alert_service.send_alert
        )
        for alert in alerts:
            target_method(alert)
            self.total_signals += 1

    def _send_no_signals_message(self):
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)
        message = (
            f"📊 Daily Scan Complete\n"
            f"Time: {now.strftime('%Y-%m-%d %H:%M')}\n\n"
            "No signals today.\nMarkets may be consolidating."
        )
        self.alert_service.send_alert(message)

    # ------------------------------------------------------------------
    # Process signal (single journal write point for scheduled scans)
    # ------------------------------------------------------------------

    def _process_signal(self, signal, strategy_type: str, is_startup: bool = False) -> bool:
        ticker = signal.ticker if strategy_type == 'TREND' else signal.stock_symbol
        existing_trade = self.trade_journal.check_signal_exists(ticker, strategy_type)
        if existing_trade:
            try:
                if strategy_type == 'TREND':
                    current_price = signal.indicators.get('close', 0)
                else:
                    current_price = getattr(signal, 'current_price', 0)
                if current_price > 0:
                    status = self._calculate_trade_status(existing_trade, current_price)
                    note = "Rechecked at startup" if is_startup else "3PM review update"
                    self.trade_journal.update_trade_note(existing_trade.get('trade_id', ''), note)
                    update_msg = self._format_update_for_telegram(existing_trade, current_price, status)
                    self.alert_service.send_alert(update_msg)
                    return True
            except Exception as e:
                logger.error(f"Error processing existing trade: {e}")
                return False
        else:
            try:
                if strategy_type == 'TREND':
                    indicators = signal.indicators
                    entry = indicators.get('close', 0)
                    ema50 = indicators.get('ema50', 0)
                    atr = indicators.get('atr', 0)
                    stop_loss = min(ema50, entry * 0.98) if ema50 > 0 else entry * 0.98
                    if atr > 0:
                        stop_loss = min(stop_loss, entry - (2 * atr))
                    risk = entry - stop_loss
                    targets = [entry + risk * 2, entry + risk * 3, entry + risk * 4]
                    volume_ratio = getattr(signal, 'volume_ratio', indicators.get('volume_ratio', 0))
                    rsi = indicators.get('rsi_value', 0) or indicators.get('rsi', 0)
                    trend_score = getattr(signal, 'trend_score', indicators.get('trend_score', 0))
                else:
                    entry = getattr(signal, 'entry_min', getattr(signal, 'current_price', 0))
                    stop_loss = getattr(signal, 'stop_loss', 0)
                    targets = [
                        getattr(signal, 'target_1', 0),
                        getattr(signal, 'target_2', 0),
                        getattr(signal, 'target_3', 0),
                    ]
                    volume_ratio = getattr(signal, 'relative_volume', 0)
                    rsi = 0
                    trend_score = 0

                # Single authoritative log_signal call
                trade_id = self.trade_journal.log_signal(
                    ticker, strategy_type, "BUY", entry, stop_loss, targets,
                    indicators={
                        'volume_ratio': volume_ratio,
                        'rsi': rsi,
                        'trend_score': trend_score,
                        'rank_score': getattr(signal, 'rank_score', 0),
                    },
                    quality=getattr(signal, 'quality', 'B'),
                    market_context=getattr(signal, 'market_context', 'BULLISH'),
                    entry_type='BREAKOUT',
                    breakout_strength=getattr(signal, 'breakout_strength', 0),
                )
                signal_msg = self._format_signal_for_telegram(signal, strategy_type)
                self.alert_service.send_alert(signal_msg)
                self.total_signals += 1
                return True
            except Exception as e:
                logger.error(f"Error sending new signal: {e}")
                return False
        return False

    # ------------------------------------------------------------------
    # Signal tracking helpers
    # ------------------------------------------------------------------

    def _track_signal_to_memory(self, signal, signal_type: str):
        try:
            stock_symbol = signal.ticker if signal_type == 'TREND' else signal.stock_symbol
            entry_price = (
                signal.indicators.get('close', 0)
                if signal_type == 'TREND'
                else getattr(signal, 'entry_min', getattr(signal, 'current_price', 0))
            )
            self.signal_memory.add_signal({
                'stock_symbol': stock_symbol,
                'signal_type': signal_type,
                'entry_price': entry_price,
                'target_price': getattr(signal, 'target_1', 0),
                'sl_price': getattr(signal, 'stop_loss', 0),
                'confidence_score': getattr(signal, 'confidence_score', 50),
            })
        except Exception as e:
            logger.error(f"Error tracking signal to memory: {e}")

    def _track_signal(self, signal_data: dict, signal_type: str):
        try:
            import uuid
            signal_id = (
                f"{signal_type}_{signal_data.get('stock_symbol', 'UNKNOWN')}"
                f"_{uuid.uuid4().hex[:8]}"
            )
            self.history_manager.add_active_signal({
                **signal_data,
                'signal_id': signal_id,
                'signal_type': signal_type,
            })
        except Exception as e:
            logger.error(f"Error tracking signal: {e}")

    # ------------------------------------------------------------------
    # Startup scan
    # ------------------------------------------------------------------

    def _run_startup_notification_scan(self):
        logger.info("Running startup notification scan...")
        try:
            stocks_data = self.data_fetcher.fetch_multiple_stocks(self.stocks)
            if not stocks_data:
                return
            all_signals = []
            if self.strategy in ['trend', 'all']:
                for signal in self._get_trend_signals(stocks_data):
                    enriched = self._enrich_signal(signal, 'TREND', stocks_data)
                    if enriched:
                        all_signals.append(enriched)
            if self.strategy in ['verc', 'all']:
                for signal in self._get_verc_signals(stocks_data):
                    enriched = self._enrich_verc_signal(signal, stocks_data)
                    if enriched:
                        all_signals.append(enriched)
            all_signals.sort(key=lambda x: getattr(x, 'final_score', 0), reverse=True)
            ist = pytz.timezone('Asia/Kolkata')
            now = datetime.now(ist)
            target_method = (
                self.alert_service.send_to_channel
                if self.alert_service.channel_chat_id
                else self.alert_service.send_alert
            )
            for signal in all_signals:
                if self._signals_sent_today >= self.max_signals_per_day:
                    break
                ticker = signal.ticker if hasattr(signal, 'ticker') else signal.stock_symbol
                if self.trade_journal.check_signal_exists(ticker, signal.strategy_type):
                    continue
                if getattr(signal, 'final_score', 0) < self.confidence_threshold:
                    continue
                self._send_new_signal_alert(signal, target_method, now)
                self._signals_sent_today += 1
            logger.info(f"Startup scan complete — sent {self._signals_sent_today} signals")
        except Exception as e:
            logger.error(f"Error in startup notification scan: {e}")

    def _run_periodic_scan(self):
        logger.info("Running periodic scan (15 min)...")
        try:
            stocks_data = self.data_fetcher.fetch_multiple_stocks(self.stocks)
            if not stocks_data:
                return
            all_signals = []
            if self.strategy in ['trend', 'all']:
                for signal in self._get_trend_signals(stocks_data):
                    enriched = self._enrich_signal(signal, 'TREND', stocks_data)
                    if enriched:
                        all_signals.append(enriched)
            if self.strategy in ['verc', 'all']:
                for signal in self._get_verc_signals(stocks_data):
                    enriched = self._enrich_verc_signal(signal, stocks_data)
                    if enriched:
                        all_signals.append(enriched)
            all_signals.sort(key=lambda x: getattr(x, 'final_score', 0), reverse=True)
            filtered = [
                s for s in all_signals
                if not self.trade_journal.check_signal_exists(
                    s.ticker if hasattr(s, 'ticker') else s.stock_symbol,
                    s.strategy_type
                )
                and getattr(s, 'final_score', 0) >= self.confidence_threshold
            ]
            self._update_top5_candidates(filtered)
            logger.info(
                f"Periodic scan: {len(filtered)} qualifying signals. "
                f"Top-5 pool: {len(self._top5_candidates)}"
            )
        except Exception as e:
            logger.error(f"Error in periodic scan: {e}")

    def _update_top5_candidates(self, new_signals: list):
        for signal in new_signals:
            ticker = signal.ticker if hasattr(signal, 'ticker') else signal.stock_symbol
            signal_key = f"{signal.strategy_type}:{ticker}"
            existing_idx = next(
                (i for i, s in enumerate(self._top5_candidates)
                 if f"{s.strategy_type}:{s.ticker if hasattr(s,'ticker') else s.stock_symbol}" == signal_key),
                None
            )
            if existing_idx is not None:
                if getattr(signal, 'final_score', 0) > getattr(self._top5_candidates[existing_idx], 'final_score', 0):
                    self._top5_candidates[existing_idx] = signal
            else:
                self._top5_candidates.append(signal)
        self._top5_candidates.sort(key=lambda x: getattr(x, 'final_score', 0), reverse=True)
        self._top5_candidates = self._top5_candidates[:5]

    # ------------------------------------------------------------------
    # Active signal checking & learning loop
    # ------------------------------------------------------------------

    def _check_active_signals(self):
        try:
            last_learning = getattr(self, '_last_learning_time', None)
            if last_learning:
                from datetime import timedelta
                if datetime.now() - last_learning < timedelta(days=1):
                    logger.debug("Learning cooldown active, skipping")
            result = self.signal_tracker.check_all_active_signals()
            completed = result.get('completed', [])
            if completed:
                target_method = (
                    self.alert_service.send_to_channel
                    if self.alert_service.channel_chat_id
                    else self.alert_service.send_alert
                )
                for signal in completed:
                    trade_id = signal.get('signal_id', '')
                    outcome = signal.get('outcome', 'UNKNOWN')
                    exit_price = signal.get('current_price', 0)
                    entry_price = signal.get('entry_price', 0)
                    stock_symbol = signal.get('stock_symbol', '')
                    if outcome == 'TARGET_HIT':
                        self.trade_journal.update_trade(trade_id, 'WIN', exit_price)
                        return_pct = ((exit_price - entry_price) / entry_price * 100) if entry_price else 0
                        target_method(
                            f"🎯 TARGET HIT: {stock_symbol}\nEntry: ₹{entry_price:.2f}\n"
                            f"Target: ₹{exit_price:.2f}\nReturn: +{return_pct:.1f}%"
                        )
                    elif outcome == 'SL_HIT':
                        self.trade_journal.update_trade(trade_id, 'LOSS', exit_price)
                        loss_pct = ((entry_price - exit_price) / entry_price * 100) if entry_price else 0
                        target_method(
                            f"🛑 STOP LOSS: {stock_symbol}\nEntry: ₹{entry_price:.2f}\n"
                            f"SL: ₹{exit_price:.2f}\nLoss: -{loss_pct:.1f}%"
                        )
                    self.notification_manager.notify_signal_completed(signal)
                self.notification_manager.notify_outcome_batch(completed)
                closed_trades = self.trade_journal.get_closed_trades(limit=100)
                if len(closed_trades) >= 20:
                    self.factor_analyzer.batch_analyze(closed_trades)
                    recommendations = self.factor_analyzer.get_optimization_recommendations()
                    if recommendations:
                        self.strategy_optimizer.adapt_filters_from_factor_analysis(recommendations)
                    self.strategy_optimizer.auto_optimize()
                    self._last_learning_time = datetime.now()
        except Exception as e:
            logger.error(f"Error checking active signals: {e}")

    # ------------------------------------------------------------------
    # Strategy runners
    # ------------------------------------------------------------------

    def _get_trend_signals(self, stocks_data):
        scan_result = self.trend_detector.analyze_multiple_stocks_with_scans(stocks_data)
        return scan_result.intersection

    def _get_verc_signals(self, stocks_data):
        return verc_scan_stocks(stocks_data)

    # ------------------------------------------------------------------
    # Alert formatting
    # ------------------------------------------------------------------

    def _format_trend_alert(self, signal, df=None):
        indicators = signal.indicators
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)
        current_price = indicators.get('close', 0)
        ema50 = indicators.get('ema50', 0)
        atr = indicators.get('atr', 0)
        stop_loss = min(ema50, current_price * 0.98) if ema50 > 0 else current_price * 0.98
        if atr > 0:
            stop_loss = min(stop_loss, current_price - (2 * atr))
        risk_pct = (current_price - stop_loss) / current_price * 100
        if risk_pct < 2:
            stop_loss = current_price * 0.98
        elif risk_pct > 3:
            stop_loss = current_price * 0.97
        risk = current_price - stop_loss
        t1 = current_price + risk * 2
        t2 = current_price + risk * 3
        atr_val = self._calculate_atr(df)
        time_t1 = self._estimate_time_to_target(current_price, t1, atr_val)
        time_t2 = self._estimate_time_to_target(current_price, t2, atr_val)
        support, resistance = self._calculate_support_resistance(df) if df is not None else (None, None)
        trend_score = getattr(signal, 'trend_score', indicators.get('trend_score', 0))
        volume_ratio = getattr(signal, 'volume_ratio', indicators.get('volume_ratio', 0))
        rsi_value = indicators.get('rsi_value', 0) or indicators.get('rsi', 0)
        sl_pct = (current_price - stop_loss) / current_price * 100
        t1_pct = (t1 - current_price) / current_price * 100
        t2_pct = (t2 - current_price) / current_price * 100
        lines = [
            "📈 TREND SIGNAL", "",
            f"Stock: {signal.ticker}",
            f"Time: {now.strftime('%Y-%m-%d %H:%M')} IST", "",
            f"💰 Price: ₹{current_price:.2f}", "",
            f"🎯 Entry Zone:\n  Buy Above: ₹{current_price * 1.005:.2f}", "",
            f"🛡️ Stop Loss:\n  SL: ₹{stop_loss:.2f} ({sl_pct:.1f}%)", "",
            f"🎯 Targets (RR ≥ 2:1):",
            f"  Target 1: ₹{t1:.2f} (+{t1_pct:.1f}%) ETA: {time_t1}",
            f"  Target 2: ₹{t2:.2f} (+{t2_pct:.1f}%) ETA: {time_t2}", "",
        ]
        if support and resistance:
            lines += [f"📊 S/R:\n  Support: ₹{support:.2f}\n  Resistance: ₹{resistance:.2f}", ""]
        lines += [
            f"📊 Metrics:\n  Score: {trend_score}/10\n  Volume: {volume_ratio:.2f}x\n  RSI: {rsi_value:.1f}",
        ]
        return "\n".join(lines)

    def _format_verc_alert(self, signal, df=None):
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)
        atr = self._calculate_atr(df)
        time_t1 = self._estimate_time_to_target(signal.current_price, signal.target_1, atr)
        time_t2 = self._estimate_time_to_target(signal.current_price, signal.target_2, atr)
        support, resistance = self._calculate_support_resistance(df) if df is not None else (None, None)
        sl_pct = (signal.current_price - signal.stop_loss) / signal.current_price * 100
        t1_pct = (signal.target_1 - signal.current_price) / signal.current_price * 100
        t2_pct = (signal.target_2 - signal.current_price) / signal.current_price * 100
        lines = [
            "📊 VERC SIGNAL (Accumulation)", "",
            f"Stock: {signal.stock_symbol}",
            f"Time: {now.strftime('%Y-%m-%d %H:%M')} IST", "",
            f"💰 Price: ₹{signal.current_price:.2f}", "",
            f"🔄 Range: ₹{signal.compression_low:.2f} - ₹{signal.compression_high:.2f}",
            f"🎯 Entry: ₹{signal.entry_min:.2f} - ₹{signal.entry_max:.2f}", "",
            f"🛡️ Stop: ₹{signal.stop_loss:.2f} ({sl_pct:.1f}%)", "",
            f"🎯 Targets:",
            f"  T1: ₹{signal.target_1:.2f} (+{t1_pct:.1f}%) ETA: {time_t1}",
            f"  T2: ₹{signal.target_2:.2f} (+{t2_pct:.1f}%) ETA: {time_t2}", "",
        ]
        if support and resistance:
            lines += [f"📊 S/R:\n  Support: ₹{support:.2f}\n  Resistance: ₹{resistance:.2f}", ""]
        lines.append(f"Confidence: {signal.confidence_score}/10")
        return "\n".join(lines)

    def _format_signal_for_telegram(self, signal, strategy_type: str, current_price: float = 0) -> str:
        if strategy_type == 'TREND':
            indicators = signal.indicators
            ticker = signal.ticker
            entry = indicators.get('close', 0)
            ema50 = indicators.get('ema50', 0)
            atr = indicators.get('atr', 0)
            stop_loss = min(ema50, entry * 0.98) if ema50 > 0 else entry * 0.98
            if atr > 0:
                stop_loss = min(stop_loss, entry - (2 * atr))
            risk = entry - stop_loss
            t1 = entry + risk * 2
            t2 = entry + risk * 3
            t3 = entry + risk * 4
            score = getattr(signal, 'rank_score', getattr(signal, 'trend_score', 0))
            return (
                f"📈 {ticker}\n🎯 Entry: {entry:.0f}\n🛡️ SL: {stop_loss:.0f}\n"
                f"🚀 Targets: {t1:.0f} / {t2:.0f} / {t3:.0f}\n⭐ Score: {score:.1f}"
            )
        ticker = signal.stock_symbol
        entry = getattr(signal, 'entry_min', getattr(signal, 'current_price', 0))
        stop_loss = getattr(signal, 'stop_loss', 0)
        t1 = getattr(signal, 'target_1', 0)
        t2 = getattr(signal, 'target_2', 0)
        t3 = getattr(signal, 'target_3', 0)
        score = getattr(signal, 'rank_score', getattr(signal, 'confidence_score', 0))
        return (
            f"📈 {ticker}\n🎯 Entry: {entry:.0f}\n🛡️ SL: {stop_loss:.0f}\n"
            f"🚀 Targets: {t1:.0f} / {t2:.0f} / {t3:.0f}\n⭐ Score: {score:.1f}"
        )

    def _format_update_for_telegram(self, trade: Dict, current_price: float, status: str) -> str:
        return (
            f"UPDATE: {trade.get('symbol','')} ({trade.get('strategy','')})\n"
            f"Status: {status}\nEntry: {trade.get('entry',0):.0f}\n"
            f"Current: {current_price:.0f}\nNote: Already shared earlier"
        )

    def _calculate_trade_status(self, trade: Dict, current_price: float) -> str:
        targets = trade.get('targets', [])
        entry = trade.get('entry', 0)
        stop_loss = trade.get('stop_loss', 0)
        if not targets or not entry:
            return 'OPEN'
        t1 = targets[0] if len(targets) > 0 else 0
        t2 = targets[1] if len(targets) > 1 else 0
        t3 = targets[2] if len(targets) > 2 else 0
        if t3 and current_price >= t3:
            return 'TARGET3_HIT'
        if t2 and current_price >= t2:
            return 'TARGET2_HIT'
        if t1 and current_price >= t1:
            return 'TARGET1_HIT'
        if stop_loss and current_price <= stop_loss:
            return 'STOP_LOSS_HIT'
        return 'OPEN'

    # ------------------------------------------------------------------
    # ATR / S/R / time estimation helpers — FIX 8 (ATR estimate)
    # ------------------------------------------------------------------

    def _calculate_atr(self, df, period=14):
        if df is None or len(df) < period:
            return None
        if not all(c in df.columns for c in ['high', 'low', 'close']):
            return None
        try:
            high, low, close = df['high'], df['low'], df['close']
            tr = pd.concat([
                high - low,
                abs(high - close.shift(1)),
                abs(low - close.shift(1)),
            ], axis=1).max(axis=1)
            return tr.rolling(window=period).mean().iloc[-1]
        except Exception:
            return None

    def _calculate_support_resistance(self, df, lookback=20):
        if df is None or len(df) < lookback:
            return None, None
        if 'high' not in df.columns or 'low' not in df.columns:
            return None, None
        try:
            recent = df.tail(lookback)
            return recent['low'].min(), recent['high'].max()
        except Exception:
            return None, None

    def _estimate_time_to_target(self, current_price, target_price, atr):
        """
        FIX 8: Use ~35% of ATR as expected directional daily progress.
        ATR is the full candle range, not the net move — dividing by ATR
        directly gave estimates that were ~3x too optimistic.
        """
        if not atr or atr <= 0 or not current_price:
            return "Unknown"
        directional_daily = atr * 0.35  # ~35% of range is directional
        price_diff = abs(target_price - current_price)
        if price_diff == 0:
            return "Already at target"
        days = price_diff / directional_daily
        if days <= 2:
            return f"~{max(1,int(days))} day{'s' if days > 1 else ''}"
        if days <= 10:
            return f"~{int(days)} days"
        if days <= 21:
            return f"~{int(days / 7)} weeks"
        return f"~{int(days / 30)} months"

    # ------------------------------------------------------------------
    # Startup / stop
    # ------------------------------------------------------------------

    def _run_startup_scan(self):
        self._run_startup_notification_scan()

    def start(self):
        logger.info(
            f"NSE Trend Scanner started — Strategy: {self.strategy}, "
            f"Stocks: {len(self.stocks)}, Max signals/day: {self.max_signals_per_day}"
        )
        self._run_startup_notification_scan()
        if self.telegram_bot:
            self.telegram_bot.start_background()

        # FIX 1: distinct job_id for each continuous job
        self.scheduler.add_continuous_job(self.run_continuous_monitoring, 'continuous_monitor')
        self.scheduler.add_continuous_job(self._run_periodic_scan, 'periodic_scan')
        self.scheduler.add_signal_generation_job(self.run_signal_generation, 'signal_generator')
        self.scheduler.start()

        try:
            while True:
                import time
                time.sleep(3600)
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        self.scheduler.stop()
        logger.info(
            f"NSE Trend Scanner stopped — Scans: {self.total_scans}, "
            f"Signals: {self.total_signals}"
        )

    def run_once(self):
        if not self.data_fetcher.is_market_open():
            logger.info("Market closed — scan will run with last available data.")
        self.scan()

    def test_telegram(self) -> bool:
        if not self.telegram_token or not self.telegram_chat_id:
            logger.warning("Telegram credentials not configured.")
            return False
        return self.alert_service.test_connection()

    def get_performance_stats(self) -> dict:
        try:
            return self.performance_tracker.generate_performance_report()
        except Exception as e:
            logger.error(f"Error getting performance stats: {e}")
            return {}


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------

def parse_arguments():
    parser = argparse.ArgumentParser(description="NSE Trend Scanner Agent")
    parser.add_argument('--strategy', default='all', choices=['trend', 'verc', 'all'])
    parser.add_argument('--config', default='config/stocks.json')
    parser.add_argument('--telegram-token', default=os.environ.get('TELEGRAM_BOT_TOKEN'))
    parser.add_argument('--telegram-chat-id', default=os.environ.get('TELEGRAM_CHAT_ID'))
    parser.add_argument('--telegram-channel-chat-id', default=os.environ.get('TELEGRAM_CHANNEL_ID'))
    parser.add_argument('--test', action='store_true')
    parser.add_argument('--test-telegram', action='store_true')
    parser.add_argument('--mock-alerts', action='store_true')
    parser.add_argument('--enable-telegram-bot', action='store_true')
    parser.add_argument('--log-level', default='INFO', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'])
    parser.add_argument('--log-file', default='logs/scanner.log')
    parser.add_argument('--schedule', action='store_true')
    return parser.parse_args()


def main():
    args = parse_arguments()
    logging.getLogger('yfinance').setLevel(logging.ERROR)
    logging.getLogger('pandas').setLevel(logging.ERROR)
    setup_logging(args.log_level, args.log_file)

    scanner = NSETrendScanner(
        config_path=args.config,
        telegram_token=args.telegram_token,
        telegram_chat_id=args.telegram_chat_id,
        telegram_channel_chat_id=args.telegram_channel_chat_id,
        use_mock_alerts=args.mock_alerts,
        strategy=args.strategy,
        enable_telegram_bot=args.enable_telegram_bot,
    )

    if args.test:
        scanner.run_once()
        return
    if args.test_telegram:
        success = scanner.test_telegram()
        print("Telegram test successful!" if success else "Telegram test failed!")
        return

    scanner.start()


if __name__ == "__main__":
    main()
