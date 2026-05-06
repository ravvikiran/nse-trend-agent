# Market Sentiment Analysis - Feature Documentation

## Overview

The Market Sentiment Analyzer is a new AI-driven component that enhances the NSE trend scanner with intelligent market sentiment analysis. Instead of alerting only on traditional technical patterns, it now:

1. **Analyzes Market Sentiment** - Determines if the market is Bullish, Bearish, or Neutral
2. **Identifies Running Stocks** - Finds stocks showing momentum with volume confirmation
3. **AI-Validates Breakouts** - Uses AI to confirm if a breakout is worth trading
4. **Context-Aware Alerts** - Filters alerts based on market sentiment and sector trends

## How It Works

### 1. Market Sentiment Detection

The sentiment analyzer examines:
- **NIFTY Trend**: Analyzes EMA alignment (EMA20 > EMA50 > EMA100 > EMA200)
- **Price Momentum**: Calculates 20-day price change and RSI levels
- **Volume Analysis**: Checks if volume is supporting price movement
- **Volatility**: Measures market volatility through ATR

**Sentiment Levels:**
- `STRONGLY_BULLISH`: NIFTY in uptrend + strong momentum
- `BULLISH`: NIFTY in uptrend with moderate momentum
- `NEUTRAL`: Sideways market without clear direction
- `BEARISH`: NIFTY in downtrend
- `STRONGLY_BEARISH`: NIFTY in strong downtrend

### 2. Running Stocks Detection

Identifies stocks that are:
- Up **1%+** in recent sessions (default: 5 days)
- With **1.2x+ volume** compared to average
- Showing technical strength (RSI, price above EMAs)

### 3. AI-Validated Breakout Detection

For each running stock, the AI analyzer checks:
- Is this a valid technical breakout?
- Does it align with market sentiment?
- What's the quality of the breakout?
- Is there good risk/reward potential?

### 4. Adaptive Filtering

Thresholds change based on market sentiment:

```
STRONGLY_BULLISH market:
  - Minimum price change: 0.5%
  - Minimum volume ratio: 1.2x
  - Even weak breakouts are considered (more signals)

BULLISH market:
  - Minimum price change: 1.0%
  - Minimum volume ratio: 1.5x
  - Standard breakout filtering

NEUTRAL market:
  - Minimum price change: 1.5%
  - Minimum volume ratio: 2.0x
  - Stricter requirements

BEARISH/STRONGLY_BEARISH:
  - Minimum price change: 2.0% - 3.0%
  - Minimum volume ratio: 2.5x - 3.0x
  - Or: Detailed scan is skipped
```

## Alert Format

When a sentiment-aligned breakout is found, you receive:

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

