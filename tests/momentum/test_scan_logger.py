"""Unit tests for ScanLogger class."""

import os
import tempfile
from datetime import date, datetime

import pytest

from src.momentum.models import (
    EODReport,
    MomentumSignal,
    ScanCycleResult,
    SetupType,
)
from src.momentum.scan_logger import ScanLogger


@pytest.fixture
def temp_db():
    """Create a temporary database file for testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    # Cleanup
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def scan_logger(temp_db):
    """ScanLogger instance with a temporary database."""
    return ScanLogger(db_path=temp_db)


@pytest.fixture
def sample_signal():
    """A sample MomentumSignal for testing."""
    return MomentumSignal(
        symbol="RELIANCE",
        setup_type=SetupType.PULLBACK_CONTINUATION,
        entry_price=2500.0,
        stop_loss=2450.0,
        target_1=2550.0,
        target_2=2600.0,
        relative_volume=2.1,
        relative_strength=3.5,
        sector_strength=1.8,
        trend_quality_score=75.0,
        rank_score=82.5,
        breakout_strength=68.0,
        distance_from_breakout=85.0,
        timeframe="15m",
        timestamp=datetime(2024, 1, 15, 10, 30, 0),
        risk_pct=2.0,
        trailing_stop=2480.0,
    )


@pytest.fixture
def sample_cycle(sample_signal):
    """A sample ScanCycleResult for testing."""
    return ScanCycleResult(
        timestamp=datetime(2024, 1, 15, 10, 30, 0),
        duration_seconds=45.2,
        stage1_passed=120,
        stage2_ranked=80,
        stage3_triggered=12,
        signals_generated=[sample_signal],
        signals_suppressed=3,
        market_breadth_healthy=True,
        rejected_reasons={"low_volume": 5, "weak_trend": 15},
    )


class TestScanLoggerInit:
    """Tests for ScanLogger initialization."""

    def test_creates_database_file(self, temp_db):
        """Database file should be created on initialization."""
        # Remove the temp file so ScanLogger creates it fresh
        os.unlink(temp_db)
        ScanLogger(db_path=temp_db)
        assert os.path.exists(temp_db)

    def test_creates_directory_if_not_exists(self):
        """Should create parent directories if they don't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "subdir", "nested", "test.db")
            ScanLogger(db_path=db_path)
            assert os.path.exists(db_path)

    def test_tables_created(self, scan_logger, temp_db):
        """All required tables should be created."""
        import sqlite3

        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()

        assert "scan_cycles" in tables
        assert "signals" in tables
        assert "rejected_setups" in tables

    def test_idempotent_init(self, temp_db):
        """Multiple initializations should not fail or duplicate tables."""
        ScanLogger(db_path=temp_db)
        ScanLogger(db_path=temp_db)  # Should not raise


