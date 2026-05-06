# Market Sentiment Analysis - Quick Reference

## 🎯 One-Line Summary
**AI-driven market sentiment analysis that alerts you on stocks running up in bullish markets, with confidence scores and AI validation.**

## ⚡ Quick Setup (30 seconds)

1. Edit `config/settings.json`:
```json
{
  "scanner": {
    "enable_sentiment_analysis": true,
    "sentiment_min_confidence": 0.60,
    "max_sentiment_signals_per_scan": 3
  }
}
```

2. Restart scanner

3. Get alerts during market hours

## 🎨 Alert Types

### Market Sentiment Alert
Sent when market sentiment changes significantly:
- **NEUTRAL → BULLISH**: Market turning positive
- **BULLISH → BEARISH**: Market turning negative
- Shows top performing/underperforming sectors

### Breakout Alert
Stock showing technical breakout with strong volume:
- Price change percentage
- Volume confirmation
- RSI and technical levels
- Support/Resistance levels
- AI confidence score

## 📊 Sentiment Levels

| Level | NIFTY State | Alert Rate | Best For |
|-------|-----------|-----------|----------|
| 🟢 STRONGLY_BULLISH | Strong uptrend, RSI>65 | HIGH (more signals) | Aggressive trading |
| 🔵 BULLISH | Moderate uptrend | MEDIUM | Most traders |
| ⚪ NEUTRAL | Sideways | LOW | Selective trades |
| 🟠 BEARISH | Downtrend | VERY LOW | Reversals only |
| 🔴 STRONGLY_BEARISH | Strong downtrend | NONE | Skip detailed scan |

## 🔧 Configuration Presets

### Conservative (Quality Over Quantity)
```json
{
  "sentiment_min_confidence": 0.80,
  "max_sentiment_signals_per_scan": 1
}
```
- Only highest quality breakouts
- ~1-2 alerts per day

### Balanced (Default)
```json
{
  "sentiment_min_confidence": 0.60,
  "max_sentiment_signals_per_scan": 3
}
```
- Good balance of opportunity vs quality
- ~3-5 alerts per day

### Aggressive (Quantity Over Quality)
```json
{
  "sentiment_min_confidence": 0.50,
  "max_sentiment_signals_per_scan": 5
}
```
- Catch more opportunities
- ~5-10 alerts per day
- More false signals

## 🚦 Signal Quality

Emoji in alerts indicates AI confidence:

- 🟢 **GREEN (80%+)**: Strong breakout, high confidence
- 🟡 **YELLOW (60-79%)**: Good breakout, decent confidence
- 🟠 **ORANGE (50-59%)**: Fair breakout, borderline confidence

## 📈 What Gets Alerted

```
Stock running UP + BULLISH market + AI validates = ALERT
```

Specifically:
- ✅ Price change > threshold (0.5% - 3% depending on sentiment)
- ✅ Volume > 1.2x - 3.0x average (depending on sentiment)
- ✅ RSI not extreme (40-75 range preferred)
- ✅ Price above moving averages
- ✅ AI confirms technical breakout
- ✅ Support/resistance levels identified

## ❌ What Doesn't Get Alerted

```
Stock running up + BEARISH market = NO ALERT
Stock weak volume + ANY market = NO ALERT
Low confidence score + ANY market = NO ALERT
Already alerted today + DUPLICATE CHECK = NO ALERT
```

## 🎯 Key Differences from Existing System

### Traditional Pattern Detection (Existing Trend Scanner)
- ✅ Requires tight consolidation
- ✅ Requires perfect EMA alignment
- ✅ High-quality signals
- ❌ Fewer alerts
- ❌ May miss running stocks

### Sentiment-Driven Detection (NEW)
- ✅ Catches any stock running with momentum
- ✅ Market-aware filtering
- ✅ AI-validated
- ✅ More alerts in bullish markets
- ❌ Slightly lower quality than tight patterns

**Both work together** - more coverage, complementary strategies

## 🏗️ System Architecture

```
Market Data (NIFTY, Sectors)
        ↓
    [Sentiment Analyzer]
        ↓
    Sentiment Level
    (BULLISH/BEARISH/NEUTRAL)
        ↓
   Running Stocks
   (Momentum Check)
        ↓
  AI Breakout Validation
  (Technical Check)
        ↓
  Confidence Score
  (50-100%)
        ↓
  Deduplication Check
  (Skip if recent/active)
        ↓
   Alert (if score > threshold)
        ↓
   Trade Journal Log
   (for tracking)
```

## 📱 Example Trading Day

```
09:15 AM - Market Opens
├─ Sentiment: NEUTRAL
├─ Alert Rate: LOW
└─ Scanning...

09:30 AM - First Signals
├─ Found 3 breakouts
├─ 2 alerts sent (confidence > 60%)
└─ INFY, TCS alerted

10:00 AM - Sentiment Shift
├─ Sentiment: BULLISH ✨
├─ Market Alert: "NIFTY turning bullish!"
└─ Alert Rate: MEDIUM

10:15 AM - More Opportunities
├─ Found 5 breakouts (more in bullish)
├─ 3 alerts sent (higher confidence)
└─ HDFC, ICICIBANK, LT alerted

12:00 PM - Mid-Day Slowdown
├─ Sentiment: BULLISH (stable)
├─ Lower volume, fewer signals
└─ 1 alert (selective)

14:00 PM - Afternoon Action
├─ Sentiment: BULLISH (stronger)
├─ Found 4 breakouts
├─ 2 alerts sent
└─ Last trading opportunities

15:30 PM - Market Close
├─ Sentiment: BULLISH (stable)
├─ Daily summary: 9 alerts sent
└─ 7 trades entered in journal

Day Summary:
├─ Market Sentiment: BULLISH
├─ Total Alerts: 9
├─ Trades Entered: 7
├─ Confidence Average: 72%
└─ Next day loading...
```

