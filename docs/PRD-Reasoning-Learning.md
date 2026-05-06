# NSE Trend Agent - Reasoning & Learning Module
## Product Requirements Document (PRD)

**Version:** 3.0  
**Date:** 2026-04-14  
**Author:** Product Team  
**Status:** Production - Agentic AI v3.0  

---

## 1. Executive Summary

This document outlines the Product Requirements for the **NSE Trend Agent v3.0** with **Agentic AI** capabilities:

1. **Agentic AI Controller** - An autonomous agent that uses LLM to decide when to SCAN, WAIT, or ADJUST strategy based on market conditions.

2. **Enhanced Reasoning Engine** - A hybrid system combining rule-based algorithms, weighted scoring, and AI-driven reasoning to generate more accurate and nuanced trading signals.

3. **Learning & Feedback System** - A closed-loop learning mechanism that tracks signal outcomes, measures accuracy, and continuously improves signal quality through historical performance analysis.

### 1.1 Problem Statement

The NSE Trend Agent (v2.x) generates trading signals using:
- Rule-based algorithms (VERC, Trend Detection, MTF)
- AI/LLM-based analysis
- Market context detection

However, it lacks:
- **Autonomous decision-making** - Scanner runs on fixed schedule regardless of conditions
- **Market-aware action selection** - No ability to skip unfavorable scans
- **Strategy adaptation** - No automatic strategy adjustment based on performance

### 1.2 Proposed Solution (v3.0)

Implement an **Agentic AI Controller** that:

- **Uses LLM to analyze market conditions** in real-time
- **Decides actions autonomously**: SCAN/WAIT/ADJUST/MONITOR/ANALYZE
- **Classifies market regime**: BULLISH/BEARISH/SIDEWAYS/VOLATILE
- **Self-corrects** based on win/loss streaks
- **Provides natural language explanations** for every decision

### 1.2 Proposed Solution

Implement a hybrid reasoning engine that combines:
- **Rule-Based Algorithms** (existing) - Technical indicators, patterns
- **Weighted Scoring** - Multi-factor scoring with configurable weights
- **AI Reasoning** (enhanced) - LLM-powered contextual analysis

Plus a Learning System that:
- Tracks all generated signals until completion (stop-loss hit or target achieved)
- Measures accuracy and performance metrics
- Provides continuous accuracy scores for signals
- Notifies users of signal outcomes via Telegram

---

## 2. Product Vision

> *To create an intelligent stock scanning system that learns from market outcomes, continuously improves signal accuracy, and provides transparent performance metrics to users.*

### 2.1 Goals

| Goal ID | Description | Success Criteria |
|---------|-------------|------------------|
| G1 | Implement hybrid reasoning engine | Combined score available for all signals |
| G2 | Track signal outcomes | 100% of signals tracked until completion |
| G3 | Provide accuracy scores | Accuracy score displayed per signal |
| G4 | Notify signal outcomes | Telegram notifications on stop-loss/target |
| G5 | Maintain history | All signal data persisted for analysis |

---

## 3. Functional Requirements

### 3.1 Enhanced Reasoning Engine (Hybrid Reasoning)

#### 3.1.1 Rule-Based Component (Existing)

Continue using existing rule-based algorithms:

| Algorithm | Purpose | Signal Types |
|-----------|---------|--------------|
| Trend Detector | EMA alignment & volume confirmation | TREND_START, TREND_CONTINUATION |
| VERC Scanner | Volume expansion range compression | BREAKOUT, ACCUMULATION |
| Indicator Engine | Technical indicators (RSI, ATR, etc.) | OVERBOUGHT, OVERSOLD |

#### 3.1.2 Weighted Scoring Component

Implement a multi-factor weighted scoring system:

```
Final Score = Σ (Factor Score × Factor Weight)

Where:
- Factor Score = 0-100 normalized score
- Factor Weight = configurable weight (default: see table)
```

