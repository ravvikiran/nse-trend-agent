# Crypto Feature Implementation - Quick Reference

## TL;DR

**Goal:** Port NSE Trend Agent's advanced features to crypto trading app:
- Web UI dashboard (Flask)
- Top5 signal selection (not all signals)
- Signal update mechanism (recurring top5 get progress alerts)
- Trade journal & learning system
- SL/target validation

**Estimated effort:** 3-5 days

---

## Files to Copy from NSE Project

### 1. UI Layer (Complete)
```
COPY these directories into crypto project:
├── templates/                    (5 HTML files)
│   ├── dashboard.html
│   ├── trades.html
│   ├── performance.html
│   ├── analysis.html
│   └── settings.html
├── static/
│   ├── css/dashboard.css
│   └── js/
│       ├── dashboard.js
│       ├── trades.js
│       ├── performance.js
│       ├── analysis.js
│       └── settings.js
└── src/api.py                   (Flask API backend)
```

### 2. Core Logic Modules (Python)

**Essential - Must Port:**
```
src/
├── signal_memory.py          # Deduplication + daily tracking + update detection
├── trade_journal.py          # Complete trade logging
├── signal_scorer.py          # NEW: Scoring 0-100
├── trade_validator.py        # SL/target validation (strengthen if needed)
├── strategy_optimizer.py     # Auto-weight adjustment
├── pattern_learning.py       # Pattern insights
└── (optional) ai_learning_layer.py  # AI-powered insights (needs LLM)
```

**Already exist in crypto? Adapt these:**
```
src/
├── main.py                   # Integrate top5, updates, learning here
├── indicator_engine.py       # Already have - ensure outputs match scorer needs
├── data_fetcher.py           # Already have - add get_current_price()
└── alert_service.py          # Add format_signal_update() method
```

---

## Critical Code Snippets

### 1. Top5 Selection (in main.py)

```python
from strategies.signal_scorer import SignalScorer

# After collecting all signals from all strategies:
all_signals = trend_signals + verc_signals + mtf_signals

# Score each
for sig in all_signals:
    indicators = self.indicator_engine.calculate(sig['symbol'])
    sig['score'] = self.signal_scorer.score_signal(sig, indicators)

# Sort and select top 5
all_signals.sort(key=lambda x: x['score'], reverse=True)
top5 = all_signals[:5]

# Process ONLY these 5
for sig in top5:
    self._process_signal(sig)
```

### 2. Update Detection (in signal_memory.py)

```python
def get_signals_sent_today(self) -> List[Dict]:
    today = datetime.utcnow().date()
    return [s for s in self.all_signals 
            if datetime.fromisoformat(s['generated_at']).date() == today]

def should_send_update(self, signal: Dict) -> Tuple[bool, Optional[Dict]]:
    """Return (is_update, previous_signal)."""
    prev = self.get_signal_status(signal['symbol'], signal['type'])
    return (prev is not None), prev
```

### 3. Update Alert Format (in alert_service.py)

```python
def format_update(self, new_sig: Dict, prev: Dict) -> str:
    current = prev['current_price']
    entry = prev['entry']
    pnl = ((current - entry) / entry) * 100
    
    return f"""🔄 UPDATE - #{new_sig['rank']} {new_sig['symbol']}
   P&L: {pnl:+.1f}% | Current: ${current:.2f}
   T1: {'✅' if prev['highest_target_hit'] >= 1 else '❌'}
   T2: {'✅' if prev['highest_target_hit'] >= 2 else '❌'}
   New Score: {new_sig['score']:.0f}/100
"""
```

### 4. Validation (in trade_validator.py)

```python
def validate(self, signal, indicators):
    errors = []
    
    # Score
    if signal['score'] < 60:
        errors.append("Score < 60")
    
    # SL
    sl_pct = abs((signal['stop_loss'] - signal['entry']) / signal['entry'] * 100)
    if not (1.0 <= sl_pct <= 5.0):
        errors.append(f"SL % out of range: {sl_pct:.1f}")
    
    # R:R
    risk = abs(signal['entry'] - signal['stop_loss'])
    t1_reward = abs(signal['targets'][0] - signal['entry'])
    rr = t1_reward / risk
    if rr < 1.5:
        errors.append(f"R:R too low: {rr:.1f}")
    
    return {'valid': len(errors)==0, 'errors': errors}
```

