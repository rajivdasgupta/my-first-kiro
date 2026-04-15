"""Slack alert bot for real-time cost notifications via incoming webhooks.

Sends formatted Block Kit messages for cost alerts, scan summaries,
and anomaly detection results. Uses webhook URLs (no bot token required).
"""

from __future__ import annotations

import json
import logging
import os
import urllib.request
import urllib.error
from typing import Any

log = logging.getLogger(__name__)

__all__ = ["SlackAlertBot"]


class SlackAlertBot:
    """Send real-time cost alerts to Slack channels via incoming webhooks."""

    def __init__(self, webhook_url: str | None = None) -> None:
        self.webhook_url = webhook_url or os.environ.get("FINXCLOUD_SLACK_WEBHOOK", "")

    @property
    def is_configured(self) -> bool:
        """Return True if a webhook URL is available."""
        return bool(self.webhook_url)

    def send_cost_alert(
        self,
        alert_name: str,
        current_spend: float,
        threshold: float,
        period: str = "daily",
    ) -> dict[str, Any]:
        """Send a formatted cost alert to Slack.

        Args:
            alert_name: Human-readable alert name.
            current_spend: Current spend amount in USD.
            threshold: Threshold amount in USD.
            period: Alert period (daily, weekly, monthly).

        Returns:
            Dict with ``ok`` bool and optional ``error`` string.
        """
        pct = (current_spend / threshold * 100) if threshold > 0 else 0
        emoji = "🔴" if current_spend >= threshold else "🟡"

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"{emoji} Cost Alert: {alert_name}"},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Period:*\n{period.capitalize()}"},
                    {"type": "mrkdwn", "text": f"*Threshold:*\n${threshold:,.2f}"},
                    {"type": "mrkdwn", "text": f"*Current Spend:*\n${current_spend:,.2f}"},
                    {"type": "mrkdwn", "text": f"*Usage:*\n{pct:.1f}%"},
                ],
            },
            {"type": "divider"},
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": "Sent by *FinXCloud* cost monitoring"},
                ],
            },
        ]

        return self._post(blocks, text=f"Cost Alert: {alert_name} — ${current_spend:,.2f}/{threshold:,.2f}")

    def _post(self, blocks: list[dict], text: str = "") -> dict[str, Any]:
        """Send a Block Kit message to the configured webhook URL.

        Args:
            blocks: Slack Block Kit blocks list.
            text: Fallback plain-text summary.

        Returns:
            Dict with ``ok`` bool and optional ``error`` string.
        """
        if not self.is_configured:
            return {"ok": False, "error": "Webhook URL not configured"}

        payload = json.dumps({"blocks": blocks, "text": text}).encode()
        req = urllib.request.Request(
            self.webhook_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = resp.read().decode()
                log.debug("Slack webhook response: %s", body)
                return {"ok": True}
        except urllib.error.HTTPError as exc:
            msg = f"HTTP {exc.code}: {exc.read().decode()[:200]}"
            log.error("Slack webhook failed: %s", msg)
            return {"ok": False, "error": msg}
        except Exception as exc:
            log.error("Slack webhook error: %s", exc)
            return {"ok": False, "error": str(exc)}

    def send_scan_summary(self, summary_data: dict) -> dict[str, Any]:
        """Send a scan results summary to Slack.

        Args:
            summary_data: Summary dict with overview, recommendations count, etc.

        Returns:
            Dict with ``ok`` bool and optional ``error`` string.
        """
        overview = summary_data.get("overview", {})
        total_cost = overview.get("total_cost_30d", 0)
        savings = overview.get("total_potential_savings", 0)
        resources = overview.get("total_resources", 0)
        rec_count = len(summary_data.get("top_recommendations", []))

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "📊 FinXCloud Scan Complete"},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Resources Scanned:*\n{resources}"},
                    {"type": "mrkdwn", "text": f"*30-Day Cost:*\n${total_cost:,.2f}"},
                    {"type": "mrkdwn", "text": f"*Potential Savings:*\n${savings:,.2f}"},
                    {"type": "mrkdwn", "text": f"*Recommendations:*\n{rec_count}"},
                ],
            },
            {"type": "divider"},
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": "Sent by *FinXCloud* cost monitoring"},
                ],
            },
        ]

        return self._post(blocks, text=f"Scan complete: {resources} resources, ${total_cost:,.2f} cost, ${savings:,.2f} potential savings")

    def send_anomaly_alert(self, anomaly_data: dict) -> dict[str, Any]:
        """Send an anomaly detection alert to Slack.

        Args:
            anomaly_data: Dict with anomaly details (service, expected, actual, etc.).

        Returns:
            Dict with ``ok`` bool and optional ``error`` string.
        """
        service = anomaly_data.get("service", "Unknown")
        expected = anomaly_data.get("expected_spend", 0)
        actual = anomaly_data.get("actual_spend", 0)
        delta = actual - expected
        pct_change = (delta / expected * 100) if expected > 0 else 0

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "🚨 Cost Anomaly Detected"},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Service:*\n{service}"},
                    {"type": "mrkdwn", "text": f"*Expected:*\n${expected:,.2f}"},
                    {"type": "mrkdwn", "text": f"*Actual:*\n${actual:,.2f}"},
                    {"type": "mrkdwn", "text": f"*Change:*\n{pct_change:+.1f}%"},
                ],
            },
            {"type": "divider"},
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": "Sent by *FinXCloud* anomaly detection"},
                ],
            },
        ]

        return self._post(blocks, text=f"Cost anomaly: {service} — ${actual:,.2f} vs ${expected:,.2f} expected")
