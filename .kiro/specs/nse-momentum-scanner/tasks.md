# Implementation Plan: NSE Momentum Scanner

## Overview

Implement a deterministic, rule-based momentum scanner for ~500 NSE stocks using a three-stage filtering pipeline (1H trend → relative strength ranking → 15m entry triggers). The scanner runs every 2 minutes during market hours, selects the top 5 momentum stocks, and delivers structured Telegram alerts. Built in Python using async patterns, reusing existing infrastructure (AlertService, MarketScheduler, IndicatorEngine).

## Tasks

- [x] 1. Set up project structure, data models, and configuration
  - [x] 1.1 Create momentum scanner package structure and data models
    - Create `src/momentum/` package with `__init__.py`
    - Create `src/momentum/models.py` with all dataclasses: `MomentumSignal`, `ScannerConfig`, `ScanCycleResult`, `AlertState`, `EODReport`, `SetupType` enum
    - Create `src/momentum/config_manager.py` with `ConfigManager` class that loads from `config/momentum_scanner.json`, validates ranges, and applies defaults
    - Create `config/momentum_scanner.json` with all default configuration values from the design
    - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5_

  - [x] 1.2 Create DataProvider abstract interface and mock implementation
    - Create `src/momentum/data_provider.py` with abstract `DataProvider` class defining `fetch_ohlcv`, `fetch_batch`, `connect`, `disconnect` methods
    - Create `src/momentum/providers/__init__.py` package
    - Create `src/momentum/providers/mock_provider.py` with `MockDataProvider` for testing that returns realistic OHLCV DataFrames
    - _Requirements: 1.1, 1.2, 1.5, 1.6_

  - [ ]* 1.3 Write unit tests for ConfigManager
    - Test loading valid config, missing file (defaults used), invalid values (warnings logged), partial config
    - _Requirements: 17.1, 17.3, 17.4, 17.5_

- [x] 2. Implement Stage 1 — Trend Filter
  - [x] 2.1 Implement Stage1TrendFilter class
    - Create `src/momentum/stage1_trend_filter.py`
    - Implement `filter()` method: evaluate EMA(200), EMA(20), EMA(50) alignment and EMA(200) slope
    - Implement `calculate_trend_quality_score()` returning 0-100 based on EMA alignment strength and slope magnitude
    - Use existing `IndicatorEngine` for EMA calculations where possible
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [ ]* 2.2 Write property test for Stage 1 bullish classification
    - **Property 4: Stage 1 Bullish Classification**
    - Generate random OHLCV 1H data, verify classification matches all three conditions (price > EMA200, EMA20 > EMA50, EMA200 slope > 0)
    - **Validates: Requirements 3.2**

  - [ ]* 2.3 Write property test for EMA slope formula
    - **Property 6: EMA Slope Formula Correctness**
    - Generate random price series with ≥205 data points, verify slope = (EMA200_current - EMA200_5_periods_ago) / 5
    - **Validates: Requirements 3.4**

- [x] 3. Implement Stage 2 — Relative Strength Filter
  - [x] 3.1 Implement Stage2RelativeStrength class
    - Create `src/momentum/stage2_relative_strength.py`
    - Implement `calculate_rs()` for single window: stock_pct_change - nifty_pct_change
    - Implement `rank()` method: compute weighted composite RS (intraday=0.5, 1day=0.3, 5day=0.2), sort descending
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [ ]* 3.2 Write property test for Relative Strength formula
    - **Property 7: Relative Strength Formula**
    - Generate random stock/NIFTY percentage changes, verify RS = stock_change - nifty_change for each window
    - **Validates: Requirements 4.2**

  - [ ]* 3.3 Write property test for RS ranking order
    - **Property 8: Relative Strength Ranking Order**
    - Generate random RS scores for multiple stocks, verify ordering by weighted composite with intraday weight > others
    - **Validates: Requirements 4.3**

