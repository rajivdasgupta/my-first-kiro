"""FinXCloud Web UI — Authentication module.

Simple JWT-based session auth with configurable credentials via env vars.
Supports role-based access control (RBAC) with admin, analyst, and viewer roles.
User store backed by ~/.finxcloud/users.json.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
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

VALID_ROLES = ("admin", "analyst", "viewer")

USERS_PATH = Path(
    os.environ.get(
        "FINXCLOUD_USERS_PATH",
        str(Path.home() / ".finxcloud" / "users.json"),
    )
)

__all__ = [
    "authenticate",
    "require_auth",
    "require_role",
    "create_token",
    "decode_token",
    "verify_password",
    "hash_password_for_static",
    "is_using_default_credentials",
    "list_users",
    "create_user",
    "delete_user",
    "get_user_role",
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


# ---------------------------------------------------------------------------
# Password hashing (SHA-256 — demo only)
# ---------------------------------------------------------------------------

def _hash_password(password: str) -> str:
    """SHA-256 hash of a password for the user store."""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(plain: str, expected: str) -> bool:
    """Constant-time comparison of plaintext password against expected."""
    return hmac.compare_digest(plain.encode(), expected.encode())


def hash_password_for_static(password: str) -> str:
    """SHA-256 hash of a password for embedding in static HTML gate."""
    return hashlib.sha256(password.encode()).hexdigest()


# ---------------------------------------------------------------------------
# User store (JSON file)
# ---------------------------------------------------------------------------

def _load_users() -> list[dict]:
    """Load users from the JSON file. Returns empty list if missing."""
    if not USERS_PATH.exists():
        return []
    try:
        data = json.loads(USERS_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        logger.warning("Failed to read users file at %s", USERS_PATH)
        return []


def _save_users(users: list[dict]) -> None:
    """Persist users list to the JSON file."""
    USERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    USERS_PATH.write_text(
        json.dumps(users, indent=2, default=str),
        encoding="utf-8",
    )


def list_users() -> list[dict]:
    """Return all users without password hashes."""
    return [
        {k: v for k, v in u.items() if k != "password_hash"}
        for u in _load_users()
    ]


def create_user(username: str, password: str, role: str) -> dict:
    """Create a new user. Raises ValueError on duplicate or invalid role."""
    if role not in VALID_ROLES:
        raise ValueError(f"Invalid role: {role}. Must be one of {VALID_ROLES}")
    if not username or not password:
        raise ValueError("Username and password are required")

    users = _load_users()
    if any(u["username"] == username for u in users):
        raise ValueError(f"User '{username}' already exists")

    user = {
        "username": username,
        "password_hash": _hash_password(password),
        "role": role,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    users.append(user)
    _save_users(users)
    return {k: v for k, v in user.items() if k != "password_hash"}


def delete_user(username: str) -> bool:
    """Delete a user by username. Returns True if deleted."""
    users = _load_users()
    filtered = [u for u in users if u["username"] != username]
    if len(filtered) == len(users):
        return False
    _save_users(filtered)
    return True


def get_user_role(username: str) -> str:
    """Get the role for a username. Returns 'admin' for env-var admin fallback."""
    users = _load_users()
    for u in users:
        if u["username"] == username:
            return u.get("role", "viewer")
    # Env-var admin fallback
    if username == ADMIN_USERNAME:
        return "admin"
    return "viewer"


# ---------------------------------------------------------------------------
# JWT tokens
# ---------------------------------------------------------------------------

def create_token(username: str, role: str | None = None) -> str:
    """Create a JWT token for an authenticated user, including their role."""
    if role is None:
        role = get_user_role(username)
    payload = {
        "sub": username,
        "role": role,
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


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def authenticate(username: str, password: str) -> Optional[str]:
    """Validate credentials and return a JWT token, or None on failure.

    Checks users.json first. Falls back to env-var admin if no users exist.
    Returns None when default credentials are still active and no users.json users.
    """
    # Check users.json first
    users = _load_users()
    for u in users:
        if u["username"] == username:
            if hmac.compare_digest(_hash_password(password), u["password_hash"]):
                return create_token(username, u.get("role", "viewer"))
            return None

    # Fallback to env-var admin if users.json is empty
    if not users:
        if is_using_default_credentials():
            return None
        if username == ADMIN_USERNAME and verify_password(password, ADMIN_PASSWORD):
            return create_token(username, "admin")

    return None


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------

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


def require_role(*roles: str):
    """FastAPI dependency factory: require the user to have one of the given roles.

    Usage:
        @app.get("/admin-only", dependencies=[Depends(require_role("admin"))])
    """
    async def _check_role(request: Request) -> dict:
        payload = await require_auth(request)
        user_role = payload.get("role", "viewer")
        if user_role not in roles:
            raise HTTPException(
                status_code=403,
                detail=f"Role '{user_role}' is not authorized. Required: {', '.join(roles)}",
            )
        return payload
    return _check_role
