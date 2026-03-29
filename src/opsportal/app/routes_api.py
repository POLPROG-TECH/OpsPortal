"""Tool API routes — status, actions, logs, logos, bulk operations."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import (
    FileResponse,
    JSONResponse,
    PlainTextResponse,
    StreamingResponse,
)

from opsportal.adapters.base import ToolCapability
from opsportal.services.health import check_all_health

router = APIRouter()

_LOGO_CANDIDATES = [
    Path("docs") / "assets" / "logo.svg",
    Path("assets") / "logo.svg",
]


# ---------------------------------------------------------------------------
# Shared helpers (imported by other route modules too)
# ---------------------------------------------------------------------------


def _registry(request: Request):
    return request.app.state.registry


def _log_store(request: Request):
    return request.app.state.log_store


def _artifact_manager(request: Request):
    return request.app.state.artifact_manager


def _process_manager(request: Request):
    return request.app.state.process_manager


def _audit_log(request: Request):
    return request.app.state.audit_log


def _config_versions(request: Request):
    return request.app.state.config_versions


def _cache(request: Request):
    return request.app.state.cache


def _find_logo(repo_path: Path | None) -> Path | None:
    if not repo_path:
        return None
    for candidate in _LOGO_CANDIDATES:
        full = repo_path / candidate
        if full.is_file():
            return full
    return None


async def tool_cards(request: Request) -> list[dict[str, Any]]:
    """Build the data structure for dashboard tool cards."""
    uptime_tracker = request.app.state.uptime_tracker
    metrics_collector = request.app.state.metrics_collector
    cards = []
    for adapter in _registry(request).all():
        status = await adapter.get_status()
        has_logo = _find_logo(adapter.repo_path) is not None
        issues = config_issues(adapter)

        uptime_summary = uptime_tracker.get_summary(adapter.slug)
        tool_metrics = metrics_collector.get_tool(adapter.slug)

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
                "uptime_percent": uptime_summary.uptime_percent,
                "total_checks": uptime_summary.total_checks,
                "avg_latency_ms": round(uptime_summary.avg_latency_ms, 1),
                "memory_mb": (
                    round(tool_metrics.memory_rss_bytes / (1024 * 1024), 1) if tool_metrics else 0
                ),
            }
        )
    return cards


def config_issues(adapter) -> list[str]:
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


def _sanitize_path(path: Path) -> str:
    s = str(path)
    home = str(Path.home())
    if s.startswith(home):
        return "~" + s[len(home) :]
    return s


# ---------------------------------------------------------------------------
# Health & Tools List
# ---------------------------------------------------------------------------


@router.get("/api/health")
async def api_health(request: Request):
    result = await check_all_health(_registry(request))
    return JSONResponse(result.to_dict())


@router.get("/api/tools")
async def api_tools(request: Request):
    cards = await tool_cards(request)
    return JSONResponse(cards)


# ---------------------------------------------------------------------------
# Bulk Actions (must be before /api/tools/{slug} to avoid slug capture)
# ---------------------------------------------------------------------------


@router.post("/api/tools/bulk/{action}")
async def api_bulk_action(request: Request, action: str):
    """Execute a lifecycle action on all tools."""
    if action not in ("start", "stop", "restart"):
        raise HTTPException(400, f"Invalid bulk action: {action}")

    results = {}
    for adapter in _registry(request).all():
        slug = adapter.slug
        try:
            result = await adapter.run_action(action, {})
            results[slug] = {"success": result.success, "error": result.error}
            _log_store(request).add(
                slug, action, f"Bulk {action}: {'ok' if result.success else 'failed'}"
            )
        except (OSError, RuntimeError) as exc:
            results[slug] = {"success": False, "error": str(exc)}

    _audit_log(request).record(
        category="lifecycle",
        action=f"bulk_{action}",
        details={"results": results},
    )
    return JSONResponse({"action": action, "results": results})


# ---------------------------------------------------------------------------
# Per-tool: status, actions, logs, logo
# ---------------------------------------------------------------------------


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

    _audit_log(request).record(
        category="lifecycle",
        action=action,
        tool_slug=slug,
        details={"success": result.success, "error": result.error},
    )

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
    """Serve the tool's logo SVG from its repository (with caching)."""
    cache = _cache(request)
    cache_key = f"logo:{slug}"
    cached_path = cache.get(cache_key)
    if cached_path and Path(cached_path).exists():
        return FileResponse(cached_path, media_type="image/svg+xml")

    adapter = _registry(request).get(slug)
    if not adapter:
        raise HTTPException(404)
    logo = _find_logo(adapter.repo_path)
    if not logo:
        raise HTTPException(404, "No logo found")

    cache.set(cache_key, str(logo))
    return FileResponse(logo, media_type="image/svg+xml")


