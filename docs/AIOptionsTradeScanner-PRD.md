# AIOptionsTradeScanner - Product Requirements Document

**Version:** 1.0  
**Date:** 2026-04-14  
**Project:** AI Options Trading Scanner  
**Base:** NSE Options Scanner Agent v3.0

---

## 1. Project Overview

### 1.1 Purpose

AIOptionsTradeScanner is an AI-powered options trading scanner that monitors NSE stocks and detects potential options trading opportunities. It extends the successful NSE Options Scanner with options-specific analysis, option chain data, Greeks tracking, and options pricing models.

### 1.2 Technology Stack

| Component     | Technology                                                  |
| ------------- | ----------------------------------------------------------- |
| Language      | Python                                                      |
| Data Source   | Yahoo Finance, NSE India API                                |
| Notifications | Telegram Bot                                                |
| AI            | Multi-Provider LLM (OpenAI, Anthropic, Google Gemini, Groq) |
| Options Data  | yfinance (options_chain), Custom NSE scraper                |

### 1.3 Core Value Proposition

> _AI-driven options trading signals where artificial intelligence makes the final call on all trade decisions, considering market structure, trend analysis, and real-time Greeks_

### 1.4 AI-First Architecture

| Component          | Role                                          |
| ------------------ | --------------------------------------------- |
| Rules/Indicators   | INPUTS - Provide data for AI analysis         |
| Technical Analysis | CONTEXT - Market structure for AI to evaluate |
| AI Decision Engine | DECISION MAKER - Final call on all signals    |
| Human Oversight    | REVIEW - Optional override capability         |

### 1.5 Signal Decision Flow

```
Data Collection → Technical Analysis → AI Analysis → AI Decision → Signal Generation
     ↓                ↓                   ↓            ↓              ↓
  Price/IV/    EMA/RSI/Volume/    Market Context   BUY/SELL/    Final Signal
  Options      Greeks              Analysis         WAIT         with Entry/SL/Target
```

---

## 2. Stock Universe & Data

### 2.1 Stock Universe

| Feature               | Status | Implementation         |
| --------------------- | ------ | ---------------------- |
| NIFTY 50 stocks       | ✅     | config/stocks.json     |
| NEXT 50 stocks        | ✅     | config/stocks.json     |
| MIDCAP 150 stocks     | ✅     | config/stocks.json     |
| SMALLCAP 250 stocks   | ✅     | config/stocks.json     |
| Total monitored       | ✅     | ~500 stocks            |
| F&O stocks only       | ✅     | Filter by NSE F&O list |
| High liquidity stocks | ✅     | Filter by volume       |

### 2.2 Data Fetching

| Feature                                 | Status | Implementation         |
| --------------------------------------- | ------ | ---------------------- |
| Real-time price data                    | ✅     | src/data_fetcher.py    |
| OHLCV data (1D)                         | ✅     | yfinance               |
| Option chain data                       | ✅     | yfinance.options_chain |
| Strike prices                           | ✅     | Available strikes      |
| Expiration dates                        | ✅     | Option expirations     |
| IV (Implied Volatility)                 | ✅     | yfinance               |
| Option volume                           | ✅     | yfinance               |
| OptionOI                                | ✅     | yfinance               |
| Greeks (Delta, Gamma, Theta, Vega, Rho) | ✅     | Calculated             |

### 2.3 Technical Indicators

| Feature                   | Description           |
| ------------------------- | --------------------- |
| EMA 20, 50, 100, 200      | Price moving averages |
| IV Percentile             | IV rank calculation   |
| IV vs HIV (Historical IV) | IV comparison         |
| PCR (Put-Call Ratio)      | Market sentiment      |
| Max Pain                  | Strike with max OI    |
| Support/Resistance        | Key price levels      |
| Volume MA                 | Volume confirmation   |

---

## 3. Options Trading Strategies

### 3.1 Strategy: Long Call (Bullish)

| Feature          | Description                         |
| ---------------- | ----------------------------------- |
| Entry            | EMA alignment + volume confirmation |
| Stock selection  | Strong momentum stock               |
| Strike selection | ATM or slightly OTM                 |
| Expiration       | 2-4 weeks                           |
| Exit             | Target reached or SL hit            |

### 3.2 Strategy: Long Put (Bearish)

| Feature          | Description              |
| ---------------- | ------------------------ |
| Entry            | Bearish EMA alignment    |
| Stock selection  | Weakening stock          |
| Strike selection | ATM or slightly OTM      |
| Expiration       | 2-4 weeks                |
| Exit             | Target reached or SL hit |

### 3.3 Strategy: Call Credit Spread (Neutral/Bullish)

| Feature    | Description                         |
| ---------- | ----------------------------------- |
| Entry      | Stock in range, IV elevated         |
| Setup      | Sell OTM call, buy further OTM call |
| Max profit | Credit received                     |
| Max loss   | Width - credit                      |
| Exit       | Manage at 50% loss                  |

### 3.4 Strategy: Put Credit Spread (Neutral/Bearish)

