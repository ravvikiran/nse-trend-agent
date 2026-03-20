# NSE Trend Scanner Agent

Automated trading scanner that monitors ~500 NSE stocks during market hours and detects potential uptrend starts based on EMA alignment and volume confirmation.

## Features

- **Stock Universe**: Monitors 500+ NSE stocks (NIFTY 50, NEXT 50, MIDCAP 150, SMALLCAP 250)
- **Real-time Data**: Uses Yahoo Finance for 15-minute OHLCV data
- **Technical Indicators**: EMA 20, 50, 100, 200 + Volume MA 30
- **Trend Detection**: Identifies EMA alignment (EMA20 > EMA50 > EMA100 > EMA200) with volume confirmation
- **VERC Strategy**: Volume Expansion Range Compression - detects accumulation before breakout
- **Smart Alerts**: Telegram notifications with entry, stop loss, targets, and confidence score
- **Scheduled Scanning**: Runs every 15 minutes during market hours (09:15 - 15:30 IST)

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd nse-trend-agent

# Create virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Configuration

### 1. Telegram Setup

To receive alerts via Telegram, you have two options:

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

# On Linux/Mac
export TELEGRAM_BOT_TOKEN=your_bot_token
export TELEGRAM_CHAT_ID=your_chat_id
```

Or pass them as command-line arguments (see Usage below).

### 2. Stock List

The stock list is configured in [`config/stocks.json`](config/stocks.json). You can modify this file to add/remove stocks. Format:

```json
["RELIANCE.NS", "HDFCBANK.NS", "TCS.NS"]
```

## Usage

### Start Scanner (Runs every 15 minutes during market hours)

```bash
# Start the scanner with all strategies
python -m src.main

# Test run (single scan)
python -m src.main --test
```

### Run Specific Strategy Separately

You can run each strategy independently:

```bash
# Run ONLY Trend Detection strategy
python -m src.main --strategy trend

# Run ONLY VERC (Volume Expansion Range Compression) strategy
python -m src.main --strategy verc

# Run both strategies (default)
python -m src.main --strategy all
```

#### Examples:

```bash
# Test run with only VERC strategy
python -m src.main --test --strategy verc

# Test run with only Trend strategy
python -m src.main --test --strategy trend

# Start scanner with only VERC running in background
python -m src.main --strategy verc
```

### Example Alert Message

**Trend Signal:**

```
📈 TREND SIGNAL

Stock: HDFCBANK
Time: 2024-01-15 14:45

💰 Price: ₹1680.50

🎯 Entry Zone:
  Buy Above: ₹1685.20

🛡️ Stop Loss:
  SL: ₹1648.90 (-1.9%)

🎯 Targets:
  Target 1: ₹1713.10 (+1.9%)
  Target 2: ₹1745.70 (+3.9%)

Confidence: 8/10

📊 Indicators:
  EMA 20: ₹1685.20
  EMA 50: ₹1675.30
  Volume: 1,250,000
  Vol Ratio: 1.28x
```

**VERC Signal:**

```
📊 VERC SIGNAL (Accumulation)

Stock: RELIANCE

💰 Current Price: ₹2450.00

🔄 Compression Range:
  Range: ₹2430.00 - ₹2460.00
  Range Width: ₹30.00

🎯 Entry Zone:
  Buy Above: ₹2460.00 - ₹2472.30

🛡️ Stop Loss:
  SL: ₹2430.00 (-0.8%)

🎯 Targets:
  Target 1: ₹2490.00 (+1.6%)
  Target 2: ₹2520.00 (+2.9%)

Confidence: 8/10

📊 Volume:
  Relative Vol: 1.85x
  Trend Aligned: Yes

📈 Factors:
  +Range Compression: 3
  +Volume Expansion: 2
  +Index Trend Alignment: 2
  +Relative Strength: 1
```

```bash
cd nse-trend-agent
python -m src.main
```

### Run Single Test Scan

```bash
python -m src.main --test
```

### Test Telegram Connection

```bash
python -m src.main --test-telegram
```

### Run with Mock Alerts (Testing Without Telegram)

```bash
python -m src.main --mock-alerts --test
```

### Custom Options

```bash
python -m src.main \
  --config config/stocks.json \
  --telegram-token YOUR_TOKEN \
  --telegram-chat-id YOUR_CHAT_ID \
  --log-level DEBUG \
  --log-file logs/scanner.log
