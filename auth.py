"""
Apple Tree Purchase Tracker - Simple PIN Authentication
HMAC-signed tokens with expiration, no external JWT dependency.
"""

import os
import hashlib
import hmac
import time
import secrets


# Default PIN for development; override via APP_PIN or APP_PIN_HASH env var
DEFAULT_PIN = "1234"
TOKEN_EXPIRY_SECONDS = 86400  # 24 hours


def _get_secret() -> str:
    """Get or auto-generate the token signing secret."""
    secret = os.getenv("JWT_SECRET")
    if not secret:
        # Generate a stable secret from APP_PIN so tokens survive restarts
        pin = os.getenv("APP_PIN", DEFAULT_PIN)
        secret = hashlib.sha256(f"apple-tree-{pin}-secret".encode()).hexdigest()
    return secret


def verify_pin(pin: str) -> bool:
    """
    Check PIN against APP_PIN_HASH (sha256) or APP_PIN env var.
    Uses constant-time comparison to prevent timing attacks.
    """
    pin_hash_env = os.getenv("APP_PIN_HASH")
    if pin_hash_env:
        pin_hash = hashlib.sha256(pin.encode()).hexdigest()
        return hmac.compare_digest(pin_hash, pin_hash_env.lower())

    expected_pin = os.getenv("APP_PIN", DEFAULT_PIN)
    return hmac.compare_digest(pin, expected_pin)


def create_token() -> str:
    """
    Create an HMAC-signed token with embedded expiration timestamp.
    Format: <expiry_timestamp>.<hmac_signature>
    """
    secret = _get_secret()
    expiry = int(time.time()) + TOKEN_EXPIRY_SECONDS
    payload = str(expiry)
    signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def verify_token(token: str) -> bool:
    """
    Verify an HMAC-signed token and check expiration.
    """
    if not token:
        return False

    parts = token.split(".")
    if len(parts) != 2:
        return False

    payload, signature = parts
    secret = _get_secret()

    # Verify signature
    expected_sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected_sig):
        return False

    # Check expiration
    try:
        expiry = int(payload)
        return time.time() < expiry
    except ValueError:
        return False
