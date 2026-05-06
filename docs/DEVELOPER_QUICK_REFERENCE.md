# NSE Trend Agent - Developer Quick Reference

## File Navigation Cheat Sheet

### 🎯 I want to understand...

**How signals are created**
→ Start at `main.py` (NSETrendScanner.scan)
→ Look at strategy files: `trend_detector.py`, `volume_compression.py`, `mtf_strategy.py`
→ See how they're combined in `reasoning_engine.py`

**How signals are validated**
→ `signal_intelligence_explainer.py` (main validation)
→ `signal_validator_enhanced.py` (gating)
→ `signal_memory.py` (deduplication)

**How signals are sent**
→ `notification_manager.py` (formatting)
→ `alert_service.py` (sending)
→ `trade_generator.py` (setup calculation)

**How the app learns**
→ `trade_journal.py` (stores outcomes)
→ `pattern_learning_recognizer.py` (analyzes patterns)
→ `ai_learning_layer.py` (generates insights)
→ `strategy_optimizer.py` (adjusts weights)

**How data is fetched**
→ `data_fetcher.py` (Yahoo Finance)
→ `indicator_engine.py` (calculates indicators)

**How scheduling works**
→ `market_scheduler.py` (market hours)
→ `scheduler/scanner_scheduler.py` (APScheduler)

---

## Architecture Layers (Quick Reference)

```
LAYER 1: DATA         data_fetcher.py, indicator_engine.py, market_context.py
         ↓
LAYER 2: SIGNALS      trend_detector.py, volume_compression.py, mtf_strategy.py,
                      swing_trade_scanner.py, options_scanner.py,
                      sentiment_driven_scanner.py
         ↓
LAYER 3: VALIDATION   reasoning_engine.py, signal_validator_enhanced.py,
                      signal_intelligence_explainer.py, signal_scorer.py,
                      trade_validator.py
         ↓
LAYER 4: MEMORY       signal_memory.py, signal_tracker.py, trade_journal.py,
                      history_manager.py
         ↓
LAYER 5: AI           ai_stock_analyzer.py, ai_rules_engine.py,
                      ai_learning_layer.py, agent_controller.py
         ↓
LAYER 6: ANALYTICS    performance_tracker.py, strategy_optimizer.py,
                      factor_analyzer.py, pattern_learning_recognizer.py
         ↓
LAYER 7: OUTPUT       alert_service.py, notification_manager.py,
                      trade_generator.py
         ↓
LAYER 8: ORCHESTRATION main.py, scheduler/scanner_scheduler.py
```

---

## Common Operations

### Adding a new indicator
1. Go to: `src/indicator_engine.py`
2. Add method: `def calculate_your_indicator(self, df):`
3. Return: Column added to DataFrame
4. Use in: `reasoning_engine.py` weighting

**Example**: Add RSI
```python
# indicator_engine.py
def calculate_rsi(self, df, period=14):
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    df['rsi'] = rsi
    return df
```

---

### Adding a new validation gate
1. Go to: `src/signal_intelligence_explainer.py`
2. Method: `_run_validation_checks(self, signal, market_data)`
3. Add check to `checks` list
4. Return `bool` for each check

**Example**: Add volume check
```python
# signal_intelligence_explainer.py
def _run_validation_checks(self, signal, market_data):
    checks = []
    
    # Existing checks...
    
    # NEW: Volume check
    volume_valid = market_data.get('volume', 0) > market_data.get('volume_ma_20', 1)
    checks.append(SignalValidationCheck(
        check_name="Volume Confirmation",
        passed=volume_valid,
        reason="Volume above 20-day MA" if volume_valid else "Volume too low",
        critical=False
    ))
    
    return checks
```

---

### Modifying signal scoring weights
1. Go to: `src/reasoning_engine.py`
2. Method: `calculate_weighted_score()`
3. Modify weights in `WEIGHTS` dict