| Feature    | Description                       |
| ---------- | --------------------------------- |
| Entry      | Stock in range, IV elevated       |
| Setup      | Sell OTM put, buy further OTM put |
| Max profit | Credit received                   |
| Max loss   | Width - credit                    |
| Exit       | Manage at 50% loss                |

### 3.5 Strategy: Straddle (Volatility)

| Feature   | Description                     |
| --------- | ------------------------------- |
| Entry     | Pre-earnings, IV crush expected |
| Setup     | Buy ATM call + ATM put          |
| Direction | Neutral                         |
| Exit      | IV expansion or expiration      |

### 3.6 Strategy: Iron Condor (Range-Bound)

| Feature    | Description                                                       |
| ---------- | ----------------------------------------------------------------- |
| Entry      | Stock in consolidation                                            |
| Setup      | Sell OTM call + buy further call + sell OTM put + buy further put |
| Max profit | Total credit                                                      |
| Max loss   | Width - credit                                                    |
| Exit       | Manage at 50% loss                                                |

---

## 4. Option Chain Analysis

### 4.1 Strike Selection Engine

| Feature               | Description             |
| --------------------- | ----------------------- |
| ATM selection         | At-the-money default    |
| Delta-based selection | Select by target delta  |
| Risk-reward selection | Optimize R:R per strike |
| Support/Resistance    | Align with S/R levels   |

### 4.2 IV Analysis

| Feature              | Description                 |
| -------------------- | --------------------------- |
| IV Percentile        | IV rank (0-100%)            |
| IV vs HV             | IV vs historical volatility |
| IV Crush detection   | Earnings IV crush           |
| Sector IV comparison | Compare IV to sector        |

### 4.3 Greeks Tracking

| Feature          | Description                           |
| ---------------- | ------------------------------------- |
| Delta            | Option price change per $1 stock move |
| Gamma            | Delta change per $1                   |
| Theta            | Time decay per day                    |
| Vega             | IV sensitivity                        |
| Rho              | Interest rate sensitivity             |
| Portfolio Greeks | Combined position Greeks              |

### 4.4 Option Metrics

| Feature               | Description               |
| --------------------- | ------------------------- |
| PCR (Put-Call Ratio)  | OI-based and volume-based |
| Max Pain              | Strike with max pain      |
| Support/Resistance OI | OI concentration          |
| Volume analysis       | Unusual volume detection  |
| Open Interest change  | OI delta                  |

---

## 5. AI/ML Features

### 5.1 AI-First Decision Making

**Core Principle:** AI makes the FINAL decision on all options signals. Rules and technical indicators serve as INPUTS to the AI for analysis and decision-making.

| Component            | Role                                   |
| -------------------- | -------------------------------------- |
| Technical Indicators | Data inputs for AI analysis            |
| Option Chain Data    | Context for AI decision                |
| Greeks               | Risk parameters for AI                 |
| Market Structure     | Trend context for AI                   |
| AI Decision Engine   | FINAL CALL - decides whether to signal |

### 5.2 AI Decision Categories

| Decision        | Description                       | Output          |
| --------------- | --------------------------------- | --------------- |
| SCAN_TRIGGER    | Should we scan now?               | SCAN/WAIT       |
| STOCK_SELECTION | Which stock has best opportunity? | Stock symbol(s) |
| STRATEGY_PICK   | Which options strategy?           | Strategy type   |
| STRIKE_PICK     | Which strike price?               | Strike + Expiry |
| ENTRY_SIGNAL    | Is this a BUY signal?             | BUY/SELL/WAIT   |
| EXIT_SIGNAL     | Should we exit?                   | EXIT/HOLD       |
| RISK_ASSESSMENT | What's the risk?                  | Risk parameters |

### 5.3 AI Prompts - Market Analysis

#### 5.3.1 Market Structure Analysis Prompt

```
You are an Expert Options Trading Analyst analyzing Indian stock markets (NSE).

CONTEXT: You are analyzing the overall market structure to determine optimal options strategy.

MARKET DATA:
- NIFTY 50: {nifty_price} ({nifty_change_pct}% change)
- NIFTY trend: {nifty_trend} (UP/DOWN/SIDEWAYS)
- NIFTY RSI: {nifty_rsi}
- India VIX: {india_vix}
- Market regime: {market_regime}

SECTOR PERFORMANCE:
{sector_data}

RECENT MARKET HISTORY:
- Last 5 days NIFTY: {nifty_history}

YOUR TASK:
Analyze the market structure and provide:
1. Market direction assessment (BULLISH/BEARISH/SIDEWAYS/VOLATILE)
2. Confidence level (1-10)
3. Recommended strategy bias (CALLS/PUTS/NEUTRAL/SPREADS)
4. Key risks to consider
5. Market timing assessment

Respond in JSON format for parsing.
```

#### 5.3.2 Stock Selection Prompt

