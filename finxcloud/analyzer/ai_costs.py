"""AI/ML service cost tracking for FinXCloud."""

import logging
from datetime import date, timedelta

import boto3
from botocore.exceptions import ClientError

log = logging.getLogger(__name__)

# AWS services classified as AI/ML
AI_ML_SERVICES = [
    "Amazon SageMaker",
    "Amazon Bedrock",
    "Amazon Comprehend",
    "Amazon Rekognition",
    "Amazon Textract",
    "Amazon Polly",
    "Amazon Transcribe",
    "Amazon Translate",
    "Amazon Lex",
    "Amazon Personalize",
    "Amazon Forecast",
    "Amazon Kendra",
]


class AICostAnalyzer:
    """Track AI/ML service costs (SageMaker, Bedrock, Comprehend, etc.)."""

    def __init__(self, session: boto3.Session) -> None:
        self.session = session
        self._client = session.client("ce")

    def get_ai_costs(self, days: int = 30) -> dict:
        """Get cost breakdown for AI/ML services from Cost Explorer.

        Returns:
            Dict with keys: services (list), total (float), daily_trend (list).
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        time_period = {
            "Start": start_date.isoformat(),
            "End": end_date.isoformat(),
        }

        services = self._get_service_breakdown(time_period)
        daily_trend = self._get_daily_trend(time_period)
        total = sum(s["amount"] for s in services)

        return {
            "services": services,
            "total": round(total, 4),
            "daily_trend": daily_trend,
            "period_days": days,
        }

    def _get_service_breakdown(self, time_period: dict) -> list[dict]:
        """Get cost per AI/ML service."""
        try:
            response = self._client.get_cost_and_usage(
                TimePeriod=time_period,
                Granularity="MONTHLY",
                Metrics=["UnblendedCost"],
                Filter={
                    "Dimensions": {
                        "Key": "SERVICE",
                        "Values": AI_ML_SERVICES,
                    },
                },
                GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
            )
        except ClientError as exc:
            code = exc.response["Error"].get("Code", "")
            if code in ("OptInRequired", "AccessDeniedException", "BillingAccessDenied"):
                log.warning("Cost Explorer not accessible for AI costs: %s", code)
                return []
            raise

        aggregated: dict[str, float] = {}
        for tp in response.get("ResultsByTime", []):
            for group in tp.get("Groups", []):
                service = group["Keys"][0]
                amount = float(
                    group.get("Metrics", {}).get("UnblendedCost", {}).get("Amount", 0.0)
                )
                aggregated[service] = aggregated.get(service, 0.0) + amount

        results = [
            {"service": svc, "amount": round(amt, 4)}
            for svc, amt in aggregated.items()
            if amt > 0.001
        ]
        results.sort(key=lambda r: r["amount"], reverse=True)
        return results

    def _get_daily_trend(self, time_period: dict) -> list[dict]:
        """Get daily AI/ML cost trend."""
        try:
            response = self._client.get_cost_and_usage(
                TimePeriod=time_period,
                Granularity="DAILY",
                Metrics=["UnblendedCost"],
                Filter={
                    "Dimensions": {
                        "Key": "SERVICE",
                        "Values": AI_ML_SERVICES,
                    },
                },
            )
        except ClientError:
            log.warning("Failed to get daily AI cost trend")
            return []

        results: list[dict] = []
        for tp in response.get("ResultsByTime", []):
            day = tp["TimePeriod"]["Start"]
            amount = float(
                tp.get("Total", {}).get("UnblendedCost", {}).get("Amount", 0.0)
            )
            results.append({"date": day, "amount": round(amount, 4)})
        return results
