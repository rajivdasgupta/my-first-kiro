"""Shared test fixtures for FinXCloud test suite."""

import os
import pytest


@pytest.fixture(autouse=True)
def _reset_auth_env(monkeypatch, tmp_path):
    """Ensure auth env vars are clean between tests."""
    monkeypatch.delenv("FINXCLOUD_ADMIN_USER", raising=False)
    monkeypatch.delenv("FINXCLOUD_ADMIN_PASS", raising=False)
    monkeypatch.delenv("FINXCLOUD_JWT_SECRET", raising=False)
    # Isolate user store to a temp directory so tests don't touch real data
    monkeypatch.setenv("FINXCLOUD_USERS_PATH", str(tmp_path / "users.json"))


@pytest.fixture
def tmp_db_path(tmp_path):
    """Provide a temporary database path for storage tests."""
    return str(tmp_path / "test.db")
