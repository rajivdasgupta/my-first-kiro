"""Scheduled report executor for FinXCloud — send reports that are due."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

from finxcloud.scheduler.report_scheduler import ReportScheduleManager

log = logging.getLogger(__name__)

_FREQUENCY_INTERVALS = {
    "daily": timedelta(days=1),
    "weekly": timedelta(weeks=1),
    "monthly": timedelta(days=30),
}


class ReportExecutor:
    """Execute due report schedules — send reports via email."""

    def __init__(self, manager: ReportScheduleManager | None = None) -> None:
        self._manager = manager or ReportScheduleManager()

    def execute_due_reports(self, now: datetime | None = None) -> list[dict]:
        """Check all schedules and send reports that are due."""
        now = now or datetime.now(timezone.utc)
        schedules = self._manager.list_schedules()
        results: list[dict] = []

        for schedule in schedules:
            if not schedule.get("enabled", True):
                continue
            if not self._is_due(schedule, now):
                continue

            result = self._send_report(schedule)
            results.append(result)

            if result.get("status") == "ok":
                self._update_last_sent(schedule["id"], now)

        return results

    def _is_due(self, schedule: dict, now: datetime) -> bool:
        """Check if a schedule is due for execution."""
        frequency = schedule.get("frequency", "weekly")
        interval = _FREQUENCY_INTERVALS.get(frequency, timedelta(weeks=1))

        last_sent = schedule.get("last_sent_at")
        if not last_sent:
            return True

        if isinstance(last_sent, str):
            try:
                last_sent_dt = datetime.fromisoformat(last_sent)
            except ValueError:
                return True
        else:
            last_sent_dt = last_sent

        if last_sent_dt.tzinfo is None:
            last_sent_dt = last_sent_dt.replace(tzinfo=timezone.utc)

        return (now - last_sent_dt) >= interval

    def _send_report(self, schedule: dict) -> dict:
        """Generate and send a report for a schedule."""
        recipients = schedule.get("recipients", [])
        if not recipients:
            return {
                "schedule_id": schedule["id"],
                "status": "skipped",
                "reason": "No recipients configured",
            }

        account_id = schedule.get("account_id")
        scan_data = self._get_latest_scan_data(account_id)
        if not scan_data:
            return {
                "schedule_id": schedule["id"],
                "status": "skipped",
                "reason": "No scan data available",
            }

        subject = f"FinXCloud Report: {schedule.get('name', 'Scheduled Report')}"
        html_body = self._build_report_html(scan_data)

        try:
            ok = self._send_email(recipients, subject, html_body)
            if ok:
                log.info("Sent scheduled report '%s' to %s", schedule.get("name"), ", ".join(recipients))
                return {"schedule_id": schedule["id"], "status": "ok", "recipients": recipients}
            return {"schedule_id": schedule["id"], "status": "error", "reason": "Email send failed"}
        except Exception as exc:
            log.error("Failed to send scheduled report '%s': %s", schedule.get("name"), exc)
            return {"schedule_id": schedule["id"], "status": "error", "reason": str(exc)}

    def _get_latest_scan_data(self, account_id: str | None) -> dict | None:
        """Retrieve latest scan results from storage."""
        try:
            from finxcloud.web.storage import get_latest_scan, list_accounts

            if account_id:
                scan = get_latest_scan(account_id)
                return scan.get("result") if scan else None

            accounts = list_accounts()
            for acct in accounts:
                scan = get_latest_scan(acct["id"])
                if scan and scan.get("result"):
                    return scan["result"]
        except Exception:
            log.debug("Could not load scan data from storage")
        return None

    @staticmethod
    def _build_report_html(data: dict) -> str:
        """Build a simple HTML email from scan results."""
        summary = data.get("summary", {})
        overview = summary.get("overview", {})
        recs = summary.get("top_recommendations", [])[:10]

        rows = ""
        for r in recs:
            rows += (
                f"<tr><td>{r.get('category', '')}</td>"
                f"<td>{r.get('title', '')}</td>"
                f"<td>{r.get('effort_level', '')}</td>"
                f"<td>${r.get('estimated_monthly_savings', 0):.2f}</td></tr>"
            )

        return f"""
        <html>
        <body style="font-family:Arial,sans-serif;color:#333;">
        <h2 style="color:#1e3a5f;">FinXCloud Scheduled Report</h2>
        <table style="border-collapse:collapse;margin:1em 0;">
          <tr><td style="padding:4px 12px;font-weight:bold;">Total Resources</td>
              <td>{overview.get('total_resources', 0)}</td></tr>
          <tr><td style="padding:4px 12px;font-weight:bold;">30-Day Cost</td>
              <td style="color:#dc2626;">${overview.get('total_cost_30d', 0):.2f}</td></tr>
          <tr><td style="padding:4px 12px;font-weight:bold;">Potential Savings</td>
              <td style="color:#16a34a;">${overview.get('total_potential_savings', 0):.2f}</td></tr>
        </table>
        <h3>Top Recommendations</h3>
        <table style="border-collapse:collapse;width:100%;">
          <tr style="background:#f3f4f6;">
            <th style="padding:6px 10px;text-align:left;">Category</th>
            <th style="padding:6px 10px;text-align:left;">Recommendation</th>
            <th style="padding:6px 10px;text-align:left;">Effort</th>
            <th style="padding:6px 10px;text-align:left;">Est. Savings/mo</th>
          </tr>
          {rows}
        </table>
        <p style="margin-top:2em;color:#6b7280;font-size:12px;">Generated by FinXCloud</p>
        </body>
        </html>
        """

    @staticmethod
    def _send_email(recipients: list[str], subject: str, html_body: str) -> bool:
        """Send email using configured method (SMTP or SES)."""
        from finxcloud.email.sender import EmailConfig, send_email

        config = EmailConfig()
        if config.is_configured:
            return send_email(config, recipients, subject, html_body)

        from finxcloud.email.sender import send_email_ses

        from_addr = os.environ.get("FINXCLOUD_FROM_EMAIL", "noreply@finxcloud.io")
        return send_email_ses(
            to_addresses=recipients,
            subject=subject,
            html_body=html_body,
            from_address=from_addr,
        )

    def _update_last_sent(self, schedule_id: str, now: datetime) -> None:
        """Update last_sent_at for a schedule."""
        schedules = self._manager._load()
        for s in schedules:
            if s["id"] == schedule_id:
                s["last_sent_at"] = now.isoformat()
                break
        self._manager._save(schedules)
