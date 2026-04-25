"""Password hashing and generation utilities for FinSight.

All passwords are hashed with bcrypt before storage.
The ``generate_secure_password`` helper is used during the Phase 4
registration flow, where the system generates a strong password on
behalf of the user and displays it exactly once in the UI.
"""

import hashlib
import secrets

import bcrypt


def hash_password(plain: str) -> str:
    """Hash a plain-text password with bcrypt.

    Args:
        plain: The raw password string supplied by the user.

    Returns:
        bcrypt hash string suitable for storage.
    """
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain-text password against a stored bcrypt hash.

    Args:
        plain:  The raw password supplied at login.
        hashed: The stored bcrypt hash from the database.

    Returns:
        True if the password matches, False otherwise.
    """
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def generate_secure_password(length: int = 20) -> str:
    """Generate a cryptographically secure random password.

    Uses ``secrets.token_urlsafe`` which draws from the OS CSPRNG and
    produces URL-safe base64 characters (A-Z, a-z, 0-9, -, _).

    Args:
        length: Desired minimum byte length before base64 encoding
                (actual string will be slightly longer).

    Returns:
        A random password string at least ``length`` characters long.
    """
    return secrets.token_urlsafe(length)


def hash_api_key(raw_key: str) -> str:
    """Produce a SHA-256 hex digest of a raw API key for storage.

    We use SHA-256 (not bcrypt) for API keys because:
    - API keys are already cryptographically random (256-bit entropy).
    - bcrypt's intentional slowness is unnecessary when the input has
      high entropy and there is no user-chosen weakness to protect.
    - Fast lookup is required on every authenticated API request.

    Args:
        raw_key: The plain-text API key string.

    Returns:
        64-character lowercase hex SHA-256 digest.
    """
    return hashlib.sha256(raw_key.encode()).hexdigest()


def generate_api_key() -> tuple[str, str, str]:
    """Generate a new developer API key.

    Returns:
        A tuple of ``(raw_key, key_hash, key_prefix)`` where:
        - ``raw_key``    is the full key returned to the user once.
        - ``key_hash``   is the SHA-256 digest to store in the DB.
        - ``key_prefix`` is the first 8 characters for display purposes.
    """
    raw_key = "fsk_" + secrets.token_urlsafe(32)
    key_hash = hash_api_key(raw_key)
    key_prefix = raw_key[:8]
    return raw_key, key_hash, key_prefix
