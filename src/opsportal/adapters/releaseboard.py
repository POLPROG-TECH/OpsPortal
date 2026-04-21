"""ReleaseBoard adapter - SUBPROCESS_WEB integration with auto-start.

ReleaseBoard exposes a full FastAPI web application with its own UI.
The portal runs it as a managed subprocess and embeds it via iframe.
The server is started automatically when the user enters the tool.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

import httpx

from opsportal.adapters._config_mixin import JsonSchemaConfigMixin
from opsportal.adapters.base import (
    ActionResult,
    EnsureReadyResult,
    HealthResult,
    IntegrationEndpoint,
    IntegrationMode,
    ToolAction,
    ToolAdapter,
    ToolCapability,
    ToolStatus,
)
from opsportal.core.errors import get_logger
from opsportal.services.process_manager import ProcessManager, ProcessStatus

logger = get_logger("adapters.releaseboard")


def _rb_validate(data: dict[str, Any]) -> list[str]:
    """Validate using ReleaseBoard's own schema validator."""
    from releaseboard.config.schema import validate_config, validate_layer_references

    errors = validate_config(data)
    errors.extend(validate_layer_references(data))
    return errors


def _sanitize_path_for_display(path: Path) -> str:
    """Return a display-safe representation of a path without exposing home dirs."""
    s = str(path)
    home = str(Path.home())
    if s.startswith(home):
        s = "~" + s[len(home) :]
    return s