### 5. Learning Cycle (in main.py)

```python
def run_learning_if_needed(self):
    closed = self.trade_journal.get_closed_trades(limit=100)
    
    if len(closed) >= 20:
        # Analyze
        insights = self.pattern_learning.analyze_patterns()
        logger.info(f"Insights: {insights}")
        
        # Optimize
        new_weights = self.strategy_optimizer.optimize_weights()
        self.signal_scorer.update_weights(new_weights)  # Apply next scan
        
        logger.info(f"Applied new weights: {new_weights}")
```

---

## API Endpoints Checklist

**From existing NSE api.py - implement ALL:**

- [x] `GET /api/dashboard`
- [x] `GET /api/market-status`
- [x] `GET /api/trades/open`
- [x] `GET /api/trades/history`
- [x] `GET /api/trades/<id>`
- [x] `GET /api/performance/summary`
- [x] `GET /api/performance/by-strategy`
- [x] `GET /api/performance/pnl-curve`
- [x] `GET /api/settings`
- [x] `POST /api/settings`
- [x] `GET /api/scanner/status`
- [x] `POST /api/scanner/start`
- [x] `POST /api/scanner/stop`

**NEW for top5:**
- [ ] `GET /api/signals/top5` - returns current top 5 with rank, score, current_price

---

## Data Model Cheatsheet

### Signal Object
```python
signal = {
    'signal_id': 'BTCUSDT_TREND_001',
    'symbol': 'BTCUSDT',
    'signal_type': 'TREND',  # or 'VERC', 'MTF'
    'rank': 1,              # 1-5
    'score': 85.5,          # 0-100
    'entry': 45000.00,
    'stop_loss': 43500.00,
    'targets': [46000, 47500],
    'direction': 'BUY',
    'strategy': 'TREND',
    'timestamp': '2026-04-24T10:30:00Z',
}
```

### Trade Object
```python
trade = {
    'trade_id': '...',
    'symbol': 'ETHUSDT',
    'strategy': 'VERC',
    'entry': 3200.00,
    'exit': 3400.00,
    'stop_loss': 3100.00,
    'targets': [3300, 3500],
    'outcome': 'WIN',  # or 'LOSS', 'OPEN', 'TIMEOUT'
    'rr_achieved': 2.1,
    'targets_hit': [1],
    'holding_days': 2.5,
    'quality': 'A',
}
```

---

## Configuration (config/settings.json)

```json
{
  "trading": {
    "max_signals_per_day": 5,
    "min_signal_score": 60
  },
  "signals": {
    "send_updates": true,
    "update_min_progress_pct": 5,
    "update_max_hours": 24
  },
  "validation": {
    "min_risk_reward": 1.5,
    "max_stop_loss_pct": 5.0,
    "min_volume_ratio": 1.2
  },
  "learning": {
    "enabled": true,
    "auto_optimize": true,
    "min_trades_for_optimization": 20
  }
}
```

---

## Testing Commands

```bash
# Start UI
python src/api.py

# Test endpoints
curl http://localhost:5000/api/dashboard
curl http://localhost:5000/api/signals/top5

# Start scanner (separate terminal)
python src/main.py

# Check logs
tail -f logs/scanner.log | grep -E "(TOP5|UPDATE|SIGNAL)"

# Verify data files
cat data/trade_journal.json | jq '.trades[-1]'
cat data/memory_all_signals.json | jq '.signals[0]'
```

---

## Debug Checklist

**Problem:** "Only 2 signals sent instead of 5"
- [ ] Are there at least 5 signals generated after scoring? Check logs
- [ ] Are validation filters too strict? Temporarily lower `min_signal_score`
- [ ] Are duplicates blocking? Check `signal_memory.is_duplicate()`