**Scoring Factors:**

| Factor | Category | Default Weight | Description |
|--------|----------|----------------|-------------|
| EMA Alignment | Technical | 15% | Score based on EMA20 > EMA50 > EMA100 > EMA200 |
| Volume Confirmation | Technical | 15% | Volume > Volume MA30 ratio |
| RSI Position | Technical | 10% | Optimal: 40-70 for buy |
| ATR Volatility | Technical | 10% | Lower ATR% = higher score |
| VERC Score | Pattern | 20% | VERC confidence score |
| RSI Divergence | Technical | 10% | Price/Volume divergence detection |
| Market Context | External | 10% | Nifty/sector trend alignment |
| Price Momentum | Technical | 10% | Recent price action strength |

**Score Calculation Rules:**
- Each factor normalized to 0-100
- Weights must sum to 100%
- Minimum threshold for signal: Final Score ≥ 60
- Signal Strength categories:
  - Strong Buy: 80-100
  - Buy: 60-79
  - Neutral: 40-59
  - Sell: 20-39
  - Strong Sell: 0-19

#### 3.1.3 AI Reasoning Component (Enhanced)

Enhance existing AI analyzer to provide:

1. **Contextual Analysis**
   - Current market conditions
   - Sector performance
   - Global market cues

2. **Pattern Recognition**
   - Chart patterns (if applicable)
   - Candlestick patterns
   - Volume-price divergence

3. **Multi-Timeframe Validation**
   - Daily, weekly, monthly analysis
   - Confluence detection

4. **Risk Assessment**
   - Risk-reward ratio calculation
   - Maximum downside estimate
   - Position sizing recommendation

5. **Reasoning Explanation**
   - Human-readable explanation of score
   - Key positive/negative factors listed

#### 3.1.4 Combined Signal Output

All signals must include:

```python
{
    "signal_id": "UUID",
    "stock_symbol": "RELIANCE",
    "timestamp": "2026-03-23T10:30:00",
    
    # Rule-Based Signals
    "rule_signals": {
        "trend_detector": {"signal": "TREND_START", "confidence": 85},
        "verc": {"signal": "BREAKOUT", "confidence": 78}
    },
    
    # Weighted Score
    "weighted_score": {
        "final_score": 72,
        "strength": "BUY",
        "factors": {
            "ema_alignment": {"score": 85, "weight": 15, "contribution": 12.75},
            "volume_confirmation": {"score": 80, "weight": 15, "contribution": 12.0},
            # ... all factors
        }
    },
    
    # AI Reasoning
    "ai_reasoning": {
        "recommendation": "BUY",
        "confidence": 7,
        "reasoning": "...",
        "risk_reward_ratio": "1:3",
        "entry_zone": "2450-2480",
        "stop_loss": "2400",
        "targets": ["2600", "2750"]
    },
    
    # Combined Signal
    "combined_signal": {
        "recommendation": "BUY",
        "final_score": 75,
        "strength": "STRONG_BUY",
        "explanation": "..."
    }
}
```

---

### 3.2 Learning & Feedback System

#### 3.2.1 Signal Tracking

**Active Signal Management:**

| Attribute | Description |
|-----------|-------------|
| Signal ID | Unique identifier (UUID) |
| Stock Symbol | NSE stock symbol |
| Entry Date | When signal was generated |
| Entry Price | Price at signal generation |
| Stop Loss | Configured stop loss |
| Target 1 | First target price |
| Target 2 | Second target price |
| Status | ACTIVE / COMPLETED / EXPIRED |
| Outcome | PENDING / HIT_SL / HIT_T1 / HIT_T2 / TIMEOUT |

#### 3.2.2 Tracking Frequency

- **Scan Interval:** Every 15 minutes (configurable)
- **Active Monitoring:** Check all active signals in each scan
- **Status Update:** Mark signal as COMPLETED when:
  - Stop loss hit
  - Target 1 hit
  - Target 2 hit
  - Signal expired (configurable: default 30 days)

