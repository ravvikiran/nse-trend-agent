# NSE Trend Scanner Agent - System Validation Document

**Version:** 3.0  
**Date:** 2026-04-15  
**Purpose:** Comprehensive system documentation for AI validation and review

---

## 1. Executive Overview

The **NSE Trend Scanner Agent v3.0** is an **Agentic AI** automated trading signal detection system that monitors ~500 NSE (National Stock Exchange of India) stocks during market hours and generates trading signals through multiple strategies:

1. **Trend Detection Strategy** - Identifies EMA alignment + volume confirmation signals
2. **VERC Strategy** - Volume Expansion Range Compression (accumulation detection)
3. **MTF Strategy** - Multi-timeframe confirmation (1D + 1H + 15m)
4. **Agentic AI (v3.0)** - Autonomous decision-making with LLM-powered market analysis
5. **AI Reasoning** - Multi-provider LLM integration with provider failover

The system includes:
- **Agentic AI Controller** - Makes autonomous decisions (SCAN/WAIT/ADJUST) based on LLM analysis
- **Trade Journal** - Tracks every signal with outcomes
- **Performance Tracker** - Calculates SIQ (Signal Intelligence Quotient)
- **Auto-Optimization** - Adjusts strategy weights based on historical performance
- **Telegram Alerts** - Real-time notifications with entry/SL/targets

---

## 2. Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Language | Python 3.11+ | Core application |
| Data Source | Yahoo Finance (yfinance) | Real-time OHLCV data |
| Notifications | Telegram Bot API | Alerts and bot commands |
| AI Providers | OpenAI, Anthropic, Google Gemini, Groq | Stock analysis + Agent decisions |
| Technical Indicators | ta library | EMA, RSI, ATR calculations |
| Scheduling | APScheduler | Market hours scheduling |
| Data Storage | JSON files | Signal history, trade journal |

---

## 3. Directory Structure

```
nse-trend-agent/
├── config/
│   ├── settings.json          # Scanner configuration
│   ├── settings.example.json  # Example settings template
│   └── stocks.json          # Stock list (~750 NSE symbols)
├── data/
│   ├── memory_all_signals.json
│   ├── trade_journal.json
│   ├── signals_active.json
│   ├── signals_history.json
│   ├── performance_metrics.json
│   ├── market_context.json
│   └── ...
├── src/
│   ├── main.py              # Entry point and scanner orchestration
│   ├── agent_controller.py # Agentic AI - autonomous decision maker (v3.0)
│   ├── data_fetcher.py      # Yahoo Finance data fetching
│   ├── indicator_engine.py  # EMA, RSI, ATR calculations
│   ├── trend_detector.py   # Trend strategy (EMA alignment)
│   ├── volume_compression.py # VERC strategy
│   ├── mtf_strategy.py     # Multi-timeframe strategy
│   ├── reasoning_engine.py  # Combined signal scoring
│   ├── ai_stock_analyzer.py # Multi-provider LLM
│   ├── alert_service.py    # Telegram notifications
│   ├── market_scheduler.py # Market hours scheduling
│   ├── signal_memory.py    # Signal deduplication
│   ├── signal_tracker.py   # Active signal tracking
│   ├── history_manager.py # History persistence (v2.0 - includes PerformanceAnalyzer, PositionManager, MultiTimeframeValidator)
│   ├── performance_tracker.py # SIQ metrics
│   ├── notification_manager.py # Outcome notifications
│   ├── trade_journal.py  # Trade logging
│   ├── trade_validator.py  # Trade setup validation
│   ├── strategy_optimizer.py # Performance optimization
│   ├── ai_learning_layer.py # AI pattern analysis
│   ├── factor_analyzer.py   # Factor-level learning (v2.0)
│   ├── market_context.py    # Market context engine (v2.0 - enhanced ATR-based detection, volatility regimes)
│   ├── signal_scorer.py   # Signal scoring utilities
│   ├── consolidation_detector.py # Consolidation detection
│   └── scheduler/
│       └── scanner_scheduler.py
├── logs/
│   └── scanner.log
├── docs/
│   ├── PRD.md
│   └── PRD-Reasoning-Learning.md
├── requirements.txt
└── README.md
```

---

## 4. Core Components

### 4.1 Data Fetcher (`src/data_fetcher.py`)

**Purpose:** Fetches OHLCV data from Yahoo Finance

**Methods:**
- `fetch Stock Data(ticker, period="1y", interval="1d")` - Single stock data
- `fetch_multiple_stocks(stocks)` - Batch fetching with concurrency
- `fetch_multiple_stocks_multi_timeframe(stocks)` - 1D + 1H + 15m data for MTF

**Key Features:**
- Handles API rate limiting
- Caches data to prevent duplicate fetches
- Returns pandas DataFrames with columns: open, high, low, close, volume

### 4.2 Indicator Engine (`src/indicator_engine.py`)

**Purpose:** Calculates technical indicators

**Indicators Calculated:**
| Indicator | Period | Purpose |
|-----------|--------|---------|
| EMA | 20, 50, 100, 200 | Trend direction |
| Volume MA | 5, 20, 30 | Volume confirmation |
| RSI | 14 | Momentum (overbought/oversold) |
| ATR | 14 | Volatility (stop loss) |
| MACD | 12, 26, 9 | Momentum confirmation |
| 20-day High/Low | 20 | Breakout detection |

