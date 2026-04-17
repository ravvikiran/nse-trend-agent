# Signal Intelligence System - Integration Guide

## Your Agent Now Understands Its Signals

Your scanner has three new superpowers:

1. **Explains** why it generates signals
2. **Validates** signals before sending them
3. **Learns** which patterns work best

This guide shows exactly where to add the code.

---

## Architecture Overview

```
┌─────────────────────────────────┐
│  ReasoningEngine (Existing)     │
│  → Generates raw signal         │
│  → Score 78.5, BUY TCS          │
└────────────────┬────────────────┘
                 │ combined_signal
                 ↓
┌─────────────────────────────────┐
│  SignalIntelligenceExplainer    │ ← NEW
│  → Explains signal              │
│  → Runs validations             │
│  → Confidence: 82.3%            │
└────────────────┬────────────────┘
                 │ intelligent_signal
                 ↓
┌─────────────────────────────────┐
│  Send Alert to Telegram         │
│  → With full explanation        │
│  → Entry/SL/Targets             │
│  → Agent confidence %           │
└────────────────┬────────────────┘
                 │ alert_sent
                 ↓
         (Signal executes)
                 │ outcome = WIN/LOSS
                 ↓
┌─────────────────────────────────┐
│  PatternLearningRecognizer      │ ← NEW
│  → Record outcome               │
│  → Update pattern stats         │
│  → Learn: TREND_ALIGNED = 68%   │
└─────────────────────────────────┘
```

---

## Step 1: Add Imports to main.py

**Location**: Top of `src/main.py` with other imports

```python
# Add these imports alongside existing ones
from signal_intelligence_explainer import (
    create_signal_intelligence_explainer,
    SignalIntelligence,
    ReasoningChain
)
from pattern_learning_recognizer import (
    create_pattern_learning_recognizer,
    PatternPerformance
)
```

---

## Step 2: Initialize Components in __init__

**Location**: In `NSETrendScanner.__init__()`, after initializing `reasoning_engine`

```python
# Inside __init__, after line ~185 where reasoning_engine is created

# ==================== NEW: Signal Intelligence System ====================
# Layer 2: Explain and validate signals
self.signal_explainer = create_signal_intelligence_explainer(
    self.trade_journal,
    self.strategy_optimizer
)
logger.info("Signal Intelligence Explainer initialized")

# Layer 3: Learn which patterns work
self.pattern_learner = create_pattern_learning_recognizer(
    self.trade_journal,
    self.strategy_optimizer
)
logger.info("Pattern Learning Recognizer initialized")

# Configuration flags
self.enable_signal_intelligence = self.config.get('agent', {}).get('enable_signal_intelligence', True)
self.min_agent_confidence = self.config.get('agent', {}).get('min_agent_confidence', 60)
```

---

## Step 3: Wrap Signal Generation

**Location**: Wherever you generate signals (in `_run_verc_scan()` or equivalent)

### Before (Existing Code):
```python
# Old way: Generate and immediately send
combined_signal = self.reasoning_engine.calculate_weighted_score(
    indicators=indicators,
    rule_signals=rule_signals,
    market_context=market_context
)

if combined_signal and combined_signal.recommendation != 'HOLD':
    # Send signal
    self.alert_service.send_signal_alert(combined_signal)
```

