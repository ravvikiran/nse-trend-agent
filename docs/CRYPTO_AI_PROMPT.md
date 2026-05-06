# AI Coder Prompt: Crypto Trading System Enhancement

## Role & Context

You are enhancing an existing cryptocurrency trading application. The app currently:
- Fetches OHLCV data from crypto exchanges (Binance/Coinbase)
- Calculates technical indicators (EMA, RSI, ATR, MACD, Volume)
- Detects trading signals based on pre-defined technical rules
- Sends alerts via Telegram
- Stores basic trade history in JSON files

**Reference Architecture:** Use the NSE Trend Agent (NSE stock scanner) as your blueprint. It has all the features you need to implement.

---

## What You Need to Build

Implement **5 major features**, in order:

### 1. Web UI Dashboard (Flask + JS)

Port the entire NSE Trend Scanner UI to the crypto project.

**Files to copy:**
- `templates/dashboard.html`, `templates/trades.html`, `templates/performance.html`, `templates/analysis.html`, `templates/settings.html`
- `static/css/dashboard.css`
- `static/js/dashboard.js`, `static/js/trades.js`, `static/js/performance.js`, `static/js/analysis.js`, `static/js/settings.js`
- `src/api.py` (Flask backend)

**Integration steps:**
1. Add Flask & Flask-CORS to `requirements.txt`
2. Place templates in `templates/`, static in `static/`
3. In `src/api.py`, import your existing crypto modules (data_fetcher, indicator_engine, trade_journal, etc.)
4. Update all data endpoints to read from your crypto trade journal JSON
5. Update labels from "NSE" → "Crypto", "₹" → "$"/"USDT"
6. Test: `python src/api.py`, open `http://localhost:5000`

**API endpoints you must provide:**
- `/api/dashboard` - summary metrics
- `/api/trades/open` - open positions
- `/api/trades/history` - historical trades
- `/api/trades/<id>` - single trade details
- `/api/performance/summary` - win rate, P&L
- `/api/performance/by-strategy` - breakdown by strategy
- `/api/performance/pnl-curve` - cumulative P&L data
- `/api/settings` (GET/POST) - config management
- `/api/scanner/status` - is scanner running?
- `/api/scanner/start` - start scanner
- `/api/scanner/stop` - stop scanner

**NEW endpoints for top5 signals:**
- `/api/signals/top5` - returns current top 5 ranked signals

---

### 2. Signal Scoring & Top5 Selection

**Problem:** Your crypto app currently sends every signal. You need to send only the **best 5 signals** per scan cycle.

**Solution:** Implement a scoring system and ranking.

**Create `src/signal_scorer.py`:**

