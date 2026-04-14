# NSE Trend Agent - Product Requirements Document

**Version:** 3.0  
**Date:** 2026-04-14  
**Project:** NSE Trend Scanner Agent (Agentic AI v3.0)

---

## 1. Project Overview

**Purpose:** Automated trading scanner for NSE (National Stock Exchange of India) stocks that monitors ~500 stocks during market hours and detects potential uptrend starts. **Now with Agentic AI (v3.0)** - the scanner makes autonomous decisions.

**Technology Stack:**
- Language: Python
- Data Source: Yahoo Finance
- Notifications: Telegram Bot
- AI: Multi-Provider LLM (OpenAI, Anthropic, Google Gemini, Groq)
- Agentic AI: Autonomous decision-making with LLM-powered market analysis

---

## 2. Core Features

### 2.1 Stock Universe
| Feature | Status | Implementation |
|---------|--------|----------------|
| NIFTY 50 stocks | ✅ | config/stocks.json |
| NEXT 50 stocks | ✅ | config/stocks.json |
| MIDCAP 150 stocks | ✅ | config/stocks.json |
| SMALLCAP 250 stocks | ✅ | config/stocks.json |
| Total monitored | ✅ | ~500 stocks |

### 2.2 Data Fetching
| Feature | Status | Implementation |
|---------|--------|----------------|
| Real-time price data | ✅ | src/data_fetcher.py |
| OHLCV data (1D timeframe) | ✅ | yfinance |
| Technical indicators | ✅ | src/indicator_engine.py |
| EMA 20, 50, 100, 200 | ✅ | ta library |
| Volume MA 30 | ✅ | ta library |
| RSI (14) | ✅ | ta library |
| ATR (14) | ✅ | ta library |

### 2.3 Trading Strategies

#### Trend Detection Strategy
| Feature | Status | Implementation |
|---------|--------|----------------|
| EMA alignment detection | ✅ | src/trend_detector.py |
| EMA20 > EMA50 > EMA100 > EMA200 | ✅ | Line 50+ |
| Volume confirmation | ✅ | Volume > Volume MA30 |
| Trend start detection | ✅ | EMA crossover detection |
| Confidence scoring | ✅ | 1-10 scale |

#### VERC Strategy (Volume Expansion Range Compression)
| Feature | Status | Implementation |
|---------|--------|----------------|
| Range compression detection | ✅ | src/volume_compression.py |
| Price range < 5% detection | ✅ | (High-Low)/Price < 0.05 |
| ATR local minimum detection | ✅ | ATR analysis |
| Volume expansion detection | ✅ | Volume MA(5) > Volume MA(20) |
| Relative volume > 1.3x | ✅ | volume_ratio calculation |
| Trend alignment check | ✅ | Price > EMA50 |
| Multi-factor scoring | ✅ | Range(+3), Volume(+2), Breakout(+2), Index(+2), Strength(+1) |
| Signal confidence ≥ 7 | ✅ | Minimum threshold |

#### MTF Strategy (Multi-Timeframe)
| Feature | Status | Implementation |
|---------|--------|----------------|
| 15m + 1h + 1D confirmation | ✅ | src/mtf_strategy.py |
| Cross-timeframe signal validation | ✅ | Confluence detection |

### 2.4 AI/ML Features

| Feature | Status | Implementation |
|---------|--------|----------------|
| Multi-provider LLM support | ✅ | src/ai_stock_analyzer.py |
| OpenAI GPT integration | ✅ | OpenAIProvider class |
| Anthropic Claude integration | ✅ | AnthropicProvider class |
| Google Gemini integration | ✅ | GoogleGeminiProvider class |
| Groq integration | ✅ | GroqProvider class |
| Automatic provider failover | ✅ | MultiProviderAIAnalyzer |
| Stock analysis with recommendations | ✅ | BUY/SELL/HOLD |
| Entry/stop/target calculation | ✅ | AI analysis output |
| Risk assessment | ✅ | Risk-reward ratio |
| Contextual market analysis | ✅ | Sector, nifty trends |

