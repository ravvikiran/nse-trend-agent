# QuantGridIndia — NSE Momentum Scanner

"""
QuantGridIndia — Deterministic rule-based momentum scanning for NSE stocks.

Scans ~500 NSE stocks every 2 minutes during market hours using a three-stage
filtering pipeline (1H trend → relative strength → 15m entry triggers) and
delivers structured Telegram alerts for the top 5 momentum stocks.
"""

__version__ = "4.0.0"
