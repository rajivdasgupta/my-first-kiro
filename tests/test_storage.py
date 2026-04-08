"""Tests for finxcloud.web.storage module.

Each test gets an isolated temporary SQLite database via the tmp_db_path
fixture (defined in conftest.py). We monkeypatch _DB_PATH and reset the
thread-local connection so every test starts fresh.
"""

import finxcloud.web.storage as storage


def _reset_storage(monkeypatch, tmp_db_path):
    """Point storage at a temp DB and clear the cached connection."""
    monkeypatch.setattr(storage, "_DB_PATH", tmp_db_path)
    # Force a new connection on next call
    storage._local.conn = None


# -- Account CRUD ----------------------------------------------------------

def test_create_and_get_account(monkeypatch, tmp_db_path):
    """create_account then get_account returns matching data."""
    _reset_storage(monkeypatch, tmp_db_path)

    created = storage.create_account(name="test-acct", region="us-west-2")
    fetched = storage.get_account(created["id"])

    assert fetched is not None
    assert fetched["name"] == "test-acct"
    assert fetched["region"] == "us-west-2"


def test_list_accounts(monkeypatch, tmp_db_path):
    """list_accounts returns all created accounts."""
    _reset_storage(monkeypatch, tmp_db_path)

    storage.create_account(name="alpha")
    storage.create_account(name="bravo")

    accounts = storage.list_accounts()
    names = {a["name"] for a in accounts}
    assert "alpha" in names
    assert "bravo" in names


def test_update_account(monkeypatch, tmp_db_path):
    """update_account changes the specified fields."""
    _reset_storage(monkeypatch, tmp_db_path)

    created = storage.create_account(name="old-name", region="us-east-1")
    storage.update_account(created["id"], name="new-name", region="eu-west-1")

    fetched = storage.get_account(created["id"])
    assert fetched["name"] == "new-name"
    assert fetched["region"] == "eu-west-1"


def test_delete_account(monkeypatch, tmp_db_path):
    """delete_account removes the account from the database."""
    _reset_storage(monkeypatch, tmp_db_path)

    created = storage.create_account(name="to-delete")
    assert storage.delete_account(created["id"]) is True
    assert storage.get_account(created["id"]) is None


# -- Scan results -----------------------------------------------------------

def test_save_and_get_latest_scan(monkeypatch, tmp_db_path):
    """save_scan_result then get_latest_scan returns the result."""
    _reset_storage(monkeypatch, tmp_db_path)

    acct = storage.create_account(name="scan-acct")
    result_data = {"findings": [{"id": "f1", "severity": "high"}]}
    scan_id = storage.save_scan_result(acct["id"], result_data)

    latest = storage.get_latest_scan(acct["id"])
    assert latest is not None
    assert latest["id"] == scan_id
    assert latest["result"]["findings"][0]["severity"] == "high"


def test_list_scans(monkeypatch, tmp_db_path):
    """list_scans returns all scans for an account."""
    _reset_storage(monkeypatch, tmp_db_path)

    acct = storage.create_account(name="multi-scan")
    storage.save_scan_result(acct["id"], {"run": 1})
    storage.save_scan_result(acct["id"], {"run": 2})

    scans = storage.list_scans(acct["id"])
    assert len(scans) == 2
