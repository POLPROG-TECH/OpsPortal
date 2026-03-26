"""Plugin loader — discovers and loads tool adapters from entry points.

Third-party packages can register adapters by declaring an entry point
in the ``opsportal.adapters`` group:

    [project.entry-points."opsportal.adapters"]
    my_tool = "my_package.adapter:MyToolAdapter"

The adapter class must inherit from ``opsportal.adapters.base.ToolAdapter``.
"""

from __future__ import annotations

from typing import Any

from opsportal.adapters.base import ToolAdapter
from opsportal.core.errors import get_logger

logger = get_logger("services.plugin_loader")

ENTRY_POINT_GROUP = "opsportal.adapters"


class PluginLoader:
    """Discovers adapter plugins from Python entry points."""

    def __init__(self) -> None:
        self._discovered: dict[str, type[ToolAdapter]] = {}

    def discover(self) -> dict[str, type[ToolAdapter]]:
        """Scan installed packages for adapter entry points."""
        try:
            from importlib.metadata import entry_points
        except ImportError:
            logger.debug("importlib.metadata not available, skipping plugin discovery")
            return {}

        eps = entry_points()

        if hasattr(eps, "select"):
            group = eps.select(group=ENTRY_POINT_GROUP)
        elif isinstance(eps, dict):
            group = eps.get(ENTRY_POINT_GROUP, [])
        else:
            group = [ep for ep in eps if ep.group == ENTRY_POINT_GROUP]

        for ep in group:
            try:
                adapter_cls = ep.load()
                if not (isinstance(adapter_cls, type) and issubclass(adapter_cls, ToolAdapter)):
                    logger.warning("Plugin %r does not extend ToolAdapter, skipping", ep.name)
                    continue
                self._discovered[ep.name] = adapter_cls
                logger.info("Discovered plugin adapter: %s → %s", ep.name, adapter_cls.__name__)
            except Exception:
                logger.exception("Failed to load plugin %r", ep.name)

        return dict(self._discovered)

    def create_adapter(
        self, slug: str, *, process_manager: Any, **kwargs: Any
    ) -> ToolAdapter | None:
        """Instantiate a discovered plugin adapter."""
        cls = self._discovered.get(slug)
        if not cls:
            return None
        try:
            adapter = cls(process_manager, **kwargs)
            logger.info("Created plugin adapter: %s", slug)
            return adapter
        except Exception:
            logger.exception("Failed to create plugin adapter %s", slug)
            return None

    @property
    def available_plugins(self) -> list[str]:
        return list(self._discovered.keys())