#### 3.2.3 Accuracy Scoring System

**Named: Signal Intelligence Quotient (SIQ)**

```
SIQ Score = (Successful Signals / Total Signals) × 100

Where:
- Successful = Target 1 or Target 2 hit before stop loss
- Total = All completed signals
```

**Score Display:**

| SIQ Range | Rating | Color Code |
|-----------|--------|------------|
| 80-100% | Excellent | 🟢 Green |
| 60-79% | Good | 🔵 Blue |
| 40-59% | Average | 🟡 Yellow |
| 20-39% | Below Average | 🟠 Orange |
| 0-19% | Poor | 🔴 Red |

**Per-Signal SIQ:**
- Track individual signal performance
- Show expected accuracy based on similar past signals
- Display on signal notification

#### 3.2.4 Performance Metrics

Track and display:

| Metric | Description | Calculation |
|--------|-------------|-------------|
| Total Signals | Count of all signals generated | COUNT(*) |
| Active Signals | Currently tracked signals | COUNT WHERE status=ACTIVE |
| Completed Signals | Signals that reached outcome | COUNT WHERE status=COMPLETED |
| Success Rate | % hitting targets | (HIT_T1 + HIT_T2) / COMPLETED |
| Failure Rate | % hitting stop loss | HIT_SL / COMPLETED |
| Avg Holding Days | Average days to resolution | AVG(resolution_date - entry_date) |
| Avg Return % | Average return on successful signals | AVG((exit_price - entry_price) / entry_price) |

#### 3.2.5 Outcome Notifications

**Telegram Notifications:**

1. **Signal Generated** (existing)
   ```
   📈 NEW SIGNAL: RELIANCE
   
   Type: STRONG_BUY
   Score: 78 (SIQ: 72%)
   Entry: ₹2450-2480
   SL: ₹2400 | T1: ₹2600 | T2: ₹2750
   
   Reason: [AI reasoning summary]
   ```

2. **Target 1 Hit**
   ```
   🎯 TARGET 1 HIT: RELIANCE
   
   Entry: ₹2450
   Target 1: ₹2600
   Return: +6.12%
   
   Continue to Target 2? Check AI recommendation.
   ```

3. **Target 2 Hit**
   ```
   🎉 TARGET 2 HIT: RELIANCE
   
   Entry: ₹2450
   Target 2: ₹2750
   Return: +12.24%
   
   ✅ Signal completed successfully!
   ```

4. **Stop Loss Hit**
   ```
   🛡️ STOP LOSS HIT: RELIANCE
   
   Entry: ₹2450
   Stop Loss: ₹2400
   Loss: -2.04%
   
   💡 Learning: Reviewing this signal for pattern improvement.
   ```

5. **Daily Summary**
   ```
   📊 DAILY SIGNAL SUMMARY
   
   Active: 5 | Completed: 2
   Today's Performance: +6.12%
   
   Overall SIQ: 68% (Good)
   
   Most Recent: RELIANCE (+6.12%)
   ```

6. **Weekly Report**
   ```
   📈 WEEKLY PERFORMANCE REPORT
   
   Signals Generated: 12
   Success Rate: 75% (9/12)
   Total Return: +₹12,450
   
   Top Performers:
   - RELIANCE: +12.24%
   - HDFCBANK: +8.5%
   
   Improvement Areas:
   - INFY: 2/3 signals hit SL
   ```

#### 3.2.6 Feedback Loop Mechanism

**Learning Process:**

1. **Signal Completion**
   - When signal completes, record outcome
   - Calculate accuracy metrics
   - Store in history

2. **Pattern Analysis**
   - Identify common factors in successful vs failed signals
   - Adjust factor weights based on historical performance
   - Flag patterns for investigation

