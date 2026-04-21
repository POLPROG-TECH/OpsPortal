"""Portal routes - HTML pages and route assembly.

Sub-modules:
  routes_api   - tool API, bulk actions, metrics, streaming
  routes_admin - config, versioning, audit, scheduler, notifications
"""

from __future__ import annotations

import html as html_mod
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from opsportal.app.routes_admin import router as admin_router
from opsportal.app.routes_api import (
    _artifact_manager,
    _log_store,
    _process_manager,
    _registry,
    config_issues,  # noqa: F401 - re-exported
    tool_cards,
)
from opsportal.app.routes_api import (
    config_issues as _config_issues,  # noqa: F401 - backward compat
)
from opsportal.app.routes_api import (
    router as api_router,
)
from opsportal.app.routes_integrations import router as integrations_router
from opsportal.services.health import check_all_health

router = APIRouter()
router.include_router(api_router)
router.include_router(admin_router)
router.include_router(integrations_router)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _templates(request: Request):
    return request.app.state.templates


def _sanitize_logs(logs: list[str]) -> list[str]:
    home = str(Path.home())
    return [line.replace(home, "~") for line in logs]


def _sanitize_path(path: Path) -> str:
    return str(path).replace(str(Path.home()), "~")


def _has_missing_config(adapter) -> bool:
    schema = adapter.config_schema()
    if not schema:
        return False
    data = adapter.get_config()
    if not data:
        return True
    return not adapter.validate_config(data).valid


# ---------------------------------------------------------------------------
# HTML Pages
# ---------------------------------------------------------------------------


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    cards = await tool_cards(request)
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
            "ops_overview_enabled": request.app.state.settings.ops_overview_enabled,
        },
    )


@router.get("/health", response_class=HTMLResponse)
async def health_page(request: Request):
    result = await check_all_health(_registry(request))
    return _templates(request).TemplateResponse(request, "health.html", {"health": result})


@router.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request):
    entries = _log_store(request).recent(200)
    return _templates(request).TemplateResponse(request, "logs.html", {"entries": entries})


@router.get("/config", response_class=HTMLResponse)
async def config_page(request: Request):
    settings = request.app.state.settings
    adapters = _registry(request).all()
    return _templates(request).TemplateResponse(
        request, "config.html", {"settings": settings, "adapters": adapters}
    )


@router.get("/uptime", response_class=HTMLResponse)
async def uptime_page(request: Request):
    tracker = request.app.state.uptime_tracker
    summaries = tracker.get_all_summaries()
    adapters = _registry(request).all()
    return _templates(request).TemplateResponse(
        request,
        "uptime.html",
        {"summaries": summaries, "adapters": adapters},
    )


@router.get("/tools/{slug}", response_class=HTMLResponse)
async def tool_page(request: Request, slug: str):
    adapter = _registry(request).get(slug)
    if not adapter:
        raise HTTPException(404, f"Tool {slug!r} not found")

    try:
        ready_result = await adapter.ensure_ready()
    except (OSError, RuntimeError) as exc:
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
        resp = HTMLResponse(entry.path.read_text(encoding="utf-8"))
        resp.headers["Content-Security-Policy"] = (
            "sandbox; default-src 'none'; style-src 'unsafe-inline'"
        )
        return resp
    content = html_mod.escape(entry.path.read_text(encoding="utf-8"))
    return HTMLResponse(f"<pre>{content}</pre>")


@router.get("/tools/{slug}/config", response_class=HTMLResponse)
async def tool_config_page(request: Request, slug: str):
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


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    """Monitoring dashboard with charts."""
    cards = await tool_cards(request)
    return _templates(request).TemplateResponse(request, "dashboard.html", {"cards": cards})


@router.get("/sla", response_class=HTMLResponse)
async def sla_page(request: Request):
    """SLA reporting page."""
    reporter = request.app.state.sla_reporter
    tracker = request.app.state.uptime_tracker
    report = reporter.generate_report(tracker)
    return _templates(request).TemplateResponse(request, "sla.html", {"report": report})


@router.get("/dependencies", response_class=HTMLResponse)
async def depgraph_page(request: Request):
    """Dependency graph visualization page."""
    return _templates(request).TemplateResponse(request, "depgraph.html", {})
