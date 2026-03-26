"""Metrics collector — gathers resource usage and tool statistics for monitoring.

Provides:
  - Per-process CPU and memory metrics (via /proc on Linux, psutil-free)
  - Tool uptime, restart counts, health check latencies
  - Prometheus-compatible text exposition format
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from opsportal.core.errors import get_logger

if TYPE_CHECKING:
    from opsportal.services.process_manager import ProcessManager

logger = get_logger("services.metrics_collector")


@dataclass(slots=True)
class ToolMetrics:
    """Collected metrics for a single tool."""

    slug: str
    pid: int | None = None
    cpu_percent: float = 0.0
    memory_rss_bytes: int = 0
    memory_vms_bytes: int = 0
    uptime_seconds: float = 0.0
    restart_count: int = 0
    health_check_latency_ms: float = 0.0
    last_health_check: float = 0.0
    is_healthy: bool = False

    def to_dict(self) -> dict:
        return {
            "slug": self.slug,
            "pid": self.pid,
            "cpu_percent": round(self.cpu_percent, 2),
            "memory_rss_mb": round(self.memory_rss_bytes / (1024 * 1024), 2),
            "memory_vms_mb": round(self.memory_vms_bytes / (1024 * 1024), 2),
            "uptime_seconds": round(self.uptime_seconds, 1),
            "restart_count": self.restart_count,
            "health_check_latency_ms": round(self.health_check_latency_ms, 1),
            "is_healthy": self.is_healthy,
        }


class MetricsCollector:
    """Collects and exposes tool metrics."""

    def __init__(self) -> None:
        self._tool_metrics: dict[str, ToolMetrics] = {}
        self._restart_counts: dict[str, int] = {}
        self._portal_start_time: float = time.time()

    def record_restart(self, slug: str) -> None:
        self._restart_counts[slug] = self._restart_counts.get(slug, 0) + 1

    async def collect(self, process_manager: ProcessManager) -> dict[str, ToolMetrics]:
        """Collect current metrics from all managed processes."""
        all_procs = process_manager.get_all()

        for name, managed in all_procs.items():
            metrics = self._tool_metrics.setdefault(name, ToolMetrics(slug=name))
            metrics.pid = managed.pid
            metrics.uptime_seconds = managed.uptime_seconds
            metrics.restart_count = self._restart_counts.get(name, 0)

            if managed.pid:
                rss, vms = _read_process_memory(managed.pid)
                metrics.memory_rss_bytes = rss
                metrics.memory_vms_bytes = vms
                metrics.cpu_percent = _read_process_cpu(managed.pid)

        return dict(self._tool_metrics)

    def record_health_check(self, slug: str, healthy: bool, latency_ms: float) -> None:
        metrics = self._tool_metrics.setdefault(slug, ToolMetrics(slug=slug))
        metrics.is_healthy = healthy
        metrics.health_check_latency_ms = latency_ms
        metrics.last_health_check = time.time()

    def get_all(self) -> dict[str, ToolMetrics]:
        return dict(self._tool_metrics)

    def get_tool(self, slug: str) -> ToolMetrics | None:
        """Return metrics for a single tool, or None if not yet collected."""
        return self._tool_metrics.get(slug)

    def to_prometheus(self) -> str:
        """Render metrics in Prometheus text exposition format."""
        lines: list[str] = []
        lines.append("# HELP opsportal_uptime_seconds Portal uptime in seconds")
        lines.append("# TYPE opsportal_uptime_seconds gauge")
        lines.append(f"opsportal_uptime_seconds {time.time() - self._portal_start_time:.1f}")

        lines.append("")
        lines.append("# HELP opsportal_tool_up Whether the tool process is running (1=up, 0=down)")
        lines.append("# TYPE opsportal_tool_up gauge")
        for slug, m in self._tool_metrics.items():
            up = 1 if m.pid else 0
            lines.append(f'opsportal_tool_up{{tool="{slug}"}} {up}')

        lines.append("")
        lines.append("# HELP opsportal_tool_uptime_seconds Tool process uptime")
        lines.append("# TYPE opsportal_tool_uptime_seconds gauge")
        for slug, m in self._tool_metrics.items():
            lines.append(f'opsportal_tool_uptime_seconds{{tool="{slug}"}} {m.uptime_seconds:.1f}')

        lines.append("")
        lines.append("# HELP opsportal_tool_memory_rss_bytes Resident memory in bytes")
        lines.append("# TYPE opsportal_tool_memory_rss_bytes gauge")
        for slug, m in self._tool_metrics.items():
            lines.append(f'opsportal_tool_memory_rss_bytes{{tool="{slug}"}} {m.memory_rss_bytes}')

        lines.append("")
        lines.append("# HELP opsportal_tool_restarts_total Number of tool restarts")
        lines.append("# TYPE opsportal_tool_restarts_total counter")
        for slug, m in self._tool_metrics.items():
            lines.append(f'opsportal_tool_restarts_total{{tool="{slug}"}} {m.restart_count}')

        lines.append("")
        lines.append("# HELP opsportal_tool_health_check_latency_ms Health check latency")
        lines.append("# TYPE opsportal_tool_health_check_latency_ms gauge")
        for slug, m in self._tool_metrics.items():
            lines.append(
                f'opsportal_tool_health_check_latency_ms{{tool="{slug}"}} '
                f"{m.health_check_latency_ms:.1f}"
            )

        lines.append("")
        lines.append("# HELP opsportal_tool_healthy Whether last health check passed")
        lines.append("# TYPE opsportal_tool_healthy gauge")
        for slug, m in self._tool_metrics.items():
            lines.append(f'opsportal_tool_healthy{{tool="{slug}"}} {1 if m.is_healthy else 0}')

        lines.append("")
        return "\n".join(lines) + "\n"


def _read_process_memory(pid: int) -> tuple[int, int]:
    """Read RSS and VMS from /proc/{pid}/status (Linux) or fallback to 0."""
    try:
        status_path = f"/proc/{pid}/status"
        if not os.path.exists(status_path):
            return _read_process_memory_macos(pid)
        rss = vms = 0
        with open(status_path) as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    rss = int(line.split()[1]) * 1024  # kB → bytes
                elif line.startswith("VmSize:"):
                    vms = int(line.split()[1]) * 1024
        return rss, vms
    except (OSError, ValueError, IndexError):
        return 0, 0


def _read_process_memory_macos(pid: int) -> tuple[int, int]:
    """Fallback memory reading for macOS using ps command."""
    try:
        import subprocess

        result = subprocess.run(
            ["ps", "-o", "rss=,vsz=", "-p", str(pid)],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split()
            rss = int(parts[0]) * 1024  # kB → bytes
            vms = int(parts[1]) * 1024
            return rss, vms
    except (OSError, ValueError, IndexError, subprocess.TimeoutExpired):
        pass
    return 0, 0


def _read_process_cpu(pid: int) -> float:
    """Best-effort CPU percentage (returns 0.0 if unavailable)."""
    try:
        stat_path = f"/proc/{pid}/stat"
        if not os.path.exists(stat_path):
            return 0.0
        with open(stat_path) as f:
            fields = f.read().split()
        utime = int(fields[13])
        stime = int(fields[14])
        total = utime + stime
        clock_ticks = os.sysconf("SC_CLK_TCK")
        return total / clock_ticks
    except (OSError, ValueError, IndexError):
        return 0.0
