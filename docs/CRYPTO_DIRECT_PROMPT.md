# AI Coding Assistant Prompt

**Copy and paste this entire prompt to your AI coding assistant (Claude, ChatGPT, etc.)**

---

## Context

I have an existing cryptocurrency trading application that:
- Fetches OHLCV data from Binance/Coinbase via API
- Calculates technical indicators (EMA, RSI, ATR, Volume MA)
- Detects trading signals using technical rule-based systems
- Already has stop loss and target calculations based on chart patterns and indicators in different rule files
- Sends alerts via Telegram
- Stores basic trade history

I want to enhance it with advanced features from the **NSE Trend Agent** (a production NSE stock scanner). That system has:
- Full web UI dashboard (Flask + JS + Chart.js)
- Comprehensive trade journaling
- AI-powered learning that improves signals over time
- Signal deduplication/memory system
- Strategy performance tracking and auto-optimization

## Specific Features to Implement

### 1. Web UI Dashboard (Flask-based)

Integrate the NSE Trend Scanner's complete web UI into my crypto project.

**What to port:**
- All files from `templates/` directory (5 HTML pages: dashboard, trades, performance, analysis, settings)
- All files from `static/` directory (CSS + JavaScript with Chart.js charts)
- `src/api.py` (Flask REST API backend)

**Tech:** Flask 2.3+, Flask-CORS, Bootstrap 5.3, Chart.js 4.4

**Your job:**
1. Copy these files into my crypto project
2. In `src/api.py`, change all references from NSE to crypto (NSE → Crypto, ₹ → $)
3. Wire API endpoints to read from my existing crypto data sources:
   - Trade journal (JSON file `data/trade_journal.json`)
   - Data fetcher for live prices
   - Config manager
4. Verify UI loads at `http://localhost:5000`

**API endpoints to provide:**
```
GET  /api/dashboard
GET  /api/market-status
GET  /api/trades/open
GET  /api/trades/history
GET  /api/trades/<id>
GET  /api/performance/summary
GET  /api/performance/by-strategy
GET  /api/performance/pnl-curve
GET  /api/analysis/market-sentiment
GET  /api/settings
POST /api/settings
GET  /api/scanner/status
POST /api/scanner/start
POST /api/scanner/stop
GET  /api/signals/top5        # NEW - I'll add this
```

---

### 2. Top5 Signal Selection

**Current problem:** My scanner sends ALL signals every cycle. I want ONLY the top 5 highest-quality signals.

**Implement:**

**A. Create `src/signal_scorer.py`** - rates signals 0-100 using weighted factors:
- EMA alignment quality: 30%
- Volume confirmation: 20%
- RSI position: 15%
- Volatility appropriateness (ATR): 15%
- Market context: 20%

Return a single float score.

**B. Modify main scanner loop** (`src/main.py`):
```python
# 1. Collect all signals from all strategies
all_signals = trend + verc + mtf + ...

# 2. Score each
for sig in all_signals:
    indicators = get_indicators(sig['symbol'])
    sig['score'] = scorer.score_signal(sig, indicators)

# 3. Sort by score descending
all_signals.sort(key=lambda x: x['score'], reverse=True)

# 4. Assign ranks
for i, sig in enumerate(all_signals):
    sig['rank'] = i + 1

# 5. Select ONLY top 5
top5 = all_signals[:5]

# 6. Process only these 5
for sig in top5:
    self.send_alert(sig)
```

**C. Add API endpoint:**
`GET /api/signals/top5` → returns JSON with today's top 5 signals (symbol, score, rank, entry, SL, targets).

---

### 3. Signal Update Mechanism

**Key requirement:** If a signal that was already sent today appears in today's top5 again, send an **UPDATE** alert, not a NEW alert. The update must show:

- Original entry/SL/targets
- Current price
- Unrealized P&L %
- Distance to stop loss
- Which targets have been hit (T1 ✅, T2 ❌)
- New ranking info

