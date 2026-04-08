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


def test_decode_invalid_token(monkeypatch):
    """decode_token() returns None for garbage input."""
    auth = _reload_auth(monkeypatch, user="ops", password="s3cure!")
    assert auth.decode_token("not.a.valid.jwt") is None
