"""Backup service - snapshot and restore portal state.

Creates zip archives of the portal work directory (configs, scheduler,
audit logs, uptime data) and can restore from a previously created archive.
"""

from __future__ import annotations

import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from opsportal.core.errors import get_logger

logger = get_logger("services.backup_service")


@dataclass(frozen=True, slots=True)
class BackupInfo:
    filename: str
    path: Path
    created_at: float
    size_bytes: int

    @property
    def created_at_str(self) -> str:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.created_at))

    @property
    def size_mb(self) -> float:
        return round(self.size_bytes / (1024 * 1024), 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "filename": self.filename,
            "created_at": self.created_at,
            "created_at_str": self.created_at_str,
            "size_bytes": self.size_bytes,
            "size_mb": self.size_mb,
        }


class BackupService:
    """Creates and restores zip backups of portal state."""

    BACKUP_PREFIX = "opsportal-backup-"
    MAX_BACKUPS = 10

    def __init__(
        self,
        work_dir: Path,
        backup_dir: Path | None = None,
        manifest_path: Path | None = None,
    ) -> None:
        self._work_dir = work_dir
        self._backup_dir = backup_dir or work_dir / "backups"
        self._manifest_path = manifest_path
        self._backup_dir.mkdir(parents=True, exist_ok=True)

    def create_backup(self, label: str = "") -> BackupInfo:
        """Create a zip backup of the portal state."""
        ts = time.strftime("%Y%m%d-%H%M%S")
        suffix = f"-{label}" if label else ""
        filename = f"{self.BACKUP_PREFIX}{ts}{suffix}.zip"
        zip_path = self._backup_dir / filename

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # Include manifest
            if self._manifest_path and self._manifest_path.exists():
                zf.write(self._manifest_path, "opsportal.yaml")

            # Include work dir contents (configs, scheduler, audit, uptime)
            for item in self._work_dir.rglob("*"):
                if item.is_file() and "backups" not in item.parts:
                    rel = item.relative_to(self._work_dir)
                    zf.write(item, f"work/{rel}")

        stat = zip_path.stat()
        logger.info("Backup created: %s (%.2f MB)", filename, stat.st_size / (1024 * 1024))

        self._prune_old()

        return BackupInfo(
            filename=filename,
            path=zip_path,
            created_at=stat.st_mtime,
            size_bytes=stat.st_size,
        )

    def list_backups(self) -> list[BackupInfo]:
        """List available backups, newest first."""
        backups = []
        for p in sorted(self._backup_dir.glob(f"{self.BACKUP_PREFIX}*.zip"), reverse=True):
            stat = p.stat()
            backups.append(
                BackupInfo(
                    filename=p.name,
                    path=p,
                    created_at=stat.st_mtime,
                    size_bytes=stat.st_size,
                )
            )
        return backups

    def restore_backup(self, filename: str) -> bool:
        """Restore portal state from a backup zip."""
        zip_path = self._backup_dir / filename
        if not zip_path.exists():
            logger.error("Backup not found: %s", filename)
            return False

        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                for member in zf.namelist():
                    self._restore_member(zf, member)
            logger.info("Backup restored: %s", filename)
            return True
        except (OSError, zipfile.BadZipFile):
            logger.exception("Failed to restore backup: %s", filename)
            return False

    def _restore_member(self, zf: zipfile.ZipFile, member: str) -> None:
        """Restore a single member from a backup archive."""
        if member == "opsportal.yaml" and self._manifest_path:
            self._manifest_path.write_bytes(zf.read(member))
            return

        if not member.startswith("work/"):
            return

        rel = member[5:]  # strip "work/"
        if not rel:
            return

        target = self._work_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(zf.read(member))

    def delete_backup(self, filename: str) -> bool:
        """Delete a backup file."""
        zip_path = self._backup_dir / filename
        if zip_path.exists():
            zip_path.unlink()
            return True
        return False

    def _prune_old(self) -> None:
        backups = self.list_backups()
        for old in backups[self.MAX_BACKUPS :]:
            old.path.unlink(missing_ok=True)