**Key Methods:**
- `calculate_indicators(df)` - Add all indicators to DataFrame
- `get_latest_indicators(df)` - Extract latest values
- `check_ema_alignment(indicators)` - EMA20 > EMA50 > EMA100 > EMA200
- `check_volume_confirmation(indicators)` - Volume > Volume MA30
- `check_trend_start(indicators)` - Fresh EMA crossover
- `check_price_breakout(indicators)` - Above 20-day high
- `check_volume_ratio(indicators, min_ratio=1.5)` - Volume spike
- `check_rsi_zone(indicators)` - Ideal (50-65), overbought (>75), weak (<45)

### 4.3 Trend Detector (`src/trend_detector.py`)

**Purpose:** Detects potential uptrend starts based on EMA alignment + volume

**PRD v2.0 Scoring System:**

| Factor | Score | Description |
|--------|-------|-------------|
| EMA Alignment | +3 | EMA20 > EMA50 > EMA100 > EMA200 |
| Fresh Crossover | +2 | EMA20 crosses above EMA50 (prev <=, curr >) |
| Price Breakout | +2 | Close > 20-day high |
| Volume Spike | +2 | Volume >= 1.5x average |
| RSI Ideal Zone | +1 | RSI in 50-65 range |
| RSI Overbought | -1 | RSI > 75 (penalty) |

**Signal Threshold:** Score >= 6/10

**Key Classes:**
- `TrendSignal` - Signal data class with ticker, timestamp, indicators, score_breakdown
- `ScanResult` - Contains scan_a, scan_b, and intersection signals

### 4.4 VERC Strategy (`src/volume_compression.py`)

**Purpose:** Volume Expansion Range Compression - detects accumulation before breakout

**Detection Rules:**

1. **Range Compression:**
   - (Highest High - Lowest Low) / Current Price < 5%
   - OR ATR(14) is at local minimum (last 30 candles)

2. **Volume Expansion:**
   - Volume MA(5) > Volume MA(20)
   - OR Relative Volume > 1.3x

3. **Breakout Confirmation:**
   - Close > Highest High of compression range
   - OR Volume > Volume MA30 on breakout

4. **Trend Alignment:**
   - Price > EMA50 (medium-term trend)

**Confidence Scoring:**

| Factor | Score | Description |
|--------|-------|-------------|
| Range Compression | +3 | Price range < 5% |
| Volume Expansion | +2 | Volume MA(5) > MA(20) |
| Breakout Volume | +2 | Rel. Volume > 1.5x |
| Index Trend Alignment | +2 | Price > EMA50 |
| Relative Strength | +1 | Range very tight < 3% |

**Signal Threshold:** Score >= 7/10

**Entry Parameters:**
- Entry: Compression High + 0.5% buffer
- Stop Loss: Compression Low (base of range)
- Target 1: High + Range Height × 1
- Target 2: High + Range Height × 2

### 4.5 MTF Strategy (`src/mtf_strategy.py`)

**Purpose:** Multi-timeframe confirmation for stronger signals

**Timeframe Analysis:**

| Timeframe | Purpose | Key Analysis |
|----------|---------|-------------|
| 1D (Daily) | Trend Identification | Price vs EMA200 |
| 1H (Hourly) | Market Structure | Higher Highs/Lower Lows |
| 15m | Entry Trigger | Breakout candle confirmation |

**Validation Steps:**

1. **Trend (1D):** Price > EMA200 = BULLISH
2. **Structure (1H):** Higher Highs + Higher Lows
3. **EMA Alignment (1H):** EMA20 > EMA50 > EMA100 > EMA200
4. **Pullback (1H):** Price at EMA50/EMA100 (within 2%)
5. **Volume (15m):** Volume > MA30
6. **Breakout (15m):** Candle closes above resistance (not wick only)

**Rejection Rules:**
- EMAs flat or tangled = No trade
- Volume below average = No trade
- No clear market structure = No trade
- Wick-only breakout = No trade
- Trade against trend = Rejected

**Confidence Score:** 0-10 based on EMA score + volume + structure + breakout + pullback

### 4.6 Unified Ranking System (`src/main.py`)

**Purpose:** Combines all strategies into ranked signals

**Rank Score Formula (PRD v2.0 - Updated):**

```
base_rank_score = (strategy_score × 0.6) + (volume_score × 0.2) + (breakout_strength × 0.2)
```

Where:
- `strategy_score` = Trend score or VERC confidence score (0-10)
- `volume_score` = min(volume_ratio / 3.0, 1.0) × 10
- `breakout_strength` = % above 20-day high × 10

**Key Principle:** Score is PURE - no mixing with strategy weights. Strategy weights are used only for sorting/ranking, not scoring.

**Sorting Formula:**
```
final_ranking = sorted(signals, key=(strategy_weight, rank_score), reverse=True)
```

**Signal Selection:**
- Max 5 signals per scan
- TREND signals take priority via strategy_weight
- Deduplication via Signal Memory

