"""Application factory — creates and configures the FastAPI portal app."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.templating import Jinja2Templates

from opsportal import __version__
from opsportal.adapters.registry import AdapterRegistry
from opsportal.adapters.releaseboard import ReleaseBoardAdapter
from opsportal.adapters.releasepilot import ReleasePilotAdapter
from opsportal.app.lifespan import lifespan
from opsportal.app.middleware import PortalSecurityMiddleware
from opsportal.app.routes import router
from opsportal.config.manifest import PortalManifest, ToolConfig, load_manifest
from opsportal.core.errors import get_logger, setup_logging
from opsportal.core.settings import PortalSettings, get_settings
from opsportal.services.artifact_manager import ArtifactManager
from opsportal.services.log_store import LogStore
from opsportal.services.process_manager import ProcessManager
from opsportal.services.tool_installer import ToolInstaller

logger = get_logger("app.factory")

_UI_DIR = Path(__file__).resolve().parent.parent / "ui"
_TEMPLATE_DIR = _UI_DIR / "templates"
_STATIC_DIR = _UI_DIR / "static"


def create_app(settings: PortalSettings | None = None) -> FastAPI:
    """Build the OpsPortal FastAPI application."""

    if settings is None:
        settings = get_settings()

    setup_logging(settings.log_level)
    logger.info("Creating OpsPortal v%s", __version__)

    app = FastAPI(
        title="OpsPortal",
        description="Unified operations portal for internal developer tools",
        version=__version__,
        lifespan=lifespan,
    )

    # -- State / services ---------------------------------------------------
    app.state.settings = settings
    app.state.process_manager = ProcessManager(log_buffer_size=settings.log_buffer_size)
    app.state.artifact_manager = ArtifactManager(settings.artifact_dir)
    app.state.log_store = LogStore(max_entries=settings.log_buffer_size)
    app.state.tool_installer = ToolInstaller(settings.tools_work_dir)

    # -- Templates & static -------------------------------------------------
    templates = Jinja2Templates(directory=str(_TEMPLATE_DIR))
    templates.env.globals["portal_version"] = __version__
    app.state.templates = templates
    if _STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    # -- Load manifest & register adapters ----------------------------------
    manifest = load_manifest(
        settings.manifest_path,
        settings.tools_base_dir,
        tools_work_dir=settings.tools_work_dir,
    )
    app.state.manifest = manifest

    registry = AdapterRegistry()
    _register_adapters(registry, manifest, settings, app)
    app.state.registry = registry

    # -- Portal routes ------------------------------------------------------
    app.include_router(router)

    # -- Exception handlers -------------------------------------------------
    templates = app.state.templates

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        return templates.TemplateResponse(
            request,
            "error.html",
            {"error": exc.detail},
            status_code=exc.status_code,
        )

    # -- Middleware ----------------------------------------------------------
    # Collect child tool ports so CSP allows framing them
    child_ports = [t.port for t in manifest.enabled_tools if t.port]
    app.add_middleware(PortalSecurityMiddleware, child_tool_ports=child_ports)

    logger.info(
        "OpsPortal ready — %d tool(s) registered",
        len(registry),
    )
    return app


# ---------------------------------------------------------------------------
# Adapter wiring — auto-install from source, then create adapters
# ---------------------------------------------------------------------------


def _register_adapters(
    registry: AdapterRegistry,
    manifest: PortalManifest,
    settings: PortalSettings,
    app: FastAPI,
) -> None:
    """Create and register an adapter for each enabled tool in the manifest."""
    installer: ToolInstaller = app.state.tool_installer

    for tool in manifest.enabled_tools:
        slug = tool.slug
        art_dir = settings.artifact_dir / slug
        art_dir.mkdir(parents=True, exist_ok=True)

        # Auto-install from source if needed
        if tool.source:
            try:
                result = installer.ensure_installed(tool.source)
                logger.info("Tool %s: %s", slug, result)
            except Exception:
                logger.exception("Failed to install %s from source", slug)

        try:
            adapter = _make_adapter(slug, tool, app)
            if adapter:
                registry.register(adapter)
        except Exception:
            logger.exception("Failed to create adapter for %s", slug)


def _make_adapter(
    slug: str,
    tool: ToolConfig,
    app: FastAPI,
):
    pm = app.state.process_manager
    installer: ToolInstaller = app.state.tool_installer
    settings = app.state.settings
    portal_origin = f"http://{settings.host}:{settings.port}"
    portal_origins = f"{portal_origin},http://localhost:{settings.port}"

    # Compute work_dir for this tool
    work_dir = installer.work_dir_for(slug)

    if slug == "releasepilot":
        return ReleasePilotAdapter(
            pm,
            repo_path=tool.repo_path,
            work_dir=work_dir,
            port=tool.port or 8082,
            cli_binary=tool.cli_binary or "releasepilot",
            env=tool.env,
            startup_timeout=tool.startup_timeout,
            portal_origins=portal_origins,
        )
    if slug == "releaseboard":
        return ReleaseBoardAdapter(
            pm,
            repo_path=tool.repo_path,
            work_dir=work_dir,
            port=tool.port or 8081,
            config_file=tool.config_file or "releaseboard.json",
            cli_binary=tool.cli_binary or "releaseboard",
            env=tool.env,
            startup_timeout=tool.startup_timeout,
            tools_base_dir=settings.tools_base_dir,
            portal_origins=portal_origins,
        )

    logger.warning("No adapter implementation for slug=%r, skipping", slug)
    return None
