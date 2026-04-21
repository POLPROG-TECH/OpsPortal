"""Managed tool installer - installs tools from remote sources via pip.

Handles:
  - pip install from git+https (GitHub/GitLab)
  - Version checking via importlib.metadata
  - Per-tool work directory management
  - Proxy / SSL-aware installation
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from opsportal.config.manifest import InstallStrategy, ToolSource
from opsportal.core.errors import get_logger

logger = get_logger("services.tool_installer")


class ToolInstallError(Exception):
    """Raised when tool installation fails."""


class ToolInstaller:
    """Install and manage remote-sourced tools."""

    def __init__(self, work_base: Path) -> None:
        self._work_base = work_base
        self._work_base.mkdir(parents=True, exist_ok=True)

    def work_dir_for(self, slug: str) -> Path:
        """Return (and create) the per-tool work directory."""
        d = self._work_base / slug
        d.mkdir(parents=True, exist_ok=True)
        return d

    def is_installed(self, package: str) -> bool:
        """Check if a package is installed."""
        try:
            from importlib.metadata import distribution

            distribution(package)
            return True
        except Exception:  # PackageNotFoundError, ImportError, or other metadata errors
            return False

    def installed_version(self, package: str) -> str | None:
        """Get the installed version of a package, or None."""
        try:
            from importlib.metadata import version

            return version(package)
        except Exception:  # PackageNotFoundError, ImportError, or other metadata errors
            return None

    def cli_available(self, cli_binary: str) -> bool:
        """Check if a CLI binary is available on PATH."""
        return shutil.which(cli_binary) is not None

    def install(self, source: ToolSource, *, upgrade: bool = False) -> dict[str, Any]:
        """Install a tool from its source definition.

        Returns a dict with install details for logging/diagnostics.
        """
        if source.install_strategy == InstallStrategy.PRE_INSTALLED:
            if not self.is_installed(source.package):
                raise ToolInstallError(
                    f"Package '{source.package}' is marked pre_installed but not found. "
                    f"Install it manually: pip install {source.package}"
                )
            return {
                "action": "verified",
                "package": source.package,
                "version": self.installed_version(source.package),
            }

        pip_spec = source.pip_spec
        cmd = [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--quiet",
            "--no-input",
        ]
        if upgrade:
            cmd.append("--upgrade")
        cmd.append(pip_spec)

        logger.info(
            "Installing %s (%s)%s",
            source.package,
            pip_spec,
            " [upgrade]" if upgrade else "",
        )

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ToolInstallError(
                f"Installation timed out after 300s: pip install {pip_spec}"
            ) from exc
        except FileNotFoundError as exc:
            raise ToolInstallError(f"Python executable not found: {sys.executable}") from exc

        if result.returncode != 0:
            stderr = result.stderr.strip()
            # Sanitize: remove any local paths from error messages
            raise ToolInstallError(
                f"pip install failed (exit {result.returncode}) for {source.package}.\n"
                f"Spec: {pip_spec}\n"
                f"Error: {stderr[-500:] if len(stderr) > 500 else stderr}"
            )

        version = self.installed_version(source.package)
        logger.info("Installed %s version %s", source.package, version)
        return {
            "action": "installed" if not upgrade else "upgraded",
            "package": source.package,
            "version": version,
            "spec": pip_spec,
        }

    def ensure_installed(self, source: ToolSource) -> dict[str, Any]:
        """Install if not already present. Returns install details."""
        if source.install_strategy == InstallStrategy.PRE_INSTALLED:
            return self.install(source)

        if self.is_installed(source.package):
            version = self.installed_version(source.package)
            logger.debug("%s already installed (version %s)", source.package, version)
            return {
                "action": "already_installed",
                "package": source.package,
                "version": version,
            }

        return self.install(source)