### 4.7 Factor-Level Learning System (`src/factor_analyzer.py`)

**Purpose:** Analyzes trade journal at granular level to track performance per factor

**Tracked Factors:**

| Factor | Buckets | Purpose |
|--------|---------|---------|
| Volume Ratio | 0.5-1.0, 1.0-1.5, 1.5-2.0, 2.0-2.5, 2.5+ | Identify best volume ranges |
| RSI | 0-40, 40-45, 45-50, 50-55, 55-60, 60-65, 65-70, 70+ | Find optimal RSI zones |
| Breakout Strength | 0-2%, 2-5%, 5%+ | Validate breakout quality |
| Quality Grade | A, B, C | Track quality performance |
| Market Context | BULLISH, SIDEWAYS, BEARISH | Context-aware analysis |
| Entry Type | BREAKOUT, PULLBACK | Strategy-specific insights |

**Output:** `data/factor_insights.json`

**Key Methods:**
- `analyze_trade()` - Updates stats for each completed trade
- `batch_analyze()` - Analyzes multiple trades
- `get_optimization_recommendations()` - Generates filter recommendations
- `get_underperforming_factors()` - Identifies weak areas

### 4.8 Market Context Engine (`src/market_context.py`)

**Purpose:** Detects NIFTY trend for context-aware filtering with ATR-based detection, structure analysis, and regime classification.

**Enhanced Context Detection (v2.0):**

| Context | Condition |
|---------|-----------|
| STRONG_BULLISH | Close > 20-day high × 1.01 AND > EMA50 + 1.5×ATR |
| BULLISH | Close > EMA50 + 1.5×ATR |
| SIDEWAYS | Within ATR bounds, low persistence, or volatility regime = LOW |
| BEARISH | Close < EMA50 - 1.5×ATR |
| STRONG_BEARISH | Close < 20-day low × 0.99 AND < EMA50 - 1.5×ATR |

**Volatility Regime Classification:**

| Regime | Condition |
|--------|-----------|
| LOW | ATR ratio < 0.5× average |
| NORMAL | 0.5× to 1.5× average |
| HIGH | ATR ratio > 1.5× average |

**Context Flip Detection:**
- Detects whipsaw (context flip < 3 periods)
- Defaults to SIDEWAYS during flip periods

**Context Persistence:**
- Tracks consecutive periods with same context
- Score boost (+10%) when persistence >= 5

**Strategy-Aware Rules:**

| Strategy | BULLISH | SIDEWAYS | BEARISH |
|----------|--------|----------|---------|
| TREND | Full scoring + boost | Reject | -2 penalty |
| VERC | Full scoring | Full scoring | Full scoring |
| SHORT | -2 penalty | -0.5 reduction | +1 boost |

**High Volatility:**
- Score reduced by 40% when volatility_regime = HIGH

**Output:** `data/market_context.json`

**Key Methods:**
- `detect_context()` - ATR-based detection with structure analysis
- `apply_context_rules()` - Context-aware scoring adjustments
- `get_context_stats()` - Returns persistence, volatility, recent flips
- `get_nifty_indicators()` - Returns EMA, ATR, volatility metrics

### 4.9 Adaptive Thresholds (`src/strategy_optimizer.py`)

**Purpose:** Dynamic filter adjustments based on performance

**Filter Bounds:**

| Filter | Floor | Cap | Default |
|--------|-------|-----|---------|
| volume_ratio_min | 1.5 | 2.5 | 1.5 |
| rsi_max | 50 | 70 | 65 |
| breakout_strength_min | 0.0 | 5% | 0.0 |
| atr_min | 0.1 | - | 0.5 |

**Update Rules:**
- Too many false breakouts → volume_ratio_min += 0.2
- Late entries/overbought → rsi_max -= 5
- Weak breakouts → breakout_strength_min += 1%

**Cooldown:** Updates restricted to once per day

### 4.9.1 PerformanceAnalyzer (`src/history_manager.py`)

**Purpose:** Analyzes historical signal performance to learn and improve. Tracks win rate, returns, best parameters per setup.

**Key Methods:**
- `analyze_all_setups()` - Returns performance metrics per setup configuration
- `generate_weight_adjustments()` - Auto-adjusts weights based on performance (>60% boost, <40% disable)

**Metrics Calculated:**
| Metric | Description |
|--------|-------------|
| win_rate | (Wins / Total) × 100 |
| avg_return_pct | Mean return % |
| best_return_pct | Maximum return |
| worst_return_pct | Minimum return |
| avg_rr | Average risk-reward |
| max_drawdown_pct | Peak-to-trough decline |
| profit_factor | Gross profit / Gross loss |

**Constraints:**
- Minimum 10 trades required for reliable stats

### 4.9.2 PositionManager (`src/history_manager.py`)

**Purpose:** Manages open positions with trailing SL, partial exits, and close on opposite signal.

**Features:**
- Opening positions from signals
- Trailing stop calculation (1% default)
- Partial exits at T1 (50%), T2 (75%)
- Close on opposite signal detection

**Key Methods:**
- `open_position()` - Create position from signal
- `update_position()` - Check exit conditions
- `close_on_opposite_signal()` - Close when reverse signal detected

