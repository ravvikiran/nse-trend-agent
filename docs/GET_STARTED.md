# NSE Trend Scanner - UI Implementation Complete! 🎉

## What You Have Now

A **complete, production-ready web dashboard** for managing your NSE Trend Scanner trading bot. You can now:

✅ Monitor open trades in real-time  
✅ View performance analytics with charts  
✅ Analyze market sentiment and signals  
✅ Configure all scanner settings from UI  
✅ Track P&L and win rates  
✅ Access from any browser, any device  

---

## Get Started in 30 Seconds

### 1️⃣ Install Flask (One-time)
```bash
cd /Users/ravikiran/Documents/nse-trend-agent
source .venv/bin/activate
pip install -r requirements.txt
```

### 2️⃣ Start the Dashboard
```bash
python src/api.py
```

### 3️⃣ Open Your Browser
```
http://localhost:5000
```

**That's it!** Your dashboard is now live. 🚀

---

## Dashboard at a Glance

When you open `http://localhost:5000`, you'll see:

### Dashboard Home Page
```
┌─────────────────────────────────────────────┐
│  NSE Trend Scanner - Dashboard              │
├─────────────────────────────────────────────┤
│                                              │
│  Market Status: OPEN (5h 20m to close)      │
│                                              │
│  Open Trades: 5      Win Rate: 67.5%        │
│  Total Trades: 160   Total P&L: ₹45,230     │
│                                              │
│  [Recent Trades Table with 5 latest]        │
│                                              │
│  [Win/Loss Chart]    [P&L Curve Chart]      │
│                                              │
│  [Start] [Stop] buttons in top right        │
│                                              │
└─────────────────────────────────────────────┘
```

### Navigation Tabs
- 📊 **Dashboard** - Main overview (current page)
- 💼 **Trades** - Open positions & history
- 📈 **Performance** - Analytics & metrics
- 🔍 **Analysis** - Market sentiment
- ⚙️ **Settings** - Configuration

---

## Key Pages & Features

### 📊 Dashboard Page
- Market status with countdown
- Key metrics: Open trades, win rate, total P&L
- Quick scanner control (Start/Stop)
- Recent trades overview
- Auto-updating charts
- Updates every 30 seconds

### 💼 Trades Page
**Two tabs:**

1. **Open Trades** - All active positions
   - Symbol, Strategy, Entry, Current Price
   - Stop Loss, Targets, Unrealized P&L
   - Distance to SL, Days Held
   - Live updates every minute

2. **Trade History** - Complete journal
   - Filter by Strategy, Outcome, Time period
   - Click trade for detailed modal
   - See all trade metrics & performance

### 📈 Performance Page
- Win rate, Profit Factor, Average RR
- Gross Profit/Loss, Max Drawdown
- Charts: Strategy performance, P&L curve, Win/Loss
- Performance breakdown table
- Strategy-wise analysis

### 🔍 Analysis Page
- Market sentiment: NIFTY trend, strength
- Sector leaders chart
- Signals generated over time
- Top performing stocks
- Real-time market analysis

### ⚙️ Settings Page
Five configuration sections:
1. **General** - Scan interval, risk, quantity
2. **Strategies** - Weights, parameters, position mgmt
3. **API Keys** - Telegram, OpenAI, Groq credentials
4. **Alerts** - Telegram/Email, confidence, sounds
5. **Advanced** - Trade limits, optimization, learning

Plus **Danger Zone** to reset or clear data.

---

## Live Data Sources

The dashboard pulls data from:

| Data | Source | Updates |
|------|--------|---------|
| Open Trades | `data/trade_journal.json` | Real-time |
| Win Rate | Calculated from trades | Every 30s |
| Market Status | Your `MarketScheduler` | Every 30s |
| Stock Prices | Yahoo Finance API | Every 60s |
| Settings | `config/settings.json` | On update |
| P&L Curve | Trade history | Every 60s |

**No changes needed to your existing scanner!**

---

## Running Both Scanner & Dashboard

### Method 1: Two Separate Terminals

**Terminal 1 - Scanner:**
```bash
cd /Users/ravikiran/Documents/nse-trend-agent
source .venv/bin/activate
python src/main.py
```

**Terminal 2 - Dashboard:**
```bash
cd /Users/ravikiran/Documents/nse-trend-agent
source .venv/bin/activate
python src/api.py
```

Then open http://localhost:5000

### Method 2: Using Launcher Script

**macOS/Linux:**
```bash
bash run_ui.sh          # UI only
bash run_ui.sh both     # Scanner + UI
```

**Windows:**
```bash
run_ui.bat              # UI only
```

---

## What Each Dashboard Widget Shows

