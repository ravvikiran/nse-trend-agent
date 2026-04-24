# 🚀 Getting Started - Sentiment Analysis Setup

## ⏱️ Time Required: 5 minutes

## 📋 Pre-Flight Checklist

- [ ] Python 3.8+ installed
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] Telegram bot token available (TELEGRAM_BOT_TOKEN)
- [ ] Telegram chat ID available (TELEGRAM_CHAT_ID)
- [ ] AI provider configured (OpenAI/Anthropic/etc.)
- [ ] Stock watchlist ready (50+ stocks recommended)

## ✅ Step 1: Enable Sentiment Analysis (1 minute)

### Edit `config/settings.json`

Add or update the `scanner` section:

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

**What these mean:**
- `enable_sentiment_analysis`: Turn on/off the entire feature
- `enable_market_sentiment_alerts`: Alert when market sentiment changes
- `max_sentiment_signals_per_scan`: Max alerts per 15-minute scan (1-5 recommended)
- `sentiment_min_confidence`: Quality threshold (0.5=loose, 0.8=strict)

## ✅ Step 2: Verify Configuration (1 minute)

Make sure your `config/settings.json` has:

```json
{
  "telegram": {
    "bot_token": "YOUR_TOKEN_HERE_OR_ENV_VAR",
    "chat_id": "YOUR_CHAT_ID_HERE_OR_ENV_VAR"
  },
  "scanner": {
    "enable_sentiment_analysis": true
  }
}
```

## ✅ Step 3: Restart Scanner (2 minutes)

In your terminal:

```bash
# Stop the current scanner (Ctrl+C if running)

# Restart with sentiment analysis enabled
python src/main.py --live
```

## ✅ Step 4: Monitor First Run (1 minute)

Watch for messages like:

```
INFO: Market Sentiment: BULLISH
INFO: Running Sentiment-Driven Scan...
INFO: Found 5 stocks running up
INFO: Sent sentiment-driven alert for INFY (confidence: 82%)
```

## 🎯 Configuration Presets

### Choice 1: Conservative (Highest Quality)
Want fewer, higher-quality alerts?

```json
{
  "sentiment_min_confidence": 0.80,
  "max_sentiment_signals_per_scan": 1,
  "enable_market_sentiment_alerts": false
}
```

**Expected**: 1-2 alerts per day, very high win rate

### Choice 2: Balanced (Recommended Default)
Want a good mix of opportunities and quality?

```json
{
  "sentiment_min_confidence": 0.60,
  "max_sentiment_signals_per_scan": 3,
  "enable_market_sentiment_alerts": true
}
```

**Expected**: 4-8 alerts per day, good win rate

### Choice 3: Aggressive (Most Opportunities)
Want to catch as many opportunities as possible?

```json
{
  "sentiment_min_confidence": 0.50,
  "max_sentiment_signals_per_scan": 5,
  "enable_market_sentiment_alerts": true
}
```

**Expected**: 8-15 alerts per day, more false signals

## 📊 What to Expect

### First Market Sentiment Analysis (9:15 AM)
```
🎯 MARKET SENTIMENT ALERT
━━━━━━━━━━━━━━━━━━━━━
Sentiment: BULLISH
NIFTY Trend: UPTREND
Momentum: +0.35
Volatility: 1.1%

Top Sectors:
✅ Strong: IT, BANKING
```

### First Breakout Alert (varies)
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

Confidence: 85% 🟢
```

## 🔧 Tuning Guide

### Getting Too Many Alerts?
```json
"sentiment_min_confidence": 0.75    # Increase from 0.60
"max_sentiment_signals_per_scan": 1 # Reduce from 3
```

### Getting Too Few Alerts?
```json
"sentiment_min_confidence": 0.50    # Decrease from 0.60
"max_sentiment_signals_per_scan": 5 # Increase from 3
```

### Want Only Market Sentiment, No Breakouts?
```json
"enable_sentiment_analysis": false  # Disable breakouts
"enable_market_sentiment_alerts": true  # Keep market alerts
```

### Want Everything, Maximize Opportunities?
```json
"sentiment_min_confidence": 0.45
"max_sentiment_signals_per_scan": 5
"enable_market_sentiment_alerts": true
```

## 📝 Logging

### View Live Logs
```bash
# Terminal 1: Run scanner
python src/main.py --live