### After (New Way):
```python
# New way: Generate, explain, validate, then send
combined_signal = self.reasoning_engine.calculate_weighted_score(
    indicators=indicators,
    rule_signals=rule_signals,
    market_context=market_context
)

if combined_signal and combined_signal.recommendation != 'HOLD':
    
    # Layer 2: Make signal intelligent
    intelligent_signal = self.signal_explainer.explain_signal(
        combined_signal,
        market_data={
            'nifty_trend': market_context.get('nifty_trend'),
            'market_regime': market_context.get('market_regime'),
            'volatility': market_context.get('volatility')
        },
        signal_type="TREND_ALIGNED"  # or LEVEL_BREAKOUT, etc.
    )
    
    logger.info(
        f"Signal explained - Confidence: {intelligent_signal.agent_confidence:.1f}%, "
        f"Quality: {intelligent_signal.signal_quality}"
    )
    
    # Gate 1: Check agent confidence
    if intelligent_signal.agent_confidence < self.min_agent_confidence:
        logger.info(
            f"Signal rejected: Confidence {intelligent_signal.agent_confidence:.1f}% "
            f"< threshold {self.min_agent_confidence}%"
        )
        return
    
    # Gate 2: Check validity
    if not intelligent_signal.is_valid:
        logger.info(f"Signal rejected: {intelligent_signal.rejection_reason}")
        return
    
    # Gate 3: Check deduplication (existing logic)
    signal_key = f"{combined_signal.stock_symbol}_{combined_signal.recommendation}"
    if signal_key in self.signal_memory.recent_signals:
        logger.info(f"Signal duplicate detected: {signal_key}")
        return
    
    # ✅ Signal passed all gates - send it!
    alert_message = self._format_intelligent_alert(intelligent_signal)
    self.alert_service.send_alert(alert_message)
    
    # Log to trade journal with full reasoning
    self.trade_journal.add_signal(
        symbol=combined_signal.stock_symbol,
        signal_type="TREND_ALIGNED",  # Important for learning
        entry=combined_signal.entry_price,
        stop_loss=combined_signal.stop_loss,
        target1=combined_signal.target_1,
        target2=combined_signal.target_2,
        agent_confidence=intelligent_signal.agent_confidence,
        explanation=intelligent_signal.explanation_text,
        reasoning_chain=intelligent_signal.reasoning_chain.to_dict() if hasattr(intelligent_signal.reasoning_chain, 'to_dict') else {}
    )
```

---

## Step 4: Format Intelligent Alerts

**Location**: Add new method to `NSETrendScanner` class

```python
def _format_intelligent_alert(self, intelligent_signal: SignalIntelligence) -> str:
    """Format signal with full intelligence for alert."""
    
    lines = []
    
    # Header
    lines.append("🤖 AI AGENT SIGNAL\n")
    lines.append(f"{'='*50}")
    
    # Signal
    lines.append(f"\n{intelligent_signal.recommendation} {intelligent_signal.symbol}")
    lines.append(f"Entry: {intelligent_signal.entry_price:.2f}")
    lines.append(f"SL: {intelligent_signal.stop_loss:.2f}")
    lines.append(f"T1: {intelligent_signal.targets[0]:.2f}")
    if len(intelligent_signal.targets) > 1:
        lines.append(f"T2: {intelligent_signal.targets[1]:.2f}")
    
    # Quality and Confidence
    lines.append(f"\n📊 SIGNAL QUALITY: {intelligent_signal.signal_quality}")
    lines.append(f"🎯 AGENT CONFIDENCE: {intelligent_signal.agent_confidence:.1f}%")
    
    # Reasoning
    lines.append(f"\n🧠 WHY THIS SIGNAL:")
    lines.append(f"• {intelligent_signal.reasoning_chain.primary_reason}")
    for reason in intelligent_signal.reasoning_chain.supporting_reasons[:2]:
        lines.append(f"• {reason}")
    
    # Pattern
    if intelligent_signal.pattern_signature:
        lines.append(f"\n📈 PATTERN: {intelligent_signal.pattern_signature.pattern_type}")
        lines.append(f"Success rate: {intelligent_signal.success_rate_for_pattern:.1f}%")
    
    # Risk Assessment
    lines.append(f"\n⚠️  RISK:")
    if intelligent_signal.reasoning_chain.counter_indicators:
        for counter in intelligent_signal.reasoning_chain.counter_indicators:
            lines.append(f"• {counter}")
    else:
        lines.append("• No major counter-indicators")
    
    lines.append(f"\n{'='*50}")
    
    return "\n".join(lines)
```

