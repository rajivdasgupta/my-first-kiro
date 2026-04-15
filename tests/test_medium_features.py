"""Tests for the 5 medium-impact features."""

import json
import pytest
from datetime import datetime, timedelta, timezone


class TestCommitmentsROI:
    """Test enhanced commitment recommendations with ROI fields."""

    def test_high_on_demand_includes_roi_fields(self):
        from finxcloud.analyzer.commitments import CommitmentsAnalyzer

        recs = CommitmentsAnalyzer._generate_recommendations(None, None, 70.0)
        assert len(recs) >= 2
        sp_rec = next(r for r in recs if r["type"] == "savings_plan")
        for field in ("commitment_hourly", "term_years", "annual_savings",
                      "annual_cost", "roi_pct", "break_even_months"):
            assert field in sp_rec
        assert sp_rec["term_years"] == 1
        assert sp_rec["roi_pct"] > 0

    def test_ri_recommendation_includes_roi(self):
        from finxcloud.analyzer.commitments import CommitmentsAnalyzer

        recs = CommitmentsAnalyzer._generate_recommendations(None, None, 40.0)
        ri_rec = next(r for r in recs if r["type"] == "reserved_instance")
        assert ri_rec["commitment_hourly"] > 0
        assert ri_rec["annual_savings"] > 0

    def test_increase_sp_includes_roi(self):
        from finxcloud.analyzer.commitments import CommitmentsAnalyzer

        sp_cov = {"avg_coverage_pct": 50.0, "available": True, "periods": []}
        recs = CommitmentsAnalyzer._generate_recommendations(sp_cov, None, 50.0)
        sp_recs = [r for r in recs if r["type"] == "increase_sp"]
        assert len(sp_recs) == 1
        assert "roi_pct" in sp_recs[0]

    def test_low_on_demand_no_recs(self):
        from finxcloud.analyzer.commitments import CommitmentsAnalyzer

        recs = CommitmentsAnalyzer._generate_recommendations(None, None, 20.0)
        assert len(recs) == 0


class TestSpotCandidates:
    """Test spot instance candidate detection."""

    def test_non_prod_instance_flagged(self):
        from finxcloud.analyzer.recommendations import RecommendationEngine

        resources = [{
            "resource_type": "ec2_instance", "instance_id": "i-test123",
            "resource_id": "i-test123", "state": "running",
            "type": "t3.medium", "region": "us-east-1",
            "tags": {"env": "dev", "Name": "dev-web"},
        }]
        engine = RecommendationEngine(resources, {}, None)
        recs = engine.generate_recommendations()
        spot_recs = [r for r in recs if "spot_savings_pct" in r]
        assert len(spot_recs) >= 1
        assert spot_recs[0]["spot_savings_pct"] == 65

    def test_batch_workload_flagged(self):
        from finxcloud.analyzer.recommendations import RecommendationEngine

        resources = [{
            "resource_type": "ec2_instance", "instance_id": "i-batch456",
            "resource_id": "i-batch456", "state": "running",
            "type": "m5.large", "region": "us-east-1",
            "tags": {"Name": "batch-processor-01"},
        }]
        engine = RecommendationEngine(resources, {}, None)
        recs = engine.generate_recommendations()
        spot_recs = [r for r in recs if "spot_savings_pct" in r]
        assert len(spot_recs) >= 1

    def test_production_instance_not_flagged(self):
        from finxcloud.analyzer.recommendations import RecommendationEngine

        resources = [{
            "resource_type": "ec2_instance", "instance_id": "i-prod789",
            "resource_id": "i-prod789", "state": "running",
            "type": "m5.large", "region": "us-east-1",
            "tags": {"env": "production", "Name": "api-server"},
        }]
        engine = RecommendationEngine(resources, {}, None)
        recs = engine.generate_recommendations()
        spot_recs = [r for r in recs if "spot_savings_pct" in r]
        assert len(spot_recs) == 0

    def test_stopped_instance_not_flagged_for_spot(self):
        from finxcloud.analyzer.recommendations import RecommendationEngine

        resources = [{
            "resource_type": "ec2_instance", "instance_id": "i-stopped",
            "resource_id": "i-stopped", "state": "stopped",
            "type": "t3.medium", "region": "us-east-1",
            "tags": {"env": "dev"},
        }]
        engine = RecommendationEngine(resources, {}, None)
        recs = engine.generate_recommendations()
        spot_recs = [r for r in recs if "spot_savings_pct" in r]
        assert len(spot_recs) == 0


