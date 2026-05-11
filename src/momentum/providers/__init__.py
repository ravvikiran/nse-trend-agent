"""Data provider implementations for the NSE Momentum Scanner."""

from src.momentum.providers.mock_provider import MockDataProvider

# KiteDataProvider uses lazy import for kiteconnect dependency.
# Import is safe even if kiteconnect is not installed.
from src.momentum.providers.kite_provider import KiteDataProvider

# DhanDataProvider uses lazy import for dhanhq dependency.
# Import is safe even if dhanhq is not installed.
from src.momentum.providers.dhan_provider import DhanDataProvider

__all__ = ["MockDataProvider", "KiteDataProvider", "DhanDataProvider"]
