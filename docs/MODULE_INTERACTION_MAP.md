# NSE Trend Agent - Module Interaction Map & Troubleshooting

## Module Interaction Diagram

### Data Flow Network

```
┌────────────────────────────────────────────────────────────────┐
│                    MAIN ORCHESTRATOR                           │
│                     (main.py)                                  │
│  NSETrendScanner                                               │
└────────────────────────────────────────────────────────────────┘
                              │
         ┌────────────────────┼────────────────────┐
         │                    │                    │
         ▼                    ▼                    ▼
    ┌─────────┐          ┌──────────┐      ┌──────────────┐
    │ Market  │          │ Schedule │      │ Config       │
    │ Context │          │ Manager  │      │ Manager      │
    │(market_ │          │(scheduler│      │(config/      │
    │context. │          │/scanner_ │      │settings.json)│
    │py)      │          │scheduler │      │              │
    └────┬────┘          │.py)      │      └──────────────┘
         │               └──────────┘
         │
         ▼
    ┌──────────────────────────────────────────────┐
    │   DATA COLLECTION LAYER                      │
    ├──────────────────────────────────────────────┤
    │ DataFetcher (data_fetcher.py)                │
    │  • fetch_stock_data()                        │
    │  • fetch_multitimeframe()                    │
    │  • Retry logic (3x)                          │
    │  • Cache multi-timeframe data                │
    └────────────┬─────────────────────────────────┘
                 │ (DataFrame with OHLCV)
                 ▼
    ┌──────────────────────────────────────────────┐
    │   INDICATOR CALCULATION LAYER                │
    ├──────────────────────────────────────────────┤
    │ IndicatorEngine (indicator_engine.py)        │
    │  • calculate_indicators()                    │
    │  • EMA(20,50,100,200)                        │
    │  • RSI, ATR, SMA, MACD                       │
    │  • Output: Enriched DataFrame                │
    └────────────┬─────────────────────────────────┘
                 │ (DataFrame with indicators)
                 ▼
    ┌──────────────────────────────────────────────┐
    │   SIGNAL DETECTION LAYER                     │
    ├──────────────────────────────────────────────┤
    │                                              │
    │ ┌──────────────┐  ┌──────────────┐          │
    │ │TrendDetector │  │VolumeCompress│          │
    │ │& Consolidat. │  │(VERC)        │          │
    │ │detector      │  │              │          │
    │ └──────┬───────┘  └────────┬─────┘          │
    │        │                   │                │
    │ ┌──────────────┐  ┌──────────────┐          │
    │ │MTFScanner    │  │SwingScanner  │          │
    │ │(multi-tf)    │  │              │          │
    │ └────────┬─────┘  └────────┬─────┘          │
    │          │                 │                │
    │ ┌──────────────┐  ┌──────────────┐          │
    │ │OptionsScanner│ │Sentiment     │          │
    │ │              │  │DrivenScanner │          │
    │ └────────┬─────┘  └────────┬─────┘          │
    │          │                 │                │
    │ (All return type-specific signals)          │
    └────────┬──────────┬────────┬────────────────┘
             │          │        │
             ▼          ▼        ▼
    ┌─────────────────────────────────────┐
    │   SIGNAL VALIDATION & SCORING       │
    ├─────────────────────────────────────┤
    │ ReasoningEngine                     │
    │ (reasoning_engine.py)               │
    │ • Weighted factor scoring           │
    │ • Combines multiple strategies      │
    │ • Applies AI reasoning              │
    │ Output: CombinedSignal              │
    │         (score 0-100)               │
    └────────────┬────────────────────────┘
                 │
                 ▼
    ┌─────────────────────────────────────────┐
    │   AI ANALYSIS                           │
    ├─────────────────────────────────────────┤
    │ AIStockAnalyzer                         │
    │ (ai_stock_analyzer.py)                  │
    │ • OpenAI / Anthropic / Groq / Google   │
    │ • Validates signals with LLM           │
    │ • Provides AI confidence               │
    │ Output: AIReasoning                    │
    │         (confidence 1-10)              │
    └────────────┬────────────────────────────┘
                 │
                 ▼
    ┌────────────────────────────────────────────┐
    │   SIGNAL INTELLIGENCE & EXPLANATION        │
    ├────────────────────────────────────────────┤
    │ SignalIntelligenceExplainer                │
    │ (signal_intelligence_explainer.py)         │
    │ • Builds reasoning chain                   │
    │ • Runs 6 validation checks                 │
    │ • Calculates agent confidence              │
    │ • Generates explanation text               │
    │ Output: SignalIntelligence                 │
    │         (is_valid: bool)                   │
    └────────────┬────────────────────────────────┘
                 │ (Only if is_valid == True)
                 ▼
    ┌────────────────────────────────────────────┐
    │   DEDUPLICATION CHECK                      │
    ├────────────────────────────────────────────┤
    │ SignalMemory (signal_memory.py)            │
    │ • In-memory recent signals cache           │
    │ • Checks for duplicates                    │
    │ Output: Is this signal new?                │
    └────────────┬────────────────────────────────┘
                 │ (Skip if duplicate)
                 ▼
    ┌────────────────────────────────────────────┐
    │   ADDITIONAL FILTERS                       │
    ├────────────────────────────────────────────┤
    │ AIRulesEngine (ai_rules_engine.py)         │
    │ • Adaptive volume ratio checks             │
    │ • RSI filters                              │
    │ • Market regime alignment                  │
    │ Output: Should this signal be sent?        │
    └────────────┬────────────────────────────────┘
                 │ (Skip if fails filters)
                 ▼
    ┌────────────────────────────────────────────┐
    │   TRADE SETUP GENERATION                   │
    ├────────────────────────────────────────────┤
    │ TradeGenerator (trade_generator.py)        │
    │ • Calculate entry price                    │
    │ • Place stop loss (ATR-based)              │
    │ • Calculate targets (R:R based)            │
    │ • Validate with TradeValidator             │
    │ Output: TradeSetup                         │
    │         (entry, SL, targets)               │
    └────────────┬────────────────────────────────┘
                 │
                 ▼
    ┌────────────────────────────────────────────┐
    │   ALERT FORMATTING                         │
    ├────────────────────────────────────────────┤
    │ NotificationManager                        │
    │ (notification_manager.py)                  │
    │ • Format Telegram message                  │
    │ • Include entry/SL/targets                 │
    │ • Add agent confidence %                   │
    │ • Add reasoning explanation                │
    │ Output: Alert message string               │
    └────────────┬────────────────────────────────┘
                 │
                 ▼
    ┌────────────────────────────────────────────┐
    │   SEND ALERT                               │
    ├────────────────────────────────────────────┤
    │ AlertService (alert_service.py)            │
    │ • Send Telegram message                    │
    │ • Log in history                           │
    │ Output: Alert sent to trader               │
    └────────────┬────────────────────────────────┘
                 │
                 ▼
    ┌────────────────────────────────────────────┐
    │   RECORD IN JOURNAL                        │
    ├────────────────────────────────────────────┤
    │ TradeJournal (trade_journal.py)            │
    │ • Record signal details                    │
    │ • Entry/SL/Target prices                  │
    │ • Signal type & reason                     │
    │ • AI confidence                            │
    │ Storage: data/trade_journal.json            │
    └────────────┬────────────────────────────────┘
                 │
                 ▼
    ┌────────────────────────────────────────────┐
    │   OUTCOME TRACKING (Later)                 │
    ├────────────────────────────────────────────┤
    │ SignalTracker (signal_tracker.py)          │
    │ • Monitor if signal hit SL or target       │
    │ • Record WIN/LOSS                          │
    │ • Update trade_journal with outcome        │
    │ Triggered: When SL or target hit           │
    └────────────┬────────────────────────────────┘
                 │
                 ▼
    ┌────────────────────────────────────────────┐
    │   LEARNING & OPTIMIZATION                  │
    ├────────────────────────────────────────────┤
    │ PatternLearningRecognizer                  │
    │ (pattern_learning_recognizer.py)           │
    │ • Record signal outcome                    │
    │ • Calculate pattern success rate           │
    │ • Analyze by market regime                 │
    │                                            │
    │ AILearningLayer                            │
    │ (ai_learning_layer.py)                     │
    │ • Detect failure patterns                  │
    │ • Suggest improvements                     │
    │                                            │
    │ PerformanceTracker                         │
    │ (performance_tracker.py)                   │
    │ • Track metrics (win rate, RR, etc)       │
    │                                            │
    │ StrategyOptimizer                          │
    │ (strategy_optimizer.py)                    │
    │ • Adjust strategy weights                  │
    │ • Auto-adjust thresholds                   │
    └────────────┬────────────────────────────────┘
                 │
                 ▼
    ┌────────────────────────────────────────────┐
    │   NEXT CYCLE USES LEARNING                 │
    │   (Weights adjusted for better signals)    │
    └────────────────────────────────────────────┘
```

