# Crypto Trading System - Feature Implementation Prompt

## Project Context

You are working with an existing cryptocurrency trading application that has:
- Technical analysis engine with multiple indicators (EMA, RSI, ATR, MACD, Volume MA)
- Signal detection based on pre-defined rules for stop loss and targets
- Alert/notification system (likely Telegram or similar)
- Basic data storage for trades

**Reference Implementation:** The NSE Trend Agent (NSE stock scanner) has a mature, production-ready implementation of:
1. A complete Web UI dashboard (Flask + JavaScript + Chart.js)
2. Comprehensive trade journaling with outcome tracking
3. An AI-powered learning system that improves signals over time
4. Signal deduplication and memory system
5. Strategy performance tracking and auto-optimization
6. Multi-strategy signal generation with ranking

## Your Task

Implement **ALL** of the following features in the crypto application, using the NSE Trend Agent as a reference architecture.

---

## Feature 1: Web UI Dashboard Integration

**Goal:** Integrate the complete NSE Trend Scanner web UI into the crypto project.

**What to Port:**
- All UI files from `templates/` and `static/` directories
- Flask API backend from `src/api.py`
- Update references from "NSE" to "Crypto" throughout

**Pages Required:**
1. **Dashboard** (`/`) - Overview with metrics, open positions, recent signals
2. **Trades** (`/trades`) - Open trades with live P&L, trade history with filters
3. **Performance** (`/performance`) - Win rate, profit factor, strategy breakdown, P&L curve
4. **Analysis** (`/analysis`) - Market sentiment, signal distribution, top coins
5. **Settings** (`/settings`) - Configuration management for all parameters

**API Endpoints to Implement:**
```python
# Dashboard
GET /api/dashboard
GET /api/market-status

# Trades
GET /api/trades/open
GET /api/trades/history
GET /api/trades/<id>

# Performance
GET /api/performance/summary
GET /api/performance/by-strategy
GET /api/performance/pnl-curve

# Analysis
GET /api/analysis/market-sentiment
GET /api/analysis/signals-generated

# Settings & Control
GET /api/settings
POST /api/settings
GET /api/scanner/status
POST /api/scanner/start
POST /api/scanner/stop

# NEW: Top Signals Endpoint (for Feature 2)
GET /api/signals/top5
```

**Tech Stack:**
- Backend: Flask 2.3+, Flask-CORS
- Frontend: HTML5, CSS3, Bootstrap 5.3, Chart.js 4.4
- Data: Read from existing crypto data files + live price fetching

**Integration Notes:**
- The UI should read from your existing trade journal and signal storage
- No changes needed to the core scanning logic - just plugin the data sources
- All charts and metrics should adapt to crypto (prices in USD/USDT, 24h change, etc.)

---

## Feature 2: Top5 Signals with Scoring & Ranking

**Goal:** Instead of sending all signals, send only the **top 5 highest-scoring signals** each scan cycle.

**Implementation Steps:**

### A. Create a Signal Scoring System

If your crypto app doesn't already have a scoring mechanism, implement one similar to NSE's `reasoning_engine.py`:

```python
# In signal_scorer.py (new module)
class SignalScorer:
    """
    Scores signals 0-100 based on multiple factors.
    Higher score = better signal quality.
    """
    
    def score_signal(self, signal_data: dict, indicators: dict) -> float:
        """
        Calculate composite score from factors:
        - Technical quality (EMA alignment, pattern clarity): 30%
        - Volume confirmation: 20%
        - RSI position (not overbought/oversold): 15%
        - Volatility appropriateness (ATR): 15%
        - Market context alignment: 20%
        """
        score = 0.0
        
        # Factor 1: EMA alignment quality (0-30 points)
        ema_score = self._calculate_ema_alignment_score(indicators)
        score += ema_score * 0.30
        
        # Factor 2: Volume confirmation (0-20 points)
        volume_score = self._calculate_volume_score(indicators)
        score += volume_score * 0.20
        
        # Factor 3: RSI position (0-15 points)
        rsi_score = self._calculate_rsi_score(indicators)
        score += rsi_score * 0.15
        
        # Factor 4: ATR-based volatility (0-15 points)
        atr_score = self._calculate_volatility_score(indicators)
        score += atr_score * 0.15
        
        # Factor 5: Market context (0-20 points)
        context_score = self._calculate_context_score(indicators)
        score += context_score * 0.20
        
        return round(score, 2)
```

### B. Rank and Select Top5

In your main scanner loop:

