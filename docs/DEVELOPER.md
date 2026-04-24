# NSE Trend Scanner - Developer Documentation

## Table of Contents

1. [Overview](#overview)
2. [Trading Strategies](#trading-strategies)
3. [AI Components](#ai-components)
4. [Core Modules & Their Roles](#core-modules--their-roles)
5. [Signal Flow Pipeline](#signal-flow-pipeline)
6. [Key Rules & Filters](#key-rules--filters)
7. [Data Flow](#data-flow)
8. [Configuration](#configuration)

---

## Overview

**NSE Trend Scanner** is an automated trading signal generator that monitors ~500 NSE (National Stock Exchange of India) stocks during market hours and detects potential trade setups using multiple strategies.

The application has evolved through versions:
- **v1.x**: Basic trend detection with EMA alignment
- **v2.x**: Added VERC, MTF strategies + learning/optimization
- **v3.x**: Agentic AI - autonomous decision-making using LLM

---

## Trading Strategies

### 1. TREND Strategy (EMA Alignment)

Detects potential uptrend starts based on:
- **EMA Alignment** (Score: +3): EMA20 > EMA50 > EMA100 > EMA200
- **Fresh Crossover** (Score: +2): EMA20 crosses above EMA50
- **Price Breakout** (Score: +2): Price breaks above 20-day high
- **Volume Spike** (Score: +2): Volume >= 1.5x average
- **RSI Ideal Zone** (Score: +1): RSI between 50-65

**Signal Threshold**: Score >= 6

### 2. VERC Strategy (Volume Expansion Range Compression)

Detects accumulation before breakout:
- Volume compression (< 30-day avg)
- Price range compression (< 5%)
- RSI in accumulation zone (40-60)
- EMA alignment (bullish)
- Breakout confirmation

### 3. MTF Strategy (Multi-Timeframe)

7-step confirmation system:
1. **Trend (1D)**: Price vs EMA200
2. **Structure (1H)**: Higher Highs/Lower Lows
3. **Pullback (1H)**: Price retraces to EMA50/100
4. **Entry (15m)**: Strong breakout candle
5. **Volume**: Volume > MA30
6. **EMA Alignment**: Valid trend conditions
7. **Trade Validator**: Final decision layer

### 4. Swing Trade Strategy

Captures medium-term swings:
- Trend identification (HH/HL pattern)
- Pullback to key EMA levels
- Volume confirmation

### 5. Options Strategy

Analyzes options data:
- IV (Implied Volatility) compression
- PCR (Put-Call Ratio) analysis
- Support/Resistance from options chain

---

## AI Components

### 1. AI Stock Analyzer (`ai_stock_analyzer.py`)

**Purpose**: Provides LLM-powered stock analysis

**Providers** (in order of priority):
- OpenAI (GPT-4)
- Anthropic (Claude)
- Groq
- Google Gemini

**What it does**:
- Takes technical indicators as input
- Returns: BUY/SELL/HOLD recommendation
- Entry zone, stop loss, targets
- Detailed reasoning

**When used**:
- Analyzes specific stocks on demand
- Provides reasoning for signals
- Fallback when chart-based analysis unavailable

### 2. Reasoning Engine (`reasoning_engine.py`)

**Purpose**: Hybrid signal generation combining rules + AI

**Components**:
- **Factor Scoring**: Weights different technical factors
- **AI Reasoning Integration**: Gates AI recommendations
- **Signal Combination**: Merges rule-based + AI signals

**Flow**:
```
Rule-based Score + AI Confidence → Combined Score → Final Recommendation
```

**AI Confidence Gates**:
- If AI confidence < 5: Use rule-based only
- If AI says SELL but rule-based strong: Downgrade to NEUTRAL
- If AI says BUY with confidence >= 8: Boost score +10

### 3. Agent Controller (`agent_controller.py`)

**Purpose**: Makes the scanner an autonomous agent (v3.0)

**Agent Loop**:
1. Fetch market data (NIFTY, sectors, active trades)
2. Analyze with LLM - decide action
3. Execute action or skip scan
4. Track outcomes for self-correction
5. Update agent state

**Agent Actions**:
- `SCAN`: Execute normal signal scan
- `WAIT`: Skip scan (unfavorable conditions)
- `ADJUST_STRATEGY`: Change focus (e.g., more VERC in sideways)
- `MONITOR`: Focus on existing positions
- `ANALYZE`: Deep dive on specific stocks

**Market Regime Detection**:
- BULLISH: Strong uptrend → maximize TREND signals
- BEARISH: Strong downtrend → minimize signals
- SIDEWAYS: Range-bound → favor VERC/MTF
- VOLATILE: High volatility → reduce confidence, tighten SL

### 4. AI Learning Layer (`ai_learning_layer.py`)

**Purpose**: Analyzes trade journal, detects patterns

**Features**:
- Win/loss pattern detection
- Strategy performance comparison
- Filter adjustments based on historical data
- Suggests improvements to rules

### 5. AI Rules Engine (`ai_rules_engine.py`)

**Purpose**: Dynamic rule adjustment based on AI analysis

**Features**:
- Adjusts volume_ratio thresholds
- Modifies RSI filters dynamically
- Adapts to market conditions

---

## Core Modules & Their Roles

| Module | File | Role |
|--------|------|------|
| **Main Entry** | `main.py` | Orchestrates all components, runs scan cycles |
| **Data Fetcher** | `data_fetcher.py` | Fetches OHLCV data from Yahoo Finance |
| **Indicator Engine** | `indicator_engine.py` | Calculates EMA, RSI, ATR, Volume MA |
| **Trend Detector** | `trend_detector.py` | Detects EMA alignment signals |
| **Volume Compression** | `volume_compression.py` | VERC strategy implementation |
| **MTF Strategy** | `mtf_strategy.py` | Multi-timeframe signal generation |
| **Swing Scanner** | `swing_trade_scanner.py` | Swing trade detection |
| **Options Scanner** | `options_scanner.py` | Options-based signals |
| **Trade Validator** | `trade_validator.py` | Validates signals against quality filters |
| **Consolidation Detector** | `consolidation_detector.py` | Detects tight consolidation patterns |
| **Market Scheduler** | `market_scheduler.py` | Runs scans every 15 min during market hours |
| **Market Context** | `market_context.py` | Detects NIFTY trend (BULLISH/BEARISH/SIDEWAYS) |
| **Trade Journal** | `trade_journal.py` | Logs all signals, tracks outcomes |
| **Alert Service** | `alert_service.py` | Sends Telegram notifications |
| **Signal Memory** | `signal_memory.py` | Prevents duplicate signals |
| **Performance Tracker** | `performance_tracker.py` | Tracks win rate, RR, drawdown |

---

## Signal Flow Pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│                    SCAN CYCLE (Every 15 min)                       │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  1. FETCH DATA                                                      │
│     - Fetch 1D, 1H, 15m data for ~500 stocks                      │
│     - Calculate indicators (EMA, RSI, ATR, Volume MA)             │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  2. AGENT DECISION (v3.0)                                          │
│     - LLM analyzes market conditions                               │
│     - Decide: SCAN / WAIT / ADJUST_STRATEGY                        │
│     - Skip if conditions unfavorable                               │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  3. RUN STRATEGIES                                                 │
│     - TREND: Check EMA alignment, breakout, volume                │
│     - VERC: Check volume compression, accumulation                 │
│     - MTF: Check multi-timeframe confirmation                      │
│     - SWING: Check swing patterns                                  │
│     - OPTIONS: Check IV compression, PCR                           │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  4. VALIDATION                                                      │
│     - Trade Validator: Check RR, SL%, targets, volume              │
│     - Consolidation: Tight consolidation + breakout                │
│     - Market Context: Adjust for BULLISH/BEARISH/SIDEWAYS         │
│     - Filters: RSI, volume ratio, breakout strength                │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  5. SCORING & RANKING                                              │
│     - Calculate rank_score =                                       │
│       (strategy_score * 0.6) + (volume_score * 0.2) +             │
│       (breakout_strength * 0.2)                                     │
│     - Sort by score descending                                     │
│     - Select top 5 signals                                         │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  6. CALCULATE SL/TARGETS (Chart-Based)                             │
│     - Find swing highs/lows from last 20 candles                  │
│     - SL = nearest support (99%)                                   │
│     - T1 = nearest resistance                                      │
│     - T2 = 2nd nearest resistance                                  │
│     - Fallback: ATR-based if chart data unavailable               │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  7. SEND ALERTS                                                    │
│     - Format Telegram message                                      │
│     - Send to channel/chat                                         │
│     - Log to trade journal                                         │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  8. TRACK OUTCOMES                                                 │
│     - Monitor SL/Target hits                                       │
│     - Update trade status in journal                               │
│     - Feed back to learning layer                                  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Key Rules & Filters

### Signal Generation Rules

| Rule | Threshold | Description |
|------|-----------|-------------|
| Min Trend Score | 6 | TREND strategy requires score >= 6 |
| Min Volume Ratio | 1.5x | Volume must be 1.5x average |
| Min Breakout | 2% | Price must break 20-day high |
| RSI Zone | 50-65 | Ideal for buy signals |
| Consolidation Range | < 4% | Tight consolidation before breakout |

### Quality Filters (Trade Validator)

| Filter | Min | Max | Description |
|--------|-----|-----|-------------|
| Risk-Reward Ratio | 2.0 | - | Minimum 1:2 RR |
| Stop Loss % | 2% | 3% | SL as % of entry |
| Target % | 5% | 10% | First target as % of entry |
| Volume Ratio | 1.3 | - | Min volume spike |
| RSI (Buy) | - | 70 | Not overbought |
| Confidence | 7 | - | Min confidence score |

### Market Context Adjustments

| Context | TREND Signals | VERC Signals | Action |
|---------|---------------|--------------|--------|
| BULLISH | Allowed | Allowed | Normal operation |
| SIDEWAYS | Score >= 6 only | Allowed | Reject weak signals |
| BEARISH | Reduced | Allowed | Lower score by 1 |
| VOLATILE | Tighter filters | Tighter filters | Reduce confidence |

### Deduplication Rules

- **Signal Memory**: Prevents same signal within 24 hours
- **Trade Journal**: Prevents duplicate logging
- **Cooldown**: 30 min between signals for same stock

---

## Data Flow

### Input Data
```python
{
    'stock_symbol': 'RELIANCE',
    'ohlcv': {
        'open': 2500,
        'high': 2550,
        'low': 2480,
        'close': 2540,
        'volume': 5000000
    },
    'indicators': {
        'ema_20': 2480,
        'ema_50': 2450,
        'ema_100': 2400,
        'ema_200': 2350,
        'rsi': 58,
        'atr': 45,
        'volume_ma_30': 4000000,
        'volume_ratio': 1.25
    }
}
```

### Output Signal
```python
{
    'signal_id': 'uuid',
    'stock_symbol': 'RELIANCE',
    'strategy': 'TREND',
    'direction': 'BUY',
    'entry': 2540.0,
    'stop_loss': 2490.0,      # Nearest support (chart-based)
    'target_1': 2600.0,       # Nearest resistance
    'target_2': 2650.0,        # 2nd resistance
    'confidence_score': 8.5,
    'trend_score': 7,
    'volume_ratio': 1.25,
    'quality': 'A',
    'market_context': 'BULLISH'
}
```

### Trade Journal Entry
```python
{
    'trade_id': 'uuid',
    'symbol': 'RELIANCE',
    'strategy': 'TREND',
    'direction': 'BUY',
    'entry': 2540.0,
    'stop_loss': 2490.0,
    'targets': [2600.0, 2650.0],
    'outcome': 'OPEN',         # WIN/LOSS/OPEN/TIMEOUT
    'quality': 'A',
    'rank_score': 8.5,
    'market_context': 'BULLISH',
    'entry_type': 'BREAKOUT'
}
```

---

## Configuration

### Stock List (`config/stocks.json`)
```json
{
    "nifty50": ["RELIANCE", "TCS", "INFY", ...],
    "next50": [...],
    "midcap150": [...],
    "smallcap250": [...]
}
```

### Settings (`config/settings.json`)
```json
{
    "scanner": {
        "enable_mtf_strategy": true,
        "enable_swing_trade": true,
        "max_signals_per_day": 5,
        "confidence_threshold": 7.0
    },
    "telegram": {
        "bot_token": "YOUR_BOT_TOKEN",
        "chat_id": "YOUR_CHAT_ID"
    },
    "trade_filters": {
        "min_rr": 2.0,
        "min_sl_pct": 2.0,
        "max_sl_pct": 3.0
    }
}
```

### Environment Variables (for AI)
```bash
OPENAI_API_KEY=your_key       # Primary AI
GROQ_API_KEY=your_key         # Fallback
ANTHROPIC_API_KEY=your_key    # Fallback
GOOGLE_API_KEY=your_key       # Fallback
```

---

## Running the Application

### Basic Usage
```bash
python -m src.main
```

### Test Mode
```bash
python -m src.main --test              # Single scan
python -m src.main --mock-alerts      # Mock alerts
```

### Specific Strategy
```bash
python -m src.main --strategy trend    # Only TREND
python -m src.main --strategy verc     # Only VERC
python -m src.main --strategy all      # All strategies
```

### Enable Telegram Bot
```bash
python -m src.main --enable-telegram-bot
```

---

## Key Files Reference

| File | Lines | Purpose |
|------|-------|---------|
| `main.py` | 2757 | Main orchestrator |
| `mtf_strategy.py` | 1903 | Multi-timeframe signals |
| `trade_journal.py` | 709 | Trade logging |
| `reasoning_engine.py` | 915 | Hybrid signal generation |
| `ai_stock_analyzer.py` | 457 | LLM analysis |
| `agent_controller.py` | ~500 | Autonomous agent |
| `market_context.py` | 440 | NIFTY trend detection |

---

*Last Updated: 2026-04-15*