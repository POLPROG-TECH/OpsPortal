"""Notification service — sends alerts via webhooks when tool status changes.

Supports generic webhook (Slack-compatible JSON), with a simple configuration
model.  Notifications are triggered on: tool crash, health check failure,
tool restart, and config changes.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from opsportal.core.errors import get_logger

logger = get_logger("services.notification_service")


class NotificationLevel(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class Notification:
    timestamp: float
    level: NotificationLevel
    title: str
    message: str
    tool_slug: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def time_str(self) -> str:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.timestamp))


@dataclass
class WebhookConfig:
    url: str
    enabled: bool = True
    min_level: NotificationLevel = NotificationLevel.WARNING
    events: list[str] = field(default_factory=lambda: ["tool_down", "health_fail", "restart"])


class NotificationService:
    """Sends notifications via configured webhooks."""

    def __init__(self, webhooks: list[WebhookConfig] | None = None) -> None:
        self._webhooks = webhooks or []
        self._history: list[Notification] = []
        self._max_history = 200
        self._pending_tasks: set[asyncio.Task[None]] = set()

    @property
    def webhooks(self) -> list[WebhookConfig]:
        return self._webhooks

    def configure(self, webhooks: list[dict]) -> None:
        """Update webhook configuration."""
        self._webhooks = [
            WebhookConfig(
                url=w["url"],
                enabled=w.get("enabled", True),
                min_level=NotificationLevel(w.get("min_level", "warning")),
                events=w.get("events", ["tool_down", "health_fail", "restart"]),
            )
            for w in webhooks
            if w.get("url")
        ]

    async def notify(
        self,
        *,
        level: NotificationLevel,
        title: str,
        message: str,
        tool_slug: str | None = None,
        event_type: str = "general",
        details: dict[str, Any] | None = None,
    ) -> None:
        """Send a notification to all matching webhooks."""
        notification = Notification(
            timestamp=time.time(),
            level=level,
            title=title,
            message=message,
            tool_slug=tool_slug,
            details=details or {},
        )

        self._history.append(notification)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history :]

        for webhook in self._webhooks:
            if not webhook.enabled:
                continue
            if event_type not in webhook.events and "all" not in webhook.events:
                continue
            level_order = list(NotificationLevel)
            if level_order.index(level) < level_order.index(webhook.min_level):
                continue

            task = asyncio.create_task(self._send_webhook(webhook, notification))
            self._pending_tasks.add(task)
            task.add_done_callback(self._pending_tasks.discard)

    async def _send_webhook(self, webhook: WebhookConfig, notification: Notification) -> None:
        """Send a single webhook request (Slack-compatible JSON)."""
        import httpx

        payload = {
            "text": f"[{notification.level.upper()}] {notification.title}",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*{notification.title}*\n{notification.message}",
                    },
                },
            ],
            "level": notification.level.value,
            "title": notification.title,
            "message": notification.message,
            "tool_slug": notification.tool_slug,
            "timestamp": notification.time_str,
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    webhook.url,
                    content=json.dumps(payload),
                    headers={"Content-Type": "application/json"},
                )
                if resp.status_code >= 400:
                    logger.warning("Webhook %s returned %d", webhook.url[:50], resp.status_code)
        except (httpx.HTTPError, OSError):
            logger.exception("Failed to send webhook to %s", webhook.url[:50])

    def recent(self, limit: int = 50) -> list[dict]:
        """Return recent notification history."""
        return [
            {
                "timestamp": n.timestamp,
                "time_str": n.time_str,
                "level": n.level.value,
                "title": n.title,
                "message": n.message,
                "tool_slug": n.tool_slug,
            }
            for n in reversed(self._history[-limit:])
        ]