```python
def run_signal_generation(self):
    """
    Modified to generate ALL signals, then filter to top 5.
    """
    all_signals = []
    
    # Run each strategy
    trend_signals = self.trend_detector.scan_all()
    verc_signals = self.verc_scanner.scan_all()
    mtf_signals = self.mtf_scanner.scan_all()
    # ... other strategies
    
    all_signals.extend(trend_signals)
    all_signals.extend(verc_signals)
    all_signals.extend(mtf_signals)
    # ...
    
    # Score each signal
    for signal in all_signals:
        signal['score'] = self.signal_scorer.score_signal(
            signal, 
            signal.get('indicators', {})
        )
        signal['rank'] = 0  # Will be set after sorting
    
    # Sort by score descending
    all_signals.sort(key=lambda x: x['score'], reverse=True)
    
    # Assign ranks
    for i, signal in enumerate(all_signals):
        signal['rank'] = i + 1
    
    # Select top 5
    top5_signals = all_signals[:5]
    
    # Log full list for reference
    logger.info(f"Generated {len(all_signals)} signals. Top 5:")
    for sig in top5_signals:
        logger.info(f"  #{sig['rank']}: {sig['symbol']} - Score: {sig['score']:.1f}")
    
    # Process only top5
    for signal in top5_signals:
        self._process_signal(signal)
```

### C. Update API Endpoint

Add new endpoint to expose top5 signals to UI:

```python
@app.route('/api/signals/top5', methods=['GET'])
def get_top5_signals():
    """Get current top 5 ranked signals."""
    try:
        # This should read from your current scan cycle's results
        # or from active signals if stored
        top5 = get_latest_top5_signals()  # Implement this
        
        return jsonify({
            'signals': top5,
            'generated_at': datetime.now().isoformat(),
            'total_signals': len(all_signals) if 'all_signals' in locals() else 0
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

---

## Feature 3: Signal Update Mechanism (Resend Top5 with Progress)

**Goal:** If a signal that was already sent appears in today's top5 again, send an **UPDATE** message showing its current progress relative to stop loss and targets.

**Why This Matters:**
- A stock might be sent on Day 1, then 2 days later it's still in top5 because it hasn't hit SL or targets yet
- Trader needs to know: "Is my original signal still valid? How is it performing?"
- Update shows exactly where price is relative to entry, SL, and each target

### A. Track Sent Signals by Day

Enhance `signal_memory.py` to track which signals were sent each day:

```python
# Add to SignalMemory class
def get_signals_sent_today(self) -> List[Dict]:
    """Get all signals sent today."""
    today = datetime.now().date()
    today_signals = []
    for sig in self.all_signals:
        sent_date = datetime.fromisoformat(sig.get('generated_at', '')).date()
        if sent_date == today:
            today_signals.append(sig)
    return today_signals

def get_signal_status(self, symbol: str, signal_type: str) -> Optional[Dict]:
    """Get current status of a previously sent signal."""
    for sig in reversed(self.all_signals):
        if sig.get('symbol') == symbol and sig.get('signal_type') == signal_type:
            # Check if still active or recently closed
            return {
                'symbol': symbol,
                'signal_type': signal_type,
                'entry_price': sig.get('entry'),
                'stop_loss': sig.get('stop_loss'),
                'targets': sig.get('targets', []),
                'status': sig.get('outcome', 'OPEN'),
                'current_price': self._get_current_price(symbol),  # Fetch live
                'days_active': (datetime.now() - datetime.fromisoformat(sig['generated_at'])).days,
                'highest_target_hit': sig.get('highest_target_hit', 0)
            }
    return None
```

### B. Detect Recurring Signals Before Sending

Before sending a new signal, check if it's already been sent today:

```python
def should_send_update(self, signal: Dict) -> Tuple[bool, Optional[Dict]]:
    """
    Check if this signal was already sent today.
    Returns: (should_send_update, previous_signal_status)
    """
    symbol = signal['symbol']
    signal_type = signal['signal_type']
    
    # Find if we already sent this signal today
    today_signals = self.signal_memory.get_signals_sent_today()
    
    for prev_signal in today_signals:
        if (prev_signal['symbol'] == symbol and 
            prev_signal['signal_type'] == signal_type):
            # This is a recurring signal - send UPDATE
            return True, prev_signal
    
    return False, None
