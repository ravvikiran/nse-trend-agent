"""Deduplication and alert throttling for the NSE Momentum Scanner.

Manages alert state to prevent duplicate/excessive Telegram notifications.
Tracks per-symbol alert history and enforces cooldown periods and daily limits.

State is persisted to SQLite so cooldowns survive process restarts
(e.g., Railway dyno recycles).
"""

import logging
import sqlite3
from datetime import datetime, date
from pathlib import Path
from typing import Dict, Optional

from src.momentum.models import AlertState, ScannerConfig, SetupType

logger = logging.getLogger(__name__)

# Default database path for alert state persistence
DEFAULT_DB_PATH = "data/momentum_scanner.db"


class Deduplicator:
    """Manages alert throttling and deduplication with SQLite persistence.

    Maintains per-symbol alert state to track which stocks have been alerted,
    when, and with what setup type. Enforces:
    - Cooldown period between alerts for the same stock + same setup type
    - Maximum daily alert limit across all symbols
    - Resend logic for changed conditions (new breakout, volume expansion, setup type)

    State is persisted to SQLite and loaded on startup, so cooldowns survive
    process restarts.
    """

    def __init__(self, config: ScannerConfig, db_path: str = DEFAULT_DB_PATH):
        """Initialize Deduplicator with scanner configuration and persistence.

        Args:
            config: ScannerConfig containing cooldown_period_seconds and max_alerts_per_day.
            db_path: Path to SQLite database for state persistence.
        """
        self.cooldown_seconds: int = config.cooldown_period_seconds
        self.max_daily_alerts: int = config.max_alerts_per_day
        self._db_path = db_path
        self._state: Dict[str, AlertState] = {}
        self._total_alerts_today: int = 0
        self._current_date: Optional[date] = None

        # Initialize database and load persisted state
        self._init_db()
        self._load_state()

    @property
    def total_alerts_today(self) -> int:
        """Total number of alerts sent today across all symbols."""
        return self._total_alerts_today

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        if self._db_path != ":memory:":
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self) -> None:
        """Create the alert_state table if it doesn't exist."""
        conn = self._get_connection()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS alert_state (
                    symbol TEXT PRIMARY KEY,
                    last_alert_time TEXT NOT NULL,
                    last_setup_type TEXT NOT NULL,
                    last_rank_score REAL NOT NULL,
                    alert_count_today INTEGER NOT NULL DEFAULT 0,
                    alert_date TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
            """)
            conn.commit()
        except sqlite3.Error as e:
            logger.error("Failed to initialize deduplicator database: %s", e)
        finally:
            conn.close()

    def _load_state(self) -> None:
        """Load persisted alert state from SQLite.

        Only loads state from today's date. Older state is ignored
        (effectively a daily reset).
        """
        today = date.today()
        self._current_date = None  # Will be set on first should_alert call
        today_str = today.isoformat()

        conn = self._get_connection()
        try:
            rows = conn.execute(
                "SELECT symbol, last_alert_time, last_setup_type, last_rank_score, "
                "alert_count_today FROM alert_state WHERE alert_date = ?",
                (today_str,),
            ).fetchall()

            self._state.clear()
            self._total_alerts_today = 0

            for row in rows:
                try:
                    state = AlertState(
                        symbol=row["symbol"],
                        last_alert_time=datetime.fromisoformat(row["last_alert_time"]),
                        last_setup_type=SetupType(row["last_setup_type"]),
                        last_rank_score=row["last_rank_score"],
                        alert_count_today=row["alert_count_today"],
                    )
                    self._state[state.symbol] = state
                    self._total_alerts_today += state.alert_count_today
                except (ValueError, KeyError) as e:
                    logger.debug("Skipping invalid alert state row: %s", e)

            if self._state:
                logger.info(
                    "Loaded %d alert states from database (total alerts today: %d)",
                    len(self._state),
                    self._total_alerts_today,
                )
        except sqlite3.Error as e:
            logger.error("Failed to load alert state: %s", e)
        finally:
            conn.close()

    def _persist_state(self, symbol: str, state: AlertState) -> None:
        """Persist a single symbol's alert state to SQLite.

        Args:
            symbol: Stock symbol.
            state: AlertState to persist.
        """
        conn = self._get_connection()
        try:
            today_str = date.today().isoformat()
            conn.execute(
                """INSERT OR REPLACE INTO alert_state
                   (symbol, last_alert_time, last_setup_type, last_rank_score,
                    alert_count_today, alert_date, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, datetime('now'))""",
                (
                    symbol,
                    state.last_alert_time.isoformat(),
                    state.last_setup_type.value,
                    state.last_rank_score,
                    state.alert_count_today,
                    today_str,
                ),
            )
            conn.commit()
        except sqlite3.Error as e:
            logger.error("Failed to persist alert state for %s: %s", symbol, e)
        finally:
            conn.close()

    def _check_day_rollover(self, current_time: datetime) -> None:
        """Check if the day has changed and reset state if needed.

        Uses the date from the provided timestamp (not system clock) to
        support testing with arbitrary dates.

        Args:
            current_time: Current timestamp for date comparison.
        """
        today = current_time.date()
        if self._current_date is None:
            # First call — initialize the date
            self._current_date = today
        elif self._current_date != today:
            logger.info("Day rollover detected. Resetting alert state.")
            self.reset_daily()
            self._current_date = today

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
        # Check for day rollover
        self._check_day_rollover(current_time)

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

        Updates the internal state cache and persists to SQLite.

        Args:
            symbol: Stock symbol that was alerted.
            setup_type: The setup type of the alert.
            rank_score: The rank score of the signal.
            current_time: Timestamp when the alert was sent.
        """
        state = self._state.get(symbol)
        if state is None:
            state = AlertState(
                symbol=symbol,
                last_alert_time=current_time,
                last_setup_type=setup_type,
                last_rank_score=rank_score,
                alert_count_today=1,
            )
            self._state[symbol] = state
        else:
            state.last_alert_time = current_time
            state.last_setup_type = setup_type
            state.last_rank_score = rank_score
            state.alert_count_today += 1

        self._total_alerts_today += 1

        # Persist to SQLite
        self._persist_state(symbol, state)

        logger.debug(
            "Alert recorded for %s: setup=%s, score=%.1f, total_today=%d",
            symbol,
            setup_type.value,
            rank_score,
            self._total_alerts_today,
        )

    def reset_daily(self) -> None:
        """Reset all alert state at 09:15 IST each trading day.

        Clears the per-symbol state cache, resets the daily alert counter,
        and cleans up old state from the database.
        """
        count = len(self._state)
        self._state.clear()
        self._total_alerts_today = 0

        # Clean up old state from database (keep only last 7 days for debugging)
        conn = self._get_connection()
        try:
            conn.execute(
                "DELETE FROM alert_state WHERE alert_date < date('now', '-7 days')"
            )
            conn.commit()
        except sqlite3.Error as e:
            logger.error("Failed to clean old alert state: %s", e)
        finally:
            conn.close()

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