3. **Weight Adjustment**
   - Auto-tune weights based on performance
   - Major changes require manual approval
   - Store weight history for rollback capability

4. **AI Model Improvement**
   - Feed outcomes back to improve AI prompts
   - Highlight successful patterns in AI context
   - Adjust AI confidence thresholds

---

## 4. Technical Architecture

### 4.1 New Components

```
┌─────────────────────────────────────────────────────────────────────┐
│                        NSE TREND AGENT v2.0                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐           │
│  │ RULE-BASED   │   │   WEIGHTED   │   │    AI        │           │
│  │ ALGORITHMS   │ → │   SCORING    │ → │  REASONING   │           │
│  │              │   │              │   │              │           │
│  │ - Trend      │   │ - Multi-     │   │ - LLM        │           │
│  │ - VERC       │   │   factor     │   │   Analysis   │           │
│  │ - Indicators │   │   scoring    │   │ - Context    │           │
│  └──────────────┘   └──────────────┘   └──────────────┘           │
│          │                  │                  │                 │
│          └──────────────────┼──────────────────┘                 │
│                             ▼                                      │
│                    ┌──────────────┐                               │
│                    │   COMBINED   │                               │
│                    │   SIGNAL     │                               │
│                    │   ENGINE     │                               │
│                    └──────────────┘                               │
│                             │                                      │
│                             ▼                                      │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │                    LEARNING MODULE                          │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │ │
│  │  │   SIGNAL    │  │   OUTCOME   │  │   PERFORMANCE       │   │ │
│  │  │   TRACKER   │→ │   TRACKER   │→ │   ANALYTICS        │   │ │
│  │  └─────────────┘  └─────────────┘  └─────────────────────┘   │ │
│  │         │                 │                  │                │ │
│  │         ▼                 ▼                  ▼                │ │
│  │  ┌──────────────────────────────────────────────────────┐   │ │
│  │  │              HISTORY DATABASE (JSON/SQLite)          │   │ │
│  │  └──────────────────────────────────────────────────────┘   │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                             │                                      │
│                             ▼                                      │
│                    ┌──────────────┐                               │
│                    │    TELEGRAM  │                               │
│                    │   NOTIFIER   │                               │
│                    └──────────────┘                               │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.2 New Modules

| Module | File | Responsibility |
|--------|------|----------------|
| Combined Signal Engine | `src/reasoning_engine.py` | Merge rule, weighted, and AI signals |
| Signal Tracker | `src/signal_tracker.py` | Track active signals until completion |
| Performance Analytics | `src/performance_tracker.py` | Calculate SIQ and metrics |
| History Manager | `src/history_manager.py` | Persist signal data |
| Notification Enhancer | `src/notification_manager.py` | Send outcome notifications |

### 4.3 Data Storage

**Primary: JSON Files (for simplicity)**

| File | Purpose | Location |
|------|---------|----------|
| `signals_active.json` | Currently active signals | `data/` |
| `signals_history.json` | All completed signals | `data/` |
| `performance_metrics.json` | SIQ scores and metrics | `data/` |
| `weight_config.json` | Scoring weights | `config/` |

**Schema: signals_history.json**

```json
{
    "version": "1.0",
    "last_updated": "2026-03-23T15:00:00",
    "signals": [
        {
            "signal_id": "uuid",
            "stock_symbol": "RELIANCE",
            "signal_type": "STRONG_BUY",
            "generated_at": "2026-03-20T10:30:00",
            "entry_price": 2450,
            "stop_loss": 2400,
            "target_1": 2600,
            "target_2": 2750,
            "weighted_score": {
                "final_score": 78,
                "strength": "STRONG_BUY",
                "factors": {...}
            },
            "ai_reasoning": {
                "recommendation": "BUY",
                "confidence": 8,
                "reasoning": "..."
            },
            "status": "COMPLETED",
            "outcome": "HIT_T1",
            "completed_at": "2026-03-22T14:15:00",
            "actual_exit": 2600,
            "return_pct": 6.12,
            "holding_days": 2,
            "signal_siq": 68
        }
    ]
}
```

### 4.4 API/Integration Points

| Integration | Method | Data Flow |
|-------------|--------|-----------|
| Data Fetcher | Direct call | Fetch current price for tracking |
| Alert Service | Direct call | Send outcome notifications |
| Scheduler | Callback | Check active signals on each scan |
| Telegram Bot | Message | Send alerts |

---

## 5. Configuration

### 5.1 New Settings

**config/settings.json additions:**

```json
{
    "reasoning": {
        "weights": {
            "ema_alignment": 15,
            "volume_confirmation": 15,
            "rsi_position": 10,
            "atr_volatility": 10,
            "verc_score": 20,
            "rsi_divergence": 10,
            "market_context": 10,
            "price_momentum": 10
        },
        "thresholds": {
            "min_signal_score": 60,
            "strong_buy_min": 80,
            "neutral_max": 59
        },
        "ai_enhancement": {
            "enabled": true,
            "include_reasoning": true,
            "confidence_weight": 0.3
        }
    },
    "learning": {
        "signal_tracking": {
            "enabled": true,
            "check_interval_minutes": 15,
            "expiry_days": 30,
            "auto_close_on_target": true
        },
        "notifications": {
            "signal_generated": true,
            "target_hit": true,
            "stop_loss_hit": true,
            "daily_summary": true,
            "weekly_report": true
        },
        "accuracy": {
            "siq_enabled": true,
            "calculate_on_completion": true
        }
    }
}
```

---

## 6. User Stories

| ID | User Story | Priority |
|----|------------|----------|
| US1 | As a user, I want to receive a signal score (0-100) along with recommendation so I can understand signal strength | P0 |
| US2 | As a user, I want to see which factors contributed to the signal score so I can validate the signal | P0 |
| US3 | As a user, I want signals tracked automatically until completion so I don't need manual monitoring | P0 |
| US4 | As a user, I want to receive Telegram notifications when my signal hits target or stop loss | P0 |
| US5 | As a user, I want to see the overall SIQ accuracy score to know how reliable the system is | P1 |
| US6 | As a user, I want a weekly performance report to understand system performance | P1 |
| US7 | As a user, I want configurable scoring weights so I can customize the system | P2 |
| US8 | As a user, I want to see historical signal performance for each stock | P2 |

---

## 7. Non-Functional Requirements

| Requirement | Description |
|-------------|-------------|
| Performance | Signal processing < 5 seconds for 50 stocks |
| Availability | 99.5% uptime during market hours |
| Scalability | Support 200+ stocks without degradation |
| Data Retention | Keep 2 years of signal history |
| Latency | Outcome notifications within 1 minute of event |

---

## 8. Implementation Phases

### Phase 1: Reasoning Engine (Week 1-2)

1. Create `reasoning_engine.py`
2. Implement weighted scoring algorithm
3. Integrate AI reasoning
4. Create combined signal output
5. Unit tests

### Phase 2: Learning System (Week 3-4)

1. Create `signal_tracker.py`
2. Create `history_manager.py`
3. Implement signal tracking logic
4. Add outcome detection (SL/Target)
5. Create notification templates

### Phase 3: Analytics & UI (Week 5-6)

1. Create `performance_tracker.py`
2. Implement SIQ calculation
3. Add daily/weekly reports
4. Telegram bot enhancements
5. Configuration UI

### Phase 4: Testing & Polish (Week 7-8)

1. Integration testing
2. Performance testing
3. User acceptance testing
4. Documentation
5. Production deployment

---

## 9. Dependencies & Risks

### 9.1 Dependencies

| Dependency | Description | Impact |
|------------|-------------|--------|
| yfinance | Stock data fetching | Required for tracking |
| Telegram Bot API | Notifications | Required for alerts |
| LLM Provider | AI reasoning | Required for enhanced analysis |

### 9.2 Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Signal overload | High | Implement minimum threshold filtering |
| API rate limits | Medium | Implement caching and rate limiting |
| Data gaps | Medium | Handle missing data gracefully |
| Accuracy degradation | Medium | Regular review and weight adjustment |

---

## 10. Success Metrics

| Metric | Target | Measurement |
|--------|--------|--------------|
| Signal Score Coverage | 100% | All signals have score |
| Outcome Tracking | 100% | All signals tracked to completion |
| Notification Delivery | 99% | Successful telegram delivery |
| SIQ Accuracy | >65% | Target achievement rate |
| False Positive Rate | <25% | Signals hitting SL before target |

---

## 11. Appendix

### A. Terminology

| Term | Definition |
|------|------------|
| SIQ | Signal Intelligence Quotient - accuracy score |
| VERC | Volume Expansion Range Compression |
| EMA | Exponential Moving Average |
| RSI | Relative Strength Index |
| ATR | Average True Range |
| SL | Stop Loss |
| T1/T2 | Target 1 / Target 2 |

### B. File Structure

```
nse-trend-agent/
├── config/
│   ├── settings.json (updated)
│   └── stocks.json
├── data/
│   ├── signals_active.json (new)
│   ├── signals_history.json (new)
│   └── performance_metrics.json (new)
├── src/
│   ├── reasoning_engine.py (new)
│   ├── signal_tracker.py (new)
│   ├── performance_tracker.py (new)
│   ├── history_manager.py (new)
│   ├── notification_manager.py (new)
│   └── ...
├── docs/
│   └── PRD-Reasoning-Learning.md (this file)
│   └── tests/
│       ├── test_reasoning.py (new)
│       └── test_learning.py (new)
```

---

## 11. v3.0 Agentic AI Implementation

### 11.1 Agent Controller Architecture

The Agentic AI is implemented in `src/agent_controller.py` with the following components:

| Component | Description |
|-----------|-------------|
| `AgentController` | Main class handling all agent logic |
| `AgentAction` | Enum: SCAN, WAIT, ADJUST_STRATEGY, MONITOR, ANALYZE, SEND_ALERT |
| `MarketRegime` | Enum: BULLISH, BEARISH, SIDEWAYS, VOLATILE, UNKNOWN |
| `AgentDecision` | Dataclass for LLM decision output |
| `AgentExplanation` | Natural language explanation wrapper |

### 11.2 Agent Decision Flow

```
1. Fetch Market Data
   └─ NIFTY 50, sectors, active signals, trade outcomes

2. LLM Analysis (analyze_and_decide)
   ├─ System prompt: Expert trading agent instructions
   ├─ Context: Market data, active trades, outcomes
   └─ Output: JSON decision

3. Execute Action
   ├─ SCAN: Run signal detection
   ├─ WAIT: Log skip, continue next cycle
   ├─ ADJUST: Modify strategy focus
   └─ MONITOR: Check active positions

4. Self-Correction (self_correct)
   └─ Track outcomes, adjust approach based on streaks
```

### 11.3 Agent State

Maintained in `data/agent_state.json`:
```json
{
  version: 3.0,
  last_decision: {...},
  market_regime: BULLISH,
  decision_history: [...],
  feedback_history: [...],
  streak: { wins: 3, losses: 1 }
}
```

### 11.4 Fallback Behavior

When LLM unavailable, agent uses rule-based fallback:

| Regime | Action | Strategy Focus |
|--------|--------|----------------|
| BULLISH | SCAN | TREND, MTF |
| BEARISH | WAIT | None |
| SIDEWAYS | SCAN | VERC, MTF |
| VOLATILE | WAIT | None |

---

**Document Version:** 3.0  
**Last Updated:** 2026-04-14  
**Status:** Production - Agentic AI v3.0 deployed