```

### C. Format Update Alert

```python
def format_update_alert(self, new_signal: Dict, previous_signal: Dict) -> str:
    """
    Format an UPDATE alert for a recurring signal.
    Shows progress from previous signal + new ranking info.
    """
    current_price = self._get_current_price(new_signal['symbol'])
    entry = previous_signal['entry']
    sl = previous_signal['stop_loss']
    targets = previous_signal['targets']
    highest_hit = previous_signal.get('highest_target_hit', 0)
    
    # Calculate current P&L
    pnl_pct = ((current_price - entry) / entry) * 100
    
    # Distance to SL
    dist_to_sl = abs((current_price - sl) / sl * 100)
    
    # Target status
    target_status = []
    for i, target in enumerate(targets, 1):
        if i <= highest_hit:
            target_status.append(f"T{i}: ₹{target:.2f} ✅ HIT")
        else:
            dist_to_target = ((target - current_price) / current_price) * 100
            target_status.append(f"T{i}: ₹{target:.2f} ({dist_to_target:.1f}% away)")
    
    # Build message
    message = f"""
🔄 SIGNAL UPDATE - {new_signal['symbol']}

📊 ORIGINAL SIGNAL (sent earlier today):
   Entry: ₹{entry:.2f}
   Stop Loss: ₹{sl:.2f}
   Targets: {' | '.join([f'T{i}: ₹{t:.2f}' for i, t in enumerate(targets, 1)])}

📈 CURRENT STATUS:
   Current Price: ₹{current_price:.2f}
   Unrealized P&L: {pnl_pct:+.2f}%
   Distance to SL: {dist_to_sl:.2f}%
   
🎯 TARGET TRACKING:
   {' | '.join(target_status)}

📊 NEW RANKING:
   Current Rank: #{new_signal['rank']}
   Score: {new_signal['score']:.1f}/100
   Confidence: {new_signal.get('confidence', 'N/A')}/10

💡 The signal remains active and is still in today's top 5.
    """
    
    return message
```

### D. Integration in Main Loop

Modify signal processing:

```python
def process_top5_signals(self, top5_signals: List[Dict]):
    """
    Process top 5 signals, sending updates for recurring ones.
    """
    for signal in top5_signals:
        symbol = signal['symbol']
        
        # Check if already sent today
        should_update, previous = self.should_send_update(signal)
        
        if should_update and previous:
            # Send UPDATE alert
            update_msg = self.format_update_alert(signal, previous)
            self.alert_service.send_alert(update_msg)
            logger.info(f"Sent UPDATE alert for {symbol} (rank #{signal['rank']})")
        else:
            # Send NEW signal alert
            new_msg = self.format_new_signal_alert(signal)
            self.alert_service.send_alert(new_msg)
            logger.info(f"Sent NEW signal alert for {symbol} (rank #{signal['rank']})")
        
        # Log signal regardless (for journal)
        self.trade_journal.record_signal(signal)
```

---

## Feature 4: Confirming Stop Loss & Target Logic

**Goal:** Ensure the stop loss and target calculations are correct based on your technical analysis rules.

**Validation Checklist:**

### A. Stop Loss Validation

Your system should verify:

1. **SL based on ATR:**
   ```python
   # Correct: SL = entry ± (ATR * multiplier)
   # For long: SL = entry - (ATR * 1.2 to 2.0)
   # For short: SL = entry + (ATR * 1.2 to 2.0)
   atr = indicators['atr']
   sl_atr = entry - (atr * 1.5)  # for long
   ```

2. **SL respects support levels:**
   - SL should be just below nearest significant support (for longs)
   - Not too tight (< 0.5%) or too wide (> 5%)
   - Preferred range: 1.5% - 3.5% from entry

3. **SL not in consolidation zone:**
   - If stock is in consolidation, SL should be below the consolidation range

**Validation Code:**
```python
def validate_stop_loss(self, entry: float, sl: float, indicators: Dict) -> Tuple[bool, str]:
    """Validate stop loss placement."""
    sl_pct = abs((sl - entry) / entry * 100)
    
    if sl_pct < 1.0:
        return False, f"SL too tight ({sl_pct:.1f}%) - minimum 1%"
    if sl_pct > 5.0:
        return False, f"SL too wide ({sl_pct:.1f}%) - maximum 5%"
    
    # For long: SL should be below entry
    if sl >= entry:
        return False, "For long signal, SL must be below entry"
    
    # Check if SL respects recent swing low
    recent_low = indicators.get('recent_low')
    if recent_low and sl < recent_low * 0.95:
        return False, "SL too far below recent low - too aggressive"
    
    return True, "SL valid"