**Current weights**:
```python
WEIGHTS = {
    'ema_alignment': 0.15,          # 15%
    'volume_confirmation': 0.15,    # 15%
    'rsi_position': 0.10,           # 10%
    'atr_volatility': 0.10,         # 10%
    'verc_score': 0.20,             # 20%
    'rsi_divergence': 0.10,         # 10%
    'market_context': 0.10,         # 10%
    'price_momentum': 0.10           # 10%
}
```

---

### Adding a new strategy
1. Create file: `src/your_strategy_scanner.py`
2. Define signal class and scanner class
3. Import in `main.py`
4. Add to `__init__`: `self.your_scanner = YourScanner()`
5. Add scan method: `def _run_your_scan(self):`
6. Call in `scan()` method

**Template**:
```python
# src/your_strategy_scanner.py
from dataclasses import dataclass

@dataclass
class YourSignal:
    symbol: str
    score: float
    confidence: int
    entry: float
    stop_loss: float
    targets: list

class YourScanner:
    def scan_stock(self, ticker) -> Optional[YourSignal]:
        # Detection logic here
        return YourSignal(...)
    
    def scan_multiple(self, tickers) -> List[YourSignal]:
        results = []
        for ticker in tickers:
            signal = self.scan_stock(ticker)
            if signal:
                results.append(signal)
        return results
```

---

## Data Structures

### Signal Object
```python
@dataclass
class CombinedSignal:
    symbol: str
    recommendation: str  # 'BUY', 'SELL', 'HOLD'
    score: float  # 0-100
    weighted_score: float
    ai_confidence: int  # 1-10
    entry: float
    stop_loss: float
    targets: List[float]
    reasoning: str
    factors_breakdown: Dict
    generated_at: datetime
```

### SignalIntelligence Object
```python
@dataclass
class SignalIntelligence:
    combined_signal: CombinedSignal
    agent_confidence: float  # 0-100%
    signal_quality: str  # 'VERY_HIGH', 'HIGH', 'MEDIUM', 'LOW'
    is_valid: bool
    validation_checks: List[SignalValidationCheck]
    reasoning_chain: ReasoningChain
    explanation_text: str
    rejection_reason: Optional[str]
```

### TradeSetup Object
```python
@dataclass
class TradeSetup:
    entry: float
    stop_loss: float
    target_1: float
    target_2: float
    risk_amount: float
    reward_amount: float
    risk_reward_ratio: float
    position_size_suggestion: str
```

---

## Configuration Files

### settings.json
```json
{
    "stocks": ["TCS", "INFY", "RELIANCE"],
    "scanning": {
        "enabled": true,
        "interval_minutes": 15,
        "market_open_time": "09:15",
        "market_close_time": "15:30"
    },
    "strategies": {
        "trend_detection": true,
        "verc_detection": true,
        "mtf_analysis": true,
        "swing_trading": true,
        "options_scanning": true,
        "sentiment_driven": true
    },
    "thresholds": {
        "minimum_signal_score": 65,
        "minimum_ai_confidence": 6,
        "min_risk_reward": 1.5
    },
    "features": {
        "deduplication_hours": 24,
        "learning_enabled": true,
        "auto_optimization": true
    },
    "alerts": {
        "telegram_enabled": true,
        "telegram_chat_id": "YOUR_CHAT_ID",
        "telegram_token": "YOUR_BOT_TOKEN"
    },
    "ai": {
        "provider": "openai",  # or "anthropic", "groq", "google"
        "api_key": "YOUR_API_KEY",
        "model": "gpt-3.5-turbo"
    }
}
```

---

## Logging & Debugging

### Key Log Points
```python
import logging
logger = logging.getLogger(__name__)

# In main scan cycle
logger.info(f"Scanning {len(stocks)} stocks...")
logger.debug(f"Fetched data for {ticker}")
logger.debug(f"Signal detected: {signal}")
logger.info(f"Alert sent: {symbol}")
logger.warning(f"Signal rejected: {reason}")
logger.error(f"API Error: {error}")
```