class ReleaseBoardAdapter(JsonSchemaConfigMixin, ToolAdapter):
    def __init__(
        self,
        process_manager: ProcessManager,
        *,
        repo_path: Path | None = None,
        work_dir: Path | None = None,
        port: int = 8081,
        config_file: str = "releaseboard.json",
        cli_binary: str = "releaseboard",
        env: dict[str, str] | None = None,
        startup_timeout: int = 30,
        tools_base_dir: Path | None = None,
        portal_origins: str = "http://127.0.0.1:8000,http://localhost:8000",
    ) -> None:
        self._repo_path = repo_path
        self._work_dir = work_dir
        self._pm = process_manager
        self._port = port
        self._config_file = config_file
        self._cli = cli_binary
        self._env = {
            **(env or {}),
            "RELEASEBOARD_ALLOW_FRAMING": "true",
            "RELEASEBOARD_CORS_ORIGINS": portal_origins,
        }
        self._startup_timeout = startup_timeout
        self._tools_base_dir = tools_base_dir
        self._process_name = "releaseboard"
        self._http_client: httpx.AsyncClient | None = None
        # Config mixin setup
        self._schema_paths = self._build_schema_paths()
        self._validate_fn = _rb_validate

    def _build_schema_paths(self) -> list[Path]:
        """Build schema search paths: installed package → repo → work_dir."""
        paths: list[Path] = []
        # Try installed package location first
        try:
            import releaseboard.config.schema as rb_schema_mod

            paths.append(Path(rb_schema_mod.__file__).resolve().parent / "schema.json")
        except ImportError:
            pass
        if self._repo_path:
            paths.append(self._repo_path / "src" / "releaseboard" / "config" / "schema.json")
            paths.append(self._repo_path / "schema" / "releaseboard.schema.json")
        if self._work_dir:
            paths.append(self._work_dir / "schema.json")
        return paths

    def _resolve_config_path(self) -> Path:
        """Multi-strategy config resolution for production use.

        Search order:
        1. Environment variable OPSPORTAL_RELEASEBOARD_CONFIG (explicit override)
        2. repo_path / config_file  (local dev checkout)
        3. work_dir / config_file   (remote-managed tool)
        4. tools_base_dir / config_file
        5. CWD / config_file

        Returns the first path that exists, or falls back to the best
        canonical location for creation/save.
        """
        env_path = os.environ.get("OPSPORTAL_RELEASEBOARD_CONFIG")
        if env_path:
            p = Path(env_path).resolve()
            if p.exists():
                return p
            logger.warning(
                "OPSPORTAL_RELEASEBOARD_CONFIG=%s does not exist, trying other locations",
                env_path,
            )

        candidates: list[Path] = []
        if self._repo_path:
            candidates.append(self._repo_path / self._config_file)
        if self._work_dir:
            candidates.append(self._work_dir / self._config_file)
        if self._tools_base_dir:
            candidates.append(self._tools_base_dir / self._config_file)
        candidates.append(Path.cwd() / self._config_file)

        for candidate in candidates:
            resolved = candidate.resolve()
            if resolved.exists():
                logger.debug("ReleaseBoard config found at %s", resolved)
                return resolved

        # Return the canonical location for creation/error messages
        # Prefer work_dir for remote-managed tools, repo_path for local
        if self._work_dir:
            return (self._work_dir / self._config_file).resolve()
        if self._repo_path:
            return (self._repo_path / self._config_file).resolve()
        return (Path.cwd() / self._config_file).resolve()

    # -- Identity -----------------------------------------------------------
    @property
    def slug(self) -> str:
        return "releaseboard"

    @property
    def display_name(self) -> str:
        return "ReleaseBoard"

    @property
    def description(self) -> str:
        return "Release readiness dashboard - track branch status across repos"

    @property
    def integration_mode(self) -> IntegrationMode:
        return IntegrationMode.SUBPROCESS_WEB

    @property
    def capabilities(self) -> set[ToolCapability]:
        return {
            ToolCapability.WEB_UI,
            ToolCapability.HEALTH_CHECK,
            ToolCapability.PROCESS,
            ToolCapability.CONFIGURABLE,
        }

    @property
    def has_first_run_wizard(self) -> bool:
        return True

    @property
    def icon(self) -> str:
        return "clipboard-check"

    @property
    def color(self) -> str:
        return "#059669"

    @property
    def repo_path(self) -> Path | None:
        return self._repo_path

    @property
    def work_dir(self) -> Path | None:
        return self._work_dir

    # -- Status & health ----------------------------------------------------
    async def get_status(self) -> ToolStatus:
        proc = self._pm.get(self._process_name)
        if proc and proc.status == ProcessStatus.RUNNING:
            return ToolStatus.RUNNING
        if proc and proc.status == ProcessStatus.FAILED:
            return ToolStatus.ERROR
        return ToolStatus.STOPPED

    def _get_http_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            from opsportal.core.network import make_http_client

            self._http_client = make_http_client()
        return self._http_client

    async def health_check(self) -> HealthResult:
        proc = self._pm.get(self._process_name)
        if not proc or proc.status != ProcessStatus.RUNNING:
            return HealthResult(healthy=False, message="Process not running")
        try:
            client = self._get_http_client()
            resp = await client.get(f"http://127.0.0.1:{self._port}/health/live")
            if resp.status_code == 200:
                return HealthResult(
                    healthy=True,
                    message="Alive",
                    details={"port": self._port, "pid": proc.pid},
                )
            return HealthResult(healthy=False, message=f"HTTP {resp.status_code}")
        except (httpx.HTTPError, OSError) as exc:
            return HealthResult(healthy=False, message=f"Connection error: {exc}")

    # -- Auto-start ---------------------------------------------------------
    async def ensure_ready(self) -> EnsureReadyResult:
        """Start the ReleaseBoard server if not running, wait for health.

        ReleaseBoard has a built-in first-run wizard: when the config file
        does not exist it launches in setup mode instead of crashing.
        """
        if not shutil.which(self._cli):
            return EnsureReadyResult(
                ready=False,
                error=f"CLI binary '{self._cli}' not found in PATH. "
                "Install ReleaseBoard: pip install releaseboard",
            )

        config_path = self._resolve_config_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            self._cli,
            "serve",
            "--port",
            str(self._port),
            "--config",
            str(config_path),
        ]

        managed = await self._pm.ensure_running(
            self._process_name,
            cmd,
            cwd=self.effective_cwd,
            env=self._env,
            port=self._port,
            health_endpoint="/health/live",
            startup_timeout=self._startup_timeout,
        )

        if managed.status == ProcessStatus.FAILED:
            logs = self._pm.get_logs(self._process_name, tail=50)
            return EnsureReadyResult(
                ready=False,
                error="Server failed to start or health check timed out",
                logs=logs,
            )

        web_url = f"http://127.0.0.1:{self._port}"
        return EnsureReadyResult(
            ready=True,
            message=f"ReleaseBoard running on port {self._port}",
            web_url=web_url,
        )

    # -- Web UI -------------------------------------------------------------
    def get_web_url(self) -> str | None:
        proc = self._pm.get(self._process_name)
        if proc and proc.status == ProcessStatus.RUNNING:
            return f"http://127.0.0.1:{self._port}"
        return None

    def get_version(self) -> str | None:
        """Read version from ReleaseBoard's installed package metadata."""
        try:
            from importlib.metadata import version

            return version("releaseboard")
        except Exception:  # PackageNotFoundError, ImportError, or other metadata errors
            return None

    # -- Actions ------------------------------------------------------------
    def get_actions(self) -> list[ToolAction]:
        return [
            ToolAction(
                name="stop",
                label="Stop Server",
                description="Stop the running server",
                icon="square",
                dangerous=True,
            ),
            ToolAction(
                name="restart",
                label="Restart Server",
                description="Restart the server",
                icon="refresh-cw",
            ),
        ]

    # -- Integration --------------------------------------------------------
    def get_integration_endpoints(self) -> list[IntegrationEndpoint]:
        from opsportal.adapters.base import IntegrationCapability, IntegrationEndpoint

        return [
            IntegrationEndpoint(
                capability=IntegrationCapability.RELEASE_CALENDAR,
                method="GET",
                path="/api/release-calendar/milestones",
                description="Upcoming release milestones with days remaining",
            ),
            IntegrationEndpoint(
                capability=IntegrationCapability.RELEASE_CALENDAR,
                method="GET",
                path="/api/release-calendar",
                description="Full release calendar data",
            ),
            IntegrationEndpoint(
                capability=IntegrationCapability.TAGS,
                method="GET",
                path="/api/analyze/results",
                description="Analysis results including latest tag per repo",
            ),
            IntegrationEndpoint(
                capability=IntegrationCapability.RELEASE_NOTES,
                method="POST",
                path="/api/release-pilot/prepare",
                description="Generate release notes for a repository",
            ),
            IntegrationEndpoint(
                capability=IntegrationCapability.RELEASE_NOTES,
                method="GET",
                path="/api/release-pilot/capabilities",
                description="Check ReleasePilot availability",
            ),
        ]

    async def run_action(self, action_name: str, params: dict[str, Any]) -> ActionResult:
        actions = {
            "start": self._action_start,
            "stop": self._stop_server,
            "restart": self._action_restart,
        }
        handler = actions.get(action_name)
        if not handler:
            return ActionResult(success=False, error=f"Unknown action: {action_name}")
        return await handler()

    async def _action_start(self) -> ActionResult:
        result = await self.ensure_ready()
        return self._ready_to_action(result)

    async def _action_restart(self) -> ActionResult:
        await self._stop_server()
        result = await self.ensure_ready()
        return self._ready_to_action(result)

    @staticmethod
    def _ready_to_action(result: EnsureReadyResult) -> ActionResult:
        if result.ready:
            return ActionResult(success=True, output=result.message)
        return ActionResult(success=False, error=result.error)

    async def _stop_server(self) -> ActionResult:
        try:
            await self._pm.stop(self._process_name, port=self._port)
            return ActionResult(success=True, output="ReleaseBoard stopped")
        except (OSError, RuntimeError) as exc:
            return ActionResult(success=False, error=str(exc))

    # -- Lifecycle ----------------------------------------------------------
    async def startup(self) -> None:
        """Ensure the work directory exists on portal startup."""
        config_path = self._resolve_config_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)

    async def shutdown(self) -> None:
        await self._stop_server()
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None