⏰ 11:45 IST
```

## Configuration

Add these settings to `config/settings.json`:

```json
{
  "scanner": {
    "enable_sentiment_analysis": true,
    "max_sentiment_signals_per_scan": 3,
    "sentiment_min_confidence": 0.60,
    "enable_mtf_strategy": true,
    "enable_market_sentiment_alerts": true
  }
}
```

**Parameters:**
- `enable_sentiment_analysis`: Enable/disable the sentiment-driven scanner
- `max_sentiment_signals_per_scan`: Max breakout alerts per scan cycle (15 min)
- `sentiment_min_confidence`: Minimum AI confidence (0.0-1.0) for alerts
- `enable_market_sentiment_alerts`: Alert when market sentiment changes significantly

## Key Features

### 1. Sector Analysis
The analyzer tracks sector trends to understand market structure:
- Identifies strong sectors (IT, Banking, Auto, Pharma, FMCG, etc.)
- Uses sector performance to validate individual stock signals
- Includes sector trend in alert messages

### 2. Multiple Breakout Types Detected
- `TREND_ALIGNED`: Price + All EMAs in proper order (strongest)
- `LEVEL_BREAKOUT`: Breaking above 20-day high
- `MA_BREAKOUT`: Breaking above key moving averages
- `MOMENTUM_BREAKOUT`: Strong momentum without pattern

### 3. Quality Scoring
Each signal gets a quality score (0-10) based on:
- EMA alignment (0-3 points)
- RSI position (0-2 points)
- Volume confirmation (0-2 points)
- Distance from 20-day high (0-2 points)
- Price above EMA100 (0-1 point)

### 4. Adaptive Confidence
Final confidence combines:
- Technical quality score (70% weight)
- AI validation result (30% weight)
- Market sentiment multiplier

## Running Stocks vs Pattern Breakouts

### Traditional Pattern-Based Detection (Existing)
Requires:
- Tight consolidation (small trading range)
- EMA alignment in perfect order
- Volume explosion
- RSI confirmation

Gets fewer signals but higher quality.

### Sentiment-Driven Detection (NEW)
Catches:
- Any stock running with momentum
- Even stocks without perfect patterns
- In bullish markets (when they matter most)
- With AI validation of breakout strength

Gets more signals during bullish markets.

## Examples

### Scenario 1: Bullish Market
**Market Sentiment:** STRONGLY_BULLISH
- NIFTY: Uptrend, RSI > 65, Volume supporting
- TCS: Up 2.1%, 1.8x volume, RSI 58, Price > EMA20/50
  - ✅ **ALERT**: "TCS breakout aligned with bullish market"

### Scenario 2: Neutral Market
**Market Sentiment:** NEUTRAL
- NIFTY: Sideways, RSI 50-55, Low volatility
- INFY: Up 0.8%, 1.2x volume
  - ❌ **SKIPPED**: Move too small in neutral market

### Scenario 3: Bearish Market
**Market Sentiment:** BEARISH
- NIFTY: Downtrend, RSI < 40, Weak volume
- RELIANCE: Up 1.5%, 1.4x volume, RSI 55
  - ❌ **SKIPPED**: Market too bearish for detailed scan

## Integration with Existing System

The sentiment analyzer works alongside your existing scanners:

1. **Trend Detector**: Finds technical breakout patterns
2. **VERC Scanner**: Detects volume expansion patterns
3. **MTF Strategy**: Validates across multiple timeframes
4. **Sentiment Scanner** (NEW): Catches momentum-based breakouts

All signals are:
- Deduplicated against recent signals
- Checked for active trades (no double alerts)
- Logged to trade journal
- Ranked by confidence score

## Benefits

1. **Catch Running Stocks**: Alerts on stocks moving up even without textbook patterns
2. **Market-Aware**: Fewer false alerts in bearish markets
3. **AI-Validated**: Each breakout is confirmed by AI analysis
4. **Context-Rich**: Alerts include market sentiment and sector information
5. **Reduced Noise**: Adaptive thresholds prevent alert fatigue

## Disabling the Feature

To disable sentiment-driven scanning:

```json
{
  "scanner": {
    "enable_sentiment_analysis": false
  }
}
```

The system will continue with traditional pattern-based detection.

## Performance Tips

1. **Adjust Confidence Threshold**:
   - Lower (0.5) = More alerts, some false signals
   - Higher (0.8) = Fewer alerts, very high quality

2. **Max Signals Per Scan**:
   - Lower (1-2) = Fewer distractions
   - Higher (4-5) = More trading opportunities

3. **Time of Day**:
   - Morning (9:15-11:00): More noise, try higher confidence
   - Midday (11:00-14:00): Slower, may want lower threshold
   - Afternoon (14:00-15:30): Cleaner moves, can alert more

## Troubleshooting

**Q: Getting too many false alerts?**
A: Increase `sentiment_min_confidence` to 0.75-0.85

**Q: Missing some good breakouts?**
A: Lower `sentiment_min_confidence` to 0.50-0.60, increase `max_sentiment_signals_per_scan`

**Q: AI validation seems slow?**
A: This is normal. AI analysis adds 2-3 seconds per stock. Consider reducing stock list.

**Q: No sentiment alerts during bearish market?**
A: By design - detailed scan is skipped in STRONGLY_BEARISH. Set `enable_market_sentiment_alerts: false` to stop market alerts.

## Future Enhancements

Planned improvements:
- Real-time sentiment from news/social media
- Sector rotation detection
- Options flow analysis
- Machine learning trained on your trade history
- Integration with market breadth indicators
