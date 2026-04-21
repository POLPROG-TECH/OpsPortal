"""Artifact manager - storage and retrieval for generated HTML/report outputs."""

from __future__ import annotations

import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from opsportal.core.errors import get_logger

logger = get_logger("services.artifact_manager")


@dataclass(frozen=True, slots=True)
class ArtifactEntry:
    name: str
    tool_slug: str
    path: Path
    content_type: str
    created_at: float
    size_bytes: int


class ArtifactManager:
    """Manages storage and retrieval of tool-generated artifacts (HTML dashboards, reports)."""

    def __init__(self, root_dir: Path) -> None:
        self._root = root_dir
        self._root.mkdir(parents=True, exist_ok=True)
        logger.info("Artifact storage: %s", self._root)

    def tool_dir(self, tool_slug: str) -> Path:
        d = self._root / tool_slug
        d.mkdir(parents=True, exist_ok=True)
        return d

    def store(self, tool_slug: str, source_path: Path, name: str | None = None) -> ArtifactEntry:
        """Copy a generated file into the artifact store and return its entry."""
        if not source_path.exists():
            msg = f"Source artifact not found: {source_path}"
            raise FileNotFoundError(msg)

        dest_dir = self.tool_dir(tool_slug)
        artifact_name = name or source_path.name
        dest = dest_dir / artifact_name

        shutil.copy2(source_path, dest)
        stat = dest.stat()

        entry = ArtifactEntry(
            name=artifact_name,
            tool_slug=tool_slug,
            path=dest,
            content_type=_guess_content_type(artifact_name),
            created_at=stat.st_mtime,
            size_bytes=stat.st_size,
        )
        logger.info("Stored artifact: %s/%s (%d bytes)", tool_slug, artifact_name, stat.st_size)
        return entry

    def store_content(
        self, tool_slug: str, content: str, name: str, content_type: str = "text/html"
    ) -> ArtifactEntry:
        """Write string content directly as an artifact."""
        dest_dir = self.tool_dir(tool_slug)
        dest = dest_dir / name
        dest.write_text(content, encoding="utf-8")
        stat = dest.stat()

        entry = ArtifactEntry(
            name=name,
            tool_slug=tool_slug,
            path=dest,
            content_type=content_type,
            created_at=stat.st_mtime,
            size_bytes=stat.st_size,
        )
        logger.info("Stored artifact content: %s/%s (%d bytes)", tool_slug, name, stat.st_size)
        return entry

    def list_artifacts(self, tool_slug: str) -> list[ArtifactEntry]:
        """Return all artifacts for a given tool, newest first."""
        d = self._root / tool_slug
        if not d.exists():
            return []

        entries = []
        for f in d.iterdir():
            if f.is_file() and not f.name.startswith("."):
                stat = f.stat()
                entries.append(
                    ArtifactEntry(
                        name=f.name,
                        tool_slug=tool_slug,
                        path=f,
                        content_type=_guess_content_type(f.name),
                        created_at=stat.st_mtime,
                        size_bytes=stat.st_size,
                    )
                )
        entries.sort(key=lambda e: e.created_at, reverse=True)
        return entries

    def get_artifact(self, tool_slug: str, name: str) -> ArtifactEntry | None:
        resolved = (self._root / tool_slug / name).resolve()
        allowed_root = (self._root / tool_slug).resolve()
        if not resolved.is_relative_to(allowed_root):
            return None  # Path traversal attempt
        f = self._root / tool_slug / name
        if not f.exists() or not f.is_file():
            return None
        stat = f.stat()
        return ArtifactEntry(
            name=name,
            tool_slug=tool_slug,
            path=f,
            content_type=_guess_content_type(name),
            created_at=stat.st_mtime,
            size_bytes=stat.st_size,
        )

    def cleanup(self, tool_slug: str, max_age_seconds: float = 7 * 86400) -> int:
        """Remove artifacts older than max_age_seconds. Returns count removed."""
        d = self._root / tool_slug
        if not d.exists():
            return 0
        cutoff = time.time() - max_age_seconds
        removed = 0
        for f in d.iterdir():
            if f.is_file() and f.stat().st_mtime < cutoff:
                f.unlink()
                removed += 1
        if removed:
            logger.info("Cleaned up %d old artifacts for %s", removed, tool_slug)
        return removed


def _guess_content_type(name: str) -> str:
    suffixes = {
        ".html": "text/html",
        ".json": "application/json",
        ".pdf": "application/pdf",
        ".csv": "text/csv",
        ".md": "text/markdown",
        ".txt": "text/plain",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    for ext, ct in suffixes.items():
        if name.lower().endswith(ext):
            return ct
    return "application/octet-stream"