---

## Step 5: Record Signal Outcomes for Learning

**Location**: When signals complete (in `_process_signal_outcomes()` or similar)

```python
def _record_signal_outcome(self, trade: Dict[str, Any]):
    """Record signal outcome for pattern learning."""
    
    try:
        outcome = "WIN" if trade.get('outcome') == 'WIN' else "LOSS"
        
        self.pattern_learner.record_signal_outcome(
            signal={
                'signal_type': trade.get('signal_type', 'UNKNOWN'),
                'entry': trade.get('entry_price'),
                'symbol': trade.get('symbol')
            },
            outcome=outcome,
            metadata={
                'risk_reward_ratio': trade.get('risk_reward_ratio', 0),
                'hold_time_hours': trade.get('hold_time_hours', 0),
                'market_regime': trade.get('market_regime', 'UNKNOWN'),
                'return_percent': trade.get('return_percent', 0),
                'exit_type': trade.get('exit_type', 'UNKNOWN')
            }
        )
        
        logger.info(
            f"Recorded outcome for {trade.get('symbol')}: {outcome} "
            f"({trade.get('signal_type')})"
        )
        
    except Exception as e:
        logger.error(f"Error recording signal outcome: {e}")
```

---

## Step 6: Generate Learning Reports

**Location**: Add method to generate periodic reports

```python
def _generate_intelligence_report(self) -> Dict[str, Any]:
    """Generate signal intelligence report."""
    
    learning_report = self.pattern_learner.get_learning_report()
    
    # Format for logging/Telegram
    report_text = []
    report_text.append("🤖 SIGNAL INTELLIGENCE REPORT\n")
    report_text.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    report_text.append(f"Total patterns tracked: {learning_report.get('total_patterns_tracked', 0)}")
    report_text.append(f"Signals analyzed: {learning_report.get('total_signals_analyzed', 0)}")
    report_text.append(f"Overall win rate: {learning_report.get('overall_win_rate', 0):.1f}%\n")
    
    if learning_report.get('top_performers'):
        report_text.append("🏆 TOP PATTERNS:")
        for pattern in learning_report['top_performers'][:3]:
            report_text.append(
                f"  • {pattern['pattern']}: "
                f"{pattern['win_rate']:.1f}% ({pattern['signals']} signals)"
            )
    
    if learning_report.get('insights'):
        report_text.append("\n💡 INSIGHTS:")
        for insight in learning_report['insights'][:3]:
            report_text.append(f"  • {insight['title']}")
            report_text.append(f"    {insight['action']}")
    
    logger.info("\n".join(report_text))
    return learning_report
```

---

## Step 7: Configuration

**Location**: `config/settings.json`

Add these settings:

```json
{
    "agent": {
        "enable_signal_intelligence": true,
        "min_agent_confidence": 60,
        "require_pattern_history": true
    },
    
    "signal_explanation": {
        "include_reasoning": true,
        "include_validation": true,
        "include_pattern_analysis": true,
        "explain_rejections": true
    },
    
    "pattern_learning": {
        "enabled": true,
        "min_signals_for_recommendation": 5,
        "learning_window_days": 90,
        "auto_weight_adjustment": true,
        "generate_reports": true,
        "report_frequency_hours": 24
    }
}
```

---

## Integration Checklist

- [ ] Added imports to main.py
- [ ] Initialized `signal_explainer` in `__init__`
- [ ] Initialized `pattern_learner` in `__init__`
- [ ] Wrapped signal generation with `explain_signal()`
- [ ] Added `_format_intelligent_alert()` method
- [ ] Added `_record_signal_outcome()` method
- [ ] Added `_generate_intelligence_report()` method
- [ ] Updated `config/settings.json` with new settings
- [ ] Tested with first signal generation

---

## Testing the Integration

### Test 1: Generate a Signal

```python
# Manually trigger a scan and watch for:
# ✓ Signal gets explained
# ✓ Validation checks run
# ✓ Alert includes confidence %
# ✓ Log shows signal_type for learning
```

