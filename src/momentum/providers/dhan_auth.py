"""
Dhan automatic token renewal using PIN + TOTP.

Generates a fresh access token daily using Dhan's DhanLogin class.
Designed for headless deployment (Railway, VPS) where manual login isn't possible.

Environment variables required:
    DHAN_CLIENT_ID: Your Dhan client ID
    DHAN_PIN: Your Dhan trading PIN (4-6 digits)
    DHAN_TOTP_SECRET: Your TOTP secret key (from authenticator app setup)

The TOTP secret is the base32-encoded key you get when setting up 2FA.
If you used a QR code, you can extract the secret from the otpauth:// URL.
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


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


def renew_dhan_token() -> Optional[str]:
    """Generate a fresh Dhan access token using PIN + TOTP.

    Reads credentials from environment variables and uses Dhan's
    DhanLogin.generate_token() method to get a new access token.

    Returns:
        New access token string, or None if renewal failed.
    """
    client_id = os.environ.get("DHAN_CLIENT_ID")
    pin = os.environ.get("DHAN_PIN")
    totp_secret = os.environ.get("DHAN_TOTP_SECRET")

    if not client_id:
        logger.error("DHAN_CLIENT_ID not set. Cannot renew token.")
        return None

    if not pin:
        logger.error("DHAN_PIN not set. Cannot renew token.")
        return None

    if not totp_secret:
        logger.error("DHAN_TOTP_SECRET not set. Cannot renew token.")
        return None

    try:
        from dhanhq import DhanLogin
    except ImportError:
        logger.error(
            "dhanhq package not installed. Install with: pip install dhanhq"
        )
        return None

    try:
        # Generate current TOTP code
        totp_code = generate_totp(totp_secret)
        logger.debug("Generated TOTP code for token renewal")

        # Use DhanLogin to generate a fresh token
        dhan_login = DhanLogin(client_id)
        token_data = dhan_login.generate_token(pin, totp_code)

        if token_data is None:
            logger.error("Dhan token renewal returned None")
            return None

        # Extract access token from response
        # Dhan API returns camelCase keys (e.g. "accessToken")
        # but handle snake_case too for forward compatibility
        if isinstance(token_data, dict):
            # Check for rate-limit or error response
            if token_data.get("status") == "error":
                msg = token_data.get("message", "Unknown error")
                logger.warning("Dhan token generation rate-limited or failed: %s", msg)
                # Return existing token if available (it's still valid)
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
        elif isinstance(token_data, str):
            access_token = token_data
        else:
            logger.error("Unexpected token response format: %s", type(token_data))
            return None

        if not access_token:
            logger.error("No access_token in Dhan response: %s", token_data)
            return None

        # Update the environment variable so the provider picks it up
        os.environ["DHAN_ACCESS_TOKEN"] = access_token
        logger.info("Dhan access token renewed successfully")
        return access_token

    except Exception as e:
        logger.error("Dhan token renewal failed: %s", e)
        return None
