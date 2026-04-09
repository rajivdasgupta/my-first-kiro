"""CSV output writer for FinXCloud cost optimization reports."""

from __future__ import annotations

import csv
import io
import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

__all__ = ["CSVWriter"]


class CSVWriter:
    """Generate CSV reports from scan results."""

    def __init__(self, output_dir: str = "reports") -> None:
        self.output_dir = output_dir

    def write_findings_csv(self, recommendations: list[dict]) -> str:
        """Write recommendations/findings to a CSV file on disk."""
        os.makedirs(self.output_dir, exist_ok=True)
        file_path = str(Path(self.output_dir) / "findings_report.csv")
        content = self.build_findings_bytes(recommendations)
        with open(file_path, "wb") as fh:
            fh.write(content)
        log.info("CSV findings report written: %s", file_path)
        return file_path

    @staticmethod
    def build_findings_bytes(recommendations: list[dict]) -> bytes:
        """Build CSV bytes for findings/recommendations."""
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "Category",
            "Title",
            "Description",
            "Resource ID",
            "Region",
            "Effort Level",
            "Estimated Monthly Savings (USD)",
            "Well-Architected Pillar",
            "Action",
        ])
        for rec in recommendations:
            writer.writerow([
                rec.get("category", ""),
                rec.get("title", ""),
                rec.get("description", ""),
                rec.get("resource_id", ""),
                rec.get("region", ""),
                rec.get("effort_level", ""),
                f"{rec.get('estimated_monthly_savings', 0):.2f}",
                rec.get("pillar", ""),
                rec.get("action", ""),
            ])
        return buf.getvalue().encode("utf-8")

    @staticmethod
    def build_resources_bytes(resources: list[dict]) -> bytes:
        """Build CSV bytes for the full resource inventory."""
        if not resources:
            return b"No resources found.\n"
        buf = io.StringIO()
        writer = csv.writer(buf)
        headers = list(resources[0].keys())
        writer.writerow(headers)
        for res in resources:
            writer.writerow([res.get(h, "") for h in headers])
        return buf.getvalue().encode("utf-8")
