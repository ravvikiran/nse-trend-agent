# NSE Trend Scanner - Web UI Setup Guide

## Overview

The NSE Trend Scanner now includes a modern, web-based dashboard for monitoring trades, viewing performance analytics, and managing scanner settings.

**Features:**
- 📊 Real-time dashboard with key metrics
- 💼 Open trades tracking with live P&L
- 📈 Performance analytics with charts
- 🔍 Market analysis and sentiment
- ⚙️ Settings and configuration management
- 📱 Responsive design (desktop & mobile)

---

## Installation

### Step 1: Install Dependencies

```bash
# Navigate to project directory
cd /Users/ravikiran/Documents/nse-trend-agent

# Activate virtual environment
source .venv/bin/activate

# Install/update requirements with Flask
pip install -r requirements.txt
```

### Step 2: Verify Installation

```bash
# Check Flask is installed
python -c "import flask; print(f'Flask {flask.__version__} installed')"
```

---

## Running the UI

### Option 1: Standalone UI Server

Run the Flask UI server independently:

```bash
cd /Users/ravikiran/Documents/nse-trend-agent

# Activate environment
source .venv/bin/activate

# Run the API server
python src/api.py
```

The dashboard will be available at: **http://localhost:5000** or **http://localhost:5050**

### Option 2: Integrated with Scanner

To run the UI alongside the scanner:

```bash
# In terminal 1 - Run the scanner
source .venv/bin/activate
python src/main.py

# In terminal 2 - Run the UI
source .venv/bin/activate
python src/api.py
```

### Option 3: Production Deployment

For production (Railway, Heroku, etc.):

```bash
# Using Gunicorn (more stable than Flask dev server)
pip install gunicorn

# Run with Gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 src.api:app
```

---

## Dashboard Pages

### 1. **Dashboard** (`/`)
- Overview of key metrics
- Market status and hours
- Open trades at a glance
- Win rate and P&L summary
- Charts: Win/Loss distribution, P&L curve
- Quick links to other pages

**Key Widgets:**
- Open Trades Counter
- Win Rate %
- Total Trades
- Total P&L (with color coding)
- Scanner Status
- Today's Performance

### 2. **Trades** (`/trades`)
- **Open Trades Tab**: Active positions with live updates
  - Symbol, Strategy, Entry, Current, SL, Targets
  - Unrealized P&L in ₹ and %
  - Distance to SL/Targets
  - Days held

- **History Tab**: Complete trade history with filters
  - Filter by Strategy (TREND, VERC, MTF, SWING)
  - Filter by Outcome (WIN, LOSS)
  - Filter by Timeframe (7, 30, 90, 365 days)
  - Click trade for detailed view

### 3. **Performance** (`/performance`)
- Performance summary with key metrics
- Win rate, Profit Factor, Avg RR
- Gross Profit/Loss breakdown
- Cumulative P&L curve chart
- Win vs Loss distribution
- Performance by strategy table
- Click strategy to view details

### 4. **Analysis** (`/analysis`)
- Market sentiment analysis
  - NIFTY trend (Bullish/Bearish)
  - Market strength meter
  - Volatility level
- Sector leaders performance
- Signals generated over time
- Top performing stocks by win rate
- Historical signal data

### 5. **Settings** (`/settings`)
- **General Settings**
  - Scanner name, scan interval
  - Default quantity per trade
  - Risk per trade percentage
  - Weekend skip toggle

- **Strategy Settings**
  - Adjust weights for each strategy
  - Configure strategy parameters
  - Position management (SL%, T1%, T2%)

- **API Keys**
  - Telegram Bot Token & Chat ID
  - OpenAI, Groq API keys
  - Secure storage (not saved in plain text)

- **Alert Preferences**
  - Telegram/Email alerts
  - Minimum confidence score
  - Alert sound settings

- **Advanced Settings**
  - Max open trades limit
  - Trade timeout period
  - Auto-optimization toggle
  - AI learning toggle
  - Logging level

- **Danger Zone**
  - Reset to defaults
  - Clear trade history

---

## API Endpoints

The Flask API exposes the following endpoints:

### Dashboard
```
GET /api/dashboard          - Overall dashboard metrics
GET /api/market-status      - Current market status & hours
```

### Trades
```
GET /api/trades/open        - All open trades with current prices
GET /api/trades/history     - Historical trades (with filters)
GET /api/trades/<trade_id>  - Detailed trade information
```

### Performance
```
GET /api/performance/summary        - Overall performance metrics
GET /api/performance/by-strategy    - Performance breakdown by strategy
GET /api/performance/pnl-curve      - Cumulative P&L data
```

### Market Analysis
```
GET /api/analysis/market-sentiment      - Market sentiment analysis
GET /api/analysis/signals-generated     - Signals generated (by day)
```

### Settings & Control
```
GET /api/settings           - Get current settings
POST /api/settings          - Update settings
GET /api/scanner/status     - Scanner status
POST /api/scanner/start     - Start scanner
POST /api/scanner/stop      - Stop scanner
```

---

## Configuration

### Update Settings via UI

1. Go to **Settings** page
2. Configure desired values in each section
3. Click **Save** button for each section
4. Settings are saved to `config/settings.json`

### Update Settings via API

```bash
# Example: Update strategy weights
curl -X POST http://localhost:5000/api/settings \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_weights": {
      "TREND": 40,
      "VERC": 20,
      "MTF": 25,
      "SWING": 15
    }
  }'
```

---

## Integration with Existing Scanner

The UI layer communicates with your existing scanner through:

