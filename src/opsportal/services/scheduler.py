"""Scheduler service — cron-like periodic action execution.

Allows users to schedule tool actions (e.g., generate release notes every
Friday at 16:00) with a simple cron-inspired syntax.  Schedules are stored
in a JSON file and executed by an asyncio background task.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from opsportal.core.errors import get_logger

logger = get_logger("services.scheduler")


@dataclass
class ScheduledJob:
    """A scheduled periodic action."""

    job_id: str
    tool_slug: str
    action_name: str
    cron_expr: str  # simplified: "interval:Ns" or "daily:HH:MM" or "weekly:DOW:HH:MM"
    params: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    last_run: float = 0.0
    next_run: float = 0.0
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "tool_slug": self.tool_slug,
            "action_name": self.action_name,
            "cron_expr": self.cron_expr,
            "params": self.params,
            "enabled": self.enabled,
            "last_run": self.last_run,
            "last_run_str": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.last_run))
            if self.last_run
            else "",
            "next_run": self.next_run,
            "next_run_str": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.next_run))
            if self.next_run
            else "",
            "created_at": self.created_at,
        }


class Scheduler:
    """Manages and executes scheduled tool actions."""

    def __init__(self, config_path: Path) -> None:
        self._config_path = config_path
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        self._jobs: dict[str, ScheduledJob] = {}
        self._task: asyncio.Task | None = None
        self._action_callback: Any = None
        self._load()

    def set_action_callback(self, callback: Any) -> None:
        """Set the callback used to execute actions: async fn(slug, action, params)."""
        self._action_callback = callback

    def add_job(
        self,
        *,
        tool_slug: str,
        action_name: str,
        cron_expr: str,
        params: dict | None = None,
    ) -> ScheduledJob:
        """Add a new scheduled job."""
        job_id = f"{tool_slug}_{action_name}_{int(time.time() * 1000)}"
        job = ScheduledJob(
            job_id=job_id,
            tool_slug=tool_slug,
            action_name=action_name,
            cron_expr=cron_expr,
            params=params or {},
        )
        job.next_run = self._compute_next_run(job)
        self._jobs[job_id] = job
        self._save()
        logger.info("Scheduled job %s: %s/%s @ %s", job_id, tool_slug, action_name, cron_expr)
        return job

    def remove_job(self, job_id: str) -> bool:
        if job_id in self._jobs:
            del self._jobs[job_id]
            self._save()
            return True
        return False

    def toggle_job(self, job_id: str, enabled: bool) -> bool:
        job = self._jobs.get(job_id)
        if not job:
            return False
        job.enabled = enabled
        if enabled:
            job.next_run = self._compute_next_run(job)
        self._save()
        return True

    def list_jobs(self, tool_slug: str | None = None) -> list[ScheduledJob]:
        jobs = list(self._jobs.values())
        if tool_slug:
            jobs = [j for j in jobs if j.tool_slug == tool_slug]
        return sorted(jobs, key=lambda j: j.created_at, reverse=True)

    async def start(self) -> None:
        """Start the background scheduler loop."""
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Scheduler started (%d jobs)", len(self._jobs))

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def _run_loop(self) -> None:
        """Check for due jobs every 30 seconds."""
        try:
            while True:
                now = time.time()
                for job in self._jobs.values():
                    if not job.enabled or not job.next_run:
                        continue
                    if now >= job.next_run:
                        await self._execute_job(job)
                await asyncio.sleep(30)
        except asyncio.CancelledError:
            pass

    async def _execute_job(self, job: ScheduledJob) -> None:
        """Execute a due job and update timing."""
        logger.info("Executing scheduled job: %s/%s", job.tool_slug, job.action_name)
        if self._action_callback:
            try:
                await self._action_callback(job.tool_slug, job.action_name, job.params)
            except (OSError, RuntimeError):
                logger.exception("Scheduled job %s failed", job.job_id)
        job.last_run = time.time()
        job.next_run = self._compute_next_run(job)
        self._save()

    def _compute_next_run(self, job: ScheduledJob) -> float:
        """Compute next run time from cron expression.

        Supported formats:
          interval:300     — every 300 seconds
          daily:16:00      — every day at 16:00 UTC
          weekly:5:16:00   — every Friday (5=Fri, 0=Mon) at 16:00 UTC
        """
        expr = job.cron_expr.strip()
        now = time.time()

        if expr.startswith("interval:"):
            return self._parse_interval(expr, now, job.last_run)
        if expr.startswith("daily:"):
            return self._parse_daily(expr, now)
        if expr.startswith("weekly:"):
            return self._parse_weekly(expr, now)
        return 0.0

    @staticmethod
    def _parse_interval(expr: str, now: float, last_run: float) -> float:
        try:
            seconds = int(expr.split(":", 1)[1])
            return max(now, last_run + seconds) if last_run else now + seconds
        except (ValueError, IndexError):
            return 0.0

    @staticmethod
    def _parse_daily(expr: str, now: float) -> float:
        try:
            parts = expr.split(":", 2)
            hour, minute = int(parts[1]), int(parts[2])
            dt_now = datetime.now(tz=UTC)
            candidate = dt_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if candidate.timestamp() <= now:
                from datetime import timedelta

                candidate += timedelta(days=1)
            return candidate.timestamp()
        except (ValueError, IndexError):
            return 0.0

    @staticmethod
    def _parse_weekly(expr: str, now: float) -> float:
        try:
            parts = expr.split(":", 3)
            dow, hour, minute = int(parts[1]), int(parts[2]), int(parts[3])
            dt_now = datetime.now(tz=UTC)
            days_ahead = dow - dt_now.weekday()
            if days_ahead < 0:
                days_ahead += 7
            from datetime import timedelta

            candidate = dt_now.replace(
                hour=hour, minute=minute, second=0, microsecond=0
            ) + timedelta(days=days_ahead)
            if candidate.timestamp() <= now:
                candidate += timedelta(weeks=1)
            return candidate.timestamp()
        except (ValueError, IndexError):
            return 0.0

    def _save(self) -> None:
        data = [job.to_dict() for job in self._jobs.values()]
        self._config_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def _load(self) -> None:
        if not self._config_path.exists():
            return
        try:
            data = json.loads(self._config_path.read_text(encoding="utf-8"))
            for item in data:
                job = ScheduledJob(
                    job_id=item["job_id"],
                    tool_slug=item["tool_slug"],
                    action_name=item["action_name"],
                    cron_expr=item["cron_expr"],
                    params=item.get("params", {}),
                    enabled=item.get("enabled", True),
                    last_run=item.get("last_run", 0.0),
                    next_run=item.get("next_run", 0.0),
                    created_at=item.get("created_at", 0.0),
                )
                self._jobs[job.job_id] = job
        except (json.JSONDecodeError, KeyError, OSError):
            logger.exception("Failed to load scheduler config")
