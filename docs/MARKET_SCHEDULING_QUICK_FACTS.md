# Market Scheduling - Quick Facts

## ⏰ Market Hours

| Period | Time (IST) | Status |
|--------|-----------|--------|
| Pre-market | 9:00 - 9:15 AM | ❌ Skipped |
| **Trading** | **9:15 AM - 3:30 PM** | ✅ **Active** |
| Post-market | 3:30 PM+ | ❌ Skipped |

## 📅 Working Days

- ✅ Monday - Friday
- ❌ Saturday - Sunday
- ❌ NSE Holidays (19 major holidays)

## 🔄 Scan Schedule

```
Every 15 minutes
├─ IF weekday AND
├─ IF 9:15 AM - 3:30 PM AND
├─ IF NOT holiday
└─ THEN scan runs ✓
```

## 🏆 Key Functions

| Function | Purpose | Returns |
|----------|---------|---------|
| `is_market_open()` | Is market open now? | bool |
| `_is_market_working_day()` | Is date a working day? | bool |
| `_is_nse_holiday()` | Is date a holiday? | bool |
| `get_time_until_market_open()` | Seconds to next open | float |
| `get_next_market_open_day()` | Next working day | date |

## 📍 NSE Holidays

### Quick List
```
Jan 26    Republic Day
Mar 8     Maha Shivaratri
Mar 25    Holi
Mar 29    Good Friday
Apr 11    Eid ul-Fitr
Apr 17    Ram Navami
Apr 21    Mahavir Jayanti
May 23    Buddha Purnima
Jun 17    Eid ul-Adha
Jul 17    Muharram
Aug 15    Independence Day
Aug 26    Janmashtami
Sep 16    Milad un-Nabi
Oct 2     Gandhi Jayanti
Oct 12    Dussehra
Oct 31-Nov 1  Diwali (2 days)
Nov 15    Guru Nanak Jayanti
Dec 25    Christmas
```

## ✅ What Works

```
Monday 10:30 AM     ✅ Scan runs
Thursday 2:00 PM    ✅ Scan runs
Tuesday 15:00 IST   ✅ Scan runs (exactly at close)

Saturday 10:30 AM   ❌ Scan skipped
Monday after Diwali ✅ Scan runs (Diwali was yesterday)
Oct 31 (Diwali)     ❌ Scan skipped
Tuesday 9:10 AM     ❌ Scan skipped (before 9:15)
Tuesday 4:00 PM     ❌ Scan skipped (after 3:30 PM)
```

## 🛠️ Configuration

**No changes needed!** Holidays are automatic.

```json
{
  "scheduler": {
    "timezone": "Asia/Kolkata",     // ← IST
    "run_days": [1,2,3,4,5],        // ← Mon-Fri
    "scan_interval_minutes": 15
  }
}
```

## 📝 Logs

```
✅ Scan runs
INFO: Scan started at 10:30 AM
DEBUG: Market is open - scanning...

❌ Scan skipped (weekend)
DEBUG: 2024-01-13 is weekend (weekday=5)
DEBUG: Skipping: Market not open

❌ Scan skipped (holiday)
DEBUG: 2024-10-31 is an NSE holiday
DEBUG: Skipping: Market not open

❌ Scan skipped (after hours)
DEBUG: 16:45:30 outside market hours (09:15:00-15:30:00)
DEBUG: Skipping: Market not open
```

## 🧪 Quick Test

```python
from src.scheduler.market_scheduler import MarketScheduler
from datetime import date

ms = MarketScheduler()

# Test 1: Is market open now?
print(ms.is_market_open())  # True/False

# Test 2: Is Oct 31 a holiday?
print(ms._is_nse_holiday(date(2024, 10, 31)))  # True

# Test 3: Is Tuesday a working day?
print(ms._is_market_working_day(date(2024, 1, 16)))  # True

# Test 4: Seconds to market open?
print(ms.get_time_until_market_open())  # float (seconds)

# Test 5: Next working day?
print(ms.get_next_market_open_day())  # date object
```

## 💾 Status Check

```python
from src.scheduler.scanner_scheduler import ScannerScheduler

config = {
    'scheduler': {'timezone': 'Asia/Kolkata'},
    'signal_mode': {'daily_signal_hour': 15}
}

scheduler = ScannerScheduler(config)
print(scheduler.get_status())

# Output:
# {
#   'running': True,
#   'next_signal_run': datetime(...),
#   'continuous_interval': '15 min',
#   'signal_time': '15:00 IST',
#   'market_hours': '09:15-15:30 IST',
#   'run_days': 'Mon-Fri (weekdays only)',
#   'excludes': 'NSE market holidays',
#   'max_signals_per_day': 3,
#   'timezone': 'Asia/Kolkata'
# }
```

## 📊 Weekly Schedule

```
MONDAY
09:15 - Scan 1 ✓
09:30 - Scan 2 ✓
...
15:30 - Final scan ✓
(96 scans today if nothing skipped)

FRIDAY
09:15 - Scan 1 ✓
... (96 scans)
15:30 - Final scan ✓

SATURDAY
(All scans skipped - no alerts)

DIWALI (Oct 31)
(All scans skipped - holiday)

NEXT DAY (Nov 1)
09:15 - Scan 1 ✓ (Back to normal)
```

## 🚀 Quick Start

1. **No setup needed** - holidays already configured
2. **No changes required** - existing code works as-is
3. **Automatic filtering** - weekends and holidays skipped
4. **Transparent logging** - see why scans are skipped
5. **Full timezone support** - IST (Asia/Kolkata)

## 📖 Full Documentation

For complete details: Read **MARKET_SCHEDULING_GUIDE.md**

---

**Status**: ✅ Live  
**Timezone**: IST (Asia/Kolkata)  
**Holidays**: 19 major NSE holidays  
**Update**: April 18, 2026
