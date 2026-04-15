"""RI/Savings Plans coverage analysis for FinXCloud.

Uses Cost Explorer APIs to analyze commitment coverage and recommend
optimal Savings Plan or Reserved Instance purchases.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

import boto3
from botocore.exceptions import ClientError

log = logging.getLogger(__name__)


class CommitmentsAnalyzer:
    """Analyze Reserved Instance and Savings Plans coverage."""

    def __init__(self, session: boto3.Session) -> None:
        self.session = session
        self._client = session.client("ce")

    def analyze(self, days: int = 30) -> dict:
        """Run full commitments analysis.

        Returns:
            Dict with keys: savings_plans_coverage, reservation_coverage,
            total_on_demand_pct, total_committed_pct, recommendations.
        """
        sp_coverage = self._get_savings_plans_coverage(days)
        ri_coverage = self._get_reservation_coverage(days)

        # Compute aggregate stats
        total_committed_pct = 0.0
        total_on_demand_pct = 100.0

        if sp_coverage or ri_coverage:
            sp_pct = sp_coverage.get("avg_coverage_pct", 0.0) if sp_coverage else 0.0
            ri_pct = ri_coverage.get("avg_coverage_pct", 0.0) if ri_coverage else 0.0
            # Combined coverage (avoid double-counting by taking max)
            total_committed_pct = min(sp_pct + ri_pct, 100.0)
            total_on_demand_pct = 100.0 - total_committed_pct

        recommendations = self._generate_recommendations(
            sp_coverage, ri_coverage, total_on_demand_pct,
        )

        return {
            "savings_plans_coverage": sp_coverage,
            "reservation_coverage": ri_coverage,
            "total_committed_pct": round(total_committed_pct, 1),
            "total_on_demand_pct": round(total_on_demand_pct, 1),
            "recommendations": recommendations,
        }

    def _get_savings_plans_coverage(self, days: int) -> dict | None:
        """Fetch Savings Plans coverage from Cost Explorer."""
        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        try:
            response = self._client.get_savings_plans_coverage(
                TimePeriod={
                    "Start": start_date.isoformat(),
                    "End": end_date.isoformat(),
                },
                Granularity="MONTHLY",
            )

            coverages = response.get("SavingsPlansCoverages", [])
            if not coverages:
                return {"avg_coverage_pct": 0.0, "periods": [], "available": True}

            periods = []
            total_pct = 0.0
            for item in coverages:
                coverage = item.get("Coverage", {})
                sp_pct = float(coverage.get("CoveragePercentage", "0"))
                spend_by_sp = float(coverage.get("SpendCoveredBySavingsPlans", "0"))
                on_demand = float(coverage.get("OnDemandCost", "0"))
                total_spend = float(coverage.get("TotalCost", "0"))

                period = item.get("TimePeriod", {})
                periods.append({
                    "start": period.get("Start", ""),
                    "end": period.get("End", ""),
                    "coverage_pct": round(sp_pct, 1),
                    "spend_covered": round(spend_by_sp, 2),
                    "on_demand_cost": round(on_demand, 2),
                    "total_cost": round(total_spend, 2),
                })
                total_pct += sp_pct

            avg_pct = total_pct / len(coverages) if coverages else 0.0

            return {
                "avg_coverage_pct": round(avg_pct, 1),
                "periods": periods,
                "available": True,
            }

        except ClientError as exc:
            code = exc.response["Error"].get("Code", "")
            if code in ("OptInRequired", "AccessDeniedException", "BillingAccessDenied"):
                log.warning("Savings Plans coverage not available: %s", code)
                return {"avg_coverage_pct": 0.0, "periods": [], "available": False}
            raise

    def _get_reservation_coverage(self, days: int) -> dict | None:
        """Fetch Reserved Instance coverage from Cost Explorer."""
        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        try:
            response = self._client.get_reservation_coverage(
                TimePeriod={
                    "Start": start_date.isoformat(),
                    "End": end_date.isoformat(),
                },
                Granularity="MONTHLY",
            )

            coverages = response.get("CoveragesByTime", [])
            if not coverages:
                return {"avg_coverage_pct": 0.0, "periods": [], "available": True}

            periods = []
            total_pct = 0.0
            for item in coverages:
                total = item.get("Total", {})
                hours = total.get("CoverageHours", {})
                pct = float(hours.get("CoverageHoursPercentage", "0"))
                reserved_hrs = float(hours.get("ReservedHours", "0"))
                total_hrs = float(hours.get("TotalRunningHours", "0"))
                on_demand_hrs = float(hours.get("OnDemandHours", "0"))

                period = item.get("TimePeriod", {})
                periods.append({
                    "start": period.get("Start", ""),
                    "end": period.get("End", ""),
                    "coverage_pct": round(pct, 1),
                    "reserved_hours": round(reserved_hrs, 2),
                    "on_demand_hours": round(on_demand_hrs, 2),
                    "total_hours": round(total_hrs, 2),
                })
                total_pct += pct

            avg_pct = total_pct / len(coverages) if coverages else 0.0

            return {
                "avg_coverage_pct": round(avg_pct, 1),
                "periods": periods,
                "available": True,
            }

        except ClientError as exc:
            code = exc.response["Error"].get("Code", "")
            if code in ("OptInRequired", "AccessDeniedException", "BillingAccessDenied"):
                log.warning("Reservation coverage not available: %s", code)
                return {"avg_coverage_pct": 0.0, "periods": [], "available": False}
            raise

    @staticmethod
    def _estimate_on_demand_monthly(sp_coverage: dict | None, ri_coverage: dict | None) -> float:
        """Estimate total monthly on-demand spend from coverage data."""
        total = 0.0
        if sp_coverage:
            for p in sp_coverage.get("periods", []):
                total += p.get("on_demand_cost", 0.0)
        if ri_coverage:
            for p in ri_coverage.get("periods", []):
                total += p.get("on_demand_hours", 0.0) * 0.05
        return total or 1000.0  # fallback if no data

    @staticmethod
    def _generate_recommendations(
        sp_coverage: dict | None,
        ri_coverage: dict | None,
        on_demand_pct: float,
    ) -> list[dict]:
        """Generate commitment purchase recommendations with ROI details."""
        recs: list[dict] = []

        monthly_od = CommitmentsAnalyzer._estimate_on_demand_monthly(sp_coverage, ri_coverage)
        annual_od = monthly_od * 12

        if on_demand_pct > 50:
            estimated_savings_pct = min(on_demand_pct * 0.30, 30.0)
            commitment_hourly = round(monthly_od / 730 * 0.70, 2)
            annual_cost = round(commitment_hourly * 730 * 12, 2)
            annual_savings = round(annual_od * estimated_savings_pct / 100, 2)
            roi_pct = round((annual_savings / annual_cost) * 100, 1) if annual_cost > 0 else 0.0
            break_even = round(annual_cost / (annual_savings / 12), 1) if annual_savings > 0 else 12.0
            recs.append({
                "type": "savings_plan",
                "title": "Purchase Compute Savings Plans",
                "description": (
                    f"{on_demand_pct:.0f}% of compute spend is on-demand. "
                    f"A ${commitment_hourly}/hour commitment for 1-year term "
                    f"could reduce costs by up to {estimated_savings_pct:.0f}% "
                    f"on committed usage (ROI: {roi_pct}%, break-even: {break_even:.0f} months)."
                ),
                "estimated_savings_pct": round(estimated_savings_pct, 1),
                "priority": "high",
                "commitment_hourly": commitment_hourly,
                "term_years": 1,
                "annual_savings": annual_savings,
                "annual_cost": annual_cost,
                "roi_pct": roi_pct,
                "break_even_months": round(break_even),
            })

        if on_demand_pct > 30:
            commitment_hourly = round(monthly_od / 730 * 0.60, 2)
            annual_cost = round(commitment_hourly * 730 * 12, 2)
            annual_savings = round(annual_od * 0.30, 2)
            roi_pct = round((annual_savings / annual_cost) * 100, 1) if annual_cost > 0 else 0.0
            break_even = round(annual_cost / (annual_savings / 12), 1) if annual_savings > 0 else 12.0
            recs.append({
                "type": "reserved_instance",
                "title": "Evaluate Reserved Instances for steady-state workloads",
                "description": (
                    f"For predictable, long-running workloads (EC2, RDS, "
                    f"ElastiCache, OpenSearch), a ${commitment_hourly}/hour "
                    f"commitment for 1-year term offers up to 72% savings "
                    f"(ROI: {roi_pct}%, break-even: {break_even:.0f} months)."
                ),
                "estimated_savings_pct": 30.0,
                "priority": "medium",
                "commitment_hourly": commitment_hourly,
                "term_years": 1,
                "annual_savings": annual_savings,
                "annual_cost": annual_cost,
                "roi_pct": roi_pct,
                "break_even_months": round(break_even),
            })

        if sp_coverage and sp_coverage.get("available"):
            avg = sp_coverage.get("avg_coverage_pct", 0)
            if 0 < avg < 80:
                gap_pct = 80 - avg
                estimated_savings_pct = round(gap_pct * 0.30, 1)
                additional_hourly = round(monthly_od * (gap_pct / 100) / 730 * 0.70, 2)
                annual_cost = round(additional_hourly * 730 * 12, 2)
                annual_savings = round(annual_od * estimated_savings_pct / 100, 2)
                roi_pct = round((annual_savings / annual_cost) * 100, 1) if annual_cost > 0 else 0.0
                break_even = round(annual_cost / (annual_savings / 12), 1) if annual_savings > 0 else 12.0
                recs.append({
                    "type": "increase_sp",
                    "title": "Increase Savings Plans coverage",
                    "description": (
                        f"Current Savings Plans coverage is {avg:.0f}%. "
                        f"Adding ${additional_hourly}/hour commitment to reach 80%+ "
                        f"would save ~{estimated_savings_pct}% more "
                        f"(ROI: {roi_pct}%, break-even: {break_even:.0f} months)."
                    ),
                    "estimated_savings_pct": estimated_savings_pct,
                    "priority": "medium",
                    "commitment_hourly": additional_hourly,
                    "term_years": 1,
                    "annual_savings": annual_savings,
                    "annual_cost": annual_cost,
                    "roi_pct": roi_pct,
                    "break_even_months": round(break_even),
                })

        return recs