### Debug Signal Flow
```python
# main.py
scanner = NSETrendScanner()

# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Run single scan
scanner.scan()

# Review trade_journal.json
import json
with open('data/trade_journal.json') as f:
    journal = json.load(f)
    print(f"Signals generated: {len(journal)}")
    print(f"Last 5 signals: {journal[-5:]}")
```

---

## Testing

### Running Test Scan
```bash
cd /Users/ravikiran/Documents/nse-trend-agent
python -m src.main --test
```

### Testing Individual Component
```python
# test_trend_detector.py
from src.core.data_fetcher import DataFetcher
from src.core.indicator_engine import IndicatorEngine
from src.core.trend_detector import TrendDetector

fetcher = DataFetcher()
engine = IndicatorEngine()
detector = TrendDetector()

df = fetcher.fetch_stock_data('TCS')
df = engine.calculate_indicators(df)
signal = detector.detect_trend(df)

print(f"Signal: {signal}")
print(f"Score: {signal.score if signal else 'None'}")
```

### Testing Signal Validation
```python
from src.notifications.signal_intelligence_explainer import SignalIntelligenceExplainer

explainer = SignalIntelligenceExplainer()
intelligent = explainer.explain_signal(combined_signal, market_data)

print(f"Valid: {intelligent.is_valid}")
print(f"Confidence: {intelligent.agent_confidence}%")
print(f"Explanation: {intelligent.explanation_text}")
```

---

## Performance Considerations

### Caching Points
- Market data: Cached per timeframe to avoid re-fetching
- Indicator calculations: Cached in DataFrame
- Market context: Cached for 15 minutes
- AI responses: Cached for 5 minutes

### Optimization Tips
1. **Reduce stock list** for faster scans
2. **Increase interval** (30 min instead of 15 min)
3. **Disable low-value strategies** in settings
4. **Use faster AI model** (Groq instead of OpenAI)
5. **Batch similar stocks** in one call

### Performance Metrics
- Single stock scan: ~2-3 seconds
- 20 stocks scan: ~45-60 seconds
- Full signal cycle: ~2-3 minutes
- Alert sending: <1 second

---

## Common Issues & Solutions

### Issue: Duplicate signals
**Solution**: Check `signal_memory.py` and `trade_journal.py`
```python
# Review duplicates
import json
with open('data/memory_all_signals.json') as f:
    memory = json.load(f)
    print(f"Recent signals: {memory['recent_signals']}")
```

### Issue: Low signal quality
**Solution**: Adjust thresholds in `reasoning_engine.py`
```python
# In calculate_weighted_score()
if final_score < 70:  # Raise threshold
    logger.warning(f"Score too low: {final_score}")
    return None
```

### Issue: Too many alerts
**Solution**: Increase deduplication window
```python
# In settings.json
"deduplication_hours": 48  # Was 24
```

### Issue: API errors
**Solution**: Add retry logic and fallbacks
```python
# In data_fetcher.py
for attempt in range(3):
    try:
        return fetch_data()
    except Exception as e:
        if attempt == 2:
            raise
        time.sleep(2 ** attempt)
```

---

## Key Code Snippets

### Fetch stock data
```python
from src.core.data_fetcher import DataFetcher
fetcher = DataFetcher()
df = fetcher.fetch_stock_data('TCS', interval='1d', days=200)
```

### Calculate indicators
```python
from src.core.indicator_engine import IndicatorEngine
engine = IndicatorEngine()
df = engine.calculate_indicators(df)
print(df[['close', 'ema_20', 'rsi', 'atr']].tail())
```

### Detect trend
```python
from src.core.trend_detector import TrendDetector
detector = TrendDetector()
signal = detector.detect_trend(df)
if signal:
    print(f"Signal: BUY {signal.symbol} @ {signal.entry}")
```