```
You are an Expert Options Trading Analyst selecting the best stock for options trading.

SCREENING CRITERIA (These are INPUTS - you analyze and decide):
- Stock universe: {universe_size} F&O stocks
- Technical signals: {technical_signals}
- Volume analysis: {volume_data}
- IV rankings: {iv_rankings}
- PCR data: {pcr_data}
- Recent momentum: {momentum_scores}

TOP CANDIDATES FROM SCREENING:
{candidates_list}

YOUR TASK:
Analyze all candidates and SELECT the best stock(s) for options opportunity.

Consider:
- Underlying stock momentum
- IV suitability for options
- Liquidity for option contracts
- Sector strength
- Recent news/events

Respond with:
1. RECOMMENDED_STOCK: Stock symbol
2. DIRECTION: BULLISH/BEARISH/NEUTRAL
3. CONFIDENCE: 1-10
4. REASONING: Your analysis (2-3 sentences)
5. STRATEGY_SUGGESTION: Initial strategy idea
```

#### 5.3.3 Strategy Selection Prompt

```
You are an Expert Options Trading Strategist selecting the optimal options strategy.

STOCK ANALYSIS:
- Symbol: {stock_symbol}
- Current price: {price}
- Trend: {trend} (EMA alignment)
- RSI: {rsi}
- ATR: {atr}
- Volume ratio: {volume_ratio}

OPTIONS DATA:
- IV: {iv}
- IV Percentile: {iv_percentile}
- IV vs HV: {iv_vs_hv}
- PCR: {pcr}
- Max Pain: {max_pain}
- Nearest strikes: {strikes}

MARKET CONTEXT:
- NIFTY: {nifty_price}
- Market regime: {regime}
- Days to earnings: {earnings_days}

AVAILABLE STRATEGIES:
1. LONG_CALL - Bullish, IV normal
2. LONG_PUT - Bearish, IV normal
3. CALL_CREDIT_SPREAD - Neutral/Bullish, IV elevated
4. PUT_CREDIT_SPREAD - Neutral/Bearish, IV elevated
5. STRADDLE - Volatility play, pre-earnings
6. IRON_CONDOR - Range-bound, high IV

YOUR TASK:
SELECT the optimal strategy based on ALL factors above.

Consider:
- IV and whether it's favorable for long/short strategies
- Stock direction vs market direction
- Time to expiration
- Risk-reward optimization

Respond in JSON:
{
    "strategy": "LONG_CALL",
    "direction": "BULLISH",
    "confidence": 8,
    "reasoning": "...",
    "ideal_conditions": {...}
}
```

#### 5.3.4 Strike & Expiration Selection Prompt

```
You are an Expert Options Trader selecting the optimal strike price and expiration.

STOCK: {symbol} @ {price}

OPTION CHAIN:
{strike_data}

YOUR ANALYSIS OF EACH STRIKE:
- Delta at each strike
- Probability of ITM/OTM
- Risk-reward at each strike
- Greeks at each strike

STRATEGY: {selected_strategy}
DIRECTION: {direction}
MARKET CONTEXT: {context}

YOUR TASK:
Select the BEST strike and expiration for this trade.

Consider:
- Delta target (e.g., 0.30-0.50 for directional trades)
- Risk-reward ratio optimization
- Probability of profit
- Greeks alignment with thesis
- Time decay impact

Respond in JSON:
{
    "strike": 2500,
    "expiry": "2026-05-01",
    "days_to_expiry": 21,
    "option_type": "CALL",
    "premium_estimate": 45.00,
    "delta": 0.45,
    "probability_of_profit": 0.65,
    "risk_reward": "1:2",
    "reasoning": "..."
}
```

#### 5.3.5 Entry Signal Generation Prompt

```
You are an Expert Options Trading Signal Generator. You make the FINAL DECISION on whether to generate a trading signal.

INPUT DATA:

Stock: {symbol} @ {price}
Strategy: {strategy}

TECHNICAL ANALYSIS:
- EMA20: {ema20}, EMA50: {ema50}, EMA100: {ema100}, EMA200: {ema200}
- RSI: {rsi}
- ATR: {atr}
- Volume: {volume} (ratio: {volume_ratio})
- Trend: {trend}

OPTIONS ANALYSIS:
- Selected Strike: {strike}
- Expiry: {expiry}
- Option Type: {option_type}
- Premium: {premium}
- IV: {iv}
- Delta: {delta}, Gamma: {gamma}, Theta: {theta}, Vega: {vega}

MARKET CONTEXT:
- NIFTY: {nifty}
- Sector: {sector}
- Market regime: {regime}

YOUR TASK:
Make the FINAL DECISION - should we send this signal?

Evaluate:
1. Is the stock momentum strong enough?
2. Is the strategy aligned with market direction?
3. Is the risk-reward favorable?
4. Are Greeks acceptable?
5. Is this the right time (not too early/late)?
6. Is IV favorable for this strategy?

Respond in JSON:
{
    "signal_decision": "SEND",
    "or_reason_to_wait": "...",
    "entry_price": 45.00,
    "stop_loss": 38.00,
    "stop_loss_pct": -15.5,
    "target_1": 60.00,
    "target_1_pct": 33.3,
    "target_2": 75.00,
    "target_2_pct": 66.7,
    "risk_reward": "1:2",
    "confidence": 8,
    "reasoning": "Your detailed reasoning (2-4 sentences)",
    "key_positive_factors": [...],
    "key_risks": [...]
}

IMPORTANT:
- If not confident, respond with "WAIT" and explain why
- Don't force a signal if conditions aren't optimal
- Better to miss an opportunity than take a bad trade
```

