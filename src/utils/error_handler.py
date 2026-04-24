"""
Error handling utilities and custom exceptions.
Provides decorators, exception classes, and error handling patterns
to prevent common issues throughout the codebase.
"""

import logging
import functools
import traceback
import json
from typing import Callable, Any, TypeVar, Optional, Dict
from datetime import datetime

logger = logging.getLogger(__name__)

# Type variables for generic functions
T = TypeVar('T')
F = TypeVar('F', bound=Callable[..., Any])


class AppError(Exception):
    """Base application exception."""
    pass


class ConfigError(AppError):
    """Configuration-related error."""
    pass


class DataValidationError(AppError):
    """Data validation error."""
    pass


class FileOperationError(AppError):
    """File operation error."""
    pass


class APIError(AppError):
    """API/Network operation error."""
    pass


class JSONParseError(AppError):
    """JSON parsing error with context."""
    pass


def handle_exceptions(
    logger_instance: logging.Logger = None,
    default_return: Any = None,
    exc_types: tuple = (Exception,),
    reraise: bool = False
) -> Callable[[F], F]:
    """
    Decorator to handle exceptions in a consistent way.
    
    Args:
        logger_instance: Logger to use (defaults to module logger)
        default_return: Value to return on exception
        exc_types: Tuple of exception types to catch
        reraise: Whether to re-raise the exception after logging
    
    Example:
        @handle_exceptions(exc_types=(ValueError, KeyError), default_return={})
        def parse_data(data):
            return json.loads(data)
    """
    if logger_instance is None:
        logger_instance = logger
    
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
            except exc_types as e:
                logger_instance.error(
                    f"{func.__name__} raised {type(e).__name__}: {str(e)}",
                    extra={'stack_trace': traceback.format_exc()}
                )
                if reraise:
                    raise
                return default_return
        return wrapper
    return decorator


def safe_dict_get(data: Dict, *keys: str, default: Any = None) -> Any:
    """
    Safely get nested dict values with validation.
    
    Args:
        data: Dictionary to get from
        *keys: Nested keys to traverse
        default: Default value if key not found
    
    Returns:
        Value at nested key or default
    
    Example:
        value = safe_dict_get(response, 'data', 'items', 0, 'name', default='Unknown')
    """
    if not isinstance(data, dict):
        return default
    
    current = data
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        elif isinstance(current, (list, tuple)) and isinstance(key, int):
            try:
                current = current[key]
            except (IndexError, TypeError):
                return default
        else:
            return default
    
    return current


def validate_type(value: Any, expected_type: type, param_name: str = "value") -> bool:
    """
    Validate that a value is of expected type, log error if not.
    
    Args:
        value: Value to validate
        expected_type: Expected type
        param_name: Name of parameter for error message
    
    Returns:
        True if valid, False otherwise
    
    Example:
        if not validate_type(symbol, str, "symbol"):
            return False
    """
    if not isinstance(value, expected_type):
        logger.error(
            f"Invalid type for {param_name}: expected {expected_type.__name__}, "
            f"got {type(value).__name__}"
        )
        return False
    return True


def safe_json_parse(json_str: str, default: Any = None) -> Any:
    """
    Safely parse JSON string with detailed error logging.
    
    Args:
        json_str: JSON string to parse
        default: Default value on parse failure
    
    Returns:
        Parsed JSON or default
    """
    if not isinstance(json_str, str):
        logger.error(f"Expected string for JSON parsing, got {type(json_str).__name__}")
        return default
    
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.error(
            f"JSON decode error at position {e.pos}: {e.msg}",
            extra={'snippet': json_str[max(0, e.pos-20):e.pos+20]}
        )
        return default
    except Exception as e:
        logger.error(f"Unexpected error parsing JSON: {e}")
        return default


def extract_json_from_text(text: str, default: Any = None) -> Any:
    """
    Extract JSON object from text (useful for LLM responses).
    
    Args:
        text: Text containing JSON
        default: Default value if no JSON found or parse fails
    
    Returns:
        Parsed JSON or default
    """
    if not isinstance(text, str):
        logger.warning(f"Expected string, got {type(text).__name__}")
        return default
    
    text = text.strip()
    
    # Try to find JSON object in text
    start = text.find('{')
    end = text.rfind('}') + 1
    
    if start < 0 or end <= start:
        logger.warning(f"No JSON object found in text: {text[:100]}")
        return default
    
    json_str = text[start:end]
    return safe_json_parse(json_str, default)


def log_error_context(error: Exception, context: Dict[str, Any] = None) -> None:
    """
    Log error with detailed context information.
    
    Args:
        error: Exception to log
        context: Additional context information
    """
    error_info = {
        'error_type': type(error).__name__,
        'error_message': str(error),
        'timestamp': datetime.now().isoformat(),
        'stack_trace': traceback.format_exc()
    }
    
    if context:
        error_info['context'] = context
    
    logger.error(f"Error occurred: {json.dumps(error_info, indent=2)}")


def safe_cast(value: Any, target_type: type, default: Any = None) -> Any:
    """
    Safely cast value to target type.
    
    Args:
        value: Value to cast
        target_type: Type to cast to
        default: Default if cast fails
    
    Returns:
        Casted value or default
    """
    try:
        if target_type == bool and isinstance(value, str):
            return value.lower() in ('true', 'yes', '1', 'on')
        return target_type(value)
    except (ValueError, TypeError):
        logger.warning(f"Cannot cast {value} to {target_type.__name__}")
        return default


class ErrorCounter:
    """Track error frequencies to detect persistent issues."""
    
    def __init__(self):
        self.errors: Dict[str, int] = {}
        self.last_reset = datetime.now()
    
    def increment(self, error_key: str) -> int:
        """Increment error counter and return new count."""
        self.errors[error_key] = self.errors.get(error_key, 0) + 1
        return self.errors[error_key]
    
    def get_count(self, error_key: str) -> int:
        """Get current error count."""
        return self.errors.get(error_key, 0)
    
    def alert_if_threshold(
        self,
        error_key: str,
        threshold: int = 5,
        alert_level: str = "warning"
    ) -> bool:
        """Alert if error count exceeds threshold."""
        count = self.increment(error_key)
        if count >= threshold:
            log_func = getattr(logger, alert_level.lower(), logger.warning)
            log_func(f"Error '{error_key}' exceeded threshold: {count} times")
            return True
        return False
    
    def reset(self) -> None:
        """Reset all counters."""
        self.errors.clear()
        self.last_reset = datetime.now()
    
    def summary(self) -> Dict[str, int]:
        """Get summary of all errors."""
        return self.errors.copy()


# Global error counter
error_counter = ErrorCounter()