```

### B. Target Validation

Your system should verify:

1. **Targets are at resistance:**
   ```python
   # Target 1: nearest resistance (1.5-2x risk)
   # Target 2: next resistance (2.5-3x risk)
   risk = entry - sl
   t1 = entry + (risk * 1.5)
   t2 = entry + (risk * 2.5)
   ```

2. **Minimum R:R ratio:**
   - T1 distance : risk >= 1.5:1
   - T2 distance : risk >= 2.5:1

3. **Targets not beyond measurable resistance:**
   - Don't set targets at arbitrary Fibonacci extensions
   - Use actual price levels where selling pressure expected

**Validation Code:**
```python
def validate_targets(self, entry: float, sl: float, targets: List[float], indicators: Dict) -> Tuple[bool, str]:
    """Validate target placement."""
    risk = abs(entry - sl)
    
    for i, target in enumerate(targets, 1):
        reward = abs(target - entry)
        rr = reward / risk
        
        if rr < 1.5 and i == 1:
            return False, f"T1 R:R too low ({rr:.1f}) - minimum 1.5"
        
        if rr < 2.5 and i == 2:
            return False, f"T2 R:R too low ({rr:.1f}) - minimum 2.5"
        
        # Check target is above resistance
        resistance = self._find_resistance_level(entry, indicators)
        if target > resistance * 1.1:  # 10% buffer
            return False, f"T{i} beyond measurable resistance"
    
    return True, "Targets valid"
```

### C. Signal Confirmation Rules

Before sending any signal, run these checks:

```python
def validate_complete_signal(self, signal: Dict, indicators: Dict) -> Dict:
    """
    Full validation of a signal before sending.
    Returns: {valid: bool, errors: []}
    """
    errors = []
    
    # 1. Check score threshold
    if signal['score'] < self.min_signal_score:
        errors.append(f"Score too low: {signal['score']:.1f} < {self.min_signal_score}")
    
    # 2. Validate stop loss
    sl_valid, sl_msg = self.validate_stop_loss(
        signal['entry'], 
        signal['stop_loss'], 
        indicators
    )
    if not sl_valid:
        errors.append(f"SL invalid: {sl_msg}")
    
    # 3. Validate targets
    t_valid, t_msg = self.validate_targets(
        signal['entry'],
        signal['stop_loss'],
        signal['targets'],
        indicators
    )
    if not t_valid:
        errors.append(f"Targets invalid: {t_msg}")
    
    # 4. Check R:R meets minimum
    rr = signal.get('risk_reward', 0)
    if rr < 1.5:
        errors.append(f"R:R too low: {rr:.1f} < 1.5")
    
    # 5. AI validation (if using LLM)
    if self.ai_validator:
        ai_valid, ai_confidence = self.ai_validator.validate(signal)
        if not ai_valid or ai_confidence < 6:
            errors.append(f"AI rejected: confidence {ai_confidence}/10")
    
    return {
        'valid': len(errors) == 0,
        'errors': errors
    }
```

---

## Feature 5: Learning & Optimization System

**Goal:** The system improves over time by learning which signals performed well and adjusting strategy weights, filters, and thresholds.

**Modules to Port/Implement:**

### A. Trade Journal (Already in NSE)

Reference: `src/trade_journal.py`

**Data to Store per Signal:**
```python
trade = {
    'trade_id': str(uuid4()),
    'symbol': 'BTCUSDT',
    'strategy': 'TREND',  # or 'VERC', 'MTF'
    'direction': 'BUY',   # or 'SELL'
    'entry': 45000.00,
    'stop_loss': 43500.00,
    'targets': [46000, 47500, 49000],
    'timestamp': '2026-04-24T10:30:00',
    'outcome': 'OPEN',  # WIN / LOSS / OPEN / TIMEOUT
    'rr_achieved': 0.0,  # Actual R:R achieved
    'max_drawdown': 0.0,  # Max adverse excursion
    'max_profit': 0.0,   # Max favorable excursion
    'targets_hit': [1],  # Which targets were hit [1,2] means T1 and T2
    'holding_days': 2.5,
    'volume_ratio': 2.3,
    'rsi': 58.0,
    'trend_score': 85.0,
    'rank_score': 78.5,
    'quality': 'A',  # A / B / C based on score
    'market_context': 'BULLISH',  # market regime
    'entry_type': 'BREAKOUT',
}
```

**Persistence:** Save to `data/trade_journal.json` (append-only, keep last 1000 trades)

### B. Strategy Performance Tracker

Reference: `src/strategy_optimizer.py`

**Track per strategy:**
```python
performance = {
    'TREND': {
        'total_signals': 150,
        'wins': 102,
        'losses': 48,
        'win_rate': 0.68,
        'avg_rr': 2.15,
        'profit_factor': 2.34,
        'max_drawdown': -12.5,
        'avg_hold_days': 3.2
    },
    'VERC': {...},
    'MTF': {...}
}
```

**Auto-Optimization:**
```python
def optimize_strategy_weights(self):
    """
    Adjust strategy weights based on recent performance.
    - Win rate > 60%: increase weight by 10%
    - Win rate < 40%: decrease weight by 10%
    - Weight bounds: 0.5 to 2.0
    """
    for strategy in ['TREND', 'VERC', 'MTF']:
        stats = self.get_strategy_stats(strategy, days=30)
        win_rate = stats['win_rate']
        current_weight = self.weights[strategy]
        
        if win_rate >= 0.60:
            new_weight = min(2.0, current_weight * 1.10)
        elif win_rate <= 0.40:
            new_weight = max(0.5, current_weight * 0.90)
        else:
            new_weight = current_weight  # No change
        
        self.weights[strategy] = new_weight
        logger.info(f"Optimized {strategy} weight: {current_weight:.2f} → {new_weight:.2f}")
