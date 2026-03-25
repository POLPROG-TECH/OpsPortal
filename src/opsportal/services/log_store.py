"""In-memory log store for portal-level activity and tool run logs."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass


@dataclass(slots=True)
class LogEntry:
    timestamp: float
    level: str
    tool_slug: str
    action: str
    message: str

    @property
    def time_str(self) -> str:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.timestamp))


class LogStore:
    """Ring-buffer log store for portal activity (non-persistent)."""

    def __init__(self, max_entries: int = 5000) -> None:
        self._entries: deque[LogEntry] = deque(maxlen=max_entries)

    def add(
        self,
        tool_slug: str,
        action: str,
        message: str,
        level: str = "info",
    ) -> LogEntry:
        entry = LogEntry(
            timestamp=time.time(),
            level=level,
            tool_slug=tool_slug,
            action=action,
            message=message,
        )
        self._entries.append(entry)
        return entry

    def recent(self, limit: int = 100, tool_slug: str | None = None) -> list[LogEntry]:
        items = list(self._entries)
        if tool_slug:
            items = [e for e in items if e.tool_slug == tool_slug]
        return items[-limit:][::-1]  # newest first

    def count(self) -> int:
        return len(self._entries)