```python
"""
Signal Scoring Engine
Ranks signals by quality (0-100 score).
"""

from typing import Dict

class SignalScorer:
    """
    Score signals across 5 factors:
    - EMA alignment quality: 30 points
    - Volume confirmation: 20 points
    - RSI positioning: 15 points
    - Volatility appropriateness: 15 points
    - Market context: 20 points
    """
    
    def score_signal(self, signal: Dict, indicators: Dict) -> float:
        score = 0.0
        
        # 1. EMA alignment (0-30 pts)
        ema_score = self._ema_alignment_score(indicators)
        score += ema_score * 0.30
        
        # 2. Volume (0-20 pts)
        vol_score = self._volume_score(indicators)
        score += vol_score * 0.20
        
        # 3. RSI (0-15 pts)
        rsi_score = self._rsi_score(indicators)
        score += rsi_score * 0.15
        
        # 4. ATR/volatility (0-15 pts)
        atr_score = self._volatility_score(indicators)
        score += atr_score * 0.15
        
        # 5. Market context (0-20 pts)
        ctx_score = self._context_score(indicators)
        score += ctx_score * 0.20
        
        return round(score, 2)
    
    def _ema_alignment_score(self, ind: Dict) -> float:
        """0-100 based on EMA ordering perfection."""
        price = ind.get('close', 0)
        ema20 = ind.get('ema20', 0)
        ema50 = ind.get('ema50', 0)
        ema100 = ind.get('ema100', 0)
        ema200 = ind.get('ema200', 0)
        
        if price > ema20 > ema50 > ema100 > ema200:
            return 100.0  # Perfect bullish alignment
        elif price < ema20 < ema50 < ema100 < ema200:
            return 100.0  # Perfect bearish alignment
        elif price > ema20 > ema50:
            return 70.0   # Partial alignment
        elif price < ema20 < ema50:
            return 70.0
        else:
            return 30.0   # Poor alignment
    
    def _volume_score(self, ind: Dict) -> float:
        volume = ind.get('volume', 0)
        volume_ma = ind.get('volume_ma', 1)
        ratio = volume / volume_ma if volume_ma > 0 else 0
        
        if ratio >= 2.0:
            return 100.0
        elif ratio >= 1.5:
            return 80.0
        elif ratio >= 1.2:
            return 60.0
        else:
            return 30.0
    
    def _rsi_score(self, ind: Dict) -> float:
        rsi = ind.get('rsi', 50)
        
        # Ideal: 40-60 (neither overbought nor oversold)
        if 40 <= rsi <= 60:
            return 100.0
        elif 30 <= rsi <= 70:
            return 80.0
        elif 20 <= rsi <= 80:
            return 50.0
        else:
            return 20.0  # Extreme
    
    def _volatility_score(self, ind: Dict) -> float:
        atr = ind.get('atr', 0)
        atr_pct = (atr / ind.get('close', 1)) * 100 if ind.get('close') else 0
        
        # Ideal ATR: 1-3% daily
        if 1.0 <= atr_pct <= 3.0:
            return 100.0
        elif 0.5 <= atr_pct <= 5.0:
            return 70.0
        else:
            return 40.0  # Too low or too high
    
    def _context_score(self, ind: Dict) -> float:
        regime = ind.get('market_regime', 'UNKNOWN')
        nifty_trend = ind.get('nifty_trend', 'NEUTRAL')
        
        # For crypto: use BTC trend or crypto market cap
        btc_trend = ind.get('btc_trend', 'NEUTRAL')
        
        score = 50.0  # neutral
        
        # Boost if market aligns with signal direction
        # (you'll customize based on your market context logic)
        
        return score
```

**Modify main scanner loop:**

In your `main.py` (or equivalent), after generating all signals:

```python
from strategies.signal_scorer import SignalScorer

# In __init__:
self.signal_scorer = SignalScorer()

# In scan method:
def run_scan(self):
    all_signals = []
    
    # Collect from all strategies
    trend_signals = self.trend_detector.scan_all()
    verc_signals = self.volume_compression.scan_all()
    # ... other strategies
    
    all_signals.extend(trend_signals)
    all_signals.extend(verc_signals)
    # ...
    
    # SCORE each signal
    for sig in all_signals:
        indicators = self._get_indicators_for_symbol(sig['symbol'])
        sig['score'] = self.signal_scorer.score_signal(sig, indicators)
        sig['rank'] = 0  # set after sort
    
    # RANK by score descending
    all_signals.sort(key=lambda x: x['score'], reverse=True)
    for i, sig in enumerate(all_signals):
        sig['rank'] = i + 1
    
    # SELECT top 5 only
    top5 = all_signals[:5]
    
    log_msg = "Top 5 signals:\n"
    for sig in top5:
        log_msg += f"  #{sig['rank']}: {sig['symbol']} - Score: {sig['score']:.1f}\n"
    logger.info(log_msg)
    
    # Process only these 5
    for signal in top5:
        self.process_signal(signal)
```

---

### 3. Signal Update Mechanism

**Problem:** If a stock/coin you already signaled is still in top5 today, you should send an UPDATE, not a NEW signal.

