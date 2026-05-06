# System Architecture - Market Sentiment Analysis Integration

## 🏗️ High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    NSE Trend Scanner Agent                  │
│                  (Main Entry Point: main.py)                │
└─────────────────────────────────────────────────────────────┘
                            │
                ┌───────────┴───────────┬───────────────────┐
                │                       │                   │
        ┌───────▼────────┐    ┌────────▼────────┐    ┌─────▼──────────┐
        │   Scheduler    │    │  AI Analyzer    │    │ Trade Journal  │
        │ (15-min cycles)│    │ (LLM Provider)  │    │  (Tracking)    │
        └───────┬────────┘    └────────┬────────┘    └─────┬──────────┘
                │                      │                    │
        ┌───────▼────────────────────────────────────────────┼──────┐
        │                                                    │      │
        │           Main Scan Cycle (15 minutes)            │      │
        │                                                    │      │
        └────────────────────────────────────────────────────┼──────┘
                     │
        ┌────────────┼────────────────────────────────────┐
        │            │                                    │
        │   STEP 1: Market Context Detection             │
        │   └─ MarketContextEngine.detect_context()       │
        │                                                 │
        │   STEP 2: Traditional Strategies                │
        │   ├─ TrendDetector                              │
        │   ├─ VERC Scanner                               │
        │   └─ Signal Validation                          │
        │                                                 │
        │   STEP 3: Multi-Timeframe Strategy              │
        │   └─ MTF Scanner (1D + 1H + 15m)                │
        │                                                 │
        │   ⭐ STEP 3.5: SENTIMENT-DRIVEN SCAN (NEW)      │
        │   ├─ MarketSentimentAnalyzer                    │
        │   │  ├─ Analyze market sentiment               │
        │   │  ├─ Identify running stocks                │
        │   │  └─ Validate with AI                       │
        │   │                                             │
        │   └─ SentimentDrivenScanner                     │
        │      ├─ Scan for breakouts                     │
        │      ├─ Apply adaptive filtering               │
        │      ├─ Calculate confidence scores            │
        │      └─ Generate alerts                        │
        │                                                 │
        │   STEP 4: Track Active Signals                  │
        │   └─ SignalTracker.check_levels()               │
        │                                                 │
        └────────────────────────────────────────────────┘
                            │
                    ┌───────▼────────┐
                    │  Deduplication │
                    │  ├─ In-memory   │
                    │  ├─ Signal mem  │
                    │  └─ Trade journal│
                    └────────┬────────┘
                            │
                    ┌───────▼────────┐
                    │  Alert Service │
                    │   (Telegram)   │
                    └────────┬────────┘
                            │
                    ┌───────▼────────┐
                    │   Trade Journal│
                    │   (Logging)    │
                    └────────────────┘
