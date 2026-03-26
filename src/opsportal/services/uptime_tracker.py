"""Uptime tracker — records historical availability data for each tool.

Stores health check results over time so the portal can display
uptime percentages, availability timelines, and incident history.
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock

from opsportal.core.errors import get_logger

logger = get_logger("services.uptime_tracker")


@dataclass(frozen=True, slots=True)
class UptimeRecord:
    timestamp: float
    healthy: bool
    latency_ms: float = 0.0

    @property
    def time_str(self) -> str:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.timestamp))


@dataclass(slots=True)
class ToolUptimeSummary:
    slug: str
    total_checks: int = 0
    healthy_checks: int = 0
    last_check: float = 0.0
    last_healthy: bool = False
    current_streak_start: float = 0.0
    avg_latency_ms: float = 0.0
    incidents: list[dict] = field(default_factory=list)

    @property
    def uptime_percent(self) -> float:
        if self.total_checks == 0:
            return 100.0
        return round((self.healthy_checks / self.total_checks) * 100, 2)

    def to_dict(self) -> dict:
        return {
            "slug": self.slug,
            "total_checks": self.total_checks,
            "healthy_checks": self.healthy_checks,
            "uptime_percent": self.uptime_percent,
            "last_check": self.last_check,
            "last_check_str": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.last_check))
            if self.last_check
            else "",
            "last_healthy": self.last_healthy,
            "avg_latency_ms": round(self.avg_latency_ms, 1),
            "incidents": self.incidents[-20:],  # last 20 incidents
        }


class UptimeTracker:
    """Tracks tool availability over time with persistence."""

    MAX_RECORDS_PER_TOOL = 2880  # 24h at 30s intervals

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._records: dict[str, list[UptimeRecord]] = defaultdict(list)
        self._summaries: dict[str, ToolUptimeSummary] = {}
        self._lock = Lock()
        self._load_summaries()

    def record(self, slug: str, healthy: bool, latency_ms: float = 0.0) -> None:
        """Record a health check result."""
        rec = UptimeRecord(timestamp=time.time(), healthy=healthy, latency_ms=latency_ms)

        with self._lock:
            records = self._records[slug]
            records.append(rec)
            # Trim to limit
            if len(records) > self.MAX_RECORDS_PER_TOOL:
                self._records[slug] = records[-self.MAX_RECORDS_PER_TOOL :]

            summary = self._summaries.setdefault(slug, ToolUptimeSummary(slug=slug))
            summary.total_checks += 1
            if healthy:
                summary.healthy_checks += 1
            summary.last_check = rec.timestamp
            summary.last_healthy = healthy

            # Update average latency (exponential moving average)
            if summary.avg_latency_ms == 0:
                summary.avg_latency_ms = latency_ms
            else:
                summary.avg_latency_ms = summary.avg_latency_ms * 0.9 + latency_ms * 0.1

            # Track incidents (transitions from healthy → unhealthy)
            if not healthy and len(records) >= 2 and records[-2].healthy:
                summary.incidents.append(
                    {
                        "start": rec.timestamp,
                        "start_str": rec.time_str,
                        "type": "down",
                    }
                )
            elif (
                healthy
                and len(records) >= 2
                and not records[-2].healthy
                and summary.incidents
                and "end" not in summary.incidents[-1]
            ):
                # Recovery — close last incident
                summary.incidents[-1]["end"] = rec.timestamp
                summary.incidents[-1]["end_str"] = rec.time_str
                duration = rec.timestamp - summary.incidents[-1]["start"]
                summary.incidents[-1]["duration_seconds"] = round(duration, 1)

        self._persist_summary(slug)

    def get_summary(self, slug: str) -> ToolUptimeSummary:
        return self._summaries.get(slug, ToolUptimeSummary(slug=slug))

    def get_all_summaries(self) -> dict[str, ToolUptimeSummary]:
        return dict(self._summaries)

    def get_timeline(self, slug: str, limit: int = 100) -> list[dict]:
        """Return recent health check records for a tool."""
        records = self._records.get(slug, [])
        return [
            {
                "timestamp": r.timestamp,
                "time_str": r.time_str,
                "healthy": r.healthy,
                "latency_ms": round(r.latency_ms, 1),
            }
            for r in records[-limit:]
        ]

    def _persist_summary(self, slug: str) -> None:
        """Write summary to disk for persistence across restarts."""
        summary = self._summaries.get(slug)
        if not summary:
            return
        path = self._data_dir / f"{slug}.json"
        try:
            path.write_text(
                json.dumps(summary.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            logger.exception("Failed to persist uptime summary for %s", slug)

    def _load_summaries(self) -> None:
        """Load persisted summaries from disk."""
        for f in self._data_dir.iterdir():
            if f.is_file() and f.suffix == ".json":
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    slug = data.get("slug", f.stem)
                    self._summaries[slug] = ToolUptimeSummary(
                        slug=slug,
                        total_checks=data.get("total_checks", 0),
                        healthy_checks=data.get("healthy_checks", 0),
                        last_check=data.get("last_check", 0),
                        last_healthy=data.get("last_healthy", False),
                        avg_latency_ms=data.get("avg_latency_ms", 0),
                        incidents=data.get("incidents", []),
                    )
                except (json.JSONDecodeError, OSError):
                    pass
