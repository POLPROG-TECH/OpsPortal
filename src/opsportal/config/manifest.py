"""YAML manifest parser for tool registration."""

from __future__ import annotations

import enum
import textwrap
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

from opsportal.adapters.base import IntegrationMode
from opsportal.core.errors import get_logger

logger = get_logger("config.manifest")

# ---------------------------------------------------------------------------
# Default manifest template — used by `opsportal init` and auto-bootstrap
# ---------------------------------------------------------------------------

DEFAULT_MANIFEST_YAML = textwrap.dedent("""\
    # OpsPortal Manifest — Tool Registration
    # Generated automatically. Customize as needed.
    # Docs: https://github.com/POLPROG-TECH/OpsPortal#configuration

    tools:
      releasepilot:
        display_name: ReleasePilot
        description: "Release notes generator — from git history to polished documents"
        integration_mode: subprocess_web
        icon: rocket
        color: "#4F46E5"
        enabled: true
        port: 8082
        startup_timeout: 30
        env: {}
        source:
          provider: github
          repository: POLPROG-TECH/ReleasePilot
          ref: v1.1.0
          package: releasepilot
          extras: [all]
          install_strategy: pip_git

      releaseboard:
        display_name: ReleaseBoard
        description: "Release readiness dashboard — track branch status across repos"
        integration_mode: subprocess_web
        icon: clipboard-check
        color: "#059669"
        enabled: true
        port: 8081
        config_file: releaseboard.json
        startup_timeout: 30
        env: {}
        source:
          provider: github
          repository: POLPROG-TECH/ReleaseBoard
          ref: v1.1.0
          package: releaseboard
          install_strategy: pip_git
""")


# ---------------------------------------------------------------------------
# Tool source definition (remote-managed tool installation)
# ---------------------------------------------------------------------------


class InstallStrategy(enum.StrEnum):
    """How to install a managed tool."""

    PIP_GIT = "pip_git"  # pip install git+https://...@ref
    PIP_REGISTRY = "pip_registry"  # pip install package==version
    PRE_INSTALLED = "pre_installed"  # CLI already on PATH, no install


class SourceProvider(enum.StrEnum):
    GITHUB = "github"
    GITLAB = "gitlab"


class ToolSource(BaseModel):
    """Declarative source definition for a managed tool.

    Defines where to install the tool from and how to verify installation.
    """

    provider: SourceProvider = SourceProvider.GITHUB
    repository: str  # e.g. "POLPROG-TECH/ReleasePilot"
    ref: str = "main"  # tag, branch, or commit hash
    package: str  # pip package name, e.g. "releasepilot"
    extras: list[str] = Field(default_factory=list)  # pip extras, e.g. ["all"]
    install_strategy: InstallStrategy = InstallStrategy.PIP_GIT

    @field_validator("repository")
    @classmethod
    def _validate_repository(cls, v: str) -> str:
        parts = v.strip("/").split("/")
        if len(parts) != 2 or not all(parts):
            msg = f"Repository must be 'owner/name', got: {v!r}"
            raise ValueError(msg)
        return v

    @property
    def git_url(self) -> str:
        """Full git+https URL for pip install."""
        base = f"https://github.com/{self.repository}.git"
        if self.provider == SourceProvider.GITLAB:
            base = f"https://gitlab.com/{self.repository}.git"
        return f"git+{base}@{self.ref}"

    @property
    def pip_spec(self) -> str:
        """Full pip install specifier including extras."""
        if self.install_strategy == InstallStrategy.PIP_REGISTRY:
            spec = f"{self.package}=={self.ref}"
        else:
            spec = self.git_url
        if self.extras:
            spec += "[" + ",".join(self.extras) + "]"
        return spec


# ---------------------------------------------------------------------------
# Tool configuration
# ---------------------------------------------------------------------------


