"""Shared cost-data utilities used by both the CLI and the web dashboard."""

from __future__ import annotations

__all__ = ["merge_cost_data"]


def merge_cost_data(cost_data_by_account: dict) -> dict:
    """Merge cost data from multiple accounts into a single dict.

    Args:
        cost_data_by_account: Mapping of account ID to cost data dict.
            Each value is expected to contain keys such as ``by_service``,
            ``by_region``, ``daily_trend``, and ``total_cost_30d``.

    Returns:
        A single cost data dict with aggregated values across all accounts.
    """
    if len(cost_data_by_account) == 1:
        return next(iter(cost_data_by_account.values()))

    merged: dict = {
        "by_service": [],
        "by_region": [],
        "by_account": [],
        "daily_trend": [],
        "total_cost_30d": 0.0,
    }
    service_totals: dict[str, float] = {}
    region_totals: dict[str, float] = {}
    daily_totals: dict[str, float] = {}

    for account_id, data in cost_data_by_account.items():
        merged["total_cost_30d"] += data.get("total_cost_30d", 0.0)
        merged["by_account"].append({
            "account": account_id,
            "amount": data.get("total_cost_30d", 0.0),
            "unit": "USD",
            "currency": "USD",
        })
        for entry in data.get("by_service", []):
            service_totals[entry["service"]] = (
                service_totals.get(entry["service"], 0) + float(entry["amount"])
            )
        for entry in data.get("by_region", []):
            region_key = entry.get("region", "unknown")
            region_totals[region_key] = (
                region_totals.get(region_key, 0) + float(entry["amount"])
            )
        for entry in data.get("daily_trend", []):
            daily_totals[entry["date"]] = (
                daily_totals.get(entry["date"], 0) + float(entry["amount"])
            )

    merged["by_service"] = [
        {"service": k, "amount": v, "unit": "USD", "currency": "USD"}
        for k, v in sorted(service_totals.items(), key=lambda x: x[1], reverse=True)
    ]
    merged["by_region"] = [
        {"region": k, "amount": v, "unit": "USD", "currency": "USD"}
        for k, v in sorted(region_totals.items(), key=lambda x: x[1], reverse=True)
    ]
    merged["daily_trend"] = [
        {"date": k, "amount": v}
        for k, v in sorted(daily_totals.items())
    ]
    return merged