### 4.9.3 MultiTimeframeValidator (`src/history_manager.py`)

**Purpose:** Validates signals across multiple timeframes (Daily trend, 1H structure, 15m entry).

**Validation Rules:**
| Timeframe | Check | Action |
|-----------|-------|--------|
| Daily | Trend vs signal direction | Opposite = REJECT |
| 1H | Structure (RANGE_BOUND) | Reduce confidence 30% |
| 15m | Volatility (EXTREME) | Reduce confidence 20% |

**Returns:**
- `valid` (bool)
- `confidence` (0.0-1.0)
- `filters_triggered` (list)
- `recommendation` (APPROVE/CAUTION/REJECT)

### 4.10 No-Trade Zone Filter (`src/main.py`)

**Purpose:** Reject signals with poor quality indicators

**Rejection Conditions:**

| Condition | Action |
|-----------|--------|
| ATR < atr_min | Reject (dead stock) |
| wick_to_body_ratio > 1.0 | Reject (choppy candle) |
| NIFTY SIDEWAYS + weak TREND | Reject |

**Key Logic:** VERC signals allowed in all market conditions, including sideways.

### 4.11 Trade Quality Grading (`src/trade_journal.py`)

**Purpose:** Classify signals by quality level

| Grade | Criteria |
|-------|----------|
| A | score ≥ 8 AND volume_ratio ≥ 1.8 AND breakout ≥ 3% |
| B | score 6-7 |
| C | score < 6 |

**Usage:**
- Stored in trade journal for analysis
- Win rate tracked per quality grade
- Quality distribution informs filter adjustments

---

## 5. Learning & Feedback System

### 5.1 Trade Journal (`src/trade_journal.py`)

**Purpose:** Logs EVERY signal with complete trade data

**Tracked Fields (Enhanced):**
- trade_id, symbol, strategy, entry, stop_loss, targets
- outcome: WIN / LOSS / OPEN / TIMEOUT
- rr_achieved, max_drawdown
- volume_ratio, rsi, trend_score, verc_score, rank_score
- **quality** (A/B/C) - Signal quality grade
- **market_context** (BULLISH/SIDEWAYS/BEARISH) - Market condition at entry
- **entry_type** (BREAKOUT/PULLBACK) - Entry strategy
- **candle_quality** (NORMAL/STRONG/WEAK) - Candle formation quality
- **breakout_strength** (%) - Percentage breakout from 20-day high
- timestamp of entry and exit

**Trade Lifecycle:**
```
Signal Generated → Logged to Journal → Active Monitoring 
→ (Target Hit OR SL Hit OR Expiry) → Outcome Recorded
→ Factor Analysis → Filter Adaptation
```

**Expiry:** 30 days from signal generation

### 5.2 Performance Tracker (`src/performance_tracker.py`)

**Purpose:** Calculates SIQ (Signal Intelligence Quotient)

**SIQ Formula:**

```
SIQ = (Successful Signals / Total Signals) × 100
```

Where:
- Successful = Target 1 or Target 2 hit before stop loss
- Total = All completed signals

**SIQ Rating:**
| Range | Rating |
|-------|-------|
| 80-100% | Excellent |
| 60-79% | Good |
| 40-59% | Average |
| 20-39% | Below Average |
| 0-19% | Poor |

**Metrics Tracked:**
- Total signals, Active signals, Completed signals
- Success rate, Failure rate
- Average holding days, Average return %
- Per-strategy breakdown (TREND, VERC, MTF)
- Per-quality-grade win rates (A/B/C)

### 5.3 Signal Tracker (`src/signal_tracker.py`)

**Purpose:** Monitors active signals for target/SL hits

**Monitoring Frequency:** Every 4 scans (configurable)

**Check Logic:**
```
For each active signal:
  - Fetch current price
  - If price >= Target 1 or Target 2 → TARGET_HIT
  - If price <= Stop Loss → SL_HIT
  - If days > expiry_days → TIMEOUT
  - Otherwise → ACTIVE
```

### 5.4 Auto-Optimization (`src/strategy_optimizer.py`)

**Purpose:** Automatically adjusts strategy weights based on performance

**Rules:**
- Win rate < 40% → Reduce strategy_weight
- Win rate > 60% → Increase strategy_weight
- Max adjustment: 10% per batch
- Requires minimum 10 trades before optimization

### 5.5 Factor Analyzer (`src/factor_analyzer.py`)

**Purpose:** Granular analysis of trade outcomes per factor

**Analysis Scope:**
- Volume ratio bucket performance
- RSI range performance
- Breakout strength performance
- Quality grade (A/B/C) win rates
- Market context (BULLISH/SIDEWAYS/BEARISH) performance
- Entry type (BREAKOUT/PULLBACK) performance

**Output:** `data/factor_insights.json`

**Learning Feedback Loop:**
```
Trade Completed
    ↓
Factor Analysis (when ≥20 closed trades)
    ↓
Optimization Recommendations
    ↓
Adaptive Filter Update (once per day cooldown)
    ↓
Strategy Weight Optimization
```

