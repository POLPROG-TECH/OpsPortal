"""Application lifespan — startup and shutdown hooks."""

from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from opsportal.core.errors import get_logger
from opsportal.services.notification_service import NotificationLevel

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from fastapi import FastAPI

logger = get_logger("app.lifespan")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage portal startup and shutdown."""
    logger.info("OpsPortal starting up")
    settings = app.state.settings

    # Start all adapters
    registry = app.state.registry
    for adapter in registry.all():
        try:
            await adapter.startup()
            logger.info("Adapter %s started", adapter.slug)
        except Exception:
            logger.exception("Failed to start adapter %s", adapter.slug)

    # Start background tasks
    bg_tasks: list[asyncio.Task] = []

    # -- Manifest watcher (#8: hot-reload) --
    if settings.manifest_watch:
        from opsportal.services.manifest_watcher import ManifestWatcher

        watcher = ManifestWatcher(
            settings.manifest_path, poll_interval=settings.manifest_watch_interval
        )
        watcher.set_reload_callback(lambda: _reload_manifest(app))
        await watcher.start()
        app.state.manifest_watcher = watcher

    # -- Scheduler (#19) --
    if settings.scheduler_enabled:
        scheduler = app.state.scheduler
        scheduler.set_action_callback(
            lambda slug, action, params: _run_scheduled_action(app, slug, action, params),
        )
        await scheduler.start()

    # -- Periodic health checks with uptime tracking (#16) & metrics (#14) --
    bg_tasks.append(asyncio.create_task(_periodic_health_loop(app)))

    # -- Artifact auto-cleanup (#18) --
    if settings.artifact_cleanup_enabled:
        bg_tasks.append(asyncio.create_task(_artifact_cleanup_loop(app)))

    # -- Cache cleanup --
    bg_tasks.append(asyncio.create_task(_cache_cleanup_loop(app)))

    yield

    # Shutdown
    logger.info("OpsPortal shutting down")

    # Cancel background tasks
    for task in bg_tasks:
        task.cancel()
    await asyncio.gather(*bg_tasks, return_exceptions=True)

    # Stop scheduler
    if hasattr(app.state, "scheduler"):
        await app.state.scheduler.stop()

    # Stop manifest watcher
    if hasattr(app.state, "manifest_watcher"):
        await app.state.manifest_watcher.stop()

    for adapter in registry.all():
        try:
            await adapter.shutdown()
        except Exception:
            logger.exception("Error shutting down adapter %s", adapter.slug)

    # Shutdown process manager
    if hasattr(app.state, "process_manager"):
        await app.state.process_manager.shutdown_all()


async def _periodic_health_loop(app: FastAPI) -> None:
    """Periodically check tool health, update uptime tracker and metrics."""
    try:
        interval = app.state.settings.health_check_interval
        while True:
            await asyncio.sleep(interval)
            registry = app.state.registry
            for adapter in registry.all():
                await _check_adapter_health(app, adapter)

            await app.state.metrics_collector.collect(app.state.process_manager)

            alert_mgr = getattr(app.state, "alert_manager", None)
            if alert_mgr:
                await alert_mgr.evaluate(
                    app.state.metrics_collector,
                    app.state.notification_service,
                )
    except asyncio.CancelledError:
        pass


async def _check_adapter_health(app: FastAPI, adapter) -> None:
    """Run a single health check and record results."""
    slug = adapter.slug
    uptime_tracker = app.state.uptime_tracker
    metrics = app.state.metrics_collector
    start = time.monotonic()

    try:
        result = await adapter.health_check()
        latency = (time.monotonic() - start) * 1000
        uptime_tracker.record(slug, result.healthy, latency)
        metrics.record_health_check(slug, result.healthy, latency)

        if not result.healthy:
            await app.state.notification_service.notify(
                level=NotificationLevel.WARNING,
                title=f"Health check failed: {adapter.display_name}",
                message=result.message,
                tool_slug=slug,
                event_type="health_fail",
            )
    except Exception as exc:
        latency = (time.monotonic() - start) * 1000
        uptime_tracker.record(slug, False, latency)
        metrics.record_health_check(slug, False, latency)
        logger.debug("Health check error for %s: %s", slug, exc)


async def _artifact_cleanup_loop(app: FastAPI) -> None:
    """Periodically clean up old artifacts (#18)."""
    try:
        settings = app.state.settings
        max_age = settings.artifact_max_age_days * 86400
        interval = settings.artifact_cleanup_interval
        while True:
            await asyncio.sleep(interval)
            am = app.state.artifact_manager
            registry = app.state.registry
            total = 0
            for adapter in registry.all():
                total += am.cleanup(adapter.slug, max_age_seconds=max_age)
            if total:
                logger.info("Artifact cleanup: removed %d old files", total)
    except asyncio.CancelledError:
        pass


async def _cache_cleanup_loop(app: FastAPI) -> None:
    """Periodically evict expired cache entries."""
    try:
        while True:
            await asyncio.sleep(60)
            app.state.cache.cleanup()
    except asyncio.CancelledError:
        pass


async def _run_scheduled_action(app: FastAPI, slug: str, action: str, params: dict) -> None:
    """Execute a scheduled action via the adapter."""
    registry = app.state.registry
    adapter = registry.get(slug)
    if not adapter:
        logger.warning("Scheduled action skipped: adapter %r not found", slug)
        return
    result = await adapter.run_action(action, params)
    app.state.log_store.add(slug, action, f"Scheduled: {'ok' if result.success else 'failed'}")
    app.state.audit_log.record(
        category="scheduler",
        action=action,
        tool_slug=slug,
        details={"success": result.success, "scheduled": True},
    )


def _reload_manifest(app: FastAPI) -> None:
    """Reload manifest and update adapter registry (hot-reload callback)."""
    from opsportal.config.manifest import load_manifest

    settings = app.state.settings
    try:
        new_manifest = load_manifest(
            settings.manifest_path,
            settings.tools_base_dir,
            tools_work_dir=settings.tools_work_dir,
        )
        app.state.manifest = new_manifest
        app.state.log_store.add("portal", "manifest_reload", "Manifest reloaded successfully")
        app.state.audit_log.record(
            category="config",
            action="manifest_reload",
            details={"tools": [t.slug for t in new_manifest.enabled_tools]},
        )
        logger.info("Manifest reloaded: %d tools", len(new_manifest.enabled_tools))
    except Exception:
        logger.exception("Failed to reload manifest")
