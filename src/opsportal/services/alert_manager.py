"""Alert manager - configurable threshold-based alerting.

Monitors tool metrics and triggers notifications when thresholds are
breached.  Rules are stored in a JSON file and evaluated periodically.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from opsportal.core.errors import get_logger

if TYPE_CHECKING:
    from opsportal.services.metrics_collector import MetricsCollector
    from opsportal.services.notification_service import NotificationService

logger = get_logger("services.alert_manager")


class AlertSeverity(StrEnum):
    WARNING = "warning"
    CRITICAL = "critical"


class AlertMetric(StrEnum):
    CPU_PERCENT = "cpu_percent"
    MEMORY_MB = "memory_mb"
    LATENCY_MS = "latency_ms"
    UPTIME_PERCENT = "uptime_percent"
    CONSECUTIVE_FAILURES = "consecutive_failures"


@dataclass(slots=True)
class AlertRule:
    rule_id: str
    name: str
    metric: AlertMetric
    operator: str  # ">", "<", ">=", "<="
    threshold: float
    severity: AlertSeverity = AlertSeverity.WARNING
    tool_slug: str | None = None  # None = all tools
    duration_seconds: int = 0  # must breach for N seconds
    enabled: bool = True
    cooldown_seconds: int = 300  # min time between alerts

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "metric": self.metric,
            "operator": self.operator,
            "threshold": self.threshold,
            "severity": self.severity,
            "tool_slug": self.tool_slug,
            "duration_seconds": self.duration_seconds,
            "enabled": self.enabled,
            "cooldown_seconds": self.cooldown_seconds,
        }


@dataclass(slots=True)
class ActiveAlert:
    rule_id: str
    tool_slug: str
    triggered_at: float
    current_value: float
    message: str
    severity: str
    acknowledged: bool = False

    @property
    def triggered_at_str(self) -> str:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.triggered_at))

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "tool_slug": self.tool_slug,
            "triggered_at": self.triggered_at,
            "triggered_at_str": self.triggered_at_str,
            "current_value": self.current_value,
            "message": self.message,
            "severity": self.severity,
            "acknowledged": self.acknowledged,
        }


_OPERATORS = {
    ">": lambda v, t: v > t,
    "<": lambda v, t: v < t,
    ">=": lambda v, t: v >= t,
    "<=": lambda v, t: v <= t,
}


class AlertManager:
    """Evaluates alert rules against current metrics."""

    def __init__(self, config_path: Path | None = None) -> None:
        self._config_path = config_path
        self._rules: dict[str, AlertRule] = {}
        self._active_alerts: list[ActiveAlert] = []
        self._breach_start: dict[str, float] = {}
        self._last_alert_time: dict[str, float] = {}
        self._failure_counts: dict[str, int] = {}
        if config_path and config_path.exists():
            self._load()
        else:
            self._add_defaults()

    def _add_defaults(self) -> None:
        defaults = [
            AlertRule("cpu-high", "High CPU Usage", AlertMetric.CPU_PERCENT, ">", 80),
            AlertRule(
                "mem-high",
                "High Memory",
                AlertMetric.MEMORY_MB,
                ">",
                500,
                severity=AlertSeverity.WARNING,
            ),
            AlertRule(
                "latency-high",
                "High Latency",
                AlertMetric.LATENCY_MS,
                ">",
                2000,
                severity=AlertSeverity.CRITICAL,
            ),
        ]
        for rule in defaults:
            self._rules[rule.rule_id] = rule

    def _load(self) -> None:
        try:
            data = json.loads(self._config_path.read_text("utf-8"))
            for r in data.get("rules", []):
                rule = AlertRule(
                    rule_id=r["rule_id"],
                    name=r["name"],
                    metric=AlertMetric(r["metric"]),
                    operator=r["operator"],
                    threshold=r["threshold"],
                    severity=AlertSeverity(r.get("severity", "warning")),
                    tool_slug=r.get("tool_slug"),
                    duration_seconds=r.get("duration_seconds", 0),
                    enabled=r.get("enabled", True),
                    cooldown_seconds=r.get("cooldown_seconds", 300),
                )
                self._rules[rule.rule_id] = rule
        except (json.JSONDecodeError, KeyError, OSError):
            logger.exception("Failed to load alert rules")
            self._add_defaults()

    def _save(self) -> None:
        if not self._config_path:
            return
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        data = {"rules": [r.to_dict() for r in self._rules.values()]}
        self._config_path.write_text(json.dumps(data, indent=2), "utf-8")

    def list_rules(self) -> list[AlertRule]:
        return list(self._rules.values())

    def add_rule(self, **kwargs: Any) -> AlertRule:
        rule = AlertRule(**kwargs)
        self._rules[rule.rule_id] = rule
        self._save()
        return rule

    def remove_rule(self, rule_id: str) -> bool:
        if rule_id in self._rules:
            del self._rules[rule_id]
            self._save()
            return True
        return False

    def active_alerts(self) -> list[ActiveAlert]:
        return list(self._active_alerts)

    def acknowledge(self, rule_id: str, tool_slug: str) -> bool:
        for alert in self._active_alerts:
            if alert.rule_id == rule_id and alert.tool_slug == tool_slug:
                alert.acknowledged = True
                return True
        return False

    def record_health_failure(self, slug: str) -> None:
        self._failure_counts[slug] = self._failure_counts.get(slug, 0) + 1

    def record_health_success(self, slug: str) -> None:
        self._failure_counts[slug] = 0

    _MAX_ALERTS = 200

    async def evaluate(
        self,
        metrics_collector: MetricsCollector,
        notification_service: NotificationService | None = None,
    ) -> list[ActiveAlert]:
        """Evaluate all rules against current metrics. Returns new alerts."""
        new_alerts: list[ActiveAlert] = []
        now = time.time()
        all_metrics = metrics_collector.get_all()

        for rule in self._rules.values():
            if not rule.enabled:
                continue
            slugs = [rule.tool_slug] if rule.tool_slug else list(all_metrics.keys())
            for slug in slugs:
                alert = await self._evaluate_rule_for_tool(
                    rule,
                    slug,
                    all_metrics,
                    now,
                    notification_service,
                )
                if alert:
                    new_alerts.append(alert)

        if len(self._active_alerts) > self._MAX_ALERTS:
            self._active_alerts = self._active_alerts[-self._MAX_ALERTS :]

        return new_alerts

    async def _evaluate_rule_for_tool(
        self,
        rule: AlertRule,
        slug: str,
        all_metrics: dict,
        now: float,
        notification_service: NotificationService | None,
    ) -> ActiveAlert | None:
        """Check one rule against one tool. Returns alert if triggered."""
        tm = all_metrics.get(slug)
        if not tm:
            return None

        value = self._get_metric_value(rule.metric, tm, slug)
        if value is None:
            return None

        op_fn = _OPERATORS.get(rule.operator)
        if not op_fn:
            return None

        breach_key = f"{rule.rule_id}:{slug}"

        if not op_fn(value, rule.threshold):
            self._breach_start.pop(breach_key, None)
            return None

        if breach_key not in self._breach_start:
            self._breach_start[breach_key] = now

        elapsed = now - self._breach_start[breach_key]
        if elapsed < rule.duration_seconds:
            return None

        last = self._last_alert_time.get(breach_key, 0)
        if now - last < rule.cooldown_seconds:
            return None

        alert = ActiveAlert(
            rule_id=rule.rule_id,
            tool_slug=slug,
            triggered_at=now,
            current_value=round(value, 2),
            message=(
                f"{rule.name}: {rule.metric} "
                f"{rule.operator} {rule.threshold} "
                f"(current: {round(value, 2)})"
            ),
            severity=rule.severity,
        )
        self._active_alerts.append(alert)
        self._last_alert_time[breach_key] = now

        if notification_service:
            await self._send_alert_notification(notification_service, rule, alert, slug)

        return alert

    async def _send_alert_notification(
        self,
        service: NotificationService,
        rule: AlertRule,
        alert: ActiveAlert,
        slug: str,
    ) -> None:
        from opsportal.services.notification_service import NotificationLevel

        level = (
            NotificationLevel.CRITICAL
            if rule.severity == AlertSeverity.CRITICAL
            else NotificationLevel.WARNING
        )
        await service.notify(
            level=level,
            title=rule.name,
            message=alert.message,
            tool_slug=slug,
            event_type="alert",
        )

    def _get_metric_value(self, metric: AlertMetric, tm: Any, slug: str) -> float | None:
        if metric == AlertMetric.CPU_PERCENT:
            return tm.cpu_percent
        if metric == AlertMetric.MEMORY_MB:
            return tm.memory_rss_bytes / (1024 * 1024)
        if metric == AlertMetric.LATENCY_MS:
            return tm.health_check_latency_ms
        if metric == AlertMetric.CONSECUTIVE_FAILURES:
            return float(self._failure_counts.get(slug, 0))
        return None