**Key Constraints:**
- Learning runs only when total_closed_trades >= 20
- Cooldown period: 1 day between updates
- Filter changes bounded by FLOOR and CAP values

---

## 6. AI Integration

### 6.1 Multi-Provider LLM (`src/ai_stock_analyzer.py`)

**Purpose:** AI-powered stock analysis with provider failover

**Supported Providers:**
- OpenAI (GPT-4)
- Anthropic (Claude)
- Google Gemini
- Groq (Llama, Mixtral)

**Features:**
- Automatic provider failover on API failure
- Stock analysis with BUY/SELL/HOLD recommendations
- Entry/stop/target calculation
- Risk-reward ratio assessment
- Sector and market context

**Analysis Output:**
```json
{
  "recommendation": "BUY",
  "confidence": 8,
  "reasoning": "...",
  "risk_reward_ratio": "1:3",
  "entry_zone": "2450-2480",
  "stop_loss": "2400",
  "targets": ["2600", "2750"]
}
```

### 6.2 AI Learning Layer (`src/ai_learning_layer.py`)

**Purpose:** Analyzes journal data for failure patterns

**Analysis Scope:**
- Per-strategy performance
- Common factors in failed signals
- Volume/rsi thresholds
- Market conditions

**Strict Mode:** AI does NOT control signals - only suggests improvements

---

## 7. Alert System

### 7.1 Telegram Alerts (`src/alert_service.py`)

**Purpose:** Sends trading signals to Telegram

**Alert Format (v2.2 - Simplified):**

**Trend Signal:**
```
📈 TREND SIGNAL

🎯 Entry Zone: ₹2462.25

🛡️ Stop Loss: ₹2400.00 (-2.0%)

🎯 Targets (Conf: 8/10):
  T1: ₹2600.00 (+6.1%) ETA: 3-5 days
  T2: ₹2750.00 (+12.2%) ETA: 7-10 days

📊 S/R: ₹2350.00 / ₹2500.00
```

**VERC Signal:**
```
📊 VERC SIGNAL (Accumulation)

🎯 Entry Zone: ₹500.00 - ₹502.50

🛡️ Stop Loss: ₹480.00 (-2.5%)

🎯 Targets (Conf: 8/10):
  T1: ₹520.00 (+4.0%) ETA: 2-4 days
  T2: ₹540.00 (+8.0%) ETA: 5-8 days

📊 S/R: ₹475.00 / ₹510.00
```

**MTF Signal:**
```
🟢 MTF SIGNAL

🎯 Entry Zone: ₹1650.00

🛡️ Stop Loss: ₹1620.00 (-1.8%)

🎯 Targets (Conf: 8/10):
  T1: ₹1720.00 (+4.2%)
  T2: ₹1790.00 (+8.5%)

📊 1D→1H→15m
```
  • Structure: HIGHER_HIGHS
  • Pullback: COMPLETE at EMA50
  • Volume: 1.5x above avg

🎯 Confidence: 8/10
```

### 7.2 Outcome Notifications

**Target Hit:**
```
🎯 TARGET 1 HIT: RELIANCE

Entry: ₹2450
Target 1: ₹2600
Return: +6.12%
```

**Stop Loss Hit:**
```
🛡️ STOP LOSS HIT: RELIANCE

Entry: ₹2450
SL: ₹2400
Loss: -2.04%
```

---

## 8. Scheduling

### 8.1 Market Hours (`src/market_scheduler.py`)

**Market Hours (IST):** 09:15 - 15:30

**Scan Interval:** Every 15 minutes

**Special Scans:**
- Startup scan (runs immediately on start)
- 3:00 PM update scan (market close review)

### 8.2 Execution Flow

```
Market Open (09:15) → Scan
       ↓
Every 15 min during market hours
       ↓
Market Close (15:30) → Final scan
       ↓
Shutdown
```

---

## 9. Configuration

### 9.1 Settings (`config/settings.json`)

```json
{
  "telegram": {
    "bot_token": "",
    "chat_id": "",
    "channel_chat_id": ""
  },
  "scanner": {
    "timeframe": "1D",
    "scan_interval_minutes": 15,
    "max_signals_per_strategy": 2,
    "enable_mtf_strategy": true
  },
  "scheduler": {
    "timezone": "Asia/Kolkata",
    "scan_time_hour": 15,
    "scan_time_minute": 0,
    "run_days": [1, 2, 3, 4, 5],
    "market_open_hour": 9,
    "market_open_minute": 15,
    "market_close_hour": 15,
    "market_close_minute": 30
  },
  "reasoning": {
    "enabled": true,
    "weights": {
      "rule_based": 0,
      "ai_reasoning": 100
    },
    "min_confidence_threshold": 60
  },
  "learning": {
    "enabled": true,
    "signal_tracking": {
      "check_interval_scans": 4,
      "expiry_days": 30,
      "auto_close_on_target": true,
      "auto_close_on_sl": true
    },
    "siq_scoring": {
      "lookback_days": 30,
      "weights": {
        "win_rate": 0.25,
        "avg_return": 0.20,
        "consistency": 0.15,
        "risk_reward": 0.15,
        "signal_quality": 0.15,
        "timing": 0.10
      }
    }
  }
}
```

### 9.2 Stock List (`config/stocks.json`)

- ~750 NSE stock symbols (NIFTY 50, NEXT 50, MIDCAP 150, SMALLCAP 250+)
- Full list includes: RELIANCE, TCS, HDFCBANK, INFY, ICICIBANK, and 740+ more

---

## 10. Key Classes and Data Structures

### 10.1 TrendSignal (`trend_detector.py`)

```python
class TrendSignal:
    ticker: str
    timestamp: datetime
    indicators: Dict[str, Any]
    signal_type: str  # "TREND"
    trend_score: int  # 0-10
    score_breakdown: Dict[str, int]
    volume_ratio: float
    breakout_strength: float
    rank_score: float