### Top Row Metrics
| Widget | Shows | Updates |
|--------|-------|---------|
| **Open Trades** | Number of active positions | Every 30s |
| **Win Rate** | % of trades that are wins | Every 30s |
| **Total Trades** | Total trades ever made | Every 30s |
| **Total P&L** | Total profit/loss in ₹ | Every 30s |

### Market Status Card
- Current time (IST)
- Market OPEN/CLOSED
- Market hours (09:15 - 15:30)
- Countdown to market close

### Recent Trades Table
- Last 5 open positions
- Entry price vs current price
- Stop loss and targets
- Unrealized profit/loss (₹ and %)

### Charts
- **Win/Loss Pie**: Shows ratio of wins to losses
- **P&L Curve**: Shows cumulative profit over time

---

## Using the Trades Page

### Open Trades Tab
1. Shows all your active positions
2. Automatically updates every 60 seconds
3. Shows P&L in real money (₹) and %
4. Green numbers = profit, Red = loss
5. Click any trade for full details modal

**Columns:**
- Symbol - Stock name
- Strategy - TREND/VERC/MTF/SWING
- Entry - Entry price
- Current - Current stock price
- SL - Stop loss price
- Target - Target prices (T1/T2/T3)
- P&L - Unrealized profit/loss
- P&L % - Percentage gain/loss
- Distance to SL - How far from stop loss
- Days Held - How many days trade is open

### Trade History Tab
1. Shows all closed trades
2. Apply filters:
   - **Strategy**: TREND, VERC, MTF, SWING
   - **Outcome**: WIN or LOSS
   - **Days**: Last 7, 30, 90, or 365 days
3. Click "Apply Filter" to search
4. Click any row to see trade details
5. Includes: RR ratio, profit, quality rating

---

## Performance Analytics

### Summary Section (Top)
- **Total Trades**: How many trades total
- **Win Rate**: % of winning trades
- **Profit Factor**: Ratio of profit to loss
- **Avg RR**: Average Risk:Reward ratio
- **Total P&L**: Total profit/loss in ₹
- **Gross Profit**: Total money made
- **Gross Loss**: Total money lost
- **Max Drawdown**: Worst losing streak

### Charts
1. **Strategy Performance**: Which strategy is best?
2. **P&L Curve**: How profits/losses grow over time
3. **Win/Loss**: How many wins vs losses?

### Strategy Table
Shows each strategy separately:
- How many trades
- Wins/Losses count
- Win rate %
- Average Risk:Reward

---

## Settings Configuration

### General Settings
- **Scanner Name**: What to call it
- **Scan Interval**: How often to check (minutes)
- **Default Qty**: Quantity per trade
- **Risk %**: Risk percentage
- **Skip Weekends**: Whether to trade weekends

### Strategy Settings
- Adjust how much each strategy is used (weights)
- Set parameters for TREND strategy
- Set stop loss and target percentages
- **Example:**
  - TREND: 40% weight
  - VERC: 20% weight
  - MTF: 25% weight
  - SWING: 15% weight

### API Keys
- Telegram Bot token (for alerts)
- Telegram Chat ID (where alerts go)
- OpenAI key (for AI analysis)
- Groq key (for AI analysis)

**Note:** Keys are never shown in plain text after saving.

### Alert Settings
- Turn Telegram alerts on/off
- Turn Email alerts on/off (when implemented)
- Minimum confidence score (0-100%)
- Alert sound: None, Bell, or Chime

### Advanced Settings
- **Max Open Trades**: Limit concurrent positions
- **Trade Timeout**: Days before trade expires
- **Auto-Optimize**: Auto-adjust weights based on performance
- **AI Learning**: Use AI to improve strategy
- **Log Level**: DEBUG/INFO/WARNING/ERROR

---

## API Endpoints (For Developers)

If you want to integrate with other tools:

```bash
# Get dashboard data
curl http://localhost:5000/api/dashboard

# Get open trades
curl http://localhost:5000/api/trades/open

# Get performance summary
curl http://localhost:5000/api/performance/summary

# Get all settings
curl http://localhost:5000/api/settings

# Update settings
curl -X POST http://localhost:5000/api/settings \
  -H "Content-Type: application/json" \
  -d '{"scan_interval": 20}'
```

Full API documentation in code comments and `UI_SETUP_GUIDE.md`.

---

## Charts & Visualizations

### Win/Loss Distribution (Pie Chart)
Shows percentage of trades that won vs lost.
- Green slice = Wins
- Red slice = Losses
- Hover to see exact numbers

### Cumulative P&L Curve (Line Chart)
Shows how profits grow over time.
- X-axis = Time/Date
- Y-axis = Cumulative profit (₹)
- Green line = Profits growing
- Dips = Losing periods

### Strategy Performance (Bar Chart)
Shows win rate for each strategy.
- X-axis = Win rate %
- Y-axis = Strategy name
- Higher bars = Better strategies