---

## Component Call Graph

```
main.py::NSETrendScanner.scan()
│
├─> _run_trend_scan()
│   ├─> DataFetcher.fetch_stock_data()
│   ├─> IndicatorEngine.calculate_indicators()
│   ├─> TrendDetector.detect_trend()
│   ├─> ConsolidationDetector.is_tight_consolidation()
│   ├─> ReasoningEngine.calculate_weighted_score()
│   ├─> AIStockAnalyzer.analyze_stock()
│   ├─> SignalIntelligenceExplainer.explain_signal()
│   ├─> SignalMemory.is_duplicate()
│   ├─> AIRulesEngine.evaluate_stock()
│   ├─> TradeGenerator.generate()
│   ├─> TradeValidator.validate_trade_setup()
│   ├─> NotificationManager.send_signal_alert()
│   ├─> AlertService.send_alert()
│   └─> TradeJournal.add_signal()
│
├─> _run_verc_scan()
│   ├─> DataFetcher.fetch_stock_data()
│   ├─> IndicatorEngine.calculate_indicators()
│   ├─> VolumeCompression.detect_verc()
│   ├─> ConsolidationDetector.is_strong_breakout()
│   ├─> ReasoningEngine.calculate_weighted_score()
│   └─> [Rest same as trend scan]
│
├─> _run_mtf_scan()
│   ├─> DataFetcher.fetch_multitimeframe()
│   ├─> IndicatorEngine.calculate_indicators() x3 (1D, 4H, 1H)
│   ├─> MTFStrategyScanner.scan_stock()
│   ├─> ReasoningEngine.calculate_weighted_score()
│   └─> [Rest same as trend scan]
│
├─> _run_swing_scan()
│   ├─> DataFetcher.fetch_stock_data()
│   ├─> IndicatorEngine.calculate_indicators()
│   ├─> SwingTradeScanner.scan_stock()
│   ├─> ReasoningEngine.calculate_weighted_score()
│   └─> [Rest same as trend scan]
│
├─> _run_options_scan()
│   ├─> DataFetcher.fetch_stock_data()
│   ├─> IndicatorEngine.calculate_indicators()
│   ├─> OptionsScanner.scan_stock()
│   ├─> ReasoningEngine.calculate_weighted_score()
│   └─> [Rest same as trend scan]
│
└─> _run_sentiment_driven_scan()
    ├─> MarketSentimentAnalyzer.analyze_market_sentiment()
    ├─> SentimentDrivenScanner.scan_with_sentiment()
    ├─> DataFetcher.fetch_stock_data()
    ├─> IndicatorEngine.calculate_indicators()
    ├─> AIStockAnalyzer.validate_breakout_with_ai()
    ├─> ReasoningEngine.calculate_weighted_score()
    └─> [Rest same as trend scan]

[After all scans]
├─> HistoryManager.update_trading_history()
├─> TradeJournal.get_closed_trades()
├─> PatternLearningRecognizer.analyze_patterns()
├─> PerformanceTracker.calculate_metrics()
└─> StrategyOptimizer.optimize_weights()
```

