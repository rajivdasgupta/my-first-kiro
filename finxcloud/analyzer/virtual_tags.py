"""Virtual tag manager for FinXCloud — allocate costs to untagged resources."""

from __future__ import annotations

import fnmatch
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

_DEFAULT_VIRTUAL_TAGS_PATH = os.environ.get(
    "FINXCLOUD_VIRTUAL_TAGS_PATH",
    str(Path.home() / ".finxcloud" / "virtual_tags.json"),
)

_VALID_MATCH_TYPES = {"service", "account", "region", "resource_type", "name_pattern"}


class VirtualTagManager:
    """Allocate costs to virtual tags based on rules (for untagged resources)."""

    def __init__(self, path: str | None = None) -> None:
        self._path = path or _DEFAULT_VIRTUAL_TAGS_PATH

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
            log.warning("Could not read virtual tags file at %s", self._path)
            return []

    def _save(self, rules: list[dict]) -> None:
        p = Path(self._path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(rules, indent=2, default=str))

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def add_rule(
        self,
        name: str,
        match_type: str,
        match_value: str,
        tag_key: str,
        tag_value: str,
    ) -> dict:
        """Create a virtual tag rule.

        Args:
            name: Human-readable rule name.
            match_type: One of "service", "account", "region",
                        "resource_type", "name_pattern".
            match_value: Value or glob pattern to match against.
            tag_key: Virtual tag key to assign.
            tag_value: Virtual tag value to assign.
        """
        if match_type not in _VALID_MATCH_TYPES:
            raise ValueError(
                f"Invalid match_type: {match_type}. Must be one of {_VALID_MATCH_TYPES}"
            )

        rules = self._load()
        entry = {
            "id": str(uuid.uuid4())[:8],
            "name": name,
            "match_type": match_type,
            "match_value": match_value,
            "tag_key": tag_key,
            "tag_value": tag_value,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        rules.append(entry)
        self._save(rules)
        log.info("Added virtual tag rule %s: %s (%s=%s)", entry["id"], name, tag_key, tag_value)
        return entry

    def list_rules(self) -> list[dict]:
        """Return all configured virtual tag rules."""
        return self._load()

    def delete_rule(self, rule_id: str) -> bool:
        """Delete a virtual tag rule by ID. Returns True if found and deleted."""
        rules = self._load()
        before = len(rules)
        rules = [r for r in rules if r["id"] != rule_id]
        if len(rules) == before:
            return False
        self._save(rules)
        return True

    def apply_tags(self, resources: list[dict]) -> list[dict]:
        """Apply virtual tags to resources based on rules.

        Returns the same resources list with ``virtual_tags`` dict added
        to each matching resource.
        """
        rules = self._load()
        if not rules:
            return resources

        for resource in resources:
            virtual_tags: dict[str, str] = resource.get("virtual_tags", {})

            for rule in rules:
                if self._matches(rule, resource):
                    virtual_tags[rule["tag_key"]] = rule["tag_value"]

            if virtual_tags:
                resource["virtual_tags"] = virtual_tags

        return resources

    @staticmethod
    def _matches(rule: dict, resource: dict) -> bool:
        """Check if a resource matches a virtual tag rule."""
        match_type = rule.get("match_type", "")
        match_value = rule.get("match_value", "").lower()

        if match_type == "service":
            svc = (resource.get("service", "") or resource.get("resource_type", "")).lower()
            return fnmatch.fnmatch(svc, match_value)

        if match_type == "account":
            acct = (resource.get("account_id", "") or "").lower()
            return acct == match_value

        if match_type == "region":
            region = (resource.get("region", "") or "").lower()
            return fnmatch.fnmatch(region, match_value)

        if match_type == "resource_type":
            rtype = (resource.get("resource_type", "") or "").lower()
            return fnmatch.fnmatch(rtype, match_value)

        if match_type == "name_pattern":
            name = (
                resource.get("name", "")
                or resource.get("resource_id", "")
                or ""
            ).lower()
            try:
                return bool(re.search(match_value, name))
            except re.error:
                return fnmatch.fnmatch(name, match_value)

        return False
