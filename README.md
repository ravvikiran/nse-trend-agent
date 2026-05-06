# NSE Trend Scanner Agent (Agentic AI v3.0)

Automated trading scanner that monitors ~500 NSE stocks during market hours and detects potential uptrend starts based on EMA alignment and volume confirmation. **Agentic AI v3.0** - the scanner is now a fully autonomous agent that makes its own decisions.

**Version:** 3.0  
**Latest Update:** 2026-04-14 - Agentic AI with autonomous decision-making

## Features

### Core Scanning

- **Stock Universe**: Monitors 500+ NSE stocks (NIFTY 50, NEXT 50, MIDCAP 150, SMALLCAP 250)
- **Real-time Data**: Uses Yahoo Finance for 1-day (1D) OHLCV data
- **Technical Indicators**: EMA 20, 50, 100, 200 + Volume MA 30 + RSI + ATR
- **Trend Detection**: Identifies EMA alignment (EMA20 > EMA50 > EMA100 > EMA200) with volume confirmation
- **VERC Strategy**: Volume Expansion Range Compression - detects accumulation before breakout
- **MTF Strategy**: Multi-timeframe confirmation (1D, 1H, 15m) for stronger signals

### Smart Features

- **Smart Alerts**: Telegram notifications with entry, stop loss, targets, and confidence score
- **Scheduled Scanning**: Runs every 15 minutes during market hours (09:15 - 15:30 IST)
- **AI Analysis**: Multi-provider LLM (OpenAI, Anthropic, Groq, Gemini) stock analysis
- **Two-way Telegram Bot**: Interactive bot - send stock symbols for instant analysis

### Learning & Optimization (v2.0)

- **Trade Journal**: Logs EVERY alert with complete trade data (entry, SL, targets, outcome, RR, indicators)
- **Strategy Performance Tracker**: Tracks win rate, avg RR, drawdown, holding time per strategy
- **Auto-Optimization Engine**: Automatically adjusts strategy weights based on performance
- **Adaptive Filters**: Dynamically adjusts volume_ratio and RSI thresholds
- **No-Trade Filter**: Avoids signals when ATR too low, choppy candles, or NIFTY unclear
- **AI Learning Layer** (Strict Mode): Analyzes journal, detects failure patterns, suggests improvements

### Additional Features (v2.1)

- **Performance Analyzer**: Setup-level analysis with win rate, returns, profit factor
- **Position Manager**: Trailing SL, partial exits at T1/T2
- **Market Context**: ATR-based detection with volatility regimes (LOW/NORMAL/HIGH)
- **Weekend Skip**: No signal generation on weekends

### Agentic AI (v3.0) - Autonomous Agent

The scanner is now a **Fully Autonomous Agent** powered by LLM that:

- **Makes Decisions**: Uses LLM to analyze market conditions and decide whether to SCAN, WAIT, or ADJUST_STRATEGY
- **Self-corrects**: Tracks win/loss streaks and automatically adjusts approach
- **Explains Decisions**: Provides natural language reasoning for every action
- **Adapts to Regime**: Classifies market as BULLISH/BEARISH/SIDEWAYS/VOLATILE and adjusts behavior
- **Dynamic Scanning**: Can adjust scan intervals based on market conditions

```
Agent Loop (v3.0):
1. Fetch market data (NIFTY, sectors, active trades)
2. Analyze with LLM - decide action (SCAN/WAIT/ADJUST)
3. Execute action or skip scan
4. Track outcomes for self-correction
5. Update agent state and provide explanation
```

**Agent Actions:**
- `SCAN`: Execute normal signal scan
- `WAIT`: Skip this scan cycle (market conditions unfavorable)
- `ADJUST_STRATEGY`: Change strategy focus (e.g., more VERC in sideways)
- `MONITOR`: Focus on existing positions instead of new signals
- `ANALYZE`: Deep dive analysis on specific stocks

**Market Regime Detection:**
- BULLISH: Strong uptrend - maximize TREND signals
- BEARISH: Strong downtrend - minimize signals, favor shorts
- SIDEWAYS: Range-bound - favor VERC/MTF over TREND
- VOLATILE: High volatility - reduce confidence, tighten SL

## System Flow

```
Scan → Detect → Score → Rank → Select → Alert → Log → Track → Optimize
```

### Rank Score Formula (v2.1 - PURE Scoring)

```
rank_score = (strategy_score * 0.6) + (volume_score * 0.2) + (breakout_strength * 0.2)
```

**Note:** Score is PURE - strategy_weight only affects sorting/ranking, not the numeric score.

## Installation

```bash
git clone <repository-url>
cd nse-trend-agent

python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

pip install -r requirements.txt
```