### Test 2: Check Signal Rejection

```python
# Watch logs for rejection reasons:
# "Signal rejected: Confidence 35.0% < threshold 60%"
# "Signal rejected: Critical check failed: Risk-Reward Ratio"
# "Signal rejected: Signal quality too low"
```

### Test 3: Check Learning

```python
# After 20+ signals complete:
learning_report = self.pattern_learner.get_learning_report()
print(learning_report['top_performers'])
# Should show winning patterns with high win rates
```

---

## Expected Output

### Alert with Intelligence:

```
🤖 AI AGENT SIGNAL

==================================================

BUY TCS
Entry: 3450.50
SL: 3380.00
T1: 3550.00
T2: 3650.00

📊 SIGNAL QUALITY: VERY_HIGH
🎯 AGENT CONFIDENCE: 82.3%

🧠 WHY THIS SIGNAL:
• Perfect EMA order (20>50>100>200)
• Volume 1.8x average
• AI validation: 8/10

📈 PATTERN: TREND_ALIGNED
Success rate: 68.5%

⚠️  RISK:
• No major counter-indicators

==================================================
```

### Learning Report:

```
🤖 SIGNAL INTELLIGENCE REPORT
Generated: 2026-04-18 18:30:00

Total patterns tracked: 12
Signals analyzed: 847
Overall win rate: 52.3%

🏆 TOP PATTERNS:
  • TREND_ALIGNED: 68.5% (147 signals)
  • MA_BREAKOUT: 61.2% (89 signals)
  • VOLUME_SPIKE: 55.3% (76 signals)

💡 INSIGHTS:
  • Excellent Pattern: TREND_ALIGNED
    Increase signal weight for TREND_ALIGNED
  • Underperforming: RSI_OVERSOLD
    Consider reducing RSI_OVERSOLD pattern
```

---

## Troubleshooting

### Issue: All signals being rejected

```python
# Check minimum confidence setting
print(self.min_agent_confidence)  # Probably too high

# Lower it
self.min_agent_confidence = 50

# Or check validation checks are too strict
```

### Issue: Pattern learner shows no data

```python
# Need at least 5 signals with signal_type set
# Make sure you're recording with signal_type:
self.trade_journal.add_signal(
    signal_type="TREND_ALIGNED",  # This is required for learning
    ...
)
```

### Issue: Confidence scores too low

```python
# Check validation_checks
for check in intelligent_signal.validation_checks:
    print(f"{check.check_name}: {check.score}")

# Usually means R:R is not good enough or score is low
```

---

## Next Steps

1. ✅ Add imports
2. ✅ Initialize components
3. ✅ Wrap signal generation
4. ✅ Add alert formatting
5. ✅ Add outcome recording
6. ✅ Generate reports
7. ✅ Test thoroughly
8. ✅ Monitor learning for 1 week
9. ✅ Adjust thresholds based on results

---

## Files Modified

- `src/main.py` - 7 new sections (imports, init, signal wrapping, formatting, outcomes, reports, config)
- `config/settings.json` - New agent configuration section

## Files Created

- `src/signal_intelligence_explainer.py` (750+ lines) ✅
- `src/pattern_learning_recognizer.py` (600+ lines) ✅
- `docs/SIGNAL_INTELLIGENCE_SYSTEM.md` (comprehensive guide) ✅
- `docs/SIGNAL_INTELLIGENCE_QUICK_REF.md` (quick reference) ✅

---

## Key Takeaway

Your agent now:
1. **Thinks before acting** - Validates signals before sending
2. **Explains its reasoning** - Full chain of thought in alerts
3. **Learns continuously** - Improves signal quality over time
4. **Adapts patterns** - Emphasizes what works, de-emphasizes what doesn't

Result: More confident, understandable, and profitable signals ✅

---

**Ready to integrate? Start with Step 1! 🚀**