---

## Import Dependency Map

```
main.py
├─ data_fetcher.py
├─ indicator_engine.py
├─ market_context.py
├─ market_scheduler.py
├─ trend_detector.py
│  └─ consolidation_detector.py
├─ volume_compression.py
├─ mtf_strategy.py
├─ swing_trade_scanner.py
├─ options_scanner.py
├─ market_sentiment_analyzer.py
├─ sentiment_driven_scanner.py
├─ reasoning_engine.py
│  └─ ai_stock_analyzer.py
│     └─ [openai, anthropic, groq, google clients]
├─ signal_intelligence_explainer.py
│  └─ signal_scorer.py
├─ signal_memory.py
├─ ai_rules_engine.py
├─ trade_generator.py
│  └─ trade_validator.py
├─ notification_manager.py
├─ alert_service.py
├─ trade_journal.py
├─ history_manager.py
├─ performance_tracker.py
├─ strategy_optimizer.py
├─ pattern_learning_recognizer.py
├─ ai_learning_layer.py
├─ factor_analyzer.py
├─ signal_tracker.py
└─ scheduler/scanner_scheduler.py
   └─ apscheduler
```

---

## Cross-Module Communication

### Message Types

```
1. Signal Objects
   TrendSignal → ReasoningEngine
   VERCSignal → ReasoningEngine
   MTFSignal → ReasoningEngine
   SwingSignal → ReasoningEngine
   OptionsSignal → ReasoningEngine
   SentimentSignal → ReasoningEngine
   
2. Combined Signals
   CombinedSignal → AIStockAnalyzer → SignalIntelligenceExplainer
   
3. Intelligence
   SignalIntelligence → TradeGenerator → NotificationManager
   
4. Trade Setups
   TradeSetup → AlertService / TradeJournal
   
5. Outcomes
   TradeOutcome → PatternLearningRecognizer → StrategyOptimizer
```

