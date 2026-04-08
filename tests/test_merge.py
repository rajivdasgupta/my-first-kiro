"""Tests for finxcloud.utils.cost.merge_cost_data."""

from finxcloud.utils.cost import merge_cost_data


def test_single_account_passthrough():
    """Single-account input returns the same dict unchanged."""
    data = {
        "by_service": [{"service": "EC2", "amount": 100}],
        "by_region": [{"region": "us-east-1", "amount": 100}],
        "daily_trend": [{"date": "2024-01-01", "amount": 50}],
        "total_cost_30d": 100.0,
    }
    result = merge_cost_data({"acct-1": data})
    assert result is data


def test_multi_account_merge_services():
    """Services from multiple accounts are summed by name."""
    acct_a = {
        "by_service": [{"service": "EC2", "amount": 80}, {"service": "S3", "amount": 20}],
        "by_region": [],
        "daily_trend": [],
        "total_cost_30d": 100.0,
    }
    acct_b = {
        "by_service": [{"service": "EC2", "amount": 40}, {"service": "Lambda", "amount": 10}],
        "by_region": [],
        "daily_trend": [],
        "total_cost_30d": 50.0,
    }
    result = merge_cost_data({"a": acct_a, "b": acct_b})

    svc_map = {e["service"]: e["amount"] for e in result["by_service"]}
    assert svc_map["EC2"] == 120
    assert svc_map["S3"] == 20
    assert svc_map["Lambda"] == 10


def test_multi_account_merge_regions():
    """Regions from multiple accounts are summed by name."""
    acct_a = {
        "by_service": [],
        "by_region": [{"region": "us-east-1", "amount": 70}],
        "daily_trend": [],
        "total_cost_30d": 70.0,
    }
    acct_b = {
        "by_service": [],
        "by_region": [
            {"region": "us-east-1", "amount": 30},
            {"region": "eu-west-1", "amount": 15},
        ],
        "daily_trend": [],
        "total_cost_30d": 45.0,
    }
    result = merge_cost_data({"a": acct_a, "b": acct_b})

    region_map = {e["region"]: e["amount"] for e in result["by_region"]}
    assert region_map["us-east-1"] == 100
    assert region_map["eu-west-1"] == 15


def test_multi_account_merge_daily_trend():
    """Daily trend entries with the same date are summed."""
    acct_a = {
        "by_service": [],
        "by_region": [],
        "daily_trend": [
            {"date": "2024-01-01", "amount": 10},
            {"date": "2024-01-02", "amount": 20},
        ],
        "total_cost_30d": 30.0,
    }
    acct_b = {
        "by_service": [],
        "by_region": [],
        "daily_trend": [{"date": "2024-01-01", "amount": 5}],
        "total_cost_30d": 5.0,
    }
    result = merge_cost_data({"a": acct_a, "b": acct_b})

    daily_map = {e["date"]: e["amount"] for e in result["daily_trend"]}
    assert daily_map["2024-01-01"] == 15
    assert daily_map["2024-01-02"] == 20


def test_total_cost_is_sum_of_accounts():
    """total_cost_30d equals the sum across all accounts."""
    accounts = {
        "a": {"by_service": [], "by_region": [], "daily_trend": [], "total_cost_30d": 100.0},
        "b": {"by_service": [], "by_region": [], "daily_trend": [], "total_cost_30d": 250.0},
        "c": {"by_service": [], "by_region": [], "daily_trend": [], "total_cost_30d": 50.0},
    }
    result = merge_cost_data(accounts)
    assert result["total_cost_30d"] == 400.0


def test_empty_cost_data_fields():
    """Accounts with missing or empty cost fields don't cause errors."""
    accounts = {
        "a": {"total_cost_30d": 10.0},
        "b": {"by_service": [], "by_region": [], "daily_trend": [], "total_cost_30d": 0.0},
    }
    result = merge_cost_data(accounts)
    assert result["total_cost_30d"] == 10.0
    assert result["by_service"] == []
    assert result["by_region"] == []
    assert result["daily_trend"] == []