- [x] 4. Implement Stage 3 — Entry Trigger Detection
  - [x] 4.1 Implement Stage3EntryTrigger class
    - Create `src/momentum/stage3_entry_trigger.py`
    - Implement `_check_pullback_continuation()`: price near EMA(20) + bullish candle + volume > 1.5x avg + breaks prev high
    - Implement `_check_compression_breakout()`: 3-6 tight candles + ATR contraction + volume expansion + strong breakout
    - Implement `_calculate_breakout_strength()`: composite 0-100 score from body/range, close/high, range expansion, volume, momentum
    - Implement `detect()` method returning `EntryTriggerResult` or None, assigning exactly one setup type
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [ ]* 4.2 Write property test for setup type mutual exclusivity
    - **Property 9: Setup Type Mutual Exclusivity**
    - Generate random 15m OHLCV data, verify at most one SetupType assigned per stock per cycle
    - **Validates: Requirements 5.4**

  - [ ]* 4.3 Write property test for breakout strength bounded [0, 100]
    - **Property 14: Breakout Strength Bounded [0, 100]**
    - Generate random candle data (any OHLCV combination), verify breakout_strength always in [0, 100]
    - **Validates: Requirements 7.1, 7.2**

- [x] 5. Checkpoint — Core pipeline stages complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement Volume and Breakout Calculations
  - [x] 6.1 Implement relative volume calculation in Stage3EntryTrigger
    - Add `_calculate_relative_volume()` method: current_volume / SMA(volume, 30)
    - Handle edge case: if SMA is zero or unavailable, exclude stock
    - Integrate relative volume into `EntryTriggerResult`
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

  - [ ]* 6.2 Write property test for relative volume formula
    - **Property 11: Relative Volume Formula**
    - Generate random volume series of length ≥30, verify RV = current_volume / SMA(volume, 30)
    - **Validates: Requirements 6.1**

  - [ ]* 6.3 Write property test for volume expansion classification
    - **Property 12: Volume Expansion Classification**
    - Generate random RV values, verify classification: RV ≥ 1.5 → expansion, RV < 1.5 → not expansion
    - **Validates: Requirements 6.2**

  - [ ]* 6.4 Write property test for higher RV ranks higher
    - **Property 13: Higher Relative Volume Ranks Higher**
    - Generate two stocks identical except RV, verify higher RV → higher rank score
    - **Validates: Requirements 6.3**

- [x] 7. Implement Sector Analysis and Market Breadth
  - [x] 7.1 Implement SectorAnalyzer class
    - Create `src/momentum/sector_analyzer.py`
    - Implement `get_sector_scores()`: calculate each sector index performance vs NIFTY
    - Implement `get_stock_sector_boost()`: return configurable boost for stocks in outperforming sectors
    - Include stock-to-sector mapping configuration
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

  - [x] 7.2 Implement MarketBreadthFilter class
    - Create `src/momentum/market_breadth_filter.py`
    - Implement `is_market_healthy()`: check advancing vs declining ratio AND NIFTY vs intraday EMA(20)
    - Log when signals are suppressed due to weak breadth
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

  - [ ]* 7.3 Write property test for market breadth suppression
    - **Property 17: Market Breadth Suppression**
    - Generate weak market state (declining > advancing by ratio AND NIFTY < EMA20), verify zero signals produced
    - **Validates: Requirements 9.3**

- [x] 8. Implement Trade Levels and Final Ranking
  - [x] 8.1 Implement trade level calculations
    - Create `src/momentum/trade_levels.py`
    - Implement entry price calculation: breakout candle high (COMPRESSION_BREAKOUT) or trigger candle high (PULLBACK_CONTINUATION)
    - Implement stop loss: min(candle_low, entry - 1.2 × ATR(14))
    - Implement Target 1 = Entry + 1R, Target 2 = Entry + 2R
    - Implement trailing stop using EMA(20) on 15m
    - Enforce minimum 1:2 risk-reward ratio (discard signals that violate)
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

  - [x] 8.2 Implement FinalRanker class
    - Create `src/momentum/final_ranker.py`
    - Implement `rank()`: normalize each component to 0-100, apply weights (RV=0.35, BS=0.25, TQ=0.20, Dist=0.10, Sector=0.10)
    - Implement distance-from-breakout inverse scoring (closer = higher score)
    - Select top min(N, 5) stocks from ranked list
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_

  - [ ]* 8.3 Write property test for trade levels calculation
    - **Property 18: Trade Levels Calculation**
    - Generate random entry/ATR/low values, verify SL = min(L, E - 1.2×A), T1 = E + Risk, T2 = E + 2×Risk
    - **Validates: Requirements 10.1, 10.2, 10.3, 10.4**

  - [ ]* 8.4 Write property test for minimum risk-reward ratio
    - **Property 19: Minimum Risk-Reward Ratio**
    - Generate random signals, verify (T1 - Entry) / (Entry - SL) ≥ 2.0 for all emitted signals
    - **Validates: Requirements 10.6**

  - [ ]* 8.5 Write property test for final ranking formula
    - **Property 20: Final Ranking Formula**
    - Generate random component scores in [0, 100], verify weighted sum = 0.35×RV + 0.25×BS + 0.20×TQ + 0.10×Dist + 0.10×Sector
    - **Validates: Requirements 11.1, 11.2**

  - [ ]* 8.6 Write property test for top 5 selection
    - **Property 22: Top 5 Selection**
    - Generate random ranked lists of N stocks, verify output contains min(N, 5) highest-ranked stocks
    - **Validates: Requirements 11.4, 11.5**

