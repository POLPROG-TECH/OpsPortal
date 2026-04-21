"""Configuration versioning - maintains a history of config changes with rollback support.

Each time a tool config is saved, a timestamped snapshot is stored.
Users can list versions and restore any previous version.
"""

from __future__ import annotations

import contextlib
import json
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from opsportal.core.errors import get_logger

logger = get_logger("services.config_versioning")


@dataclass(frozen=True, slots=True)
class ConfigVersion:
    """Metadata for a stored config snapshot."""

    version_id: str
    tool_slug: str
    timestamp: float
    path: Path
    size_bytes: int
    actor: str = "system"

    @property
    def time_str(self) -> str:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.timestamp))

    def to_dict(self) -> dict:
        return {
            "version_id": self.version_id,
            "tool_slug": self.tool_slug,
            "timestamp": self.timestamp,
            "time_str": self.time_str,
            "size_bytes": self.size_bytes,
            "actor": self.actor,
        }


class ConfigVersionManager:
    """Stores and retrieves config version history per tool."""

    MAX_VERSIONS_PER_TOOL = 50

    def __init__(self, root_dir: Path) -> None:
        self._root = root_dir
        self._root.mkdir(parents=True, exist_ok=True)

    def _tool_dir(self, tool_slug: str) -> Path:
        d = self._root / tool_slug
        d.mkdir(parents=True, exist_ok=True)
        return d

    def snapshot(
        self,
        tool_slug: str,
        config_path: Path,
        *,
        actor: str = "system",
    ) -> ConfigVersion:
        """Create a versioned snapshot of the current config file."""
        if not config_path.exists():
            msg = f"Config file does not exist: {config_path}"
            raise FileNotFoundError(msg)

        ts = time.time()
        version_id = f"{int(ts * 1000)}"
        dest_dir = self._tool_dir(tool_slug)
        dest = dest_dir / f"{version_id}.json"
        shutil.copy2(config_path, dest)

        stat = dest.stat()
        version = ConfigVersion(
            version_id=version_id,
            tool_slug=tool_slug,
            timestamp=ts,
            path=dest,
            size_bytes=stat.st_size,
            actor=actor,
        )
        logger.info("Snapshot %s/%s (%d bytes)", tool_slug, version_id, stat.st_size)
        self._prune(tool_slug)
        return version

    def snapshot_content(
        self,
        tool_slug: str,
        content: dict,
        *,
        actor: str = "system",
    ) -> ConfigVersion:
        """Create a version snapshot from dict content (before overwrite)."""
        ts = time.time()
        version_id = f"{int(ts * 1000)}"
        dest = self._tool_dir(tool_slug) / f"{version_id}.json"
        dest.write_text(json.dumps(content, indent=2, ensure_ascii=False), encoding="utf-8")

        stat = dest.stat()
        version = ConfigVersion(
            version_id=version_id,
            tool_slug=tool_slug,
            timestamp=ts,
            path=dest,
            size_bytes=stat.st_size,
            actor=actor,
        )
        logger.info("Snapshot content %s/%s", tool_slug, version_id)
        self._prune(tool_slug)
        return version

    def list_versions(self, tool_slug: str) -> list[ConfigVersion]:
        """Return all versions for a tool, newest first."""
        d = self._root / tool_slug
        if not d.exists():
            return []

        versions = []
        for f in d.iterdir():
            if f.is_file() and f.suffix == ".json":
                stat = f.stat()
                vid = f.stem
                try:
                    ts = int(vid) / 1000.0
                except ValueError:
                    ts = stat.st_mtime
                versions.append(
                    ConfigVersion(
                        version_id=vid,
                        tool_slug=tool_slug,
                        timestamp=ts,
                        path=f,
                        size_bytes=stat.st_size,
                    )
                )
        versions.sort(key=lambda v: v.timestamp, reverse=True)
        return versions

    def get_version(self, tool_slug: str, version_id: str) -> ConfigVersion | None:
        """Retrieve a specific version."""
        f = self._tool_dir(tool_slug) / f"{version_id}.json"
        if not f.exists():
            return None
        stat = f.stat()
        try:
            ts = int(version_id) / 1000.0
        except ValueError:
            ts = stat.st_mtime
        return ConfigVersion(
            version_id=version_id,
            tool_slug=tool_slug,
            timestamp=ts,
            path=f,
            size_bytes=stat.st_size,
        )

    def get_version_content(self, tool_slug: str, version_id: str) -> dict | None:
        """Read the JSON content of a stored version."""
        version = self.get_version(tool_slug, version_id)
        if not version:
            return None
        try:
            return json.loads(version.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def restore(self, tool_slug: str, version_id: str, target_path: Path) -> bool:
        """Restore a version by copying it to the target config path."""
        version = self.get_version(tool_slug, version_id)
        if not version:
            return False
        shutil.copy2(version.path, target_path)
        logger.info("Restored %s/%s → %s", tool_slug, version_id, target_path)
        return True

    def _prune(self, tool_slug: str) -> None:
        """Remove oldest versions if over the limit."""
        versions = self.list_versions(tool_slug)
        for old in versions[self.MAX_VERSIONS_PER_TOOL :]:
            with contextlib.suppress(OSError):
                old.path.unlink()