**Implementation:**

**A. Enhance `src/signal_memory.py`:**

```python
def get_signals_sent_today(self) -> List[Dict]:
    """Return all signals where generated_at is today UTC."""
    today = datetime.utcnow().date()
    return [s for s in self.all_signals 
            if datetime.fromisoformat(s['generated_at']).date() == today]

def get_signal_status(self, symbol: str, signal_type: str) -> Optional[Dict]:
    """
    Find the most recent signal for this symbol+type.
    Return: {symbol, entry, sl, targets, status, current_price, 
             highest_target_hit, generated_at}
    """
    # Fetch from all_signals, get live current price
    pass

def should_send_update(self, new_signal: Dict) -> Tuple[bool, Optional[Dict]]:
    """Return (is_update, previous_signal)."""
    prev = self.get_signal_status(new_signal['symbol'], new_signal['signal_type'])
    return (prev is not None), prev
```

**B. Add `format_signal_update()` in `src/alert_service.py`:**

```python
def format_signal_update(self, new_sig: Dict, prev: Dict) -> str:
    current = prev['current_price']
    entry = prev['entry']
    sl = prev['stop_loss']
    targets = prev['targets']
    hit = prev.get('highest_target_hit', 0)
    
    pnl = ((current - entry) / entry) * 100
    dist_sl = abs((current - sl) / sl * 100)
    
    target_lines = []
    for i, t in enumerate(targets, 1):
        if i <= hit:
            target_lines.append(f"T{i}: ${t:.2f} ✅ HIT")
        else:
            dist = ((t - current) / current) * 100
            target_lines.append(f"T{i}: ${t:.2f} ({dist:+.1f}%)")
    
    return f"""🔄 UPDATE - #{new_sig['rank']} {new_sig['symbol']}

📈 P&L: {pnl:+.1f}%
📍 Current: ${current:.2f}
🎯 { ' | '.join(target_lines) }
📊 Score: {new_sig['score']:.0f}/100 → Rank #{new_sig['rank']}
"""
```

**C. In `main.py` processing loop:**

```python
for signal in top5:
    is_update, previous = self.signal_memory.should_send_update(signal)
    
    if is_update and previous:
        msg = self.alert_service.format_signal_update(signal, previous)
        logger.info(f"UPDATE sent: {signal['symbol']}")
    else:
        msg = self.alert_service.format_new_signal(signal)
        logger.info(f"NEW signal: {signal['symbol']}")
    
    self.alert_service.send(msg)
    self.trade_journal.record_signal(signal, msg_type='UPDATE' if is_update else 'NEW')
    self.signal_memory.add_signal(signal)
```

---

### 4. Confirming Stop Loss & Target Logic

**My SL/targets are calculated by existing rules. I need validation to confirm they're correct before sending.**

**Create/enhance `src/trade_validator.py`:**