### Data Passing Patterns

```
Pattern 1: Object Passing
└─ module_a() → creates DataClass → module_b() receives DataClass

Pattern 2: Dictionary Passing
└─ module_a() → creates Dict → module_b() receives Dict

Pattern 3: Direct Computation
└─ module_a() → computes value → module_b() reads DataFrame

Pattern 4: Async File Storage
└─ module_a() writes JSON → module_b() reads JSON (later)
   Used for: TradeJournal, SignalMemory
```

---

## Troubleshooting Guide

### Problem Category 1: No Signals Generated

#### Symptom: Zero signals for all stocks
```
Logs show: "Scanning 20 stocks... Generated 0 signals"
```

**Diagnosis Steps**:
```python
# Step 1: Check data fetching
from src.core.data_fetcher import DataFetcher
fetcher = DataFetcher()
df = fetcher.fetch_stock_data('TCS')
if df.empty or df is None:
    print("ERROR: No data returned")
    
# Step 2: Check indicators
from src.core.indicator_engine import IndicatorEngine
engine = IndicatorEngine()
df = engine.calculate_indicators(df)
print(df[['close', 'ema_20', 'ema_50', 'rsi']].tail())
if df['ema_20'].isna().all():
    print("ERROR: Indicators not calculated")

# Step 3: Check detection logic
from src.core.trend_detector import TrendDetector
detector = TrendDetector()
signal = detector.detect_trend(df)
print(f"Trend signal: {signal}")
if signal is None:
    print("No trend detected - check condition logic")
```

