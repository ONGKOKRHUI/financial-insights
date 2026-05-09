"""JWT utilities for FinSight authentication.

Token strategy
--------------
- **Access token** — short-lived (15 minutes), sent as an HttpOnly cookie named
  ``access_token``.  Contains ``sub`` (user email) and ``role``.
- **Refresh token** — long-lived (7 days), sent as an HttpOnly cookie named
  ``refresh_token``.  Contains only ``sub``; its hash is persisted in the DB so
  it can be revoked server-side on logout or compromise.

Environment variables required
-------------------------------
- ``SECRET_KEY``  — random 32-byte hex string; **must** be set in production.
- ``ALGORITHM``   — JWT signing algorithm (default: ``HS256``).
"""

import os
import secrets
import logging
from datetime import datetime, timedelta
from typing import Optional

from dotenv import find_dotenv, load_dotenv
from jose import JWTError, jwt

load_dotenv(find_dotenv())

logger = logging.getLogger(__name__)

_environment = os.getenv("ENVIRONMENT", os.getenv("ENV", "development")).strip().lower()
_is_production = _environment in {"prod", "production"}
_configured_secret = os.getenv("SECRET_KEY", "").strip()

if _configured_secret:
    SECRET_KEY: str = _configured_secret
elif _is_production:
    raise RuntimeError("SECRET_KEY must be set in production.")
else:
    # Avoid predictable fallback secrets in non-production environments.
    SECRET_KEY = secrets.token_hex(32)
    logger.warning("SECRET_KEY is not set; generated ephemeral development secret.")

ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
REFRESH_TOKEN_EXPIRE_DAYS: int = 7


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT access token.

    Args:
        data: Payload dict — must include ``sub`` (user email) and ``role``.
        expires_delta: Override the default 15-minute TTL.

    Returns:
        Encoded JWT string.
    """
    payload = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    payload.update({"exp": expire, "type": "access"})
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> str:
    """Create a signed JWT refresh token (7-day TTL).

    Args:
        data: Payload dict — must include ``sub`` (user email).

    Returns:
        Encoded JWT string.
    """
    payload = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload.update({"exp": expire, "type": "refresh"})
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and verify a JWT token.

    Args:
        token: Raw JWT string from a cookie or header.

    Returns:
        Decoded payload dict.

    Raises:
        JWTError: If the token is expired, malformed, or has an invalid signature.
    """
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


def is_access_token(payload: dict) -> bool:
    """Return True if the decoded payload belongs to an access token.

    Args:
        payload: Decoded JWT payload dict.

    Returns:
        True when ``payload["type"] == "access"``.
    """
    return payload.get("type") == "access"


def is_refresh_token(payload: dict) -> bool:
    """Return True if the decoded payload belongs to a refresh token.

    Args:
        payload: Decoded JWT payload dict.

    Returns:
        True when ``payload["type"] == "refresh"``.
    """
    return payload.get("type") == "refresh"
