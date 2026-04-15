"""EKS Kubernetes scanner for FinXCloud AWS cost optimization."""

import logging
from typing import Any

from botocore.exceptions import ClientError

from .base import ResourceScanner

log = logging.getLogger(__name__)

# Approximate hourly on-demand prices (USD) for common instance types used in EKS nodegroups.
_HOURLY_PRICES: dict[str, float] = {
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
    "c5.large": 0.085,
    "c5.xlarge": 0.17,
    "c5.2xlarge": 0.34,
    "r5.large": 0.126,
    "r5.xlarge": 0.252,
    "p3.2xlarge": 3.06,
    "p3.8xlarge": 12.24,
    "g4dn.xlarge": 0.526,
    "g4dn.2xlarge": 0.752,
    "g5.xlarge": 1.006,
    "g5.2xlarge": 1.212,
}


class KubernetesScanner(ResourceScanner):
    """Scan EKS clusters and estimate namespace/pod-level costs."""

    def scan(self) -> list[dict]:
        """Scan EKS clusters and return resource dicts with cost estimates."""
        resources: list[dict] = []
        for region in self.get_regions():
            try:
                eks = self.session.client("eks", region_name=region)
                resources.extend(self._scan_clusters(eks, region))
            except ClientError as exc:
                log.warning("EKS scan failed in %s: %s", region, exc)
            except Exception as exc:
                log.warning("Unexpected error scanning EKS in %s: %s", region, exc)
        return resources

    def _scan_clusters(self, eks: Any, region: str) -> list[dict]:
        results: list[dict] = []
        paginator = eks.get_paginator("list_clusters")
        page_iterator = self._safe_api_call(paginator.paginate)
        if page_iterator is None:
            return results

        for page in page_iterator:
            for cluster_name in page.get("clusters", []):
                cluster_info = self._describe_cluster(eks, cluster_name, region)
                if cluster_info:
                    results.append(cluster_info)
                results.extend(self._scan_nodegroups(eks, cluster_name, region))
        return results

    def _describe_cluster(self, eks: Any, name: str, region: str) -> dict | None:
        resp = self._safe_api_call(eks.describe_cluster, name=name)
        if resp is None:
            return None
        cluster = resp.get("cluster", {})
        return {
            "resource_type": "eks_cluster",
            "region": region,
            "resource_id": cluster.get("arn", name),
            "cluster_name": name,
            "status": cluster.get("status"),
            "version": cluster.get("version"),
            "endpoint": cluster.get("endpoint"),
            "platform_version": cluster.get("platformVersion"),
            "tags": cluster.get("tags", {}),
            "created_at": cluster.get("createdAt"),
        }

    def _scan_nodegroups(self, eks: Any, cluster_name: str, region: str) -> list[dict]:
        results: list[dict] = []
        paginator = eks.get_paginator("list_nodegroups")
        page_iterator = self._safe_api_call(paginator.paginate, clusterName=cluster_name)
        if page_iterator is None:
            return results

        for page in page_iterator:
            for ng_name in page.get("nodegroups", []):
                ng_info = self._describe_nodegroup(eks, cluster_name, ng_name, region)
                if ng_info:
                    results.append(ng_info)
        return results

    def _describe_nodegroup(
        self, eks: Any, cluster_name: str, ng_name: str, region: str,
    ) -> dict | None:
        resp = self._safe_api_call(
            eks.describe_nodegroup, clusterName=cluster_name, nodegroupName=ng_name,
        )
        if resp is None:
            return None
        ng = resp.get("nodegroup", {})
        instance_types = ng.get("instanceTypes", [])
        scaling = ng.get("scalingConfig", {})
        desired = scaling.get("desiredSize", 0)

        # Estimate monthly cost based on instance types and desired capacity
        estimated_monthly = self._estimate_monthly_cost(instance_types, desired)

        return {
            "resource_type": "eks_nodegroup",
            "region": region,
            "resource_id": ng.get("nodegroupArn", ng_name),
            "cluster_name": cluster_name,
            "nodegroup_name": ng_name,
            "status": ng.get("status"),
            "instance_types": instance_types,
            "desired_size": desired,
            "min_size": scaling.get("minSize", 0),
            "max_size": scaling.get("maxSize", 0),
            "ami_type": ng.get("amiType"),
            "capacity_type": ng.get("capacityType", "ON_DEMAND"),
            "tags": ng.get("tags", {}),
            "estimated_monthly_cost": estimated_monthly,
        }

    @staticmethod
    def _estimate_monthly_cost(instance_types: list[str], node_count: int) -> float:
        """Estimate monthly cost from instance types and node count."""
        if not instance_types or node_count <= 0:
            return 0.0
        # Use the first instance type for pricing (EKS nodegroups typically use one)
        itype = instance_types[0]
        hourly = _HOURLY_PRICES.get(itype, 0.0)
        return round(hourly * 730 * node_count, 2)  # ~730 hours/month