**Common Causes**:
| Cause | Fix |
|-------|-----|
| Market is closed | Check `market_scheduler.py` is_market_open() |
| Bad stock symbols | Check `config/settings.json` stock list |
| Data fetch failure | Check internet, Yahoo Finance limits |
| Thresholds too strict | Lower `minimum_signal_score` in settings |
| All strategies disabled | Enable strategies in `config/settings.json` |

---

#### Symptom: Only one or two signals, not many
```
Logs show: "Generated 2 signals out of 20 stocks"
```

**Diagnosis**:
```python
# Check individual strategy performance
from src.trade.performance_tracker import StrategyPerformanceTracker
tracker = StrategyPerformanceTracker()
stats = tracker.get_all_strategy_stats()

for strategy, stat in stats.items():
    print(f"{strategy}:")
    print(f"  Signals: {stat['total_signals']}")
    print(f"  Win rate: {stat['win_rate']}%")
    if stat['total_signals'] == 0:
        print(f"  WARNING: No signals from this strategy!")
```

**Common Causes**:
| Cause | Fix |
|-------|-----|
| Market not in signal regime | Check market sentiment (BULLISH/BEARISH) |
| Recent losses reduced weights | Check `strategy_optimizer.py` adjustments |
| Deduplication too aggressive | Increase `deduplication_hours` |
| AI filter rejecting signals | Lower AI confidence threshold |
| Validation gates too strict | Review `signal_intelligence_explainer.py` checks |

---

### Problem Category 2: Too Many Duplicate Signals

#### Symptom: Same stock signaled multiple times in one scan
```
Logs show: "TCS: 3 signals generated in one scan"
```

**Diagnosis**:
```python
# Check signal memory
from src.ai.signal_memory import SignalMemory
memory = SignalMemory()
print(f"Recent signals: {memory.recent_signals}")

# Check trade journal for duplicates
import json
with open('data/trade_journal.json') as f:
    journal = json.load(f)
    from collections import Counter
    symbols = [s['symbol'] for s in journal]
    duplicates = [s for s, count in Counter(symbols).items() if count > 1]
    print(f"Duplicate symbols: {duplicates}")
```

**Common Causes**:
| Cause | Fix |
|-------|-----|
| Multiple strategies detecting same setup | This is normal! Signals are combined |
| Deduplication not working | Check `signal_memory.py` initialization |
| TTL expired | Increase `deduplication_hours` |
| Journal not loaded | Verify `trade_journal.json` file exists |

**Note**: Multiple detections from different strategies are **GOOD** - they all get combined into one stronger signal!

---

### Problem Category 3: Low Signal Quality

#### Symptom: Signals generated but mostly failing
```
Journal shows: "Win rate: 32% (should be 50%+)"
```

**Diagnosis**:
```python
# Analyze failed trades
import json
with open('data/trade_journal.json') as f:
    journal = json.load(f)
    
wins = [t for t in journal if t['outcome'] == 'WIN']
losses = [t for t in journal if t['outcome'] == 'LOSS']

print(f"Win rate: {len(wins) / len(journal) * 100:.1f}%")

# Find common patterns in losses
loss_patterns = {}
for trade in losses:
    pattern_type = trade.get('signal_type', 'UNKNOWN')
    if pattern_type not in loss_patterns:
        loss_patterns[pattern_type] = []
    loss_patterns[pattern_type].append(trade)

for pattern, trades in loss_patterns.items():
    print(f"\n{pattern}: {len(trades)} losses")
    for trade in trades[:3]:
        print(f"  Entry: {trade['entry']}, SL: {trade['sl']}, Market close: ???")
```

**Common Causes**:
| Cause | Fix |
|-------|-----|
| Thresholds too low | Increase `minimum_signal_score` to 75+ |
| Wrong market regime | Add sentiment check to filters |
| SL placement too tight | Increase ATR multiplier in `trade_generator.py` |
| AI model not confident | Increase `minimum_ai_confidence` threshold |
| Strategy weights imbalanced | Run `strategy_optimizer.py` to rebalance |

---

