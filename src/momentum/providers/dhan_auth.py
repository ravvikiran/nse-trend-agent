"""
Dhan automatic token renewal using PIN + TOTP.

Generates a fresh access token daily using Dhan's DhanLogin class.
Designed for headless deployment (Railway, VPS) where manual login isn't possible.

Token caching strategy:
    - Tokens are cached in data/dhan_token.json with their expiry time.
    - On startup, the cached token is loaded and reused if still valid.
    - A new token is only generated when the cached one has expired.
    - This avoids Dhan's rate-limit ("Token can be generated once every 2 minutes")
      and unnecessary API calls.

Environment variables required:
    DHAN_CLIENT_ID: Your Dhan client ID
    DHAN_PIN: Your Dhan trading PIN (4-6 digits)
    DHAN_TOTP_SECRET: Your TOTP secret key (from authenticator app setup)

The TOTP secret is the base32-encoded key you get when setting up 2FA.
If you used a QR code, you can extract the secret from the otpauth:// URL.
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Token cache file location
# Try data/ first (project dir), fall back to /tmp for ephemeral environments like Railway
_PROJECT_DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"
_TMP_CACHE_FILE = Path("/tmp/dhan_token.json")


def _get_token_cache_path() -> Path:
    """Get the best available path for token caching.

    Prefers the project's data/ directory, falls back to /tmp.
    """
    try:
        _PROJECT_DATA_DIR.mkdir(parents=True, exist_ok=True)
        # Test if writable
        test_file = _PROJECT_DATA_DIR / ".write_test"
        test_file.touch()
        test_file.unlink()
        return _PROJECT_DATA_DIR / "dhan_token.json"
    except OSError:
        return _TMP_CACHE_FILE

# IST timezone
_IST = timezone(timedelta(hours=5, minutes=30))


def generate_totp(secret: str) -> str:
    """Generate a TOTP code from the secret key.

    Uses the pyotp library to generate a time-based one-time password.

    Args:
        secret: Base32-encoded TOTP secret key.

    Returns:
        6-digit TOTP code as a string.
    """
    try:
        import pyotp
    except ImportError:
        raise ImportError(
            "pyotp package required for TOTP generation. "
            "Install with: pip install pyotp"
        )

    totp = pyotp.TOTP(secret)
    return totp.now()


def _load_cached_token() -> Optional[dict]:
    """Load the cached token from disk.

    Returns:
        Dict with 'access_token' and 'expiry_time' keys, or None if
        no valid cache exists.
    """
    try:
        cache_path = _get_token_cache_path()
        if not cache_path.exists():
            return None

        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not data.get("access_token") or not data.get("expiry_time"):
            return None

        return data
    except (json.JSONDecodeError, OSError) as e:
        logger.debug("Could not read token cache: %s", e)
        return None


def _save_token_cache(access_token: str, expiry_time: str) -> None:
    """Save the token to the cache file.

    Args:
        access_token: The JWT access token.
        expiry_time: ISO format expiry timestamp from Dhan response.
    """
    try:
        cache_path = _get_token_cache_path()
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_data = {
            "access_token": access_token,
            "expiry_time": expiry_time,
            "cached_at": datetime.now(_IST).isoformat(),
        }
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, indent=2)
        logger.debug("Token cached to %s", cache_path)
    except OSError as e:
        logger.warning("Could not save token cache: %s", e)


def _is_token_valid(cached: dict) -> bool:
    """Check if a cached token is still valid (not expired).

    Considers the token expired 30 minutes before actual expiry
    to provide a safety buffer.

    Args:
        cached: Dict with 'expiry_time' key (ISO format string).

    Returns:
        True if the token is still valid, False if expired or unparseable.
    """
    try:
        expiry_str = cached["expiry_time"]
        # Dhan returns expiry like "2026-05-12T13:23:03.753"
        # Parse it — assume IST if no timezone info
        expiry = datetime.fromisoformat(expiry_str)
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=_IST)

        # Add 30-minute safety buffer before expiry
        now = datetime.now(_IST)
        buffer = timedelta(minutes=30)

        if now < (expiry - buffer):
            remaining = expiry - now
            logger.debug("Cached token valid for %.1f more hours", remaining.total_seconds() / 3600)
            return True
        else:
            logger.debug("Cached token expired or expiring soon")
            return False
    except (ValueError, KeyError) as e:
        logger.debug("Could not parse token expiry: %s", e)
        return False


def renew_dhan_token() -> Optional[str]:
    """Get a valid Dhan access token, using cache if available.

    Strategy:
    1. Check if a cached token exists and is still valid → use it.
    2. If no valid cache, generate a new token via PIN + TOTP.
    3. Save the new token to cache for future use.

    Returns:
        Access token string, or None if unavailable.
    """
    client_id = os.environ.get("DHAN_CLIENT_ID")
    pin = os.environ.get("DHAN_PIN")
    totp_secret = os.environ.get("DHAN_TOTP_SECRET")

    if not client_id:
        logger.error("DHAN_CLIENT_ID not set. Cannot renew token.")
        return None

    # Step 1: Try to use cached token
    cached = _load_cached_token()
    if cached and _is_token_valid(cached):
        access_token = cached["access_token"]
        os.environ["DHAN_ACCESS_TOKEN"] = access_token
        logger.info("Using cached Dhan access token (still valid)")
        return access_token

    # Step 2: Need a fresh token — check credentials
    if not pin:
        logger.error("DHAN_PIN not set. Cannot generate new token.")
        # Fall back to existing env token if available
        existing = os.environ.get("DHAN_ACCESS_TOKEN")
        if existing:
            logger.info("Using existing DHAN_ACCESS_TOKEN from environment")
            return existing
        return None

    if not totp_secret:
        logger.error("DHAN_TOTP_SECRET not set. Cannot generate new token.")
        existing = os.environ.get("DHAN_ACCESS_TOKEN")
        if existing:
            logger.info("Using existing DHAN_ACCESS_TOKEN from environment")
            return existing
        return None

    try:
        from dhanhq import DhanLogin
    except ImportError:
        logger.error(
            "dhanhq package not installed. Install with: pip install dhanhq"
        )
        return None

    # Step 3: Generate a new token
    try:
        totp_code = generate_totp(totp_secret)
        logger.debug("Generated TOTP code for token renewal")

        dhan_login = DhanLogin(client_id)
        token_data = dhan_login.generate_token(pin, totp_code)

        if token_data is None:
            logger.error("Dhan token renewal returned None")
            return None

        # Handle response
        if isinstance(token_data, dict):
            # Check for rate-limit or error response
            if token_data.get("status") == "error":
                msg = token_data.get("message", "Unknown error")
                logger.warning("Dhan token generation failed: %s", msg)
                # Return existing token if available
                existing = os.environ.get("DHAN_ACCESS_TOKEN")
                if existing:
                    logger.info("Using existing access token (still valid)")
                    return existing
                return None

            access_token = (
                token_data.get("accessToken")
                or token_data.get("access_token")
                or token_data.get("data", {}).get("accessToken")
                or token_data.get("data", {}).get("access_token")
            )
            # Extract expiry time from response
            expiry_time = (
                token_data.get("expiryTime")
                or token_data.get("expiry_time")
                or token_data.get("data", {}).get("expiryTime")
            )
        elif isinstance(token_data, str):
            access_token = token_data
            # No expiry info available — assume 24 hours from now
            expiry_time = (datetime.now(_IST) + timedelta(hours=24)).isoformat()
        else:
            logger.error("Unexpected token response format: %s", type(token_data))
            return None

        if not access_token:
            logger.error("No access_token in Dhan response: %s", token_data)
            return None

        # Default expiry if not provided (24 hours from now)
        if not expiry_time:
            expiry_time = (datetime.now(_IST) + timedelta(hours=24)).isoformat()

        # Step 4: Cache the token and update environment
        _save_token_cache(access_token, expiry_time)
        os.environ["DHAN_ACCESS_TOKEN"] = access_token
        logger.info("Dhan access token renewed and cached (expires: %s)", expiry_time)
        return access_token

    except Exception as e:
        logger.error("Dhan token renewal failed: %s", e)
        return None