```

## 📊 Sentiment Analysis Component Details

```
┌────────────────────────────────────────────────┐
│     MarketSentimentAnalyzer (NEW)              │
│                                                │
│  Input: NIFTY Data (3-month)                 │
│  ├─ Price, Volume, Indicators                │
│  ├─ Sector Stocks (5 per sector)             │
│  └─ Market Breadth                           │
│                                                │
│  Processing:                                  │
│  ├─ EMA Alignment (20>50>100>200)            │
│  ├─ RSI Analysis (50-65 = bullish)           │
│  ├─ Momentum Calculation (-1 to +1)          │
│  ├─ Volatility Assessment (ATR %)           │
│  ├─ Price Trend (up/down/sideways)           │
│  └─ Sector Classification                    │
│                                                │
│  Output:                                      │
│  ├─ current_sentiment                        │
│  │  ├─ STRONGLY_BULLISH                      │
│  │  ├─ BULLISH                               │
│  │  ├─ NEUTRAL                               │
│  │  ├─ BEARISH                               │
│  │  └─ STRONGLY_BEARISH                      │
│  │                                            │
│  ├─ sentiment_strength (-1 to +1)           │
│  ├─ market_momentum (-1 to +1)              │
│  ├─ nifty_trend (UP/DOWN/SIDEWAYS)          │
│  ├─ volatility (%)                          │
│  └─ sector_trends (dict)                    │
│                                                │
│  Cache: data/market_sentiment.json           │
│  TTL: 15 minutes                             │
└────────────────────────────────────────────────┘
```

## 🔍 Sentiment-Driven Scanner Component

```
┌──────────────────────────────────────────────┐
│  SentimentDrivenScanner (NEW)                │
│                                              │
│  For each stock in watchlist:                │
│                                              │
│  ┌─ Fetch Data (3-month)                   │
│  │  └─ Price, Volume, Indicators            │
│  │                                          │
│  ├─ Calculate Metrics                      │
│  │  ├─ Price change (5-day)                │
│  │  ├─ Volume ratio                        │
│  │  ├─ RSI position                        │
│  │  ├─ EMA alignment                       │
│  │  └─ Distance from 20-day high           │
│  │                                          │
│  ├─ Apply Sentiment Threshold               │
│  │  If market is BULLISH:                  │
│  │  ├─ Min price change: 0.5-1.0%          │
│  │  ├─ Min volume: 1.2-1.5x                │
│  │  └─ Enable weak breakouts                │
│  │                                          │
│  │  If market is NEUTRAL:                  │
│  │  ├─ Min price change: 1.5%              │
│  │  ├─ Min volume: 2.0x                    │
│  │  └─ Stricter requirements                │
│  │                                          │
│  │  If market is BEARISH:                  │
│  │  └─ Skip detailed analysis (return)     │
│  │                                          │
│  ├─ Calculate Scores                       │
│  │  ├─ Momentum Score (0-10)               │
│  │  │  • Price change contribution          │
│  │  │  • Volume contribution                │
│  │  │  • RSI contribution                   │
│  │  │  • EMA position                       │
│  │  │                                       │
│  │  └─ Quality Score (0-10)                │
│  │     • EMA alignment (0-3)               │
│  │     • RSI position (0-2)                │
│  │     • Volume confirmation (0-2)         │
│  │     • Distance from high (0-2)          │
│  │     • Price above EMA100 (0-1)          │
│  │                                         │
│  ├─ Determine Breakout Type                │
│  │  ├─ TREND_ALIGNED (strongest)          │
│  │  ├─ LEVEL_BREAKOUT                     │
│  │  ├─ MA_BREAKOUT                        │
│  │  └─ MOMENTUM_BREAKOUT                  │
│  │                                         │
│  ├─ AI Validation (if available)           │
│  │  └─ Confidence Score (0-1)             │
│  │                                         │
│  ├─ Calculate Final Confidence             │
│  │  = (Quality * 0.7) + (AI * 0.3)        │
│  │  x Sentiment Multiplier                 │
│  │  (1.4x bullish, 0.4x bearish)           │
│  │                                         │
│  └─ Generate Alert Signal                  │
│     (if confidence > threshold)             │
│                                             │
│  Output: List[Signal] sorted by confidence │
│                                             │
└──────────────────────────────────────────────┘
```

## 🔄 Data Flow for One Alert

```
Stock: INFY
│
├─ DataFetcher.fetch_data("INFY", "3mo", "1d")
│  └─ Returns: DataFrame with OHLCV
│
├─ Calculate Technical Indicators
│  ├─ EMA20, EMA50, EMA100, EMA200
│  ├─ RSI(14)
│  ├─ ATR(14)
│  ├─ Volume SMA(20)
│  └─ 20-day High
│
├─ Compare with Market Sentiment
│  ├─ Get: sentiment_analyzer.current_sentiment
│  └─ Apply: threshold_table[sentiment]
│
├─ Calculate Momentum & Quality
│  ├─ Momentum: (price_change * 0.4) + (volume * 0.3) + (rsi * 0.2) + (ema * 0.1)
│  └─ Quality: ema_score + rsi_score + volume_score + high_score + ema100_score
│
├─ AI Validation (Optional)
│  ├─ Call: ai_analyzer.analyze_generic(prompt)
│  └─ Get: is_valid, reason, confidence
│
├─ Calculate Final Confidence
│  ├─ Base: Quality / 10 * Sentiment_Multiplier
│  └─ Final: (Base * 0.7) + (AI * 0.3)
│
├─ Deduplication Check
│  ├─ In-memory: signal_key in previous_signals?
│  ├─ Persistent: signal_memory.is_duplicate(symbol)?
│  └─ Journal: trade_journal.check_signal_exists(symbol)?
│
├─ If confidence > min_confidence:
│  │
│  ├─ Format Alert
│  │  ├─ Symbol, Price, Change
│  │  ├─ RSI, Volume Ratio
│  │  ├─ Support/Resistance
│  │  ├─ Confidence Score
│  │  └─ Market Context
│  │
│  ├─ Send Alert
│  │  └─ AlertService.send_alert(formatted_alert)
│  │
│  └─ Log to Trade Journal
│     ├─ symbol, strategy, entry_price
│     ├─ stop_loss, targets
│     ├─ quality_score, confidence
│     └─ indicators
│
└─ Alert Sent! ✅
```

## 📈 Complete Signal Processing Pipeline

```
Raw Market Data
     ↓