```

### C. Pattern Learning Recognizer

Reference: `src/pattern_learning_recognizer.py`

**Learns:**
- Which signal types work best in which market regimes
- Which factors correlate with winning trades
- Emerging patterns (newly successful setups)

**Output Insights:**
```
[INSIGHT] TREND_ALIGNED signals performing excellently (68.5% win rate)
[INSIGHT] VERC breakouts work best in SIDEWAYS markets (72% win)
[INSIGHT] RSI > 65 correlates with losses - consider tightening filter
[ACTION] Increase TREND weight from (1.0 → 1.2)
[ACTION] Increase VERC weight in sideways markets (1.0 → 1.3)
```

### D. AI Learning Layer

Reference: `src/ai_learning_layer.py`

If you have LLM integration (OpenAI/Anthropic), use it to:
1. Analyze the trade journal for failure patterns
2. Suggest parameter adjustments
3. Generate natural language insights

**Integration Point:** Run this every 20+ completed trades:
```python
def run_learning_cycle(self):
    if len(closed_trades) >= 20:
        insights = self.ai_learning_layer.analyze_recent_trades(limit=50)
        recommendations = insights.get('recommendations', [])
        
        if recommendations:
            # Apply recommendations
            self.ai_learning_layer.apply_recommended_filters()
            logger.info(f"Applied {len(recommendations)} learning-based filter adjustments")
```

### E. Adaptive Filters

Reference: `src/strategy_optimizer.py` (adapt_filters_based_on_performance)

**Dynamic Threshold Adjustment:**
```python
# Example: Too many false breakouts → increase volume_ratio threshold
if false_breakout_rate > 0.4:  # >40% false
    self.adaptive_filters['volume_ratio_min'] = min(
        2.5, 
        self.adaptive_filters['volume_ratio_min'] * 1.15
    )

# Example: Late entries → tighten RSI filter
if avg_entry_rsi > 70:
    self.adaptive_filters['rsi_max'] = max(50, self.adaptive_filters['rsi_max'] - 5)

# These adaptive filters are used during signal validation
```

---

## Feature 6: Signal Deduplication & Memory

**Goal:** Prevent duplicate alerts and manage active signal state.

**Reference:** `src/signal_memory.py`

**Key Functionality:**
```python
class SignalMemory:
    """
    Prevents duplicate signals and tracks outcomes.
    """
    
    def is_duplicate(self, symbol: str, signal_type: str, 
                     trend_phase: str = 'BREAKOUT') -> bool:
        """
        Check if we already sent this signal recently.
        Cooldown periods by outcome:
        - TARGET_HIT: 5 days (winner, can re-enter quickly)
        - SL_HIT: 15 days (loser, wait longer)
        - TIMEOUT: 10 days
        """
        cooldown = self.get_cooldown_by_last_outcome(symbol)
        cutoff = datetime.now() - timedelta(days=cooldown)
        
        # Check active signals
        for sig in self.active_signals.values():
            if sig['symbol'] == symbol and sig['type'] == signal_type:
                return True
        
        # Check recent closed signals
        for sig in self.all_signals:
            if sig['symbol'] == symbol and sig['type'] == signal_type:
                signal_time = datetime.fromisoformat(sig['generated_at'])
                if signal_time > cutoff:
                    return True
        
        return False