```

### 10.2 VERCSignal (`volume_compression.py`)

```python
@dataclass
class VERCSignal:
    stock_symbol: str
    compression_detected: bool
    breakout_detected: bool
    current_price: float
    compression_high: float
    compression_low: float
    range_height: float
    entry_min: float
    entry_max: float
    stop_loss: float
    target_1: float
    target_2: float
    confidence_score: int  # 0-10
    confidence_factors: Dict[str, int]
    relative_volume: float
    trend_aligned: bool
```

### 10.3 MTFSignal (`mtf_strategy.py`)

```python
@dataclass
class MTFSignal:
    ticker: str
    signal_type: str  # BUY/SELL
    
    # Timeframes
    trend_timeframe: str   # 1D
    structure_timeframe: str  # 1H
    entry_timeframe: str   # 15m
    
    # Entry parameters
    entry_price: float
    stop_loss: float
    target_1: float
    target_2: float
    
    # Analysis
    trend_direction: str  # BULLISH/BEARISH
    structure_status: str  # HIGHER_HIGHS/LOWER_LOWS/SIDEWAYS
    pullback_status: str  # ACTIVE/COMPLETE/NONE
    breakout_confirmed: bool
    volume_confirmed: bool
    
    # Confidence
    confidence_score: int  # 0-10
    rejection_reason: Optional[str]
    risk_reward_1: float
    risk_reward_2: float
```

### 10.4 Trade (`trade_journal.py`)

```python
@dataclass
class Trade:
    trade_id: str
    symbol: str
    strategy: str  # TREND/VERC/MTF
    entry: float
    stop_loss: float
    targets: List[float]
    timestamp: str
    outcome: str  # WIN/LOSS/OPEN/TIMEOUT
    rr_achieved: float
    max_drawdown: float
    volume_ratio: float
    rsi: float
    trend_score: float
    verc_score: float
    rank_score: float
    quality: str = "B"  # A/B/C quality grade
    market_context: str = "BULLISH"  # BULLISH/SIDEWAYS/BEARISH
    entry_type: str = "BREAKOUT"  # BREAKOUT/PULLBACK
    candle_quality: str = "NORMAL"  # NORMAL/STRONG/WEAK
    breakout_strength: float = 0.0  # percentage
```

---

## 11. Signal Flow Summary

```
Scanning Process:
───────────────────────────────────────────────────────────────

1. FETCH DATA
   ├─ fetch_multiple_stocks() → 1D data
   └─ fetch_multiple_stocks_multi_timeframe() → 1D+1H+15m

2. CALCULATE INDICATORS
   └─ indicator_engine.calculate_indicators()
      ├─ EMA 20/50/100/200
      ├─ RSI, ATR, MACD
      ├─ Volume MA 5/20/30
      └─ 20-day High/Low

3. DETECT SIGNALS
   ┌─ Trend (trend_detector.py)
   │  ├─ EMA Alignment (+3)
   │  ├─ Fresh Crossover (+2)
   │  ├─ Price Breakout (+2)
   │  ├─ Volume Spike (+2)
   │  └─ RSI Ideal (+1/-1)
   │  
   ├─ VERC (volume_compression.py)
   │  ├─ Range Compression (+3)
   │  ├─ Volume Expansion (+2)
   │  ├─ Breakout Volume (+2)
   │  ├─ Index Alignment (+2)
   │  └─ Relative Strength (+1)
   │  
   └─ MTF (mtf_strategy.py)
      ├─ Trend (1D)
      ├─ Structure (1H)
      ├─ Pullback (1H)
      ├─ Breakout (15m)
      └─ Volume (15m)

4. RANK & FILTER
   ├─ Calculate PURE rank_score (no weight mixing)
   ├─ Sort by (strategy_weight, rank_score)
   ├─ Market context filter (strategy-aware)
   │  ├─ TREND: -1 in BEARISH, reject weak in SIDEWAYS
   │  └─ VERC: allowed in all contexts
   ├─ No-trade zone filter (ATR, wick/body, weak signals)
   ├─ Quality grading (A/B/C)
   ├─ Deduplicate (signal_memory)
   ├─ Max 5 per scan

5. ALERT & TRADE
   ├─ Format alerts with quality grade
   ├─ Send to Telegram
   ├─ Log to trade_journal (with quality, market_context)
   └─ Track for outcomes

