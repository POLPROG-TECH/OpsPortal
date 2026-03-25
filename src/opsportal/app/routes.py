"""Portal routes — HTML pages and JSON API endpoints."""

from __future__ import annotations

import html as html_mod
import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from opsportal.adapters.base import ToolCapability
from opsportal.services.health import check_all_health

router = APIRouter()

# Known logo locations within tool repos (checked in order)
_LOGO_CANDIDATES = [
    Path("docs") / "assets" / "logo.svg",
    Path("assets") / "logo.svg",
]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _templates(request: Request):
    return request.app.state.templates


def _registry(request: Request):
    return request.app.state.registry


def _log_store(request: Request):
    return request.app.state.log_store


def _artifact_manager(request: Request):
    return request.app.state.artifact_manager


def _process_manager(request: Request):
    return request.app.state.process_manager


def _find_logo(repo_path: Path | None) -> Path | None:
    """Return the first existing logo file in a tool's repo, or None."""
    if not repo_path or not repo_path.is_dir():
        return None
    for candidate in _LOGO_CANDIDATES:
        full = repo_path / candidate
        if full.is_file():
            return full
    return None


def _config_issues(adapter) -> list[str]:
    """Check for common configuration problems."""
    issues: list[str] = []

    rp = adapter.repo_path
    wd = getattr(adapter, "work_dir", None)
    if rp is None and wd is None:
        issues.append("Neither repository path nor work directory is configured")
    elif rp is not None and not rp.is_dir():
        issues.append("Repository not found at expected location")

    if not _has_missing_config(adapter):
        return issues

    # Tool handles missing config with its own setup wizard
    if getattr(adapter, "has_first_run_wizard", False):
        return issues

    # Config file is expected but missing — try scaffolding first
    if hasattr(adapter, "scaffold_default_config") and adapter.scaffold_default_config():
        return issues

    # Scaffolding didn't work — report actionable guidance
    slug = getattr(adapter, "slug", "tool")
    config_file = getattr(adapter, "_config_file", "config.json")
    env_var = f"OPSPORTAL_{slug.upper()}_CONFIG"
    config_dir = wd or rp or Path.cwd()
    issues.append(
        f"Configuration file '{config_file}' not found. "
        f"Create it at {_sanitize_path(config_dir / config_file)} "
        f"or set {env_var} environment variable, "
        f"or use the Configuration page to set up this tool."
    )
    return issues


def _has_missing_config(adapter) -> bool:
    """Return True if the adapter expects a config file but doesn't have one."""
    if adapter.config_file_path() is not None:
        return False
    config_file = getattr(adapter, "_config_file", None)
    return bool(config_file)


def _sanitize_logs(logs: list[str]) -> list[str]:
    """Replace the user's home directory path with ``~`` in log lines."""
    home = str(Path.home())
    return [line.replace(home, "~") for line in logs]


def _sanitize_path(path: Path) -> str:
    """Return a display-safe path without exposing home directories."""
    s = str(path)
    home = str(Path.home())
    if s.startswith(home):
        s = "~" + s[len(home) :]
    return s


async def _tool_cards(request: Request) -> list[dict[str, Any]]:
    """Build the data structure for dashboard tool cards."""
    cards = []
    for adapter in _registry(request).all():
        status = await adapter.get_status()
        has_logo = _find_logo(adapter.repo_path) is not None
        issues = _config_issues(adapter)
        cards.append(
            {
                "slug": adapter.slug,
                "name": adapter.display_name,
                "description": adapter.description,
                "icon": adapter.icon,
                "color": adapter.color,
                "status": status.value,
                "mode": adapter.integration_mode.value,
                "version": adapter.get_version(),
                "has_web_ui": ToolCapability.WEB_UI in adapter.capabilities,
                "has_cli": ToolCapability.CLI_COMMANDS in adapter.capabilities,
                "has_artifacts": ToolCapability.ARTIFACTS in adapter.capabilities,
                "has_config": ToolCapability.CONFIGURABLE in adapter.capabilities,
                "has_logo": has_logo,
                "logo_url": f"/api/tools/{adapter.slug}/logo" if has_logo else None,
                "config_ok": len(issues) == 0,
                "config_issues": issues,
            }
        )
    return cards


# ---------------------------------------------------------------------------
# HTML Pages
# ---------------------------------------------------------------------------


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    cards = await _tool_cards(request)
    total = len(cards)
    configured = sum(1 for c in cards if c["config_ok"])
    running = sum(1 for c in cards if c["status"] == "running")
    needs_attention = sum(1 for c in cards if not c["config_ok"] or c["status"] == "error")
    platform = {
        "total": total,
        "configured": configured,
        "running": running,
        "needs_attention": needs_attention,
    }
    return _templates(request).TemplateResponse(
        request,
        "home.html",
        {
            "cards": cards,
            "platform": platform,
        },
    )


