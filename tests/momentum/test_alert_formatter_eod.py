"""Unit tests for AlertFormatter EOD report formatting and delivery."""

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from src.momentum.alert_formatter import AlertFormatter
from src.momentum.models import EODReport, MomentumSignal, SetupType


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
def sample_eod_report(sample_signal):
    """A sample EODReport with populated fields."""
    signal_2 = MomentumSignal(
        symbol="TCS",
        setup_type=SetupType.COMPRESSION_BREAKOUT,
        entry_price=3800.0,
        stop_loss=3750.0,
        target_1=3850.0,
        target_2=3900.0,
        relative_volume=1.8,
        relative_strength=2.9,
        sector_strength=2.1,
        trend_quality_score=80.0,
        rank_score=78.0,
        breakout_strength=72.0,
        distance_from_breakout=88.0,
        timeframe="15m",
        timestamp=datetime(2024, 1, 15, 11, 0, 0),
        risk_pct=1.3,
        trailing_stop=3770.0,
    )
    return EODReport(
        date=datetime(2024, 1, 15),
        total_scans=45,
        total_signals=12,
        top_performers=[sample_signal, signal_2],
        setup_breakdown={
            "PULLBACK_CONTINUATION": 8,
            "COMPRESSION_BREAKOUT": 4,
        },
        sector_breakdown={"RELIANCE": 3, "TCS": 2, "INFY": 1},
        avg_rank_score=74.5,
        market_breadth_suppressed_count=3,
    )


@pytest.fixture
def empty_eod_report():
    """An EODReport with no signals (quiet day)."""
    return EODReport(
        date=datetime(2024, 1, 15),
        total_scans=45,
        total_signals=0,
        top_performers=[],
        setup_breakdown={},
        sector_breakdown={},
        avg_rank_score=0.0,
        market_breadth_suppressed_count=10,
    )


@pytest.fixture
def mock_alert_service():
    """A mock AlertService that tracks sent messages."""
    service = MagicMock()
    service.send_message = MagicMock(return_value=True)
    return service


class TestFormatEodReport:
    """Tests for format_eod_report() method."""

    def test_contains_report_header_emoji(self, sample_eod_report):
        """Should include 📋 emoji for report header."""
        formatter = AlertFormatter()
        message = formatter.format_eod_report(sample_eod_report)
        assert "📋" in message

    def test_contains_end_of_day_title(self, sample_eod_report):
        """Should include END OF DAY REPORT title."""
        formatter = AlertFormatter()
        message = formatter.format_eod_report(sample_eod_report)
        assert "END OF DAY REPORT" in message

    def test_contains_date_header(self, sample_eod_report):
        """Should include the report date."""
        formatter = AlertFormatter()
        message = formatter.format_eod_report(sample_eod_report)
        assert "2024-01-15" in message

    def test_contains_total_scans(self, sample_eod_report):
        """Should include total scans count."""
        formatter = AlertFormatter()
        message = formatter.format_eod_report(sample_eod_report)
        assert "Total Scans: 45" in message

    def test_contains_total_signals(self, sample_eod_report):
        """Should include total signals count."""
        formatter = AlertFormatter()
        message = formatter.format_eod_report(sample_eod_report)
        assert "Total Signals: 12" in message

    def test_contains_avg_rank_score(self, sample_eod_report):
        """Should include average rank score."""
        formatter = AlertFormatter()
        message = formatter.format_eod_report(sample_eod_report)
        assert "Avg Rank Score: 74.5/100" in message

    def test_contains_breadth_suppressed_count(self, sample_eod_report):
        """Should include market breadth suppressed count."""
        formatter = AlertFormatter()
        message = formatter.format_eod_report(sample_eod_report)
        assert "Breadth Suppressed: 3" in message

    def test_contains_top_performers_emoji(self, sample_eod_report):
        """Should include 🏆 emoji for top performers section."""
        formatter = AlertFormatter()
        message = formatter.format_eod_report(sample_eod_report)
        assert "🏆" in message

    def test_contains_top_performer_symbols(self, sample_eod_report):
        """Should include top performer symbols."""
        formatter = AlertFormatter()
        message = formatter.format_eod_report(sample_eod_report)
        assert "RELIANCE" in message
        assert "TCS" in message

    def test_contains_top_performer_setup_type(self, sample_eod_report):
        """Should include setup type for top performers."""
        formatter = AlertFormatter()
        message = formatter.format_eod_report(sample_eod_report)
        assert "Pullback Continuation" in message
        assert "Compression Breakout" in message

    def test_contains_top_performer_rank_score(self, sample_eod_report):
        """Should include rank score for top performers."""
        formatter = AlertFormatter()
        message = formatter.format_eod_report(sample_eod_report)
        assert "Score: 82.5" in message
        assert "Score: 78.0" in message

    def test_contains_stats_emoji(self, sample_eod_report):
        """Should include 📊 emoji for stats section."""
        formatter = AlertFormatter()
        message = formatter.format_eod_report(sample_eod_report)
        assert "📊" in message

    def test_contains_setup_breakdown(self, sample_eod_report):
        """Should include setup type breakdown."""
        formatter = AlertFormatter()
        message = formatter.format_eod_report(sample_eod_report)
        assert "Pullback Continuation: 8" in message
        assert "Compression Breakout: 4" in message

    def test_empty_report_no_top_performers_section(self, empty_eod_report):
        """Should not include top performers section when list is empty."""
        formatter = AlertFormatter()
        message = formatter.format_eod_report(empty_eod_report)
        assert "🏆" not in message

    def test_empty_report_no_setup_breakdown_section(self, empty_eod_report):
        """Should not include setup breakdown when dict is empty."""
        formatter = AlertFormatter()
        message = formatter.format_eod_report(empty_eod_report)
        # The 📊 emoji is used for Daily Statistics, so it should still appear
        assert "Setup Breakdown" not in message

    def test_empty_report_still_has_stats(self, empty_eod_report):
        """Should still include basic stats even with no signals."""
        formatter = AlertFormatter()
        message = formatter.format_eod_report(empty_eod_report)
        assert "Total Scans: 45" in message
        assert "Total Signals: 0" in message
        assert "Breadth Suppressed: 10" in message

    def test_limits_top_performers_to_5(self):
        """Should show at most 5 top performers even if more exist."""
        performers = [
            MomentumSignal(
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
                rank_score=90.0 - i,
                breakout_strength=60.0,
                distance_from_breakout=85.0,
                timeframe="15m",
                timestamp=datetime(2024, 1, 15, 10, 30, 0),
                risk_pct=5.0,
                trailing_stop=98.0,
            )
            for i in range(7)
        ]
        report = EODReport(
            date=datetime(2024, 1, 15),
            total_scans=45,
            total_signals=7,
            top_performers=performers,
            setup_breakdown={"PULLBACK_CONTINUATION": 7},
            sector_breakdown={},
            avg_rank_score=80.0,
            market_breadth_suppressed_count=0,
        )
        formatter = AlertFormatter()
        message = formatter.format_eod_report(report)
        # Should show STOCK0 through STOCK4 but not STOCK5 or STOCK6
        assert "STOCK0" in message
        assert "STOCK4" in message
        assert "STOCK5" not in message
        assert "STOCK6" not in message


