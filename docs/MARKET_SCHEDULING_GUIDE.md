# NSE Trend Agent - Market Scheduling & Working Days Guide

## Overview

The application now properly respects **NSE market working days and hours**. It will:

✅ **Run only on weekdays** (Monday to Friday)  
✅ **Respect NSE market holidays** (automatically excluded)  
✅ **Run only within market hours** (9:15 AM - 3:30 PM IST)  
✅ **Skip pre-market and post-market** scanning  
✅ **Handle timezone properly** (IST - Asia/Kolkata)  

---

## Market Hours & Working Days

### Official Market Timings

| Period | Time (IST) | Scanner Activity |
|--------|-----------|------------------|
| Pre-market | 9:00 - 9:15 AM | ❌ Skipped (high noise) |
| **Market Open** | **9:15 AM - 3:30 PM** | ✅ **Active Scanning** |
| Post-market | 3:30 PM onwards | ❌ Skipped |

### Working Days

| Day | Scanning |
|-----|----------|
| Monday - Friday | ✅ Active (if not holiday) |
| Saturday - Sunday | ❌ Closed |
| NSE Holidays | ❌ Closed |

---

## NSE Market Holidays (2024-2026)

The application automatically excludes these NSE holidays:

### 2024
- January 26: Republic Day
- March 8: Maha Shivaratri
- March 25: Holi
- March 29: Good Friday
- April 11: Eid ul-Fitr
- April 17: Ram Navami
- April 21: Mahavir Jayanti
- May 23: Buddha Purnima
- June 17: Eid ul-Adha
- July 17: Muharram
- August 15: Independence Day
- August 26: Janmashtami
- September 16: Milad un-Nabi
- October 2: Gandhi Jayanti
- October 12: Dussehra
- October 31 - November 1: Diwali (2 days)
- November 15: Guru Nanak Jayanti
- December 25: Christmas

---

## Configuration

### settings.json - Scheduler Configuration

```json
{
  "scheduler": {
    "timezone": "Asia/Kolkata",
    "run_days": [1, 2, 3, 4, 5],
    "scan_interval_minutes": 15
  },
  "signal_mode": {
    "daily_signal_hour": 15,
    "max_signals_per_day": 3
  }
}
```

