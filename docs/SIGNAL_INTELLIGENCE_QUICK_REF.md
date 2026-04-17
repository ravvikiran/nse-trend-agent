# Signal Intelligence Quick Reference

## Three Systems Working Together

| System | File | Does What | Output |
|--------|------|-----------|--------|
| **Layer 1** | `reasoning_engine.py` | Generates signals | Raw signal (score, recommendation) |
| **Layer 2** | `signal_intelligence_explainer.py` | Explains signals | Intelligent signal (why, validation, confidence) |
| **Layer 3** | `pattern_learning_recognizer.py` | Learns from outcomes | Pattern insights (what works) |

---

## Quick Start Integration

### Step 1: Add imports to main.py
```python
from signal_intelligence_explainer import create_signal_intelligence_explainer
from pattern_learning_recognizer import create_pattern_learning_recognizer
```

### Step 2: Initialize in __init__
```python
self.signal_explainer = create_signal_intelligence_explainer(
    self.trade_journal,
    self.strategy_optimizer
)

self.pattern_learner = create_pattern_learning_recognizer(
    self.trade_journal,
    self.strategy_optimizer
)
```

### Step 3: Use in signal generation
```python
# After generating signal from reasoning_engine
combined_signal = reasoning_engine.calculate_weighted_score(...)

# Make it intelligent
intelligent_signal = self.signal_explainer.explain_signal(
    combined_signal,
    market_data,
    signal_type="TREND_ALIGNED"
)

# Check if signal is valid
if intelligent_signal.is_valid:
    # Send alert with explanation
    alert_text = f"{intelligent_signal.explanation_text}\n"
    alert_text += f"Entry: {intelligent_signal.entry_price}\n"
    alert_text += f"Stop Loss: {intelligent_signal.stop_loss}\n"
    self.alert_service.send_alert(alert_text)
else:
    # Log rejection
    logger.info(f"Signal rejected: {intelligent_signal.rejection_reason}")
```

### Step 4: Learn from outcomes
```python
# When signal completes
outcome = "WIN" if exit_price > entry_price else "LOSS"

self.pattern_learner.record_signal_outcome(
    signal={'signal_type': 'TREND_ALIGNED', 'entry': entry_price},
    outcome=outcome,
    metadata={
        'risk_reward_ratio': rr_ratio,
        'hold_time_hours': hours,
        'market_regime': market_regime
    }
)
```

---

## Signal Objects

### CombinedSignal (From reasoning_engine)
```python
combined_signal.stock_symbol       # "TCS"
combined_signal.entry_price        # 3450.50
combined_signal.stop_loss          # 3380.00
combined_signal.target_1           # 3550.00
combined_signal.recommendation     # "BUY"
combined_signal.final_score        # 78.5
combined_signal.weighted_score     # WeightedScore object
combined_signal.ai_reasoning       # AIReasoning object
```

### SignalIntelligence (From explainer)
```python
# All fields from CombinedSignal PLUS:

intelligent_signal.reasoning_chain          # ReasoningChain
intelligent_signal.validation_checks        # List[ValidationCheck]
intelligent_signal.pattern_signature        # PatternSignature
intelligent_signal.agent_confidence         # 82.3 (0-100%)
intelligent_signal.signal_quality           # "VERY_HIGH"
intelligent_signal.explanation_text         # Human-readable
intelligent_signal.is_valid                 # True/False
intelligent_signal.rejection_reason         # Why rejected
intelligent_signal.success_rate_for_pattern # 68.5 (historical)
```

---

## Key Classes & Methods

### SignalIntelligenceExplainer

```python
# Create
explainer = create_signal_intelligence_explainer(trade_journal, optimizer)

# Main method
intelligent_signal = explainer.explain_signal(
    combined_signal,          # From reasoning engine
    market_data,              # Market context
    signal_type="TREND_ALIGNED"  # Pattern type
)

# Access results
print(intelligent_signal.reasoning_chain.primary_reason)
print(intelligent_signal.validation_checks)
print(intelligent_signal.agent_confidence)
print(intelligent_signal.explanation_text)
```

### ReasoningChain

```python
chain = intelligent_signal.reasoning_chain

chain.primary_reason              # Main factor
chain.supporting_reasons          # List of confirmations
chain.counter_indicators          # Things against signal
chain.confidence_factors          # Dict of factor scores
chain.final_confidence            # Overall 0-100%
```

### SignalValidationCheck

```python
for check in intelligent_signal.validation_checks:
    print(f"{check.check_name}: {check.reason}")
    print(f"  Passed: {check.passed}")
    print(f"  Score: {check.score}")
    print(f"  Critical: {check.critical}")
```

### PatternLearningRecognizer

```python
# Create
learner = create_pattern_learning_recognizer(trade_journal, optimizer)

# Record outcome
learner.record_signal_outcome(
    signal={'signal_type': 'TREND_ALIGNED', 'entry': 3450.50},
    outcome="WIN",
    metadata={
        'risk_reward_ratio': 2.45,
        'hold_time_hours': 2.5,
        'market_regime': 'BULLISH'
    }
)

# Get insights
insights = learner.get_pattern_insights("TREND_ALIGNED")
report = learner.get_learning_report()

# Get best patterns
best_patterns = learner.get_best_patterns(limit=5)
```

### PatternPerformance

```python
perf = learner.pattern_performance['TREND_ALIGNED']

perf.pattern_name                 # "TREND_ALIGNED"
perf.total_signals                # 147
perf.winning_signals              # 100
perf.losing_signals               # 47
perf.win_rate                      # 68.5
perf.avg_risk_reward              # 2.12
perf.best_market_regime           # "BULLISH"
perf.worst_market_regime          # "BEARISH"
```