**Why:** Shows progress: "BTC is still #3, currently up 4%, T1 hit, now targeting T2"

**Implementation:**

**Step A: Track daily signals**

Modify `src/signal_memory.py` (or create if not exists):

```python
"""
Signal Memory - Deduplication + Tracking
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class SignalMemory:
    def __init__(self, data_dir: str = 'data'):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.all_signals_file = self.data_dir / 'memory_all_signals.json'
        self.active_signals_file = self.data_dir / 'signals_active.json'
        
        self.all_signals = self._load_json(self.all_signals_file, [])
        self.active_signals = self._load_json(self.active_signals_file, {})
    
    def _load_json(self, path: Path, default):
        if path.exists():
            with open(path) as f:
                return json.load(f)
        return default
    
    def _save_json(self, path: Path, data):
        tmp = path.with_suffix('.tmp')
        with open(tmp, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        tmp.replace(path)
    
    def get_signals_sent_today(self) -> List[Dict]:
        """Get all signals sent today (midnight UTC)."""
        today_utc = datetime.utcnow().date()
        today_signals = []
        
        for sig in self.all_signals:
            sent_time = datetime.fromisoformat(sig['generated_at'])
            if sent_time.date() == today_utc:
                today_signals.append(sig)
        
        return today_signals
    
    def get_signal_status(self, symbol: str, signal_type: str) -> Optional[Dict]:
        """Find latest signal for symbol+type and return its current status."""
        # Find most recent signal for this symbol+type
        matching = [
            s for s in reversed(self.all_signals)
            if s.get('symbol') == symbol and s.get('signal_type') == signal_type
        ]
        
        if not matching:
            return None
        
        latest = matching[0]
        
        # Get current price from exchange
        current_price = self._fetch_current_price(symbol)
        
        return {
            'symbol': symbol,
            'signal_type': signal_type,
            'entry': latest['entry'],
            'stop_loss': latest['stop_loss'],
            'targets': latest['targets'],
            'status': latest.get('outcome', 'OPEN'),
            'current_price': current_price,
            'highest_target_hit': latest.get('highest_target_hit', 0),
            'generated_at': latest['generated_at'],
        }
    
    def _fetch_current_price(self, symbol: str) -> float:
        """Call your exchange API to get current price."""
        # Use your existing data_fetcher
        # from core.data_fetcher import DataFetcher
        # fetcher = DataFetcher()
        # return fetcher.get_current_price(symbol)
        pass
    
    def should_send_update(self, new_signal: Dict) -> Tuple[bool, Optional[Dict]]:
        """
        Check if new_signal was already sent today.
        Returns: (should_send_update, previous_signal_status or None)
        """
        symbol = new_signal['symbol']
        signal_type = new_signal['signal_type']
        
        prev = self.get_signal_status(symbol, signal_type)
        if prev:
            # Was already sent - check if it's still in top5
            # (if it dropped out of top5, don't send update)
            return True, prev
        
        return False, None
    
    def add_signal(self, signal: Dict):
        """Add new signal to memory."""
        signal['generated_at'] = datetime.utcnow().isoformat()
        signal['signal_id'] = f"{signal['symbol']}_{signal['signal_type']}_{signal['rank']}"
        
        self.all_signals.append(signal)
        self._save_json(self.all_signals_file, self.all_signals)
```

**Step B: Format update alert**

Add to `src/alert_service.py` (or wherever alerts are formatted):