#### 5.3.6 Exit Decision Prompt

```
You are an Expert Options Trader deciding whether to exit an active position.

ACTIVE POSITION:
- Stock: {symbol}
- Entry price: {entry_price}
- Current price: {current_price}
- Entry date: {entry_date}
- Days since entry: {days_elapsed}

OPTION DETAILS:
- Strike: {strike}
- Expiry: {expiry}
- Days to expiry: {dte}
- Option type: {option_type}
- Current premium: {current_premium}

GREEKS NOW:
- Delta: {delta}
- Gamma: {gamma}
- Theta: {theta}
- Vega: {vega}

P&L:
- Current P&L: {pnl_pct}%
- Target 1 hit: {t1_hit}
- Target 2 hit: {t2_hit}
- Stop loss level: {sl_level}

MARKET NOW:
- NIFTY: {nifty}
- Stock trend: {stock_trend}
- IV change: {iv_change}

YOUR TASK:
Decide: EXIT_NOW / HOLD / ADJUST_STOP_LOSS

Consider:
- Is target reached?
- Is stop loss near?
- Has thesis changed?
- Time decay (theta) impact
- IV change impact
- Days to expiry

Respond in JSON:
{
    "decision": "HOLD",
    "reasoning": "...",
    "if_exit_target": ...,
    "if_adjust": ...
}
```

### 5.4 Multi-Provider LLM

| Feature            | Implementation          |
| ------------------ | ----------------------- |
| OpenAI GPT         | OpenAIProvider          |
| Anthropic Claude   | AnthropicProvider       |
| Google Gemini      | GoogleGeminiProvider    |
| Groq               | GroqProvider            |
| Automatic failover | MultiProviderAIAnalyzer |

### 5.5 AI Prompts - Implementation Requirements

All AI prompts must be stored in `config/prompts/` and follow these principles:

#### Prompt Design Principles

1. **Clear role definition** - AI knows its expertise level
2. **Input data clearly formatted** - Structured data for parsing
3. **Output format specified** - JSON for programmatic use
4. **Decision-first approach** - AI must make a decision, not just analyze
5. **Confidence scoring** - AI rates its confidence
6. **Reasoning required** - Explain WHY a decision was made

#### Required Prompt Files

| File                                  | Purpose               |
| ------------------------------------- | --------------------- |
| prompts/market_structure_prompt.txt   | Market analysis       |
| prompts/stock_selection_prompt.txt    | Stock picking         |
| prompts/strategy_selection_prompt.txt | Strategy picking      |
| prompts/strike_selection_prompt.txt   | Strike/expiry picking |
| prompts/entry_decision_prompt.txt     | Final signal decision |
| prompts/exit_decision_prompt.txt      | Exit decision         |
| prompts/risk_assessment_prompt.txt    | Risk evaluation       |

#### Prompt Variables (Dynamic)

All prompts receive these dynamic variables at runtime:

```python
prompt_variables = {
    # Market Data
    "nifty_price": float,
    "nifty_change_pct": float,
    "nifty_trend": str,
    "nifty_rsi": float,
    "india_vix": float,
    "market_regime": str,  # BULLISH/BEARISH/SIDEWAYS/VOLATILE

    # Sector Data
    "sector_performance": dict,
    "leading_sectors": list,
    "lagging_sectors": list,

    # Stock Data
    "stock_symbol": str,
    "price": float,
    "ema20": float,
    "ema50": float,
    "ema100": float,
    "ema200": float,
    "rsi": float,
    "atr": float,
    "volume": int,
    "volume_ratio": float,
    "trend": str,

    # Options Data
    "iv": float,
    "iv_percentile": float,
    "hv": float,
    "pcr": float,
    "max_pain": float,
    "strikes": list,
    "expirations": list,

    # Greeks
    "delta": float,
    "gamma": float,
    "theta": float,
    "vega": float,
    "rho": float,

    # Context
    "days_to_earnings": int,
    "earnings_date": str,
    "dividend_date": str
}
| Feature | Implementation |
|---------|----------------|
| OpenAI GPT | OpenAIProvider |
| Anthropic Claude | AnthropicProvider |
| Google Gemini | GoogleGeminiProvider |
| Groq | GroqProvider |
| Automatic failover | MultiProviderAIAnalyzer |

### 5.2 AI Option Analysis
| Feature | Description |
|---------|-------------|
| Stock analysis | AI picks best stock for options |
| Strategy selection | AI recommends strategy |
| Strike selection | AI optimizes strike |
| Expiration selection | AI recommends expiry |
| Entry/exit timing | AI timing signals |
| Risk assessment | AI evaluates risk |

### 5.3 Market Context
| Feature | Description |
|---------|-------------|
| NIFTY analysis | Market direction |
| Sector analysis | Sector rotation |
| Global cues | US/Asia markets |
| FII/DII activity | Institutional flows |

---

## 6. Agentic AI (v3.0) - AI as Decision Maker

### 6.1 Core Principle: AI is the Decision Maker
The Agentic AI system in this application is designed with a clear principle: **AI makes the final decision on all signals**. Technical indicators, rules, and market data serve as INPUTS for AI analysis, but the final call is made by the AI.

### 6.2 Agent Architecture

| Component | Role |
|-----------|------|
| Data Collection Layer | Fetch stock/options data |
| Analysis Layer | Calculate indicators, Greeks |
| Context Building | Aggregate market context |
| AI Decision Engine | FINAL DECISION MAKER |
| Execution Layer | Generate signal / Wait / Skip |

### 6.3 Agent Loop
```

