# Railway Deployment - Implementation Checklist

## ✅ What's Already Done (Railway Compatible)

- ✅ `Procfile` updated to use `python src/main.py --schedule`
- ✅ Logging configured to use stdout only on Railway
- ✅ Config loading uses environment variables as fallback
- ✅ Main settings load gracefully from environment if file missing
- ✅ Stock list loads from `STOCKS_LIST` environment variable
- ✅ Exception handling catches file I/O errors

## 🚀 Quick Start on Railway

### 1. Set Environment Variables

In Railway dashboard, set:

```env
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id
STOCKS_LIST=["RELIANCE","TCS","HDFCBANK","INFY","ICICIBANK"]
```

### 2. Deploy

Railway will automatically:
1. Install dependencies from `requirements.txt`
2. Run the app using the `Procfile`
3. Start scanning at 3 PM IST daily (Mon-Fri)
4. Send Telegram alerts

### 3. Monitor

Watch logs in Railway dashboard:
```
Railway > Your Project > Logs
```

## ⚠️ Data Persistence (Important!)

### What Gets Lost on Every Restart

- Signal memory (deduplication cache)
- Trade journal entries
- Performance metrics
- Historical analysis data

### Current Behavior

The app will:
- ✅ Start fresh after each restart
- ✅ Continue scanning normally
- ✅ Send alerts on new signals
- ⚠️ Not remember previous trades

### Acceptable For

- **Development/Testing**: Perfect - clean slate each time
- **Small-scale alerts**: Fine - just sends alerts, doesn't need history
- **Paper trading**: Manageable - logs are still sent to Telegram

### Not Suitable For

- **Production trading**: Needs persistent trade journal
- **Performance tracking**: Needs historical data
- **Advanced analytics**: Requires historical signal analysis

## 📦 For Production (Future Enhancement)

To make fully production-ready with persistent data:

### Option 1: Railway PostgreSQL (Recommended)

```bash
# In Railway dashboard:
# 1. Add PostgreSQL plugin
# 2. Get connection details
# 3. Add env var: DATABASE_URL

# Then run migration script to create schema
python src/migrations/init_db.py
```

**Benefits:**
- Fully persistent data
- Scales automatically
- Backups included
- ~$15/month with Railway

### Option 2: External Database

Connect to any PostgreSQL, MySQL, or MongoDB:
```env
DATABASE_URL=postgresql://user:pass@host:port/db
```

### Option 3: File Storage with Volume

Deploy a Railway Volume:
```yaml
volumes:
  - data
```

Then data persists (but still limited to ~10GB free tier).

## 🔧 Current Railway Implementation

### How It Works

1. **On Startup**:
   - Checks for `config/settings.json` (won't exist on Railway)
   - Falls back to environment variables
   - Initializes with defaults if both missing

2. **During Execution**:
   - Scans stocks every 15 minutes
   - Logs to stdout (Railway captures)
   - Sends alerts via Telegram
   - Writes files to `/tmp` (ephemeral, lost on restart)

3. **On Restart**:
   - All state is lost (unless using database)
   - App initializes fresh
   - Continues scanning normally

### Environment Variable Configuration

```env
# Required
TELEGRAM_BOT_TOKEN=xxx
TELEGRAM_CHAT_ID=123

# Optional
TELEGRAM_CHANNEL_CHAT_ID=456
STOCKS_LIST=["RELIANCE","TCS"]
LOG_LEVEL=INFO
```

## 🧪 Testing Before Production

### Local Test
```bash
source venv/bin/activate
export TELEGRAM_BOT_TOKEN=test_token
export TELEGRAM_CHAT_ID=test_chat
export STOCKS_LIST='["RELIANCE"]'
python src/main.py --schedule
```

### Railway Staging
1. Create separate Railway project for staging
2. Deploy code
3. Set same env vars
4. Monitor for 24 hours
5. Check logs for errors
6. Verify Telegram alerts work

## 📊 Monitoring Strategy

### In Railway Dashboard
- **Logs**: Check for ERROR or WARNING
- **CPU/Memory**: Should be <100MB RAM, <5% CPU idle
- **Network**: Minimal bandwidth usage

### Custom Monitoring (via Telegram)
The app sends alerts when:
- ✅ Scan starts
- ✅ Signals detected
- ✅ Alerts sent
- ⚠️ Errors occur

## 🎯 Next Steps

### Immediately (This Week)
1. Set up Railway account
2. Connect GitHub
3. Configure env variables
4. Deploy and test
5. Monitor first scan

### Soon (Upcoming)
1. Optimize stock list based on your criteria
2. Fine-tune alert thresholds
3. Add more stocks/strategies

### Later (Production)
1. Add PostgreSQL for persistent storage
2. Create admin dashboard
3. Add advanced analytics
4. Implement paper trading

## ✅ Deployment Checklist

- [ ] Railway account created
- [ ] GitHub connected to Railway
- [ ] `TELEGRAM_BOT_TOKEN` set in Railway
- [ ] `TELEGRAM_CHAT_ID` set in Railway
- [ ] `STOCKS_LIST` set in Railway (optional)
- [ ] Code pushed to GitHub
- [ ] Railway deployment started
- [ ] First scan completed successfully
- [ ] Alert received on Telegram
- [ ] Logs checked for errors

## 🆘 Troubleshooting

### App crashes immediately
```
Check: Railway Logs for Python errors
Fix: Verify all required env variables are set
```

### No alerts received
```
Check: TELEGRAM_BOT_TOKEN is correct
Check: TELEGRAM_CHAT_ID is correct
Check: Check Railway logs for scan execution
```

### Scans not running at 3 PM
```
Check: IST timezone is correct
Check: Verify APScheduler jobs in logs
Fix: Restart deployment manually
```

### Memory/CPU too high
```
Check: Number of stocks being scanned
Fix: Reduce stock list or upgrade Railway plan
```

## 📞 Support

- Railway docs: https://docs.railway.app
- Telegram bot docs: https://core.telegram.org/bots
- Python issues: Check logs and README.md

**You're ready to deploy! 🚀**
