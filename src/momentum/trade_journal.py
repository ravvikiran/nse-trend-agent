"""
Trade Journal: Tracks open positions and monitors SL/target hits.

When a signal is sent to Telegram, it's recorded as an "open trade" in the journal.
On each scan cycle, the journal checks current prices against entry, SL, and targets.
Sends Telegram updates when:
  - Stop loss is hit (trade closed at loss)
  - Target 1 is hit (partial profit)
  - Target 2 is hit (full profit, trade closed)
  - Trailing stop is hit (trade closed at profit)

Stores all trade outcomes in SQLite for performance tracking.
"""

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from src.momentum.models import MomentumSignal

logger = logging.getLogger(__name__)

# IST timezone
IST = timezone(timedelta(hours=5, minutes=30))

# Default database path
DEFAULT_DB_PATH = "data/momentum_scanner.db"

# Max age for open trades (auto-close after 5 trading days)
MAX_TRADE_AGE_DAYS = 5


class TradeStatus(Enum):
    """Status of a trade in the journal."""
    OPEN = "OPEN"
    TARGET_1_HIT = "TARGET_1_HIT"
    TARGET_2_HIT = "TARGET_2_HIT"
    STOP_LOSS_HIT = "STOP_LOSS_HIT"
    TRAILING_STOP_HIT = "TRAILING_STOP_HIT"
    EXPIRED = "EXPIRED"  # Auto-closed after max age


@dataclass
class OpenTrade:
    """An active trade being monitored."""
    id: int
    symbol: str
    setup_type: str
    entry_price: float
    stop_loss: float
    target_1: float
    target_2: float
    trailing_stop: float
    rank_score: float
    entry_time: datetime
    status: TradeStatus
    target_1_hit: bool = False
    highest_price: float = 0.0