class TestLogCycle:
    """Tests for log_cycle() method."""

    def test_log_cycle_returns_id(self, scan_logger, sample_cycle):
        """log_cycle should return the scan_cycle_id."""
        cycle_id = scan_logger.log_cycle(sample_cycle)
        assert cycle_id is not None
        assert cycle_id > 0

    def test_log_cycle_persists_cycle_data(self, scan_logger, sample_cycle, temp_db):
        """Scan cycle metadata should be persisted correctly."""
        import sqlite3

        scan_logger.log_cycle(sample_cycle)

        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM scan_cycles WHERE id = 1")
        row = cursor.fetchone()
        conn.close()

        assert row["duration_seconds"] == 45.2
        assert row["stage1_passed"] == 120
        assert row["stage2_ranked"] == 80
        assert row["stage3_triggered"] == 12
        assert row["signals_generated_count"] == 1
        assert row["signals_suppressed"] == 3
        assert row["market_breadth_healthy"] == 1

    def test_log_cycle_persists_signals(self, scan_logger, sample_cycle, temp_db):
        """Signals should be persisted with all fields."""
        import sqlite3

        scan_logger.log_cycle(sample_cycle)

        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM signals WHERE scan_cycle_id = 1")
        row = cursor.fetchone()
        conn.close()

        assert row["symbol"] == "RELIANCE"
        assert row["setup_type"] == "PULLBACK_CONTINUATION"
        assert row["entry_price"] == 2500.0
        assert row["stop_loss"] == 2450.0
        assert row["target_1"] == 2550.0
        assert row["target_2"] == 2600.0
        assert row["relative_volume"] == 2.1
        assert row["rank_score"] == 82.5
        assert row["timeframe"] == "15m"

    def test_log_cycle_persists_rejected_reasons(self, scan_logger, sample_cycle, temp_db):
        """Rejected reasons should be persisted."""
        import sqlite3

        scan_logger.log_cycle(sample_cycle)

        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM rejected_setups WHERE scan_cycle_id = 1 ORDER BY reason"
        )
        rows = cursor.fetchall()
        conn.close()

        assert len(rows) == 2
        reasons = {row["reason"]: row["count"] for row in rows}
        assert reasons["low_volume"] == 5
        assert reasons["weak_trend"] == 15

    def test_log_cycle_empty_signals(self, scan_logger):
        """Should handle cycles with no signals."""
        cycle = ScanCycleResult(
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            duration_seconds=30.0,
            stage1_passed=50,
            stage2_ranked=20,
            stage3_triggered=0,
            signals_generated=[],
            signals_suppressed=0,
            market_breadth_healthy=True,
            rejected_reasons={},
        )
        cycle_id = scan_logger.log_cycle(cycle)
        assert cycle_id is not None

    def test_log_cycle_multiple_signals(self, scan_logger):
        """Should handle cycles with multiple signals."""
        signals = [
            MomentumSignal(
                symbol=f"STOCK{i}",
                setup_type=SetupType.COMPRESSION_BREAKOUT,
                entry_price=100.0 + i,
                stop_loss=95.0 + i,
                target_1=105.0 + i,
                target_2=110.0 + i,
                relative_volume=1.5 + i * 0.1,
                relative_strength=2.0 + i * 0.5,
                sector_strength=1.0,
                trend_quality_score=70.0 + i,
                rank_score=80.0 + i,
                breakout_strength=60.0 + i,
                distance_from_breakout=90.0 - i,
                timeframe="15m",
                timestamp=datetime(2024, 1, 15, 10, 30, 0),
                risk_pct=5.0,
                trailing_stop=98.0 + i,
            )
            for i in range(5)
        ]
        cycle = ScanCycleResult(
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            duration_seconds=55.0,
            stage1_passed=200,
            stage2_ranked=100,
            stage3_triggered=20,
            signals_generated=signals,
            signals_suppressed=5,
            market_breadth_healthy=True,
            rejected_reasons={"no_trigger": 80},
        )
        cycle_id = scan_logger.log_cycle(cycle)
        assert cycle_id is not None

    def test_log_multiple_cycles(self, scan_logger, sample_cycle):
        """Should handle logging multiple cycles sequentially."""
        id1 = scan_logger.log_cycle(sample_cycle)
        id2 = scan_logger.log_cycle(sample_cycle)
        assert id1 != id2
        assert id2 == id1 + 1


