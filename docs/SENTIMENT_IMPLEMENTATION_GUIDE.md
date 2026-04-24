# Market Sentiment Analysis - Implementation Guide

## 🎯 What's New

I've added comprehensive AI-driven market sentiment analysis to your NSE trend scanner. This enhancement allows your system to:

1. **Detect Market Sentiment** - Analyze if NIFTY is in BULLISH, BEARISH, or NEUTRAL mode
2. **Identify Running Stocks** - Find stocks showing momentum even without traditional patterns
3. **AI-Validate Breakouts** - Use AI to confirm technical breakouts are worth trading
4. **Generate Smart Alerts** - Alert on stocks that are running in bullish markets with volume confirmation

## 📦 New Files Added

### Core Modules

1. **`src/market_sentiment_analyzer.py`** (NEW)
   - Analyzes overall market sentiment
   - Detects sector trends
   - Identifies running stocks with momentum
   - Uses AI to validate breakouts
   - Caches sentiment data for performance

2. **`src/sentiment_driven_scanner.py`** (NEW)
   - Scans stocks for technical breakouts
   - Applies adaptive filtering based on market sentiment
   - Calculates momentum and quality scores
   - Validates signals with AI
   - Formats breakout alerts

### Documentation

3. **`docs/MARKET_SENTIMENT_ANALYSIS.md`** (NEW)
   - Comprehensive feature documentation
   - Examples and use cases
   - Configuration guide
   - Troubleshooting tips

4. **`config/settings.sentiment.json`** (NEW)
   - Example configuration with sentiment settings
   - Recommended parameter values

### Updated Files

5. **`src/main.py`** (UPDATED)
   - Added imports for sentiment modules
   - Initialized sentiment analyzer in NSETrendScanner.__init__
   - Added `_run_sentiment_driven_scan()` method
   - Integrated sentiment scan into main scan cycle

## 🚀 Quick Start

### 1. Enable Sentiment Analysis

Edit your `config/settings.json`:

```json
{
  "scanner": {
    "enable_sentiment_analysis": true,
    "enable_market_sentiment_alerts": true,
    "max_sentiment_signals_per_scan": 3,
    "sentiment_min_confidence": 0.60
  }
}
```

### 2. Restart the Scanner

Your scanner will now:
- Analyze market sentiment every 15 minutes
- Send market sentiment alerts when conditions change
- Scan for stocks running with momentum
- Validate each breakout with AI
- Alert on high-confidence breakouts

### 3. Monitor Alerts

You'll see new alert types:

**Market Sentiment Alert:**
```
🎯 MARKET SENTIMENT ALERT
━━━━━━━━━━━━━━━━━━━━━
Sentiment: STRONGLY_BULLISH
NIFTY Trend: UPTREND
Momentum: +0.45 (Strong)
Volatility: 1.2%

Top Sectors:
✅ Strong: IT, BANKING, AUTO
```

**Sentiment-Driven Breakout Alert:**
```
🟢 SENTIMENT-DRIVEN BREAKOUT
━━━━━━━━━━━━━━━━━━━━━━━
📊 INFY @ ₹2150.50

📈 Price Action:
   • Change: +2.35%
   • Volume: 1.85x avg
   • RSI: 62.3

🎯 Technical:
   • Type: TREND_ALIGNED
   • Support: ₹2130.25
   • Target: ₹2180.75
   • Quality: 7.5/10

📍 Market Context:
   • Sentiment: BULLISH
   • Confidence: 85%
```

## 🔧 Configuration Reference

### Enable/Disable Features

```json
"scanner": {
  "enable_sentiment_analysis": true,           // Main toggle
  "enable_market_sentiment_alerts": true,      // Market sentiment change alerts
  "max_sentiment_signals_per_scan": 3,         // Breakout signals per scan
  "sentiment_min_confidence": 0.60             // AI confidence threshold (0.5-1.0)
}
```

### Tuning Parameters

**For More Aggressive Alerts (Catch More Opportunities):**
```json
{
  "sentiment_min_confidence": 0.50,
  "max_sentiment_signals_per_scan": 5
}
```