```python
class TradeValidator:
    def __init__(self, config):
        self.config = config
        self.min_rr = config.get('min_rr', 1.5)
        self.max_sl_pct = config.get('max_sl_pct', 5.0)
        self.min_sl_pct = config.get('min_sl_pct', 1.0)
    
    def validate(self, signal: Dict, indicators: Dict) -> Dict:
        """Return {valid: bool, errors: []}"""
        errors = []
        entry, sl = signal['entry'], signal['stop_loss']
        targets = signal['targets']
        
        # --- STOP LOSS CHECKS ---
        sl_pct = abs((sl - entry) / entry * 100)
        if sl >= entry:
            errors.append("SL must be below entry for long")
        if sl_pct < self.min_sl_pct:
            errors.append(f"SL too tight: {sl_pct:.1f}%")
        if sl_pct > self.max_sl_pct:
            errors.append(f"SL too wide: {sl_pct:.1f}%")
        
        # SL should respect recent swing low
        swing_low = indicators.get('recent_low') or indicators.get('support')
        if swing_low and sl < swing_low * 0.98:
            # SL below swing low (acceptable - indicates strong conviction)
            pass
        
        # --- TARGET CHECKS ---
        if len(targets) < 2:
            errors.append("Need at least 2 targets")
        
        risk = abs(entry - sl)
        for i, target in enumerate(targets, 1):
            reward = abs(target - entry)
            rr = reward / risk if risk else 0
            
            if i == 1 and rr < 1.5:
                errors.append(f"T1 R:R={rr:.1f} < 1.5")
            if i == 2 and rr < 2.5:
                errors.append(f"T2 R:R={rr:.1f} < 2.5")
            
            # Target shouldn't be beyond nearest resistance
            resistance = self._find_resistance(entry, indicators)
            if target > resistance * 1.1:
                errors.append(f"T{i} beyond resistance (${target:.0f} > ${resistance:.0f})")
        
        # --- SCORE CHECK ---
        if signal.get('score', 0) < 60:
            errors.append(f"Score too low: {signal['score']:.0f}")
        
        # --- VOLUME CHECK ---
        vol_ratio = indicators.get('volume_ratio', 0)
        if vol_ratio < 1.2:
            errors.append(f"Volume insufficient: {vol_ratio:.1f}x")
        
        return {'valid': len(errors) == 0, 'errors': errors}
    
    def _find_resistance(self, entry: float, ind: Dict) -> float:
        swing_high = ind.get('swing_high') or ind.get('resistance')
        if swing_high and swing_high > entry:
            return swing_high
        # Fallback: EMA-based
        ema20 = ind.get('ema20', entry * 1.02)
        return max(entry * 1.02, ema20 * 1.01)
```

**Usage in main loop (BEFORE sending any signal):**

```python
validator = TradeValidator(self.config)

def process_signal(self, signal):
    indicators = self.indicator_engine.calculate(signal['symbol'])
    validation = validator.validate(signal, indicators)
    
    if not validation['valid']:
        logger.warning(f"REJECTED {signal['symbol']}: {validation['errors']}")
        return  # Don't send
    
    # Passed - send it
    self.send_alert(signal)
```

**Validation must check:**
1. ✅ Score ≥ 60/100
2. ✅ Stop loss 1-5% from entry
3. ✅ T1 R:R ≥ 1.5:1
4. ✅ T2 R:R ≥ 2.5:1
5. ✅ Volume ratio ≥ 1.2x average
6. ✅ SL below entry (for long) or above entry (for short)
7. ✅ Targets not beyond measurable resistance

---

### 5. Learning & Optimization System

**Goal:** System improves automatically by learning which strategies work best.

**Step A: Trade Journal (`src/trade_journal.py`)**