[DataFetcher] ←─────────────────┐
     ↓                          │
Multiple Stocks OHLCV Data      │
     ↓                          │
     ├──→ [TrendDetector]       │
     │    └→ Trend Signals      │
     │                          │
     ├──→ [VERCScanner]         │
     │    └→ VERC Signals       │
     │                          │
     ├──→ [MTFScanner]          │
     │    └→ MTF Signals        │
     │                          │
     └──→ [SentimentScanner] ←──┤
          ├─→ [SentimentAnalyzer]
          │   ├─→ NIFTY Analysis
          │   ├─→ Sector Analysis
          │   └─→ Sentiment Level
          │
          ├─→ Calculate Metrics
          ├─→ Apply Filters
          ├─→ AI Validation
          └─→ Confidence Score
                    ↓
           All Signals Combined
                    ↓
           [Deduplication Layer]
           ├─ In-memory check
           ├─ Signal memory
           └─ Trade journal check
                    ↓
           [Alert Service]
           ├─ Format alerts
           └─ Send Telegram
                    ↓
           [Trade Journal]
           └─ Log for analysis
                    ↓
           Trader Receives Alert
```

## 🎯 Key Integration Points

### 1. Main Scan Cycle
Location: `main.py` in `scan()` method
```python
# Step 3.5: NEW - Run Sentiment-Driven Scanner
self._run_sentiment_driven_scan()
```

### 2. Initialization
Location: `main.py` in `NSETrendScanner.__init__`
```python
self.sentiment_analyzer = create_market_sentiment_analyzer(
    data_fetcher=self.data_fetcher,
    ai_analyzer=self.ai_analyzer
)

self.sentiment_driven_scanner = create_sentiment_driven_scanner(
    data_fetcher=self.data_fetcher,
    sentiment_analyzer=self.sentiment_analyzer,
    ai_analyzer=self.ai_analyzer
)
```

### 3. Data Dependencies
```
Requires:
├─ DataFetcher (already initialized)
├─ AI Analyzer (already initialized)
└─ Settings (config/settings.json)

Provides:
├─ Market Sentiment Data
├─ Running Stocks List
├─ Breakout Signals
└─ Confidence Scores
```

## 🔌 Configuration Influence

Settings → Scanner Behavior:

```
enable_sentiment_analysis
├─ TRUE: Run sentiment analysis
└─ FALSE: Skip sentiment scanning

sentiment_min_confidence (0.0-1.0)
├─ 0.5: Many alerts (low threshold)
├─ 0.7: Balanced (medium threshold)
└─ 0.9: Few alerts (high threshold)

max_sentiment_signals_per_scan (1-5)
├─ 1: One alert per scan (conservative)
├─ 3: Three alerts per scan (balanced)
└─ 5: Five alerts per scan (aggressive)

enable_market_sentiment_alerts
├─ TRUE: Alert on sentiment changes
└─ FALSE: Silent sentiment analysis
```

## 📊 Performance Metrics

### Execution Time Per Cycle
- Market Sentiment Analysis: ~20 seconds
  - NIFTY data fetch: ~5s
  - Sector analysis: ~10s
  - Calculations: ~5s

- Running Stocks Detection: ~30 seconds
  - 100 stocks * 0.3s each

- AI Validation (top signals): ~5-15 seconds
  - 2-5 signals * 2-3s each

- Alert Generation: ~2 seconds

**Total: ~60 seconds per 15-minute cycle** (acceptable overhead)

### Storage
- Sentiment cache: ~2KB per update
- Signal history: ~1KB per signal
- Yearly storage: ~50MB

## 🔐 Data Flow Isolation

Sentiment analysis operates independently:
- Doesn't modify existing signals
- Adds new signal type: SENTIMENT_BREAKOUT
- Uses separate deduplication
- Own alert formatting
- Separate trade journal entries

No impact on existing strategies if disabled.

## 📞 Extension Points

Future enhancements can:
- Add real-time news sentiment
- Include social media signals
- Integrate options flow analysis
- Add correlation analysis
- Machine learning predictions

All integrated through MarketSentimentAnalyzer interface.

---

**System is modular, extensible, and non-invasive to existing functionality.**
