"""SaaS spend tracking for FinXCloud."""

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)

DEFAULT_PATH = Path.home() / ".finxcloud" / "saas_costs.json"


class SaaSTracker:
    """Track SaaS costs from AWS Marketplace and manual entries."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else DEFAULT_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data: list[dict] = self._load()

    def _load(self) -> list[dict]:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text())
            except (json.JSONDecodeError, OSError) as exc:
                log.warning("Failed to load SaaS costs from %s: %s", self.path, exc)
        return []

    def _save(self) -> None:
        try:
            self.path.write_text(json.dumps(self._data, indent=2, default=str))
        except OSError as exc:
            log.error("Failed to save SaaS costs to %s: %s", self.path, exc)

    def add_saas_cost(
        self,
        name: str,
        monthly_cost: float,
        category: str = "SaaS",
    ) -> dict:
        """Add a SaaS cost entry. Returns the created entry."""
        entry = {
            "id": str(uuid.uuid4()),
            "name": name,
            "monthly_cost": round(monthly_cost, 2),
            "category": category,
            "created_at": datetime.utcnow().isoformat(),
        }
        self._data.append(entry)
        self._save()
        return entry

    def list_saas_costs(self) -> list[dict]:
        """Return all tracked SaaS costs."""
        return list(self._data)

    def delete_saas_cost(self, cost_id: str) -> bool:
        """Delete a SaaS cost entry by ID. Returns True if found and deleted."""
        before = len(self._data)
        self._data = [e for e in self._data if e.get("id") != cost_id]
        if len(self._data) < before:
            self._save()
            return True
        return False

    def get_total_monthly(self) -> float:
        """Return total monthly SaaS spend."""
        return round(sum(e.get("monthly_cost", 0.0) for e in self._data), 2)