- [x] 9. Checkpoint — Scoring and ranking pipeline complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Implement Deduplication and Alert Throttling
  - [x] 10.1 Implement Deduplicator class
    - Create `src/momentum/deduplicator.py`
    - Implement `should_alert()`: check same setup type + cooldown period + daily limit
    - Implement `record_alert()`: update state cache with alert details
    - Implement `reset_daily()`: clear state at 09:15 IST
    - Implement `should_resend()`: allow resend on new breakout, new volume expansion, or new setup type
    - Enforce configurable max daily alerts (default: 20)
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6_

  - [ ]* 10.2 Write property test for deduplication suppression
    - **Property 25: Deduplication Suppression**
    - Generate alert sequences with same stock/setup within cooldown, verify duplicates suppressed
    - **Validates: Requirements 14.2, 14.4**

  - [ ]* 10.3 Write property test for resend on changed conditions
    - **Property 26: Resend on Changed Conditions**
    - Generate previously alerted stocks with new breakout/volume/setup, verify new alert sent
    - **Validates: Requirements 14.3**

  - [ ]* 10.4 Write property test for daily alert limit
    - **Property 27: Daily Alert Limit**
    - Generate alert sequences exceeding daily max, verify cap enforced (no more than 20)
    - **Validates: Requirements 14.6**

- [x] 11. Implement Alert Formatting and Telegram Delivery
  - [x] 11.1 Implement AlertFormatter class
    - Create `src/momentum/alert_formatter.py`
    - Implement `format()`: Markdown message with emoji indicators, all required fields (symbol, setup type, entry, SL, risk%, T1, T2, RV, RS, sector, trend score, rank score, timeframe, IST timestamp)
    - Implement `send()`: use existing `AlertService` from `src/notifications/alert_service.py`, log failure and continue on error
    - _Requirements: 12.1, 12.2, 12.3, 12.4_

  - [ ]* 11.2 Write unit tests for AlertFormatter
    - Verify Markdown structure, emoji presence, all 14 required fields present in formatted output
    - Test failure handling (AlertService error → log and continue)
    - _Requirements: 12.1, 12.3, 12.4_

- [x] 12. Implement Scan Scheduling and Orchestration
  - [x] 12.1 Implement ScanScheduler class
    - Create `src/momentum/scan_scheduler.py`
    - Implement `run()`: main async loop with 2-minute intervals during 09:15-15:30 IST
    - Implement `is_market_day()`: check weekday + NSE holiday calendar
    - Implement pre-market preparation at 09:00 IST (preload universe, prev day data, sector indices, NIFTY)
    - First scan at 09:30 IST (after first 15m candle completes)
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6_

  - [x] 12.2 Implement main scan pipeline orchestrator
    - Create `src/momentum/scanner.py` with `MomentumScanner` class
    - Wire all stages: DataProvider → Stage1 → Stage2 → Stage3 → FinalRanker → Deduplicator → AlertFormatter
    - Implement `run_cycle()`: execute one complete scan cycle, return `ScanCycleResult`
    - Apply MarketBreadthFilter before Stage 3 triggers
    - Handle partial failures gracefully (skip stocks with missing data)
    - Track and log cycle duration, warn if > 60s, error if > 90s
    - _Requirements: 1.3, 1.6, 16.1, 16.2, 16.3, 16.4, 18.1, 18.3_

  - [ ]* 12.3 Write property test for market hours enforcement
    - **Property 24: Market Hours Enforcement**
    - Generate timestamps outside 09:15-15:30 IST, weekends, holidays — verify no scan cycle executes
    - **Validates: Requirements 13.1, 13.6**

  - [ ]* 12.4 Write property test for determinism
    - **Property 28: Determinism**
    - Generate random OHLCV inputs, run pipeline twice with identical inputs, verify identical outputs
    - **Validates: Requirements 18.1, 18.3**

- [x] 13. Checkpoint — Full pipeline wired and running
  - Ensure all tests pass, ask the user if questions arise.