### Problem Category 4: Alerts Not Sending

#### Symptom: No Telegram messages received
```
Logs show: "Alert should be sent" but no message arrives
```

**Diagnosis**:
```python
# Step 1: Check alert service configuration
import json
with open('config/settings.json') as f:
    config = json.load(f)
    print(f"Telegram enabled: {config['alerts']['telegram_enabled']}")
    print(f"Chat ID: {config['alerts']['telegram_chat_id']}")
    print(f"Token (first 10): {config['alerts']['telegram_token'][:10]}...")
    
# Step 2: Test alert service directly
from src.notifications.alert_service import AlertService
service = AlertService()
try:
    service.send_alert("Test message from NSE Agent")
    print("✓ Alert sent successfully")
except Exception as e:
    print(f"✗ Alert failed: {e}")

# Step 3: Check logs for errors
import subprocess
result = subprocess.run(['grep', '-i', 'alert', 'logs/nse_trend_agent.log'], 
                       capture_output=True, text=True)
print("Alert-related logs:")
print(result.stdout)
```

**Common Causes**:
| Cause | Fix |
|-------|-----|
| Token invalid/expired | Regenerate token from BotFather |
| Chat ID wrong | Get correct ID from bot (send /start) |
| Network blocked | Check firewall/proxy settings |
| Alert service disabled | Set `telegram_enabled: true` in config |
| Message too long | Telegram max 4096 chars, check formatting |

---

### Problem Category 5: High API Costs

#### Symptom: OpenAI/Anthropic bills are high
```
OpenAI usage: $50/day (too high)
```

**Diagnosis**:
```python
# Count API calls
import re
with open('logs/nse_trend_agent.log') as f:
    logs = f.read()
    
openai_calls = len(re.findall(r'Calling OpenAI', logs))
total_tokens = sum(
    int(m.group(1)) 
    for m in re.finditer(r'tokens_used: (\d+)', logs)
)

print(f"OpenAI calls: {openai_calls}")
print(f"Total tokens: {total_tokens}")
print(f"Avg cost: ${total_tokens * 0.0015 / 1000:.2f}")  # Approx for gpt-3.5
```

**Common Causes & Solutions**:
| Cause | Fix |
|-------|-----|
| Too many API calls | Increase interval (30 min instead of 15) |
| Expensive model | Switch to cheaper: Groq or gpt-3.5-turbo |
| Long prompts | Shorten AI analysis prompts |
| All stocks analyzed | Reduce stock list or analyze fewer stocks |
| AI disabled | Disable in settings if cost too high |

**Optimization**:
```json
// In config/settings.json
{
    "ai": {
        "provider": "groq",  // Cheaper option
        "model": "mixtral-8x7b-32768",  // Free tier available
        "cache_responses": true,  // Cache AI responses
        "cache_ttl_minutes": 60
    }
}
```

---

### Problem Category 6: Data Fetch Failures

#### Symptom: Frequent "Failed to fetch data" errors
```
Logs show: "ERROR: Failed to fetch TCS after 3 retries"
```

**Diagnosis**:
```python
# Test data fetcher
from src.core.data_fetcher import DataFetcher
fetcher = DataFetcher()

tickers = ['TCS', 'INFY', 'RELIANCE']
for ticker in tickers:
    try:
        df = fetcher.fetch_stock_data(ticker)
        print(f"{ticker}: ✓ {len(df)} rows")
    except Exception as e:
        print(f"{ticker}: ✗ {e}")

# Check internet connectivity
import requests
try:
    r = requests.get('https://finance.yahoo.com', timeout=5)
    print(f"Yahoo Finance: ✓ {r.status_code}")
except Exception as e:
    print(f"Yahoo Finance: ✗ {e}")
```

**Common Causes**:
| Cause | Fix |
|-------|-----|
| Internet down | Check connection, try ping google.com |
| Yahoo Finance blocked | Use VPN or check if IP banned |
| Ticker not found | Verify stock symbol (NSE symbols end with .NS) |
| Rate limited | Increase timeout or add delays |
| Temporarily unavailable | Retry, issue usually resolves in minutes |

