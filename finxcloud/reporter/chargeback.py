"""Chargeback/showback report generation for FinXCloud."""

import logging

log = logging.getLogger(__name__)


class ChargebackReporter:
    """Generate chargeback/showback reports allocating costs to teams."""

    def generate(
        self,
        cost_data: dict,
        tag_allocation: dict | None = None,
        teams_config: dict | None = None,
    ) -> dict:
        """Generate a chargeback report from cost data and tag allocations.

        Args:
            cost_data: Merged cost data dict (by_service, total_cost_30d, etc.).
            tag_allocation: Optional tag-based cost allocation data from scan.
            teams_config: Optional dict mapping tag values to team names,
                e.g. {"Engineering": ["backend", "frontend"], "Data": ["analytics"]}.

        Returns:
            Dict with keys: teams (list), unallocated (float), total (float).
        """
        total_cost = cost_data.get("total_cost_30d", 0.0)
        if isinstance(total_cost, dict):
            total_cost = float(total_cost.get("amount", 0.0))
        total_cost = float(total_cost)

        teams: list[dict] = []
        allocated = 0.0

        # If we have tag allocation data, use it to build team breakdown
        if tag_allocation and tag_allocation.get("by_tag"):
            teams, allocated = self._allocate_from_tags(
                tag_allocation, teams_config or {},
            )

        # If no tag data, try to allocate by service
        if not teams:
            teams, allocated = self._allocate_from_services(cost_data)

        unallocated = max(0.0, round(total_cost - allocated, 2))

        return {
            "teams": teams,
            "unallocated": unallocated,
            "total": round(total_cost, 2),
            "allocation_method": "tags" if tag_allocation else "services",
        }

    def _allocate_from_tags(
        self,
        tag_allocation: dict,
        teams_config: dict,
    ) -> tuple[list[dict], float]:
        """Build team allocations from tag-based cost data."""
        teams: list[dict] = []
        allocated = 0.0

        # Build reverse mapping: tag_value -> team_name
        value_to_team: dict[str, str] = {}
        for team_name, values in teams_config.items():
            for v in values:
                value_to_team[v.lower()] = team_name

        team_costs: dict[str, dict] = {}

        for tag_group in tag_allocation.get("by_tag", []):
            for val_entry in tag_group.get("values", []):
                value = val_entry.get("value", "")
                amount = float(val_entry.get("amount", 0.0))
                # Map to team name or use the tag value itself
                team_name = value_to_team.get(value.lower(), value)
                if not team_name:
                    continue

                if team_name not in team_costs:
                    team_costs[team_name] = {
                        "name": team_name,
                        "total_cost": 0.0,
                        "services": [],
                    }
                team_costs[team_name]["total_cost"] += amount
                team_costs[team_name]["services"].append({
                    "tag_key": tag_group.get("tag_key", ""),
                    "tag_value": value,
                    "amount": round(amount, 2),
                })
                allocated += amount

        for team in team_costs.values():
            team["total_cost"] = round(team["total_cost"], 2)
            teams.append(team)

        teams.sort(key=lambda t: t["total_cost"], reverse=True)
        return teams, round(allocated, 2)

    def _allocate_from_services(
        self, cost_data: dict,
    ) -> tuple[list[dict], float]:
        """Fallback: group costs by service as pseudo-teams."""
        teams: list[dict] = []
        allocated = 0.0

        by_service = cost_data.get("by_service", [])
        for svc in by_service:
            amount = float(svc.get("amount", 0.0))
            if amount < 0.01:
                continue
            teams.append({
                "name": svc.get("service", "Unknown"),
                "total_cost": round(amount, 2),
                "services": [{"service": svc.get("service", ""), "amount": round(amount, 2)}],
            })
            allocated += amount

        teams.sort(key=lambda t: t["total_cost"], reverse=True)
        return teams, round(allocated, 2)