### Score signal
```python
from src.ai.reasoning_engine import ReasoningEngine
engine = ReasoningEngine()
score = engine.calculate_weighted_score(indicators, rules)
print(f"Score: {score.final_score}")
```

### Explain signal
```python
from src.notifications.signal_intelligence_explainer import SignalIntelligenceExplainer
explainer = SignalIntelligenceExplainer()
intelligent = explainer.explain_signal(combined_signal, market_data)
print(f"Valid: {intelligent.is_valid}")
print(f"Explanation: {intelligent.explanation_text}")
```

### Send alert
```python
from src.notifications.alert_service import AlertService
alert_service = AlertService()
alert_service.send_alert("🤖 BUY TCS @ 3450")
```

---

## Git Workflow

### Creating a feature branch
```bash
git checkout -b feature/new-indicator
# ... make changes ...
git add .
git commit -m "Add RSI Divergence indicator"
git push origin feature/new-indicator
```

### Updating from main
```bash
git fetch origin
git rebase origin/main
# Fix conflicts if any
git push -f origin feature/new-indicator
```

### Merging to main
```bash
git checkout main
git pull origin main
git merge feature/new-indicator
git push origin main
```

---

## Performance Monitoring

### Check signal generation rate
```python
# In main.py after scan
print(f"Signals generated: {len(all_signals)}")
print(f"Signals sent: {len(sent_signals)}")
print(f"Rejection rate: {(len(all_signals) - len(sent_signals)) / len(all_signals) * 100:.1f}%")
```

### Check strategy breakdown
```python
from src.trade.performance_tracker import StrategyPerformanceTracker
tracker = StrategyPerformanceTracker()
stats = tracker.get_all_strategy_stats()
for strategy, stat in stats.items():
    print(f"{strategy}: Win rate {stat['win_rate']}%, RR {stat['avg_rr']:.2f}")
```

### Check learning insights
```python
from src.ai.pattern_learning_recognizer import PatternLearningRecognizer
learner = PatternLearningRecognizer()
report = learner.get_learning_report()
print(json.dumps(report, indent=2))
```

---

## Development Checklist

Before committing code:

- [ ] Code follows existing style (4-space indents, type hints)
- [ ] Docstrings added for all functions
- [ ] Error handling added (try/except)
- [ ] Logging added for key operations
- [ ] No hardcoded values (use config)
- [ ] Tested locally with sample stocks
- [ ] No circular imports
- [ ] Type hints used throughout
- [ ] Comments explain complex logic
- [ ] No print() statements (use logger)

---

## Quick Command Reference

```bash
# Setup
cd /Users/ravikiran/Documents/nse-trend-agent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run scanner
python src/main.py              # Run continuously
python src/main.py --test      # Test mode
python src/main.py --once      # Single scan

# Review results
tail -f logs/nse_trend_agent.log
cat data/trade_journal.json | python -m json.tool

# Testing
python -m pytest tests/          # Run all tests
python -m pytest tests/test_trend_detector.py -v

# Code quality
pylint src/**/*.py
black src/
mypy src/
```

---

## Resources

| Resource | Location | Purpose |
|----------|----------|---------|
| Full Architecture | `DEVELOPER_ARCHITECTURE_GUIDE.md` | Complete reference |
| Main Code | `src/main.py` | Entry point |
| Config | `config/settings.json` | Settings |
| Trade History | `data/trade_journal.json` | Past signals |
| Signal Memory | `data/memory_all_signals.json` | Recent signals |
| Logs | `logs/nse_trend_agent.log` | Execution logs |

---

## Version Info

- **Framework**: Python 3.8+
- **Main Dependencies**: pandas, ta-lib, yfinance, openai, anthropic, groq, telebot, apscheduler
- **Last Updated**: April 18, 2026
- **Maintainers**: Development Team

---

**Quick Tip**: When stuck, always check logs first! Most issues are clearly logged.