---

### Problem Category 7: Performance Issues (Slow Scans)

#### Symptom: Scans taking too long
```
Expected: ~2 minutes for 20 stocks
Actual: ~8 minutes
```

**Diagnosis**:
```python
# Time each component
import time
from src.main import NSETrendScanner

scanner = NSETrendScanner()

# Time data fetch
start = time.time()
df = scanner.data_fetcher.fetch_stock_data('TCS')
print(f"Data fetch: {time.time() - start:.2f}s")

# Time indicator calculation
start = time.time()
df = scanner.indicator_engine.calculate_indicators(df)
print(f"Indicators: {time.time() - start:.2f}s")

# Time trend detection
start = time.time()
signal = scanner.trend_detector.detect_trend(df)
print(f"Trend detection: {time.time() - start:.2f}s")
```

**Common Causes**:
| Cause | Fix |
|-------|-----|
| Large stock list | Reduce stocks or use separate scans |
| Slow internet | Check connection speed |
| MTF analysis enabled | Disable or reduce timeframes |
| All AI calls | Reduce AI usage or use faster provider (Groq) |
| Logging level DEBUG | Change to INFO in production |
| System resources | Free up RAM/CPU, close other apps |

**Optimization**:
```json
{
    "scanning": {
        "interval_minutes": 30,  // Was 15
        "batch_size": 5,  // Process 5 stocks in parallel
        "timeout_seconds": 10,  // Skip slow stocks
        "cache_data": true  // Cache for 5 minutes
    }
}
```

---

### Problem Category 8: Learning Not Improving

#### Symptom: Win rate not improving over time
```
Week 1: 45% win rate
Week 2: 42% win rate
Week 3: 41% win rate (getting worse!)
```

**Diagnosis**:
```python
# Check learning data
from src.ai.pattern_learning_recognizer import PatternLearningRecognizer
learner = PatternLearningRecognizer()
report = learner.get_learning_report()

print("Win rates by strategy:")
for strategy, data in report.items():
    if 'win_rate' in data:
        print(f"  {strategy}: {data['win_rate']}%")

print("\nWin rates by market regime:")
for regime, data in report.get('by_regime', {}).items():
    print(f"  {regime}: {data['win_rate']}%")

# Check if optimization is running
from src.trade.strategy_optimizer import StrategyOptimizer
optimizer = StrategyOptimizer()
weights = optimizer.get_dynamic_weights()
print(f"\nStrategy weights: {weights}")
```

**Common Causes**:
| Cause | Fix |
|-------|-----|
| Learning disabled | Enable: `"learning_enabled": true` |
| Insufficient data | Need 20+ trades for meaningful patterns |
| Market changed | Update thresholds manually |
| Optimization too aggressive | Reduce weight adjustment magnitude |
| Wrong patterns identified | Review failed trades manually |

**Manual Fix**:
```json
{
    "features": {
        "auto_optimization": false  // Disable auto
    },
    "manual_strategy_weights": {
        "TREND": 0.25,  // Increase
        "VERC": 0.15,   // Decrease
        "MTF": 0.20,
        "SWING": 0.20,
        "OPTIONS": 0.12,
        "SENTIMENT": 0.08
    }
}
```

---

### Problem Category 9: Configuration Issues

#### Symptom: Settings not being applied
```
Changed config but scanner still uses old settings
```

**Diagnosis**:
```python
# Check configuration loading
from src.main import NSETrendScanner
scanner = NSETrendScanner()
print(f"Loaded config: {scanner.config}")

# Verify specific settings
print(f"Min score threshold: {scanner.config.get('thresholds', {}).get('minimum_signal_score')}")
print(f"Stocks to scan: {scanner.stocks}")
print(f"Telegram enabled: {scanner.config.get('alerts', {}).get('telegram_enabled')}")
```