class TestVirtualTags:
    """Test virtual tag manager."""

    def test_add_and_list_rules(self, tmp_path):
        from finxcloud.analyzer.virtual_tags import VirtualTagManager

        mgr = VirtualTagManager(path=str(tmp_path / "vt.json"))
        rule = mgr.add_rule("Test Rule", "service", "ec2*", "Team", "Platform")
        assert rule["name"] == "Test Rule"
        rules = mgr.list_rules()
        assert len(rules) == 1
        assert rules[0]["tag_key"] == "Team"

    def test_delete_rule(self, tmp_path):
        from finxcloud.analyzer.virtual_tags import VirtualTagManager

        mgr = VirtualTagManager(path=str(tmp_path / "vt.json"))
        rule = mgr.add_rule("Rule1", "region", "us-east-1", "Region", "East")
        assert mgr.delete_rule(rule["id"])
        assert len(mgr.list_rules()) == 0
        assert not mgr.delete_rule("nonexistent")

    def test_apply_tags_resource_type_match(self, tmp_path):
        from finxcloud.analyzer.virtual_tags import VirtualTagManager

        mgr = VirtualTagManager(path=str(tmp_path / "vt.json"))
        mgr.add_rule("EC2 Team", "resource_type", "ec2_instance", "Team", "Infra")
        resources = [
            {"resource_type": "ec2_instance", "resource_id": "i-123"},
            {"resource_type": "s3_bucket", "resource_id": "my-bucket"},
        ]
        tagged = mgr.apply_tags(resources)
        assert tagged[0].get("virtual_tags", {}).get("Team") == "Infra"
        assert "Team" not in tagged[1].get("virtual_tags", {})

    def test_apply_tags_name_pattern(self, tmp_path):
        from finxcloud.analyzer.virtual_tags import VirtualTagManager

        mgr = VirtualTagManager(path=str(tmp_path / "vt.json"))
        mgr.add_rule("Dev Pattern", "name_pattern", "dev-.*", "Env", "Development")
        resources = [
            {"resource_type": "ec2_instance", "name": "dev-web-01"},
            {"resource_type": "ec2_instance", "name": "prod-api-01"},
        ]
        tagged = mgr.apply_tags(resources)
        assert tagged[0]["virtual_tags"]["Env"] == "Development"
        assert "Env" not in tagged[1].get("virtual_tags", {})

    def test_invalid_match_type_raises(self, tmp_path):
        from finxcloud.analyzer.virtual_tags import VirtualTagManager

        mgr = VirtualTagManager(path=str(tmp_path / "vt.json"))
        with pytest.raises(ValueError, match="Invalid match_type"):
            mgr.add_rule("Bad", "invalid_type", "val", "Key", "Val")


class TestReportExecutor:
    """Test scheduled report executor."""

    def test_is_due_no_last_sent(self, tmp_path):
        from finxcloud.scheduler.report_executor import ReportExecutor
        from finxcloud.scheduler.report_scheduler import ReportScheduleManager

        mgr = ReportScheduleManager(path=str(tmp_path / "sched.json"))
        executor = ReportExecutor(manager=mgr)
        schedule = {"id": "t1", "frequency": "daily", "enabled": True}
        assert executor._is_due(schedule, datetime.now(timezone.utc))

    def test_is_due_after_interval(self, tmp_path):
        from finxcloud.scheduler.report_executor import ReportExecutor
        from finxcloud.scheduler.report_scheduler import ReportScheduleManager

        mgr = ReportScheduleManager(path=str(tmp_path / "sched.json"))
        executor = ReportExecutor(manager=mgr)
        now = datetime.now(timezone.utc)
        schedule = {
            "id": "t2", "frequency": "daily",
            "last_sent_at": (now - timedelta(days=2)).isoformat(),
        }
        assert executor._is_due(schedule, now)

    def test_not_due_within_interval(self, tmp_path):
        from finxcloud.scheduler.report_executor import ReportExecutor
        from finxcloud.scheduler.report_scheduler import ReportScheduleManager

        mgr = ReportScheduleManager(path=str(tmp_path / "sched.json"))
        executor = ReportExecutor(manager=mgr)
        now = datetime.now(timezone.utc)
        schedule = {
            "id": "t3", "frequency": "weekly",
            "last_sent_at": (now - timedelta(days=3)).isoformat(),
        }
        assert not executor._is_due(schedule, now)

    def test_send_report_no_recipients(self, tmp_path):
        from finxcloud.scheduler.report_executor import ReportExecutor
        from finxcloud.scheduler.report_scheduler import ReportScheduleManager

        mgr = ReportScheduleManager(path=str(tmp_path / "sched.json"))
        executor = ReportExecutor(manager=mgr)
        result = executor._send_report({"id": "t4", "recipients": []})
        assert result["status"] == "skipped"

    def test_last_sent_at_updated(self, tmp_path):
        from finxcloud.scheduler.report_executor import ReportExecutor
        from finxcloud.scheduler.report_scheduler import ReportScheduleManager

        mgr = ReportScheduleManager(path=str(tmp_path / "sched.json"))
        mgr.add_schedule("Test", "daily", ["user@example.com"])
        executor = ReportExecutor(manager=mgr)
        schedules = mgr.list_schedules()
        executor._update_last_sent(schedules[0]["id"], datetime.now(timezone.utc))
        updated = mgr.list_schedules()
        assert updated[0].get("last_sent_at") is not None


class TestEstimateOnDemandMonthly:
    """Test on-demand spend estimation helper."""

    def test_with_sp_data(self):
        from finxcloud.analyzer.commitments import CommitmentsAnalyzer

        sp = {"periods": [{"on_demand_cost": 500.0}, {"on_demand_cost": 600.0}]}
        assert CommitmentsAnalyzer._estimate_on_demand_monthly(sp, None) == 1100.0

    def test_fallback_no_data(self):
        from finxcloud.analyzer.commitments import CommitmentsAnalyzer

        assert CommitmentsAnalyzer._estimate_on_demand_monthly(None, None) == 1000.0
