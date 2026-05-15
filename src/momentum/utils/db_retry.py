"""Database retry utility for SQLite operations.

Provides a decorator and context manager for retrying SQLite operations
that may fail with 'database is locked' errors under concurrent access.
"""

import logging
import sqlite3
import time
from functools import wraps
from typing import Callable, TypeVar

logger = logging.getLogger(__name__)

# Default retry configuration
MAX_RETRIES = 3
BASE_DELAY_SECONDS = 0.1  # 100ms initial delay
MAX_DELAY_SECONDS = 2.0

T = TypeVar("T")


def retry_on_lock(
    max_retries: int = MAX_RETRIES,
    base_delay: float = BASE_DELAY_SECONDS,
    max_delay: float = MAX_DELAY_SECONDS,
) -> Callable:
    """Decorator that retries a function on sqlite3.OperationalError (database locked).

    Uses exponential backoff between retries.

    Args:
        max_retries: Maximum number of retry attempts.
        base_delay: Initial delay in seconds before first retry.
        max_delay: Maximum delay between retries.

    Returns:
        Decorated function with retry logic.
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except sqlite3.OperationalError as e:
                    if "database is locked" in str(e) or "locked" in str(e):
                        last_error = e
                        if attempt < max_retries:
                            delay = min(base_delay * (2 ** attempt), max_delay)
                            logger.debug(
                                "Database locked, retrying in %.2fs (attempt %d/%d): %s",
                                delay,
                                attempt + 1,
                                max_retries,
                                func.__name__,
                            )
                            time.sleep(delay)
                        else:
                            logger.error(
                                "Database locked after %d retries: %s",
                                max_retries,
                                func.__name__,
                            )
                    else:
                        # Not a lock error — re-raise immediately
                        raise

            # All retries exhausted
            raise last_error  # type: ignore[misc]

        return wrapper

    return decorator
