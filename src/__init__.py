# NSE Trend Scanner Agent

"""
NSE Trend Scanner Agent - Automated trading scanner for NSE stocks.

Monitors ~500 NSE stocks during market hours and detects potential 
uptrend starts based on EMA alignment and volume confirmation.
"""

__version__ = "1.0.0"
__author__ = "NSE Trend Scanner"

from src.data_fetcher import DataFetcher
from src.indicator_engine import IndicatorEngine
from src.trend_detector import TrendDetector, TrendSignal
from src.alert_service import AlertService, MockAlertService
from src.scheduler import MarketScheduler

__all__ = [
    'DataFetcher',
    'IndicatorEngine', 
    'TrendDetector',
    'TrendSignal',
    'AlertService',
    'MockAlertService',
    'MarketScheduler'
]