### 2.5 Alert & Notifications

| Feature | Status | Implementation |
|---------|--------|----------------|
| Telegram notifications | ✅ | src/alert_service.py |
| Trend signal alerts | ✅ | _format_trend_alert |
| VERC signal alerts | ✅ | _format_verc_alert |
| MTF signal alerts | ✅ | format_mtf_signal_alert |
| Entry zone specification | ✅ | Buy Above range |
| Stop loss specification | ✅ | SL with percentage |
| Target specification | ✅ | T1, T2 with percentages |
| Confidence score display | ✅ | 1-10 scale |
| Duplicate alert prevention | ✅ | alerted_today set |
| Signal outcome notifications | ✅ | Target hit / SL hit alerts |

### 2.6 Interactive Telegram Bot

| Feature | Status | Implementation |
|---------|--------|----------------|
| Stock symbol queries | ✅ | Send stock symbol |
| /analyze command | ✅ | Full AI analysis |
| /trend command | ✅ | Technical analysis only |
| /status command | ✅ | Scanner status |
| /help command | ✅ | Help message |
| Two-way communication | ✅ | Interactive bot |

### 2.7 Agentic AI (v3.0) - Autonomous Agent

| Feature | Status | Implementation |
|---------|--------|----------------|
| Agent Controller | ✅ | src/agent_controller.py |
| LLM-powered decision making | ✅ | Uses LLM to analyze and decide actions |
| Market regime detection | ✅ | BULLISH/BEARISH/SIDEWAYS/VOLATILE classification |
| Dynamic action selection | ✅ | SCAN/WAIT/ADJUST/MONITOR/ANALYZE |
| Self-correction | ✅ | Win/loss streak tracking and approach adjustment |
| Natural language explanations | ✅ | Reasoning provided for every decision |
| Agent state management | ✅ | data/agent_state.json |
| Fallback behavior | ✅ | Rule-based when LLM unavailable |

### 2.10 Swing Trade Scanner (PRD 2)

| Feature | Status | Implementation |
|---------|--------|----------------|
| Focus: Clean trends | ✅ | src/swing_trade_scanner.py |
| Focus: Swing trades | ✅ | SwingTradeScanner class |
| Timeframes: Trend → Daily | ✅ | 1D for trend identification |
| Timeframes: Entry → 1H | ✅ | 1H for entry timing |
| EMA 50/200 alignment | ✅ | check_ema_50_200_alignment |
| Volume delivery spike | ✅ | check_volume_spike (>1.5x) |
| Structure (HH/HL) | ✅ | detect_structure_1h |
| Sector strength | ✅ | sector_data parameter |
| NIFTY alignment | ✅ | check_nifty_alignment |
| Delivery % | ✅ | get_delivery_percent |
| Trend continuation | ✅ | Strategy type detection |
| Breakout after consolidation | ✅ | check_breakout_consolidation |
| Avoid: Low volume | ✅ | MIN_VOLUME_RATIO filter |
| Avoid: News spikes | ✅ | Volume pattern check |

### 2.11 Options Scanner (PRD 3)

| Feature | Status | Implementation |
|---------|--------|----------------|
| Focus: Volatility + timing | ✅ | src/options_scanner.py |
| Timeframes: Trend → Daily | ✅ | 1D for underlying direction |
| Timeframes: Entry → 15m/5m | ✅ | 15m for entry timing |
| Underlying stock gives signal | ✅ | underlying_signal check |
| IV expansion starting | ✅ | check_iv_expansion |
| OI confirms direction | ✅ | get_oi_data + oi_direction |
| IV percentile | ✅ | get_iv_data |
| OI change | ✅ | oi_change_pct tracking |
| PCR (Put Call Ratio) | ✅ | get_pcr |
| ATR expansion | ✅ | check_atr_expansion |
| Breakout + Call buy | ✅ | BREAKOUT_CALL strategy |
| Breakdown + Put buy | ✅ | BREAKDOWN_PUT strategy |
| High IV → option selling | ✅ | HIGH_IV_SELL strategy |
| Strict SL (options decay fast) | ✅ | MAX_STOP_LOSS_PCT = 30% |

