"""Persistent audit log - records configuration changes, lifecycle actions, and user activity.

Unlike the in-memory LogStore (activity ring buffer), AuditLog writes entries
to a JSON-Lines file on disk so they survive portal restarts.  Each entry
includes a timestamp, actor, action category, and structured details.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from opsportal.core.errors import get_logger

logger = get_logger("services.audit_log")


@dataclass(frozen=True, slots=True)
class AuditEntry:
    """Single audit record."""

    timestamp: float
    actor: str  # username or "system"
    category: str  # "config", "lifecycle", "auth", "tool_register"
    action: str  # "save_config", "start_tool", "login", etc.
    tool_slug: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def time_str(self) -> str:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.timestamp))

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["time_str"] = self.time_str
        return d


class AuditLog:
    """Append-only persistent audit log backed by a JSONL file."""

    def __init__(self, log_path: Path) -> None:
        self._path = log_path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        logger.info("Audit log: %s", self._path)

    def record(
        self,
        *,
        actor: str = "system",
        category: str,
        action: str,
        tool_slug: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditEntry:
        """Append an audit entry to the log file."""
        entry = AuditEntry(
            timestamp=time.time(),
            actor=actor,
            category=category,
            action=action,
            tool_slug=tool_slug,
            details=details or {},
        )
        line = json.dumps(entry.to_dict(), ensure_ascii=False)
        with self._lock, self._path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
        return entry

    def recent(self, limit: int = 100, category: str | None = None) -> list[AuditEntry]:
        """Read the most recent entries (newest first)."""
        if not self._path.exists():
            return []

        entries: list[AuditEntry] = []
        with self._lock:
            lines = self._path.read_text(encoding="utf-8").strip().splitlines()

        for line in reversed(lines):
            if not line.strip():
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if category and d.get("category") != category:
                continue
            # Remove computed field before constructing dataclass
            d.pop("time_str", None)
            entries.append(AuditEntry(**d))
            if len(entries) >= limit:
                break
        return entries

    def count(self) -> int:
        if not self._path.exists():
            return 0
        with self._lock:
            return sum(1 for line in self._path.open(encoding="utf-8") if line.strip())
