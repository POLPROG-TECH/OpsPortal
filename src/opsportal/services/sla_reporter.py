"""SLA reporter — generates uptime SLA reports with target comparisons.

Produces monthly/weekly reports from UptimeTracker data, with CSV
export and summary statistics.
"""

from __future__ import annotations

import csv
import io
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from opsportal.core.errors import get_logger

if TYPE_CHECKING:
    from opsportal.services.uptime_tracker import UptimeTracker

logger = get_logger("services.sla_reporter")


@dataclass(slots=True)
class SLATarget:
    tool_slug: str
    target_percent: float = 99.9
    name: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_slug": self.tool_slug,
            "target_percent": self.target_percent,
            "name": self.name,
        }


@dataclass(slots=True)
class SLAToolReport:
    tool_slug: str
    tool_name: str
    target_percent: float
    actual_percent: float
    total_checks: int
    healthy_checks: int
    avg_latency_ms: float
    incidents_count: int
    meets_sla: bool

    @property
    def gap_percent(self) -> float:
        return round(self.actual_percent - self.target_percent, 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_slug": self.tool_slug,
            "tool_name": self.tool_name,
            "target_percent": self.target_percent,
            "actual_percent": self.actual_percent,
            "gap_percent": self.gap_percent,
            "total_checks": self.total_checks,
            "healthy_checks": self.healthy_checks,
            "avg_latency_ms": round(self.avg_latency_ms, 1),
            "incidents_count": self.incidents_count,
            "meets_sla": self.meets_sla,
        }


@dataclass(slots=True)
class SLAReport:
    generated_at: float
    period: str
    tool_reports: list[SLAToolReport]
    overall_percent: float
    tools_meeting_sla: int
    tools_total: int

    @property
    def generated_at_str(self) -> str:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.generated_at))

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "generated_at_str": self.generated_at_str,
            "period": self.period,
            "overall_percent": self.overall_percent,
            "tools_meeting_sla": self.tools_meeting_sla,
            "tools_total": self.tools_total,
            "tool_reports": [r.to_dict() for r in self.tool_reports],
        }


class SLAReporter:
    """Generates SLA reports from uptime tracking data."""

    DEFAULT_TARGET = 99.9

    def __init__(self) -> None:
        self._targets: dict[str, SLATarget] = {}

    def set_target(self, tool_slug: str, target_percent: float, name: str = "") -> SLATarget:
        target = SLATarget(
            tool_slug=tool_slug,
            target_percent=target_percent,
            name=name,
        )
        self._targets[tool_slug] = target
        return target

    def get_targets(self) -> list[SLATarget]:
        return list(self._targets.values())

    def generate_report(
        self,
        uptime_tracker: UptimeTracker,
        period: str = "current",
    ) -> SLAReport:
        """Generate an SLA report from current uptime data."""
        summaries = uptime_tracker.get_all_summaries()
        tool_reports: list[SLAToolReport] = []

        for slug, summary in summaries.items():
            target = self._targets.get(slug)
            target_pct = target.target_percent if target else self.DEFAULT_TARGET

            report = SLAToolReport(
                tool_slug=slug,
                tool_name=target.name if target and target.name else slug,
                target_percent=target_pct,
                actual_percent=summary.uptime_percent,
                total_checks=summary.total_checks,
                healthy_checks=summary.healthy_checks,
                avg_latency_ms=summary.avg_latency_ms,
                incidents_count=len(summary.incidents),
                meets_sla=summary.uptime_percent >= target_pct,
            )
            tool_reports.append(report)

        # Sort: worst performers first
        tool_reports.sort(key=lambda r: r.actual_percent)

        total = len(tool_reports)
        meeting = sum(1 for r in tool_reports if r.meets_sla)
        overall = sum(r.actual_percent for r in tool_reports) / total if total else 100.0

        return SLAReport(
            generated_at=time.time(),
            period=period,
            tool_reports=tool_reports,
            overall_percent=round(overall, 2),
            tools_meeting_sla=meeting,
            tools_total=total,
        )

    def report_to_csv(self, report: SLAReport) -> str:
        """Export an SLA report as CSV string."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "Tool",
                "Target %",
                "Actual %",
                "Gap %",
                "Checks",
                "Healthy",
                "Avg Latency (ms)",
                "Incidents",
                "Meets SLA",
            ]
        )
        for r in report.tool_reports:
            writer.writerow(
                [
                    r.tool_name,
                    r.target_percent,
                    r.actual_percent,
                    r.gap_percent,
                    r.total_checks,
                    r.healthy_checks,
                    round(r.avg_latency_ms, 1),
                    r.incidents_count,
                    "Yes" if r.meets_sla else "No",
                ]
            )
        return output.getvalue()