class ToolConfig(BaseModel):
    """Typed configuration for a single integrated tool."""

    slug: str
    display_name: str
    description: str = ""
    repo_path: Path | None = None  # Optional: local checkout (for dev or legacy)
    source: ToolSource | None = None  # Optional: remote-managed install definition
    integration_mode: IntegrationMode
    icon: str = "box"
    color: str = "#6B7280"
    enabled: bool = True

    # For SUBPROCESS_WEB
    port: int | None = None
    serve_command: list[str] | None = None
    health_endpoint: str | None = None

    # For CLI tools
    cli_binary: str | None = None

    # For artifacts
    artifact_subdir: str | None = None

    # Config file inside the tool repo / work dir
    config_file: str | None = None

    # Extra env vars to pass to the tool
    env: dict[str, str] = Field(default_factory=dict)

    # Route prefix override (defaults to /tools/{slug})
    route_prefix: str | None = None

    # Timeouts
    startup_timeout: int = 30
    task_timeout: int = 300

    _warnings: list[str] = []

    @field_validator("repo_path", mode="before")
    @classmethod
    def _ensure_resolved(cls, v: Path | str | None) -> Path | None:
        if v is None:
            return None
        return Path(v).resolve()

    @model_validator(mode="after")
    def _check_recommended_fields(self) -> ToolConfig:
        warnings: list[str] = []
        if not self.description:
            warnings.append(f"[{self.slug}] 'description' is empty")
        if self.integration_mode == IntegrationMode.SUBPROCESS_WEB and self.port is None:
            warnings.append(f"[{self.slug}] subprocess_web tool has no 'port' configured")
        if self.repo_path is None and self.source is None:
            warnings.append(
                f"[{self.slug}] neither 'repo_path' nor 'source' defined — "
                "tool must be pre-installed and CLI must be on PATH"
            )
        self._warnings = warnings
        return self

    @property
    def is_remote_managed(self) -> bool:
        """True if tool uses remote source installation (no local repo_path)."""
        return self.source is not None and self.repo_path is None


class PortalManifest(BaseModel):
    """Top-level manifest representing all registered tools."""

    tools: list[ToolConfig] = Field(default_factory=list)

    def get_tool(self, slug: str) -> ToolConfig | None:
        return next((t for t in self.tools if t.slug == slug), None)

    @property
    def enabled_tools(self) -> list[ToolConfig]:
        return [t for t in self.tools if t.enabled]

    def validate(self) -> list[str]:
        """Aggregate tool warnings and cross-tool diagnostics."""
        diagnostics: list[str] = []
        for tool in self.tools:
            diagnostics.extend(tool._warnings)

        # Cross-tool: duplicate slugs
        slugs = [t.slug for t in self.tools]
        seen_slugs: set[str] = set()
        for s in slugs:
            if s in seen_slugs:
                diagnostics.append(f"Duplicate slug: {s!r}")
            seen_slugs.add(s)

        # Cross-tool: duplicate ports (only for tools that define one)
        ports: list[tuple[str, int]] = [(t.slug, t.port) for t in self.tools if t.port is not None]
        seen_ports: dict[int, str] = {}
        for slug, port in ports:
            if port in seen_ports:
                diagnostics.append(
                    f"Duplicate port {port}: used by {seen_ports[port]!r} and {slug!r}"
                )
            seen_ports[port] = slug

        return diagnostics


def load_manifest(
    manifest_path: Path,
    tools_base_dir: Path,
    tools_work_dir: Path | None = None,
) -> PortalManifest:
    """Load and validate the YAML manifest file.

    Relative ``repo_path`` values are resolved against *tools_base_dir*.
    Tools with a ``source`` block but no ``repo_path`` are remote-managed.
    """
    if not manifest_path.exists():
        return PortalManifest()

    raw: dict[str, Any] = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}

    tool_defs: dict[str, Any] = raw.get("tools", {})
    tools: list[ToolConfig] = []

    for slug, cfg in tool_defs.items():
        if not isinstance(cfg, dict):
            continue
        cfg["slug"] = slug

        # Parse source block if present
        source_raw = cfg.pop("source", None)
        if source_raw and isinstance(source_raw, dict):
            cfg["source"] = ToolSource(**source_raw)

        # Resolve repo_path only if explicitly set
        raw_repo = cfg.get("repo_path")
        if raw_repo is not None:
            repo_path = Path(raw_repo)
            if not repo_path.is_absolute():
                repo_path = (tools_base_dir / repo_path).resolve()
            cfg["repo_path"] = repo_path
        # else: repo_path stays None (remote-managed or pre-installed)

        tools.append(ToolConfig(**cfg))

    manifest = PortalManifest(tools=tools)
    for warning in manifest.validate():
        logger.warning(warning)
    return manifest
