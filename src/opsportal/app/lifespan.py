"""Application lifespan — startup and shutdown hooks."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from opsportal.core.errors import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from fastapi import FastAPI

logger = get_logger("app.lifespan")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage portal startup and shutdown."""
    logger.info("OpsPortal starting up")

    # Start all adapters
    registry = app.state.registry
    for adapter in registry.all():
        try:
            await adapter.startup()
            logger.info("Adapter %s started", adapter.slug)
        except Exception:
            logger.exception("Failed to start adapter %s", adapter.slug)

    yield

    # Shutdown
    logger.info("OpsPortal shutting down")
    for adapter in registry.all():
        try:
            await adapter.shutdown()
        except Exception:
            logger.exception("Error shutting down adapter %s", adapter.slug)

    # Shutdown process manager
    if hasattr(app.state, "process_manager"):
        await app.state.process_manager.shutdown_all()