1. Collect data (stock prices, option chain, Greeks, market data)
2. Analyze context (NIFTY, sectors, IV, PCR, regime)
3. AI decides ACTION:
   - SCAN: Look for new opportunities
   - PICK_STOCK: Select best stock from universe
   - PICK_STRATEGY: Choose strategy type
   - DECIDE_ENTRY: Make final call on signal
   - MONITOR: Watch active positions
   - EXIT: Close positions
4. Execute action
5. Track outcomes
6. AI self-corrects based on results
7. Log reasoning for transparency

```

### 6.4 Market Structure Analysis by AI

The AI considers the following market structure elements BEFORE making any decision:

| Factor | AI Analysis |
|--------|-------------|
| NIFTY direction | Bullish/Bearish/Sideways |
| Sector rotation | Which sectors leading/lagging |
| India VIX | Volatility regime |
| FII/DII activity | Institutional flow |
| Global cues | US/Asia market impact |
| Market breadth | Advance/Decline ratio |
| Support/Resistance | Key levels |

### 6.5 Agent Decisions (AI as Decision Maker)

| Decision | Trigger | AI Considers |
|----------|---------|--------------|
| SCAN | Scheduled/signal | Market conditions favorable? |
| PICK_STOCK | After scan | Which stock has best setup |
| PICK_STRATEGY | Stock selected | Strategy aligned with market |
| DECIDE_ENTRY | Strategy selected | Final go/no-go decision |
| EXIT | Active position | Exit criteria met? |
| WAIT | Any check | Conditions not optimal |

### 6.6 Self-Correction

The AI Agent learns from trade outcomes and adjusts:

| Outcome | AI Action |
|---------|-----------|
| 3+ consecutive losses | Increase strictness, require higher confidence |
| 5+ consecutive wins | Maintain current approach |
| Market regime change | Adjust strategy selection |
| IV crush detected | Avoid earnings plays temporarily |

---

## 7. Scanning Engine - AI as Decision Maker

### 7.1 AI-First Scan Flow

**CRITICAL:** No signal is sent without AI decision-making. The scanning engine feeds data to AI at each stage.

| Step | Process | AI Decision |
|------|---------|-------------|
| 1 | Collect market data | - |
| 2 | Analyze market structure | Should we scan now? |
| 3 | Screen stocks | Which stock to analyze? |
| 4 | Analyze options chain | What strategy? |
| 5 | Calculate Greeks | Which strike? |
| 6 | **AI MAKES FINAL DECISION** | Send signal or WAIT |

### 7.2 Scan Types
| Scan | Description | Frequency | AI Decision Point |
|------|-------------|------------|-------------------|
| Momentum Scan | Find bullish/bearish stocks | Every 15 min | Stock Selection |
| IV Scan | Find high IV opportunities | Daily | Strategy Selection |
| Earnings Scan | Pre-earnings setups | Daily | Strike Selection |
| Sector Scan | Sector rotation opportunities | Every 30 min | Entry Decision |

### 7.3 Signal Generation - AI Decision Gates

**Every signal MUST pass through AI decision gates:**

| Gate | AI Question | Decision |
|------|-------------|----------|
| Gate 1 | Should we scan now? | SCAN / WAIT |
| Gate 2 | Which stock? | Stock symbol |
| Gate 3 | Which strategy? | Strategy type |
| Gate 4 | Which strike/expiry? | Strike + Expiry |
| Gate 5 | **FINAL CALL** - Send signal? | SEND / WAIT |

**Signal is ONLY sent when Gate 5 returns SEND with confidence >= min_confidence_to_signal**

### 7.4 Signal Generation
| Feature | Description |
|---------|-------------|
| Stock signal | Underlying stock opportunity |
| Strategy signal | Recommended strategy |
| Strike selection | Recommended strikes |
| Expiration | Recommended expiry |
| Entry zone | Entry price range |
| Target | Profit target |
| Stop loss | Loss limit |
| Risk-Reward | Calculated R:R |

---

## 8. Learning & Feedback System

### 8.1 Signal Tracking
| Feature | Description |
|---------|-------------|
| Active signal tracking | Monitor until completion |
| Outcome detection | Target/SL/Expiry detection |
| Signal expiry | 30-day default |
| Historical persistence | All signals saved |

### 8.2 Performance Metrics
| Metric | Calculation |
|--------|-------------|
| Options SIQ | Success rate on options |
| Win rate | % hitting targets |
| Avg return | Average return % |
| Avg holding time | Days to resolution |
| Profit factor | Gross profit/loss |

### 8.3 Auto-Optimization

**IMPORTANT:** Auto-optimization is AI-guided. The AI analyzes performance and recommends parameter changes.

| Trigger | AI Action |
|---------|-----------|
| Win rate < 40% | AI recommends strategy adjustment |
| Win rate > 60% | AI recommends increasing position size |
| High IV crush losses | AI avoids earnings plays |
| theta_decay too high | AI reduces hold time |

### 8.4 AI Reasoning Log

Every AI decision must be logged with full reasoning:

| Field | Description |
|-------|-------------|
| decision_id | Unique ID |
| timestamp | When decision was made |
| decision_type | SCAN/PICK_STOCK/STRATEGY/ENTRY/EXIT |
| input_data | All data given to AI |
| ai_response | Full AI response |
| final_decision | What AI decided |
| confidence | AI confidence score |
| reasoning | AI's reasoning in plain English |
| outcome | What happened (for learning) |

### 8.4 Trade Journal
| Field | Description |
|-------|-------------|
| trade_id | Unique identifier |
| symbol | Stock symbol |
| strategy | Strategy type |
| entry_date | Entry timestamp |
| entry_price | Stock/option entry |
| expiry_date | Option expiration |
| strike | Strike price |
| option_type | Call/Put |
| contracts | Number of contracts |
| premium | Premium paid/received |
| stop_loss | SL level |
| targets | T1, T2 levels |
| outcome | WIN/LOSS/TIMEOUT |
| return_pct | Return percentage |
| greeks_entry | Initial Greeks |
| greeks_exit | Exit Greeks |

---

## 9. Alert & Notifications

### 9.1 Signal Alerts
| Alert | Content |
|-------|---------|
| New Signal | Stock, Strategy, Entry, SL, Targets, R:R |
| IV Alert | High IV detection |
| Earnings Alert | Pre-earnings setup |

### 9.2 Outcome Alerts
| Alert | Content |
|-------|---------|
| Target Hit | T1/T2 hit notification |
| Stop Loss Hit | SL hit notification |
| Expiry Warning | 3 days to expiration |
| Expiration | Option expired |

### 9.3 Reports
| Report | Frequency |
|--------|------------|
| Daily Summary | End of day |
| Weekly Report | Weekly |
| Monthly Report | Monthly |
| Performance Report | On-demand |

---

## 10. Interactive Telegram Bot

### 10.1 Commands
| Command | Description |
|---------|-------------|
| `RELIANCE` | Stock analysis |
| `/analyze RELIANCE` | Full AI analysis |
| `/options RELIANCE` | Options chain analysis |
| `/strategies RELIANCE` | Available strategies |
| `/greeks RELIANCE` | Current Greeks |
| `/iv RELIANCE` | IV analysis |
| `/status` | Scanner status |
| `/performance` | Performance metrics |
| `/help` | Help message |

### 10.2 Interactive Features
| Feature | Description |
|---------|-------------|
| Strategy builder | Build custom strategies |
| Position sizing | Calculate position size |
| Risk calculator | Calculate risk |
| Greeks calculator | What-if scenarios |

---

## 11. Risk Management

### 11.1 Position Rules
| Rule | Value |
|------|-------|
| Max risk per trade | 2% of capital |
| Max concurrent positions | 5 |
| Max sector exposure | 25% |
| Daily loss limit | 5% |

### 11.2 Greeks Limits
| Limit | Value |
|-------|-------|
| Max Delta | 50 |
| Max Gamma | 20 |
| Max Theta | 50 (negative) |
| Max Vega | 30 |

### 11.3 Exit Rules
| Rule | Trigger |
|------|---------|
| Stop Loss | 50% of max loss |
| Take Profit T1 | 50% of target |
| Take Profit T2 | Full target |
| Time Exit | 3 days to expiry |
| IV Crush Exit | >50% IV drop |

---

## 12. Configuration

### 12.1 Environment Variables
```