**Problem:** "UPDATE not sent for recurring signal"
- [ ] Is `send_updates` = true in config?
- [ ] Is signal still in top5 today? (top5 list changes)
- [ ] Check `should_send_update()` logic

**Problem:** "UI shows blank/no data"
- [ ] Is Flask running? Check port 5000
- [ ] API endpoints returning data? Test with curl
- [ ] JS console errors? Open DevTools (F12)
- [ ] CORS errors? Verify flask-cors installed

**Problem:** "Learning not optimizing"
- [ ] Have 20+ closed trades? Check `trade_journal.get_closed_trades()`
- [ ] Learning cycle called? Check logs for "Running learning cycle"
- [ ] See insights? Check logs for "INSIGHT" messages

---

## File Changes Overview

```
crypto-app/
├── NEW FILES (6):
│   ├── src/signal_scorer.py           (80 lines)
│   ├── src/trade_journal.py           (200 lines)
│   ├── src/strategy_optimizer.py      (150 lines)
│   ├── src/pattern_learning.py        (120 lines)
│   ├── src/api.py                     (COPY from NSE)
│   └── templates/ + static/           (COPY from NSE)
│
├── MODIFIED FILES (3):
│   ├── src/main.py                    (+100 lines: top5, updates, learning)
│   ├── src/alert_service.py           (+30 lines: format_update)
│   └── src/signal_memory.py           (+50 lines: daily tracking)
│
└── CONFIG (1):
    └── config/settings.json           (+new keys)
```

---

## Learning System Output Example

Log output after 20 trades:

```
[INFO] Learning cycle triggered: 24 closed trades analyzed
[INFO] INSIGHT: TREND win rate 68% (excellent) → Recommend INCREASE weight
[INFO] INSIGHT: VERC win rate 32% (poor) → Recommend DECREASE weight
[INFO] INSIGHT: RSI > 70 correlates with losses - filter tightened
[INFO] Optimized weights: {'TREND': 1.10, 'VERC': 0.65, 'MTF': 1.0}
[INFO] Adaptive filters updated: {'rsi_max': 60, 'volume_ratio_min': 1.8}
[INFO] Learning cycle complete
```

---

## Daily Workflow After Implementation

**Each market day:**
1. Scanner runs every 15 minutes
2. Each run: generates signals → scores → top5 selected → alerts sent
3. If signal already in top5 → UPDATE sent instead of NEW
4. All signals logged to `trade_journal.json`
5. At market close: check if 20+ trades closed → run learning cycle
6. Learning updates weights for next day's scanning

**Each morning:**
1. Open UI at `http://localhost:5000`
2. Check Dashboard: open trades, today's P&L
3. Check Trades: any updates on positions?
4. Check Performance: weekly stats
5. Adjust strategy if needed in Settings

---

## Final Checklist

Before declaring done:

- [ ] UI renders at `http://localhost:5000`
- [ ] Dashboard shows real metrics from trade_journal.json
- [ ] Scanner sends max 5 signals per cycle (not more)
- [ ] Duplicate signal within 24h gets blocked
- [ ] Same signal in top5 next day → UPDATE alert received
- [ ] UPDATE alert shows: current price, P&L %, target status, new rank
- [ ] All signals have score ≥60 before sending
- [ ] All signals have SL 1-5% from entry
- [ ] All signals have R:R ≥ 1.5:1
- [ ] Trade journal has complete data for all signals
- [ ] After 20 closed trades, learning cycle runs (check logs)
- [ ] Strategy weights change after learning cycle
- [ ] `/api/signals/top5` returns JSON with 5 items

---

## One-Liner Summary

**Port NSE's battle-tested signal scoring, learning, and UI system to crypto, then add top5 selection + update mechanism for recurring signals.**

---

**Last updated:** 2026-04-24  
**Reference:** NSE Trend Agent at `/Users/ravikiran/Documents/nse-trend-agent/`
