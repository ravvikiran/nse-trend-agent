"""Deduplication and alert throttling for the NSE Momentum Scanner.

Manages alert state to prevent duplicate/excessive Telegram notifications.
Tracks per-symbol alert history and enforces cooldown periods and daily limits.
"""

import logging
from datetime import datetime
from typing import Dict, Optional

from src.momentum.models import AlertState, ScannerConfig, SetupType

logger = logging.getLogger(__name__)


class Deduplicator:
    """Manages alert throttling and deduplication.

    Maintains an in-memory dict of symbol → AlertState to track which stocks
    have been alerted, when, and with what setup type. Enforces:
    - Cooldown period between alerts for the same stock + same setup type
    - Maximum daily alert limit across all symbols
    - Resend logic for changed conditions (new breakout, volume expansion, setup type)
    """

    def __init__(self, config: ScannerConfig):
        """Initialize Deduplicator with scanner configuration.

        Args:
            config: ScannerConfig containing cooldown_period_seconds and max_alerts_per_day.
        """
        self.cooldown_seconds: int = config.cooldown_period_seconds
        self.max_daily_alerts: int = config.max_alerts_per_day
        self._state: Dict[str, AlertState] = {}
        self._total_alerts_today: int = 0

    @property
    def total_alerts_today(self) -> int:
        """Total number of alerts sent today across all symbols."""
        return self._total_alerts_today

    def should_alert(
        self,
        symbol: str,
        setup_type: SetupType,
        rank_score: float,
        current_time: datetime,
    ) -> bool:
        """Check if an alert should be sent for this symbol.

        Returns False if:
        - Same symbol + same setup_type + within cooldown period
        - Daily alert count >= max_alerts_per_day

        Returns True otherwise (new symbol, different setup type, or cooldown expired).

        Args:
            symbol: Stock symbol (e.g., 'RELIANCE').
            setup_type: The detected setup type for this signal.
            rank_score: The final rank score for this signal.
            current_time: Current timestamp for cooldown comparison.

        Returns:
            True if the alert should be sent, False if it should be suppressed.
        """
        # Check daily limit
        if self._total_alerts_today >= self.max_daily_alerts:
            logger.debug(
                "Alert suppressed for %s: daily limit reached (%d/%d)",
                symbol,
                self._total_alerts_today,
                self.max_daily_alerts,
            )
            return False

        # Check if symbol has been alerted before
        state = self._state.get(symbol)
        if state is None:
            # Never alerted this symbol today — allow
            return True

        # Check if same setup type and within cooldown
        if state.last_setup_type == setup_type:
            elapsed = (current_time - state.last_alert_time).total_seconds()
            if elapsed < self.cooldown_seconds:
                logger.debug(
                    "Alert suppressed for %s: same setup type '%s' within cooldown "
                    "(%.0fs elapsed, %ds required)",
                    symbol,
                    setup_type.value,
                    elapsed,
                    self.cooldown_seconds,
                )
                return False

        # Different setup type or cooldown expired — allow
        return True

    def should_resend(
        self,
        symbol: str,
        setup_type: SetupType,
        has_new_breakout: bool,
        has_new_volume_expansion: bool,
    ) -> bool:
        """Check if a previously alerted stock should receive a new alert.

        Returns True if:
        - setup_type changed from last alert for this symbol
        - has_new_breakout is True (new breakout detected since last alert)
        - has_new_volume_expansion is True (new volume spike)

        Returns False otherwise (still in cooldown with same conditions).

        Args:
            symbol: Stock symbol.
            setup_type: Current setup type detected.
            has_new_breakout: Whether a new breakout has been detected since last alert.
            has_new_volume_expansion: Whether a new volume expansion event occurred.

        Returns:
            True if the alert should be resent, False otherwise.
        """
        state = self._state.get(symbol)
        if state is None:
            # Never alerted — not a "resend" scenario, but allow
            return True

        # Check if setup type changed
        if state.last_setup_type != setup_type:
            logger.debug(
                "Resend allowed for %s: setup type changed from '%s' to '%s'",
                symbol,
                state.last_setup_type.value,
                setup_type.value,
            )
            return True

        # Check for new breakout
        if has_new_breakout:
            logger.debug(
                "Resend allowed for %s: new breakout detected",
                symbol,
            )
            return True

        # Check for new volume expansion
        if has_new_volume_expansion:
            logger.debug(
                "Resend allowed for %s: new volume expansion detected",
                symbol,
            )
            return True

        # No changed conditions — suppress
        return False

    def record_alert(
        self,
        symbol: str,
        setup_type: SetupType,
        rank_score: float,
        current_time: datetime,
    ) -> None:
        """Record that an alert was sent for a symbol.

        Updates the internal state cache with the alert details and increments
        the daily alert counter.

        Args:
            symbol: Stock symbol that was alerted.
            setup_type: The setup type of the alert.
            rank_score: The rank score of the signal.
            current_time: Timestamp when the alert was sent.
        """
        state = self._state.get(symbol)
        if state is None:
            self._state[symbol] = AlertState(
                symbol=symbol,
                last_alert_time=current_time,
                last_setup_type=setup_type,
                last_rank_score=rank_score,
                alert_count_today=1,
            )
        else:
            state.last_alert_time = current_time
            state.last_setup_type = setup_type
            state.last_rank_score = rank_score
            state.alert_count_today += 1

        self._total_alerts_today += 1
        logger.debug(
            "Alert recorded for %s: setup=%s, score=%.1f, total_today=%d",
            symbol,
            setup_type.value,
            rank_score,
            self._total_alerts_today,
        )

    def reset_daily(self) -> None:
        """Reset all alert state at 09:15 IST each trading day.

        Clears the per-symbol state cache and resets the daily alert counter.
        Called at the start of each trading day.
        """
        count = len(self._state)
        self._state.clear()
        self._total_alerts_today = 0
        logger.info(
            "Daily alert state reset: cleared %d symbol states",
            count,
        )

    def get_state(self, symbol: str) -> Optional[AlertState]:
        """Get the current alert state for a symbol.

        Args:
            symbol: Stock symbol to look up.

        Returns:
            AlertState if the symbol has been alerted today, None otherwise.
        """
        return self._state.get(symbol)