```python
def format_signal_update(self, new_signal: Dict, previous: Dict) -> str:
    """
    Create UPDATE message for recurring signal.
    """
    symbol = new_signal['symbol']
    entry = previous['entry']
    sl = previous['stop_loss']
    targets = previous['targets']
    current = previous['current_price']
    hit_count = previous.get('highest_target_hit', 0)
    
    # Calculate metrics
    pnl_pct = ((current - entry) / entry) * 100
    dist_to_sl = abs((current - sl) / sl * 100)
    
    # Build targets string
    target_lines = []
    for i, t in enumerate(targets, 1):
        if i <= hit_count:
            target_lines.append(f"T{i}: ${t:.2f} ✅ HIT")
        else:
            dist = ((t - current) / current) * 100
            target_lines.append(f"T{i}: ${t:.2f} ({dist:+.1f}%)")
    
    msg = f"""🔄 SIGNAL UPDATE - #{new_signal['rank']} - {symbol}

📈 Progress: {'🔺' if pnl_pct >= 0 else '🔻'} {pnl_pct:+.1f}%
📍 Current: ${current:.2f}
🎯 Targets: {' | '.join(target_lines)}

📊 New Ranking:
   Rank: #{new_signal['rank']}/5
   Score: {new_signal['score']:.0f}/100
   Strategy: {new_signal['strategy']}

original_signal: {previous['generated_at']}
"""
    return msg
```

**Step C: Integrate into main loop**

In `main.py`, where signals are sent:

```python
from ai.signal_memory import SignalMemory
signal_memory = SignalMemory()

def process_signal(self, signal: Dict):
    symbol = signal['symbol']
    
    # Check if already sent today
    is_update, previous = signal_memory.should_send_update(signal)
    
    if is_update and previous:
        # Send UPDATE
        msg = self.alert_service.format_signal_update(signal, previous)
        msg_type = "UPDATE"
    else:
        # Send NEW signal
        msg = self.alert_service.format_new_signal(signal)
        msg_type = "NEW"
    
    # Send alert
    self.alert_service.send(msg)
    
    # Log to journal
    self.trade_journal.record_signal(signal, msg_type=msg_type)
    
    # Store in memory
    signal_memory.add_signal(signal)
    
    logger.info(f"Sent {msg_type} alert for {symbol} (rank #{signal['rank']})")
```

---

### 4. Stop Loss & Target Validation

**Ensure every signal's SL and targets are technically sound before sending.**

**Create `src/trade_validator.py` (if not exists):**