6. MONITOR & LEARN
   ├─ Check active signals (every 4 scans)
   ├─ Detect target/SL hits
   ├─ Update trade outcomes
   ├─ Factor analysis (when ≥20 closed trades)
   ├─ Adaptive filter update (1-day cooldown)
   ├─ Strategy weight optimization
   └─ Calculate SIQ
```

---

## 12. Dependencies

```
yfinance>=0.2.36        # Market data
pandas>=2.0.0           # Data processing
ta>=0.11.0              # Technical indicators
schedule>=1.2.0         # Scheduling
APScheduler>=3.10.0       # Advanced scheduling
requests>=2.31.0          # HTTP requests
python-telegram-bot>=20.0  # Telegram bot
python-dotenv>=1.0.0       # Environment config
pytz>=2023.3            # Timezone handling
openai>=1.0.0            # OpenAI GPT
anthropic>=0.25.0          # Anthropic Claude
google-genai>=0.1.0        # Google Gemini
groq>=0.4.0              # Groq Llama/Mixtral
```

---

## 13. Trade-off Decisions

| Decision | Rationale |
|----------|----------|
| JSON storage | Simplicity over SQL - suitable for 500-1000 trades |
| 15-minute interval | Balance between signal freshness and API limits |
| 5 signals max | Avoid signal overload |
| 30-day expiry | Capture medium-term moves |
| AI strict mode | AI suggests, human decides |
| YFinance | Free and reliable, vs paid alternatives |

---

## 14. Known Limitations

1. **Data Source:** Yahoo Finance may have slight delays
2. **Market Hours:** Only runs during NSE market hours (09:15-15:30 IST)
3. **Signal Volume:** May generate no signals on consolidating markets
4. **Historical Backtesting:** Not implemented - only forward testing
5. **Paper Trading:** Not integrated

---

## 15. Usage

### Start Scanner
```bash
python -m src.main
```

### Test Run (single scan)
```bash
python -m src.main --test
```

### Run Specific Strategy
```bash
python -m src.main --strategy trend   # Only TREND
python -m src.main --strategy verc    # Only VERC
python -m src.main --strategy mtf     # Only MTF
python -m src.main --strategy all   # All strategies (default)
```

### Enable Telegram Bot
```bash
python -m src.main --enable-telegram-bot
```

---

## 17. v2.0 Upgrade Features (2026-04-09)

### 17.1 Key Architecture Changes

| Feature | Before | After |
|---------|--------|-------|
| Rank Score | Mixed with strategy_weight | PURE score, sorting uses weights separately |
| Market Context | Not integrated | Strategy-aware filtering |
| Trade Quality | Not tracked | A/B/C grading with win rate analysis |
| Factor Learning | Basic | Granular analysis per factor bucket |
| Adaptive Filters | Manual | Auto-updated with bounds and cooldown |
| Learning Loop | Every completion | Minimum 20 trades + 1-day cooldown |

### 17.2 New Files Added

- `src/factor_analyzer.py` - Factor-level learning system
- `src/market_context.py` - Market context detection engine

### 17.3 New Data Files

- `data/factor_insights.json` - Factor performance analytics
- `data/market_context.json` - NIFTY context history
- `data/adaptive_filters.json` - Dynamic filter state

### 17.4 Stability Controls

- **Minimum trades:** 20 closed trades before learning runs
- **Cooldown:** 1 day between filter updates
- **Filter bounds:** FLOOR and CAP limits prevent drift
- **Score purity:** Strategy weights only affect ranking, not scoring

---

## 18. v2.1 Upgrade Features (2026-04-12)

### 18.1 History Manager Enhancements

| Feature | Description |
|---------|-------------|
| PerformanceAnalyzer | Analyzes setups, calculates win rate, returns, profit factor |
| PositionManager | Trailing SL, partial exits at T1/T2 |
| MultiTimeframeValidator | Daily/1H/15m validation |
| TradeSetup | Entry, SL, targets, RR validation |

### 18.2 Market Context Enhancements

| Feature | Description |
|---------|-------------|
| ATR-based detection | Uses ATR × multiplier bounds instead of % |
| Volatility regimes | LOW/NORMAL/HIGH classification |
| Context flip detection | Whipsaw filter |
| Context persistence | Score boost when >= 5 periods |
| STRONG_BULLISH/BEARISH | Strong momentum contexts |

### 18.3 Main.py Enhancements

| Feature | Description |
|---------|-------------|
| Weekend skip | No signals on weekends |
| Telegram security | Warning when token in config |
| MTF deduplication | Additional dedup checks (memory, signal_memory, journal) |
| PURE ranking | Strategy weight only affects sort order |

---

## 16. Disclaimer

This software is for **educational purposes only**. Trading in financial markets involves substantial risk. Always do your own research. Past performance does not guarantee future results.

---

**Document Version:** 3.0  
**Last Updated:** 2026-04-15

---

## 20. v3.0 Agentic AI Features (2026-04-14)

### 20.1 Agent Controller Overview

The Agentic AI transforms the scanner from a rule-based system into an autonomous agent that:

| Feature | Description |
|---------|-------------|
| **LLM-Powered Decisions** | Uses LLM to analyze market conditions and decide actions |
| **Market Regime Detection** | Classifies market as BULLISH/BEARISH/SIDEWAYS/VOLATILE |
| **Dynamic Action Selection** | CHOOSE: SCAN/WAIT/ADJUST/MONITOR/ANALYZE |
| **Self-Correction** | Tracks win/loss streaks, adjusts approach automatically |
| **Natural Language Explanations** | Provides clear reasoning for every decision |
| **State Management** | Maintains agent state with history, metrics, feedback |

### 20.2 Agent Actions

| Action | Description | When Used |
|--------|-------------|------------|
| `SCAN` | Execute normal signal scan | Default, favorable conditions |
| `WAIT` | Skip this scan cycle | Unfavorable market conditions |
| `ADJUST_STRATEGY` | Change strategy focus | When current strategy underperforming |
| `MONITOR` | Focus on existing positions | High market risk |
| `ANALYZE` | Deep dive analysis | On specific stocks or sectors |

### 20.3 Agent Controller Architecture

**File:** `src/agent_controller.py`

| Component | Description |
|-----------|-------------|
| `AgentController` | Main class handling all agent logic |
| `AgentAction` | Enum of possible actions |
| `MarketRegime` | Enum of market conditions |
| `AgentDecision` | Dataclass for decisions (action, confidence, reasoning) |
| `AgentExplanation` | Natural language explanation wrapper |
| `create_agent_controller()` | Factory function for instantiation |

### 20.4 Agent Decision Process

```
1. Fetch Market Data
   ├─ NIFTY 50 index data
   ├─ Sector performance
   ├─ Active signals
   └─ Recent trade outcomes

