"""FinXCloud Web UI — Authentication module.

Simple JWT-based session auth with configurable credentials via env vars.
PoC-appropriate: no database, no OAuth — just username/password + JWT tokens.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
import time
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import jwt
except ImportError:
    raise ImportError(
        "PyJWT is required for the web module. "
        "Install it with: pip install finxcloud[web]"
    )
from fastapi import Cookie, HTTPException, Request

# Config via env vars (defaults for local dev)
ADMIN_USERNAME = os.environ.get("FINXCLOUD_ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("FINXCLOUD_ADMIN_PASS", "admin")
JWT_SECRET = os.environ.get("FINXCLOUD_JWT_SECRET", secrets.token_hex(32))
JWT_EXPIRY_HOURS = int(os.environ.get("FINXCLOUD_JWT_EXPIRY_HOURS", "24"))

__all__ = [
    "authenticate",
    "require_auth",
    "create_token",
    "decode_token",
    "verify_password",
    "hash_password_for_static",
    "is_using_default_credentials",
]


def is_using_default_credentials() -> bool:
    """Return True when both ADMIN_USERNAME and ADMIN_PASSWORD are 'admin'."""
    return ADMIN_USERNAME == "admin" and ADMIN_PASSWORD == "admin"


def check_default_credentials_startup() -> None:
    """Log a warning at startup if default credentials are still in use."""
    if is_using_default_credentials():
        logger.warning(
            "Default admin credentials detected. "
            "Set FINXCLOUD_ADMIN_USER and FINXCLOUD_ADMIN_PASS environment "
            "variables before running in production."
        )


# Run credential check at module load
check_default_credentials_startup()


def verify_password(plain: str, expected: str) -> bool:
    """Constant-time comparison of plaintext password against expected."""
    return hmac.compare_digest(plain.encode(), expected.encode())


def create_token(username: str) -> str:
    """Create a JWT token for an authenticated user."""
    payload = {
        "sub": username,
        "iat": int(time.time()),
        "exp": int(time.time()) + JWT_EXPIRY_HOURS * 3600,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT token. Returns payload or None."""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


def authenticate(username: str, password: str) -> Optional[str]:
    """Validate credentials and return a JWT token, or None on failure.

    Returns None when default credentials are still active, forcing the
    operator to configure custom credentials via environment variables.
    """
    if is_using_default_credentials():
        return None
    if username == ADMIN_USERNAME and verify_password(password, ADMIN_PASSWORD):
        return create_token(username)
    return None


async def require_auth(request: Request) -> dict:
    """FastAPI dependency: extract and validate auth from cookie or header.

    Raises HTTPException 401 if not authenticated.
    """
    token = None

    # Check Authorization header first
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]

    # Fall back to cookie
    if not token:
        token = request.cookies.get("finxcloud_token")

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return payload


def hash_password_for_static(password: str) -> str:
    """SHA-256 hash of a password for embedding in static HTML gate."""
    return hashlib.sha256(password.encode()).hexdigest()