---

## 3. Agent Actions

| Action | Description | When Used |
|--------|-------------|------------|
| SCAN | Execute normal signal scan | Default, favorable conditions |
| WAIT | Skip this scan cycle | Unfavorable market conditions |
| ADJUST_STRATEGY | Change strategy focus | Current strategy underperforming |
| MONITOR | Focus on existing positions | High market risk |
| ANALYZE | Deep dive on specific stocks | On demand |

### 2.8 Learning & Feedback System

| Feature | Status | Implementation |
|---------|--------|----------------|
| Active signal tracking | ✅ | src/signal_tracker.py |
| Signal outcome monitoring | ✅ | check_all_active_signals |
| Stop loss hit detection | ✅ | Outcome tracking |
| Target hit detection | ✅ | T1, T2 tracking |
| Signal expiry (30 days) | ✅ | expiry_days config |
| History persistence | ✅ | src/history_manager.py |
| Performance metrics | ✅ | src/performance_tracker.py |
| SIQ (Signal Intelligence Quotient) | ✅ | Success rate calculation |
| Daily summary notifications | ✅ | notification_manager.py |
| Weekly performance report | ✅ | Weekly report generation |
| Signal completion notifications | ✅ | Target/SL hit alerts |

### 2.8 Reasoning Engine

| Feature | Status | Implementation |
|---------|--------|----------------|
| Rule-based algorithms | ✅ | Existing strategies |
| Weighted scoring | ✅ | src/reasoning_engine.py |
| Multi-factor scoring | ✅ | 8-factor model |
| Combined signal output | ✅ | rule + weighted + AI |
| Factor contribution breakdown | ✅ | Per-factor scoring |
| Signal strength classification | ✅ | STRONG_BUY/BUY/NEUTRAL/SELL/STRONG_SELL |

### 2.9 Scheduling & Execution

| Feature | Status | Implementation |
|---------|--------|----------------|
| Scheduled scanning | ✅ | src/scheduler.py |
| 15-minute intervals | ✅ | scan_interval config |
| Market hours only (09:15-15:30 IST) | ✅ | market_hours check |
| Single test run | ✅ | --test flag |
| Strategy selection | ✅ | --strategy flag |
| Configurable stock list | ✅ | --config flag |

---

## 3. Configuration

### 3.1 Environment Variables
```
OPENAI_API_KEY          # OpenAI GPT API key
ANTHROPIC_API_KEY      # Anthropic Claude API key
GOOGLE_API_KEY         # Google Gemini API key
GROQ_API_KEY           # Groq API key
TELEGRAM_BOT_TOKEN     # Telegram bot token
TELEGRAM_CHAT_ID       # Telegram chat ID
```

### 3.2 Config Files
| File | Purpose |
|------|---------|
| config/stocks.json | Stock list (500+ symbols) |
| config/settings.json | Scanner settings, weights, notifications |
| data/signals_active.json | Active signal tracking |
| data/signals_history.json | Completed signals |
| data/performance_metrics.json | SIQ and metrics |

---

## 4. Signal Output Format