---

## Decision Tree: Should We Send Signal?

```
Signal generated?
├─ No → Do nothing
└─ Yes → Explain signal
   │
   ├─ Run validation checks
   │  ├─ Critical check fails?
   │  │  ├─ Yes → REJECT
   │  │  └─ No → Continue
   │  │
   │  └─ Agent confidence < 40?
   │     ├─ Yes → REJECT
   │     └─ No → Continue
   │
   ├─ Calculate signal quality
   │  ├─ VERY_HIGH (80%+) → SEND with confidence
   │  ├─ HIGH (60-79%) → SEND with caution
   │  ├─ MEDIUM (50-59%) → SEND but speculative flag
   │  └─ LOW (<50%) → REJECT
   │
   └─ Send with explanation
      ├─ Agent confidence
      ├─ Why generated
      ├─ Validation results
      └─ Historical win rate
```

---

## Example: Full Signal Flow

```python
# 1. Generate signal (ReasoningEngine)
combined_signal = reasoning_engine.calculate_weighted_score(
    indicators={'ema_alignment': 85, 'rsi': 58, 'volume': 1.8},
    rule_signals={'buy': True},
    market_context={'trend': 'BULLISH'}
)
# Result: Score 78.5, BUY recommendation

# 2. Make it intelligent (Explainer)
intelligent_signal = signal_explainer.explain_signal(
    combined_signal,
    market_data={'nifty_trend': 'BULLISH', 'market_regime': 'BULLISH'},
    signal_type="TREND_ALIGNED"
)

# What happens inside:
# • Build reasoning: EMA alignment is primary reason
# • Create signature: TREND_ALIGNED_BULLISH pattern
# • Run checks: Score ✓, R:R ✓, AI ✓, Pattern ✓
# • Calculate confidence: 82.3%
# • Assess quality: VERY_HIGH
# • Generate explanation: Full text

# 3. Check validity
if intelligent_signal.is_valid:
    print("VALID - Send signal")
    print(f"Confidence: {intelligent_signal.agent_confidence}%")
    print(f"Quality: {intelligent_signal.signal_quality}")
    print(intelligent_signal.explanation_text)
else:
    print(f"REJECTED - {intelligent_signal.rejection_reason}")

# 4. Later, when signal completes
if exit_hit_target:
    pattern_learner.record_signal_outcome(
        signal={'signal_type': 'TREND_ALIGNED'},
        outcome='WIN',
        metadata={'hold_time_hours': 2.5, 'rr': 2.45}
    )

# 5. System learns
learning_report = pattern_learner.get_learning_report()
print(f"TREND_ALIGNED now: {learning_report['top_performers'][0]['win_rate']}% win rate")
```

---

## Alert Format Example

When sending Telegram alert:

```
🤖 SIGNAL INTELLIGENCE ALERT

BUY TCS @ 3450.50
────────────────────

📊 SIGNAL QUALITY: VERY_HIGH
🎯 AGENT CONFIDENCE: 82.3%

WHY THIS SIGNAL?
✓ Perfect EMA order (primary)
✓ RSI bullish zone
✓ Volume 1.8x average
✓ AI validation: 8/10

✅ VALIDATION:
✓ Score: 78.5/100
✓ R:R: 1:2.45
✓ AI: 8/10
✓ Pattern: 68.5% win rate

TARGET 1: 3550.00 (2.9%)
TARGET 2: 3650.00 (5.8%)
STOP LOSS: 3380.00 (2.3%)

PATTERN: TREND_ALIGNED (68.5% historical)
MARKET: BULLISH (works well here)
```

---

## Configuration Checklist

```json
{
    "enable_signal_intelligence": true,
    "min_agent_confidence": 60,
    "signal_explanation_details": "full",
    "learning_enabled": true,
    "min_signals_for_learning": 5,
    "auto_weight_adjustment": true
}
```

---

## Debugging

### Why was signal rejected?

```python
if not intelligent_signal.is_valid:
    print(intelligent_signal.rejection_reason)
    for check in intelligent_signal.validation_checks:
        if check.critical and not check.passed:
            print(f"  Critical failure: {check.check_name}")
            print(f"  Reason: {check.reason}")
```

### Why does agent have low confidence?

```python
print(f"Reasoning confidence: {intelligent_signal.reasoning_chain.final_confidence}")
for check in intelligent_signal.validation_checks:
    print(f"{check.check_name}: {check.score}/10")
print(f"Pattern quality: {intelligent_signal.pattern_signature.momentum_level}")
```

### Is a pattern working?

```python
insights = pattern_learner.get_pattern_insights("TREND_ALIGNED")
print(f"Win rate: {insights['win_rate']}")
print(f"Total: {insights['total_signals']}")
print(f"Recommendation: {insights['recommendation']}")
```

---

## Metrics to Monitor

| Metric | Target | Good | Bad |
|--------|--------|------|-----|
| **Agent Confidence** | 70%+ | 75-85% | <50% |
| **Signal Quality** | HIGH+ | VERY_HIGH | LOW |
| **Win Rate by Pattern** | 50%+ | 60-70% | <40% |
| **Validation Pass Rate** | 80%+ | 85-95% | <70% |
| **Pattern Consistency** | Stable | Varies <5% | Varies >15% |

---

## Next: Integration into main.py

See next section for code examples on integrating all three layers.