# AI Providers

OPENAI_API_KEY
ANTHROPIC_API_KEY
GOOGLE_API_KEY
GROQ_API_KEY

# Telegram

TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID

# Trading Capital

TRADING_CAPITAL
MAX_POSITION_SIZE

````

### 12.2 Config Files
| File | Purpose |
|------|---------|
| config/stocks.json | Stock list |
| config/settings.json | Scanner settings |
| config/options_strategies.json | Strategy configs |
| data/signals_active.json | Active signals |
| data/signals_history.json | Signal history |
| data/performance.json | Performance metrics |

### 12.3 Settings Schema
```json
{
    "scanner": {
        "timeframe": "1D",
        "scan_interval_minutes": 15,
        "max_signals_per_strategy": 2,
        "min_iv_for_options": 15,
        "max_iv_for_options": 60
    },
    "ai_decision": {
        "enabled": true,
        "min_confidence_to_signal": 7,
        "require_ai_approval": true,
        "allow_manual_override": true,
        "auto_reject_low_confidence": true,
        "ai_decision_timeout_seconds": 30
    },
    "options": {
        "default_expiry_days": 21,
        "strike_width_pct": 2.5,
        "min_days_to_expiry": 7,
        "max_days_to_expiry": 45
    },
    "strategies": {
        "long_call": { "enabled": true, "min_rr": 2.0 },
        "long_put": { "enabled": true, "min_rr": 2.0 },
        "credit_spread": { "enabled": true, "min_rr": 1.5 },
        "straddle": { "enabled": true, "min_iv": 30 },
        "iron_condor": { "enabled": true, "min_iv": 25 }
    },
    "filters": {
        "min_volume": 500000,
        "min_option_volume": 100,
        "max_spread_pct": 10,
        "min_open_interest": 50000
    },
    "risk": {
        "max_position_pct": 2,
        "max_positions": 5,
        "stop_loss_pct": 50
    }
}
```