**For More Conservative Alerts (Higher Quality):**
```json
{
  "sentiment_min_confidence": 0.80,
  "max_sentiment_signals_per_scan": 2
}
```

## 📊 How Market Sentiment Affects Alerts

### STRONGLY_BULLISH Market
- Market: Strong uptrend, high RSI, strong volume
- **Min Price Change:** 0.5% (Lower threshold)
- **Min Volume:** 1.2x average
- **Alert Rate:** HIGH (more opportunities)
- **Best For:** Swing trading, catching trends early

### BULLISH Market
- Market: Moderate uptrend, moderate RSI
- **Min Price Change:** 1.0%
- **Min Volume:** 1.5x average
- **Alert Rate:** MEDIUM (balanced)
- **Best For:** Most trading styles

### NEUTRAL Market
- Market: Sideways, no clear direction
- **Min Price Change:** 1.5%
- **Min Volume:** 2.0x average
- **Alert Rate:** LOW (fewer alerts)
- **Best For:** Selective traders only

### BEARISH Market
- Market: Downtrend, low RSI, weak volume
- **Min Price Change:** 2.0%
- **Min Volume:** 2.5x average
- **Alert Rate:** VERY LOW (conservative)
- **Best For:** Look for reversal setups

### STRONGLY_BEARISH Market
- Market: Strong downtrend
- **Detailed Scan:** SKIPPED (no breakout alerts)
- **Alert Rate:** NONE (only market sentiment alert)
- **Best For:** Avoid new positions, or short trading

## 🎨 Alert Quality Indicators

Each alert includes a confidence emoji:

- 🟢 **GREEN (80%+)**: Very high confidence - strong technical setup
- 🟡 **YELLOW (60-79%)**: Good confidence - solid technical setup
- 🟠 **ORANGE (50-59%)**: Moderate confidence - acceptable setup

## 🔍 What Gets Alerted

The sentiment-driven scanner alerts on:

1. **Stocks Breaking Above 20-Day High**
   - Good support/resistance level
   - Shows strength

2. **Stocks with Price > All EMAs (Perfect Alignment)**
   - Price > EMA20 > EMA50 > EMA100 > EMA200
   - Strongest technical signal

3. **Stocks with Strong Momentum (2%+ move, 1.5x+ volume)**
   - Shows conviction
   - Volume confirmation

4. **Stocks in Bullish/Neutral Markets**
   - Context alignment
   - Reduced false signals in bearish conditions

## 📈 Trading Strategy with Sentiment Analysis

### Pre-Market (Before 9:15 AM)
- Sentiment analyzer warms up, loads cached data
- No alerts (market closed)

### Market Open (9:15-10:00 AM)
- First sentiment analysis runs
- May show NEUTRAL initially
- Fewer alerts during price discovery

### Mid-Morning (10:00-12:00 PM)
- Sentiment becomes clearer
- Most reliable signals
- Good volume confirmation

### Lunch Hour (12:00-14:00 PM)
- Reduced volume, more noise
- Try higher confidence threshold
- Fewer alerts expected

### Afternoon (14:00-15:30 PM)
- Strong directional moves
- High-quality signals
- Final hour is active

### Post-Market (15:30+)
- Market close sentiment analysis
- Prepares for next day

## 🎯 Signal Deduplication

The system prevents alert fatigue through:

1. **In-Memory Deduplication** - Won't alert same stock twice in one session
2. **Signal Memory** - Persistent dedup (prevents recent repeats)
3. **Trade Journal** - Won't alert on stock already in active trade
4. **Confidence Threshold** - Only high-quality signals

## 🤖 AI Validation

Each breakout goes through AI validation checking:

- Is the technical pattern valid?
- Does it align with market sentiment?
- What's the quality of the breakout?
- Is there good risk/reward potential?

AI confidence (0-100%):
- 80%+: "Yes, this is a strong breakout"
- 60-79%: "Yes, but with some caution"
- 50-59%: "Borderline, be selective"
- <50%: "Skip this one"

## 🐛 Debugging

### Enable Debug Logging

Edit your logging configuration to see detailed sentiment analysis:

```python
logging.getLogger('__main__').setLevel(logging.DEBUG)
```

### Check Sentiment Data

The analyzer saves sentiment data to `data/market_sentiment.json`:

```json
{
  "current_sentiment": "BULLISH",
  "sentiment_strength": 0.35,
  "nifty_trend": "UPTREND",
  "market_momentum": 0.42,
  "volatility": 1.25,
  "sector_trends": {
    "IT": "STRONG",
    "BANKING": "POSITIVE",
    ...
  }
}
```

## 📝 What Happens Behind the Scenes

### Every 15 Minutes During Market Hours:

1. **Sentiment Analysis** (10-20 seconds)
   - Fetch NIFTY 3-month data
   - Calculate EMAs, RSI, ATR
   - Determine trend and momentum
   - Analyze sector performance
   - Save sentiment data

2. **Running Stocks Identification** (30-60 seconds for 100 stocks)
   - Check each stock for 1%+ move
   - Verify volume confirmation
   - Calculate momentum score

3. **AI Breakout Validation** (2-3 seconds per signal)
   - For top breakout candidates
   - Use LLM to validate
   - Calculate confidence score

4. **Alert Generation**
   - Filter by confidence threshold
   - Avoid duplicates
   - Format and send alerts

## 🎬 Example Session

**9:15 AM - Market Opens**
```
INFO: Market context: SIDEWAYS
INFO: Market Sentiment: NEUTRAL
DEBUG: No sentiment alerts (stable market)
```

**9:30 AM - First Scan**
```
INFO: Scanning 100 stocks...
INFO: Found 12 stocks running up
INFO: Validating with AI...
INFO: Found 3 high-confidence breakouts
📊 ALERT: INFY breakout (confidence: 82%)
📊 ALERT: TCS breakout (confidence: 76%)
```

**10:00 AM - Sentiment Shift**
```
INFO: Market Sentiment changed!
INFO: Market Sentiment: BULLISH
🎯 MARKET SENTIMENT ALERT: NIFTY turned bullish!
INFO: Sentiment Strength: 0.45
```

**10:15 AM - Active Scan**
```
INFO: Scanning 100 stocks...
INFO: Found 8 stocks running up (bullish market)
INFO: Validating with AI...
📊 ALERT: HDFC breakout (confidence: 71%)
INFO: 3 alerts skipped (already sent, or low confidence)
```

## ⚙️ Performance Considerations

- **Sentiment Analysis**: ~20 seconds per 15-min cycle
- **Stock Scanning**: ~1 second per 10 stocks
- **AI Validation**: ~2-3 seconds per stock

Total overhead: ~30-60 seconds per 15-minute scan

If this is too slow:
- Reduce stock list size
- Disable AI validation (set confidence threshold very high)
- Increase scan interval

## 🔐 Security Notes

- Sentiment data is cached locally in `data/` directory
- No external APIs beyond your AI provider
- Uses existing LLM configuration
- All stock data comes from yfinance (same as before)

## 📞 Support

If you encounter issues:

1. **Check logs** in `logs/scanner.log`
2. **Verify settings** in `config/settings.json`
3. **Test manually**:
   ```python
   from market.market_sentiment_analyzer import create_market_sentiment_analyzer
   analyzer = create_market_sentiment_analyzer()
   sentiment = analyzer.analyze_market_sentiment()
   print(sentiment)
   ```

## ✨ Next Steps

1. ✅ Sentiment analysis is now integrated
2. ✅ Review documentation and examples
3. ✅ Configure settings for your trading style
4. ✅ Monitor alerts during market hours
5. ✅ Adjust confidence threshold based on results
6. ✅ Track performance in trade journal

## 🎉 Summary

You now have:
- **Market Sentiment Detection** - Know when market is bullish/bearish
- **Running Stocks Identification** - Catch momentum moves
- **AI-Validated Breakouts** - Confidence scores on each signal
- **Smart Filtering** - Fewer alerts, better quality
- **Sector Analysis** - Understand sector rotation
- **Adaptive Thresholds** - Adjust to market conditions automatically

Happy trading! 📈