# ---------------------------------------------------------------------------
# SSE Log Streaming
# ---------------------------------------------------------------------------


@router.get("/api/tools/{slug}/logs/stream")
async def api_tool_logs_stream(request: Request, slug: str):
    """Server-Sent Events stream for real-time process logs."""

    async def event_generator():
        seen_count = 0
        try:
            while True:
                logs = _process_manager(request).get_logs(slug, tail=500)
                if len(logs) <= seen_count:
                    await asyncio.sleep(1)
                    continue
                for line in logs[seen_count:]:
                    yield f"data: {json.dumps({'line': line})}\n\n"
                seen_count = len(logs)
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/api/logs/stream")
async def api_activity_logs_stream(request: Request):
    """SSE stream for portal activity logs."""

    async def event_generator():
        last_count = _log_store(request).count()
        try:
            while True:
                current_count = _log_store(request).count()
                if current_count <= last_count:
                    await asyncio.sleep(1)
                    continue
                entries = _log_store(request).recent(current_count - last_count)
                for e in reversed(entries):
                    payload = json.dumps(
                        {
                            "time": e.time_str,
                            "level": e.level,
                            "tool": e.tool_slug,
                            "action": e.action,
                            "message": e.message,
                        }
                    )
                    yield f"data: {payload}\n\n"
                last_count = current_count
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


# ---------------------------------------------------------------------------
# Metrics & Uptime
# ---------------------------------------------------------------------------


@router.get("/metrics")
async def prometheus_metrics(request: Request):
    """Prometheus-compatible metrics endpoint."""
    metrics = request.app.state.metrics_collector
    await metrics.collect(_process_manager(request))
    return PlainTextResponse(metrics.to_prometheus(), media_type="text/plain; charset=utf-8")


@router.get("/api/metrics")
async def api_metrics(request: Request):
    """JSON metrics for dashboard display."""
    metrics = request.app.state.metrics_collector
    await metrics.collect(_process_manager(request))
    all_metrics = metrics.get_all()
    return JSONResponse({slug: m.to_dict() for slug, m in all_metrics.items()})


@router.get("/api/uptime")
async def api_uptime(request: Request):
    tracker = request.app.state.uptime_tracker
    summaries = tracker.get_all_summaries()
    return JSONResponse({slug: s.to_dict() for slug, s in summaries.items()})


@router.get("/api/uptime/{slug}/timeline")
async def api_uptime_timeline(request: Request, slug: str):
    tracker = request.app.state.uptime_tracker
    return JSONResponse(tracker.get_timeline(slug, limit=200))


@router.get("/api/dependencies")
async def api_dependencies(request: Request):
    """Return tool dependency graph for D3 visualization."""
    registry = _registry(request)
    pm = _process_manager(request)
    adapters = registry.all()
    nodes = []
    links = []
    seen = set()
    for a in adapters:
        slug = a.slug
        status = "stopped"
        if pm.is_running(slug):
            status = "running"
        nodes.append(
            {
                "id": slug,
                "label": a.name,
                "icon": getattr(a, "icon", "⚙️"),
                "status": status,
            }
        )
        seen.add(slug)
        deps = getattr(a, "depends_on", None) or []
        for dep in deps:
            links.append({"source": dep, "target": slug})
            if dep not in seen:
                nodes.append(
                    {
                        "id": dep,
                        "label": dep,
                        "icon": "📦",
                        "status": "unknown",
                    }
                )
                seen.add(dep)
    return JSONResponse({"nodes": nodes, "links": links})
