"""
Safe API request utilities with retry logic, timeout handling, and validation.
Prevents API-related errors and resource leaks.
"""

import logging
import json
import httpx
import requests
from typing import Optional, Dict, Any, Callable, Tuple
from datetime import datetime, timedelta
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class APIRequestHandler:
    """
    Handles API requests with retry logic, timeout handling, and proper cleanup.
    """

    def __init__(
        self, max_retries: int = 3, backoff_factor: float = 1.0, timeout: int = 30
    ):
        """
        Initialize API request handler.

        Args:
            max_retries: Maximum number of retries
            backoff_factor: Backoff factor for exponential backoff
            timeout: Request timeout in seconds
        """
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.timeout = timeout
        self.session = self._create_session()

    def __enter__(self) -> "APIRequestHandler":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - cleanup."""
        self.close()

    def _create_session(self) -> requests.Session:
        """Create requests session with retry strategy."""
        session = requests.Session()

        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=self.backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            method_whitelist=["HEAD", "GET", "OPTIONS", "POST", "PUT", "DELETE"],
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        return session

    def get(
        self,
        url: str,
        params: Dict[str, Any] = None,
        headers: Dict[str, str] = None,
        validate_fn: Optional[Callable] = None,
    ) -> Tuple[bool, Any, Optional[str]]:
        """
        Make GET request with error handling.

        Returns:
            Tuple of (success, data, error_message)
        """
        try:
            response = self.session.get(
                url, params=params, headers=headers, timeout=self.timeout
            )
            return self._handle_response(response, validate_fn)

        except requests.exceptions.Timeout:
            error_msg = f"Timeout: Request to {url} timed out after {self.timeout}s"
            logger.error(error_msg)
            return False, None, error_msg
        except requests.exceptions.ConnectionError as e:
            error_msg = f"Connection error to {url}: {str(e)}"
            logger.error(error_msg)
            return False, None, error_msg
        except requests.exceptions.RequestException as e:
            error_msg = f"Request failed: {str(e)}"
            logger.error(error_msg)
            return False, None, error_msg
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(error_msg)
            return False, None, error_msg

    def post(
        self,
        url: str,
        data: Any = None,
        json_data: Dict[str, Any] = None,
        headers: Dict[str, str] = None,
        validate_fn: Optional[Callable] = None,
    ) -> Tuple[bool, Any, Optional[str]]:
        """
        Make POST request with error handling.

        Returns:
            Tuple of (success, data, error_message)
        """
        try:
            response = self.session.post(
                url, data=data, json=json_data, headers=headers, timeout=self.timeout
            )
            return self._handle_response(response, validate_fn)

        except requests.exceptions.Timeout:
            error_msg = f"Timeout: Request to {url} timed out after {self.timeout}s"
            logger.error(error_msg)
            return False, None, error_msg
        except requests.exceptions.ConnectionError as e:
            error_msg = f"Connection error to {url}: {str(e)}"
            logger.error(error_msg)
            return False, None, error_msg
        except requests.exceptions.RequestException as e:
            error_msg = f"Request failed: {str(e)}"
            logger.error(error_msg)
            return False, None, error_msg
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(error_msg)
            return False, None, error_msg

    def _handle_response(
        self, response: requests.Response, validate_fn: Optional[Callable] = None
    ) -> Tuple[bool, Any, Optional[str]]:
        """
        Handle API response with validation.

        Returns:
            Tuple of (success, data, error_message)
        """
        try:
            # Check HTTP status
            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                logger.error(error_msg)
                return False, None, error_msg

            # Try to parse JSON
            try:
                data = response.json()
            except json.JSONDecodeError as e:
                error_msg = f"Invalid JSON response: {e.msg}"
                logger.error(error_msg)
                return False, None, error_msg

            # Validate if function provided
            if validate_fn and not validate_fn(data):
                error_msg = "Response validation failed"
                logger.error(error_msg)
                return False, None, error_msg

            return True, data, None

        except Exception as e:
            error_msg = f"Error handling response: {str(e)}"
            logger.error(error_msg)
            return False, None, error_msg

    def close(self) -> None:
        """Close the session."""
        try:
            self.session.close()
        except Exception as e:
            logger.warning(f"Error closing session: {e}")


class HTTPXClientManager:
    """
    Manages httpx.Client lifecycle with proper context management and error handling.
    """

    def __init__(
        self, base_url: str, timeout: float = 30.0, headers: Dict[str, str] = None
    ):
        """
        Initialize httpx client manager.

        Args:
            base_url: Base URL for requests
            timeout: Request timeout
            headers: Default headers
        """
        self.base_url = base_url
        self.timeout = timeout
        self.headers = headers or {}
        self.client = None

    def __enter__(self) -> httpx.Client:
        """Context manager entry."""
        try:
            self.client = httpx.Client(
                base_url=self.base_url, timeout=self.timeout, headers=self.headers
            )
            return self.client
        except Exception as e:
            logger.error(f"Failed to create httpx client: {e}")
            raise

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - cleanup."""
        if self.client:
            try:
                self.client.close()
            except Exception as e:
                logger.warning(f"Error closing httpx client: {e}")

    @staticmethod
    def make_request(
        base_url: str, method: str = "GET", url: str = "", **kwargs
    ) -> Tuple[bool, Any, Optional[str]]:
        """
        Make request using context manager (automatic cleanup).

        Returns:
            Tuple of (success, data, error_message)
        """
        try:
            with HTTPXClientManager(
                base_url, timeout=kwargs.get("timeout", 30.0)
            ) as client:
                if method.upper() == "GET":
                    response = client.get(url)
                elif method.upper() == "POST":
                    response = client.post(url, json=kwargs.get("json"))
                else:
                    return False, None, f"Unsupported method: {method}"

                # Check status
                if response.status_code != 200:
                    return False, None, f"HTTP {response.status_code}"

                # Parse JSON
                try:
                    data = response.json()
                    return True, data, None
                except json.JSONDecodeError as e:
                    return False, None, f"Invalid JSON: {e.msg}"

        except Exception as e:
            return False, None, str(e)