```python
"""
Trade Validator - Ensures SL/targets are valid.
"""

class TradeValidator:
    def __init__(self, config: Dict):
        self.config = config
        self.min_rr = config.get('min_risk_reward', 1.5)
        self.max_sl_pct = config.get('max_stop_loss_pct', 5.0)
        self.min_sl_pct = config.get('min_stop_loss_pct', 1.0)
    
    def validate(self, signal: Dict, indicators: Dict) -> Dict:
        """
        Full validation. Returns {valid: bool, errors: []}
        """
        errors = []
        entry = signal['entry']
        sl = signal['stop_loss']
        targets = signal['targets']
        
        # 1. Validate STOP LOSS
        sl_valid, sl_errors = self.validate_stop_loss(entry, sl, indicators)
        errors.extend(sl_errors)
        
        # 2. Validate TARGETS
        t_valid, t_errors = self.validate_targets(entry, sl, targets, indicators)
        errors.extend(t_errors)
        
        # 3. Validate R:R
        risk = abs(entry - sl)
        t1_reward = abs(targets[0] - entry)
        rr = t1_reward / risk if risk > 0 else 0
        if rr < self.min_rr:
            errors.append(f"R:R too low: {rr:.1f} < {self.min_rr}")
        
        # 4. Score threshold
        if signal.get('score', 0) < self.config.get('min_signal_score', 60):
            errors.append(f"Score too low: {signal.get('score', 0):.0f}")
        
        # 5. Volume confirmation
        volume_ratio = indicators.get('volume_ratio', 0)
        if volume_ratio < 1.2:
            errors.append(f"Insufficient volume: {volume_ratio:.1f}x")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }
    
    def validate_stop_loss(self, entry: float, sl: float, ind: Dict) -> Tuple[bool, List[str]]:
        errors = []
        
        sl_pct = abs((sl - entry) / entry * 100)
        
        # Must be below entry for long
        if sl >= entry:
            errors.append("SL must be below entry for long signals")
        
        # Not too tight
        if sl_pct < self.min_sl_pct:
            errors.append(f"SL too tight: {sl_pct:.1f}% < {self.min_sl_pct}%")
        
        # Not too wide
        if sl_pct > self.max_sl_pct:
            errors.append(f"SL too wide: {sl_pct:.1f}% > {self.max_sl_pct}%")
        
        # Should respect nearest swing low
        swing_low = ind.get('swing_low')
        if swing_low and sl < swing_low * 0.98:
            # SL is below recent swing low (OK, but maybe too conservative?)
            pass  # Acceptable but could note
        
        return len(errors) == 0, errors
    
    def validate_targets(self, entry: float, sl: float, targets: List[float], ind: Dict) -> Tuple[bool, List[str]]:
        errors = []
        risk = abs(entry - sl)
        
        if len(targets) < 2:
            errors.append("Need at least 2 targets")
            return False, errors
        
        for i, target in enumerate(targets, 1):
            reward = abs(target - entry)
            rr = reward / risk if risk > 0 else 0
            
            # R:R thresholds
            if i == 1 and rr < 1.5:
                errors.append(f"T1 R:R too low: {rr:.1f} < 1.5")
            if i == 2 and rr < 2.5:
                errors.append(f"T2 R:R too low: {rr:.1f} < 2.5")
            
            # Target shouldn't be beyond nearest resistance
            resistance = self._find_resistance(entry, ind)
            if target > resistance * 1.1:  # 10% buffer
                errors.append(f"T{i} beyond measurable resistance")
        
        return len(errors) == 0, errors
    
    def _find_resistance(self, entry: float, ind: Dict) -> float:
        """Find nearest resistance level."""
        swing_high = ind.get('swing_high')
        if swing_high and swing_high > entry:
            return swing_high
        # Fallback: EMA-based resistance
        ema20 = ind.get('ema20', entry)
        return max(entry * 1.02, ema20 * 1.01)
```

**Usage in main loop:**

```python
validator = TradeValidator(config)

def process_signal(self, signal):
    indicators = self._get_indicators(signal['symbol'])
    validation = validator.validate(signal, indicators)
    
    if not validation['valid']:
        logger.warning(f"Signal rejected: {validation['errors']}")
        return  # Don't send
    
    # Passed - send it
    self.send_alert(signal)
```

---

### 5. Learning & Optimization System

**Goal:** System learns from past trades and improves over time.

**Component A: Trade Journal**

Create `src/trade_journal.py`:

```python
"""
Trade Journal - Records every signal and outcome.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

@dataclass
class Trade:
    trade_id: str
    symbol: str
    strategy: str
    direction: str
    entry: float
    stop_loss: float
    targets: List[float]
    timestamp: str
    outcome: str  # WIN / LOSS / OPEN / TIMEOUT
    rr_achieved: float = 0.0
    max_drawdown: float = 0.0
    max_profit: float = 0.0
    targets_hit: List[int] = None
    holding_days: float = 0.0
    quality: str = "B"
    market_context: str = "BULLISH"
    # ... more fields as needed

class TradeJournal:
    def __init__(self, filepath: str = 'data/trade_journal.json'):
        self.filepath = Path(filepath)
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        self.trades: List[Dict] = self._load()
    
    def _load(self) -> List[Dict]:
        if self.filepath.exists():
            with open(self.filepath) as f:
                data = json.load(f)
                return data.get('trades', [])
        return []
    
    def _save(self):
        tmp = self.filepath.with_suffix('.tmp')
        with open(tmp, 'w') as f:
            json.dump({'trades': self.trades}, f, indent=2, default=str)
        tmp.replace(self.filepath)
    
    def add_signal(self, signal: Dict):
        """Record signal before it's opened."""
        trade = Trade(
            trade_id=signal['signal_id'],
            symbol=signal['symbol'],
            strategy=signal['strategy'],
            direction=signal['direction'],
            entry=signal['entry'],
            stop_loss=signal['stop_loss'],
            targets=signal['targets'],
            timestamp=datetime.utcnow().isoformat(),
            outcome='OPEN',
            quality=signal.get('quality', 'B'),
            market_context=signal.get('market_context', 'NEUTRAL')
        )
        self.trades.append(asdict(trade))
        self._save()
    
    def close_trade(self, trade_id: str, outcome: str, exit_price: float):
        """Mark trade as closed with outcome."""
        for trade in self.trades:
            if trade['trade_id'] == trade_id:
                trade['outcome'] = outcome
                trade['exit_price'] = exit_price
                trade['closed_at'] = datetime.utcnow().isoformat()
                
                # Calculate P&L
                entry = trade['entry']
                if outcome == 'WIN':
                    # Assume hit T1 or better
                    trade['exit_price'] = trade['targets'][0]
                elif outcome == 'LOSS':
                    trade['exit_price'] = trade['stop_loss']
                
                # Calculate RR achieved
                if outcome == 'WIN':
                    trade['rr_achieved'] = abs((trade['exit_price'] - entry) / 
                                                abs(entry - trade['stop_loss']))
                
                self._save()
                break
    
    def get_closed_trades(self, limit: int = 100) -> List[Dict]:
        """Get recently closed trades."""
        closed = [t for t in self.trades if t.get('outcome') in ['WIN', 'LOSS']]
        return closed[-limit:]
    
    def get_open_trades(self) -> List[Dict]:
        """Get currently open trades."""
        return [t for t in self.trades if t.get('outcome') == 'OPEN']
    
    def get_trades_by_strategy(self, strategy: str) -> List[Dict]:
        return [t for t in self.trades if t.get('strategy') == strategy]
```

**Component B: Strategy Optimizer**

Create `src/strategy_optimizer.py`:

```python
"""
Strategy Performance Tracker & Auto-Optimizer
"""

from collections import defaultdict
from typing import Dict, List

class StrategyOptimizer:
    """
    Tracks performance per strategy and adjusts weights.
    """
    
    def __init__(self, trade_journal):
        self.trade_journal = trade_journal
        self.weights = {
            'TREND': 1.0,
            'VERC': 0.8,
            'MTF': 0.9
        }
    
    def calculate_strategy_stats(self, strategy: str, days: int = 30) -> Dict:
        """Calculate win rate, avg RR, profit factor for strategy."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        recent_trades = [
            t for t in self.trade_journal.get_trades_by_strategy(strategy)
            if datetime.fromisoformat(t['timestamp']) > cutoff
        ]
        
        if not recent_trades:
            return {'win_rate': 0, 'avg_rr': 0, 'profit_factor': 0, 'trades': 0}
        
        wins = [t for t in recent_trades if t['outcome'] == 'WIN']
        losses = [t for t in recent_trades if t['outcome'] == 'LOSS']
        
        win_rate = len(wins) / len(recent_trades)
        
        avg_rr = sum(t['rr_achieved'] for t in wins) / len(wins) if wins else 0
        
        # Profit factor = gross profit / gross loss
        gross_profit = sum(
            t['rr_achieved'] * 1  # simplified
            for t in wins
        )
        gross_loss = sum(1 for _ in losses)  # simplified: each loss = 1R
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        return {
            'trades': len(recent_trades),
            'win_rate': win_rate,
            'avg_rr': avg_rr,
            'profit_factor': profit_factor
        }
    
    def optimize_weights(self):
        """
        Adjust strategy weights based on recent performance.
        Call this after every 20+ closed trades.
        """
        for strategy in self.weights:
            stats = self.calculate_strategy_stats(strategy, days=30)
            
            if stats['trades'] < 10:
                continue  # Not enough data
            
            win_rate = stats['win_rate']
            old_weight = self.weights[strategy]
            
            # Increase if winning > 55%, decrease if < 45%
            if win_rate > 0.55:
                new_weight = min(2.0, old_weight * 1.1)
            elif win_rate < 0.45:
                new_weight = max(0.5, old_weight * 0.9)
            else:
                new_weight = old_weight
            
            self.weights[strategy] = new_weight
            
            if new_weight != old_weight:
                logger.info(f"Optimized {strategy}: {old_weight:.2f} → {new_weight:.2f} (WR: {win_rate:.1%})")
        
        return self.weights
```