**Common Causes**:
| Cause | Fix |
|-------|-----|
| JSON syntax error | Use JSON validator, check commas/braces |
| File not saved | Save config file after editing |
| Wrong file path | Verify `config/settings.json` exists |
| Capitalization wrong | JSON keys are case-sensitive |
| Scanner not restarted | Restart scanner to reload config |

**Validation**:
```bash
# Check JSON syntax
python -m json.tool config/settings.json

# If valid, output shown; if invalid, error displayed
```

---

### Problem Category 10: Integration Issues

#### Symptom: Component A works alone but fails with Component B
```
TrendDetector works fine
AIStockAnalyzer works fine
But together they fail
```

**Diagnosis**:
```python
# Test component integration
from src.core.trend_detector import TrendDetector
from src.ai.ai_stock_analyzer import AIStockAnalyzer
from src.ai.reasoning_engine import ReasoningEngine

# Step 1: Trend detection
detector = TrendDetector()
signal = detector.detect_trend(df)
print(f"Signal type: {type(signal)}")
print(f"Signal fields: {signal.__dict__ if signal else 'None'}")

# Step 2: AI analysis
analyzer = AIStockAnalyzer()
ai_result = analyzer.analyze_stock('TCS', market_data)
print(f"AI result type: {type(ai_result)}")

# Step 3: Reasoning engine
engine = ReasoningEngine()
combined = engine.calculate_weighted_score({...}, {'trend': signal})
print(f"Combined type: {type(combined)}")
```

**Common Causes**:
| Cause | Fix |
|-------|-----|
| Type mismatch | Ensure signal is correct type (TrendSignal, etc) |
| Missing fields | Check dataclass has all required fields |
| None returned | Handle None cases with `if signal:` |
| API key missing | Add to config if using AI |
| Import error | Check all imports in main.py |

---

## Quick Debug Checklist

When something breaks:

```
□ Check logs: tail -f logs/nse_trend_agent.log
□ Check config: cat config/settings.json | python -m json.tool
□ Check data: cat data/trade_journal.json | python -m json.tool | head -20
□ Test data fetch: python -c "from src.core.data_fetcher import DataFetcher; ..."
□ Test internet: ping 8.8.8.8
□ Check market hours: python -c "from src.scheduler.market_scheduler import ..."
□ Verify API keys: echo $OPENAI_API_KEY (not in logs!)
□ Check Telegram bot: Send test message manually
□ Review recent changes: git log --oneline -5
□ Restart scanner: Stop and start fresh
```

---

## Performance Benchmarks

### Expected Metrics

| Operation | Expected Time | Alert |
|-----------|---------------|-------|
| Fetch single stock | 0.5-1s | >2s |
| Calculate indicators | 0.2-0.3s | >1s |
| Trend detection | 0.1s | >0.5s |
| AI analysis (OpenAI) | 2-3s | >5s |
| AI analysis (Groq) | 0.5-1s | >2s |
| Full scan 1 stock | 3-5s | >10s |
| Full scan 20 stocks | 60-120s | >300s |
| Send alert | 0.5s | >2s |

### System Requirements

- **Minimum**: 2GB RAM, 2 Mbps internet
- **Recommended**: 4GB RAM, 10 Mbps internet
- **Optimal**: 8GB RAM, 50+ Mbps internet

---

## Learning Resources

**For debugging issues**:
1. Always check logs first
2. Review recent git changes
3. Test components individually
4. Check configuration
5. Verify API keys and permissions
6. Test internet connectivity
7. Review data in JSON files

**For extending code**:
1. Read the module you're modifying
2. Check existing patterns in codebase
3. Write type hints
4. Add logging
5. Test locally before committing
6. Update documentation

---

**Version**: 1.0  
**Last Updated**: April 18, 2026  
**For help**: Check specific section above or review DEVELOPER_ARCHITECTURE_GUIDE.md