# Helper functions for common operations


def safe_api_get(
    url: str, params: Dict[str, Any] = None, timeout: int = 30, max_retries: int = 3
) -> Tuple[bool, Any, Optional[str]]:
    """
    Make safe GET request with retries.

    Returns:
        Tuple of (success, data, error_message)
    """
    with APIRequestHandler(max_retries=max_retries, timeout=timeout) as handler:
        return handler.get(url, params=params)


def safe_api_post(
    url: str, json_data: Dict[str, Any] = None, timeout: int = 30, max_retries: int = 3
) -> Tuple[bool, Any, Optional[str]]:
    """
    Make safe POST request with retries.

    Returns:
        Tuple of (success, data, error_message)
    """
    with APIRequestHandler(max_retries=max_retries, timeout=timeout) as handler:
        return handler.post(url, json_data=json_data)


def safe_httpx_get(
    base_url: str, url: str = "", timeout: float = 30.0
) -> Tuple[bool, Any, Optional[str]]:
    """
    Make safe httpx GET request with automatic cleanup.

    Returns:
        Tuple of (success, data, error_message)
    """
    return HTTPXClientManager.make_request(base_url, "GET", url, timeout=timeout)


def safe_httpx_post(
    base_url: str,
    url: str = "",
    json_data: Dict[str, Any] = None,
    timeout: float = 30.0,
) -> Tuple[bool, Any, Optional[str]]:
    """
    Make safe httpx POST request with automatic cleanup.

    Returns:
        Tuple of (success, data, error_message)
    """
    return HTTPXClientManager.make_request(
        base_url, "POST", url, json=json_data, timeout=timeout
    )
