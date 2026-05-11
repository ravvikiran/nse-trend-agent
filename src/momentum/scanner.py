"""
MomentumScanner: Main pipeline orchestrator for the NSE Momentum Scanner.

Wires all pipeline stages together and executes one complete scan cycle:
  DataProvider (1H) → Stage1 filter → DataProvider (NIFTY + RS rank) →
  MarketBreadth check → DataProvider (15m) → Stage3 triggers → TradeLevels →
  SectorBoost → FinalRank → Dedup → Alert → Log

Returns a ScanCycleResult with all metrics for each cycle.

Requirements: 1.3, 1.6, 16.1, 16.2, 16.3, 16.4, 18.1, 18.3
"""

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import pandas as pd

from src.momentum.alert_formatter import AlertFormatter
from src.momentum.data_provider import DataProvider
from src.momentum.deduplicator import Deduplicator
from src.momentum.final_ranker import CandidateSignal, FinalRanker
from src.momentum.market_breadth_filter import MarketBreadthFilter
from src.momentum.models import MomentumSignal, ScanCycleResult, ScannerConfig, SetupType
from src.momentum.scan_logger import ScanLogger
from src.momentum.sector_analyzer import SectorAnalyzer
from src.momentum.stage1_trend_filter import Stage1TrendFilter
from src.momentum.stage2_relative_strength import Stage2RelativeStrength
from src.momentum.stage3_entry_trigger import Stage3EntryTrigger
from src.momentum.trade_levels import TradeLevelCalculator
from src.momentum.universe_manager import UniverseManager

logger = logging.getLogger(__name__)

# IST timezone offset (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))

# NIFTY 50 symbol used for relative strength and breadth calculations
NIFTY_SYMBOL = "NIFTY 50"

# Number of candles to fetch per timeframe
PERIODS_1H = 210  # Enough for EMA(200) + slope lookback
PERIODS_15M = 40  # Enough for EMA(20) + volume SMA(30) + Stage 3 detection