# Terminal 2: Watch logs
tail -f logs/scanner.log | grep "SENTIMENT"
```

### What to Look For
```
✅ INFO: Market Sentiment: BULLISH    # Sentiment detected
✅ INFO: Running Sentiment-Driven Scan... # Scan started
✅ INFO: Found X stocks running up     # Stocks found
✅ INFO: Sent sentiment-driven alert   # Alert sent
❌ DEBUG: Skipping X: in signal memory # Duplicate (normal)
❌ ERROR: Error in sentiment scan:     # Problem (check logs)
```

## 🎛️ Daily Workflow

### 9:15 AM - Market Opens
1. Scanner starts
2. Sentiment analysis begins
3. First scan happens
4. Market sentiment alert sent (if sentiment is strong)

### 9:30-15:00 - Trading Hours
1. Every 15 minutes:
   - Sentiment analysis runs
   - Breakout scan runs
   - Alerts sent (if conditions met)

### 15:30 - Market Close
1. Final sentiment analysis
2. Prepares for next day

## 📊 Metrics to Track

Over the next week, monitor:

1. **Alert Volume**
   - How many alerts per day?
   - Match your trading capacity?

2. **Accuracy**
   - How many lead to profitable trades?
   - Track in trade journal

3. **Confidence Correlation**
   - Do green (80%+) alerts win more often?
   - Adjust threshold based on this

4. **Market Sentiment Usefulness**
   - Do bullish market alerts lead to better trades?
   - Do bearish market alerts prevent losses?

## 🚨 Troubleshooting

### No Alerts for 1+ Hour?

**Check 1: Is market open?**
```
Market hours: 9:15 AM - 3:30 PM IST
Skip: Weekends and holidays
```

**Check 2: Is sentiment analysis enabled?**
```bash
grep "enable_sentiment_analysis" config/settings.json
# Should show: "enable_sentiment_analysis": true
```

**Check 3: Look at logs**
```bash
tail -20 logs/scanner.log | grep SENTIMENT
```

**Check 4: Market might be bearish**
```
In STRONGLY_BEARISH market, detailed scan is skipped
Only market sentiment alerts are sent
This is by design
```

### Too Many False Signals?

**Solution 1: Increase confidence threshold**
```json
"sentiment_min_confidence": 0.75    # From 0.60
```

**Solution 2: Reduce max signals**
```json
"max_sentiment_signals_per_scan": 1 # From 3
```

**Solution 3: Wait for green (80%+) signals only**
- Track in trade journal
- Adjust threshold based on results

### Telegram Not Receiving Alerts?

**Check:**
1. Is TELEGRAM_BOT_TOKEN set? `echo $TELEGRAM_BOT_TOKEN`
2. Is TELEGRAM_CHAT_ID set? `echo $TELEGRAM_CHAT_ID`
3. Is bot still running? (check for token expiry)
4. Check logs for Telegram errors: `grep -i telegram logs/scanner.log`

### Scanner Running Slow?

**Sentiment analysis typically adds:**
- 20 seconds for market analysis
- 30 seconds for stock scanning
- 5-15 seconds for AI validation
- **Total: ~60 seconds per 15-minute cycle** ✓ Normal

**If slower:**
1. Reduce stock list size
2. Disable AI validation temporarily
3. Check system resources

## 📈 First Week Expectations

### Day 1-2
- System warming up
- Market sentiment detected
- 0-5 alerts (market dependent)
- No trades needed yet (observe)

### Day 3-5
- Pattern emerges
- Alert quality visible
- 5-15 alerts (market dependent)
- Some trades taken if conditions right

### Day 6-7
- Tune based on results
- Adjust confidence threshold
- Optimize for your style

## 💡 Pro Tips for First Week

1. **Don't trade on first day**: Just observe alerts
2. **Track in trade journal**: Essential for analysis
3. **Adjust gradually**: Don't change settings daily
4. **Watch bullish markets**: Better alert quality
5. **Trust the confidence**: Green (80%+) beats yellow/orange
6. **Monitor sector trends**: Shown in market sentiment alerts
7. **Note market conditions**: Track when alerts work best

## 🎓 Next Steps

### Once Setup is Complete:

1. **Read documentation**
   - `docs/SENTIMENT_QUICK_REFERENCE.md` - 10 min read
   - `docs/MARKET_SENTIMENT_ANALYSIS.md` - 15 min read

2. **Monitor for 2-3 days**
   - Get feel for alert frequency
   - Understand market sentiment changes
   - Track trade outcomes

3. **Tune settings**
   - Based on your trading style
   - Based on alert accuracy
   - Based on market conditions

4. **Optimize strategy**
   - Combine with your existing rules
   - Set position sizes
   - Manage risk per alert

## ✅ First 24 Hours Checklist

- [ ] Edit config/settings.json with sentiment settings
- [ ] Restart scanner
- [ ] Check logs for "Market Sentiment: " messages
- [ ] Receive first market sentiment alert
- [ ] Receive first breakout alert
- [ ] Verify alert format is clear
- [ ] Check trade journal has entries
- [ ] Review one alert in detail

## 📞 Quick Help

| Issue | Quick Fix |
|-------|-----------|
| No logs | `enable_sentiment_analysis` missing or false |
| No alerts | Market might be bearish (by design) |
| Too many alerts | Increase `sentiment_min_confidence` to 0.75 |
| Too few alerts | Lower `sentiment_min_confidence` to 0.50 |
| Slow scanner | Reduce stock list or disable AI validation |
| Telegram failing | Check bot token and chat ID |

## 🎉 You're Ready!

```
✅ Setup Complete
✅ Configuration Done
✅ Scanner Running
✅ Sentiment Analysis Active
✅ Alerts Incoming

Ready to catch running stocks! 📈
```

---

**Start here**: Edit config/settings.json and restart → You're done! 🚀

Need help? Check docs in `/docs/` folder.

Happy trading! 📈💰
