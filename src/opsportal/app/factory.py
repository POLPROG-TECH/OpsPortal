"""Application factory — creates and configures the FastAPI portal app."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse
from starlette.templating import Jinja2Templates

from opsportal import __version__
from opsportal.adapters.appsecone import AppSecOneAdapter
from opsportal.adapters.flowboard import FlowBoardAdapter
from opsportal.adapters.localesync import LocaleSyncAdapter
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
from opsportal.services.audit_log import AuditLog
from opsportal.services.cache import TTLCache
from opsportal.services.config_versioning import ConfigVersionManager
from opsportal.services.log_store import LogStore
from opsportal.services.metrics_collector import MetricsCollector
from opsportal.services.notification_service import NotificationService, WebhookConfig
from opsportal.services.plugin_loader import PluginLoader
from opsportal.services.process_manager import ProcessManager
from opsportal.services.scheduler import Scheduler
from opsportal.services.sla_reporter import SLAReporter
from opsportal.services.tool_installer import ToolInstaller, ToolInstallError
from opsportal.services.uptime_tracker import UptimeTracker

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

    # -- New services -------------------------------------------------------
    app.state.audit_log = AuditLog(settings.work_dir / "audit.jsonl")
    app.state.config_versions = ConfigVersionManager(settings.work_dir / "config_versions")
    app.state.metrics_collector = MetricsCollector()
    app.state.uptime_tracker = UptimeTracker(settings.uptime_data_dir)
    app.state.cache = TTLCache(default_ttl=settings.cache_ttl)

    # Notification service
    webhooks = []
    if settings.webhook_urls:
        for url in settings.webhook_urls.split(","):
            url = url.strip()
            if url:
                webhooks.append(WebhookConfig(url=url))
    app.state.notification_service = NotificationService(webhooks)

    # Scheduler
    app.state.scheduler = Scheduler(settings.scheduler_config_path)

    # Plugin loader
    app.state.plugin_loader = PluginLoader()
    app.state.plugin_loader.discover()

    # Alert manager
    from opsportal.services.alert_manager import AlertManager

    app.state.alert_manager = AlertManager(settings.work_dir / "alerts.json")

    # Backup service
    from opsportal.services.backup_service import BackupService

    app.state.backup_service = BackupService(
        work_dir=settings.work_dir,
        manifest_path=settings.manifest_path,
    )

    # SLA reporter
    app.state.sla_reporter = SLAReporter()

    # Auth manager (RBAC)
    from opsportal.services.auth_manager import AuthManager

    app.state.auth_manager = AuthManager(settings.work_dir / "users.json")

    # -- Templates & static -------------------------------------------------
    templates = Jinja2Templates(directory=str(_TEMPLATE_DIR))
    templates.env.globals["portal_version"] = __version__
    templates.env.globals["auth_enabled"] = settings.auth_enabled
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
        if request.url.path.startswith("/api/"):
            return JSONResponse(
                {"error": exc.detail},
                status_code=exc.status_code,
            )
        return templates.TemplateResponse(
            request,
            "error.html",
            {"error": exc.detail},
            status_code=exc.status_code,
        )

    # -- Middleware ----------------------------------------------------------
    # Collect child tool ports so CSP allows framing them
    child_ports = [t.port for t in manifest.enabled_tools if t.port]
    app.add_middleware(
        PortalSecurityMiddleware,
        child_tool_ports=child_ports,
        auth_enabled=settings.auth_enabled,
        auth_username=settings.auth_username,
        auth_password=settings.auth_password,
    )

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
        (settings.artifact_dir / slug).mkdir(parents=True, exist_ok=True)
        _auto_install_tool(installer, tool)
        _create_and_register(registry, slug, tool, app)


def _auto_install_tool(installer: ToolInstaller, tool: ToolConfig) -> None:
    """Install a tool from its source definition if configured."""
    if not tool.source:
        return
    try:
        result = installer.ensure_installed(tool.source)
        logger.info("Tool %s: %s", tool.slug, result)
    except (ToolInstallError, OSError):
        logger.exception("Failed to install %s from source", tool.slug)


def _create_and_register(registry: AdapterRegistry, slug: str, tool: ToolConfig, app) -> None:
    """Create an adapter and register it, logging any errors."""
    try:
        adapter = _make_adapter(slug, tool, app)
        if adapter:
            registry.register(adapter)
    except (ValueError, TypeError, OSError):
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
            tools_base_dir=settings.tools_base_dir,
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
    if slug == "localesync":
        return LocaleSyncAdapter(
            pm,
            repo_path=tool.repo_path,
            work_dir=work_dir,
            port=tool.port or 8083,
            config_file=tool.config_file or "localesync.json",
            cli_binary=tool.cli_binary or "locale-sync",
            env=tool.env,
            startup_timeout=tool.startup_timeout,
            tools_base_dir=settings.tools_base_dir,
            portal_origins=portal_origins,
        )
    if slug == "flowboard":
        return FlowBoardAdapter(
            pm,
            repo_path=tool.repo_path,
            work_dir=work_dir,
            port=tool.port or 8084,
            config_file=tool.config_file or "flowboard.json",
            cli_binary=tool.cli_binary or "flowboard",
            env=tool.env,
            startup_timeout=tool.startup_timeout,
            tools_base_dir=settings.tools_base_dir,
            portal_origins=portal_origins,
        )
    if slug == "appsecone":
        return AppSecOneAdapter(
            pm,
            repo_path=tool.repo_path,
            work_dir=work_dir,
            port=tool.port or 8085,
            config_file=tool.config_file or "appsecone.json",
            cli_binary=tool.cli_binary or "appsecone",
            env=tool.env,
            startup_timeout=tool.startup_timeout,
            tools_base_dir=settings.tools_base_dir,
            portal_origins=portal_origins,
        )

    logger.warning("No adapter implementation for slug=%r, skipping", slug)
    return None
