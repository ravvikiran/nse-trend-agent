"""Alert formatting and delivery for the NSE Momentum Scanner.

Formats MomentumSignal data into structured Telegram messages with emoji
indicators and delivers them via TelegramService.
Also formats and sends end-of-day (EOD) reports summarizing daily scan activity.
"""

import logging
from datetime import datetime, timezone, timedelta

from src.momentum.models import EODReport, MomentumSignal, SetupType

logger = logging.getLogger(__name__)

# IST timezone offset (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))


class AlertFormatter:
    """Formats MomentumSignal into Telegram messages and sends via TelegramService.

    Uses Markdown formatting with emoji indicators for signal quality.
    All 14 required fields are included in the formatted output.
    """

    # Emoji mapping for setup types
    SETUP_EMOJIS = {
        SetupType.PULLBACK_CONTINUATION: "🟢",
        SetupType.COMPRESSION_BREAKOUT: "🔵",
    }

    def __init__(self, alert_service=None):
        """Initialize AlertFormatter.

        Args:
            alert_service: An instance of AlertService from src/notifications/alert_service.py.
                          If None, send() will log a warning and return False.
        """
        self.alert_service = alert_service

    def format(self, signal: MomentumSignal) -> str:
        """Format a MomentumSignal as a Markdown Telegram message.

        Includes all 14 required fields: symbol, setup type, entry price,
        stop loss, risk percentage, target 1, target 2, relative volume,
        relative strength, sector strength, trend quality score, rank score,
        timeframe, and IST timestamp.

        Args:
            signal: MomentumSignal dataclass instance with all fields populated.

        Returns:
            Formatted Markdown string ready for Telegram delivery.
        """
        setup_emoji = self.SETUP_EMOJIS.get(signal.setup_type, "📊")
        setup_name = signal.setup_type.value.replace("_", " ").title()

        # Convert timestamp to IST
        ist_timestamp = self._to_ist(signal.timestamp)
        timestamp_str = ist_timestamp.strftime("%Y-%m-%d %H:%M IST")

        # Build the formatted message
        message = (
            f"{setup_emoji} *MOMENTUM SIGNAL*\n"
            f"\n"
            f"*Symbol:* `{signal.symbol}`\n"
            f"*Setup:* {setup_name}\n"
            f"*Timeframe:* {signal.timeframe}\n"
            f"\n"
            f"🎯 *Trade Levels*\n"
            f"  Entry: ₹{signal.entry_price:.2f}\n"
            f"  Stop Loss: ₹{signal.stop_loss:.2f}\n"
            f"  ⚠️ Risk: {signal.risk_pct:.2f}%\n"
            f"  Target 1: ₹{signal.target_1:.2f}\n"
            f"  Target 2: ₹{signal.target_2:.2f}\n"
            f"\n"
            f"📊 *Scores*\n"
            f"  Relative Volume: {signal.relative_volume:.1f}x\n"
            f"  Relative Strength: {signal.relative_strength:.2f}\n"
            f"  Sector Strength: {signal.sector_strength:.2f}\n"
            f"  Trend Score: {signal.trend_quality_score:.1f}/100\n"
            f"  Rank Score: {signal.rank_score:.1f}/100\n"
            f"\n"
            f"⏰ {timestamp_str}"
        )

        return message

    def send(self, signal: MomentumSignal) -> bool:
        """Format and send a MomentumSignal alert via AlertService.

        On AlertService error, logs the failure and returns False without
        raising an exception. This ensures the scanner continues processing
        remaining alerts.

        Args:
            signal: MomentumSignal to format and send.

        Returns:
            True if the message was sent successfully, False otherwise.
        """
        if self.alert_service is None:
            logger.warning(
                "AlertService not configured, cannot send alert for %s",
                signal.symbol,
            )
            return False

        try:
            message = self.format(signal)
            success = self.alert_service.send_message(message, parse_mode="Markdown")

            if not success:
                logger.error(
                    "AlertService failed to send message for %s", signal.symbol
                )
                return False

            logger.debug("Alert sent successfully for %s", signal.symbol)
            return True

        except Exception as e:
            logger.error(
                "Error sending alert for %s: %s", signal.symbol, str(e)
            )
            return False

    def _to_ist(self, dt: datetime) -> datetime:
        """Convert a datetime to IST (UTC+5:30).

        If the datetime is naive (no timezone info), it is assumed to be IST.
        If it has timezone info, it is converted to IST.

        Args:
            dt: datetime to convert.

        Returns:
            datetime in IST timezone.
        """
        if dt.tzinfo is None:
            # Assume naive datetimes are already IST
            return dt.replace(tzinfo=IST)
        return dt.astimezone(IST)

    def format_eod_report(self, report: EODReport) -> str:
        """Format an EODReport as a Markdown Telegram message.

        Includes: date header, total scans, total signals, top 3-5 performers
        (symbol, setup type, rank score), setup type breakdown, average rank
        score, and market breadth suppressed count.

        Args:
            report: EODReport dataclass instance with aggregated daily metrics.

        Returns:
            Formatted Markdown string ready for Telegram delivery.
        """
        # Date header
        report_date_str = report.date.strftime("%Y-%m-%d")

        message = (
            f"📋 *END OF DAY REPORT*\n"
            f"*Date:* {report_date_str}\n"
            f"\n"
        )

        # Stats section
        message += (
            f"📊 *Daily Statistics*\n"
            f"  Total Scans: {report.total_scans}\n"
            f"  Total Signals: {report.total_signals}\n"
            f"  Avg Rank Score: {report.avg_rank_score:.1f}/100\n"
            f"  Breadth Suppressed: {report.market_breadth_suppressed_count}\n"
            f"\n"
        )

        # Top performers section (top 3-5)
        if report.top_performers:
            performers_to_show = report.top_performers[:5]
            message += f"🏆 *Top Performers*\n"
            for i, signal in enumerate(performers_to_show, start=1):
                setup_name = signal.setup_type.value.replace("_", " ").title()
                message += (
                    f"  {i}. `{signal.symbol}` — {setup_name} "
                    f"(Score: {signal.rank_score:.1f})\n"
                )
            message += "\n"

        # Setup type breakdown
        if report.setup_breakdown:
            message += f"📊 *Setup Breakdown*\n"
            for setup_type, count in report.setup_breakdown.items():
                setup_display = setup_type.replace("_", " ").title()
                message += f"  {setup_display}: {count}\n"
            message += "\n"

        return message.rstrip("\n")

    def send_eod_report(self, report: EODReport) -> bool:
        """Format and send an EOD report via AlertService.

        On AlertService error, logs the failure and returns False without
        raising an exception.

        Args:
            report: EODReport to format and send.

        Returns:
            True if the message was sent successfully, False otherwise.
        """
        if self.alert_service is None:
            logger.warning(
                "AlertService not configured, cannot send EOD report for %s",
                report.date.strftime("%Y-%m-%d"),
            )
            return False

        try:
            message = self.format_eod_report(report)
            success = self.alert_service.send_message(message, parse_mode="Markdown")

            if not success:
                logger.error(
                    "AlertService failed to send EOD report for %s",
                    report.date.strftime("%Y-%m-%d"),
                )
                return False

            logger.debug(
                "EOD report sent successfully for %s",
                report.date.strftime("%Y-%m-%d"),
            )
            return True

        except Exception as e:
            logger.error(
                "Error sending EOD report for %s: %s",
                report.date.strftime("%Y-%m-%d"),
                str(e),
            )
            return False