2. Analyze with LLM
   ├─ System prompt: Expert trading agent instructions
   ├─ Context: Market data, active trades, outcomes
   └─ Output: JSON decision (action, confidence, reasoning)

3. Execute Action
   ├─ SCAN: Run signal detection
   ├─ WAIT: Log skip reason, continue next cycle
   ├─ ADJUST: Modify strategy focus
   └─ MONITOR: Check active positions

4. Track & Self-Correct
   ├─ Record decision in agent state
   ├─ Track win/loss streaks
   └─ Adjust approach based on outcomes
```

### 20.5 Agent State Management

The agent maintains state in `data/agent_state.json`:

```json
{
  version: 3.0,
  last_decision: {
    action: SCAN,
    confidence: 8,
    reasoning: Market is bullish, NIFTY trending up,
    market_regime: BULLISH,
    timestamp: 2026-04-14T10:30:00
  },
  market_regime: BULLISH,
  decision_history: [...],
  feedback_history: [...],
  streak: { wins: 3, losses: 1 },
  strategy_adjustments: {...}
}
```

### 20.6 Agent Integration in Main Loop

The agent is integrated into `main.py`:

```python
# Agent Controller initialization
self.agent_controller = create_agent_controller(
    ai_analyzer=self.ai_analyzer,
    market_context_engine=self.market_context
)

# Agent decision in scan loop
agent_decision = self.agent_controller.analyze_and_decide(
    market_data, active_signals
)

# Execute agent decision
if agent_decision.action == AgentAction.WAIT:
    logger.info(f Agent decided to WAIT: {agent_decision.reasoning})
    return  # Skip this scan
elif agent_decision.action == AgentAction.ADJUST_STRATEGY:
    self.strategy = agent_decision.recommended_strategies[0]
```

### 20.7 Fallback Behavior

If no LLM is available, the agent uses rule-based fallback:

| Regime | Action | Strategy Focus |
|--------|--------|----------------|
| BULLISH | SCAN | TREND, MTF |
| BEARISH | WAIT | None (avoid signals) |
| SIDEWAYS | SCAN | VERC, MTF (avoid TREND) |
| VOLATILE | WAIT | None (high risk) |

---

## 19. Recent Fixes (2026-04-13)

### 19.1 Data Fetcher Reliability Improvements

| Fix | Description |
|-----|-------------|
| Exponential Backoff | Retry 3 times with 1s, 2s, 4s delay on failures |
| Minimum Candles | Validates 20 (1D), 30 (1H/15m) candles before accepting data |
| Error Logging | Logs specific failures for debugging |

### 19.2 Trade Validator Fixes

| Issue | Fix |
|-------|-----|
| EMA Alignment Check | Removed - was never set on signal objects, blocking ALL trades silently |
| Attribute Errors | Changed from `signal.ema_alignment` to proper attribute access |
| Logging | Added logging for filtered signals with reasons |

### 19.4 Alert Message Format (Updated 2026-04-13)

| Field | Status | Format |
|-------|--------|--------|
| Entry Zone | ✅ | `🎯 Entry Zone: ₹{entry}` |
| Stop Loss | ✅ | `🛡️ Stop Loss: ₹{sl} ({pct}%)` |
| Targets with Conf | ✅ | `🎯 Targets (Conf: {score}/10):` |
| Time Estimation | ✅ | `ETA: {time}` |
| S/R Levels | ✅ | `📊 S/R: ₹{support} / ₹{resistance}` |

**Removed from alerts:**
- Stock name header
- Timestamp
- Current price
- Volume Ratio / RSI metrics
- Compression range details