```json
{
  "signal_id": "UUID",
  "stock_symbol": "RELIANCE",
  "timestamp": "2026-04-05T10:30:00",
  "strategy": "TREND",
  
  "price_data": {
    "current_price": 2450.00,
    "ema20": 2445.00,
    "ema50": 2430.00,
    "ema100": 2410.00,
    "ema200": 2390.00,
    "volume": 1250000,
    "volume_ma30": 980000,
    "volume_ratio": 1.28,
    "rsi": 58.5,
    "atr": 25.0
  },
  
  "entry_zone": {
    "buy_above": 2455.00,
    "entry_min": 2455.00,
    "entry_max": 2472.30
  },
  
  "risk_management": {
    "stop_loss": 2400.00,
    "stop_loss_pct": -2.04,
    "target_1": 2600.00,
    "target_1_pct": 6.12,
    "target_2": 2750.00,
    "target_2_pct": 12.24
  },
  
  "signal_strength": {
    "confidence": 8,
    "verc_score": 78,
    "weighted_score": 72,
    "strength": "STRONG_BUY"
  },
  
  "ai_analysis": {
    "recommendation": "BUY",
    "reasoning": "...",
    "risk_reward_ratio": "1:3"
  },
  
  "tracking": {
    "signal_id": "uuid",
    "status": "ACTIVE",
    "entry_date": "2026-04-05",
    "expiry_date": "2026-05-05"
  }
}
```

---

## 5. File Structure

```
nse-trend-agent/
├── config/
│   ├── settings.json          # All configuration
│   └── stocks.json            # Stock list
├── data/                      # Signal data storage
├── src/
│   ├── __init__.py
│   ├── main.py               # Entry point
│   ├── agent_controller.py  # Agentic AI (v3.0) - autonomous decision maker
│   ├── data_fetcher.py       # Yahoo Finance data
│   ├── indicator_engine.py   # Technical indicators
│   ├── trend_detector.py     # Trend strategy
│   ├── volume_compression.py # VERC strategy
│   ├── mtf_strategy.py       # Multi-timeframe strategy
│   ├── reasoning_engine.py   # Combined scoring
│   ├── ai_stock_analyzer.py  # Multi-provider LLM
│   ├── alert_service.py      # Telegram alerts
│   ├── signal_tracker.py     # Signal tracking
│   ├── history_manager.py    # History persistence
│   ├── performance_tracker.py # SIQ metrics
│   ├── notification_manager.py # Notifications
│   ├── scheduler.py          # Scheduling
│   └── scheduler/
│       └── scanner_scheduler.py
├── docs/
│   ├── PRD-Reasoning-Learning.md
│   └── (this file)
├── requirements.txt
└── README.md
```

---

## 6. Feature Checklist for Comparison

Use this table to compare with other projects:

| # | Feature | This Project | Project A | Project B |
|---|---------|--------------|-----------|------------|
| 1 | Stock universe (500+) | ✅ | | |
| 2 | Real-time data (yfinance) | ✅ | | |
| 3 | EMA 20/50/100/200 | ✅ | | |
| 4 | Volume MA 30 | ✅ | | |
| 5 | RSI/ATR | ✅ | | |
| 6 | Trend detection (EMA alignment) | ✅ | | |
| 7 | VERC strategy | ✅ | | |
| 8 | MTF strategy (15m+1h+1D) | ✅ | | |
| 9 | Multi-provider LLM | ✅ | | |
| 10 | Provider failover | ✅ | | |
| 11 | Telegram alerts | ✅ | | |
| 12 | Interactive Telegram bot | ✅ | | |
| 13 | Signal tracking | ✅ | | |
| 14 | SIQ scoring | ✅ | | |
| 15 | Performance metrics | ✅ | | |
| 16 | Outcome notifications | ✅ | | |
| 17 | Weighted scoring | ✅ | | |
| 18 | Combined signal engine | ✅ | | |
| 19 | Scheduled scanning | ✅ | | |
| 20 | Market hours filtering | ✅ | | |
| 21 | Duplicate prevention | ✅ | | |
| 22 | Test run mode | ✅ | | |

---

## 7. Dependencies

```
yfinance>=0.2.36
pandas>=2.0.0
ta>=0.11.0
schedule>=1.2.0
APScheduler>=3.10.0
requests>=2.31.0
python-telegram-bot>=20.0
python-dotenv>=1.0.0
pytz>=2023.3
openai>=1.0.0
anthropic>=0.25.0
google-genai>=0.1.0
groq>=0.4.0
```

---

**Document Version:** 3.0  
**Last Updated:** 2026-04-14