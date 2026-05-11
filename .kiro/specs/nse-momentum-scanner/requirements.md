# Requirements Document

## Introduction

A deterministic, rule-based momentum trend scanner for NSE stocks. The system continuously scans ~500 NSE stocks during market hours (09:15–15:30 IST) to identify the TOP 5 strongest momentum stocks likely starting or continuing an intraday trend. It uses a multi-stage filtering pipeline: Stage 1 filters for higher-timeframe trend on 1H candles, Stage 2 ranks by relative strength vs NIFTY, and Stage 3 detects entry triggers on 15m candles. Telegram alerts include entry, stop loss, targets, relative volume, relative strength, sector strength, trend quality, and ranking scores. The scanner is purely rule-based and deterministic — same inputs produce same outputs. No AI/LLM is used for signal generation or trading logic.

## Glossary

- **Scanner**: The core momentum scanning engine that evaluates stocks against deterministic rules in a multi-stage pipeline
- **Stock_Universe**: The configured set of ~500 NSE stocks with sufficient liquidity, loaded from configuration
- **Relative_Volume**: The ratio of current candle volume to the 30-period simple moving average of volume (current_volume / SMA(volume, 30))
- **Relative_Strength**: A stock's percentage price change compared to NIFTY's percentage change over the same period, measured across intraday, 1-day, and 5-day windows
- **Trend_Quality_Score**: A component score (0-100) measuring the quality of the higher-timeframe trend structure based on EMA alignment and slope
- **Momentum_Signal**: A structured output object containing stock symbol, setup type, entry, stop loss, targets, relative volume, relative strength, sector strength, trend score, rank score, timeframe, and timestamp
- **Setup_Type**: Classification of the detected momentum pattern — either PULLBACK_CONTINUATION or COMPRESSION_BREAKOUT
- **Confidence_Score**: The final composite ranking score (0-100) combining relative volume, breakout strength, trend quality, distance from breakout, and sector strength
- **ATR**: Average True Range (14-period) used for calculating stop loss and target levels
- **Scan_Cycle**: One complete iteration of the multi-stage pipeline producing ranked results
- **Alert_Formatter**: The component that formats Momentum_Signal data into structured Telegram messages
- **Breakout_Strength**: A composite measure of candle body size, close proximity to high, range expansion, volume, and momentum acceleration
- **Sector_Strength**: A measure of how strongly a stock's sector is outperforming NIFTY intraday
- **Market_Breadth**: The ratio of advancing to declining stocks and overall market health indicators
- **Data_Provider**: The broker API used for fetching NSE data (Zerodha Kite Connect, Angel One SmartAPI, Fyers API, or Upstox API)
- **Cooldown_Period**: The configurable time window during which duplicate alerts for the same stock are suppressed

## Requirements

### Requirement 1: Data Source and Acquisition

**User Story:** As a trader, I want the scanner to fetch reliable intraday NSE data from a broker API, so that momentum calculations use accurate, near-live market data.

#### Acceptance Criteria

1. THE Scanner SHALL use a broker API (Zerodha Kite Connect, Angel One SmartAPI, Fyers API, or Upstox API) as the Data_Provider for all market data
2. THE Scanner SHALL fetch OHLCV data in three timeframes: 15-minute candles for entry triggers, 1-hour candles for trend filtering, and daily candles for context
3. WHEN a Scan_Cycle begins, THE Scanner SHALL use only the latest COMPLETED candle for all calculations
4. THE Scanner SHALL fetch NIFTY 50 index data in matching timeframes for Relative_Strength and Market_Breadth calculations
5. THE Scanner SHALL support websocket streaming for near-live data where the Data_Provider supports it
6. IF the Data_Provider returns no data for a stock, THEN THE Scanner SHALL skip that stock and continue scanning remaining stocks without interruption
7. THE Scanner SHALL preload the following data at 09:00 IST before market open: stock universe, previous day data, sector indices, and NIFTY data

### Requirement 2: Stock Universe Management

**User Story:** As a trader, I want the scanner to maintain a clean universe of liquid stocks, so that signals come only from tradeable instruments.

#### Acceptance Criteria

1. THE Scanner SHALL load the stock universe from a configuration file containing NIFTY 500 constituents or equivalent liquid NSE stocks
2. THE Scanner SHALL exclude stocks where the average daily traded value is below a configurable threshold
3. THE Scanner SHALL exclude stocks where the average daily volume is below a configurable minimum volume threshold
4. THE Scanner SHALL exclude penny stocks, suspended stocks, and stocks with abnormal opening gaps (configurable gap percentage)
5. THE Scanner SHALL refresh the liquidity filter daily during the pre-market preparation phase at 09:00 IST

