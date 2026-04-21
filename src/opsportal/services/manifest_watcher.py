"""Manifest watcher - detects changes to opsportal.yaml and triggers reload.

Uses file stat polling (works on all OS) to detect modifications.
When a change is detected, it signals the portal to re-read the manifest
and update adapters accordingly.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Callable
from pathlib import Path
from typing import Any

from opsportal.core.errors import get_logger

logger = get_logger("services.manifest_watcher")


class ManifestWatcher:
    """Watches the manifest file for changes and calls a reload callback."""

    def __init__(
        self,
        manifest_path: Path,
        *,
        poll_interval: float = 5.0,
    ) -> None:
        self._path = manifest_path
        self._poll_interval = poll_interval
        self._last_mtime: float = 0.0
        self._last_size: int = 0
        self._task: asyncio.Task | None = None
        self._reload_callback: Callable[[], Any] | None = None

        # Initialize baseline
        self._update_stat()

    def set_reload_callback(self, callback: Callable[[], Any]) -> None:
        """Set the callback to invoke when manifest changes.

        The callback may be sync or async.
        """
        self._reload_callback = callback

    async def start(self) -> None:
        if self._task is not None:
            return
        self._update_stat()
        self._task = asyncio.create_task(self._watch_loop())
        logger.info("Manifest watcher started: %s (poll=%ss)", self._path, self._poll_interval)

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    def _update_stat(self) -> bool:
        """Read current file stats. Returns True if file changed."""
        try:
            stat = self._path.stat()
            mtime = stat.st_mtime
            size = stat.st_size
            changed = mtime != self._last_mtime or size != self._last_size
            self._last_mtime = mtime
            self._last_size = size
            return changed
        except OSError:
            return False

    async def _watch_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(self._poll_interval)
                if self._update_stat():
                    logger.info("Manifest change detected: %s", self._path)
                    await self._trigger_reload()
        except asyncio.CancelledError:
            pass

    async def _trigger_reload(self) -> None:
        if not self._reload_callback:
            return
        try:
            result = self._reload_callback()
            if asyncio.iscoroutine(result):
                await result
            logger.info("Manifest reload completed")
        except (OSError, ValueError):
            logger.exception("Error during manifest reload")