class TradeJournal:
    """Tracks open trades and monitors them for SL/target hits.

    Integrates with the scan cycle to check current prices of open trades
    and sends Telegram alerts on status changes.
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH, alert_service=None):
        """Initialize TradeJournal.

        Args:
            db_path: Path to SQLite database.
            alert_service: TelegramService instance for sending updates.
        """
        self._db_path = db_path
        self._alert_service = alert_service
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self) -> None:
        """Create the trade journal table if it doesn't exist."""
        conn = self._get_connection()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS trade_journal (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    setup_type TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    stop_loss REAL NOT NULL,
                    target_1 REAL NOT NULL,
                    target_2 REAL NOT NULL,
                    trailing_stop REAL NOT NULL,
                    rank_score REAL NOT NULL,
                    entry_time TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'OPEN',
                    target_1_hit INTEGER NOT NULL DEFAULT 0,
                    highest_price REAL NOT NULL DEFAULT 0.0,
                    exit_price REAL,
                    exit_time TEXT,
                    pnl_pct REAL,
                    risk_reward_achieved REAL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE INDEX IF NOT EXISTS idx_journal_status
                    ON trade_journal(status);
                CREATE INDEX IF NOT EXISTS idx_journal_symbol
                    ON trade_journal(symbol, status);
            """)
            conn.commit()
        except sqlite3.Error as e:
            logger.error("Failed to initialize trade journal: %s", e)
        finally:
            conn.close()

    def record_signal(self, signal: MomentumSignal) -> None:
        """Record a new signal as an open trade in the journal.

        Called when a signal is sent to Telegram.

        Args:
            signal: The MomentumSignal that was alerted.
        """
        conn = self._get_connection()
        try:
            # Check if this symbol already has an open trade
            existing = conn.execute(
                "SELECT id FROM trade_journal WHERE symbol = ? AND status = 'OPEN'",
                (signal.symbol,)
            ).fetchone()

            if existing:
                logger.debug("Trade already open for %s, skipping journal entry", signal.symbol)
                return

            conn.execute(
                """INSERT INTO trade_journal
                   (symbol, setup_type, entry_price, stop_loss, target_1, target_2,
                    trailing_stop, rank_score, entry_time, status, highest_price)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', ?)""",
                (
                    signal.symbol,
                    signal.setup_type.value,
                    signal.entry_price,
                    signal.stop_loss,
                    signal.target_1,
                    signal.target_2,
                    signal.trailing_stop,
                    signal.rank_score,
                    signal.timestamp.isoformat(),
                    signal.entry_price,
                ),
            )
            conn.commit()
            logger.info("Trade journal: recorded open trade for %s (entry=%.2f)",
                       signal.symbol, signal.entry_price)
        except sqlite3.Error as e:
            logger.error("Failed to record signal in journal: %s", e)
        finally:
            conn.close()

    def get_open_trades(self) -> List[OpenTrade]:
        """Get all currently open trades.

        Returns:
            List of OpenTrade objects.
        """
        conn = self._get_connection()
        try:
            rows = conn.execute(
                """SELECT id, symbol, setup_type, entry_price, stop_loss,
                          target_1, target_2, trailing_stop, rank_score,
                          entry_time, status, target_1_hit, highest_price
                   FROM trade_journal
                   WHERE status = 'OPEN'"""
            ).fetchall()

            trades = []
            for row in rows:
                trades.append(OpenTrade(
                    id=row["id"],
                    symbol=row["symbol"],
                    setup_type=row["setup_type"],
                    entry_price=row["entry_price"],
                    stop_loss=row["stop_loss"],
                    target_1=row["target_1"],
                    target_2=row["target_2"],
                    trailing_stop=row["trailing_stop"],
                    rank_score=row["rank_score"],
                    entry_time=datetime.fromisoformat(row["entry_time"]),
                    status=TradeStatus(row["status"]),
                    target_1_hit=bool(row["target_1_hit"]),
                    highest_price=row["highest_price"],
                ))
            return trades
        except sqlite3.Error as e:
            logger.error("Failed to get open trades: %s", e)
            return []
        finally:
            conn.close()

    def check_open_trades(self, price_data: Dict[str, pd.DataFrame]) -> None:
        """Check all open trades against current prices.

        For each open trade, checks if the current price has hit:
        - Stop loss → close trade, send alert
        - Target 1 → mark T1 hit, send alert, update trailing stop
        - Target 2 → close trade, send alert
        - Trailing stop (after T1 hit) → close trade, send alert

        Args:
            price_data: Dict of symbol -> 15m OHLCV DataFrame with latest prices.
        """
        open_trades = self.get_open_trades()
        if not open_trades:
            return

        now = datetime.now(IST)

        for trade in open_trades:
            # Check if trade has expired (too old)
            trade_age = (now - trade.entry_time.replace(tzinfo=IST)).days
            if trade_age > MAX_TRADE_AGE_DAYS:
                self._close_trade(trade, TradeStatus.EXPIRED, trade.entry_price)
                continue

            # Get current price data for this symbol
            df = price_data.get(trade.symbol)
            if df is None or df.empty:
                continue

            # Get the current (latest) price and the high/low of recent candles
            current_price = float(df["close"].iloc[-1])
            recent_low = float(df["low"].iloc[-1])
            recent_high = float(df["high"].iloc[-1])

            # Update highest price
            if recent_high > trade.highest_price:
                self._update_highest_price(trade.id, recent_high)
                trade.highest_price = recent_high

            # Check stop loss (using candle low)
            if recent_low <= trade.stop_loss:
                self._close_trade(trade, TradeStatus.STOP_LOSS_HIT, trade.stop_loss)
                self._send_trade_update(trade, TradeStatus.STOP_LOSS_HIT, trade.stop_loss)
                continue

            # Check target 2 first (full exit)
            if recent_high >= trade.target_2:
                self._close_trade(trade, TradeStatus.TARGET_2_HIT, trade.target_2)
                self._send_trade_update(trade, TradeStatus.TARGET_2_HIT, trade.target_2)
                continue

            # Check target 1 (partial profit)
            if not trade.target_1_hit and recent_high >= trade.target_1:
                self._mark_target_1_hit(trade.id)
                trade.target_1_hit = True
                self._send_trade_update(trade, TradeStatus.TARGET_1_HIT, trade.target_1)
                # After T1 hit, trailing stop becomes active
                continue

            # Check trailing stop (only after T1 is hit)
            if trade.target_1_hit and trade.trailing_stop > 0:
                # Trailing stop: use entry price as minimum trailing stop
                effective_trailing = max(trade.trailing_stop, trade.entry_price)
                if recent_low <= effective_trailing:
                    self._close_trade(trade, TradeStatus.TRAILING_STOP_HIT, effective_trailing)
                    self._send_trade_update(trade, TradeStatus.TRAILING_STOP_HIT, effective_trailing)
                    continue

    def _close_trade(self, trade: OpenTrade, status: TradeStatus, exit_price: float) -> None:
        """Close a trade with the given status and exit price."""
        conn = self._get_connection()
        try:
            now = datetime.now(IST)
            pnl_pct = ((exit_price - trade.entry_price) / trade.entry_price) * 100
            risk = trade.entry_price - trade.stop_loss
            reward = exit_price - trade.entry_price
            rr_achieved = reward / risk if risk > 0 else 0.0

            conn.execute(
                """UPDATE trade_journal
                   SET status = ?, exit_price = ?, exit_time = ?,
                       pnl_pct = ?, risk_reward_achieved = ?
                   WHERE id = ?""",
                (status.value, exit_price, now.isoformat(), pnl_pct, rr_achieved, trade.id),
            )
            conn.commit()
            logger.info(
                "Trade closed: %s — %s at ₹%.2f (P&L: %.2f%%, R:R: %.2f)",
                trade.symbol, status.value, exit_price, pnl_pct, rr_achieved,
            )
        except sqlite3.Error as e:
            logger.error("Failed to close trade %s: %s", trade.symbol, e)
        finally:
            conn.close()

    def _mark_target_1_hit(self, trade_id: int) -> None:
        """Mark target 1 as hit for a trade."""
        conn = self._get_connection()
        try:
            conn.execute(
                "UPDATE trade_journal SET target_1_hit = 1 WHERE id = ?",
                (trade_id,),
            )
            conn.commit()
        except sqlite3.Error as e:
            logger.error("Failed to mark T1 hit: %s", e)
        finally:
            conn.close()

    def _update_highest_price(self, trade_id: int, price: float) -> None:
        """Update the highest price reached for a trade."""
        conn = self._get_connection()
        try:
            conn.execute(
                "UPDATE trade_journal SET highest_price = ? WHERE id = ?",
                (price, trade_id),
            )
            conn.commit()
        except sqlite3.Error as e:
            logger.error("Failed to update highest price: %s", e)
        finally:
            conn.close()

    def _send_trade_update(self, trade: OpenTrade, status: TradeStatus, price: float) -> None:
        """Send a Telegram alert about a trade status change."""
        if self._alert_service is None:
            return

        pnl_pct = ((price - trade.entry_price) / trade.entry_price) * 100
        risk = trade.entry_price - trade.stop_loss
        reward = price - trade.entry_price
        rr_achieved = reward / risk if risk > 0 else 0.0

        # Format message based on status
        if status == TradeStatus.STOP_LOSS_HIT:
            emoji = "🔴"
            title = "STOP LOSS HIT"
            outcome = f"Loss: {pnl_pct:.2f}%"
        elif status == TradeStatus.TARGET_1_HIT:
            emoji = "🟡"
            title = "TARGET 1 HIT"
            outcome = f"Profit: +{pnl_pct:.2f}% (1R achieved)"
        elif status == TradeStatus.TARGET_2_HIT:
            emoji = "🟢"
            title = "TARGET 2 HIT"
            outcome = f"Profit: +{pnl_pct:.2f}% (R:R {rr_achieved:.1f})"
        elif status == TradeStatus.TRAILING_STOP_HIT:
            emoji = "🟠"
            title = "TRAILING STOP HIT"
            outcome = f"Profit: +{pnl_pct:.2f}% (R:R {rr_achieved:.1f})"
        else:
            emoji = "⚪"
            title = "TRADE EXPIRED"
            outcome = f"P&L: {pnl_pct:.2f}%"

        message = (
            f"{emoji} *{title}*\n"
            f"\n"
            f"*Symbol:* `{trade.symbol}`\n"
            f"*Setup:* {trade.setup_type.replace('_', ' ').title()}\n"
            f"\n"
            f"📊 *Trade Summary*\n"
            f"  Entry: ₹{trade.entry_price:.2f}\n"
            f"  Exit: ₹{price:.2f}\n"
            f"  {outcome}\n"
            f"\n"
            f"📋 *Levels*\n"
            f"  Stop Loss: ₹{trade.stop_loss:.2f}\n"
            f"  Target 1: ₹{trade.target_1:.2f} {'✅' if trade.target_1_hit else '—'}\n"
            f"  Target 2: ₹{trade.target_2:.2f} {'✅' if status == TradeStatus.TARGET_2_HIT else '—'}\n"
            f"  Highest: ₹{trade.highest_price:.2f}\n"
        )

        try:
            self._alert_service.send_message(message, parse_mode="Markdown")
        except Exception as e:
            logger.error("Failed to send trade update for %s: %s", trade.symbol, e)

    def is_symbol_in_journal(self, symbol: str) -> bool:
        """Check if a symbol has an open trade in the journal.

        Args:
            symbol: Stock symbol to check.

        Returns:
            True if the symbol has an active open trade.
        """
        conn = self._get_connection()
        try:
            row = conn.execute(
                "SELECT id FROM trade_journal WHERE symbol = ? AND status = 'OPEN'",
                (symbol,)
            ).fetchone()
            return row is not None
        except sqlite3.Error:
            return False
        finally:
            conn.close()

    def get_journal_stats(self) -> Dict:
        """Get performance statistics from the trade journal.

        Returns:
            Dict with hit_rate, avg_rr, total_trades, wins, losses.
        """
        conn = self._get_connection()
        try:
            rows = conn.execute(
                """SELECT status, pnl_pct, risk_reward_achieved
                   FROM trade_journal
                   WHERE status != 'OPEN'"""
            ).fetchall()

            if not rows:
                return {"total_trades": 0, "hit_rate": 0.0, "avg_rr": 0.0, "wins": 0, "losses": 0}

            total = len(rows)
            wins = sum(1 for r in rows if r["pnl_pct"] and r["pnl_pct"] > 0)
            losses = total - wins
            avg_rr = sum(r["risk_reward_achieved"] or 0 for r in rows) / total

            return {
                "total_trades": total,
                "hit_rate": (wins / total) * 100 if total > 0 else 0.0,
                "avg_rr": avg_rr,
                "wins": wins,
                "losses": losses,
            }
        except sqlite3.Error as e:
            logger.error("Failed to get journal stats: %s", e)
            return {"total_trades": 0, "hit_rate": 0.0, "avg_rr": 0.0, "wins": 0, "losses": 0}
        finally:
            conn.close()