---

## Real-time Updates

Dashboard auto-refreshes:
- **Every 30 seconds**: Dashboard, market status
- **Every 60 seconds**: Open trades, performance
- **Every 5 minutes**: Market analysis

All updates happen in background - **no page refresh needed!**

To manually refresh: Press `Ctrl+R` (Windows) or `Cmd+R` (Mac)

---

## Color Coding Guide

| Color | Meaning |
|-------|---------|
| 🟢 **Green** | Profit, Win, Success |
| 🔴 **Red** | Loss, Alert, Negative |
| 🔵 **Blue** | Information, Primary action |
| 🟡 **Yellow** | Warning, Caution |
| ⚫ **Gray** | Inactive, Neutral |

---

## Keyboard Shortcuts (Future)

Coming soon:
- `/` - Quick search
- `?` - Help
- `d` - Go to Dashboard
- `t` - Go to Trades
- etc.

---

## Mobile Usage

The dashboard works on mobile:
- 📱 Smartphones (portrait & landscape)
- 📱 Tablets
- 💻 All desktop browsers

**Best experience on tablet in landscape mode.**

---

## Troubleshooting Quick Fixes

### Port 5000 Already in Use
```bash
# Use different port
python src/api.py --port 8000

# Then visit http://localhost:8000
```

### No Trades Showing
1. Check that `data/trade_journal.json` exists
2. Run scanner to generate trades
3. Refresh page (Ctrl+R)
4. Check browser console (F12 → Console tab)

### Charts Not Displaying
1. Refresh page
2. Check browser console for errors
3. Ensure trade data exists
4. Wait a minute and refresh again

### Settings Not Saving
1. Check `config/settings.json` is writable
2. Look for errors in browser console
3. Check Flask terminal output
4. Ensure JSON is valid format

---

## Performance Tips

1. **Dashboard is slow?**
   - Reduce auto-refresh interval
   - Close unnecessary browser tabs
   - Check internet connection

2. **Lots of trades?**
   - Filter history by date range
   - Archive old trade journal
   - Use different database

3. **Charts not loading?**
   - Ensure at least 2 trades exist
   - Check browser memory usage
   - Try different browser

---

## File Locations

Important files:
```
config/settings.json         ← Your settings (editable)
data/trade_journal.json      ← All trade data (auto-created)
src/api.py                   ← Flask API server
templates/                   ← HTML pages
static/js/                   ← JavaScript logic
static/css/                  ← Styling
```

---

## Next Steps

1. ✅ **Install**: `pip install -r requirements.txt`
2. ✅ **Run Dashboard**: `python src/api.py`
3. ✅ **Open Browser**: http://localhost:5000
4. ✅ **Generate Test Data**: Run scanner
5. ✅ **Configure Settings**: Adjust parameters
6. ✅ **Monitor Trades**: Watch real-time updates
7. ✅ **Deploy to Production** (optional)

---

## Additional Resources

📖 **Detailed Guides:**
- `UI_SETUP_GUIDE.md` - Complete setup instructions
- `UI_QUICK_REFERENCE.md` - Feature reference
- Code comments in `src/api.py`

📹 **API Documentation:**
- See API endpoints in `src/api.py`
- Test with `curl` commands

🛠️ **Customization:**
- Edit CSS: `static/css/dashboard.css`
- Edit HTML: `templates/*.html`
- Edit JS: `static/js/*.js`

---

## What's Included

✅ **5 Full Pages**: Dashboard, Trades, Performance, Analysis, Settings
✅ **12 API Endpoints**: Complete REST API
✅ **5 JavaScript Modules**: Full frontend logic
✅ **Professional CSS**: Modern styling with Bootstrap
✅ **Real-time Charts**: Chart.js integration
✅ **Responsive Design**: Works on all devices
✅ **Complete Documentation**: Setup guides & references
✅ **Launcher Scripts**: Easy start on macOS/Linux/Windows
✅ **Production Ready**: Can deploy immediately

---

## Starting the Dashboard

**The simplest way:**

```bash
cd /Users/ravikiran/Documents/nse-trend-agent
source .venv/bin/activate
python src/api.py
```

Then open: **http://localhost:5000**

That's it! You're ready to go. 🚀

---

## Support

For issues:
1. Check `UI_SETUP_GUIDE.md` - Most answers are there
2. Check Flask output - Backend errors show in terminal
3. Check browser console (F12 → Console) - Frontend errors
4. Verify trade_journal.json has data
5. Test API directly with curl

---

**🎉 Congratulations! Your NSE Trend Scanner now has a professional web dashboard!**

**Everything is ready to use. Just run `python src/api.py` and open http://localhost:5000**

Enjoy monitoring your trades in real-time! 📊💹