### Requirement 3: Stage 1 — Trend Filter (1H Timeframe)

**User Story:** As a trader, I want the scanner to first filter for stocks in a higher-timeframe uptrend, so that entry triggers align with the dominant trend direction.

#### Acceptance Criteria

1. THE Scanner SHALL evaluate Stage 1 using 1-hour timeframe candles
2. THE Scanner SHALL classify a stock as bullish ONLY when ALL of the following conditions are true: price is above EMA(200), EMA(20) is above EMA(50), and EMA(200) slope is positive
3. WHEN a stock fails the Stage 1 trend filter, THE Scanner SHALL exclude it from Stage 2 and Stage 3 processing
4. THE Scanner SHALL calculate EMA(200) slope as the difference between current EMA(200) and EMA(200) from 5 periods ago, divided by 5
5. THE Scanner SHALL pass all Stage 1 qualifying stocks to Stage 2 for relative strength ranking

### Requirement 4: Stage 2 — Relative Strength Filter

**User Story:** As a trader, I want to identify stocks outperforming NIFTY across multiple timeframes, so that I focus on names showing institutional accumulation.

#### Acceptance Criteria

1. THE Scanner SHALL calculate Relative_Strength across three windows: intraday performance vs NIFTY, 1-day outperformance vs NIFTY, and 5-day outperformance vs NIFTY
2. THE Scanner SHALL calculate each Relative_Strength metric as: stock percentage change minus NIFTY percentage change over the same period
3. THE Scanner SHALL rank stocks by a weighted composite of the three Relative_Strength windows, with intraday weighted highest
4. WHEN a stock shows positive Relative_Strength across all three windows, THE Scanner SHALL classify it as having strong relative strength
5. THE Scanner SHALL pass all Stage 2 ranked stocks to Stage 3 for entry trigger detection

### Requirement 5: Stage 3 — Entry Trigger Detection (15m Timeframe)

**User Story:** As a trader, I want the scanner to detect specific entry setups on the 15-minute chart, so that I receive actionable signals with clear entry points.

#### Acceptance Criteria

1. THE Scanner SHALL evaluate Stage 3 entry triggers using 15-minute timeframe candles
2. WHEN a stock's price pulls back near EMA(20) AND a bullish candle forms with a strong close AND current volume is greater than 1.5 times average volume AND price breaks the previous candle high, THE Scanner SHALL classify the setup as PULLBACK_CONTINUATION
3. WHEN a stock shows 3 to 6 tight-range candles AND ATR contraction is visible AND a sudden volume expansion occurs (volume greater than 1.5 times average) AND a strong breakout candle closes near its high, THE Scanner SHALL classify the setup as COMPRESSION_BREAKOUT
4. THE Scanner SHALL assign exactly one Setup_Type per stock per Scan_Cycle
5. WHEN no entry trigger is detected for a stock, THE Scanner SHALL exclude it from the final ranking

### Requirement 6: Relative Volume Calculation

**User Story:** As a trader, I want to see volume expansion relative to average, so that I can identify unusual buying interest early.

#### Acceptance Criteria

1. THE Scanner SHALL calculate Relative_Volume as the ratio of current candle volume to the 30-period simple moving average of volume
2. WHEN Relative_Volume is greater than or equal to 1.5, THE Scanner SHALL classify the stock as having volume expansion
3. THE Scanner SHALL prioritize stocks with higher Relative_Volume in the final ranking
4. IF the 30-period volume average is zero or unavailable, THEN THE Scanner SHALL exclude the stock from the current Scan_Cycle

### Requirement 7: Breakout Strength Calculation

**User Story:** As a trader, I want a measure of breakout quality, so that I can distinguish strong breakouts from weak ones.

#### Acceptance Criteria

1. THE Scanner SHALL calculate Breakout_Strength as a composite of: candle body size relative to total range, close proximity to candle high, range expansion compared to previous candles, breakout candle volume relative to average, and momentum acceleration (current candle range vs previous candle range)
2. THE Scanner SHALL normalize Breakout_Strength to a 0-100 scale
3. WHEN Breakout_Strength is below a configurable minimum threshold, THE Scanner SHALL exclude the stock from the final ranking

### Requirement 8: Sector Strength Analysis

