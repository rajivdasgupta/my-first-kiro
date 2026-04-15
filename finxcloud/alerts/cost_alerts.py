"""Cost alert manager for FinXCloud — configurable spend thresholds."""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

_DEFAULT_ALERTS_PATH = os.environ.get(
    "FINXCLOUD_COST_ALERTS_PATH",
    str(Path.home() / ".finxcloud" / "cost_alerts.json"),
)


class CostAlertManager:
    """Manage cost alert thresholds stored in a local JSON file.

    Each alert entry:
    {
        "id": "<uuid>",
        "name": "Daily spend > $500",
        "threshold_amount": 500.0,
        "alert_type": "daily",
        "notify_via": "webhook",
        "notify_target": "",
        "enabled": true,
        "created_at": "2026-04-06T..."
    }
    """

    def __init__(self, path: str | None = None) -> None:
        self._path = path or _DEFAULT_ALERTS_PATH

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> list[dict]:
        p = Path(self._path)
        if not p.exists():
            return []
        try:
            return json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            log.warning("Could not read cost alerts file at %s", self._path)
            return []

    def _save(self, alerts: list[dict]) -> None:
        p = Path(self._path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(alerts, indent=2, default=str))

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def add_alert(
        self,
        name: str,
        threshold_amount: float,
        alert_type: str = "daily",
        notify_via: str = "webhook",
        notify_target: str = "",
    ) -> dict:
        """Create a new cost alert threshold.

        Args:
            name: Human-readable alert name.
            threshold_amount: USD amount that triggers the alert.
            alert_type: Period — ``daily``, ``weekly``, or ``monthly``.
            notify_via: Notification channel — ``webhook`` or ``email``.
            notify_target: Webhook URL or email address.
        """
        alerts = self._load()
        entry = {
            "id": str(uuid.uuid4())[:8],
            "name": name,
            "threshold_amount": threshold_amount,
            "alert_type": alert_type,
            "notify_via": notify_via,
            "notify_target": notify_target,
            "enabled": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        alerts.append(entry)
        self._save(alerts)
        log.info("Added cost alert %s: %s ($%.2f %s)", entry["id"], name, threshold_amount, alert_type)
        return entry

    def list_alerts(self) -> list[dict]:
        """Return all configured cost alerts."""
        return self._load()

    def delete_alert(self, alert_id: str) -> bool:
        """Delete a cost alert by ID. Returns True if found and deleted."""
        alerts = self._load()
        before = len(alerts)
        alerts = [a for a in alerts if a["id"] != alert_id]
        if len(alerts) == before:
            return False
        self._save(alerts)
        return True

    def check_alerts(self, current_spend: float, period: str = "daily") -> list[dict]:
        """Check which alerts are triggered for the given spend and period.

        Returns a list of triggered alert dicts.
        """
        triggered: list[dict] = []
        for alert in self._load():
            if not alert.get("enabled", True):
                continue
            if alert.get("alert_type") != period:
                continue
            if current_spend >= alert["threshold_amount"]:
                triggered.append({
                    **alert,
                    "current_spend": current_spend,
                    "exceeded_by": round(current_spend - alert["threshold_amount"], 2),
                })
        return triggered