```

**Usage:** Before sending any signal, check `if not signal_memory.is_duplicate(symbol, type):`

---

## Data Storage Architecture

### File Structure (in `data/` directory)
```
data/
├── trade_journal.json         # All signals ever generated
├── signals_active.json        # Currently active (open) signals
├── memory_all_signals.json    # Full signal history
├── memory_outcomes.json       # Completed outcomes only
├── stock_blacklist.json       # Blacklisted stocks after N losses
├── strategy_performance.json  # Per-strategy metrics
└── pattern_learning.json      # Learned pattern insights
```

### Database Schema (if using SQLite/PostgreSQL)

If you want to move from JSON files to a real database:

```sql
-- trades table
CREATE TABLE trades (
    trade_id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    strategy TEXT NOT NULL,
    direction TEXT CHECK(direction IN ('BUY', 'SELL')),
    entry_price DECIMAL(10, 2),
    stop_loss DECIMAL(10, 2),
    target_1 DECIMAL(10, 2),
    target_2 DECIMAL(10, 2),
    timestamp TIMESTAMP,
    outcome TEXT CHECK(outcome IN ('WIN', 'LOSS', 'OPEN', 'TIMEOUT')),
    rr_achieved DECIMAL(5, 2),
    max_drawdown DECIMAL(5, 2),
    max_profit DECIMAL(5, 2),
    targets_hit JSON,  -- [1, 2] means T1 and T2 hit
    holding_days DECIMAL(6, 2),
    market_context TEXT,
    quality_score DECIMAL(5, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- signals table (for tracking sent signals)
CREATE TABLE signals_sent (
    signal_id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    rank INTEGER,
    score DECIMAL(5, 2),
    entry_price DECIMAL(10, 2),
    stop_loss DECIMAL(10, 2),
    targets JSON,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_top5 BOOLEAN DEFAULT TRUE
);

-- signal_outcomes table
CREATE TABLE signal_outcomes (
    outcome_id TEXT PRIMARY KEY,
    signal_id TEXT REFERENCES signals(signal_id),
    outcome TEXT NOT NULL,  -- TARGET_HIT, SL_HIT, TIMEOUT
    pnl_percent DECIMAL(6, 2),
    completed_at TIMESTAMP
);

-- strategy_performance table
CREATE TABLE strategy_performance (
    strategy TEXT PRIMARY KEY,
    total_signals INTEGER,
    wins INTEGER,
    losses INTEGER,
    win_rate DECIMAL(5, 2),
    avg_rr DECIMAL(5, 2),
    profit_factor DECIMAL(10, 2),
    last_updated TIMESTAMP
);
```

---

## Implementation Order

**Phase 1: Core - Week 1**
1. Set up Flask + CORS in crypto project
2. Port all UI templates (HTML/CSS/JS)
3. Port API backend (`api.py`)
4. Connect API to your existing crypto data sources
5. Verify UI loads and displays data

**Phase 2: Signal Top5 - Week 1-2**
6. Implement SignalScorer module
7. Add ranking logic to main scanner
8. Modify to select only top5 signals
9. Update alert formatting for ranked signals
10. Test: ensure only 5 signals sent per cycle

**Phase 3: Signal Updates - Week 2**
11. Enhance SignalMemory to track daily signals
12. Add `get_signals_sent_today()` method
13. Implement `should_send_update()` check
14. Create `format_update_alert()` function
15. Update main loop to send updates for recurring top5 signals
16. Test: Send signal, wait, see update if still in top5

**Phase 4: Validation - Week 2-3**
17. Implement complete SL validation (check ATR, support levels, % range)
18. Implement complete Target validation (check R:R, resistance levels)
19. Implement AI validation gate (if LLM available)
20. Run validation before ANY signal is sent
21. Log validation failures for debugging

**Phase 5: Learning System - Week 3**
22. Port TradeJournal (complete with all fields)
23. Port StrategyOptimizer (auto-weight adjustment)
24. Port PatternLearningRecognizer (pattern insights)
25. Wire learning into scan cycle (run after N trades close)
26. Test: Make 20+ trades, verify weights adjust

**Phase 6: Production Polish - Week 4**
27. Add data migrations (if moving from JSON to DB)
28. Add monitoring/logging throughout
29. Create admin endpoints for learning insights
30. Deploy and monitor

---

## Code Patterns & Conventions

### Naming Conventions (follow your existing codebase)
- Classes: `PascalCase` → `SignalMemory`, `TradeJournal`
- Functions/methods: `snake_case` → `is_duplicate()`, `score_signal()`
- Variables: `snake_case` → `active_signals`, `win_rate`
- Constants: `UPPER_CASE` → `STOCK_DEDUP_DAYS = 7`

### File Structure in Crypto Project
```
crypto-trading-app/
├── src/
│   ├── main.py                    # Main scanner (orchestrator)
│   ├── data_fetcher.py            # Price data (crypto exchange API)
│   ├── indicator_engine.py        # Indicator calculations
│   ├── trend_detector.py          # Trend logic
│   ├── volume_compression.py      # VERC logic
│   ├── signal_scorer.py           # NEW: Scoring engine
│   ├── signal_memory.py           # NEW: Deduplication & tracking
│   ├── trade_journal.py           # NEW: Complete trade log
│   ├── strategy_optimizer.py      # NEW: Performance + optimization
│   ├── pattern_learning.py        # NEW: Pattern insights
│   ├── ai_learning_layer.py       # NEW: AI analysis (optional)
│   ├── trade_validator.py         # Validate SL/targets
│   ├── alert_service.py           # Telegram alerts
│   ├── api.py                     # NEW: Flask API
│   └── [other existing modules]
├── templates/                     # NEW: HTML templates
├── static/                        # NEW: CSS/JS/Charts
├── config/
├── data/                          # NEW: All JSON storage
├── logs/
└── requirements.txt               # Add flask, flask-cors
```

### Data Flow Pattern

Use this pattern consistently:

```python
# 1. SCAN phase: generate all raw signals
raw_signals = []
for strategy in strategies:
    signals = strategy.scan()
    raw_signals.extend(signals)

# 2. SCORE phase: rank by quality
scored_signals = []
for sig in raw_signals:
    score = signal_scorer.score_signal(sig, indicators)
    sig['score'] = score
    scored_signals.append(sig)

# 3. SORT phase: rank from best to worst
scored_signals.sort(key=lambda x: x['score'], reverse=True)

# 4. FILTER phase: deduplicate + validate
filtered_signals = []
for sig in scored_signals:
    if signal_memory.is_duplicate(sig['symbol'], sig['type']):
        continue  # skip duplicate
    if not trade_validator.validate(sig):
        continue  # skip invalid
    
    filtered_signals.append(sig)

# 5. SELECT phase: choose top5
top5 = filtered_signals[:5]

# 6. PROCESS phase: send alerts (new or update)
for sig in top5:
    is_update, prev = signal_memory.should_send_update(sig)
    if is_update:
        msg = format_update_alert(sig, prev)
    else:
        msg = format_new_signal_alert(sig)
    
    alert_service.send(msg)
    trade_journal.record_signal(sig)
    signal_memory.add_signal(sig)
```

---

## Testing Checklist

### Unit Tests (per module)
- [ ] `SignalScorer.score_signal()` returns 0-100
- [ ] `TradeValidator.validate_stop_loss()` rejects SL > 5%
- [ ] `TradeValidator.validate_targets()` enforces R:R >= 1.5
- [ ] `SignalMemory.is_duplicate()` blocks re-signals within cooldown
- [ ] `StrategyOptimizer.optimize_weights()` adjusts correctly based on win rate
- [ ] `PatternLearning.get_insights()` returns non-empty after 20 trades

### Integration Tests
- [ ] Full scan generates signals
- [ ] Only top5 signals pass through
- [ ] Duplicate signal blocked
- [ ] Recurring signal triggers UPDATE alert
- [ ] Trade journal logs complete data
- [ ] Performance tracker calculates correct win rate
- [ ] Learning cycle runs automatically after 20 closed trades

### UI Tests
- [ ] Dashboard loads with metrics
- [ ] Trades page shows open positions with live prices
- [ ] Performance page displays charts
- [ ] Settings page saves to config
- [ ] `/api/signals/top5` returns JSON
- [ ] Auto-refresh works (30s dashboard, 60s trades)

### End-to-End Test
1. Start scanner
2. Wait for signal generation
3. Verify Telegram alert received (NEW or UPDATE format)
4. Check trade_journal.json has entry
5. Manually close trade (WIN or LOSS)
6. Wait for 20 trades to accumulate
7. Verify learning cycle runs (check logs)
8. Confirm strategy weights changed
9. Next scan should reflect new weights

---

## Configuration

Add to your `config/settings.json`:

```json
{
  "trading": {
    "max_signals_per_day": 5,
    "min_signal_score": 60,
    "require_ai_validation": true
  },
  "signals": {
    "send_updates": true,
    "update_cooldown_hours": 4,
    "min_progress_for_update_pct": 5
  },
  "validation": {
    "min_rr_ratio": 1.5,
    "max_sl_percent": 5.0,
    "min_volume_ratio": 1.5
  },
  "learning": {
    "enabled": true,
    "auto_optimize_weights": true,
    "min_trades_for_learning": 20,
    "learning_check_interval_days": 7
  },
  "storage": {
    "journal_file": "data/trade_journal.json",
    "signals_file": "data/signals_active.json",
    "performance_file": "data/strategy_performance.json"
  }
}
```

---

## Logging & Monitoring

Add comprehensive logging:

```python
import logging
logger = logging.getLogger(__name__)

# At key points:
logger.info(f"Generated {len(all_signals)} total signals")
logger.info(f"Top5 after filtering: {[s['symbol'] for s in top5]}")
logger.info(f"Signal UPDATE sent for {symbol} (was rank #{prev_rank}, now #{new_rank})")
logger.info(f"Learning cycle: Analyzed {n_trades} trades, {n_insights} insights found")
logger.info(f"Optimized weights: {self.strategy_optimizer.weights}")
```

Monitor logs for:
- `SIGNAL_NEW` vs `SIGNAL_UPDATE` counts
- Duplicate rejection rate
- Validation failure reasons
- Weight adjustment frequency
- Learning insight count

---

## Common Pitfalls & Solutions

### Problem 1: Fewer than 5 signals generated
**Solution:** Lower score threshold or relax validation filters. Don't force 5 signals if quality is low.

### Problem 2: Same stocks in top5 every day (lack of rotation)
**Solution:** Add "recently sent" exclusion list - if sent in last 2 days, exclude from top5 even if high score.

### Problem 3: Updates spam too frequently
**Solution:** Only send update if:
- Signal improved rank by ≥2 positions, OR
- Price moved ≥5% toward target, OR
- 4+ hours since last update

### Problem 4: Learning doesn't improve results
**Solution:** 
- Ensure you have enough data (50+ closed trades)
- Check `pattern_learning.json` for insights
- Manually review insights - may be wrong
- Adjust learning cycle frequency

### Problem 5: UI shows stale data
**Solution:**
- API should read fresh from JSON files on every request
- JavaScript should have appropriate cache headers
- Add cache-busting query params: `/api/dashboard?ts=123456`

---

## Key Differences: NSE vs Crypto

When porting code:

1. **Market Hours:** Crypto trades 24/7, no market scheduler needed
2. **Price Data:** Use crypto exchange API (Binance, Coinbase) instead of yfinance
3. **Volume:** Crypto volume is 24h volume, not daily volume
4. **Volatility:** Crypto is more volatile - adjust ATR multipliers (1.5x instead of 2x)
5. **Leverage:** Crypto often uses leverage - consider position sizing if applicable
6. **Pairs:** Trading pairs like BTC/USDT, ETH/USDT instead of single symbols

---

## Quick Start Commands

```bash
# 1. Install dependencies
cd /path/to/crypto-project
pip install flask flask-cors pandas ta

# 2. Copy UI files
cp -r nse-trend-agent/templates ./templates
cp -r nse-trend-agent/static ./static
cp nse-trend-agent/src/api.py ./src/

# 3. Create data directory
mkdir -p data

# 4. Run Flask UI
python src/api.py

# 5. Open browser
# http://localhost:5000

# 6. In another terminal, run scanner
python src/main.py

# 7. Watch top5 signals appear on dashboard
```

---

## Success Criteria

✅ **UI fully ported** - All 5 pages work with crypto data  
✅ **Top5 selection** - Only 5 highest-scoring signals sent per cycle  
✅ **Update mechanism** - Recurring top5 signals get progress updates  
✅ **SL/target validation** - All signals pass strict validation before alert  
✅ **Trade journal** - Complete data stored for every signal  
✅ **Learning system** - Strategy weights adjust automatically based on performance  
✅ **Dashboard displays** - Real-time signals, top5 rankings, P&L tracking  

---

## Resources

- NSE Trend Agent docs: `/Users/ravikiran/Documents/nse-trend-agent/`
- Developer Guide: `DEVELOPER_ARCHITECTURE_GUIDE.md`
- UI Setup: `UI_SETUP_GUIDE.md`
- API Reference: `API.md` (this file hypothetically)
- Learning System: `LEARNING_SYSTEM_CODE_CHANGES.md`

---

## Final Note

The NSE Trend Agent is a **complete, production-grade trading system**. All features requested (UI, journaling, learning, top5 signals, signal updates, SL/target confirmation) are **already implemented** and battle-tested.

Your task is not to invent new architecture, but to **port and adapt** the proven NSE implementation to your crypto use case. Copy the patterns, adapt the logic for crypto markets, and maintain the same data flow.

Good luck. The blueprint is complete.