```python
"""
Complete trade journal - records every signal and outcome.
"""

import json, uuid
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict

@dataclass
class Trade:
    trade_id: str
    symbol: str
    strategy: str
    direction: str
    entry: float
    stop_loss: float
    targets: list
    timestamp: str
    outcome: str = 'OPEN'  # WIN / LOSS / OPEN / TIMEOUT
    rr_achieved: float = 0.0
    targets_hit: list = None
    quality: str = 'B'
    market_context: str = 'NEUTRAL'

class TradeJournal:
    def __init__(self, filepath='data/trade_journal.json'):
        self.filepath = Path(filepath)
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        self.trades = self._load()
    
    def _load(self):
        if self.filepath.exists():
            with open(self.filepath) as f:
                data = json.load(f)
                return data.get('trades', [])
        return []
    
    def _save(self):
        with open(self.filepath, 'w') as f:
            json.dump({'trades': self.trades}, f, indent=2, default=str)
    
    def record_signal(self, signal: Dict, msg_type: str = 'NEW'):
        """Log signal before outcome known."""
        trade = Trade(
            trade_id=signal['signal_id'],
            symbol=signal['symbol'],
            strategy=signal['signal_type'],
            direction=signal['direction'],
            entry=signal['entry'],
            stop_loss=signal['stop_loss'],
            targets=signal['targets'],
            timestamp=datetime.utcnow().isoformat(),
            quality=self._grade_by_score(signal['score']),
            market_context=signal.get('market_context', 'NEUTRAL')
        )
        self.trades.append(asdict(trade))
        self._save()
    
    def close_trade(self, trade_id: str, outcome: str, exit_price: float = None):
        """Mark trade as WIN/LOSS/TIMEOUT."""
        for t in self.trades:
            if t['trade_id'] == trade_id:
                t['outcome'] = outcome
                t['closed_at'] = datetime.utcnow().isoformat()
                
                if outcome == 'WIN':
                    exit_price = t['targets'][0]  # Assume T1 hit
                    t['exit_price'] = exit_price
                    t['rr_achieved'] = abs((exit_price - t['entry']) / 
                                           abs(t['entry'] - t['stop_loss']))
                    t['targets_hit'] = [1]
                
                self._save()
                break
    
    def get_closed_trades(self, limit: int = 100) -> List[Dict]:
        closed = [t for t in self.trades if t.get('outcome') in ['WIN', 'LOSS']]
        return closed[-limit:]
    
    def get_open_trades(self) -> List[Dict]:
        return [t for t in self.trades if t.get('outcome') == 'OPEN']
    
    def get_trades_by_strategy(self, strategy: str) -> List[Dict]:
        return [t for t in self.trades if t.get('strategy') == strategy]
    
    def _grade_by_score(self, score: float) -> str:
        if score >= 80: return 'A'
        elif score >= 65: return 'B'
        else: return 'C'
```

**Step B: Strategy Optimizer (`src/strategy_optimizer.py`)**

```python
"""
Auto-adjusts strategy weights based on performance.
Call after every 20+ closed trades.
"""

from datetime import datetime, timedelta

class StrategyOptimizer:
    def __init__(self, trade_journal: TradeJournal):
        self.trade_journal = trade_journal
        self.weights = {'TREND': 1.0, 'VERC': 0.8, 'MTF': 0.9}
    
    def optimize_weights(self):
        """Update weights based on last 30 days performance."""
        for strategy in self.weights:
            stats = self._calculate_stats(strategy, days=30)
            
            if stats['trades'] < 10:
                continue  # Not enough data
            
            win_rate = stats['win_rate']
            old_weight = self.weights[strategy]
            
            if win_rate > 0.60:
                new_weight = min(2.0, old_weight * 1.10)
            elif win_rate < 0.40:
                new_weight = max(0.5, old_weight * 0.90)
            else:
                new_weight = old_weight
            
            self.weights[strategy] = new_weight
            
            if new_weight != old_weight:
                print(f"[OPTIMIZER] {strategy}: {old_weight:.2f} → {new_weight:.2f} (WR={win_rate:.0%})")
        
        return self.weights
    
    def _calculate_stats(self, strategy: str, days: int):
        cutoff = datetime.utcnow() - timedelta(days=days)
        trades = [
            t for t in self.trade_journal.get_trades_by_strategy(strategy)
            if datetime.fromisoformat(t['timestamp']) > cutoff
        ]
        
        closed = [t for t in trades if t.get('outcome') in ['WIN', 'LOSS']]
        wins = [t for t in closed if t['outcome'] == 'WIN']
        
        win_rate = len(wins) / len(closed) if closed else 0
        avg_rr = sum(w['rr_achieved'] for w in wins) / len(wins) if wins else 0
        
        return {
            'trades': len(closed),
            'win_rate': win_rate,
            'avg_rr': avg_rr
        }
```

**Step C: Pattern Learning (`src/pattern_learning.py`)**