@router.get("/health", response_class=HTMLResponse)
async def health_page(request: Request):
    result = await check_all_health(_registry(request))
    return _templates(request).TemplateResponse(
        request,
        "health.html",
        {
            "health": result,
        },
    )


@router.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request):
    entries = _log_store(request).recent(200)
    return _templates(request).TemplateResponse(
        request,
        "logs.html",
        {
            "entries": entries,
        },
    )


@router.get("/config", response_class=HTMLResponse)
async def config_page(request: Request):
    settings = request.app.state.settings
    adapters = _registry(request).all()
    return _templates(request).TemplateResponse(
        request,
        "config.html",
        {
            "settings": settings,
            "adapters": adapters,
        },
    )


@router.get("/tools/{slug}", response_class=HTMLResponse)
async def tool_page(request: Request, slug: str):
    adapter = _registry(request).get(slug)
    if not adapter:
        raise HTTPException(404, f"Tool {slug!r} not found")

    # Auto-start / ensure the tool is ready before rendering
    try:
        ready_result = await adapter.ensure_ready()
    except Exception as exc:
        proc_logs = _process_manager(request).get_logs(slug, tail=100)
        return _templates(request).TemplateResponse(
            request,
            "tool_error.html",
            {
                "tool": adapter,
                "error": f"Startup error: {exc}",
                "logs": _sanitize_logs(proc_logs),
            },
        )

    if not ready_result.ready:
        # Show diagnostic error page
        proc_logs = _process_manager(request).get_logs(slug, tail=100)
        return _templates(request).TemplateResponse(
            request,
            "tool_error.html",
            {
                "tool": adapter,
                "error": ready_result.error or "Tool failed to start",
                "logs": _sanitize_logs(ready_result.logs + proc_logs),
            },
        )

    status = await adapter.get_status()
    web_url = ready_result.web_url or adapter.get_web_url()
    actions = adapter.get_actions()
    artifacts = []
    latest_artifact = None
    art_dir = adapter.get_artifact_dir()

    # If ensure_ready produced an artifact, register it
    if ready_result.artifact_path and ready_result.artifact_path.exists():
        _artifact_manager(request).store(slug, ready_result.artifact_path)

    if art_dir:
        artifacts = _artifact_manager(request).list_artifacts(slug)
        if artifacts:
            latest_artifact = artifacts[0]

    ctx = {
        "tool": adapter,
        "status": status.value,
        "web_url": web_url,
        "actions": actions,
        "artifacts": artifacts,
        "latest_artifact": latest_artifact,
        "proc_logs": _process_manager(request).get_logs(slug, tail=100),
    }

    if web_url:
        return _templates(request).TemplateResponse(request, "tool_web.html", ctx)
    return _templates(request).TemplateResponse(request, "tool_cli.html", ctx)


@router.get("/tools/{slug}/artifacts/{name:path}", response_class=HTMLResponse)
async def view_artifact(request: Request, slug: str, name: str):
    adapter = _registry(request).get(slug)
    if not adapter:
        raise HTTPException(404)

    entry = _artifact_manager(request).get_artifact(slug, name)
    if not entry:
        raise HTTPException(404, f"Artifact {name!r} not found")

    if entry.content_type == "text/html":
        # Serve HTML artifacts in a sandboxed iframe context
        resp = HTMLResponse(entry.path.read_text(encoding="utf-8"))
        resp.headers["Content-Security-Policy"] = (
            "sandbox; default-src 'none'; style-src 'unsafe-inline'"
        )
        return resp
    content = html_mod.escape(entry.path.read_text(encoding="utf-8"))
    return HTMLResponse(f"<pre>{content}</pre>")


# ---------------------------------------------------------------------------
# JSON API
# ---------------------------------------------------------------------------


@router.get("/api/health")
async def api_health(request: Request):
    result = await check_all_health(_registry(request))
    return JSONResponse(result.to_dict())


@router.get("/api/tools")
async def api_tools(request: Request):
    cards = await _tool_cards(request)
    return JSONResponse(cards)


@router.get("/api/tools/{slug}/status")
async def api_tool_status(request: Request, slug: str):
    adapter = _registry(request).get(slug)
    if not adapter:
        raise HTTPException(404)
    status = await adapter.get_status()
    health = await adapter.health_check()
    return JSONResponse(
        {
            "slug": slug,
            "status": status.value,
            "health": {"healthy": health.healthy, "message": health.message},
        }
    )