**User Story:** As a trader, I want sector-level analysis, so that stocks in strong sectors receive a ranking boost.

#### Acceptance Criteria

1. THE Scanner SHALL track sector indices (BANKNIFTY, NIFTY IT, NIFTY PHARMA, and other major sector indices) intraday performance vs NIFTY
2. THE Scanner SHALL identify the strongest sectors of the day based on intraday outperformance vs NIFTY
3. WHEN a stock belongs to a sector that is outperforming NIFTY, THE Scanner SHALL apply a configurable ranking boost to that stock's final score
4. THE Scanner SHALL include Sector_Strength as a component in the final ranking formula

### Requirement 9: Market Breadth Filter

**User Story:** As a trader, I want the scanner to consider overall market health, so that aggressive long signals are suppressed in weak markets.

#### Acceptance Criteria

1. THE Scanner SHALL track market breadth by counting advancing stocks vs declining stocks in the NIFTY 500 universe
2. THE Scanner SHALL track whether NIFTY is above or below its intraday EMA(20)
3. WHEN overall market breadth is weak (declining stocks exceed advancing stocks by a configurable ratio) AND NIFTY is below its intraday EMA, THE Scanner SHALL suppress new long signals
4. THE Scanner SHALL log when signals are suppressed due to weak market breadth

### Requirement 10: Entry, Stop Loss, and Target Calculation

**User Story:** As a trader, I want calculated entry, stop loss, and target levels based on ATR, so that I can execute trades with defined risk and reward.

#### Acceptance Criteria

1. THE Scanner SHALL set the Entry price as the breakout candle high (for COMPRESSION_BREAKOUT) or the trigger candle high (for PULLBACK_CONTINUATION)
2. THE Scanner SHALL calculate Stop Loss as the safer of: trigger/breakout candle low, OR Entry price minus 1.2 multiplied by ATR(14)
3. THE Scanner SHALL calculate Target 1 as Entry price plus 1 times the risk amount (1R)
4. THE Scanner SHALL calculate Target 2 as Entry price plus 2 times the risk amount (2R)
5. THE Scanner SHALL include a trailing stop recommendation using EMA(20) on the 15-minute timeframe
6. THE Scanner SHALL ensure a minimum risk-reward ratio of 1:2 for all signals

### Requirement 11: Final Ranking and Top 5 Selection

**User Story:** As a trader, I want only the top 5 strongest momentum stocks per scan, so that I focus on the best opportunities without noise.

#### Acceptance Criteria

1. THE Scanner SHALL calculate the final ranking score using the formula: (Relative_Volume contribution * 0.35) + (Breakout_Strength contribution * 0.25) + (Trend_Quality_Score contribution * 0.20) + (Distance_From_Breakout contribution * 0.10) + (Sector_Strength contribution * 0.10)
2. THE Scanner SHALL normalize each component to a 0-100 scale before applying weights
3. THE Scanner SHALL calculate Distance_From_Breakout as an inverse score — stocks closer to the breakout level rank higher than extended stocks
4. WHEN a Scan_Cycle completes, THE Scanner SHALL select the top 5 stocks by final ranking score
5. IF fewer than 5 stocks qualify through all three stages, THEN THE Scanner SHALL output only the qualifying stocks without padding

### Requirement 12: Telegram Alert Formatting and Delivery

**User Story:** As a trader, I want structured Telegram alerts with all signal details, so that I can act on signals quickly from my phone.

#### Acceptance Criteria

1. WHEN the Scanner produces a TOP 5 list, THE Alert_Formatter SHALL send one Telegram message per stock containing: stock symbol, setup type, entry price, stop loss, risk percentage, target 1, target 2, relative volume (1 decimal), relative strength score, sector strength, trend quality score, final rank score, timeframe, and timestamp in IST
2. THE Alert_Formatter SHALL use the existing AlertService module to send messages via Telegram
3. THE Alert_Formatter SHALL format messages using Markdown with emoji indicators for signal quality
4. IF the AlertService fails to send a message, THEN THE Alert_Formatter SHALL log the failure and continue sending remaining alerts without retry
5. WHERE chart snapshot capability is available, THE Alert_Formatter SHALL include a chart image with the alert message

### Requirement 13: Scan Scheduling and Market Hours

**User Story:** As a trader, I want the scanner to run automatically during market hours at frequent intervals, so that I receive timely signals for early trend detection.

#### Acceptance Criteria