### 12.4 AI Decision Configuration

| Setting | Description | Default |
|---------|-------------|---------|
| `ai_decision.enabled` | Enable AI to make decisions | true |
| `ai_decision.min_confidence_to_signal` | Minimum confidence (1-10) | 7 |
| `ai_decision.require_ai_approval` | Require AI approval for all signals | true |
| `ai_decision.allow_manual_override` | Allow manual override | true |
| `ai_decision.auto_reject_low_confidence` | Auto-reject signals below threshold | true |
| `ai_decision.ai_decision_timeout_seconds` | Timeout for AI decision | 30 |`

---

## 13. Signal Output Format

### 13.1 Signal Object

```json
{
  "signal_id": "UUID",
  "timestamp": "2026-04-14T10:30:00",
  "stock_symbol": "RELIANCE",
  "underlying_price": 2450.0,

  "strategy": {
    "type": "LONG_CALL",
    "name": "Long Call (Bullish)",
    "direction": "BULLISH"
  },

  "option_chain": {
    "strike": 2500,
    "expiry_date": "2026-05-01",
    "days_to_expiry": 21,
    "option_type": "CALL",
    "premium": 45.0,
    "bid": 43.5,
    "ask": 46.5,
    "spread": 2.5,
    "volume": 1250,
    "open_interest": 25000
  },

  "greeks": {
    "delta": 0.45,
    "gamma": 0.025,
    "theta": -2.5,
    "vega": 0.12,
    "rho": 0.05
  },

  "iv_analysis": {
    "iv": 28.5,
    "iv_percentile": 45,
    "hv": 22.0,
    "iv_vs_hv": 1.3
  },

  "indicators": {
    "ema20": 2445.0,
    "ema50": 2430.0,
    "ema100": 2410.0,
    "ema200": 2390.0,
    "rsi": 58.5,
    "atr": 25.0,
    "volume_ratio": 1.28
  },

  "entry_zone": {
    "buy_above": 2455.0,
    "option_entry": 45.0
  },

  "risk_management": {
    "stop_loss": 38.0,
    "stop_loss_pct": -15.5,
    "target_1": 60.0,
    "target_1_pct": 33.3,
    "target_2": 75.0,
    "target_2_pct": 66.7,
    "risk_reward_1": "1:1.5",
    "risk_reward_2": "1:3"
  },

  "position_sizing": {
    "max_contracts": 10,
    "max_investment": 5000,
    "capital_remaining_pct": 80
  },

  "ai_analysis": {
    "recommendation": "BUY",
    "confidence": 8,
    "reasoning": "Strong bullish momentum with EMA alignment...",
    "risk_reward_ratio": "1:2"
  },

  "tracking": {
    "status": "ACTIVE",
    "entry_price": 45.0,
    "entry_date": "2026-04-14",
    "expiry_date": "2026-05-01"
  }
}
```

---

## 14. File Structure

```
ai-options-trade-scanner/
├── config/
│   ├── settings.json          # All configuration
│   ├── stocks.json            # Stock list
│   ├── options_strategies.json # Strategy configs
│   └── prompts/               # AI prompts directory
│       ├── market_structure_prompt.txt
│       ├── stock_selection_prompt.txt
│       ├── strategy_selection_prompt.txt
│       ├── strike_selection_prompt.txt
│       ├── entry_decision_prompt.txt
│       ├── exit_decision_prompt.txt
│       └── risk_assessment_prompt.txt
├── data/
│   ├── signals_active.json   # Active signals
│   ├── signals_history.json   # Completed signals
│   ├── performance_metrics.json # SIQ and metrics
│   └── greeks_history.json   # Greeks tracking
├── src/
│   ├── __init__.py
│   ├── main.py               # Entry point
│   ├── data_fetcher.py       # Stock + Options data
│   ├── indicator_engine.py   # Technical indicators
│   ├── options_chain.py      # Option chain analysis
│   ├── greeks_calculator.py # Greeks calculations
│   ├── strategies/
│   │   ├── __init__.py
│   │   ├── long_call.py     # Long Call
│   │   ├── long_put.py     # Long Put
│   │   ├── credit_spread.py  # Credit Spreads
│   │   ├── straddle.py     # Straddles
│   │   └── iron_condor.py   # Iron Condors
│   ├── scanner.py           # Options scanner
│   ├── signal_generator.py # Signal generation
│   ├── reasoning_engine.py # Combined scoring
│   ├── ai_stock_analyzer.py # Multi-provider AI
│   ├── agent_controller.py  # Agentic AI
│   ├── alert_service.py   # Telegram alerts
│   ├── signal_tracker.py  # Signal tracking
│   ├── history_manager.py # History persistence
│   ├── performance_tracker.py # Performance metrics
│   ├── notification_manager.py # Notifications
│   ├── scheduler/
│   │   ├── __init__.py
│   │   └── scanner_scheduler.py
│   └── trade_journal.py   # Trade journal
├── docs/
│   ├── PRD.md
│   └── (this file)
├── requirements.txt
└── README.md
```

---

## 15. Feature Checklist

| #   | Feature                          | Status         |
| --- | -------------------------------- | -------------- |
| 1   | Stock universe (500+ F&O stocks) | ✅ From parent |
| 2   | Real-time data (yfinance)        | ✅ From parent |
| 3   | Option chain data                | ✅ New         |
| 4   | Strike selection engine          | ✅ New         |
| 5   | Greeks tracking                  | ✅ New         |
| 6   | IV analysis                      | ✅ New         |
| 7   | PCR analysis                     | ✅ New         |
| 8   | Max Pain calculation             | ✅ New         |
| 9   | Long Call strategy               | ✅ New         |
| 10  | Long Put strategy                | ✅ New         |
| 11  | Credit Spread strategy           | ✅ New         |
| 12  | Straddle strategy                | ✅ New         |
| 13  | Iron Condor strategy             | ✅ New         |
| 14  | Multi-provider AI                | ✅ From parent |
| 15  | Provider failover                | ✅ From parent |
| 16  | Telegram alerts                  | ✅ From parent |
| 17  | Interactive Telegram bot         | ✅ Enhanced    |
| 18  | Signal tracking                  | ✅ From parent |
| 19  | Options SIQ                      | ✅ New         |
| 20  | Performance metrics              | ✅ Enhanced    |
| 21  | Outcome notifications            | ✅ From parent |
| 22  | Weighted scoring                 | ✅ From parent |
| 23  | Agentic AI                       | ✅ Enhanced    |
| 24  | Scheduled scanning               | ✅ From parent |
| 25  | Market hours filtering           | ✅ From parent |
| 26  | Auto-optimization                | ✅ From parent |
| 27  | Trade journal                    | ✅ From parent |
| 28  | Position sizing                  | ✅ New         |
| 29  | Risk limits                      | ✅ New         |
| 30  | Greeks alerts                    | ✅ New         |

---

## 16. Implementation Phases

### Phase 1: Foundation (Week 1-2)

1. Setup project structure
2. Implement option chain fetcher
3. Implement Greeks calculator
4. Implement IV analysis
5. Basic scanning engine

### Phase 2: Strategies (Week 3-4)

1. Implement Long Call
2. Implement Long Put
3. Implement Credit Spreads
4. Implement Straddles
5. Implement Iron Condors

### Phase 3: Intelligence (Week 5-6)

1. Enhance AI analyzer for options
2. Implement strike selection AI
3. Enhance Agentic AI
4. Implement strategy selection AI

### Phase 4: Tracking (Week 7-8)

1. Enhance signal tracking
2. Implement Greeks tracking
3. Implement Options SIQ
4. Performance analytics

### Phase 5: Polish (Week 9-10)

1. Telegram bot enhancements
2. Reports and dashboards
3. Testing
4. Documentation

---

## 17. Dependencies

```
yfinance>=0.2.36
pandas>=2.0.0
ta>=0.11.0
numpy>=1.24.0
scipy>=1.11.0
schedule>=1.2.0
APScheduler>=3.10.0
requests>=2.31.0
python-telegram-bot>=20.0
python-dotenv>=1.0.0
pytz>=2023.3
openai>=1.0.0
anthropic>=0.25.0
google-genai>=0.1.0
groq>=0.4.0
```

---

## 18. Terminology

| Term     | Definition                                |
| -------- | ----------------------------------------- |
| ATM      | At-The-Money (strike = underlying price)  |
| OTM      | Out-Of-The-Money (strike away from price) |
| ITM      | In-The-Money (strike favorable)           |
| IV       | Implied Volatility                        |
| HV       | Historical Volatility                     |
| PCR      | Put-Call Ratio                            |
| Greeks   | Delta, Gamma, Theta, Vega, Rho            |
| Max Pain | Strike with most OI causing loss          |
| OI       | Open Interest                             |
| Premium  | Option price                              |
| Strike   | Option exercise price                     |
| Expiry   | Option expiration date                    |

---

**Document Version:** 1.0  
**Last Updated:** 2026-04-14  
**Based On:** NSE Options Scanner Agent v3.0
