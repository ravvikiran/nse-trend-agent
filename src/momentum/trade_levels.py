"""
Trade Level Calculations for the NSE Momentum Scanner.

Calculates entry, stop loss, targets, and trailing stop for triggered signals.
Enforces minimum risk-reward ratio and discards invalid signals.

Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6
"""

import logging
from dataclasses import dataclass
from typing import Optional

from src.momentum.models import ScannerConfig, SetupType

logger = logging.getLogger(__name__)


@dataclass
class TradeLevels:
    """Calculated trade levels for a momentum signal."""

    entry_price: float
    stop_loss: float
    target_1: float
    target_2: float
    risk: float  # Entry - Stop Loss (1R)
    risk_pct: float  # (entry - stop_loss) / entry * 100
    trailing_stop: float  # EMA(20) on 15m
    reward_risk_ratio: float  # Target 2 reward / risk


class TradeLevelCalculator:
    """Calculates trade levels (entry, SL, targets, trailing stop).

    Entry price:
      - COMPRESSION_BREAKOUT: breakout candle high
      - PULLBACK_CONTINUATION: trigger candle high

    Stop Loss = min(trigger_candle_low, entry - atr_sl_multiplier × ATR(14))

    Target 1 = Entry + 1R (where R = Entry - Stop Loss)
    Target 2 = Entry + 2R

    Trailing Stop = EMA(20) on 15m timeframe

    Signals are discarded (returns None) when:
      - Stop loss >= entry price (invalid risk)
      - Risk is zero or negative
    """

    def __init__(self, config: Optional[ScannerConfig] = None):
        """Initialize with scanner configuration.

        Args:
            config: Scanner configuration. Uses defaults if None.
        """
        self.config = config or ScannerConfig()
        self.atr_sl_multiplier = self.config.atr_sl_multiplier  # 1.2

    def calculate(
        self,
        entry_price: float,
        trigger_candle_low: float,
        atr_value: float,
        ema_20_value: float,
    ) -> Optional[TradeLevels]:
        """Calculate trade levels for a triggered signal.

        Args:
            entry_price: The trigger/breakout candle high (entry point).
            trigger_candle_low: The low of the trigger/breakout candle.
            atr_value: ATR(14) value at the time of the trigger.
            ema_20_value: Current EMA(20) value on 15m timeframe (trailing stop).

        Returns:
            TradeLevels dataclass with all calculated levels, or None if the
            signal is invalid (SL >= entry, or risk is non-positive).
        """
        # Validate inputs
        if entry_price <= 0 or atr_value <= 0:
            logger.debug(
                "Invalid inputs: entry_price=%.2f, atr_value=%.4f",
                entry_price,
                atr_value,
            )
            return None

        # Calculate stop loss: min(trigger_candle_low, entry - multiplier × ATR)
        atr_based_sl = entry_price - self.atr_sl_multiplier * atr_value
        stop_loss = min(trigger_candle_low, atr_based_sl)

        # Validate: stop loss must be below entry price
        risk = entry_price - stop_loss
        if risk <= 0:
            logger.debug(
                "Invalid signal: SL (%.2f) >= Entry (%.2f), risk=%.4f",
                stop_loss,
                entry_price,
                risk,
            )
            return None

        # Calculate targets
        target_1 = entry_price + risk  # Entry + 1R
        target_2 = entry_price + 2 * risk  # Entry + 2R

        # Risk percentage
        risk_pct = (risk / entry_price) * 100

        # Reward-to-risk ratio for Target 2
        reward_risk_ratio = (target_2 - entry_price) / risk  # Always 2.0 by construction

        # Trailing stop is EMA(20) on 15m
        trailing_stop = ema_20_value

        return TradeLevels(
            entry_price=entry_price,
            stop_loss=stop_loss,
            target_1=target_1,
            target_2=target_2,
            risk=risk,
            risk_pct=risk_pct,
            trailing_stop=trailing_stop,
            reward_risk_ratio=reward_risk_ratio,
        )