class TestGenerateEodReport:
    """Tests for generate_eod_report() method."""

    def test_empty_day_returns_zero_report(self, scan_logger):
        """Report for a day with no scans should have zero values."""
        report = scan_logger.generate_eod_report(date(2024, 1, 15))
        assert report.total_scans == 0
        assert report.total_signals == 0
        assert report.avg_rank_score == 0.0
        assert report.top_performers == []
        assert report.setup_breakdown == {}

    def test_report_counts_scans(self, scan_logger, sample_cycle):
        """Should count total scan cycles for the day."""
        scan_logger.log_cycle(sample_cycle)
        scan_logger.log_cycle(sample_cycle)
        scan_logger.log_cycle(sample_cycle)

        report = scan_logger.generate_eod_report(date(2024, 1, 15))
        assert report.total_scans == 3

    def test_report_counts_signals(self, scan_logger, sample_cycle):
        """Should count total signals across all cycles."""
        scan_logger.log_cycle(sample_cycle)  # 1 signal
        scan_logger.log_cycle(sample_cycle)  # 1 signal

        report = scan_logger.generate_eod_report(date(2024, 1, 15))
        assert report.total_signals == 2

    def test_report_top_performers(self, scan_logger):
        """Should return top 5 signals by rank_score."""
        for i in range(7):
            signal = MomentumSignal(
                symbol=f"STOCK{i}",
                setup_type=SetupType.PULLBACK_CONTINUATION,
                entry_price=100.0,
                stop_loss=95.0,
                target_1=105.0,
                target_2=110.0,
                relative_volume=2.0,
                relative_strength=3.0,
                sector_strength=1.0,
                trend_quality_score=70.0,
                rank_score=50.0 + i * 5,  # 50, 55, 60, 65, 70, 75, 80
                breakout_strength=60.0,
                distance_from_breakout=85.0,
                timeframe="15m",
                timestamp=datetime(2024, 1, 15, 10, 30, 0),
                risk_pct=5.0,
                trailing_stop=98.0,
            )
            cycle = ScanCycleResult(
                timestamp=datetime(2024, 1, 15, 10, 30 + i, 0),
                duration_seconds=40.0,
                stage1_passed=100,
                stage2_ranked=50,
                stage3_triggered=5,
                signals_generated=[signal],
                signals_suppressed=0,
                market_breadth_healthy=True,
                rejected_reasons={},
            )
            scan_logger.log_cycle(cycle)

        report = scan_logger.generate_eod_report(date(2024, 1, 15))
        assert len(report.top_performers) == 5
        # Top performers should be ordered by rank_score descending
        assert report.top_performers[0].rank_score == 80.0
        assert report.top_performers[4].rank_score == 60.0

    def test_report_setup_breakdown(self, scan_logger):
        """Should break down signals by setup type."""
        signals_pb = [
            MomentumSignal(
                symbol="RELIANCE",
                setup_type=SetupType.PULLBACK_CONTINUATION,
                entry_price=100.0, stop_loss=95.0, target_1=105.0, target_2=110.0,
                relative_volume=2.0, relative_strength=3.0, sector_strength=1.0,
                trend_quality_score=70.0, rank_score=80.0, breakout_strength=60.0,
                distance_from_breakout=85.0, timeframe="15m",
                timestamp=datetime(2024, 1, 15, 10, 30, 0),
                risk_pct=5.0, trailing_stop=98.0,
            )
        ]
        signals_cb = [
            MomentumSignal(
                symbol="TCS",
                setup_type=SetupType.COMPRESSION_BREAKOUT,
                entry_price=200.0, stop_loss=190.0, target_1=210.0, target_2=220.0,
                relative_volume=2.5, relative_strength=4.0, sector_strength=2.0,
                trend_quality_score=80.0, rank_score=85.0, breakout_strength=70.0,
                distance_from_breakout=90.0, timeframe="15m",
                timestamp=datetime(2024, 1, 15, 11, 0, 0),
                risk_pct=5.0, trailing_stop=195.0,
            )
        ]

        cycle1 = ScanCycleResult(
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            duration_seconds=40.0, stage1_passed=100, stage2_ranked=50,
            stage3_triggered=5, signals_generated=signals_pb,
            signals_suppressed=0, market_breadth_healthy=True, rejected_reasons={},
        )
        cycle2 = ScanCycleResult(
            timestamp=datetime(2024, 1, 15, 11, 0, 0),
            duration_seconds=40.0, stage1_passed=100, stage2_ranked=50,
            stage3_triggered=5, signals_generated=signals_cb,
            signals_suppressed=0, market_breadth_healthy=True, rejected_reasons={},
        )
        scan_logger.log_cycle(cycle1)
        scan_logger.log_cycle(cycle2)

        report = scan_logger.generate_eod_report(date(2024, 1, 15))
        assert report.setup_breakdown["PULLBACK_CONTINUATION"] == 1
        assert report.setup_breakdown["COMPRESSION_BREAKOUT"] == 1

    def test_report_avg_rank_score(self, scan_logger):
        """Should calculate average rank score across all signals."""
        signals = []
        for rank in [70.0, 80.0, 90.0]:
            signals.append(
                MomentumSignal(
                    symbol="TEST",
                    setup_type=SetupType.PULLBACK_CONTINUATION,
                    entry_price=100.0, stop_loss=95.0, target_1=105.0, target_2=110.0,
                    relative_volume=2.0, relative_strength=3.0, sector_strength=1.0,
                    trend_quality_score=70.0, rank_score=rank, breakout_strength=60.0,
                    distance_from_breakout=85.0, timeframe="15m",
                    timestamp=datetime(2024, 1, 15, 10, 30, 0),
                    risk_pct=5.0, trailing_stop=98.0,
                )
            )

        cycle = ScanCycleResult(
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            duration_seconds=40.0, stage1_passed=100, stage2_ranked=50,
            stage3_triggered=5, signals_generated=signals,
            signals_suppressed=0, market_breadth_healthy=True, rejected_reasons={},
        )
        scan_logger.log_cycle(cycle)

        report = scan_logger.generate_eod_report(date(2024, 1, 15))
        assert report.avg_rank_score == pytest.approx(80.0, abs=0.01)

    def test_report_market_breadth_suppressed(self, scan_logger):
        """Should count cycles where market breadth was unhealthy."""
        healthy_cycle = ScanCycleResult(
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            duration_seconds=40.0, stage1_passed=100, stage2_ranked=50,
            stage3_triggered=5, signals_generated=[],
            signals_suppressed=0, market_breadth_healthy=True, rejected_reasons={},
        )
        unhealthy_cycle = ScanCycleResult(
            timestamp=datetime(2024, 1, 15, 11, 0, 0),
            duration_seconds=40.0, stage1_passed=100, stage2_ranked=50,
            stage3_triggered=0, signals_generated=[],
            signals_suppressed=5, market_breadth_healthy=False, rejected_reasons={},
        )

        scan_logger.log_cycle(healthy_cycle)
        scan_logger.log_cycle(unhealthy_cycle)
        scan_logger.log_cycle(unhealthy_cycle)

        report = scan_logger.generate_eod_report(date(2024, 1, 15))
        assert report.market_breadth_suppressed_count == 2

    def test_report_only_includes_requested_date(self, scan_logger, sample_signal):
        """Should only aggregate data for the requested date."""
        cycle_jan15 = ScanCycleResult(
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            duration_seconds=40.0, stage1_passed=100, stage2_ranked=50,
            stage3_triggered=5, signals_generated=[sample_signal],
            signals_suppressed=0, market_breadth_healthy=True, rejected_reasons={},
        )
        # Different date signal
        signal_jan16 = MomentumSignal(
            symbol="TCS",
            setup_type=SetupType.COMPRESSION_BREAKOUT,
            entry_price=200.0, stop_loss=190.0, target_1=210.0, target_2=220.0,
            relative_volume=2.5, relative_strength=4.0, sector_strength=2.0,
            trend_quality_score=80.0, rank_score=85.0, breakout_strength=70.0,
            distance_from_breakout=90.0, timeframe="15m",
            timestamp=datetime(2024, 1, 16, 10, 30, 0),
            risk_pct=5.0, trailing_stop=195.0,
        )
        cycle_jan16 = ScanCycleResult(
            timestamp=datetime(2024, 1, 16, 10, 30, 0),
            duration_seconds=40.0, stage1_passed=100, stage2_ranked=50,
            stage3_triggered=5, signals_generated=[signal_jan16],
            signals_suppressed=0, market_breadth_healthy=True, rejected_reasons={},
        )

        scan_logger.log_cycle(cycle_jan15)
        scan_logger.log_cycle(cycle_jan16)

        report_15 = scan_logger.generate_eod_report(date(2024, 1, 15))
        assert report_15.total_scans == 1
        assert report_15.total_signals == 1

        report_16 = scan_logger.generate_eod_report(date(2024, 1, 16))
        assert report_16.total_scans == 1
        assert report_16.total_signals == 1

    def test_report_returns_eod_report_type(self, scan_logger):
        """Should return an EODReport instance."""
        report = scan_logger.generate_eod_report(date(2024, 1, 15))
        assert isinstance(report, EODReport)

    def test_report_date_field(self, scan_logger, sample_cycle):
        """Report date field should match the requested date."""
        scan_logger.log_cycle(sample_cycle)
        report = scan_logger.generate_eod_report(date(2024, 1, 15))
        assert report.date.date() == date(2024, 1, 15)
