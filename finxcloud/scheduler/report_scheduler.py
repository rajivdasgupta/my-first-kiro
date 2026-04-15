"""Scheduled report delivery manager for FinXCloud."""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

_DEFAULT_REPORT_SCHEDULES_PATH = os.environ.get(
    "FINXCLOUD_REPORT_SCHEDULES_PATH",
    str(Path.home() / ".finxcloud" / "report_schedules.json"),
)


class ReportScheduleManager:
    """Manage scheduled report delivery.

    Each schedule entry:
    {
        "id": "<uuid>",
        "name": "Weekly team report",
        "frequency": "weekly",
        "recipients": ["user@example.com"],
        "report_format": "pdf",
        "account_id": null,
        "enabled": true,
        "created_at": "2026-04-06T..."
    }
    """

    def __init__(self, path: str | None = None) -> None:
        self._path = path or _DEFAULT_REPORT_SCHEDULES_PATH

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
            log.warning("Could not read report schedules file at %s", self._path)
            return []

    def _save(self, schedules: list[dict]) -> None:
        p = Path(self._path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(schedules, indent=2, default=str))

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def add_schedule(
        self,
        name: str,
        frequency: str,
        recipients: list[str],
        report_format: str = "pdf",
        account_id: str | None = None,
    ) -> dict:
        """Create a new report delivery schedule.

        Args:
            name: Human-readable schedule name.
            frequency: ``daily``, ``weekly``, or ``monthly``.
            recipients: List of email addresses.
            report_format: ``pdf`` or ``csv``.
            account_id: Optional account to scope the report to.
        """
        schedules = self._load()
        entry = {
            "id": str(uuid.uuid4())[:8],
            "name": name,
            "frequency": frequency,
            "recipients": recipients,
            "report_format": report_format,
            "account_id": account_id,
            "enabled": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        schedules.append(entry)
        self._save(schedules)
        log.info("Added report schedule %s: %s (%s)", entry["id"], name, frequency)
        return entry

    def list_schedules(self) -> list[dict]:
        """Return all configured report schedules."""
        return self._load()

    def delete_schedule(self, schedule_id: str) -> bool:
        """Delete a report schedule by ID. Returns True if found and deleted."""
        schedules = self._load()
        before = len(schedules)
        schedules = [s for s in schedules if s["id"] != schedule_id]
        if len(schedules) == before:
            return False
        self._save(schedules)
        return True
