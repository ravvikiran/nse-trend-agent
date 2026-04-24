# NSE Trend Scanner - Web UI Quick Reference

## Quick Start (30 seconds)

```bash
# 1. Install Flask
pip install flask flask-cors

# 2. Start the UI
python src/api.py

# 3. Open browser
http://localhost:5000
```

Or use the launcher:
```bash
# macOS/Linux
bash run_ui.sh

# Windows
run_ui.bat
```

---

## Dashboard Overview

### Left Sidebar Navigation
```
📊 Dashboard    → Main overview with key metrics
💼 Trades       → Open positions and trade history
📈 Performance  → Analytics and performance charts
🔍 Analysis     → Market analysis and signals
⚙️ Settings     → Configuration and API keys
```

### Dashboard Widgets

| Widget | Shows |
|--------|-------|
| **Open Trades** | Number of active positions |
| **Win Rate** | Percentage of winning trades |
| **Total Trades** | All trades (wins + losses) |
| **Total P&L** | Cumulative profit/loss |
| **Market Status** | OPEN/CLOSED with time to close |
| **Scanner Status** | Running/Stopped + stats |
| **Today's Performance** | Trades and P&L for today |
| **Charts** | Win/Loss pie + P&L curve |

---

## Features By Page

### 1️⃣ Dashboard (`/`)

**Real-time Metrics:**
- Market hours countdown
- Scanner status indicator
- Open positions count
- Win rate percentage

**Charts:**
- Win/Loss distribution (pie chart)
- Cumulative P&L curve (line chart)

**Recent Trades Table:**
- Last 5 open trades
- Entry, Current, SL, Targets
- Unrealized P&L with color coding

**Quick Actions:**
- 🟢 Start Scanner button
- 🔴 Stop Scanner button

### 2️⃣ Trades (`/trades`)

**Tab 1: Open Trades**
- All active positions
- Live price updates every 60 seconds
- P&L calculation in ₹ and %
- Distance to SL and targets
- Days held counter

**Tab 2: Trade History**
- Complete trade journal
- Filters: Strategy, Outcome, Timeframe
- Click trade for detailed modal
- Trade details include:
  - Entry/Exit prices
  - Risk:Reward ratio
  - Indicator values (RSI, Volume, etc.)
  - Trade quality rating

### 3️⃣ Performance (`/performance`)

**Summary Metrics:**
- Total trades count
- Win count / Loss count
- Win rate percentage
- Profit Factor
- Average Risk:Reward ratio

**P&L Summary:**
- Total P&L (₹)
- Gross Profit (₹)
- Gross Loss (₹)
- Max Drawdown (₹)

**Charts:**
- Strategy performance (horizontal bar)
- Cumulative P&L curve (line)
- Win vs Loss distribution (doughnut)

**Strategy Table:**
- Performance breakdown by strategy
- Win rate per strategy
- Click "View" for strategy details

### 4️⃣ Analysis (`/analysis`)

**Market Sentiment:**
- NIFTY Trend: BULLISH/BEARISH/SIDEWAYS
- Market Strength: 0-100%
- Volatility: LOW/NORMAL/HIGH
- Last updated time

**Charts:**
- Sector Leaders (bar chart)
- Signals Distribution (doughnut)

**Signals by Day:**
- Last 30 days data
- Daily signal count
- Win/Loss breakdown
- Win rate percentage

**Top Performing Stocks:**
- Ranked by win rate
- Total trades per stock
- Average profit/loss

### 5️⃣ Settings (`/settings`)

#### General Settings
- Scanner name
- Scan interval (minutes)
- Default quantity per trade
- Risk per trade (%)
- Skip weekends toggle

#### Strategy Settings
- Strategy weights (TREND, VERC, MTF, SWING)
- Trend parameters (volume ratio, RSI)
- Position management (SL%, T1%, T2%)

#### API Keys
- Telegram Bot Token
- Telegram Chat ID
- OpenAI API Key
- Groq API Key

#### Alert Preferences
- Telegram alerts toggle
- Email alerts toggle
- Minimum confidence score
- Alert sound selection

#### Advanced Settings
- Max open trades limit
- Trade timeout period (days)
- Auto-optimization toggle
- AI learning toggle
- Logging level

#### Danger Zone
- Reset to defaults button
- Clear trade history button

---

## How to Use Each Feature

### Monitor Open Trades

1. Go to **Trades** page
2. Click **Open Trades** tab
3. View all active positions
4. Click any row to see full trade details
5. P&L updates every 60 seconds

**Color Coding:**
- 🟢 Green = Profitable position
- 🔴 Red = Losing position

### Check Performance

1. Go to **Performance** page
2. View summary metrics (top)
3. Check strategy performance breakdown
4. View charts for trends

**Key Metrics to Watch:**
- Win Rate: Target > 50%
- Profit Factor: Target > 1.5
- Max Drawdown: Should be reasonable

### Analyze Market Sentiment