1. **Trade Journal** - Reads from `data/trade_journal.json`
2. **Signal Tracker** - Uses `history_manager` to track signals
3. **Performance Tracker** - Calculates metrics from trade data
4. **Market Data** - Fetches via `DataFetcher` (Yahoo Finance)

### Key Integration Points

To make the UI work with your scanner, update `src/main.py`:

```python
from api import init_api, app
from flask import Flask

# After initializing your components:
trade_journal = create_trade_journal()
data_fetcher = DataFetcher()
market_scheduler = MarketScheduler()
performance_tracker = create_performance_tracker()
history_manager = create_history_manager()

# Initialize the API
init_api(
    trade_journal_inst=trade_journal,
    data_fetcher_inst=data_fetcher,
    market_scheduler_inst=market_scheduler,
    performance_tracker_inst=performance_tracker,
    history_manager_inst=history_manager
)

# Run both scanner and UI
if __name__ == '__main__':
    # Start scanner in background
    scanner_thread = threading.Thread(target=run_scanner_loop, daemon=True)
    scanner_thread.start()
    
    # Start Flask UI
    app.run(debug=False, host='0.0.0.0', port=5000)
```

---

## Real-time Updates

The dashboard updates automatically:
- **Dashboard**: Every 30 seconds
- **Open Trades**: Every 60 seconds
- **Performance**: Every 60 seconds
- **Market Sentiment**: Every 5 minutes

Customize refresh intervals in the JavaScript files:
- `static/js/dashboard.js` - Line 21
- `static/js/trades.js` - Line 7
- `static/js/performance.js` - Line 16

---

## Browser Compatibility

- Chrome/Edge 90+
- Firefox 88+
- Safari 14+
- Mobile browsers (iOS Safari, Chrome Android)

Recommended: **Latest Chrome or Edge** for best performance

---

## Troubleshooting

### Port Already in Use
```bash
# Find process using port 5000
lsof -i :5000

# Kill the process
kill -9 <PID>

# Or use a different port
python src/api.py --port 8000
```

### CORS Errors
The API includes CORS headers. If still getting errors:
- Check browser console for specific errors
- Ensure Flask-CORS is installed: `pip install flask-cors`

### Charts Not Displaying
- Check browser console for JavaScript errors
- Ensure Chart.js loaded: `https://cdn.jsdelivr.net/npm/chart.js@4.4.0`
- Check API response: `curl http://localhost:5000/api/performance/pnl-curve`

### No Data Showing
- Verify `data/trade_journal.json` has data
- Check API responses with curl
- Look at Flask console for errors
- Enable debug logging in settings

---

## Performance Tips

1. **Limit History Display**: Only load necessary trades in tables
2. **Cache Settings**: Cache API responses client-side (5-10 minutes)
3. **Lazy Load Charts**: Load charts only when tab is visible
4. **Compress Images**: Use optimized static assets
5. **Database**: Consider SQLite for larger datasets

---

## Customization

### Change Theme Colors
Edit `static/css/dashboard.css`:
```css
:root {
    --primary: #0d6efd;      /* Blue */
    --success: #198754;       /* Green */
    --danger: #dc3545;        /* Red */
    /* ... */
}
```

### Add Custom Charts
1. Add canvas element to HTML template
2. Create Chart.js instance in JavaScript
3. Populate with data from API

### Add New Settings
1. Add form field in `templates/settings.html`
2. Add save function in `static/js/settings.js`
3. Update API endpoint in `src/api.py`
4. Save to `config/settings.json`

---

## Security Notes

⚠️ **Important for Production:**

1. **Hide API Keys**: Never display full API keys in frontend
2. **Use HTTPS**: Always use HTTPS in production
3. **Authentication**: Add login/password protection
4. **Rate Limiting**: Implement rate limits on API
5. **CSRF Protection**: Add CSRF tokens to forms

Example (add to `src/api.py`):
```python
@app.before_request
def check_auth():
    # Add authentication logic
    pass
```

---

## Deployment

### Railway.app (Free Tier)
1. Connect GitHub repo
2. Set environment: Python
3. Update `Procfile`:
   ```
   web: gunicorn -w 1 -b 0.0.0.0:$PORT src.api:app
   ```
4. Push to GitHub - Railway deploys automatically

### Heroku
```bash
# Create app
heroku create your-app-name

# Push code
git push heroku main

# Scale dyno
heroku ps:scale web=1
```

### Docker
Create `Dockerfile`:
```dockerfile
FROM python:3.11
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["gunicorn", "-w", "1", "-b", "0.0.0.0:5000", "src.api:app"]
```

Run:
```bash
docker build -t nse-scanner .
docker run -p 5000:5000 nse-scanner
```

---

## Support & Debugging

### Enable Debug Mode
```python
# In src/api.py
app.run(debug=True, host='0.0.0.0', port=5000)
```

### Check Logs
```bash
# Flask logs show in console
# Also check: logs/scanner.log
tail -f logs/scanner.log
```

### Test API Endpoints
```bash
# Dashboard
curl http://localhost:5000/api/dashboard | python -m json.tool

# Open trades
curl http://localhost:5000/api/trades/open | python -m json.tool

# Performance
curl http://localhost:5000/api/performance/summary | python -m json.tool
```

---

## Next Steps

1. ✅ Install Flask dependencies
2. ✅ Run the UI: `python src/api.py`
3. ✅ Open http://localhost:5000 in browser
4. ✅ Configure settings as needed
5. ✅ Start scanner: `python src/main.py` (in different terminal)
6. ✅ View trades and performance data

---

**Enjoy your new trading dashboard! 🚀**