**Component C: Pattern Learning Recognizer**

Create `src/pattern_learning.py`:

```python
"""
Pattern Learning Recognizer
Analyzes trade journal to learn which patterns work best.
"""

from collections import defaultdict
from typing import Dict, List

class PatternLearning:
    def __init__(self, trade_journal):
        self.trade_journal = trade_journal
        self.insights = []
    
    def analyze_patterns(self, limit: int = 100) -> Dict:
        """
        Analyze recent trades to generate insights.
        Returns dict with insights and recommendations.
        """
        closed_trades = self.trade_journal.get_closed_trades(limit=limit)
        
        if len(closed_trades) < 20:
            return {'insights': [], 'message': 'Need 20+ trades for analysis'}
        
        # Group by strategy
        by_strategy = defaultdict(list)
        for t in closed_trades:
            by_strategy[t['strategy']].append(t)
        
        insights = []
        
        for strategy, trades in by_strategy.items():
            wins = [t for t in trades if t['outcome'] == 'WIN']
            win_rate = len(wins) / len(trades)
            avg_rr = sum(t['rr_achieved'] for t in wins) / len(wins) if wins else 0
            
            insights.append({
                'type': 'STRATEGY_PERFORMANCE',
                'strategy': strategy,
                'trades': len(trades),
                'win_rate': win_rate,
                'avg_rr': avg_rr,
                'recommendation': self._get_recommendation(win_rate, avg_rr)
            })
        
        # Also analyze by market regime
        by_regime = defaultdict(list)
        for t in closed_trades:
            by_regime[t['market_context']].append(t)
        
        for regime, trades in by_regime.items():
            if len(trades) < 10:
                continue
            wins = [t for t in trades if t['outcome'] == 'WIN']
            win_rate = len(wins) / len(trades)
            
            insights.append({
                'type': 'REGIME_ANALYSIS',
                'regime': regime,
                'trades': len(trades),
                'win_rate': win_rate,
                'recommendation': f"Market regime {regime} win rate: {win_rate:.0%}"
            })
        
        return {'insights': insights}
    
    def _get_recommendation(self, win_rate: float, avg_rr: float) -> str:
        if win_rate > 0.65 and avg_rr > 2.0:
            return "INCREASE strategy weight (excellent performance)"
        elif win_rate < 0.40:
            return "DECREASE strategy weight (poor performance)"
        else:
            return "Maintain current weight"
```

**Step 4: Wire learning into scan cycle**

In `main.py`, add learning cycle:

```python
from pattern_learning import PatternLearning
from trade.strategy_optimizer import StrategyOptimizer

# In __init__:
self.trade_journal = TradeJournal()
self.optimizer = StrategyOptimizer(self.trade_journal)
self.learning = PatternLearning(self.trade_journal)

# After each scan or daily, check if learning should run:
def maybe_run_learning(self):
    """Run learning cycle if enough trades closed."""
    closed_trades = self.trade_journal.get_closed_trades(limit=100)
    
    if len(closed_trades) >= 20:
        # Analyze patterns
        analysis = self.learning.analyze_patterns(limit=100)
        insights = analysis.get('insights', [])
        
        for insight in insights:
            logger.info(f"[LEARNING] {insight['recommendation']}")
        
        # Optimize weights
        new_weights = self.optimizer.optimize_weights()
        logger.info(f"Updated strategy weights: {new_weights}")
        
        # Save insights
        self._save_learning_report(analysis)
```