## Configuration

### 1. Agentic AI Setup (Optional)

To enable full Agentic AI capabilities, set any LLM API key:

```bash
# Choose one (or multiple for fallback)
export OPENAI_API_KEY=your_key          # GPT-4 (Recommended)
export GROQ_API_KEY=your_key            # Fast, free tier available
export ANTHROPIC_API_KEY=your_key       # Claude
export GOOGLE_API_KEY=your_key         # Gemini
```

Without LLM, the agent falls back to rule-based decisions.

### 2. Telegram Setup

**Option A: Config File (Recommended)**
Edit `config/settings.json`:

```json
{
  "telegram": {
    "bot_token": "YOUR_BOT_TOKEN_HERE",
    "chat_id": "YOUR_CHAT_ID_HERE"
  }
}
```

**Option B: Environment Variables**

```bash
# On Windows
set TELEGRAM_BOT_TOKEN=your_bot_token
set TELEGRAM_CHAT_ID=your_chat_id
```

### 3. Stock List

The stock list is configured in [`config/stocks.json`](config/stocks.json).

### 4. AI Configuration (Optional)

To enable AI-powered stock analysis, set `OPENAI_API_KEY` environment variable.

## Usage

### Start Scanner (Runs every 15 minutes during market hours)

```bash
python -m src.main
python -m src.main --test              # Single scan test
python -m src.main --test-telegram     # Test Telegram connection
python -m src.main --mock-alerts       # Test with mock alerts
```

### Run Specific Strategy

```bash
python -m src.main --strategy trend   # Only Trend Detection
python -m src.main --strategy verc    # Only VERC
python -m src.main --strategy all     # All strategies (default)
```

### Enable Telegram Bot

```bash
python -m src.main --enable-telegram-bot
```

### Telegram Bot Commands

| Command             | Description                               |
| ------------------- | ----------------------------------------- |
| `RELIANCE`          | Send stock symbol for instant AI analysis |
| `/analyze RELIANCE` | AI-powered stock analysis                 |
| `/trend HDFCBANK`   | Technical trend analysis                  |
| `/status`           | Check scanner status                      |

## Project Structure

```
nse-trend-agent/
├── config/
│   ├── settings.json         # Telegram and scanner settings
│   └── stocks.json          # Stock list configuration
├── data/                    # Data storage (trade journal, history)
├── src/
│   ├── __init__.py
│   ├── main.py              # Main entry point
│   ├── agent_controller.py # Agentic AI - autonomous decision maker (v3.0)
│   ├── data_fetcher.py      # Yahoo Finance data fetching
│   ├── indicator_engine.py  # EMA, RSI, ATR calculations
│   ├── trend_detector.py    # Trend detection logic
│   ├── volume_compression.py # VERC strategy
│   ├── mtf_strategy.py      # Multi-timeframe strategy
│   ├── alert_service.py    # Telegram alerts
│   ├── scheduler.py        # Market hours scheduling
│   ├── trade_journal.py    # Trade logging system
│   ├── strategy_optimizer.py # Performance tracker + auto-opt
│   └── ai_learning_layer.py # AI analysis (strict mode)
├── logs/                    # Log files
├── requirements.txt
└── README.md
```

## Trade Journal Data Model

```python
trade = {
  trade_id,
  symbol,
  strategy,            # TREND / VERC / MTF
  entry,
  stop_loss,
  targets,
  timestamp,
  outcome,             # WIN / LOSS / OPEN / TIMEOUT
  rr_achieved,
  max_drawdown,
  volume_ratio,
  rsi,
  trend_score,
  verc_score,
  rank_score
}
```

## Auto-Optimization Rules

- **Win rate < 40%**: Reduce strategy_weight
- **Win rate > 60%**: Increase strategy_weight

## Adaptive Filters

- **Too many false breakouts**: Increase volume_ratio (1.5 → 1.8)
- **Late entries**: Tighten RSI (70 → 65)
- **Dead stock**: Increase ATR minimum

## No-Trade Conditions

Avoid signals when:

- ATR very low (dead stock)
- Choppy candles (wick > body)
- NIFTY unclear direction (SIDEWAYS)

## AI Learning Layer (Strict Mode)

AI does NOT control signals. AI role:

- Analyze journal data
- Detect failure patterns
- Suggest parameter improvements

Example output:

```
Insight:
- TREND failing in low volume stocks
- Suggest increasing volume threshold
```

## Performance

- **Scanning 500 stocks**: 10-30 seconds per scan
- **Scan Interval**: Every 15 minutes during market hours
- **Trade expiry**: 30 days

## Disclaimer

This software is for educational purposes only. Trading in financial markets involves substantial risk. Always do your own research.
