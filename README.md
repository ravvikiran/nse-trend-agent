# QuantGridIndia — NSE Momentum Scanner

Deterministic, rule-based momentum scanner for ~500 NSE stocks. Scans every 2 minutes during market hours using a three-stage filtering pipeline and delivers structured Telegram alerts for the top 5 momentum stocks.

**Data Provider:** Yahoo Finance (free, no API key required)  
**Deployment:** Railway (worker process)  
**Alerts:** Telegram

## How It Works

```
500 stocks → 1H Trend Filter → RS Ranking → 15m Entry Triggers → Top 5 Alerts
```

### Pipeline Stages

1. **Stage 1 — Trend Filter (1H):** Filters for bullish EMA alignment (price > EMA200, EMA20 > EMA50, positive slope)
2. **Stage 2 — Relative Strength:** Ranks survivors by performance vs NIFTY (intraday 50% + 1-day 30% + 5-day 20%)
3. **Stage 3 — Entry Triggers (15m):** Detects Pullback Continuation or Compression Breakout patterns
4. **Final Ranking:** Weighted scoring → selects top 5 stocks
5. **Alerts:** Sends structured Telegram messages with entry, SL, targets, and scores

### Setup Types

| Type | Pattern |
|------|---------|
| 🟢 Pullback Continuation | Price near EMA(20) + bullish candle + volume > 1.5x + breaks prev high |
| 🔵 Compression Breakout | 3-6 tight candles + ATR contraction + volume expansion + strong breakout |

### Market Safety

- **Market Breadth Filter:** Suppresses all signals when declining > advancing by 1.5x AND NIFTY < EMA(20)
- **Deduplication:** 30-min cooldown per stock, max 20 alerts/day
- **NSE Holiday Calendar:** No scans on weekends or market holidays

## Quick Start

```bash
# Clone and install
git clone https://github.com/YOUR_USERNAME/QuantGridIndia.git
cd QuantGridIndia
pip install -r requirements.txt

# Run with mock data (no broker needed)
python -m src.momentum.main --mock

# Run with Yahoo Finance (production)
python -m src.momentum.main
```

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```env
# Telegram Alerts
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### Getting Your Credentials

**Yahoo Finance:**
No API key or credentials required. The scanner uses Yahoo Finance's public API.

**Telegram:**
1. Message [@BotFather](https://t.me/BotFather) → `/newbot` → copy the token
2. Message your bot, then visit `https://api.telegram.org/bot<TOKEN>/getUpdates` to get your chat ID

### Scanner Configuration

Edit `config/momentum_scanner.json`:

```json
{
    "scan_interval_seconds": 120,
    "ema_fast": 20,
    "ema_medium": 50,
    "ema_slow": 200,
    "volume_expansion_threshold": 1.5,
    "max_alerts_per_day": 20,
    "cooldown_period_seconds": 1800,
    "min_breakout_strength": 40.0,
    "batch_size": 50
}
```

## Railway Deployment

1. Connect your GitHub repo to Railway
2. Set environment variables in Railway dashboard → Variables:

| Variable | Description |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Telegram bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | Your Telegram chat ID |

3. Deploy — the scanner auto-starts as a worker process

## Project Structure

```
QuantGridIndia/
├── config/
│   ├── momentum_scanner.json      # Scanner configuration
│   └── nifty500_universe.json     # NIFTY 500 stock universe
├── data/                          # SQLite scan logs (auto-created)
├── src/
│   └── momentum/
│       ├── main.py                # Entry point (CLI)
│       ├── scanner.py             # Pipeline orchestrator
│       ├── models.py              # Data models & config
│       ├── config_manager.py      # Configuration loader
│       ├── data_provider.py       # Abstract broker interface
│       ├── telegram_service.py    # Telegram message delivery
│       ├── stage1_trend_filter.py # 1H EMA trend filter
│       ├── stage2_relative_strength.py  # RS ranking vs NIFTY
│       ├── stage3_entry_trigger.py      # 15m entry detection
│       ├── final_ranker.py        # Weighted scoring & top-5
│       ├── trade_levels.py        # Entry, SL, targets
│       ├── deduplicator.py        # Alert throttling
│       ├── alert_formatter.py     # Telegram message formatting
│       ├── market_breadth_filter.py     # Market health check
│       ├── sector_analyzer.py     # Sector performance
│       ├── scan_scheduler.py      # Market hours scheduling
│       ├── scan_logger.py         # SQLite persistence
│       ├── universe_manager.py    # Stock universe management
│       └── providers/
│           └── mock_provider.py   # Mock data for testing
├── tests/momentum/                # Unit tests
├── logs/                          # Log files (auto-created)
├── .env.example                   # Environment variable template
├── .env.railway                   # Railway deployment template
├── Procfile                       # Railway process definition
├── requirements.txt               # Python dependencies
└── README.md
```

## CLI Options

```
python -m src.momentum.main [OPTIONS]

Options:
  --mock        Use mock data (no broker API needed)
  --config PATH Path to config JSON (default: config/momentum_scanner.json)
  --log-level   Console log level: DEBUG, INFO, WARNING, ERROR (default: INFO)
  --log-file    Log file path (default: logs/momentum_scanner.log)
```

## Alert Format

```
🟢 MOMENTUM SIGNAL

Symbol: RELIANCE
Setup: Pullback Continuation
Timeframe: 15m

🎯 Trade Levels
  Entry: ₹2,500.00
  Stop Loss: ₹2,450.00
  ⚠️ Risk: 2.00%
  Target 1: ₹2,550.00
  Target 2: ₹2,600.00

📊 Scores
  Relative Volume: 2.1x
  Relative Strength: 3.50
  Sector Strength: 5.00
  Trend Score: 75.0/100
  Rank Score: 82.5/100

⏰ 2024-01-15 10:30 IST
```

## Disclaimer

This software is for educational purposes only. Trading in financial markets involves substantial risk. Always do your own research and never risk more than you can afford to lose.