## 🎛️ Tuning Parameters

### Feeling Bullish? (Want more alerts)
```json
"sentiment_min_confidence": 0.55,
"max_sentiment_signals_per_scan": 5
```

### Market Looks Weak? (Want fewer alerts)
```json
"sentiment_min_confidence": 0.75,
"max_sentiment_signals_per_scan": 1
```

### Want Market Alerts? (Know sentiment changes)
```json
"enable_market_sentiment_alerts": true
```

### Want Only Highest Quality? (Conservative)
```json
"sentiment_min_confidence": 0.85,
"max_sentiment_signals_per_scan": 1,
"enable_market_sentiment_alerts": false
```

## 🔍 Data Flow

1. **Market Data Collection** (Nifty + Sectors)
   - Fetches 3-month historical data
   - Calculates EMAs, RSI, ATR
   - ~20 seconds per cycle

2. **Sentiment Analysis**
   - Determines trend (up/down/sideways)
   - Calculates momentum (-1 to +1)
   - Classifies sentiment level
   - ~5 seconds per cycle

3. **Stock Screening**
   - Identifies stocks up 1%+ with volume
   - Calculates momentum score
   - ~0.5 seconds per stock

4. **AI Validation**
   - For top candidates only
   - Validates breakout strength
   - Calculates confidence
   - ~2-3 seconds per stock

5. **Alert Generation**
   - Deduplication checks
   - Confidence filtering
   - Telegram dispatch
   - Trade journal logging

## 📊 Alert Rate Expectations

### In BULLISH Markets
- **Per 15-minute scan**: 2-4 alerts (varies by max_sentiment_signals_per_scan)
- **Per trading day**: 8-16 alerts
- **Per week**: 40-80 alerts
- **False signal rate**: ~30-40%

### In NEUTRAL Markets
- **Per 15-minute scan**: 0-1 alerts
- **Per trading day**: 0-5 alerts
- **Per week**: 0-25 alerts
- **False signal rate**: ~40-50%

### In BEARISH Markets
- **Detailed scan**: SKIPPED
- **Per trading day**: 0 alerts (unless market reverses)
- **False signal rate**: N/A

## 🎓 Learning from Alerts

The trade journal automatically logs all sentiment-driven alerts:
- Entry price
- Stop loss and targets
- Quality score
- Final outcome (Win/Loss)

Over time, you'll learn:
- Which confidence thresholds work best
- When sentiment alerts are most reliable
- Which sectors perform best
- Your personal win rate

## 🛑 Disable If Needed

To temporarily disable sentiment analysis:

```json
"enable_sentiment_analysis": false
```

The system will continue with existing Trend + VERC + MTF strategies.

## ✅ Checklist Before Using

- [ ] Dependencies installed (pandas, yfinance, etc.)
- [ ] Settings configured in `config/settings.json`
- [ ] Telegram alerts working
- [ ] AI analyzer configured (OpenAI/Anthropic/etc.)
- [ ] Sufficient stock list (50+ stocks recommended)
- [ ] Trade journal initialized
- [ ] Logs directory exists

## 🚀 Go Live

```bash
# Terminal 1: Start scanner
python src/main.py --live

# Terminal 2: Monitor logs
tail -f logs/scanner.log | grep "SENTIMENT"
```

Watch for:
- Market sentiment changes
- Breakout alerts with confidence scores
- Trade journal entries
- Any errors in logs

## 💡 Pro Tips

1. **Morning Trading**: Watch 9:30-11:00 AM for best signals
2. **Volume Confirmation**: Green signals usually have 1.5x+ volume
3. **Sector Alignment**: Better signals when stock is in strong sector
4. **Confidence > Speed**: Don't chase orange signals, wait for green
5. **Market Context**: Bullish alerts in bullish markets = higher win rate

## 📞 Troubleshooting Quick Fix

| Issue | Fix |
|-------|-----|
| Too many alerts | Increase `sentiment_min_confidence` to 0.75 |
| Too few alerts | Lower `sentiment_min_confidence` to 0.50 |
| False signals | Increase `sentiment_min_confidence`, reduce `max_sentiment_signals_per_scan` |
| Missing good trades | Lower `sentiment_min_confidence`, increase `max_sentiment_signals_per_scan` |
| No market alerts | Set `enable_market_sentiment_alerts: true` |
| Slow scanning | Reduce stock list size or disable AI validation temporarily |

---

**Key Takeaway**: Sentiment analysis catches running stocks in bullish markets that traditional pattern detection might miss, while reducing false alerts in bearish conditions through adaptive filtering and AI validation.

Happy trading! 📈
