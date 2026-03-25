"""ReleasePilot adapter — SUBPROCESS_WEB integration with auto-start.

ReleasePilot now exposes a full FastAPI web application with its own UI.
The portal runs it as a managed subprocess and embeds it via iframe.
The server is started automatically when the user enters the tool.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import httpx

from opsportal.adapters._config_mixin import JsonSchemaConfigMixin
from opsportal.adapters.base import (
    ActionResult,
    EnsureReadyResult,
    HealthResult,
    IntegrationMode,
    ToolAction,
    ToolAdapter,
    ToolCapability,
    ToolStatus,
)
from opsportal.core.errors import get_logger
from opsportal.services.process_manager import ProcessManager, ProcessStatus

logger = get_logger("adapters.releasepilot")


def _rp_validate(data: dict[str, Any]) -> list[str]:
    """Validate using ReleasePilot's own validator (returns warnings)."""
    from releasepilot.config.file_config import validate_config

    warnings = validate_config(data)
    return [w.message for w in warnings]


class ReleasePilotAdapter(JsonSchemaConfigMixin, ToolAdapter):
    def __init__(
        self,
        process_manager: ProcessManager,
        *,
        repo_path: Path | None = None,
        work_dir: Path | None = None,
        port: int = 8082,
        cli_binary: str = "releasepilot",
        env: dict[str, str] | None = None,
        startup_timeout: int = 30,
        portal_origins: str = "http://127.0.0.1:8000,http://localhost:8000",
    ) -> None:
        self._repo_path = repo_path
        self._work_dir = work_dir
        self._pm = process_manager
        self._port = port
        self._cli = cli_binary
        self._env = {
            **(env or {}),
            "RELEASEPILOT_ALLOW_FRAMING": "true",
            "RELEASEPILOT_CORS_ORIGINS": portal_origins,
        }
        self._startup_timeout = startup_timeout
        self._process_name = "releasepilot"
        self._http_client: httpx.AsyncClient | None = None
        # Config mixin setup — ReleasePilot uses auto-discovered config files
        self._config_file = ".releasepilot.json"
        self._schema_paths = self._build_schema_paths()
        self._validate_fn = _rp_validate

    def _build_schema_paths(self) -> list[Path]:
        """Build schema search paths: installed package → repo → work_dir."""
        paths: list[Path] = []
        # Try installed package location
        try:
            import releasepilot

            pkg_dir = Path(releasepilot.__file__).resolve().parent
            paths.append(pkg_dir / "schema" / "releasepilot.schema.json")
        except ImportError:
            pass
        if self._repo_path:
            paths.append(self._repo_path / "schema" / "releasepilot.schema.json")
        if self._work_dir:
            paths.append(self._work_dir / "releasepilot.schema.json")
        return paths

    # -- Identity -----------------------------------------------------------
    @property
    def slug(self) -> str:
        return "releasepilot"

    @property
    def display_name(self) -> str:
        return "ReleasePilot"

    @property
    def description(self) -> str:
        return "Release notes generator — from git history to polished documents"

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
    def icon(self) -> str:
        return "rocket"

    @property
    def color(self) -> str:
        return "#4F46E5"

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
        if not shutil.which(self._cli):
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
        except Exception as exc:
            return HealthResult(healthy=False, message=f"Connection error: {exc}")

    # -- Auto-start ---------------------------------------------------------
    async def ensure_ready(self) -> EnsureReadyResult:
        """Start the ReleasePilot server if not running, wait for health."""
        if not shutil.which(self._cli):
            return EnsureReadyResult(
                ready=False,
                error=f"CLI binary '{self._cli}' not found in PATH. "
                "Install ReleasePilot: pip install releasepilot",
            )

        # Auto-scaffold default config from schema if missing
        self.scaffold_default_config()

        cmd = [
            self._cli,
            "serve",
            "--port",
            str(self._port),
        ]

        cwd = self.effective_cwd
        managed = await self._pm.ensure_running(
            self._process_name,
            cmd,
            cwd=cwd,
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
            message=f"ReleasePilot running on port {self._port}",
            web_url=web_url,
        )

    # -- Web UI -------------------------------------------------------------
    def get_web_url(self) -> str | None:
        proc = self._pm.get(self._process_name)
        if proc and proc.status == ProcessStatus.RUNNING:
            return f"http://127.0.0.1:{self._port}"
        return None

    def get_version(self) -> str | None:
        """Read version from ReleasePilot's installed package metadata."""
        try:
            from importlib.metadata import version

            return version("releasepilot")
        except Exception:
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

    async def run_action(self, action_name: str, params: dict[str, Any]) -> ActionResult:
        if action_name == "start":
            result = await self.ensure_ready()
            if result.ready:
                return ActionResult(success=True, output=result.message)
            return ActionResult(success=False, error=result.error)
        if action_name == "stop":
            return await self._stop_server()
        if action_name == "restart":
            await self._stop_server()
            result = await self.ensure_ready()
            if result.ready:
                return ActionResult(success=True, output=result.message)
            return ActionResult(success=False, error=result.error)
        return ActionResult(success=False, error=f"Unknown action: {action_name}")

    async def _stop_server(self) -> ActionResult:
        try:
            await self._pm.stop(self._process_name)
            return ActionResult(success=True, output="ReleasePilot stopped")
        except Exception as exc:
            return ActionResult(success=False, error=str(exc))

    # -- Lifecycle ----------------------------------------------------------
    async def startup(self) -> None:
        pass  # Started on demand

    async def shutdown(self) -> None:
        await self._stop_server()
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None