class MomentumScanner:
    """Main pipeline orchestrator that wires all stages together.

    Accepts all dependencies via constructor and implements a single
    `run_cycle()` method that executes one complete scan pipeline.

    The pipeline is deterministic: same OHLCV inputs always produce
    the same ranked output.
    """

    def __init__(
        self,
        data_provider: DataProvider,
        stage1_filter: Stage1TrendFilter,
        stage2_rs: Stage2RelativeStrength,
        stage3_trigger: Stage3EntryTrigger,
        final_ranker: FinalRanker,
        deduplicator: Deduplicator,
        alert_formatter: AlertFormatter,
        market_breadth_filter: MarketBreadthFilter,
        sector_analyzer: SectorAnalyzer,
        trade_level_calculator: TradeLevelCalculator,
        scan_logger: ScanLogger,
        universe_manager: UniverseManager,
        config: ScannerConfig,
    ):
        """Initialize MomentumScanner with all pipeline dependencies.

        Args:
            data_provider: Broker API data fetcher (abstract interface).
            stage1_filter: 1H trend filter (EMA alignment + slope).
            stage2_rs: Relative strength ranker vs NIFTY.
            stage3_trigger: 15m entry trigger detector.
            final_ranker: Weighted scoring and top-5 selection.
            deduplicator: Alert throttling and deduplication.
            alert_formatter: Telegram message formatting and delivery.
            market_breadth_filter: Market health check (breadth + NIFTY EMA).
            sector_analyzer: Sector performance vs NIFTY.
            trade_level_calculator: Entry, SL, targets, trailing stop.
            scan_logger: SQLite persistence for scan cycles.
            universe_manager: Stock universe loading and filtering.
            config: Scanner configuration parameters.
        """
        self.data_provider = data_provider
        self.stage1_filter = stage1_filter
        self.stage2_rs = stage2_rs
        self.stage3_trigger = stage3_trigger
        self.final_ranker = final_ranker
        self.deduplicator = deduplicator
        self.alert_formatter = alert_formatter
        self.market_breadth_filter = market_breadth_filter
        self.sector_analyzer = sector_analyzer
        self.trade_level_calculator = trade_level_calculator
        self.scan_logger = scan_logger
        self.universe_manager = universe_manager
        self.config = config

    async def run_cycle(self) -> ScanCycleResult:
        """Execute one complete scan cycle and return results.

        Pipeline steps:
          1. Get active universe
          2. Fetch 1H data for all stocks
          3. Stage 1: Trend filter (EMA alignment + slope)
          4. Fetch NIFTY data + compute RS rankings
          5. Check market breadth
          6. Fetch 15m data for Stage 1 survivors
          7. Stage 3: Entry trigger detection
          8. Calculate trade levels
          9. Apply sector boost
          10. Final ranking (top 5)
          11. Deduplication
          12. Send alerts
          13. Log cycle

        Returns:
            ScanCycleResult with all metrics from the cycle.
        """
        start_time = time.monotonic()
        now = datetime.now(IST)
        rejected_reasons: Dict[str, int] = {}

        # Track pipeline metrics
        stage1_passed = 0
        stage2_ranked = 0
        stage3_triggered = 0
        signals_generated: List[MomentumSignal] = []
        signals_suppressed = 0
        market_breadth_healthy = True

        try:
            # Step 1: Get active universe
            universe = self.universe_manager.get_active_universe()
            if not universe:
                logger.info("No stocks in active universe. Skipping cycle.")
                return self._build_result(
                    now, start_time, 0, 0, 0, [], 0, True, rejected_reasons
                )

            # Step 2: Fetch 1H data for all stocks (batch)
            stocks_1h_data = await self._fetch_1h_data(universe)
            if not stocks_1h_data:
                logger.warning("No 1H data fetched. Skipping cycle.")
                rejected_reasons["no_1h_data"] = len(universe)
                return self._build_result(
                    now, start_time, 0, 0, 0, [], 0, True, rejected_reasons
                )

            skipped_1h = len(universe) - len(stocks_1h_data)
            if skipped_1h > 0:
                rejected_reasons["missing_1h_data"] = skipped_1h

            # Step 3: Stage 1 — Trend filter
            stage1_symbols = self.stage1_filter.filter(stocks_1h_data)
            stage1_passed = len(stage1_symbols)

            if not stage1_symbols:
                logger.info("No stocks passed Stage 1 trend filter.")
                rejected_reasons["stage1_failed"] = len(stocks_1h_data)
                return self._build_result(
                    now, start_time, 0, 0, 0, [], 0, True, rejected_reasons
                )

            rejected_reasons["stage1_failed"] = len(stocks_1h_data) - stage1_passed

            # Step 4: Fetch NIFTY data + RS ranking
            nifty_data = await self.data_provider.fetch_ohlcv(
                NIFTY_SYMBOL, "1h", PERIODS_1H
            )
            if nifty_data is None or nifty_data.empty:
                logger.warning("NIFTY data unavailable. Using Stage 1 order.")
                # Fall through with unranked list
                rs_ranked = [(s, 0.0) for s in stage1_symbols]
            else:
                rs_ranked = self.stage2_rs.rank(
                    stage1_symbols, stocks_1h_data, nifty_data
                )

            stage2_ranked = len(rs_ranked)

            # Step 5: Check market breadth
            market_breadth_healthy = await self._check_market_breadth(
                stocks_1h_data, universe
            )

            if not market_breadth_healthy:
                logger.warning(
                    "Market breadth unhealthy — suppressing all long signals."
                )
                return self._build_result(
                    now, start_time, stage1_passed, stage2_ranked, 0,
                    [], 0, False, rejected_reasons
                )

            # Step 6: Fetch 15m data for Stage 1 survivors
            stage1_15m_data = await self._fetch_15m_data(stage1_symbols)
            if not stage1_15m_data:
                logger.warning("No 15m data fetched for Stage 1 survivors.")
                rejected_reasons["missing_15m_data"] = len(stage1_symbols)
                return self._build_result(
                    now, start_time, stage1_passed, stage2_ranked, 0,
                    [], 0, True, rejected_reasons
                )

            # Step 6b: Data staleness check — remove stocks with stale data (>30 min old)
            stage1_15m_data = self._filter_stale_data(stage1_15m_data, now)

            skipped_15m = len(stage1_symbols) - len(stage1_15m_data)
            if skipped_15m > 0:
                rejected_reasons["missing_15m_data"] = skipped_15m

            # Step 7: Stage 3 — Entry trigger detection
            triggered_results = self._run_stage3(stage1_15m_data)
            stage3_triggered = len(triggered_results)

            if not triggered_results:
                logger.info("No entry triggers detected in Stage 3.")
                rejected_reasons["no_trigger"] = len(stage1_15m_data)
                return self._build_result(
                    now, start_time, stage1_passed, stage2_ranked, 0,
                    [], 0, True, rejected_reasons
                )

            rejected_reasons["no_trigger"] = len(stage1_15m_data) - stage3_triggered

            # Step 8: Calculate trade levels
            candidates_with_levels = self._calculate_trade_levels(
                triggered_results, stage1_15m_data
            )

            if not candidates_with_levels:
                logger.info("No valid trade levels calculated.")
                rejected_reasons["invalid_trade_levels"] = stage3_triggered
                return self._build_result(
                    now, start_time, stage1_passed, stage2_ranked,
                    stage3_triggered, [], 0, True, rejected_reasons
                )

            invalid_levels = stage3_triggered - len(candidates_with_levels)
            if invalid_levels > 0:
                rejected_reasons["invalid_trade_levels"] = invalid_levels

            # Step 9: Apply sector boost
            sector_scores = await self._get_sector_scores()
            candidates = self._build_candidates(
                candidates_with_levels, rs_ranked, stocks_1h_data, sector_scores
            )

            # Step 10: Final ranking (top 5)
            ranked_signals = self.final_ranker.rank(candidates)

            # Step 11: Build MomentumSignal objects
            momentum_signals = self._build_momentum_signals(
                ranked_signals, rs_ranked, sector_scores, now
            )

            # Step 12: Deduplication + Alert
            for signal in momentum_signals:
                should_send = self.deduplicator.should_alert(
                    signal.symbol, signal.setup_type, signal.rank_score, now
                )
                if should_send:
                    signals_generated.append(signal)
                    self.deduplicator.record_alert(
                        signal.symbol, signal.setup_type, signal.rank_score, now
                    )
                    # Send alert (non-blocking, failure doesn't stop pipeline)
                    self._send_alert(signal)
                else:
                    signals_suppressed += 1

            # Step 13: Build and log result
            result = self._build_result(
                now, start_time, stage1_passed, stage2_ranked,
                stage3_triggered, signals_generated, signals_suppressed,
                market_breadth_healthy, rejected_reasons
            )

            # Log cycle to database (non-critical path)
            self._log_cycle(result)

            # Check cycle duration and warn/error
            self._check_duration(result.duration_seconds)

            return result

        except Exception as e:
            logger.error(f"Scan cycle failed with unexpected error: {e}", exc_info=True)
            # Return partial result on unexpected failure
            return self._build_result(
                now, start_time, stage1_passed, stage2_ranked,
                stage3_triggered, signals_generated, signals_suppressed,
                market_breadth_healthy, rejected_reasons
            )

    # -------------------------------------------------------------------------
    # Private helper methods
    # -------------------------------------------------------------------------

    async def _fetch_1h_data(
        self, symbols: List[str]
    ) -> Dict[str, pd.DataFrame]:
        """Fetch 1H OHLCV data for all symbols, skipping failures gracefully.

        Args:
            symbols: List of stock symbols to fetch.

        Returns:
            Dict mapping symbol to its 1H DataFrame. Only includes
            symbols with valid data.
        """
        try:
            data = await self.data_provider.fetch_batch(
                symbols, "1h", PERIODS_1H
            )
            return data
        except Exception as e:
            logger.error(f"Failed to fetch 1H batch data: {e}")
            return {}

    async def _fetch_15m_data(
        self, symbols: List[str]
    ) -> Dict[str, pd.DataFrame]:
        """Fetch 15m OHLCV data for symbols, skipping failures gracefully.

        Args:
            symbols: List of stock symbols to fetch.

        Returns:
            Dict mapping symbol to its 15m DataFrame. Only includes
            symbols with valid data.
        """
        try:
            data = await self.data_provider.fetch_batch(
                symbols, "15m", PERIODS_15M
            )
            return data
        except Exception as e:
            logger.error(f"Failed to fetch 15m batch data: {e}")
            return {}

    def _filter_stale_data(
        self,
        stocks_data: Dict[str, pd.DataFrame],
        current_time: datetime,
        max_age_minutes: int = 30,
    ) -> Dict[str, pd.DataFrame]:
        """Remove stocks whose latest candle is older than max_age_minutes.

        This ensures we're not making decisions on stale/delayed data.

        Args:
            stocks_data: Dict of symbol -> DataFrame with 'timestamp' column.
            current_time: Current IST datetime for comparison.
            max_age_minutes: Maximum allowed age of the latest candle (default 30).

        Returns:
            Filtered dict with only stocks that have fresh data.
        """
        fresh_data: Dict[str, pd.DataFrame] = {}

        for symbol, df in stocks_data.items():
            if df is None or df.empty:
                continue

            # Check if DataFrame has a timestamp column
            if "timestamp" not in df.columns:
                # No timestamp to check — include it (can't verify freshness)
                fresh_data[symbol] = df
                continue

            try:
                latest_timestamp = pd.to_datetime(df["timestamp"].iloc[-1])

                # Make timezone-aware if naive
                if latest_timestamp.tzinfo is None:
                    latest_timestamp = latest_timestamp.replace(tzinfo=IST)

                # Compare with current time
                age = current_time - latest_timestamp
                age_minutes = age.total_seconds() / 60

                if age_minutes <= max_age_minutes:
                    fresh_data[symbol] = df
                else:
                    logger.debug(
                        "%s: data is stale (%.0f min old, max %d min). Excluding.",
                        symbol, age_minutes, max_age_minutes,
                    )
            except Exception as e:
                # If we can't parse the timestamp, include the stock anyway
                logger.debug("%s: could not check staleness: %s", symbol, e)
                fresh_data[symbol] = df

        stale_count = len(stocks_data) - len(fresh_data)
        if stale_count > 0:
            logger.info(
                "Staleness check: %d/%d stocks excluded (data older than %d min)",
                stale_count, len(stocks_data), max_age_minutes,
            )

        return fresh_data

    async def _check_market_breadth(
        self,
        stocks_1h_data: Dict[str, pd.DataFrame],
        universe: List[str],
    ) -> bool:
        """Check market breadth health using advancing/declining counts.

        Counts advancing vs declining stocks from the 1H data and fetches
        NIFTY 15m data for EMA comparison.

        Args:
            stocks_1h_data: 1H data already fetched for the universe.
            universe: Full active universe for breadth calculation.

        Returns:
            True if market is healthy, False if signals should be suppressed.
        """
        try:
            # Count advancing vs declining from 1H data
            advancing = 0
            declining = 0
            for symbol, df in stocks_1h_data.items():
                if df is None or df.empty or len(df) < 2:
                    continue
                current_close = df["close"].iloc[-1]
                prev_close = df["close"].iloc[-2]
                if current_close > prev_close:
                    advancing += 1
                elif current_close < prev_close:
                    declining += 1

            # Fetch NIFTY 15m data for EMA check
            nifty_15m = await self.data_provider.fetch_ohlcv(
                NIFTY_SYMBOL, "15m", PERIODS_15M
            )
            if nifty_15m is None:
                nifty_15m = pd.DataFrame()

            return self.market_breadth_filter.is_market_healthy(
                advancing, declining, nifty_15m
            )
        except Exception as e:
            logger.error(f"Market breadth check failed: {e}")
            # On error, assume healthy to avoid suppressing signals
            return True

    def _run_stage3(
        self, stocks_15m_data: Dict[str, pd.DataFrame]
    ) -> Dict[str, "EntryTriggerResult"]:
        """Run Stage 3 entry trigger detection on all stocks.

        Skips stocks that fail detection gracefully.

        Args:
            stocks_15m_data: Dict mapping symbol to 15m DataFrame.

        Returns:
            Dict mapping symbol to its EntryTriggerResult (only triggered stocks).
        """
        from src.momentum.stage3_entry_trigger import EntryTriggerResult

        triggered: Dict[str, EntryTriggerResult] = {}

        for symbol, df in stocks_15m_data.items():
            try:
                result = self.stage3_trigger.detect(df)
                if result is not None:
                    triggered[symbol] = result
            except Exception as e:
                logger.debug(f"{symbol}: Stage 3 detection error — {e}")
                continue

        return triggered

    def _calculate_trade_levels(
        self,
        triggered: Dict[str, "EntryTriggerResult"],
        stocks_15m_data: Dict[str, pd.DataFrame],
    ) -> Dict[str, dict]:
        """Calculate trade levels for all triggered stocks.

        Uses the trigger candle data and ATR to compute entry, SL, targets.
        Discards signals with invalid risk-reward.

        Args:
            triggered: Dict of symbol -> EntryTriggerResult from Stage 3.
            stocks_15m_data: 15m data for EMA(20) trailing stop and ATR.

        Returns:
            Dict mapping symbol to a dict with 'trigger' and 'levels' keys.
        """
        from ta.volatility import AverageTrueRange
        from ta.trend import EMAIndicator

        results: Dict[str, dict] = {}

        for symbol, trigger_result in triggered.items():
            try:
                df = stocks_15m_data.get(symbol)
                if df is None or df.empty:
                    continue

                # Calculate ATR(14) on 15m data
                if len(df) < self.config.atr_period + 1:
                    continue

                atr_indicator = AverageTrueRange(
                    high=df["high"], low=df["low"], close=df["close"],
                    window=self.config.atr_period
                )
                atr_series = atr_indicator.average_true_range()
                atr_value = atr_series.iloc[-1]

                if pd.isna(atr_value) or atr_value <= 0:
                    continue

                # Calculate EMA(20) on 15m for trailing stop
                ema_indicator = EMAIndicator(
                    close=df["close"], window=self.config.ema_fast
                )
                ema_20 = ema_indicator.ema_indicator()
                ema_20_value = ema_20.iloc[-1]

                if pd.isna(ema_20_value):
                    continue

                # Get trigger candle low
                trigger_idx = trigger_result.trigger_candle_index
                if trigger_idx < 0 or trigger_idx >= len(df):
                    trigger_idx = len(df) - 1
                trigger_candle_low = df["low"].iloc[trigger_idx]

                # Calculate trade levels
                levels = self.trade_level_calculator.calculate(
                    entry_price=trigger_result.entry_price,
                    trigger_candle_low=trigger_candle_low,
                    atr_value=atr_value,
                    ema_20_value=ema_20_value,
                )

                if levels is not None:
                    results[symbol] = {
                        "trigger": trigger_result,
                        "levels": levels,
                    }

            except Exception as e:
                logger.debug(f"{symbol}: Trade level calculation error — {e}")
                continue

        return results

    async def _get_sector_scores(self) -> Dict[str, float]:
        """Fetch sector index data and compute sector scores vs NIFTY.

        Returns:
            Dict mapping sector name to its RS score vs NIFTY.
            Returns empty dict on failure.
        """
        try:
            from src.momentum.sector_analyzer import SECTOR_INDICES

            # Fetch NIFTY data for sector comparison
            nifty_data = await self.data_provider.fetch_ohlcv(
                NIFTY_SYMBOL, "1h", PERIODS_1H
            )
            if nifty_data is None or nifty_data.empty:
                return {}

            # Fetch sector index data
            sector_data = await self.data_provider.fetch_batch(
                SECTOR_INDICES, "1h", PERIODS_1H
            )
            if not sector_data:
                return {}

            return self.sector_analyzer.get_sector_scores(sector_data, nifty_data)

        except Exception as e:
            logger.error(f"Sector score calculation failed: {e}")
            return {}

    def _build_candidates(
        self,
        candidates_with_levels: Dict[str, dict],
        rs_ranked: List[tuple],
        stocks_1h_data: Dict[str, pd.DataFrame],
        sector_scores: Dict[str, float],
    ) -> List[CandidateSignal]:
        """Build CandidateSignal objects for the FinalRanker.

        Combines trigger results, trade levels, trend quality scores,
        RS scores, and sector boosts into CandidateSignal instances.

        Args:
            candidates_with_levels: Dict of symbol -> {trigger, levels}.
            rs_ranked: List of (symbol, rs_score) from Stage 2.
            stocks_1h_data: 1H data for trend quality score calculation.
            sector_scores: Sector RS scores from SectorAnalyzer.

        Returns:
            List of CandidateSignal ready for FinalRanker.
        """
        # Build RS lookup
        rs_lookup = {symbol: score for symbol, score in rs_ranked}

        candidates: List[CandidateSignal] = []

        for symbol, data in candidates_with_levels.items():
            trigger = data["trigger"]
            levels = data["levels"]

            # Get trend quality score from Stage 1
            trend_quality = 0.0
            df_1h = stocks_1h_data.get(symbol)
            if df_1h is not None:
                trend_quality = self.stage1_filter.calculate_trend_quality_score(df_1h)

            # Get sector boost
            sector_boost = self.sector_analyzer.get_stock_sector_boost(
                symbol, sector_scores
            )

            # Distance from breakout (0 since we just triggered)
            distance_from_breakout = 0.0

            candidates.append(
                CandidateSignal(
                    symbol=symbol,
                    relative_volume=trigger.relative_volume or 0.0,
                    breakout_strength=trigger.breakout_strength,
                    trend_quality_score=trend_quality,
                    distance_from_breakout=distance_from_breakout,
                    sector_boost=sector_boost,
                    setup_type=trigger.setup_type.value,
                    entry_price=levels.entry_price,
                    stop_loss=levels.stop_loss,
                    target_1=levels.target_1,
                    target_2=levels.target_2,
                    relative_strength=rs_lookup.get(symbol, 0.0),
                    timeframe="15m",
                )
            )

        return candidates

    def _build_momentum_signals(
        self,
        ranked_signals: List,
        rs_ranked: List[tuple],
        sector_scores: Dict[str, float],
        timestamp: datetime,
    ) -> List[MomentumSignal]:
        """Convert RankedSignal objects to MomentumSignal dataclass instances.

        Args:
            ranked_signals: Output from FinalRanker.rank().
            rs_ranked: RS scores for relative_strength field.
            sector_scores: Sector scores for sector_strength field.
            timestamp: Current IST timestamp for the signal.

        Returns:
            List of MomentumSignal instances.
        """
        rs_lookup = {symbol: score for symbol, score in rs_ranked}
        signals: List[MomentumSignal] = []

        for ranked in ranked_signals:
            try:
                # Get sector strength for this stock
                sector_strength = self.sector_analyzer.get_stock_sector_boost(
                    ranked.symbol, sector_scores
                )

                signal = MomentumSignal(
                    symbol=ranked.symbol,
                    setup_type=SetupType(ranked.setup_type),
                    entry_price=ranked.entry_price,
                    stop_loss=ranked.stop_loss,
                    target_1=ranked.target_1,
                    target_2=ranked.target_2,
                    relative_volume=ranked.relative_volume,
                    relative_strength=rs_lookup.get(ranked.symbol, 0.0),
                    sector_strength=sector_strength,
                    trend_quality_score=ranked.trend_quality_score,
                    rank_score=ranked.rank_score,
                    breakout_strength=ranked.breakout_strength,
                    distance_from_breakout=ranked.distance_from_breakout,
                    timeframe=ranked.timeframe,
                    timestamp=timestamp,
                    risk_pct=(ranked.entry_price - ranked.stop_loss)
                    / ranked.entry_price
                    * 100
                    if ranked.entry_price > 0
                    else 0.0,
                    trailing_stop=0.0,  # Set from trade levels if available
                )
                signals.append(signal)
            except Exception as e:
                logger.debug(
                    f"Failed to build MomentumSignal for {ranked.symbol}: {e}"
                )
                continue

        return signals

    def _send_alert(self, signal: MomentumSignal) -> None:
        """Send alert for a signal. Failure is logged but does not stop pipeline.

        Args:
            signal: MomentumSignal to send as Telegram alert.
        """
        try:
            self.alert_formatter.send(signal)
        except Exception as e:
            logger.error(f"Alert send failed for {signal.symbol}: {e}")

    def _log_cycle(self, result: ScanCycleResult) -> None:
        """Log scan cycle to database. Failure is non-critical.

        Args:
            result: The completed ScanCycleResult to persist.
        """
        try:
            self.scan_logger.log_cycle(result)
        except Exception as e:
            logger.error(f"Failed to log scan cycle: {e}")

    def _check_duration(self, duration_seconds: float) -> None:
        """Check cycle duration and log warnings/errors as appropriate.

        Args:
            duration_seconds: How long the cycle took in seconds.
        """
        if duration_seconds > self.config.warn_scan_duration_seconds:
            logger.error(
                "Scan cycle took %.1fs — exceeds ERROR threshold of %ds. "
                "Investigate performance bottleneck.",
                duration_seconds,
                self.config.warn_scan_duration_seconds,
            )
        elif duration_seconds > self.config.max_scan_duration_seconds:
            logger.warning(
                "Scan cycle took %.1fs — exceeds WARNING threshold of %ds.",
                duration_seconds,
                self.config.max_scan_duration_seconds,
            )
        else:
            logger.info("Scan cycle completed in %.1fs.", duration_seconds)

    def _build_result(
        self,
        timestamp: datetime,
        start_time: float,
        stage1_passed: int,
        stage2_ranked: int,
        stage3_triggered: int,
        signals_generated: List[MomentumSignal],
        signals_suppressed: int,
        market_breadth_healthy: bool,
        rejected_reasons: Dict[str, int],
    ) -> ScanCycleResult:
        """Build a ScanCycleResult with computed duration.

        Args:
            timestamp: Cycle start timestamp (IST).
            start_time: monotonic start time for duration calculation.
            stage1_passed: Number of stocks passing Stage 1.
            stage2_ranked: Number of stocks ranked in Stage 2.
            stage3_triggered: Number of stocks triggering in Stage 3.
            signals_generated: List of final MomentumSignal objects sent.
            signals_suppressed: Count of signals suppressed by dedup.
            market_breadth_healthy: Whether market breadth was healthy.
            rejected_reasons: Dict of rejection reason -> count.

        Returns:
            Fully populated ScanCycleResult.
        """
        duration = time.monotonic() - start_time

        return ScanCycleResult(
            timestamp=timestamp,
            duration_seconds=duration,
            stage1_passed=stage1_passed,
            stage2_ranked=stage2_ranked,
            stage3_triggered=stage3_triggered,
            signals_generated=signals_generated,
            signals_suppressed=signals_suppressed,
            market_breadth_healthy=market_breadth_healthy,
            rejected_reasons=rejected_reasons,
        )
