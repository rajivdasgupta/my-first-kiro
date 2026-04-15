"""Tests for finxcloud.web.auth module.

The auth module reads env vars at import time into module-level constants,
so we monkeypatch os.environ *before* reloading the module for each test
that needs non-default credentials.
"""

import importlib
import os


_TEST_SECRET = "a]k9Xp2!mR7wQ4vL0nB8cY6dF3hJ5tG1"  # 32-byte test-only key


def _reload_auth(monkeypatch, *, user="admin", password="admin", secret=_TEST_SECRET):
    """Set env vars and reload the auth module so constants pick them up."""
    monkeypatch.setenv("FINXCLOUD_ADMIN_USER", user)
    monkeypatch.setenv("FINXCLOUD_ADMIN_PASS", password)
    monkeypatch.setenv("FINXCLOUD_JWT_SECRET", secret)
    import finxcloud.web.auth as auth_mod
    importlib.reload(auth_mod)
    return auth_mod


# -- is_using_default_credentials ------------------------------------------

def test_default_credentials_detected(monkeypatch):
    """Returns True when user/pass are both 'admin'."""
    auth = _reload_auth(monkeypatch, user="admin", password="admin")
    assert auth.is_using_default_credentials() is True


def test_custom_credentials_not_default(monkeypatch):
    """Returns False when env vars override the defaults."""
    auth = _reload_auth(monkeypatch, user="ops", password="s3cure!")
    assert auth.is_using_default_credentials() is False


# -- authenticate -----------------------------------------------------------

def test_authenticate_rejects_default_credentials(monkeypatch):
    """authenticate() returns None when defaults are still active."""
    auth = _reload_auth(monkeypatch, user="admin", password="admin")
    assert auth.authenticate("admin", "admin") is None


def test_authenticate_accepts_custom_credentials(monkeypatch):
    """authenticate() returns a JWT string for valid custom credentials."""
    auth = _reload_auth(monkeypatch, user="ops", password="s3cure!")
    token = auth.authenticate("ops", "s3cure!")
    assert isinstance(token, str)
    assert len(token) > 0


# -- create_token / decode_token round-trip ---------------------------------

def test_token_round_trip(monkeypatch):
    """A token created by create_token() can be decoded back."""
    auth = _reload_auth(monkeypatch, user="ops", password="s3cure!")
    token = auth.create_token("ops")
    payload = auth.decode_token(token)
    assert payload is not None
    assert payload["sub"] == "ops"
    assert payload["role"] == "admin"  # env-var admin gets admin role


def test_decode_invalid_token(monkeypatch):
    """decode_token() returns None for garbage input."""
    auth = _reload_auth(monkeypatch, user="ops", password="s3cure!")
    assert auth.decode_token("not.a.valid.jwt") is None


# -- RBAC: user store -------------------------------------------------------

def test_create_and_list_users(monkeypatch):
    """create_user() adds a user; list_users() returns it without hash."""
    auth = _reload_auth(monkeypatch, user="ops", password="s3cure!")
    user = auth.create_user("analyst1", "pass123", "analyst")
    assert user["username"] == "analyst1"
    assert user["role"] == "analyst"
    assert "password_hash" not in user

    users = auth.list_users()
    assert len(users) == 1
    assert users[0]["username"] == "analyst1"


def test_create_duplicate_user_raises(monkeypatch):
    """create_user() raises ValueError for duplicate username."""
    auth = _reload_auth(monkeypatch, user="ops", password="s3cure!")
    auth.create_user("dup", "pass", "viewer")
    try:
        auth.create_user("dup", "pass2", "admin")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


def test_create_user_invalid_role_raises(monkeypatch):
    """create_user() raises ValueError for invalid role."""
    auth = _reload_auth(monkeypatch, user="ops", password="s3cure!")
    try:
        auth.create_user("bad", "pass", "superadmin")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


def test_delete_user(monkeypatch):
    """delete_user() removes a user and returns True."""
    auth = _reload_auth(monkeypatch, user="ops", password="s3cure!")
    auth.create_user("todelete", "pass", "viewer")
    assert auth.delete_user("todelete") is True
    assert auth.delete_user("todelete") is False
    assert len(auth.list_users()) == 0


def test_get_user_role(monkeypatch):
    """get_user_role() returns the correct role from users.json."""
    auth = _reload_auth(monkeypatch, user="ops", password="s3cure!")
    auth.create_user("viewer1", "pass", "viewer")
    assert auth.get_user_role("viewer1") == "viewer"
    # Env-var admin fallback
    assert auth.get_user_role("ops") == "admin"


def test_authenticate_with_users_json(monkeypatch):
    """authenticate() checks users.json and returns a token with role."""
    auth = _reload_auth(monkeypatch, user="ops", password="s3cure!")
    auth.create_user("analyst1", "mypass", "analyst")
    token = auth.authenticate("analyst1", "mypass")
    assert token is not None
    payload = auth.decode_token(token)
    assert payload["sub"] == "analyst1"
    assert payload["role"] == "analyst"


def test_authenticate_wrong_password_users_json(monkeypatch):
    """authenticate() returns None for wrong password in users.json."""
    auth = _reload_auth(monkeypatch, user="ops", password="s3cure!")
    auth.create_user("user1", "correct", "viewer")
    assert auth.authenticate("user1", "wrong") is None


def test_require_role_in_token(monkeypatch):
    """create_token() includes role in JWT payload."""
    auth = _reload_auth(monkeypatch, user="ops", password="s3cure!")
    token = auth.create_token("someone", role="analyst")
    payload = auth.decode_token(token)
    assert payload["role"] == "analyst"