@router.post("/api/tools/{slug}/actions/{action}")
async def api_run_action(request: Request, slug: str, action: str):
    adapter = _registry(request).get(slug)
    if not adapter:
        raise HTTPException(404)

    ct = request.headers.get("content-type", "")
    if ct.startswith("application/json"):
        try:
            body = await request.json()
        except (json.JSONDecodeError, ValueError):
            return JSONResponse({"ok": False, "error": "Invalid JSON body"}, status_code=400)
    else:
        body = {}
    log = _log_store(request)

    log.add(slug, action, f"Starting action: {action}")
    result = await adapter.run_action(action, body)
    log.add(
        slug,
        action,
        f"Completed: {'success' if result.success else 'failed'}"
        + (f" — {result.error}" if result.error else ""),
        level="info" if result.success else "error",
    )

    # If an artifact was produced, store it
    if result.artifact_path and result.artifact_path.exists():
        _artifact_manager(request).store(slug, result.artifact_path)

    return JSONResponse(
        {
            "success": result.success,
            "output": result.output,
            "error": result.error,
            "duration_ms": result.duration_ms,
            "artifact": result.artifact_path.name if result.artifact_path else None,
        }
    )


@router.post("/api/tools/{slug}/start")
async def api_start_tool(request: Request, slug: str):
    return await api_run_action(request, slug, "start")


@router.post("/api/tools/{slug}/stop")
async def api_stop_tool(request: Request, slug: str):
    return await api_run_action(request, slug, "stop")


@router.get("/api/tools/{slug}/logs")
async def api_tool_logs(request: Request, slug: str):
    entries = _log_store(request).recent(100, tool_slug=slug)
    proc_logs = _process_manager(request).get_logs(slug, tail=100)
    return JSONResponse(
        {
            "activity": [
                {"time": e.time_str, "action": e.action, "message": e.message} for e in entries
            ],
            "process_logs": proc_logs,
        }
    )


@router.get("/api/tools/{slug}/logo")
async def api_tool_logo(request: Request, slug: str):
    """Serve the tool's logo SVG from its repository."""
    adapter = _registry(request).get(slug)
    if not adapter:
        raise HTTPException(404)
    logo = _find_logo(adapter.repo_path)
    if not logo:
        raise HTTPException(404, "No logo found")
    return FileResponse(logo, media_type="image/svg+xml")


# ---------------------------------------------------------------------------
# Config API — per-tool configuration read / validate / save
# ---------------------------------------------------------------------------


@router.get("/api/tools/{slug}/config")
async def api_tool_config(request: Request, slug: str):
    """Return the tool's JSON Schema and current config values."""
    adapter = _registry(request).get(slug)
    if not adapter:
        raise HTTPException(404)
    schema = adapter.config_schema()
    data = adapter.get_config()
    config_path = adapter.config_file_path()
    return JSONResponse(
        {
            "slug": slug,
            "configurable": schema is not None,
            "schema": schema,
            "values": data,
            "config_file": str(config_path) if config_path else None,
        }
    )


@router.post("/api/tools/{slug}/config/validate")
async def api_tool_config_validate(request: Request, slug: str):
    """Validate config data without saving."""
    adapter = _registry(request).get(slug)
    if not adapter:
        raise HTTPException(404)
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError):
        return JSONResponse({"ok": False, "error": "Invalid JSON body"}, status_code=400)
    result = adapter.validate_config(body)
    return JSONResponse(
        {
            "valid": result.valid,
            "errors": result.errors,
        }
    )


@router.put("/api/tools/{slug}/config")
async def api_tool_config_save(request: Request, slug: str):
    """Validate and save config data."""
    adapter = _registry(request).get(slug)
    if not adapter:
        raise HTTPException(404)
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError):
        return JSONResponse({"ok": False, "error": "Invalid JSON body"}, status_code=400)
    result = adapter.save_config(body)
    return JSONResponse(
        {
            "success": result.success,
            "output": result.output,
            "error": result.error,
        }
    )


@router.get("/tools/{slug}/config", response_class=HTMLResponse)
async def tool_config_page(request: Request, slug: str):
    """Per-tool configuration editing page."""
    adapter = _registry(request).get(slug)
    if not adapter:
        raise HTTPException(404, f"Tool {slug!r} not found")
    schema = adapter.config_schema()
    data = adapter.get_config()
    config_path = adapter.config_file_path()
    return _templates(request).TemplateResponse(
        request,
        "tool_config.html",
        {
            "tool": adapter,
            "schema": schema,
            "values": data,
            "config_file": str(config_path) if config_path else None,
            "configurable": schema is not None,
        },
    )
