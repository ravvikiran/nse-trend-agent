"""Centralized timezone definitions for the NSE Momentum Scanner.

All modules should import IST from here instead of defining their own.
"""

from datetime import timedelta, timezone

# Indian Standard Time (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))