- [x] 14. Implement Logging, EOD Report, and Stock Universe Management
  - [x] 14.1 Implement ScanLogger class
    - Create `src/momentum/scan_logger.py`
    - Implement `log_cycle()`: store all indicators, scores, triggered/rejected setups, timestamps to SQLite
    - Implement `generate_eod_report()`: aggregate daily metrics into `EODReport`
    - Create database schema for scan logs
    - _Requirements: 15.1, 15.2, 15.3, 15.4_

  - [x] 14.2 Implement EOD report Telegram delivery
    - Add EOD report formatting to `AlertFormatter` (total scans, signals, top performers, setup breakdown)
    - Trigger at 15:30 IST via ScanScheduler
    - Send via existing AlertService
    - _Requirements: 15.4, 15.5_

  - [x] 14.3 Implement stock universe management
    - Create `src/momentum/universe_manager.py`
    - Load stock universe from config file (NIFTY 500 constituents)
    - Apply liquidity filter: exclude stocks below min daily traded value and min daily volume
    - Exclude penny stocks, suspended stocks, abnormal gap stocks
    - Refresh filter daily at 09:00 IST pre-market phase
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [ ]* 14.4 Write property test for liquidity filter exclusion
    - **Property 3: Liquidity Filter Exclusion**
    - Generate stocks with traded value below threshold or volume below minimum, verify exclusion from universe
    - **Validates: Requirements 2.2, 2.3, 2.4**

- [x] 15. Implement Broker API DataProvider (Concrete Implementation)
  - [x] 15.1 Implement at least one concrete DataProvider
    - Create `src/momentum/providers/kite_provider.py` (or Angel One / Fyers / Upstox based on user preference)
    - Implement `connect()`: authenticate with broker API using credentials from environment
    - Implement `fetch_ohlcv()`: fetch OHLCV for single symbol in specified timeframe
    - Implement `fetch_batch()`: concurrent async fetching for multiple symbols with batching (batch_size=50)
    - Implement `disconnect()`: clean up resources
    - Handle connection failures with exponential backoff retry
    - _Requirements: 1.1, 1.2, 1.5, 1.6, 16.2, 16.5_

  - [ ]* 15.2 Write unit tests for DataProvider implementation
    - Test authentication flow, error handling, retry logic, batch fetching
    - Mock broker API responses
    - _Requirements: 1.1, 1.6_

- [x] 16. Integration wiring and entry point
  - [x] 16.1 Create main entry point for momentum scanner
    - Create `src/momentum/main.py` with CLI entry point
    - Wire ConfigManager → DataProvider → MomentumScanner → ScanScheduler
    - Add graceful shutdown handling (SIGINT/SIGTERM)
    - Integrate with existing `src/main.py` or provide standalone execution
    - _Requirements: 13.1, 17.1, 18.1_

  - [ ]* 16.2 Write integration tests for full pipeline
    - Test full pipeline with MockDataProvider returning realistic NSE data
    - Verify end-to-end: data fetch → Stage 1 → Stage 2 → Stage 3 → ranking → dedup → alert format
    - Test multi-cycle deduplication across simulated trading day
    - _Requirements: 1.6, 18.1, 18.3_

- [x] 17. Final checkpoint — All components integrated and tested
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document using `hypothesis` library
- Unit tests validate specific examples and edge cases
- The scanner reuses existing infrastructure: `AlertService` (src/notifications/), `MarketScheduler` (src/scheduler/), `IndicatorEngine` (src/core/)
- All code is Python with async/await patterns for concurrent data fetching
- Configuration lives in `config/momentum_scanner.json`

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["1.3", "2.1", "3.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "3.2", "3.3", "4.1"] },
    { "id": 3, "tasks": ["4.2", "4.3", "6.1", "7.1", "7.2"] },
    { "id": 4, "tasks": ["6.2", "6.3", "6.4", "7.3", "8.1", "8.2"] },
    { "id": 5, "tasks": ["8.3", "8.4", "8.5", "8.6", "10.1"] },
    { "id": 6, "tasks": ["10.2", "10.3", "10.4", "11.1", "14.3"] },
    { "id": 7, "tasks": ["11.2", "12.1", "14.1", "14.4"] },
    { "id": 8, "tasks": ["12.2", "14.2", "15.1"] },
    { "id": 9, "tasks": ["12.3", "12.4", "15.2", "16.1"] },
    { "id": 10, "tasks": ["16.2"] }
  ]
}
```
