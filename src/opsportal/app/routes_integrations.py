"""Integration API routes - cross-tool data aggregation and one-click actions.

All integration endpoints live under ``/api/integrations/`` and proxy or
orchestrate data from child tools through the integration gateway.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from opsportal.core.errors import get_logger

router = APIRouter(prefix="/api/integrations", tags=["integrations"])

logger = get_logger("app.routes_integrations")


def _require_ops_overview(request: Request) -> None:
    """Raise 404 if Operations Overview is disabled in settings."""
    if not request.app.state.settings.ops_overview_enabled:
        raise HTTPException(
            status_code=404,
            detail="Operations Overview is disabled. Enable it in Admin → Configuration.",
        )


# ---------------------------------------------------------------------------
# Accessor helpers
# ---------------------------------------------------------------------------


def _calendar(request: Request):
    return request.app.state.calendar_aggregator


def _tags(request: Request):
    return request.app.state.tags_aggregator


def _release_notes(request: Request):
    return request.app.state.release_notes_orchestrator


def _translation(request: Request):
    return request.app.state.translation_proxy


def _widget_registry(request: Request):
    return request.app.state.widget_registry


# ---------------------------------------------------------------------------
# Calendar
# ---------------------------------------------------------------------------


@router.get("/calendar/milestones")
async def calendar_milestones(request: Request):
    """Upcoming release milestones from all capable tools."""
    result = await _calendar(request).get_milestones()
    return JSONResponse(result)


@router.get("/calendar")
async def calendar_full(request: Request):
    """Full release calendar data."""
    result = await _calendar(request).get_full_calendar()
    return JSONResponse(result)


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------


@router.get("/tags")
async def tags_overview(request: Request):
    """Latest Git tags per repository from all capable tools."""
    result = await _tags(request).get_tags_summary()
    return JSONResponse(result)


# ---------------------------------------------------------------------------
# Release Notes
# ---------------------------------------------------------------------------


@router.post("/release-notes/generate")
async def generate_release_notes(request: Request):
    """Generate release notes across all connected applications."""
    body: dict = {}
    with contextlib.suppress(json.JSONDecodeError, ValueError):
        body = await request.json()

    result = await _release_notes(request).generate_all(
        audience=body.get("audience", "changelog"),
        output_format=body.get("output_format", "markdown"),
        language=body.get("language", "en"),
        app_filter=body.get("apps"),
    )
    return JSONResponse(result)


@router.post("/release-notes/stream")
async def generate_release_notes_stream(request: Request):
    """Generate release notes with SSE streaming progress per repo."""
    body: dict = {}
    with contextlib.suppress(json.JSONDecodeError, ValueError):
        body = await request.json()

    orchestrator = _release_notes(request)

    async def event_stream():
        async for event in orchestrator.generate_all_streaming(
            audience=body.get("audience", "changelog"),
            output_format=body.get("output_format", "markdown"),
            language=body.get("language", "en"),
            app_filter=body.get("apps"),
        ):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


# ---------------------------------------------------------------------------
# Translation
# ---------------------------------------------------------------------------


@router.get("/translate/languages")
async def translation_languages(request: Request):
    """Supported target languages for JSON translation."""
    proxy = _translation(request)
    return JSONResponse({"ok": True, "languages": proxy.supported_languages()})


@router.post("/translate")
async def translate_json(request: Request):
    """Translate a JSON object preserving structure, keys, and nesting."""
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError):
        return JSONResponse({"ok": False, "error": "Invalid JSON body"}, status_code=400)

    json_data = body.get("json_data")
    target = body.get("target_language", "pl")
    source = body.get("source_language", "en")

    if not json_data or not isinstance(json_data, dict):
        return JSONResponse(
            {"ok": False, "error": "'json_data' must be a JSON object"},
            status_code=400,
        )

    result = await _translation(request).translate_json(json_data, target, source)
    return JSONResponse(
        {
            "ok": result.get("success", False),
            "translated_json": result.get("translated_json"),
            "source_language": source,
            "target_language": target,
            "keys_translated": result.get("keys_translated", 0),
            "keys_skipped": result.get("keys_skipped", 0),
            "error": result.get("error", ""),
        }
    )


@router.post("/translate/stream")
async def translate_json_stream(request: Request):
    """Translate JSON with real-time SSE progress (0-100%).

    Yields ``data: {"progress": N, "done": D, "total": T}`` events
    followed by a final ``data: {"complete": true, ...}`` event.
    """
    from fastapi.responses import StreamingResponse

    from opsportal.services.translation_proxy import TranslationProgress

    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError):
        return JSONResponse({"ok": False, "error": "Invalid JSON body"}, status_code=400)

    json_data = body.get("json_data")
    target = body.get("target_language", "pl")
    source = body.get("source_language", "en")

    if not json_data or not isinstance(json_data, dict):
        return JSONResponse(
            {"ok": False, "error": "'json_data' must be a JSON object"},
            status_code=400,
        )

    proxy = _translation(request)
    progress_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    loop = asyncio.get_event_loop()

    def _on_progress(prog: TranslationProgress) -> None:
        loop.call_soon_threadsafe(
            progress_queue.put_nowait,
            {"progress": prog.percent, "done": prog.done, "total": prog.total},
        )

    async def _generate():
        # Start translation in background
        task = asyncio.create_task(
            proxy.translate_json_with_progress(json_data, target, source, _on_progress)
        )
        last_pct = -1

        while not task.done():
            try:
                evt = await asyncio.wait_for(progress_queue.get(), timeout=0.3)
                if evt["progress"] != last_pct:
                    last_pct = evt["progress"]
                    yield f"data: {json.dumps(evt)}\n\n"
            except TimeoutError:
                pass

        # Drain remaining progress events
        while not progress_queue.empty():
            evt = progress_queue.get_nowait()
            if evt["progress"] != last_pct:
                last_pct = evt["progress"]
                yield f"data: {json.dumps(evt)}\n\n"

        result = task.result()
        final = {
            "complete": True,
            "ok": result.get("success", False),
            "translated_json": result.get("translated_json"),
            "keys_translated": result.get("keys_translated", 0),
            "keys_skipped": result.get("keys_skipped", 0),
            "error": result.get("error", ""),
        }
        yield f"data: {json.dumps(final)}\n\n"

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


# ---------------------------------------------------------------------------
# Composite dashboard endpoint
# ---------------------------------------------------------------------------


@router.get("/dashboard")
async def dashboard_data(request: Request):
    """All widget data in a single call for initial dashboard load."""
    _require_ops_overview(request)
    if request.query_params.get("refresh"):
        gateway = request.app.state.integration_gateway
        gateway.clear_cache()
    calendar_task = _calendar(request).get_milestones()
    tags_task = _tags(request).get_tags_summary()

    results = await asyncio.gather(calendar_task, tags_task, return_exceptions=True)

    calendar_data = (
        results[0]
        if not isinstance(results[0], BaseException)
        else {"ok": False, "error": str(results[0]), "milestones": []}
    )
    tags_data = (
        results[1]
        if not isinstance(results[1], BaseException)
        else {"ok": False, "error": str(results[1]), "tags": []}
    )

    # Build capabilities map
    registry = request.app.state.registry
    capabilities: dict[str, list[str]] = {}
    for adapter in registry.all():
        caps = adapter.integration_capabilities
        if caps:
            capabilities[adapter.slug] = sorted(c.value for c in caps)

    # Widget definitions
    widgets = [
        {
            "id": w.id,
            "title": w.title,
            "icon": w.icon,
            "size": w.size.value,
            "refresh_seconds": w.refresh_seconds,
            "available": any(w.capability in a.integration_capabilities for a in registry.all()),
        }
        for w in _widget_registry(request).all()
    ]

    return JSONResponse(
        {
            "calendar": calendar_data,
            "tags": tags_data,
            "capabilities": capabilities,
            "widgets": widgets,
        }
    )


# ---------------------------------------------------------------------------
# Capabilities discovery
# ---------------------------------------------------------------------------


@router.get("/capabilities")
async def capabilities_list(request: Request):
    """List all tools and their declared integration capabilities."""
    registry = request.app.state.registry
    tools: list[dict[str, Any]] = []

    for adapter in registry.all():
        caps = adapter.integration_capabilities
        endpoints = adapter.get_integration_endpoints()
        tools.append(
            {
                "slug": adapter.slug,
                "name": adapter.display_name,
                "capabilities": sorted(c.value for c in caps),
                "endpoints": [
                    {
                        "capability": ep.capability.value,
                        "method": ep.method,
                        "path": ep.path,
                        "description": ep.description,
                    }
                    for ep in endpoints
                ],
            }
        )

    return JSONResponse({"ok": True, "tools": tools})