```python
"""
Analyzes journal for insights and recommendations.
"""

from collections import defaultdict

class PatternLearning:
    def __init__(self, trade_journal):
        self.trade_journal = trade_journal
    
    def analyze(self, limit: int = 100) -> Dict:
        """Returns insights list."""
        closed = self.trade_journal.get_closed_trades(limit=limit)
        
        if len(closed) < 20:
            return {'insights': [], 'message': 'Need 20+ trades'}
        
        insights = []
        
        # By strategy
        by_strategy = defaultdict(list)
        for t in closed:
            by_strategy[t['strategy']].append(t)
        
        for strategy, trades in by_strategy.items():
            wins = [t for t in trades if t['outcome'] == 'WIN']
            wr = len(wins) / len(trades)
            
            if wr > 0.65:
                insights.append(f"🚀 {strategy} EXCELLENT ({wr:.0%}) → Increase weight")
            elif wr < 0.40:
                insights.append(f"⚠️  {strategy} POOR ({wr:.0%}) → Decrease weight")
        
        # By regime
        by_regime = defaultdict(list)
        for t in closed:
            by_regime[t['market_context']].append(t)
        
        for regime, trades in by_regime.items():
            if len(trades) >= 10:
                wins = [t for t in trades if t['outcome'] == 'WIN']
                wr = len(wins) / len(trades)
                insights.append(f"📊 Regime {regime}: {wr:.0%} win rate")
        
        return {'insights': insights}
```

**Step D: Wire into main scanner**

In `main.py`:

```python
from trade.trade_journal import TradeJournal
from trade.strategy_optimizer import StrategyOptimizer
from pattern_learning import PatternLearning

# In __init__:
self.trade_journal = TradeJournal()
self.optimizer = StrategyOptimizer(self.trade_journal)
self.learning = PatternLearning(self.trade_journal)

# After each scan or daily:
def maybe_run_learning(self):
    closed = self.trade_journal.get_closed_trades(limit=100)
    
    if len(closed) >= 20:
        analysis = self.learning.analyze(limit=100)
        for insight in analysis['insights']:
            logger.info(f"[LEARNING] {insight}")
        
        new_weights = self.optimizer.optimize_weights()
        # Apply weights to signal_scorer for next cycle
        self.signal_scorer.update_weights(new_weights)
```

---

## What Changes in Each File

### Files to CREATE (8 new):
1. `src/signal_scorer.py` - Scoring engine (80 lines)
2. `src/trade_journal.py` - Journal system (200 lines)
3. `src/strategy_optimizer.py` - Weight optimizer (150 lines)
4. `src/pattern_learning.py` - Insights generator (120 lines)
5. `src/api.py` - Flask API (COPY from NSE, ~600 lines)
6. `templates/` directory (COPY from NSE, 5 HTML files)
7. `static/` directory (COPY from NSE, CSS + 5 JS files)
8. `data/` directory - for JSON files

### Files to MODIFY:
1. **`src/main.py`** (+~100 lines):
   - Import new modules
   - Add top5 selection logic (score → sort → top5)
   - Add update check before sending
   - Call learning cycle periodically

2. **`src/alert_service.py`** (+~30 lines):
   - Add `format_signal_update()` method

3. **`src/signal_memory.py`** (+~50 lines):
   - Add `get_signals_sent_today()`
   - Add `should_send_update()`
   - Add `get_signal_status()` with current price fetch

4. **`config/settings.json`** (+new config keys for validation, learning, top5)

5. **`requirements.txt`** (+ `flask>=2.3.0`, `flask-cors>=4.0.0`)

---

## Implementation Order (4 Days)

**Day 1 - Core:**
1. Set up Flask: `pip install flask flask-cors`
2. Copy `src/api.py`, test `python src/api.py` → `http://localhost:5000`
3. Copy `templates/` and `static/`, verify all pages load
4. Implement `SignalScorer` and integrate top5 logic in `main.py`
5. Verify: scanner now sends ≤5 signals per cycle

**Day 2 - Updates + Validation:**
6. Enhance `SignalMemory` with daily tracking
7. Add `format_signal_update()` to alerts
8. Modify signal loop to detect updates
9. Implement `TradeValidator` with strict SL/target checks
10. Test: Send signal → wait → see if it updates tomorrow

