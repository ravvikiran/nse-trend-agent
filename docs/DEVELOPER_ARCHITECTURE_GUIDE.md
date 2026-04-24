# NSE Trend Agent - Complete Developer Guide & Architecture

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture & Layers](#architecture--layers)
3. [Signal Flow Diagram](#signal-flow-diagram)
4. [Module Directory](#module-directory)
5. [Detailed Module Documentation](#detailed-module-documentation)
6. [Feature Implementation Map](#feature-implementation-map)
7. [Data Flow Examples](#data-flow-examples)
8. [Integration Points](#integration-points)
9. [New Developer Quick Start](#new-developer-quick-start)
10. [Common Development Tasks](#common-development-tasks)

---

## Project Overview

### What Is This Application?

**NSE Trend Agent** is an AI-powered trading signal generator for Indian stock markets (NSE). It monitors stocks, detects technical opportunities, and alerts traders via Telegram.

### Project Type

- **Language**: Python 3.8+
- **Domain**: Algorithmic Trading / Technical Analysis
- **Architecture**: Modular, Layered, Event-Driven
- **AI Integration**: LLM-based (OpenAI, Anthropic, Groq, Google)
- **Real-time Capability**: Can scan continuously with APScheduler

### Core Value Proposition

```
Market Data → Technical Analysis → AI Reasoning → Validated Signals → Trader Alerts
                                                        ↓
                                          Learning System Improves Over Time
```

---

## Architecture & Layers

### Layer 1: Data & Indicators (Foundation)

**Purpose**: Fetch and process market data

| Component | File | Role |
|-----------|------|------|
| DataFetcher | `data_fetcher.py` | Fetches OHLCV from Yahoo Finance |
| IndicatorEngine | `indicator_engine.py` | Calculates EMA, RSI, ATR, Volume MA |
| MarketContext | `market_context.py` | Analyzes market regime (BULLISH, BEARISH, etc.) |
| MarketScheduler | `market_scheduler.py` | Manages trading hours & market schedule |

**Data Flow**:
```
Yahoo Finance 
    ↓ (fetch_stock_data)
DataFrame (OHLCV)
    ↓ (calculate_indicators)
Enriched DataFrame (with EMA, RSI, Volume MA, ATR)
```

---

### Layer 2: Signal Detection (Multiple Strategies)

**Purpose**: Detect trading opportunities using different strategies

#### Strategy A: Trend Detection
| Component | File | Role |
|-----------|------|------|
| TrendDetector | `trend_detector.py` | Detects uptrend/downtrend using EMA alignment |
| ConsolidationDetector | `consolidation_detector.py` | Detects tight consolidations before breakouts |

**Signal Logic**:
- Perfect EMA order: `price > EMA20 > EMA50 > EMA100 > EMA200`
- RSI confirmation: RSI between 50-65 (bullish zone)
- Volume confirmation: Volume > 30-day average
- Result: TrendSignal (score 0-100)

#### Strategy B: VERC (Volume Expansion Range Compression)
| Component | File | Role |
|-----------|------|------|
| VolumeCompression | `volume_compression.py` | Detects VERC breakouts |

**Signal Logic**:
- Compression phase: Low volatility, tight price range
- Expansion phase: Sudden volume surge with breakout
- Confirmation: Directional move with volume
- Result: VERCSignal with confidence score

#### Strategy C: MTF (Multi-Timeframe)
| Component | File | Role |
|-----------|------|------|
| MTFStrategyScanner | `mtf_strategy.py` | Analyzes 1D, 4H, 1H timeframes together |
| ICTScanner | `mtf_strategy.py` (internal) | Smart Money Concepts strategy |

**Signal Logic**:
- 1D analysis: Major trend direction
- 4H analysis: Intermediate setup
- 1H analysis: Entry confirmation
- Result: MTFSignal with multi-timeframe alignment

#### Strategy D: Swing Trading
| Component | File | Role |
|-----------|------|------|
| SwingTradeScanner | `swing_trade_scanner.py` | Swing trade setup detection |

**Signal Logic**:
- Recent pullback after move
- Support level bounce
- Volume confirmation
- Result: SwingSignal

#### Strategy E: Options Setup Detection
| Component | File | Role |
|-----------|------|------|
| OptionsScanner | `options_scanner.py` | Detects options-friendly setups |

**Signal Logic**:
- IV Rank evaluation
- Support/Resistance distances
- Premium decay analysis
- Result: OptionsSignal

#### Strategy F: Market Sentiment Driven
| Component | File | Role |
|-----------|------|------|
| MarketSentimentAnalyzer | `market_sentiment_analyzer.py` | Analyzes overall market mood |
| SentimentDrivenScanner | `sentiment_driven_scanner.py` | Finds breakouts aligned with sentiment |

**Signal Logic**:
- NIFTY trend analysis
- Sector performance tracking
- Running stocks identification
- AI breakout validation
- Result: SentimentDrivenSignal

---

### Layer 3: Signal Validation & Scoring

**Purpose**: Validate signals meet quality thresholds

| Component | File | Role |
|-----------|------|------|
| ReasoningEngine | `reasoning_engine.py` | Combines weighted scoring + AI reasoning |
| SignalValidator | `signal_validator_enhanced.py` | Enhanced validation gates |
| SignalIntelligenceExplainer | `signal_intelligence_explainer.py` | Makes signals understandable (NEW) |
| SignalScorer | `signal_scorer.py` | Scores signals for ranking |
| TradeValidator | `trade_validator.py` | Validates entry/SL/target setup |

**Processing Pipeline**:
```
Raw Signal
    ↓ (ReasoningEngine)
Weighted Score + AI Reasoning
    ↓ (SignalValidator)
Pass/Fail validation gates
    ↓ (SignalIntelligenceExplainer)
Reasoned Signal with Confidence
    ↓ (SignalScorer)
Ranked & Scored for Output
```

---

### Layer 4: Memory & Deduplication

**Purpose**: Prevent duplicate alerts and track signal state

| Component | File | Role |
|-----------|------|------|
| SignalMemory | `signal_memory.py` | In-memory signal deduplication |
| SignalTracker | `signal_tracker.py` | Tracks active signals till completion |
| TradeJournal | `trade_journal.py` | Persistent signal history |
| HistoryManager | `history_manager.py` | Manages signal/trade history |

**Data Structure**:
```
SignalMemory (session)
├─ Recent signals (prevents duplicates)
└─ Active signals

TradeJournal (persistent)
├─ All signals ever generated
├─ Entry/Exit points
├─ Outcomes
└─ Strategy attribution

HistoryManager
└─ Closed trades with full details
```

---

### Layer 5: AI & Learning

**Purpose**: Improve signals through machine learning and AI analysis

| Component | File | Role |
|-----------|------|------|
| AIStockAnalyzer | `ai_stock_analyzer.py` | LLM-based stock analysis |
| AIRulesEngine | `ai_rules_engine.py` | AI-driven rule adjustment |
| AILearningLayer | `ai_learning_layer.py` | Analyzes patterns for improvement |
| PatternLearningRecognizer | `pattern_learning_recognizer.py` | Learns what patterns work (NEW) |
| AgentController | `agent_controller.py` | Autonomous agent decision-making |

**Learning Flow**:
```
Signal Generated
    ↓
Signal Completes (WIN/LOSS)
    ↓
Pattern Recorded in Journal
    ↓
Learning Analysis
├─ Win rate by pattern type
├─ Best/worst performing strategies
├─ Market regime correlation
└─ Recommendations
    ↓
Next Cycle Uses Learning
└─ Weights adjusted for better signals
```

---

### Layer 6: Performance Tracking & Optimization

**Purpose**: Measure performance and optimize strategy weights

| Component | File | Role |
|-----------|------|------|
| PerformanceTracker | `performance_tracker.py` | Tracks win rates, RR, drawdown |
| StrategyOptimizer | `strategy_optimizer.py` | Adjusts strategy weights |
| FactorAnalyzer | `factor_analyzer.py` | Analyzes factor importance |

**Metrics Tracked**:
```
Per-Strategy Metrics:
├─ Total signals generated
├─ Win rate (%)
├─ Average risk-reward
├─ Profit factor
├─ Max drawdown
└─ Sharpe ratio

Optimization Output:
└─ Weight adjustments (which strategies to prioritize)
```

---

### Layer 7: Notification & Output

**Purpose**: Send alerts and track outcomes

| Component | File | Role |
|-----------|------|------|
| AlertService | `alert_service.py` | Sends alerts via Telegram/SMS |
| NotificationManager | `notification_manager.py` | Formats alert messages |
| TradeGenerator | `trade_generator.py` | Generates entry/SL/target setup |

**Alert Flow**:
```
Signal Validated
    ↓ (TradeGenerator)
Entry/SL/Target Calculated
    ↓ (NotificationManager)
Alert Message Formatted
    ↓ (AlertService)
Telegram Message Sent to Trader
```

---

### Layer 8: Orchestration

**Purpose**: Coordinate all components and manage scan cycles

| Component | File | Role |
|-----------|------|------|
| NSETrendScanner | `main.py` | Main orchestrator |
| ScannerScheduler | `scheduler/scanner_scheduler.py` | Scheduling engine |

**Orchestration Pattern**:
```
Every 15 minutes (configurable):
├─ Run TrendDetection strategy
├─ Run VERC strategy
├─ Run MTF strategy
├─ Run Swing strategy
├─ Run Options strategy
├─ Run Sentiment strategy
│
├─ Combine all signals
├─ Apply deduplication
├─ Validate with ReasoningEngine
├─ Check AIRulesEngine filters
├─ Score and rank
│
├─ For each valid signal:
│  ├─ Generate trade setup
│  ├─ Format alert
│  └─ Send Telegram
│
└─ Update performance metrics
```

---

## Signal Flow Diagram

### Complete End-to-End Flow

```
╔════════════════════════════════════════════════════════════════════════════════╗
║                          NSE TREND AGENT - SIGNAL FLOW                        ║
╚════════════════════════════════════════════════════════════════════════════════╝

STEP 1: DATA COLLECTION
┌─────────────────────────────┐
│ MarketScheduler             │
├─────────────────────────────┤
│ Checks if market is open    │
│ Reads stock list from config│
│ Determines scan frequency   │
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│ DataFetcher                 │
├─────────────────────────────┤
│ fetch_stock_data()          │
│ Retry 3x on failure         │
│ Yahoo Finance → DataFrame   │
└────────────┬────────────────┘
             │
             ▼ (OHLCV Data for each stock)

STEP 2: INDICATOR CALCULATION
┌─────────────────────────────┐
│ IndicatorEngine             │
├─────────────────────────────┤
│ Calculate:                  │
│ • EMA 20, 50, 100, 200      │
│ • RSI (14)                  │
│ • ATR (14)                  │
│ • Volume MA 5, 20, 30       │
│ • 20-day High/Low           │
│ • MACD                      │
└────────────┬────────────────┘
             │
             ▼ (Enriched DataFrame)

STEP 3: MARKET CONTEXT ANALYSIS
┌──────────────────────────────────┐
│ MarketContext + Sentiment        │
├──────────────────────────────────┤
│ • Analyze NIFTY trend            │
│ • Detect market regime           │
│ • Sector performance             │
│ • Volatility regime              │
│ • Broader market context         │
└──────────────┬───────────────────┘
               │
               ▼ (Market Context for signal filters)

STEP 4: SIGNAL DETECTION (6 Parallel Strategies)
┌─────────────────────┬──────────────────┬──────────────┬──────────────┬─────────────┬──────────────┐
│ TrendDetector       │ VolumeCompression│ MTFScanner   │ SwingScanner │ OptionsScanner
│                     │                  │              │              │              │ SentimentScanner
├─────────────────────┼──────────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
│ • EMA alignment     │ • Compression    │ • 1D trend   │ • Pullback   │ • IV analysis│ • NIFTY trend
│ • RSI confirmation  │ • Volume surge   │ • 4H setup   │ • Bounce     │ • Premium    │ • Running stocks
│ • Volume check      │ • Directional    │ • 1H entry   │ • Volume     │ • Distance   │ • Momentum
│ • 20-day breakout   │   breakout       │ • Confluence │ • Targets    │ • Expiry     │ • AI validation
└─────────────────────┴──────────────────┴──────────────┴──────────────┴──────────────┴──────────────┘
         │                    │                  │              │              │              │
         └────────────────────┴──────────────────┴──────────────┴──────────────┴──────────────┘
                              │
         (Multiple raw signals: TrendSignal, VERCSignal, MTFSignal, etc.)

STEP 5: SIGNAL VALIDATION & COMBINATION
┌──────────────────────────────────────────┐
│ ReasoningEngine.calculate_weighted_score │
├──────────────────────────────────────────┤
│ Weighted Factor Scoring:                 │
│ • EMA alignment (15%)                    │
│ • Volume confirmation (15%)              │
│ • RSI position (10%)                     │
│ • ATR volatility (10%)                   │
│ • VERC score (20%) - if available        │
│ • RSI divergence (10%)                   │
│ • Market context (10%)                   │
│ • Price momentum (10%)                   │
│                                          │
│ Result: Combined score 0-100             │
└────────────┬─────────────────────────────┘
             │
             ▼
┌──────────────────────────────────────────┐
│ AIStockAnalyzer (LLM-based)              │
├──────────────────────────────────────────┤
│ • Queries OpenAI/Anthropic/Groq/Google   │
│ • Provides AI reasoning                  │
│ • AI confidence 1-10                     │
│ • Recommendation (BUY/SELL/HOLD)         │
│ • Risk-reward analysis                   │
└────────────┬─────────────────────────────┘
             │
             ▼
┌──────────────────────────────────────────┐
│ CombinedSignal Object Created            │
├──────────────────────────────────────────┤
│ • Final score: 78.5                      │
│ • Recommendation: BUY                    │
│ • Entry/SL/Targets calculated           │
│ • Weighted factors breakdown             │
│ • AI reasoning included                  │
└────────────┬─────────────────────────────┘
             │
             ▼

STEP 6: SIGNAL INTELLIGENCE (NEW LAYER)
┌──────────────────────────────────────────┐
│ SignalIntelligenceExplainer              │
├──────────────────────────────────────────┤
│ Make signal UNDERSTANDABLE:              │
│ • Build reasoning chain (WHY?)           │
│ • Create pattern signature               │
│ • Run 6 validation checks                │
│ • Calculate agent confidence 0-100%      │
│ • Generate explanation text              │
└────────────┬─────────────────────────────┘
             │
             ▼
┌──────────────────────────────────────────┐
│ SignalIntelligence Object                │
├──────────────────────────────────────────┤
│ • Agent confidence: 82.3%                │
│ • Signal quality: VERY_HIGH              │
│ • Validation: All checks passed ✓        │
│ • is_valid: TRUE                         │
└────────────┬─────────────────────────────┘
             │
             ├─ is_valid == FALSE? → LOG & REJECT
             │
             └─ is_valid == TRUE ↓

STEP 7: DEDUPLICATION CHECK
┌──────────────────────────────────────────┐
│ SignalMemory (in-memory)                 │
├──────────────────────────────────────────┤
│ Recent signals cache                     │
│ Check if signal already sent today       │
└────────────┬─────────────────────────────┘
             │
├─ Duplicate? → REJECT
│
└─ New signal? ↓

┌──────────────────────────────────────────┐
│ TradeJournal (persistent)                │
├──────────────────────────────────────────┤
│ Historical signals database              │
│ Double-check against last 30 days        │
└────────────┬─────────────────────────────┘
             │
├─ Already tracked? → REJECT
│
└─ Fresh signal? ↓

STEP 8: ADDITIONAL FILTERING
┌──────────────────────────────────────────┐
│ AIRulesEngine                            │
├──────────────────────────────────────────┤
│ • Check volume_ratio threshold           │
│ • Check RSI filters                      │
│ • Market regime alignment                │
│ • Adaptive thresholds                    │
└────────────┬─────────────────────────────┘
             │
├─ Failed filter? → REJECT
│
└─ Passed? ↓

STEP 9: TRADE SETUP GENERATION
┌──────────────────────────────────────────┐
│ TradeGenerator                           │
├──────────────────────────────────────────┤
│ Calculate:                               │
│ • Entry price (current or optimized)     │
│ • Stop loss (risk management)            │
│ • Target 1 (primary)                     │
│ • Target 2 (extended)                    │
│ • Risk-reward ratio                      │
│ • Position sizing suggestion             │
└────────────┬─────────────────────────────┘
             │
             ▼

STEP 10: ALERT FORMATTING
┌──────────────────────────────────────────┐
│ NotificationManager                      │
├──────────────────────────────────────────┤
│ Format message for Telegram:             │
│ • Stock symbol & price                   │
│ • Entry/SL/Targets                       │
│ • Agent confidence %                     │
│ • Strategy type                          │
│ • Risk-reward ratio                      │
│ • Reasoning explanation                  │
│ • Additional context                     │
└────────────┬─────────────────────────────┘
             │
             ▼

STEP 11: SEND ALERT
┌──────────────────────────────────────────┐
│ AlertService.send_signal_alert()         │
├──────────────────────────────────────────┤
│ • Format Telegram message                │
│ • Send to configured chat ID             │
│ • Log alert in history                   │
│ • Record in trade journal                │
└────────────┬─────────────────────────────┘
             │
             ▼
        Trader Receives
        Telegram Alert
        with Full Context
        
        ═══════════════════════════════════════════════════════════

STEP 12: OUTCOME TRACKING (Later)
┌──────────────────────────────────────────┐
│ When Trade Completes (SL or Target hit)  │
├──────────────────────────────────────────┤
│ • Record outcome: WIN/LOSS               │
│ • Update trade journal                   │
│ • Calculate metrics                      │
└────────────┬─────────────────────────────┘
             │
             ▼
┌──────────────────────────────────────────┐
│ Pattern Learning                         │
├──────────────────────────────────────────┤
│ PatternLearningRecognizer updates:       │
│ • Pattern type success rate              │
│ • Market regime correlation              │
│ • Strategy performance metrics           │
│ • Generates learning insights            │
└────────────┬─────────────────────────────┘
             │
             ▼
┌──────────────────────────────────────────┐
│ Next Scan Cycle                          │
├──────────────────────────────────────────┤
│ • Uses learning data                     │
│ • Adjusts weights                        │
│ • Better signal quality                  │
└──────────────────────────────────────────┘
```

---

## Module Directory

### Core Modules (Foundation Layer)

#### data_fetcher.py
```
Purpose:    Fetch OHLCV data from Yahoo Finance
Key Class:  DataFetcher
Key Methods:
  - fetch_stock_data(ticker, interval, days)
  - fetch_multiple_stocks(tickers)
  - fetch_multitimeframe(ticker)
Retry Logic: 3 attempts with exponential backoff (1s, 2s, 4s)
Cache:       Multi-timeframe data caching
```

#### indicator_engine.py
```
Purpose:    Calculate technical indicators
Key Class:  IndicatorEngine
Key Methods:
  - calculate_indicators(df)
  - calculate_rsi(df, period=14)
  - calculate_atr(df, period=14)
  - calculate_macd(df)
Indicators: EMA(20,50,100,200), RSI, ATR, SMA(Volume), MACD
Output:     DataFrame with all indicators added as columns
```

#### market_context.py
```
Purpose:    Analyze market regime and context
Key Class:  MarketContext
Key Methods:
  - analyze_market_context()
  - determine_market_regime()
  - calculate_volatility_regime()
  - analyze_sector_trends()
Market Regimes: BULLISH, BEARISH, SIDEWAYS, VOLATILE, CHOPPY
```

#### market_scheduler.py
```
Purpose:    Manage trading hours and scheduling
Key Class:  MarketScheduler
Key Methods:
  - is_market_open()
  - get_next_scan_time()
  - should_skip_market()
Handles:    IST timezone, market holidays, pre-market/post-market
```

---

### Signal Detection Modules (Strategy Layer)

#### trend_detector.py
```
Purpose:    Detect uptrends and downtrends
Key Class:  TrendDetector
Key Methods:
  - detect_trend(stock_data)
Signal Logic:
  - Perfect EMA order: price > EMA20 > EMA50 > EMA100 > EMA200
  - RSI 50-65 (bullish zone)
  - Volume > 30-day MA
Output:     TrendSignal(score, recommendation, confidence)
```

#### consolidation_detector.py
```
Purpose:    Detect tight consolidations
Key Functions:
  - is_tight_consolidation(df)
  - is_valid_breakout(df)
  - is_strong_breakout(df)
Usage:      Used by TrendDetector to confirm breakouts
```

#### volume_compression.py
```
Purpose:    Detect VERC (Volume Expansion Range Compression) signals
Key Functions:
  - detect_verc(df)
  - generate_signal(df, stock)
  - scan_stocks(stocks_data)
Signal Logic:
  - Compression: Low volatility, tight range
  - Expansion: Volume surge with directional move
Output:     VERCSignal(score, breakout_direction, support/resistance)
```

#### mtf_strategy.py
```
Purpose:    Multi-timeframe analysis (1D, 4H, 1H)
Key Classes:
  - MTFStrategyScanner
  - ICTScanner (Smart Money Concepts)
Key Methods:
  - scan_stock(ticker)
  - scan_multiple_stocks(tickers)
Analysis:
  - 1D: Major trend
  - 4H: Intermediate setup
  - 1H: Entry confirmation
Output:     MTFSignal with multi-timeframe alignment score
```

#### swing_trade_scanner.py
```
Purpose:    Detect swing trade setups
Key Class:  SwingTradeScanner
Key Methods:
  - scan_stock(ticker)
  - scan_multiple_stocks(tickers)
Signal Logic:
  - Recent pullback in uptrend
  - Support level bounce
  - Volume confirmation
Output:     SwingSignal with setup quality score
```

#### options_scanner.py
```
Purpose:    Detect options-friendly setups
Key Class:  OptionsScanner
Key Methods:
  - scan_stock(ticker)
  - scan_multiple_stocks(tickers)
Analysis:
  - IV Rank levels
  - Support/Resistance distances
  - Premium decay potential
Output:     OptionsSignal with options-specific metrics
```

#### market_sentiment_analyzer.py
```
Purpose:    Analyze overall market sentiment
Key Class:  MarketSentimentAnalyzer
Key Methods:
  - analyze_market_sentiment()
  - identify_running_stocks()
  - validate_breakout_with_ai()
  - analyze_sector_trends()
Sentiment Levels:
  - STRONGLY_BULLISH
  - BULLISH
  - NEUTRAL
  - BEARISH
  - STRONGLY_BEARISH
Caching: Sentiment data cached for 15 minutes
```

#### sentiment_driven_scanner.py
```
Purpose:    Find breakouts aligned with market sentiment
Key Class:  SentimentDrivenScanner
Key Methods:
  - scan_with_sentiment(stocks)
  - analyze_stock_breakout(ticker)
  - calculate_momentum_score()
  - calculate_quality_score()
Adaptive Thresholds: Changes based on market sentiment
Output:     List of sentiment-aligned breakout signals
```

---

### Signal Validation & Scoring (Filtering Layer)

#### reasoning_engine.py
```
Purpose:    Combine weighted scoring with AI reasoning
Key Class:  ReasoningEngine
Key Methods:
  - calculate_weighted_score(indicators, rules)
  - apply_ai_reasoning(weighted_score)
  - combine_signals(weighted, ai_reasoning)
Weighting:
  - EMA alignment: 15%
  - Volume confirmation: 15%
  - RSI position: 10%
  - ATR volatility: 10%
  - VERC score: 20%
  - RSI divergence: 10%
  - Market context: 10%
Output:     CombinedSignal with final_score 0-100
```

#### signal_validator_enhanced.py
```
Purpose:    Enhanced signal validation
Key Class:  EnhancedSignalValidator
Key Methods:
  - validate_signal(signal)
  - apply_gates(signal)
  - check_thresholds()
Gates:
  1. Minimum score threshold
  2. Risk-reward ratio
  3. AI confidence
  4. Pattern validity
  5. Market alignment
  6. Volume confirmation
Output:     Boolean (pass/fail) + rejection reason
```

#### signal_intelligence_explainer.py
```
Purpose:    Make signals understandable and self-validating
Key Class:  SignalIntelligenceExplainer
Key Methods:
  - explain_signal(combined_signal, market_data)
  - build_reasoning_chain()
  - run_validation_checks()
  - calculate_agent_confidence()
Validation Checks: 6 gates including scoring, R:R, AI, pattern history
Output:     SignalIntelligence with explanation + confidence
```

#### signal_scorer.py
```
Purpose:    Score and rank signals
Key Class:  SignalScorer
Key Methods:
  - score_signal(signal)
  - rank_signals(signals)
Scoring Factors:
  - Technical quality
  - Confidence score
  - Risk-reward potential
  - Historical success
Output:     ScoredSignal with ranking priority
```

#### trade_validator.py
```
Purpose:    Validate entry/SL/target setup
Key Class:  TradeValidator
Key Methods:
  - validate_trade_setup(entry, sl, target)
  - check_risk_reward_ratio()
  - check_entry_proximity()
Validations:
  - R:R >= 1.5 (critical)
  - SL not within entry zone
  - Target achievable
Output:     Boolean (valid/invalid) + error message
```

---

### Memory & State Management (Persistence Layer)

#### signal_memory.py
```
Purpose:    In-memory signal deduplication
Key Class:  SignalMemory
Key Methods:
  - add_signal(symbol, signal_type)
  - is_duplicate(symbol, signal_type)
  - get_recent_signals()
  - sync_with_history_manager()
Storage:    Session-based (cleared on restart)
TTL:        Configurable (default: 24 hours)
Purpose:    Prevents duplicate alerts within timeframe
```

#### signal_tracker.py
```
Purpose:    Track active signals until completion
Key Class:  SignalTracker
Key Methods:
  - add_active_signal(signal)
  - check_signal_completion(symbol)
  - mark_completed(symbol)
  - get_active_signals()
Tracking:   Monitors which signals hit SL or target
Status:     ACTIVE, HIT_TARGET, HIT_SL, EXPIRED
```

#### trade_journal.py
```
Purpose:    Persistent signal/trade history
Key Class:  TradeJournal
Key Methods:
  - add_signal(signal_data)
  - add_outcome(symbol, outcome, exit_price)
  - get_closed_trades(limit)
  - get_open_trades()
Storage:    JSON file (data/trade_journal.json)
Fields:     Entry, Exit, Outcome, Duration, R:R, Strategy, etc.
```

#### history_manager.py
```
Purpose:    Manage signal/trade history
Key Class:  HistoryManager
Key Methods:
  - save_signal(signal)
  - get_signal_history(limit)
  - generate_weight_adjustments()
  - get_statistics()
Purpose:    Used by learning layer to analyze patterns
```

---

### AI & Learning Modules (Intelligence Layer)

#### ai_stock_analyzer.py
```
Purpose:    LLM-based stock analysis
Key Classes:
  - OpenAIAnalyzer
  - AnthropicAnalyzer
  - GroqAnalyzer
  - GoogleAnalyzer
Key Methods:
  - analyze_stock(symbol, market_data)
  - generate_reasoning(prompt)
LLM Usage:
  - Validates technical signals
  - Provides confidence scores
  - Generates risk-reward analysis
```

#### ai_rules_engine.py
```
Purpose:    AI-driven dynamic rule adjustment
Key Class:  AIRulesEngine
Key Methods:
  - evaluate_stock(stock_data, signal_context)
  - apply_adaptive_filters()
  - refresh_adaptive_filters()
Adapts:
  - Volume ratio thresholds
  - RSI filters
  - Market condition rules
  - Based on recent performance
```

#### ai_learning_layer.py
```
Purpose:    Analyze patterns and suggest improvements
Key Class:  AILearningLayer
Key Methods:
  - analyze_recent_trades(limit)
  - detect_failure_patterns()
  - suggest_improvements()
  - generate_ai_insights()
Learning:
  - Win/loss pattern detection
  - Strategy performance comparison
  - Filter adjustments based on data
```

#### pattern_learning_recognizer.py
```
Purpose:    Learn which signal patterns work best
Key Class:  PatternLearningRecognizer
Key Methods:
  - record_signal_outcome(signal, outcome)
  - get_pattern_insights(pattern_type)
  - get_learning_report()
Tracks:
  - Win rate by pattern type
  - Performance in market regimes
  - Avg risk-reward by pattern
  - Emerging patterns
```

#### agent_controller.py
```
Purpose:    Autonomous agent decision-making
Key Class:  AgentController
Key Methods:
  - analyze_and_decide(market_data, active_signals)
  - is_available()
  - track_outcomes(signals)
Agent Actions:
  - SCAN: Search for signals
  - WAIT: Skip this cycle
  - ANALYZE: Detailed analysis
  - ADJUST_STRATEGY: Change parameters
  - MONITOR: Watch active trades
```

---

### Performance & Optimization (Analytics Layer)

#### performance_tracker.py
```
Purpose:    Track strategy performance metrics
Key Class:  StrategyPerformanceTracker
Key Methods:
  - calculate_metrics(trades)
  - get_strategy_stats(strategy_name)
  - get_all_strategy_stats()
  - generate_performance_report()
Metrics:
  - Win rate (%)
  - Profit factor
  - Avg RR (Risk-Reward)
  - Max drawdown
  - Sharpe ratio
  - Holding time
```

#### strategy_optimizer.py
```
Purpose:    Optimize strategy weights based on performance
Key Class:  StrategyPerformanceTracker
Key Methods:
  - optimize_weights(stats)
  - get_dynamic_weights()
  - auto_adjust_thresholds()
Optimization:
  - Increases weight for high-performing strategies
  - Decreases weight for underperforming strategies
  - Auto-adjusts thresholds
```

#### factor_analyzer.py
```
Purpose:    Analyze importance of each factor
Key Class:  FactorAnalyzer
Key Methods:
  - analyze_factors(trades)
  - get_factor_importance()
  - identify_key_drivers()
Analysis:
  - Which factors most predict wins?
  - Correlation analysis
  - Feature importance ranking
```

---

### Notification & Output (Output Layer)

#### alert_service.py
```
Purpose:    Send alerts via Telegram and SMS
Key Classes:
  - AlertService (Telegram)
  - MockAlertService (Testing)
  - TelegramBotHandler (2-way communication)
Key Methods:
  - send_alert(message)
  - send_signal_alert(signal)
  - process_user_commands()
Features:
  - Telegram channel support
  - Direct chat support
  - Bot command processing
  - Message formatting
```

#### notification_manager.py
```
Purpose:    Format alert messages
Key Class:  NotificationManager
Key Methods:
  - send_signal_alert(signal)
  - send_outcome_alert(trade)
  - format_message(signal)
Message Types:
  - Signal alerts (BUY/SELL)
  - Win/loss notifications
  - Performance reports
  - Daily summaries
```

#### trade_generator.py
```
Purpose:    Calculate entry/SL/target setup
Key Class:  TradeGenerator
Key Methods:
  - generate(signal, data)
  - calculate_entry()
  - calculate_stop_loss()
  - calculate_targets()
Calculation:
  - ATR-based SL placement
  - Risk-based target calculation
  - Entry optimization
  - Risk-reward targeting
```

---

### Main Orchestrator

#### main.py (NSETrendScanner)
```
Purpose:    Orchestrate all components and manage scan cycles
Key Class:  NSETrendScanner
Key Methods:
  - __init__(): Initialize all components
  - scan(): Main scan cycle
  - run_live(): Continuous scanning
  - run_one_off(): Single scan
  - _run_trend_scan()
  - _run_verc_scan()
  - _run_mtf_scan()
  - _run_swing_scan()
  - _run_options_scan()
  - _run_sentiment_driven_scan()
Main Flow:
  1. Load configuration
  2. Fetch stock data
  3. Run all strategies
  4. Combine and validate signals
  5. Send alerts
  6. Track outcomes
  7. Update learning metrics
```

---

## Feature Implementation Map

### Feature: Trend Detection

**Requirement**: Detect uptrends and send alerts when price breaks above EMA alignment

**Code Implementation**:
1. `data_fetcher.py` → Fetch stock data
2. `indicator_engine.py` → Calculate EMAs
3. `trend_detector.py` → Detect EMA order
4. `consolidation_detector.py` → Confirm not in consolidation
5. `reasoning_engine.py` → Score signal
6. `signal_intelligence_explainer.py` → Explain signal
7. `alert_service.py` → Send alert

**Data Flow**:
```python
# In main.py _run_trend_scan()
for stock in stocks:
    df = self.data_fetcher.fetch_stock_data(stock)                  # Layer 1
    df = self.indicator_engine.calculate_indicators(df)             # Layer 2
    trend_signal = self.trend_detector.detect_trend(df)             # Layer 2
    
    if trend_signal:
        combined = self.reasoning_engine.calculate_weighted_score(  # Layer 3
            indicators=get_indicators(df),
            rule_signals={'trend': trend_signal}
        )
        intelligent = self.signal_explainer.explain_signal(         # Layer 3
            combined, market_data
        )
        
        if intelligent.is_valid:                                    # Layer 4
            msg = self.notification_manager.format_alert(intelligent)
            self.alert_service.send_alert(msg)                      # Layer 7
```

---

### Feature: VERC Detection

**Requirement**: Detect volume expansion + range compression breakouts

**Code Implementation**:
1. `volume_compression.py` → Detect compression & expansion
2. `consolidation_detector.py` → Validate breakout strength
3. `reasoning_engine.py` → Score with higher VERC weight
4. `signal_intelligence_explainer.py` → Explain signal
5. `alert_service.py` → Send alert

**Signal Type** parameter: "VERC_BREAKOUT"

---

### Feature: Multi-Timeframe Analysis

**Requirement**: Analyze 1D, 4H, 1H for alignment before signaling

**Code Implementation**:
1. `data_fetcher.py` → Fetch data for multiple timeframes
2. `mtf_strategy.py` → MTFStrategyScanner.scan_stock()
3. Multi-frame confluence checking
4. `reasoning_engine.py` → Score higher if aligned
5. Signal sent only if multiple timeframes confirm

**Signal Type** parameter: "MTF_ALIGNED"

---

### Feature: Swing Trade Detection

**Requirement**: Detect pullback + bounce patterns in trends

**Code Implementation**:
1. `swing_trade_scanner.py` → SwingTradeScanner.scan_stock()
2. Identifies pullback zones
3. Bounce confirmation
4. Volume check
5. `reasoning_engine.py` → Score swing patterns

**Signal Type** parameter: "SWING_TRADE"

---

### Feature: Market Sentiment Analysis

**Requirement**: Analyze market mood and adapt signal filtering

**Code Implementation**:
1. `market_sentiment_analyzer.py` → Analyze NIFTY
2. Classify as BULLISH/BEARISH/NEUTRAL
3. Identify sector trends
4. Find running stocks
5. `sentiment_driven_scanner.py` → Adaptive filtering
6. Modify thresholds based on sentiment
7. Apply AI validation

**Signal Type** parameter: "SENTIMENT_BREAKOUT"

---

### Feature: AI-Driven Signal Validation

**Requirement**: Use LLM to validate signals and provide reasoning

**Code Implementation**:
1. `ai_stock_analyzer.py` → Query LLM
2. Provide technical context
3. Request analysis
4. Parse response for confidence
5. `reasoning_engine.py` → Blend with rule-based score
6. AI acts as gatekeeper (confidence > 6/10)

**Integration Point**: In ReasoningEngine._combine_signals()

---

### Feature: Signal Learning & Optimization

**Requirement**: Learn which patterns work best and improve over time

**Code Implementation**:
1. `trade_journal.py` → Record all signal outcomes
2. `pattern_learning_recognizer.py` → Analyze patterns
3. Calculate win rates by pattern type
4. `strategy_optimizer.py` → Adjust weights
5. Next cycle uses optimized weights
6. Continuous improvement loop

**Update Cycle**: Every 24 hours or after 20+ signals

---

### Feature: In-Memory Deduplication

**Requirement**: Prevent duplicate signals within 24 hours

**Code Implementation**:
1. `signal_memory.py` → Track recent signals
2. Check before sending each alert
3. `trade_journal.py` → Cross-check with history
4. Skip if signal already sent today
5. Configurable TTL

**Check Point**: In main.py before calling alert_service

---

### Feature: Trade Setup Generation

**Requirement**: Calculate entry/SL/target automatically

**Code Implementation**:
1. `trade_generator.py` → TradeGenerator.generate()
2. Calculate ATR for volatility
3. Place SL based on risk tolerance
4. Calculate targets based on R:R goal
5. Validate setup with TradeValidator
6. Include in alert message

**Output Format**:
```
Entry: 3450.50
Stop Loss: 3380.00
Target 1: 3550.00 (1% upside)
Target 2: 3650.00 (5.8% upside)
Risk:Reward: 1:2.45
```

---

### Feature: Performance Reporting

**Requirement**: Track performance by strategy

**Code Implementation**:
1. `trade_journal.py` → Log each signal
2. `performance_tracker.py` → Calculate metrics
3. Win rate, profit factor, Sharpe ratio
4. Per-strategy breakdown
5. `strategy_optimizer.py` → Generate recommendations
6. `notification_manager.py` → Format report
7. Send as Telegram message

**Report Frequency**: Daily or weekly

---

## Data Flow Examples

### Example 1: Complete Trend Signal Flow

```python
# SCENARIO: TCS has perfect EMA alignment, good volume, RSI bullish

# STEP 1: Data Collection
ticker = "TCS"
df = data_fetcher.fetch_stock_data(ticker)
# Output: DataFrame with OHLCV

# STEP 2: Indicator Calculation
df = indicator_engine.calculate_indicators(df)
# Output: Added columns: EMA20, EMA50, EMA100, EMA200, RSI, ATR, Volume_MA

# STEP 3: Trend Detection
latest = df.iloc[-1]  # Most recent candle
if (latest['close'] > latest['ema_20'] > latest['ema_50'] > 
    latest['ema_100'] > latest['ema_200']):  # Perfect EMA order
    
    if 50 < latest['rsi'] < 65:  # Bullish RSI zone
        if latest['volume'] > latest['volume_ma_30'] * 1.2:  # Volume confirm
            trend_signal = TrendSignal(
                recommendation='BUY',
                score=75.0,
                confidence=8,
                entry=latest['close'],
                stop_loss=latest['close'] - 2 * latest['atr'],
                target_1=latest['close'] * 1.02,
                target_2=latest['close'] * 1.05
            )

# STEP 4: Get Market Context
market_context = market_context_engine.analyze_market_context()
# Output: market_regime='BULLISH', nifty_trend='UP', volatility='NORMAL'

# STEP 5: Reasoning Engine - Weighted Scoring
weighted_score = reasoning_engine.calculate_weighted_score(
    indicators={
        'ema_alignment_score': 85,
        'rsi_score': 75,
        'volume_score': 80,
        'atr_score': 70,
        'price_momentum': 80,
        'market_context': 'BULLISH'
    },
    rule_signals={'trend': trend_signal},
    market_context=market_context
)
# Output: WeightedScore(final_score=78.5, strength='STRONG_BUY', factors=[...])

# STEP 6: AI Reasoning
ai_analysis = ai_stock_analyzer.analyze_stock('TCS', {
    'score': 78.5,
    'indicators': {...},
    'market_context': 'BULLISH'
})
# Output: AIReasoning(recommendation='BUY', confidence=8, reasoning="Perfect EMA...", targets=[3550, 3650])

# STEP 7: Combine Signals
combined_signal = reasoning_engine.combine_signals(
    weighted_score=weighted_score,
    ai_reasoning=ai_analysis
)
# Output: CombinedSignal(final_score=79.2, recommendation='BUY', entry=3450.50, sl=3380, ...)

# STEP 8: Signal Intelligence Explanation
intelligent_signal = signal_explainer.explain_signal(
    combined_signal,
    market_data=market_context,
    signal_type='TREND_ALIGNED'
)
# Output: SignalIntelligence(
#   agent_confidence=82.3,
#   signal_quality='VERY_HIGH',
#   is_valid=True,
#   reasoning_chain=ReasoningChain(...),
#   explanation_text="I'm signaling BUY because..."
# )

# STEP 9: Deduplication Check
if not signal_memory.is_duplicate('TCS', 'TREND_ALIGNED'):
    if 'TCS' not in [t['symbol'] for t in trade_journal.get_closed_trades()]:
        
        # STEP 10: Trade Setup
        trade_setup = trade_generator.generate(intelligent_signal, market_data)
        # Output: TradeSetup(entry=3450.50, sl=3380, t1=3550, t2=3650, rr=2.45)
        
        # STEP 11: Format Alert
        alert_msg = notification_manager.format_alert(intelligent_signal, trade_setup)
        # Output: "🤖 AI AGENT SIGNAL\nBUY TCS @ 3450.50\n..."
        
        # STEP 12: Send
        alert_service.send_alert(alert_msg)
        
        # STEP 13: Log
        trade_journal.add_signal(
            symbol='TCS',
            signal_type='TREND_ALIGNED',
            entry=3450.50,
            stop_loss=3380,
            target_1=3550,
            target_2=3650,
            agent_confidence=82.3,
            reasoning=intelligent_signal.explanation_text
        )
        signal_memory.add_signal('TCS', 'TREND_ALIGNED')
```

---

### Example 2: VERC Signal Flow

```python
# SCENARIO: Stock has volume compression followed by breakout

# STEP 1-2: Data + Indicators (same as above)
df = data_fetcher.fetch_stock_data(ticker)
df = indicator_engine.calculate_indicators(df)

# STEP 3: VERC Detection (Volume Compression)
verc_signal = volume_compression.detect_verc(df)
# Looks for:
# - Last 10 candles: low volatility, volume < avg
# - Recent candles: volume > 1.5x avg + directional move
# Output: VERCSignal(
#   breakout_direction='UPSIDE',
#   compression_strength=8,
#   expansion_strength=9,
#   confidence=85,
#   support=3400, resistance=3500
# )

# STEP 4: Consolidation Check
if consolidation_detector.is_strong_breakout(df):
    # STEP 5: Score with VERC Weight
    weighted_score = reasoning_engine.calculate_weighted_score(
        indicators={...},
        rule_signals={'verc': verc_signal},
        # Note: VERC score gets 20% weight in reasoning engine
    )
    # Output: WeightedScore(final_score=82.3, factors=[...])
    
    # STEP 6-13: Rest is same as trend signal flow
    # AI validation → Signal Intelligence → Dedup → Trade Setup → Alert
```

---

### Example 3: Learning Loop

```python
# SCENARIO: Signal from Day 1 completes on Day 2

# DAY 1: Signal Generated
# Entry: 3450.50, Stop Loss: 3380, Target: 3550
# signal_type: 'TREND_ALIGNED'
# Recorded in trade_journal with signal_type

# DAY 2: Signal Outcome
# Market: Stock hit target at 3550
# Profit: 2.9%
# Risk: 2.02% (difference entry to SL)
# Risk-Reward: 1:1.44

# STEP 1: Record Outcome
trade_journal.add_outcome(
    symbol='TCS',
    entry=3450.50,
    exit=3550,
    outcome='WIN',
    hold_time_hours=24,
    risk_reward_ratio=1.44,
    market_regime='BULLISH'
)

# STEP 2: Update Pattern Learning
pattern_learner.record_signal_outcome(
    signal={'signal_type': 'TREND_ALIGNED', 'entry': 3450.50},
    outcome='WIN',
    metadata={
        'hold_time_hours': 24,
        'risk_reward_ratio': 1.44,
        'market_regime': 'BULLISH'
    }
)

# STEP 3: Analyze Patterns
report = pattern_learner.get_learning_report()
# Output:
# {
#   'TREND_ALIGNED': {
#     'total_signals': 147,
#     'winning_signals': 100,
#     'win_rate': 68.5%,
#     'avg_risk_reward': 2.12,
#     'best_regime': 'BULLISH' (71% win rate),
#     'worst_regime': 'BEARISH' (42% win rate)
#   }
# }

# STEP 4: Generate Insights
insights = pattern_learner.get_learning_report()['insights']
# [
#   'TREND_ALIGNED performing excellently (68.5%)',
#   'Works best in BULLISH markets (71% vs 42% in BEARISH)',
#   'Recommend: Prioritize TREND_ALIGNED in BULLISH markets'
# ]

# STEP 5: Next Cycle Uses Learning
# When ReasoningEngine runs next time:
# - TREND_ALIGNED signals get weight boost (+15%)
# - In BEARISH markets, TREND_ALIGNED signals get filter boost (higher threshold)
# - Result: Better signal quality due to learning
```

---

## Integration Points

### Integration Point 1: Adding a New Strategy

**To add a new trading strategy (e.g., "SuperTrend Breakout"):

1. Create new module: `src/supertrend_scanner.py`
   ```python
   class SuperTrendSignal:
       symbol: str
       score: float
       confidence: int
       entry: float
       stop_loss: float
       targets: List[float]
   
   class SuperTrendScanner:
       def scan_stock(self, ticker) -> Optional[SuperTrendSignal]:
           # Implementation
       
       def scan_multiple(self, tickers) -> List[SuperTrendSignal]:
           # Implementation
   ```

2. Add to main.py imports:
   ```python
   from supertrend_scanner import create_supertrend_scanner
   ```

3. Initialize in NSETrendScanner.__init__:
   ```python
   self.supertrend_scanner = create_supertrend_scanner()
   ```

4. Add scan method:
   ```python
   def _run_supertrend_scan(self):
       signals = self.supertrend_scanner.scan_multiple(self.stocks)
       for signal in signals:
           # Validate and send
   ```

5. Add to main scan cycle:
   ```python
   def scan(self):
       self._run_trend_scan()
       self._run_verc_scan()
       self._run_supertrend_scan()  # NEW
       self._run_mtf_scan()
       # ... etc
   ```

6. Update signal_type parameter:
   ```python
   intelligent = self.signal_explainer.explain_signal(
       combined_signal,
       market_data,
       signal_type="SUPERTREND_BREAKOUT"  # NEW
   )
   ```

---

### Integration Point 2: Adding a New Validation Gate

**To add additional validation (e.g., "News Check"):

1. Create validator function:
   ```python
   # In signal_validator_enhanced.py
   def check_news_sentiment(symbol) -> Tuple[bool, str]:
       # Call news API
       # Return (valid, reason)
   ```

2. Add to validation checks:
   ```python
   # In signal_intelligence_explainer.py _run_validation_checks()
   checks.append(SignalValidationCheck(
       check_name="News Sentiment",
       passed=check_result,
       score=sentiment_score,
       reason=f"Recent news: {sentiment}",
       critical=False
   ))
   ```

3. Higher confidence gates immediately reject (critical=True)
4. Lower gates just reduce quality score (critical=False)

---

### Integration Point 3: Adding AI Provider Support

**To add support for a new LLM (e.g., Anthropic's Claude):

1. Add to ai_stock_analyzer.py:
   ```python
   class ClaudeAnalyzer(BaseAnalyzer):
       def generate(self, messages, **kwargs):
           # Call Claude API
           return response
   ```

2. Register in create_analyzer():
   ```python
   elif provider == 'claude':
       return ClaudeAnalyzer()
   ```

3. Update config settings for API key
4. System auto-loads based on env variables

---

## New Developer Quick Start

### Day 1: Understand the Architecture

**Morning (1 hour)**:
1. Read this document (Section: Architecture & Layers)
2. Review the Signal Flow Diagram
3. Understand the 8-layer architecture

**Afternoon (1 hour)**:
1. Clone project
2. Review `README.md`
3. Set up dev environment: `.venv`, install `requirements.txt`
4. Run: `python src/main.py --test` to verify setup

**Evening (30 min)**:
1. Read through `main.py` (NSETrendScanner.__init__)
2. Note the component initialization order
3. Understand how components connect

### Day 2: Trace a Signal

**Morning (2 hours)**:
1. Pick a module to trace: `trend_detector.py`
2. Read its code completely
3. Understand TrendSignal dataclass
4. Understand detect_trend() logic

**Afternoon (2 hours)**:
1. Trace into indicator_engine.py
2. See how indicators are calculated
3. Review the formulas used
4. Understand data flow in and out

**Evening (1 hour)**:
1. Trace through reasoning_engine.py
2. See how signals get scored
3. Understand weighting system
4. Review combine_signals() logic

### Day 3: Run & Test

**Morning (2 hours)**:
1. Create test script:
   ```python
   from src.main import NSETrendScanner
   scanner = NSETrendScanner()
   scanner.scan()
   ```
2. Run scanner for 1-2 iterations
3. Observe log output
4. Understand what happens

**Afternoon (2 hours)**:
1. Review trade_journal.json output
2. See signals that were generated
3. Check deduplication logs
4. Understand what got rejected and why

**Evening (1 hour)**:
1. Review alert_service.py
2. Test with MockAlertService
3. Verify alert formatting
4. Understand Telegram integration

### Day 4: Make a Change

**Pick a small task:**

Option A: Add a new indicator to IndicatorEngine
- Add MACD or Bollinger Bands
- Use in signal scoring

Option B: Add a new validation check
- Check if stock is near 52-week high
- Add to SignalIntelligenceExplainer

Option C: Modify scoring weights
- Adjust percentages in ReasoningEngine
- Test if it improves results

**Process**:
1. Make change
2. Run tests
3. Observe impact in logs
4. Document what you changed and why

### Day 5: Full Understanding

**Review end-to-end:**
1. Data fetching (data_fetcher.py)
2. Indicator calculation (indicator_engine.py)
3. Signal detection (all strategy modules)
4. Signal validation (reasoning_engine.py)
5. Signal explanation (signal_intelligence_explainer.py)
6. Deduplication (signal_memory.py)
7. Alert formatting (notification_manager.py)
8. Alert sending (alert_service.py)
9. Outcome tracking (trade_journal.py)
10. Learning (pattern_learning_recognizer.py)

---

## Common Development Tasks

### Task 1: Add a New Indicator

**Objective**: Add RSI Divergence detection

**Files to modify**:
1. `indicator_engine.py` - Add calculation
2. `reasoning_engine.py` - Add to scoring
3. `main.py` - Update weights if needed

**Implementation**:
```python
# In indicator_engine.py
def detect_rsi_divergence(self, df):
    """
    Bullish divergence: Lower lows in price, higher lows in RSI
    Bearish divergence: Higher highs in price, lower highs in RSI
    """
    # Implementation
    return divergence_score  # 0-10 scale

# In reasoning_engine.py
'rsi_divergence': 10,  # Add to weights
```

---

### Task 2: Modify Signal Thresholds

**Objective**: Make signals stricter (reduce false positives)

**Files to modify**:
1. `reasoning_engine.py` - Increase min_score
2. `signal_validator_enhanced.py` - Add more gates
3. `config/settings.json` - Adjust thresholds

**Implementation**:
```python
# In reasoning_engine.py
self.STRATEGY_THRESHOLDS = {
    'TREND': 70,          # Was 60, now stricter
    'VERC': 72,           # Was 65
    'STRONG_BUY': 85      # Was 80
}

# In signal_validator_enhanced.py
# Add gate: Only signals in aligned market regimes
if market_regime == 'CHOPPY':
    return False, "Market too choppy"
```

---

### Task 3: Add Performance Metric

**Objective**: Track "Consecutive Wins" metric

**Files to modify**:
1. `performance_tracker.py` - Add calculation
2. `trade_journal.py` - Track state
3. `notification_manager.py` - Include in reports

**Implementation**:
```python
# In performance_tracker.py
def calculate_consecutive_wins(self, trades):
    current_streak = 0
    max_streak = 0
    for trade in trades:
        if trade.outcome == 'WIN':
            current_streak += 1
            max_streak = max(max_streak, current_streak)
        else:
            current_streak = 0
    return current_streak, max_streak
```

---

### Task 4: Debug Signal Rejection

**Objective**: Understand why signals are being rejected

**Files to review**:
1. `signal_intelligence_explainer.py` - Validation checks
2. `signal_validator_enhanced.py` - Additional gates
3. `signal_memory.py` - Deduplication
4. Log files for rejection reasons

**Process**:
```python
# Add debug logging
logger.debug(f"Signal rejected: {intelligent_signal.rejection_reason}")

# Review validation checks
for check in intelligent_signal.validation_checks:
    if not check.passed:
        logger.debug(f"  Failed: {check.check_name} - {check.reason}")

# Review deduplication
if signal_key in signal_memory.recent_signals:
    logger.debug(f"  Duplicate: {signal_key}")
```

---

### Task 5: Add New Signal Type

**Objective**: Support "GapUp_Breakout" signal type

**Files to modify**:
1. Create detection logic
2. Add to main.py scan cycle
3. Add to pattern_learning_recognizer
4. Add to alert formatting

**Implementation**:
```python
# src/gap_up_scanner.py
class GapUpDetector:
    def detect_gap_up(self, today_data, yesterday_data):
        """Gap up: today_open > yesterday_close"""
        if today_data['open'] > yesterday_data['close'] * 1.01:  # >1% gap
            return GapUpSignal(...)
        return None

# In main.py
def _run_gap_up_scan(self):
    # Implementation

# In pattern_learning_recognizer.py
pattern_db['GAPUP_BREAKOUT'] = {...}
```

---

### Task 6: Add Configuration Option

**Objective**: Add toggle for new feature

**Files to modify**:
1. `config/settings.json` - Add setting
2. `main.py` - Load and use setting

**Implementation**:
```json
// In config/settings.json
{
    "features": {
        "enable_gap_up_detection": true,
        "gap_up_minimum_percent": 1.0,
        "gap_up_min_confidence": 70
    }
}
```

```python
# In main.py __init__
self.enable_gap_up = self.config.get('features', {}).get('enable_gap_up_detection', False)

# In scan cycle
if self.enable_gap_up:
    self._run_gap_up_scan()
```

---

## Project Statistics

| Metric | Value |
|--------|-------|
| Total Python files | 35+ |
| Total lines of code | 15,000+ |
| Number of strategies | 6 |
| Number of AI providers | 4 |
| Number of validation gates | 10+ |
| Update cycle | Every 15 minutes (configurable) |
| Signal retention | 30 days |
| Max concurrent signals | Unlimited |
| Learning window | 90 days |

---

## Conclusion

The NSE Trend Agent is a sophisticated, multi-layered trading signal generator with:

- **Data Layer**: Real-time data fetching with retry logic
- **Detection Layer**: 6 parallel signal detection strategies
- **Validation Layer**: Weighted scoring + AI reasoning + gating
- **Memory Layer**: Deduplication + signal tracking
- **Learning Layer**: Pattern analysis + continuous improvement
- **Analytics Layer**: Performance tracking + optimization
- **Output Layer**: Formatted alerts via Telegram
- **Orchestration Layer**: Main scan cycle coordinator

**Key Design Principles**:
1. **Modularity**: Each component is independent
2. **Layering**: Clear separation of concerns
3. **Extensibility**: Easy to add strategies/indicators
4. **Transparency**: Full reasoning chains for all decisions
5. **Learning**: Continuous improvement from outcomes
6. **Reliability**: Retry logic + error handling
7. **Performance**: Multi-timeframe caching

**For New Developers**:
- Start with this guide to understand architecture
- Trace a signal through all layers
- Review relevant source files
- Make small modifications to learn
- Gradually take on bigger features

**Next Steps**:
- Read specific module code for details
- Run the scanner in test mode
- Review trade journal outputs
- Make your first modification
- Join the development team!

---

**Document Version**: 1.0
**Last Updated**: April 18, 2026
**For Questions**: Review module docstrings and in-code comments
