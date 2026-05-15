"""
Self-contained Telegram service for the NSE Momentum Scanner.

Sends messages via the Telegram Bot API using HTTP requests with
connection pooling for performance.

Implements the AlertService interface for decoupled alert delivery.

Environment variables:
    TELEGRAM_BOT_TOKEN: Bot token from @BotFather
    TELEGRAM_CHAT_ID: Target chat ID for alerts
"""

import logging
import os
from typing import Optional

import requests
from requests.adapters import HTTPAdapter

from src.momentum.alert_service import AlertService

logger = logging.getLogger(__name__)


class TelegramService(AlertService):
    """Sends messages via Telegram Bot API.

    Uses HTTP connection pooling for efficient request handling.
    Implements the AlertService interface for decoupled usage.
    """

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
    ):
        """Initialize TelegramService with connection pooling.

        Args:
            bot_token: Telegram bot token. Falls back to TELEGRAM_BOT_TOKEN env var.
            chat_id: Target chat ID. Falls back to TELEGRAM_CHAT_ID env var.
        """
        self.bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
        self.enabled = bool(self.bot_token and self.chat_id)

        # Connection pooling for performance (PERF-001)
        self._session = requests.Session()
        adapter = HTTPAdapter(
            pool_connections=5,
            pool_maxsize=10,
            max_retries=3,
        )
        self._session.mount("https://", adapter)

        if self.enabled:
            logger.info("TelegramService enabled (chat_id: %s)", self.chat_id)
        else:
            logger.warning(
                "TelegramService disabled — set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID"
            )

    def send_message(self, text: str, parse_mode: str = "Markdown") -> bool:
        """Send a message via Telegram Bot API.

        Args:
            text: Message text (supports Markdown formatting).
            parse_mode: Parse mode — 'Markdown' or 'HTML'.

        Returns:
            True if sent successfully, False otherwise.
        """
        if not self.enabled:
            logger.debug("Telegram disabled, message not sent: %s", text[:80])
            return False

        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": parse_mode,
            }

            response = self._session.post(url, json=payload, timeout=30)

            if response.status_code == 200:
                logger.debug("Telegram message sent successfully")
                return True
            else:
                logger.error(
                    "Telegram API error %d: %s",
                    response.status_code,
                    response.text[:200],
                )
                return False

        except requests.exceptions.Timeout:
            logger.error("Telegram send timed out")
            return False
        except requests.exceptions.RequestException as e:
            logger.error("Telegram send failed: %s", e)
            return False
        except Exception as e:
            logger.error("Unexpected error sending Telegram message: %s", e)
            return False

    def test_connection(self) -> bool:
        """Test the Telegram bot connection.

        Returns:
            True if the bot token is valid and reachable.
        """
        if not self.bot_token:
            return False

        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/getMe"
            response = self._session.get(url, timeout=10)
            if response.status_code == 200 and response.json().get("ok"):
                bot_name = response.json()["result"]["username"]
                logger.info("Telegram bot connected: @%s", bot_name)
                return True
            return False
        except Exception as e:
            logger.error("Telegram connection test failed: %s", e)
            return False

    def __del__(self):
        """Close the session on garbage collection."""
        try:
            self._session.close()
        except Exception:
            pass