1. Go to **Analysis** page
2. Check NIFTY trend
3. View sector leaders
4. See signals generated over time

### Configure Scanner

1. Go to **Settings** page
2. Navigate to desired section (left sidebar)
3. Update values
4. Click **Save** button
5. Confirmation message appears

### Export Trade Data

From **Trades** page:
```javascript
// In browser console
JSON.stringify(trades, null, 2)
```

Then copy/paste to spreadsheet.

---

## API Integration

### Get Open Trades (JavaScript)
```javascript
fetch('/api/trades/open')
  .then(r => r.json())
  .then(data => {
    console.log(`Open trades: ${data.count}`);
    console.log(`Unrealized P&L: ₹${data.total_unrealized_pnl}`);
  });
```

### Get Performance Summary
```javascript
fetch('/api/performance/summary')
  .then(r => r.json())
  .then(data => {
    console.log(`Win Rate: ${data.win_rate}%`);
    console.log(`Total P&L: ₹${data.total_pnl}`);
  });
```

### Update Settings
```javascript
fetch('/api/settings', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    scan_interval: 20,
    risk_per_trade: 2.5
  })
})
.then(r => r.json())
.then(data => console.log('Settings saved!'));
```

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `/` | Focus search (future) |
| `?` | Show keyboard help |
| `d` | Go to Dashboard |
| `t` | Go to Trades |
| `p` | Go to Performance |
| `a` | Go to Analysis |
| `s` | Go to Settings |

*(Requires JavaScript enhancement)*

---

## Color Meanings

| Color | Meaning |
|-------|---------|
| 🟢 Green | Profit / Positive / Success |
| 🔴 Red | Loss / Negative / Alert |
| 🔵 Blue | Primary action / Information |
| 🟡 Yellow | Warning / Caution |
| ⚫ Gray | Inactive / Neutral |

---

## Troubleshooting

### No data showing?
1. Check if `data/trade_journal.json` exists
2. Ensure trades have been generated
3. Check browser console for errors
4. Verify API endpoint: `curl http://localhost:5000/api/dashboard`

### Trades not updating?
1. Refresh page (Ctrl+R or Cmd+R)
2. Check scanner is running
3. Look for JavaScript errors in console
4. Verify data fetcher has internet access

### Settings not saving?
1. Check browser console for errors
2. Verify settings.json is writable
3. Check API response: `POST /api/settings`
4. Look for Flask errors in terminal

### Charts not showing?
1. Verify data exists in trade history
2. Check if Chart.js loaded (see page source)
3. Ensure at least 2 trades exist
4. Check browser console for errors

### Port 5000 already in use?
```bash
# Find process
lsof -i :5000

# Kill it
kill -9 <PID>

# Or use different port
python src/api.py --port 8000
```

---

## Browser Tips

### Refresh Auto-reload
Trades and dashboard auto-refresh every 30-60 seconds. To disable:
1. Open DevTools (F12)
2. Go to Console
3. Paste: `clearInterval(dashboardRefreshInterval)`

### Export Data
1. Right-click table
2. Select "Inspect" or similar
3. Copy table data
4. Paste to Excel/Google Sheets

### Mobile View
Responsive design works on:
- iPad (landscape recommended)
- Large smartphones (landscape)
- Tablets

---

## Performance Optimization

### For Large Trade Histories (1000+ trades)
1. Go to **Settings**
2. Increase **Logging Level** to WARNING
3. Reduce chart update frequency
4. Archive old trades to separate file

### For Slow Internet
1. Reduce auto-refresh frequency
2. Disable chart animations
3. Use browser caching
4. Compress static assets

---

## Advanced Usage

### Monitor via API Only
```bash
# Get dashboard data every 5 seconds
while true; do
  curl -s http://localhost:5000/api/dashboard | jq '.open_trades'
  sleep 5
done
```

### Set Up Mobile Alerts
Use IFTTT or similar to trigger alerts based on API data:
```bash
# Check P&L and send SMS if > ₹10,000
curl http://localhost:5000/api/dashboard | \
  jq 'if .total_pnl > 10000 then "Send SMS" else empty end'
```

### Webhook Integration
Forward signals to external systems:
```python
# In src/api.py, add:
@app.route('/webhook/signal', methods=['POST'])
def signal_webhook():
    signal = request.json
    # Process signal
    # Send to external system
    return jsonify({'status': 'received'})
```

---

## Keyboard Navigation

Tab through interface:
- `Tab` - Next element
- `Shift+Tab` - Previous element
- `Enter` - Activate button/link
- `Space` - Toggle checkbox
- `Arrow keys` - Table navigation

---

## Support

**Need help?**
1. Check `UI_SETUP_GUIDE.md` for detailed setup
2. Review API endpoints in `src/api.py`
3. Check browser console for errors
4. See Flask terminal for backend errors

**Report issues:**
- Save browser console output
- Note exact steps to reproduce
- Include error messages
- Share relevant settings

---

**Happy Trading! 🚀**
