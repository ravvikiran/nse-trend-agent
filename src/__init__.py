# NSE Trend Scanner Agent

"""
NSE Trend Scanner Agent - Automated trading scanner for NSE stocks.

Monitors ~500 NSE stocks during market hours and detects potential 
uptrend starts based on EMA alignment and volume confirmation.
"""

__version__ = "2.0.0"
__author__ = "NSE Trend Scanner"

__all__ = [
    'DataFetcher',
    'IndicatorEngine', 
    'TrendDetector',
    'TrendSignal',
    'AlertService',
    'MockAlertService',
]