**Field Explanations**:
- `timezone`: IST timezone (don't change)
- `run_days`: Weekday indices (0=Monday, 1=Tuesday, ..., 4=Friday) - already configured
- `scan_interval_minutes`: Scan frequency (default 15 minutes)
- `daily_signal_hour`: Time for daily signal generation (15 = 3:00 PM)
- `max_signals_per_day`: Maximum signals allowed per day

### Do Not Edit

⚠️ **Do not manually change `run_days`** - it's already set to `[1,2,3,4,5]` (Mon-Fri)  
⚠️ **Holidays are automatic** - don't need manual configuration

---

## How It Works

### Scan Cycle - Every 15 Minutes (9:15 AM - 3:30 PM IST)

```
9:15 AM ├─ Run scan
        ├─ Check: Is today a working day? ✓
        ├─ Check: Is current time 9:15-15:30? ✓
        ├─ Check: Is it a holiday? ✗ No
        └─ SCAN EXECUTES ✓

During Weekend (Saturday):
        ├─ Run scan (cron trigger)
        ├─ Check: Is today a working day? ✗ No (weekend)
        └─ SCAN SKIPPED ✓

During Holiday (Diwali):
        ├─ Run scan (cron trigger)
        ├─ Check: Is today a working day? ✗ No (holiday)
        └─ SCAN SKIPPED ✓

After Market Close (4:00 PM):
        ├─ Run scan (cron trigger)
        ├─ Check: Is current time 9:15-15:30? ✗ No (4:00 PM)
        └─ SCAN SKIPPED ✓
```

### Key Functions

#### 1. `MarketScheduler.is_market_open()`

Comprehensive check that returns `True` only if:
- Today is a weekday (Mon-Fri)
- Today is NOT an NSE holiday
- Current time is between 9:15 AM - 3:30 PM IST

```python
from src.scheduler.market_scheduler import MarketScheduler

scheduler = MarketScheduler()

# During 10:30 AM on Tuesday (working day)
scheduler.is_market_open()  # Returns: True

# During 4:00 PM on Tuesday
scheduler.is_market_open()  # Returns: False (after hours)

# During 10:00 AM on Diwali
scheduler.is_market_open()  # Returns: False (holiday)

# During 10:00 AM on Saturday
scheduler.is_market_open()  # Returns: False (weekend)
```

#### 2. `MarketScheduler._is_market_working_day()`

Checks if a date is a working day:

```python
from datetime import date

# Monday that's not a holiday
scheduler._is_market_working_day(date(2024, 1, 8))  # True

# Saturday
scheduler._is_market_working_day(date(2024, 1, 13))  # False

# Diwali holiday
scheduler._is_market_working_day(date(2024, 10, 31))  # False
```

#### 3. `MarketScheduler._is_nse_holiday()`

Checks if a specific date is an NSE holiday:

```python
# Diwali
scheduler._is_nse_holiday(date(2024, 10, 31))  # True

# Regular Tuesday
scheduler._is_nse_holiday(date(2024, 1, 16))  # False
```

#### 4. `MarketScheduler.get_time_until_market_open()`

Returns seconds until market opens (skips holidays):

```python
# Saturday evening - returns seconds until Monday 9:15 AM
scheduler.get_time_until_market_open()  # Returns: ~48 hours in seconds

# Sunday - returns seconds until Monday 9:15 AM
scheduler.get_time_until_market_open()  # Returns: ~24 hours in seconds

# Diwali - returns seconds until next working day 9:15 AM
scheduler.get_time_until_market_open()  # Returns: appropriate hours

# Tuesday 8:00 AM - returns seconds until 9:15 AM today
scheduler.get_time_until_market_open()  # Returns: ~1.25 hours in seconds
```

---

## Practical Examples

### Example 1: Regular Tuesday 10:30 AM

```
Scan executes at 10:30 AM
├─ Is Tuesday a working day? ✓ Yes (not weekend, not holiday)
├─ Is 10:30 AM within 9:15-15:30? ✓ Yes
└─ RESULT: Scan runs normally
```

### Example 2: Friday after Diwali

```
Scan executes at 10:30 AM on Friday (day after Diwali)
├─ Is Friday a working day? ✓ Yes (Friday is weekday)
├─ Is Friday a holiday? ✗ No (Diwali was yesterday)
├─ Is 10:30 AM within 9:15-15:30? ✓ Yes
└─ RESULT: Scan runs normally
```

### Example 3: Saturday Morning

```
Scan triggered at 10:30 AM on Saturday
├─ Is Saturday a working day? ✗ No (weekend)
├─ Weekday check failed
└─ RESULT: Scan skipped (no alert, no processing)
```

### Example 4: Diwali Holiday

```
Scan triggered at 10:30 AM on Diwali (October 31, 2024)
├─ Is October 31 a working day? ✗ No
├─ Holiday check: October 31 = Diwali ✓ Confirmed holiday
├─ Market working day check failed
└─ RESULT: Scan skipped
```

### Example 5: Tuesday 3:45 PM (After Market Close)

```
Scan triggered at 3:45 PM on Tuesday
├─ Is Tuesday a working day? ✓ Yes
├─ Is 3:45 PM within 9:15-15:30? ✗ No (market closed at 15:30)
├─ Time check failed
└─ RESULT: Scan skipped (no alerts after market close)
```

### Example 6: Tuesday 9:10 AM (Before Market Open)

```
Scan triggered at 9:10 AM on Tuesday
├─ Is Tuesday a working day? ✓ Yes
├─ Is 9:10 AM within 9:15-15:30? ✗ No (market opens at 9:15)
├─ Time check failed
└─ RESULT: Scan skipped (no pre-market scanning)
```

---

## Scheduler Status

### Checking Current Schedule

```python
from src.scheduler.scanner_scheduler import ScannerScheduler

config = {
    'scheduler': {
        'timezone': 'Asia/Kolkata',
        'run_days': [1, 2, 3, 4, 5],
        'scan_interval_minutes': 15
    },
    'signal_mode': {
        'daily_signal_hour': 15,
        'max_signals_per_day': 3
    }
}

scheduler = ScannerScheduler(config)
status = scheduler.get_status()

print(status)
# Output:
# {
#   'running': True,
#   'next_signal_run': datetime(...),  # Next 3 PM signal
#   'continuous_interval': '15 min',   # Every 15 minutes
#   'signal_time': '15:00 IST',        # 3:00 PM
#   'market_hours': '09:15-15:30 IST', # Market hours
#   'run_days': 'Mon-Fri (weekdays only)',
#   'excludes': 'NSE market holidays',
#   'max_signals_per_day': 3,
#   'timezone': 'Asia/Kolkata'
# }
```

---

## Monitoring & Logs

### Log Messages

The application logs the scheduling decisions:

#### ✅ When Scan Runs

```
INFO: Scan started at 10:30 AM
DEBUG: Market is open - scanning...
INFO: Generated 5 signals
INFO: Sent 3 alerts to Telegram
```

#### ❌ When Scan is Skipped

**Weekend**:
```
DEBUG: 2024-01-13 is weekend (weekday=5)
DEBUG: Skipping continuous_monitor: Market not open (holiday/weekend)
```

**Holiday**:
```
DEBUG: 2024-10-31 is an NSE holiday
DEBUG: Skipping continuous_monitor: Market not open (holiday/weekend)
```

**After Hours**:
```
DEBUG: 16:45:30 outside market hours (09:15:00-15:30:00)
DEBUG: Skipping continuous_monitor: Market not open (holiday/weekend)
```

### Check Current Status

```bash
# View logs
tail -f logs/nse_trend_agent.log | grep "market"

# Check if scanner is running
ps aux | grep "nse-trend-agent"

# View scheduler next run
python -c "
from src.scheduler.scanner_scheduler import ScannerScheduler
config = {'scheduler': {'timezone': 'Asia/Kolkata'}, 'signal_mode': {'daily_signal_hour': 15}}
scheduler = ScannerScheduler(config)
print(scheduler.get_status())
"
```

---

## Adding or Removing Holidays

### To Add a New Holiday (2025+)

Edit `src/market_scheduler.py`:

```python
NSE_HOLIDAYS_DATES = [
    # ... existing holidays ...
    (12, 25),  # Christmas
    (12, 26),  # NEW: Day after Christmas 2025 (if added)
]
```

### Format

```python
NSE_HOLIDAYS_DATES = [
    (month, day),  # Format: (1-12, 1-31)
    (1, 26),       # Example: January 26 (Republic Day)
    (3, 25),       # Example: March 25 (Holi)
    (10, 31),      # Example: October 31 (Diwali)
]
```

### To Modify Holiday List

1. Open: `src/market_scheduler.py`
2. Find: `NSE_HOLIDAYS_DATES = [`
3. Add/Remove dates as (month, day) tuples
4. Restart the application
5. Changes take effect immediately

---

## Testing Market Scheduling

### Manual Test 1: Check Current Market Status

```python
from src.scheduler.market_scheduler import MarketScheduler
from datetime import datetime

ms = MarketScheduler()

print(f"Is market open now? {ms.is_market_open()}")
print(f"Time until market open: {ms.get_time_until_market_open()}")
print(f"Next working day: {ms.get_next_market_open_day()}")
print(f"Current session: {ms.get_session_name()}")
```

### Manual Test 2: Test With Specific Date

```python
from datetime import date

ms = MarketScheduler()

# Test various dates
test_dates = [
    date(2024, 1, 15),  # Regular Monday
    date(2024, 1, 13),  # Saturday
    date(2024, 1, 26),  # Republic Day holiday
    date(2024, 10, 31), # Diwali
]

for test_date in test_dates:
    is_working = ms._is_market_working_day(test_date)
    is_holiday = ms._is_nse_holiday(test_date)
    print(f"{test_date}: Working day={is_working}, Holiday={is_holiday}")
```

### Manual Test 3: Check Scheduler

```python
from src.scheduler.scanner_scheduler import ScannerScheduler
import json

config = {
    'scheduler': {'timezone': 'Asia/Kolkata', 'run_days': [1,2,3,4,5], 'scan_interval_minutes': 15},
    'signal_mode': {'daily_signal_hour': 15, 'max_signals_per_day': 3}
}

scheduler = ScannerScheduler(config)
status = scheduler.get_status()
print(json.dumps(status, indent=2, default=str))
```

---

## Troubleshooting

### Problem: Scans Running on Weekends

**Cause**: Scheduler configuration issue or holiday not recognized

**Solution**:
```python
# Check market status
from src.scheduler.market_scheduler import MarketScheduler
ms = MarketScheduler()

# Should return False on weekends
print(ms.is_market_open())  # False if working correctly
```

### Problem: Scans Stopped Working After Holiday

**Cause**: Holiday date format incorrect or timezone issue

**Solution**:
```python
# Verify holiday detection
from datetime import date
ms = MarketScheduler()

# Check specific holiday
is_holiday = ms._is_nse_holiday(date(2024, 10, 31))
print(f"Is Oct 31 a holiday? {is_holiday}")  # Should be True
```

### Problem: Scans Running Before 9:15 AM

**Cause**: Timezone or time check not working

**Solution**:
```python
from src.scheduler.market_scheduler import MarketScheduler
ms = MarketScheduler()

# Check current market status
print(f"Current time: {datetime.now(ms.ist)}")
print(f"Is market open? {ms.is_market_open()}")
```

---

## Summary

| Feature | Status | Details |
|---------|--------|---------|
| Market Hours | ✅ Implemented | 9:15 AM - 3:30 PM IST |
| Working Days | ✅ Implemented | Mon-Fri only |
| NSE Holidays | ✅ Implemented | 19 major holidays auto-excluded |
| Timezone | ✅ Implemented | Asia/Kolkata (IST) |
| Skip Pre-Market | ✅ Implemented | No scanning before 9:15 AM |
| Skip Post-Market | ✅ Implemented | No scanning after 3:30 PM |
| Weekends | ✅ Implemented | No Saturday/Sunday scanning |
| Holiday Add/Remove | ✅ Easy | Edit `NSE_HOLIDAYS_DATES` list |

---

**Version**: 1.0  
**Last Updated**: April 18, 2026  
**For Questions**: Review the examples above or check logs for debugging
