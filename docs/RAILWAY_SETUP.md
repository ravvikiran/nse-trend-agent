# Railway Deployment Guide

This guide explains how to deploy the NSE Trend Scanner Agent to Railway.

## Prerequisites

- Railway account (railway.app)
- GitHub repository with this code
- Telegram Bot Token and Chat IDs

## Step 1: Connect Railway to GitHub

1. Go to [railway.app](https://railway.app)
2. Click "New Project"
3. Select "Deploy from GitHub"
4. Connect your GitHub account and select this repository

## Step 2: Configure Environment Variables

Railway will automatically read the `Procfile` to determine how to run your app. 

**Add these environment variables in the Railway dashboard:**

```
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_personal_chat_id
TELEGRAM_CHANNEL_CHAT_ID=your_channel_chat_id_or_leave_empty

# Optional: Specify stocks as JSON (comma-separated or JSON array)
# Example: ["RELIANCE", "TCS", "HDFCBANK", "INFY"]
STOCKS_LIST=["RELIANCE","TCS","HDFCBANK","INFY","ICICIBANK","SBIN","BHARTIARTL","LT","BAJFINANCE","HINDUNILVR"]

# Logging level
LOG_LEVEL=INFO
```

### How to Get Telegram IDs

1. **Bot Token**:
   - Create a bot with @BotFather on Telegram
   - Copy the token provided

2. **Chat ID** (your personal ID):
   - Message your bot
   - Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
   - Copy the `chat.id` from the response
   - Or use a Telegram ID finder bot

3. **Channel Chat ID** (optional):
   - Add your bot to the channel as admin
   - Send a message
   - Use the API endpoint above to find the channel ID
   - Format: `-100xxxxxxxxxx`

## Step 3: Deploy

1. Push your code to GitHub
2. Railway will automatically detect changes and deploy
3. View logs in the Railway dashboard to verify the deployment

## What Works on Railway

✅ **Full Stack Operations:**
- Real-time stock scanning (every 15 min)
- Telegram alert delivery
- Scheduled market scans (3 PM IST Mon-Fri)
- APScheduler job execution
- Multi-strategy analysis (TREND + VERC)

✅ **Configuration:**
- Environment variables for Telegram credentials
- Stock list from `STOCKS_LIST` env var
- Dynamic fallback to defaults if missing

✅ **Logging:**
- All logs output to stdout
- Visible in Railway dashboard logs
- No file-based logging (ephemeral filesystem)

## What Doesn't Persist

⚠️ **Important Limitations:**
- Signal memory files (`data/smart_dedup.json`) - lost on restart
- Trade journal entries (JSON files) - lost on restart
- Performance tracking data - lost on restart
- Config changes - lost on restart

**For Production:** Migrate to a database (PostgreSQL recommended on Railway)

## Monitoring & Troubleshooting

### View Logs
```
Railway Dashboard > Your Project > Logs
```

### Common Issues

**Issue**: "No module named 'config/settings.json'"
- **Solution**: Settings will be loaded from environment variables automatically

**Issue**: Stocks not being scanned
- **Solution**: Ensure `STOCKS_LIST` environment variable is set correctly as JSON

**Issue**: Telegram alerts not sending
- **Solution**: Verify `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in Railway dashboard

**Issue**: App crashes on startup
- **Solution**: Check Railway logs for the specific error message

## Viewing Logs in Railway

```
# Real-time logs
Railway Dashboard > Logs tab (auto-refreshes)

# Search for errors
Filter for "ERROR" or "WARNING" in the logs panel
```

## Stopping/Restarting

- **Pause deployment**: Railway dashboard > Pause
- **Redeploy**: Push to GitHub, Railway auto-deploys
- **Manual restart**: Railway dashboard > Restart

## Database Integration (Optional - Future)

For persistent signal memory and trade journal:

1. Add Railway PostgreSQL plugin
2. Update the code to use SQLAlchemy instead of JSON files
3. Store trades, signals, and performance metrics in DB

This would require code changes - contact support if needed.

## Pricing

Railway offers:
- **$5/month** free tier
- Includes enough resources for this app
- Auto-scales with usage

## Support

For Railway-specific issues:
- Check [Railway Docs](https://docs.railway.app)
- Visit [Railway Discord Community](https://discord.gg/railway)

For app-specific issues:
- Check logs in Railway dashboard
- Verify environment variables are set correctly
- Ensure Telegram credentials are valid
