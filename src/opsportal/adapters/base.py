"""Base adapter abstraction and shared types for tool integration."""

from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class IntegrationMode(enum.StrEnum):
    NATIVE_APP = "native_app"
    SUBPROCESS_WEB = "subprocess_web"
    CLI_TASK = "cli_task"
    STATIC_ARTIFACT = "static_artifact"
    HYBRID = "hybrid"


class ToolCapability(enum.StrEnum):
    WEB_UI = "web_ui"
    CLI_COMMANDS = "cli_commands"
    ARTIFACTS = "artifacts"
    HEALTH_CHECK = "health_check"
    CONFIGURABLE = "configurable"
    PROCESS = "process"


class IntegrationCapability(enum.StrEnum):
    """Capabilities that tools can expose for portal-level data integration."""

    RELEASE_CALENDAR = "release_calendar"
    RELEASE_NOTES = "release_notes"
    TRANSLATION = "translation"
    TAGS = "tags"
    ANALYSIS = "analysis"


class ToolStatus(enum.StrEnum):
    AVAILABLE = "available"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Data classes for actions and results
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ActionField:
    name: str
    label: str
    field_type: str = "text"  # text, select, path, number, boolean, textarea
    required: bool = False
    default: str = ""
    choices: list[str] = field(default_factory=list)
    help_text: str = ""
    placeholder: str = ""


@dataclass(frozen=True, slots=True)
class ToolAction:
    name: str
    label: str
    description: str
    fields: list[ActionField] = field(default_factory=list)
    dangerous: bool = False
    icon: str = "play"


@dataclass(slots=True)
class ActionResult:
    success: bool
    output: str = ""
    error: str | None = None
    artifact_path: Path | None = None
    duration_ms: int = 0


@dataclass(frozen=True, slots=True)
class Artifact:
    name: str
    path: Path
    tool_slug: str
    content_type: str = "text/html"
    created_at: str = ""
    size_bytes: int = 0


@dataclass(frozen=True, slots=True)
class IntegrationEndpoint:
    """Describes an API endpoint a child tool exposes for portal integration."""

    capability: IntegrationCapability
    method: str  # GET, POST
    path: str  # e.g., "/api/release-calendar/milestones"
    description: str = ""


@dataclass(frozen=True, slots=True)
class HealthResult:
    healthy: bool
    message: str = "OK"
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EnsureReadyResult:
    """Returned by ensure_ready() — tells the portal whether the tool is usable."""

    ready: bool
    message: str = ""
    web_url: str | None = None
    artifact_path: Path | None = None
    logs: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass(slots=True)
class ConfigValidationResult:
    """Returned by validate_config() — field-level validation feedback."""

    valid: bool
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Abstract adapter
# ---------------------------------------------------------------------------


class ToolAdapter(ABC):
    """Base class for all tool integration adapters.

    Each concrete adapter wraps one child tool and exposes a uniform interface
    for the portal shell to query status, run actions, and present UI.
    """

    # -- Identity (must be implemented) -------------------------------------

    @property
    @abstractmethod
    def slug(self) -> str: ...

    @property
    @abstractmethod
    def display_name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @property
    @abstractmethod
    def integration_mode(self) -> IntegrationMode: ...

    @property
    @abstractmethod
    def capabilities(self) -> set[ToolCapability]: ...

    @property
    @abstractmethod
    def icon(self) -> str: ...

    @property
    @abstractmethod
    def color(self) -> str: ...

    @property
    def repo_path(self) -> Path | None:
        """Local repository path, or None for remote-managed tools."""
        return None

    @property
    def work_dir(self) -> Path | None:
        """Managed work directory for configs/data. Used as CWD when no repo_path."""
        return None

    @property
    def effective_cwd(self) -> Path | None:
        """CWD for launching the tool: repo_path if available, else work_dir."""
        return self.repo_path or self.work_dir

    # -- Status & health ----------------------------------------------------

    @abstractmethod
    async def get_status(self) -> ToolStatus: ...

    @abstractmethod
    async def health_check(self) -> HealthResult: ...

    # -- Actions (for CLI_TASK / HYBRID) ------------------------------------

    def get_actions(self) -> list[ToolAction]:
        """Return available user-triggerable actions."""
        return []

    async def run_action(self, action_name: str, params: dict[str, Any]) -> ActionResult:
        """Execute a named action with the given parameters."""
        return ActionResult(success=False, error=f"Action {action_name!r} not supported")

    # -- Auto-start / on-demand lifecycle ------------------------------------

    async def ensure_ready(self) -> EnsureReadyResult:
        """Ensure this tool is running and ready for use.

        Called when the user navigates to the tool page.  Subclasses override
        to auto-start servers, generate artifacts, poll health endpoints, etc.
        The default implementation simply reports the tool as ready.
        """
        return EnsureReadyResult(ready=True, message="Tool available")

    # -- Web UI (for SUBPROCESS_WEB / NATIVE_APP) ---------------------------

    def get_web_url(self) -> str | None:
        """Return the URL where the tool's web UI is accessible."""
        return None

    def get_version(self) -> str | None:
        """Return the tool's version string, or None if unavailable.

        Adapters should override this to read from pyproject.toml, __init__.py,
        a health endpoint, or a manifest.  The portal displays this on
        dashboard cards and tool headers.
        """
        return None

    # -- Artifacts ----------------------------------------------------------

    def get_artifact_dir(self) -> Path | None:
        """Return the directory where this tool stores generated artifacts."""
        return None

    # -- Integration capabilities -------------------------------------------

    def get_integration_endpoints(self) -> list[IntegrationEndpoint]:
        """Return API endpoints this tool exposes for portal-level integration.

        Override in subclasses to declare data-level capabilities such as
        calendar, tags, release notes, or translation endpoints.
        """
        return []

    @property
    def integration_capabilities(self) -> set[IntegrationCapability]:
        """Derived set of integration capabilities from declared endpoints."""
        return {ep.capability for ep in self.get_integration_endpoints()}

    # -- Configuration (schema-driven editing) ------------------------------

    def config_schema(self) -> dict[str, Any] | None:
        """Return JSON Schema for this tool's config, or None if not configurable."""
        return None

    def get_config(self) -> dict[str, Any]:
        """Read current effective config from disk."""
        return {}

    def validate_config(self, data: dict[str, Any]) -> ConfigValidationResult:
        """Validate config data against the tool's schema. Does not save."""
        return ConfigValidationResult(valid=True)

    def save_config(self, data: dict[str, Any]) -> ActionResult:
        """Validate and write config to disk. Returns success/failure."""
        return ActionResult(success=False, error="Not configurable")

    def config_file_path(self) -> Path | None:
        """Return the path to the tool's config file, or None."""
        return None

    @property
    def has_first_run_wizard(self) -> bool:
        """True if the tool handles missing config with its own setup UI.

        When True, the portal skips scaffolding and config-missing warnings,
        and starts the tool even without a config file present.
        """
        return False

    # -- Lifecycle ----------------------------------------------------------

    async def startup(self) -> None:  # noqa: B027
        """Called when the portal starts up."""

    async def shutdown(self) -> None:  # noqa: B027
        """Called when the portal shuts down.

        Subclasses that create resources (e.g. HTTP clients) should override
        this to release them.
        """