Run this after every scan or daily at market close.

---

## Code to Add/Modify Summary

**New files to create:**
1. `src/signal_scorer.py` - scoring engine
2. Extend `src/signal_memory.py` - add daily tracking + update logic
3. Extend `src/alert_service.py` - add `format_signal_update()` method
4. `src/trade_journal.py` - full journal (if not already present)
5. `src/strategy_optimizer.py` - auto-weight adjustment
6. `src/pattern_learning.py` - pattern analysis
7. `src/api.py` - Flask API (from NSE)
8. `templates/` & `static/` - UI files (from NSE)

**Files to modify:**
- `src/main.py` - add top5 selection, update checks, learning cycle
- `config/settings.json` - add new settings
- `requirements.txt` - add flask, flask-cors

---

## Implementation Order

Work in this order:

**Day 1:**
1. Add Flask, create `api.py`, verify `/api/dashboard` works with placeholder data
2. Copy UI templates/static, verify pages load
3. Connect API to real trade journal data
4. Top5 implementation (scoring + ranking)
5. Verify only 5 signals processed per cycle

**Day 2:**
6. Signal update mechanism (daily tracking)
7. Update alert formatting
8. Stop loss/target validation
9. Test new signal vs update flow

**Day 3:**
10. Trade journal implementation
11. Strategy optimizer
12. Pattern learning
13. Wire learning into scan cycle
14. Test: generate 20+ test trades, see weights adjust

**Day 4:**
15. UI polish - show top5 in dashboard
16. Add `/api/signals/top5` endpoint
17. Monitoring/logging
18. Full end-to-end test

---

## Testing Commands

```bash
# Unit tests
python -m pytest tests/test_signal_scorer.py -v
python -m pytest tests/test_validator.py -v
python -m pytest tests/test_signal_memory.py -v

# Integration test
python -m pytest tests/test_top5_flow.py -v

# Manual test
python src/main.py --test  # Single scan
# Check: only 5 signals processed, logs show ranking

# UI test
python src/api.py &
curl http://localhost:5000/api/dashboard
curl http://localhost:5000/api/signals/top5
```

---

## Success Criteria - Pass/Fail

✅ **PASS** if:
- UI displays all pages with live data
- Scanner sends exactly 5 signals per cycle (or fewer if <5 qualify)
- Duplicate/recurring signal triggers UPDATE alert (not NEW)
- All signals pass validation before sending
- Trade journal stores complete signal data
- After 20+ closed trades, strategy weights adjust automatically
- Dashboard shows current top5 signals with rankings

❌ **FAIL** if:
- More than 5 signals sent on any cycle
- Same signal sent twice in same day as NEW
- Invalid SL (too tight/wide) passes through
- Invalid targets (poor R:R) passes through
- Trade journal missing required fields
- Learning doesn't adjust weights
- UI errors or blank pages

---

## Quick Validation

After implementation, answer these:

1. **Top5:** Does scanner send exactly 5 signals max per cycle? ✓
2. **Updates:** Does recurring top5 signal get UPDATE not NEW? ✓
3. **Validation:** Do ALL signals have score ≥60, R:R ≥1.5, SL 1-5%? ✓
4. **Journal:** Is every signal (new OR update) in trade_journal.json? ✓
5. **Learning:** Do strategy weights change after 20 closed trades? ✓
6. **UI:** Does `/api/signals/top5` return JSON with rank, symbol, score? ✓

If YES to all → implementation complete.

---

## Notes

- The NSE code is **production-ready** - copy patterns directly
- Crypto adaptation: replace yfinance with exchange API, adjust volatility parameters
- Test on small capital first
- Monitor learning insights weekly - ensure they make sense
- Never skip validation

Good luck. Start with the scoring + top5, then updates, then validation, then learning. UI can be done in parallel.
