"""Infrastructure-as-Code cost estimation for FinXCloud."""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)

# Approximate monthly hours
_HOURS_PER_MONTH = 730


class IaCCostEstimator:
    """Estimate costs from Terraform/CloudFormation resource definitions."""

    # Hourly on-demand prices (USD) for common resource types
    HOURLY_PRICES: dict[str, dict[str, float]] = {
        "aws_instance": {
            "t3.micro": 0.0104,
            "t3.small": 0.0208,
            "t3.medium": 0.0416,
            "t3.large": 0.0832,
            "t3.xlarge": 0.1664,
            "t3.2xlarge": 0.3328,
            "m5.large": 0.096,
            "m5.xlarge": 0.192,
            "m5.2xlarge": 0.384,
            "m5.4xlarge": 0.768,
            "m6i.large": 0.096,
            "m6i.xlarge": 0.192,
            "m6i.2xlarge": 0.384,
            "c5.large": 0.085,
            "c5.xlarge": 0.17,
            "c5.2xlarge": 0.34,
            "r5.large": 0.126,
            "r5.xlarge": 0.252,
            "r5.2xlarge": 0.504,
            "p3.2xlarge": 3.06,
            "g4dn.xlarge": 0.526,
            "g5.xlarge": 1.006,
        },
        "aws_db_instance": {
            "db.t3.micro": 0.017,
            "db.t3.small": 0.034,
            "db.t3.medium": 0.068,
            "db.t3.large": 0.136,
            "db.m5.large": 0.171,
            "db.m5.xlarge": 0.342,
            "db.m5.2xlarge": 0.684,
            "db.r5.large": 0.24,
            "db.r5.xlarge": 0.48,
            "db.r5.2xlarge": 0.96,
        },
        "aws_elasticache_cluster": {
            "cache.t3.micro": 0.017,
            "cache.t3.small": 0.034,
            "cache.t3.medium": 0.068,
            "cache.m5.large": 0.156,
            "cache.m5.xlarge": 0.311,
            "cache.r5.large": 0.228,
        },
        "aws_opensearch_domain": {
            "t3.small.search": 0.036,
            "t3.medium.search": 0.073,
            "m5.large.search": 0.142,
            "m5.xlarge.search": 0.284,
            "r5.large.search": 0.186,
        },
        "aws_nat_gateway": {
            "default": 0.045,
        },
        "aws_lb": {
            "default": 0.0225,
        },
    }

    # Monthly flat-rate prices for storage/other resources (per GB or per unit)
    MONTHLY_PRICES: dict[str, dict[str, float]] = {
        "aws_ebs_volume": {
            "gp3": 0.08,
            "gp2": 0.10,
            "io1": 0.125,
            "io2": 0.125,
            "st1": 0.045,
            "sc1": 0.015,
            "standard": 0.05,
        },
        "aws_s3_bucket": {
            "default": 0.023,
        },
    }

    # Mapping from Terraform resource types to internal resource types
    TERRAFORM_RESOURCE_MAP: dict[str, str] = {
        "aws_instance": "aws_instance",
        "aws_db_instance": "aws_db_instance",
        "aws_ebs_volume": "aws_ebs_volume",
        "aws_lb": "aws_lb",
        "aws_nat_gateway": "aws_nat_gateway",
        "aws_elasticache_cluster": "aws_elasticache_cluster",
        "aws_opensearch_domain": "aws_opensearch_domain",
        "aws_s3_bucket": "aws_s3_bucket",
    }

    def estimate_from_terraform_plan(self, plan_json: dict) -> dict:
        """Estimate monthly cost from ``terraform show -json tfplan`` output.

        Parses the ``resource_changes`` array, extracts resource type,
        instance type, and count, then delegates to the existing pricing
        lookup via :meth:`estimate_from_resources`.

        Args:
            plan_json: Parsed JSON from ``terraform show -json tfplan``.

        Returns:
            Same format as :meth:`estimate_from_resources`.
        """
        resource_changes = plan_json.get("resource_changes", [])
        resources: list[dict] = []

        for change in resource_changes:
            actions = change.get("change", {}).get("actions", [])
            # Skip resources being destroyed with no create
            if actions == ["delete"]:
                continue

            tf_type = change.get("type", "")
            mapped_type = self.TERRAFORM_RESOURCE_MAP.get(tf_type)
            if not mapped_type:
                log.debug("Skipping unsupported Terraform resource type: %s", tf_type)
                continue

            after = change.get("change", {}).get("after", {}) or {}
            resource = self._extract_terraform_resource(mapped_type, after)
            resources.append(resource)

        return self.estimate_from_resources(resources)

    def _extract_terraform_resource(self, res_type: str, attrs: dict) -> dict:
        """Extract a normalised resource dict from Terraform plan attributes."""
        resource: dict = {"type": res_type}

        if res_type == "aws_instance":
            resource["instance_type"] = attrs.get("instance_type", "default")
        elif res_type == "aws_db_instance":
            resource["instance_type"] = attrs.get("instance_class", "default")
        elif res_type == "aws_ebs_volume":
            resource["volume_type"] = attrs.get("type", "gp3")
            resource["size_gb"] = attrs.get("size", 20)
        elif res_type == "aws_elasticache_cluster":
            resource["instance_type"] = attrs.get("node_type", "default")
            resource["count"] = attrs.get("num_cache_nodes", 1)
        elif res_type == "aws_opensearch_domain":
            cluster_cfg = attrs.get("cluster_config", {}) or {}
            resource["instance_type"] = cluster_cfg.get("instance_type", "default")
            resource["count"] = cluster_cfg.get("instance_count", 1)
        elif res_type in ("aws_lb", "aws_nat_gateway"):
            resource["instance_type"] = "default"

        resource.setdefault("count", 1)
        return resource

    def estimate_from_resources(self, resources: list[dict]) -> dict:
        """Estimate monthly cost from a list of resource definitions.

        Each resource dict should have:
            - type: str (e.g. "aws_instance", "aws_db_instance")
            - instance_type: str (e.g. "t3.medium", "db.t3.micro")
            - count: int (default 1)
            - size_gb: int (optional, for storage resources)
            - volume_type: str (optional, for EBS)

        Returns:
            Dict with keys: resources (list of estimates), total_monthly (float).
        """
        estimates: list[dict] = []
        total = 0.0

        for res in resources:
            est = self._estimate_single(res)
            estimates.append(est)
            total += est["monthly_cost"]

        return {
            "resources": estimates,
            "total_monthly": round(total, 2),
        }

    def _estimate_single(self, resource: dict) -> dict:
        """Estimate cost for a single resource."""
        res_type = resource.get("type", "")
        instance_type = resource.get("instance_type", "default")
        count = max(int(resource.get("count", 1)), 1)
        size_gb = float(resource.get("size_gb", 0))
        volume_type = resource.get("volume_type", "gp3")

        monthly_cost = 0.0
        pricing_note = ""

        # Check hourly-priced resources
        if res_type in self.HOURLY_PRICES:
            prices = self.HOURLY_PRICES[res_type]
            hourly = prices.get(instance_type, prices.get("default", 0.0))
            if hourly > 0:
                monthly_cost = hourly * _HOURS_PER_MONTH * count
                pricing_note = f"${hourly}/hr x {_HOURS_PER_MONTH}h x {count}"
            else:
                pricing_note = f"Unknown instance type: {instance_type}"

        # Check monthly-priced (storage) resources
        elif res_type in self.MONTHLY_PRICES:
            prices = self.MONTHLY_PRICES[res_type]
            if res_type == "aws_ebs_volume":
                per_gb = prices.get(volume_type, prices.get("gp3", 0.08))
                gb = size_gb if size_gb > 0 else 20  # default 20 GB
                monthly_cost = per_gb * gb * count
                pricing_note = f"${per_gb}/GB x {gb}GB x {count}"
            elif res_type == "aws_s3_bucket":
                per_gb = prices.get("default", 0.023)
                gb = size_gb if size_gb > 0 else 0
                monthly_cost = per_gb * gb * count
                pricing_note = f"${per_gb}/GB x {gb}GB" if gb > 0 else "Storage cost depends on usage"
            else:
                per_unit = prices.get("default", 0.0)
                monthly_cost = per_unit * count
                pricing_note = f"${per_unit}/unit x {count}"
        else:
            pricing_note = f"No pricing data for resource type: {res_type}"

        return {
            "type": res_type,
            "instance_type": instance_type,
            "count": count,
            "monthly_cost": round(monthly_cost, 2),
            "pricing_note": pricing_note,
        }