**Day 3 - Learning System:**
11. Implement `TradeJournal` with all fields
12. Implement `StrategyOptimizer`
13. Implement `PatternLearning`
14. Wire learning cycle into `main.py`
15. Test: Generate 20+ test trades, verify weights adjust

**Day 4 - Polish:**
16. Add `/api/signals/top5` endpoint
17. Show top5 on dashboard UI
18. Comprehensive logging
19. Manual end-to-end test
20. Deploy

---

## Validation Checklist

After implementation, verify:

### Top5 Selection
- [ ] `len(all_signals)` > 5 before filtering
- [ ] `top5 = all_signals[:5]` used
- [ ] Only 5 alerts max per scan cycle
- [ ] Logs show ranking: `#1 BTC, #2 ETH, ...`

### Update Mechanism
- [ ] Send BTC on Monday
- [ ] BTC still in top5 on Tuesday → UPDATE sent (not NEW)
- [ ] UPDATE shows: current price, P&L %, T1/T2 status, new rank
- [ ] `signal_memory.get_signals_sent_today()` returns BTC
- [ ] `should_send_update()` returns `(True, prev_status)`

### Validation
- [ ] All signals have `score >= 60`
- [ ] All signals have `sl_pct` between 1-5%
- [ ] All signals have `R:R >= 1.5`
- [ ] Rejected signals logged with reason
- [ ] No alerts sent for invalid signals

### Learning
- [ ] Every signal logged to `trade_journal.json`
- [ ] After 20 closed trades, learning cycle runs (check logs)
- [ ] Strategy weights change (`optimizer.optimize_weights()`)
- [ ] Insights printed: `[LEARNING] TREND: increase weight`
- [ ] Next cycle uses new weights (check logs)

### UI
- [ ] `http://localhost:5000` loads
- [ ] Dashboard shows open trades count, win rate
- [ ] Trades page shows live P&L (updates every 60s)
- [ ] Performance page shows charts
- [ ] Settings page saves to `config/settings.json`
- [ ] `/api/signals/top5` returns JSON with 5 items

---

## Common Issues & Fixes

**"Flask module not found"**
```bash
pip install flask flask-cors
# Verify in requirements.txt
```

**"Templates not found"**
```python
# In api.py, ensure:
app = Flask(__name__, 
            template_folder="templates",  # relative path
            static_folder="static")
```

**"CORS error"**
```python
from flask_cors import CORS
CORS(app)  # Make sure this is present
```

**"Port 5000 in use"**
```bash
# Use different port:
python src/api.py --port 8000
# Or kill existing:
lsof -ti:5000 | xargs kill -9
```

**"No signals in top5"**
```python
# Debug: print all scores before filtering
for sig in all_signals:
    print(f"{sig['symbol']}: score={sig['score']:.1f}")

# Lower threshold in config
"min_signal_score": 50  # instead of 60
```

---

## Final Deliverables

✅ **Working web UI** at `http://localhost:5000`
✅ **Top5 selection** - only best signals sent
✅ **Update alerts** - recurring signals show progress
✅ **Validation gates** - all signals quality-checked
✅ **Trade journal** - complete persistent history
✅ **Learning system** - auto-optimizes weights based on performance
✅ **Dashboard** - real-time monitoring of all metrics

---

## Key Insight

**Don't reinvent - adapt!** The NSE Trend Agent already has all these features built and working. Your job is:
1. Copy UI layer (templates + static + api.py)
2. Adapt signal scoring for crypto (modify weights/indicators)
3. Add top5 filter
4. Add daily tracking for updates
5. Add validation gates
6. Wire learning into scan cycle

All core logic exists - you're integrating and configuring, not building from scratch.

**Start:** Copy UI → Verify it works → Add top5 → Add updates → Add validation → Add learning. One step at a time.

Good luck!
