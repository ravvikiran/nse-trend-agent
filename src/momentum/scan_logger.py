"""ScanLogger: Logs every scan cycle to SQLite and generates EOD reports.

Persists scan cycle results, signals, and rejected setups to a SQLite database.
Provides end-of-day report aggregation for performance tracking.
"""

import json
import logging
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from src.momentum.models import EODReport, MomentumSignal, ScanCycleResult, SetupType

logger = logging.getLogger(__name__)

# Default database path
DEFAULT_DB_PATH = "data/momentum_scanner.db"


class ScanLogger:
    """Logs every scan cycle to SQLite database.

    Creates the database and tables on first use (if not exists).
    Stores all indicators, scores, triggered/rejected setups, and timestamps.
    Generates end-of-day reports aggregating daily metrics.
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        """Initialize ScanLogger with database path.

        Args:
            db_path: Path to SQLite database file. Created if not exists.
        """
        self._db_path = db_path
        self._ensure_db_directory()
        self._init_db()

    def _ensure_db_directory(self) -> None:
        """Create the directory for the database file if it doesn't exist."""
        db_dir = Path(self._db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        """Get a new database connection."""
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self) -> None:
        """Create database tables if they don't exist."""
        conn = self._get_connection()
        try:
            conn.executescript(self._get_schema())
            conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Failed to initialize scan logger database: {e}")
        finally:
            conn.close()

    @staticmethod
    def _get_schema() -> str:
        """Return the SQL schema for scan log tables."""
        return """
        CREATE TABLE IF NOT EXISTS scan_cycles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            duration_seconds REAL NOT NULL,
            stage1_passed INTEGER NOT NULL,
            stage2_ranked INTEGER NOT NULL,
            stage3_triggered INTEGER NOT NULL,
            signals_generated_count INTEGER NOT NULL,
            signals_suppressed INTEGER NOT NULL,
            market_breadth_healthy INTEGER NOT NULL,
            rejected_reasons TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_cycle_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            setup_type TEXT NOT NULL,
            entry_price REAL NOT NULL,
            stop_loss REAL NOT NULL,
            target_1 REAL NOT NULL,
            target_2 REAL NOT NULL,
            relative_volume REAL NOT NULL,
            relative_strength REAL NOT NULL,
            sector_strength REAL NOT NULL,
            trend_quality_score REAL NOT NULL,
            rank_score REAL NOT NULL,
            breakout_strength REAL NOT NULL,
            distance_from_breakout REAL NOT NULL,
            timeframe TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            risk_pct REAL NOT NULL,
            trailing_stop REAL NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (scan_cycle_id) REFERENCES scan_cycles(id)
        );

        CREATE TABLE IF NOT EXISTS rejected_setups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_cycle_id INTEGER NOT NULL,
            reason TEXT NOT NULL,
            count INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (scan_cycle_id) REFERENCES scan_cycles(id)
        );

        CREATE INDEX IF NOT EXISTS idx_scan_cycles_timestamp
            ON scan_cycles(timestamp);

        CREATE INDEX IF NOT EXISTS idx_signals_scan_cycle_id
            ON signals(scan_cycle_id);

        CREATE INDEX IF NOT EXISTS idx_signals_symbol
            ON signals(symbol);

        CREATE INDEX IF NOT EXISTS idx_signals_timestamp
            ON signals(timestamp);

        CREATE INDEX IF NOT EXISTS idx_rejected_setups_scan_cycle_id
            ON rejected_setups(scan_cycle_id);
        """

    def log_cycle(self, cycle: ScanCycleResult) -> Optional[int]:
        """Store a complete scan cycle result to the database.

        Persists all indicators, scores, triggered/rejected setups, and timestamps.

        Args:
            cycle: The ScanCycleResult from a completed scan cycle.

        Returns:
            The scan_cycle_id of the inserted record, or None on failure.
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Insert scan cycle record
            cursor.execute(
                """
                INSERT INTO scan_cycles (
                    timestamp, duration_seconds, stage1_passed, stage2_ranked,
                    stage3_triggered, signals_generated_count, signals_suppressed,
                    market_breadth_healthy, rejected_reasons
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cycle.timestamp.isoformat(),
                    cycle.duration_seconds,
                    cycle.stage1_passed,
                    cycle.stage2_ranked,
                    cycle.stage3_triggered,
                    len(cycle.signals_generated),
                    cycle.signals_suppressed,
                    1 if cycle.market_breadth_healthy else 0,
                    json.dumps(cycle.rejected_reasons) if cycle.rejected_reasons else None,
                ),
            )
            scan_cycle_id = cursor.lastrowid

            # Insert signals
            for signal in cycle.signals_generated:
                cursor.execute(
                    """
                    INSERT INTO signals (
                        scan_cycle_id, symbol, setup_type, entry_price, stop_loss,
                        target_1, target_2, relative_volume, relative_strength,
                        sector_strength, trend_quality_score, rank_score,
                        breakout_strength, distance_from_breakout, timeframe,
                        timestamp, risk_pct, trailing_stop
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        scan_cycle_id,
                        signal.symbol,
                        signal.setup_type.value,
                        signal.entry_price,
                        signal.stop_loss,
                        signal.target_1,
                        signal.target_2,
                        signal.relative_volume,
                        signal.relative_strength,
                        signal.sector_strength,
                        signal.trend_quality_score,
                        signal.rank_score,
                        signal.breakout_strength,
                        signal.distance_from_breakout,
                        signal.timeframe,
                        signal.timestamp.isoformat(),
                        signal.risk_pct,
                        signal.trailing_stop,
                    ),
                )

            # Insert rejected setups
            for reason, count in cycle.rejected_reasons.items():
                cursor.execute(
                    """
                    INSERT INTO rejected_setups (scan_cycle_id, reason, count)
                    VALUES (?, ?, ?)
                    """,
                    (scan_cycle_id, reason, count),
                )

            conn.commit()
            logger.debug(
                f"Logged scan cycle at {cycle.timestamp.isoformat()}: "
                f"{len(cycle.signals_generated)} signals, "
                f"{cycle.signals_suppressed} suppressed"
            )
            return scan_cycle_id

        except sqlite3.Error as e:
            logger.error(f"Failed to log scan cycle: {e}")
            conn.rollback()
            return None
        finally:
            conn.close()

    def generate_eod_report(self, report_date: date) -> EODReport:
        """Aggregate all scan cycles for a given date into an EODReport.

        Args:
            report_date: The date to generate the report for.

        Returns:
            EODReport with aggregated daily metrics.
        """
        conn = self._get_connection()
        try:
            # Get all scan cycles for the date
            date_str = report_date.isoformat()
            cursor = conn.cursor()

            # Count total scans for the day
            cursor.execute(
                """
                SELECT COUNT(*) as total_scans
                FROM scan_cycles
                WHERE date(timestamp) = ?
                """,
                (date_str,),
            )
            row = cursor.fetchone()
            total_scans = row["total_scans"] if row else 0

            # Count total signals generated
            cursor.execute(
                """
                SELECT COUNT(*) as total_signals
                FROM signals s
                JOIN scan_cycles sc ON s.scan_cycle_id = sc.id
                WHERE date(sc.timestamp) = ?
                """,
                (date_str,),
            )
            row = cursor.fetchone()
            total_signals = row["total_signals"] if row else 0

            # Get top performers (top 5 by rank_score for the day)
            cursor.execute(
                """
                SELECT s.*
                FROM signals s
                JOIN scan_cycles sc ON s.scan_cycle_id = sc.id
                WHERE date(sc.timestamp) = ?
                ORDER BY s.rank_score DESC
                LIMIT 5
                """,
                (date_str,),
            )
            top_performer_rows = cursor.fetchall()
            top_performers = [self._row_to_signal(r) for r in top_performer_rows]

            # Setup type breakdown
            cursor.execute(
                """
                SELECT s.setup_type, COUNT(*) as count
                FROM signals s
                JOIN scan_cycles sc ON s.scan_cycle_id = sc.id
                WHERE date(sc.timestamp) = ?
                GROUP BY s.setup_type
                """,
                (date_str,),
            )
            setup_breakdown = {row["setup_type"]: row["count"] for row in cursor.fetchall()}

            # Sector breakdown (group by symbol prefix as proxy for sector)
            # Since we don't have a direct sector field in signals, we count by symbol
            # This provides a per-symbol signal count which serves as sector proxy
            cursor.execute(
                """
                SELECT s.symbol, COUNT(*) as count
                FROM signals s
                JOIN scan_cycles sc ON s.scan_cycle_id = sc.id
                WHERE date(sc.timestamp) = ?
                GROUP BY s.symbol
                ORDER BY count DESC
                """,
                (date_str,),
            )
            sector_breakdown = {row["symbol"]: row["count"] for row in cursor.fetchall()}

            # Average rank score
            cursor.execute(
                """
                SELECT AVG(s.rank_score) as avg_rank
                FROM signals s
                JOIN scan_cycles sc ON s.scan_cycle_id = sc.id
                WHERE date(sc.timestamp) = ?
                """,
                (date_str,),
            )
            row = cursor.fetchone()
            avg_rank_score = row["avg_rank"] if row and row["avg_rank"] is not None else 0.0

            # Market breadth suppressed count
            cursor.execute(
                """
                SELECT COUNT(*) as suppressed_count
                FROM scan_cycles
                WHERE date(timestamp) = ? AND market_breadth_healthy = 0
                """,
                (date_str,),
            )
            row = cursor.fetchone()
            market_breadth_suppressed_count = row["suppressed_count"] if row else 0

            return EODReport(
                date=datetime.combine(report_date, datetime.min.time()),
                total_scans=total_scans,
                total_signals=total_signals,
                top_performers=top_performers,
                setup_breakdown=setup_breakdown,
                sector_breakdown=sector_breakdown,
                avg_rank_score=avg_rank_score,
                market_breadth_suppressed_count=market_breadth_suppressed_count,
            )

        except sqlite3.Error as e:
            logger.error(f"Failed to generate EOD report for {report_date}: {e}")
            return EODReport(
                date=datetime.combine(report_date, datetime.min.time()),
                total_scans=0,
                total_signals=0,
            )
        finally:
            conn.close()

    @staticmethod
    def _row_to_signal(row: sqlite3.Row) -> MomentumSignal:
        """Convert a database row to a MomentumSignal dataclass."""
        return MomentumSignal(
            symbol=row["symbol"],
            setup_type=SetupType(row["setup_type"]),
            entry_price=row["entry_price"],
            stop_loss=row["stop_loss"],
            target_1=row["target_1"],
            target_2=row["target_2"],
            relative_volume=row["relative_volume"],
            relative_strength=row["relative_strength"],
            sector_strength=row["sector_strength"],
            trend_quality_score=row["trend_quality_score"],
            rank_score=row["rank_score"],
            breakout_strength=row["breakout_strength"],
            distance_from_breakout=row["distance_from_breakout"],
            timeframe=row["timeframe"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            risk_pct=row["risk_pct"],
            trailing_stop=row["trailing_stop"],
        )
