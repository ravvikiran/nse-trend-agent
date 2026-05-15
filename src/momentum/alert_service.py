"""Abstract AlertService interface for the NSE Momentum Scanner.

Defines the contract for all alert delivery implementations.
Allows AlertFormatter to work with any notification backend
(Telegram, Slack, email, etc.) without tight coupling.
"""

from abc import ABC, abstractmethod


class AlertService(ABC):
    """Abstract interface for alert delivery.

    All concrete alert service implementations must implement these methods
    to deliver formatted messages to users.
    """

    @abstractmethod
    def send_message(self, text: str, parse_mode: str = "Markdown") -> bool:
        """Send a formatted message to the configured destination.

        Args:
            text: Message text (supports formatting based on parse_mode).
            parse_mode: Format mode — 'Markdown' or 'HTML'.

        Returns:
            True if sent successfully, False otherwise.
        """
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """Test the connection to the alert service.

        Returns:
            True if the service is reachable and configured correctly.
        """
        pass