class TestSendEodReport:
    """Tests for send_eod_report() method."""

    def test_send_success(self, mock_alert_service, sample_eod_report):
        """Should return True when AlertService sends successfully."""
        formatter = AlertFormatter(alert_service=mock_alert_service)
        result = formatter.send_eod_report(sample_eod_report)
        assert result is True

    def test_calls_alert_service_send_message(self, mock_alert_service, sample_eod_report):
        """Should call alert_service.send_message with formatted message."""
        formatter = AlertFormatter(alert_service=mock_alert_service)
        formatter.send_eod_report(sample_eod_report)
        mock_alert_service.send_message.assert_called_once()
        call_args = mock_alert_service.send_message.call_args
        assert "END OF DAY REPORT" in call_args[0][0]
        assert call_args[1]["parse_mode"] == "Markdown"

    def test_returns_false_when_no_alert_service(self, sample_eod_report):
        """Should return False when alert_service is None."""
        formatter = AlertFormatter(alert_service=None)
        result = formatter.send_eod_report(sample_eod_report)
        assert result is False

    def test_returns_false_on_send_failure(self, mock_alert_service, sample_eod_report):
        """Should return False when AlertService fails to send."""
        mock_alert_service.send_message.return_value = False
        formatter = AlertFormatter(alert_service=mock_alert_service)
        result = formatter.send_eod_report(sample_eod_report)
        assert result is False

    def test_returns_false_on_exception(self, mock_alert_service, sample_eod_report):
        """Should return False and not raise when AlertService throws."""
        mock_alert_service.send_message.side_effect = Exception("Network error")
        formatter = AlertFormatter(alert_service=mock_alert_service)
        result = formatter.send_eod_report(sample_eod_report)
        assert result is False

    def test_send_empty_report(self, mock_alert_service, empty_eod_report):
        """Should successfully send an empty report."""
        formatter = AlertFormatter(alert_service=mock_alert_service)
        result = formatter.send_eod_report(empty_eod_report)
        assert result is True
        mock_alert_service.send_message.assert_called_once()