1. THE Scanner SHALL execute Scan_Cycles only between 09:15 IST and 15:30 IST on weekdays (Monday through Friday)
2. THE Scanner SHALL execute a Scan_Cycle every 2 minutes during market hours
3. THE Scanner SHALL use only the latest completed candle at each scan time (e.g., at 10:17, use the completed 10:15 candle)
4. THE Scanner SHALL perform pre-market preparation at 09:00 IST: preload stock universe, previous day data, sector indices, and NIFTY data
5. THE Scanner SHALL wait for the first completed 15-minute candle (09:30 IST) before executing the first Scan_Cycle
6. THE Scanner SHALL skip execution on NSE market holidays

### Requirement 14: Deduplication and Alert Throttling

**User Story:** As a trader, I want to avoid receiving repeated alerts for the same stock, so that my Telegram is not flooded with noise.

#### Acceptance Criteria

1. THE Scanner SHALL maintain a state cache of alerted stock symbols with their setup details and scores
2. WHEN a stock has already been alerted in the current trading day with the same Setup_Type, THE Scanner SHALL suppress the duplicate alert
3. THE Scanner SHALL resend an alert for a previously alerted stock ONLY when a new breakout occurs, a new volume expansion event is detected, or a new setup type forms
4. THE Scanner SHALL enforce a configurable Cooldown_Period between alerts for the same stock
5. THE Scanner SHALL reset the state cache at 09:15 IST each trading day
6. THE Scanner SHALL limit total alerts per day to a configurable maximum (default: 20 unique stocks)

### Requirement 15: Logging and Trade Journal

**User Story:** As a trader, I want all scans and signals logged with full detail, so that I can review performance and refine the system.

#### Acceptance Criteria

1. THE Scanner SHALL log every Scan_Cycle with: all indicator values, ranking scores, triggered setups, rejected setups (with rejection reason), and timestamps
2. THE Scanner SHALL store scan logs in a database (SQLite or PostgreSQL)
3. THE Scanner SHALL maintain a trade journal tracking: hit rate, average risk-reward achieved, setup-wise performance, sector-wise performance, best-performing time windows, and best-performing setup type
4. THE Scanner SHALL generate an end-of-day report automatically at 15:30 IST containing: total scans executed, total signals generated, top performers, and setup-type breakdown
5. THE Scanner SHALL send the end-of-day report via Telegram

### Requirement 16: Scan Performance

**User Story:** As a trader, I want the scanner to complete each cycle quickly, so that signals are timely and actionable.

#### Acceptance Criteria

1. THE Scanner SHALL complete one full Scan_Cycle within 60 seconds for the full stock universe
2. THE Scanner SHALL use async processing and batching for data fetching to maximize throughput
3. THE Scanner SHALL log the duration of each Scan_Cycle for performance monitoring
4. IF a Scan_Cycle exceeds 90 seconds, THEN THE Scanner SHALL log a warning identifying the bottleneck phase (fetch, calculate, rank, or alert)
5. THE Scanner SHALL support multiprocessing for indicator calculations when the stock universe exceeds 300 stocks

### Requirement 17: Configuration Management

**User Story:** As a trader, I want all thresholds and parameters configurable from a file, so that I can tune the scanner without code changes.

#### Acceptance Criteria

1. THE Scanner SHALL load all configurable parameters from a JSON configuration file
2. THE Scanner SHALL support configuration of: EMA periods, ATR multiplier, volume multiplier thresholds, cooldown period, scan interval, minimum liquidity thresholds, ranking weights, maximum alerts per day, and gap percentage threshold
3. THE Scanner SHALL validate configuration values on startup and log warnings for out-of-range values
4. THE Scanner SHALL use sensible defaults when configuration values are missing
5. IF the configuration file is missing or unreadable, THEN THE Scanner SHALL start with default values and log a warning

### Requirement 18: AI Usage Boundary

**User Story:** As a trader, I want clear separation between rule-based scanning and optional AI features, so that signal generation remains deterministic.

#### Acceptance Criteria

1. THE Scanner SHALL generate all trade signals, entries, exits, and rankings using deterministic rule-based logic only
2. THE Scanner SHALL allow AI/LLM usage ONLY for: post-market summary generation, trade journal commentary, Telegram message formatting enhancements, and analytics commentary
3. THE Scanner SHALL produce identical outputs for identical inputs regardless of whether AI features are enabled or disabled
4. IF AI features are disabled in configuration, THEN THE Scanner SHALL continue operating with full signal generation capability