```

## Command Line Options

| Option               | Description                                 | Default                                   |
| -------------------- | ------------------------------------------- | ----------------------------------------- |
| `--strategy`         | Strategy: trend, verc, or all               | `all`                                     |
| `--config`           | Path to stocks configuration file           | `config/stocks.json`                      |
| `--telegram-token`   | Telegram bot token                          | Environment variable `TELEGRAM_BOT_TOKEN` |
| `--telegram-chat-id` | Telegram chat ID                            | Environment variable `TELEGRAM_CHAT_ID`   |
| `--test`             | Run a single test scan                      | False                                     |
| `--test-telegram`    | Test Telegram connection                    | False                                     |
| `--mock-alerts`      | Use mock alert service                      | False                                     |
| `--log-level`        | Logging level (DEBUG, INFO, WARNING, ERROR) | INFO                                      |
| `--log-file`         | Log file path                               | `logs/scanner.log`                        |

## Project Structure

```
nse-trend-agent/
├── config/
│   ├── settings.json         # Telegram and scanner settings
│   └── stocks.json          # Stock list configuration
├── data/                    # Data storage (optional)
├── src/
│   ├── __init__.py          # Package initialization
│   ├── data_fetcher.py      # Yahoo Finance data fetching
│   ├── indicator_engine.py  # EMA and Volume MA calculations
│   ├── trend_detector.py    # Trend detection logic
│   ├── volume_compression.py # VERC (Volume Expansion Range Compression)
│   ├── alert_service.py     # Telegram alert handling
│   ├── scheduler.py         # Market hours scheduling
│   └── main.py              # Main entry point
├── logs/                    # Log files
├── requirements.txt         # Python dependencies
└── README.md               # This file
```

## How It Works

### Available Strategies

The scanner supports two independent strategies:

| Strategy            | File                        | Detection Method                                |
| ------------------- | --------------------------- | ----------------------------------------------- |
| **Trend Detection** | `src/trend_detector.py`     | EMA20>EMA50>EMA100>EMA200 + Volume confirmation |
| **VERC**            | `src/volume_compression.py` | Range Compression + Volume Expansion            |

### Trend Detection Logic

A stock is considered in **uptrend alignment** when:

```
EMA20 > EMA50 > EMA100 > EMA200
```

**Volume confirmation**:

```
Current Volume > Volume MA 30
```

**Trend start detection**:

```
Previous Candle: EMA20 <= EMA50
Current Candle:  EMA20 > EMA50
```

This signals the beginning of a potential bullish trend.

### VERC (Volume Expansion Range Compression) Strategy

Detects stocks that are quietly being accumulated by institutions before a breakout.

**Detection Criteria:**

- **Range Compression**: Price range (High-Low) < 5% of current price, OR ATR(14) is at local minimum
- **Volume Expansion**: Volume MA(5) > Volume MA(20), OR Relative Volume > 1.3
- **Trend Alignment**: Price > EMA50, OR EMA20 > EMA50

**Signal Generation:**

- Confidence score ≥ 7 required to generate alert
- Scoring: Range Compression (+3), Volume Expansion (+2), Breakout Volume (+2), Index Trend Alignment (+2), Relative Strength (+1)

**Alert Output:**

```
ACCUMULATION BREAKOUT

Stock: HDFCBANK

Compression Detected
Range: 1675.00 – 1685.00

Entry: 1685.00 – 1693.42
Stop: 1675.00

Target 1: 1695.00
Target 2: 1705.00

Confidence: 8/10

Factors:
  +Range Compression: 3
  +Volume Expansion: 2
  +Index Trend Alignment: 2
  +Relative Strength: 1
```

### Alert Message Format

```
🚨 TREND ALERT

📌 Stock: HDFCBANK
⏰ Time: 2024-01-15 10:30:00
📊 Timeframe: 15m

Signal Type: 🎯 New Uptrend Starting

Price: ₹1680.50
EMA Alignment:
  • EMA 20: ₹1685.20
  • EMA 50: ₹1675.30
  • EMA 100: ₹1660.40
  • EMA 200: ₹1645.50

Volume:
  • Current: 1,250,000
  • MA 30: 980,000
  • Ratio: 1.28x

EMA Alignment: 20 > 50 > 100 > 200
```

### Duplicate Alert Prevention

The system maintains an in-memory set (`alerted_today`) to prevent duplicate alerts. This list resets daily at midnight.

## Performance

- **Scanning 500 stocks**: 10-30 seconds per scan cycle
- **Memory usage**: Below 1GB
- **Scan Time**: Every 15 minutes during market hours (09:15 - 15:30 IST)

## Troubleshooting

### No Data Fetched

- Check internet connection
- Verify Yahoo Finance is accessible
- Some stocks may have limited data availability

### Telegram Alerts Not Working

- Verify bot token and chat ID
- Start a chat with your bot first
- Check bot permissions

### High Memory Usage

- Reduce the number of stocks being monitored
- Run during market hours only

## Future Improvements

- Multi-timeframe confirmation (15m + 1h + daily)
- RSI momentum filter
- Relative volume spikes
- AI-based trend strength analysis
- Web dashboard for signal history
- Backtesting engine
- VPS deployment for 24/7 reliability

## License

MIT License

## Disclaimer

This software is for educational purposes only. Trading in financial markets involves substantial risk. Always do your own research before making investment decisions.
