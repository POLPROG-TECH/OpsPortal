"""Portal state store — durable persistence for runtime-mutable settings.

Unlike ``PortalSettings`` (which reads env vars once at startup and is
effectively immutable), ``PortalStateStore`` manages settings that users
change at runtime through the Admin UI and that **must survive restarts**.

Storage: ``work/portal_state.json`` — atomic writes, schema-versioned.
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from opsportal.core.errors import get_logger

logger = get_logger("services.portal_state")

# Bump when the on-disk schema changes in an incompatible way.
_SCHEMA_VERSION = 1

# Keys that the portal state store manages, with their default values.
# These defaults apply when no persisted state exists yet (first run).
_DEFAULTS: dict[str, Any] = {
    "ops_overview_enabled": False,
}


class PortalStateStore:
    """Manages portal runtime state that must survive application restarts.

    All values are stored in a single JSON file (``portal_state.json``)
    inside the ``work/`` directory.  Writes are atomic (write-to-tempfile
    then ``os.replace``) so a crash mid-write cannot corrupt the file.

    Parameters
    ----------
    path:
        Full path to the ``portal_state.json`` file.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._data: dict[str, Any] = dict(_DEFAULTS)
        self._loaded = False
        self.load()

    # -- Public API ---------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        """Return a persisted value (or *default* if not set)."""
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a value and persist immediately."""
        self._data[key] = value
        self._save()

    def set_many(self, updates: dict[str, Any]) -> None:
        """Set multiple values and persist in one write."""
        self._data.update(updates)
        self._save()

    def all(self) -> dict[str, Any]:
        """Return a copy of all persisted state."""
        return dict(self._data)

    @property
    def loaded_from_disk(self) -> bool:
        """Whether state was loaded from an existing file (vs fresh defaults)."""
        return self._loaded

    # -- Load / save --------------------------------------------------------

    def load(self) -> None:
        """Load persisted state from disk, falling back to defaults."""
        if not self._path.exists():
            logger.info("No portal state file at %s — using defaults", self._path)
            self._loaded = False
            return

        try:
            raw = self._path.read_text("utf-8")
            data = json.loads(raw)
        except (json.JSONDecodeError, OSError):
            logger.exception("Failed to read portal state from %s", self._path)
            self._loaded = False
            return

        version = data.get("_schema_version", 0)
        if version > _SCHEMA_VERSION:
            logger.warning(
                "Portal state schema v%d > supported v%d — using defaults",
                version,
                _SCHEMA_VERSION,
            )
            self._loaded = False
            return

        state = data.get("state", {})
        # Merge: persisted values override defaults, but missing keys get defaults
        merged = dict(_DEFAULTS)
        merged.update(state)
        self._data = merged
        self._loaded = True
        logger.info("Portal state loaded from %s (%d keys)", self._path, len(state))

    def _save(self) -> None:
        """Atomically persist current state to disk."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "_schema_version": _SCHEMA_VERSION,
            "state": self._data,
        }
        blob = json.dumps(payload, indent=2, sort_keys=True)

        # Atomic write: temp file in same directory → os.replace
        fd, tmp = tempfile.mkstemp(
            dir=str(self._path.parent), suffix=".tmp", prefix=".portal_state_"
        )
        try:
            os.write(fd, blob.encode("utf-8"))
            os.fsync(fd)
            os.close(fd)
            os.replace(tmp, str(self._path))
        except OSError:
            logger.exception("Failed to persist portal state to %s", self._path)
            with contextlib.suppress(OSError):
                os.unlink(tmp)

    def reset(self) -> None:
        """Reset all state to defaults and persist."""
        self._data = dict(_DEFAULTS)
        self._save()
        self._loaded = True
