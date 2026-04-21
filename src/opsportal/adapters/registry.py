"""Adapter registry - central lookup for all registered tool adapters."""

from __future__ import annotations

from opsportal.adapters.base import ToolAdapter
from opsportal.core.errors import get_logger

logger = get_logger("adapters.registry")


class AdapterRegistry:
    """Thread-safe registry mapping tool slugs to their adapters."""

    def __init__(self) -> None:
        self._adapters: dict[str, ToolAdapter] = {}

    def register(self, adapter: ToolAdapter) -> None:
        slug = adapter.slug
        if slug in self._adapters:
            msg = f"Duplicate adapter slug: {slug!r}"
            raise ValueError(msg)
        self._adapters[slug] = adapter
        logger.info("Registered adapter: %s (%s)", slug, adapter.integration_mode.value)

    def unregister(self, slug: str) -> ToolAdapter | None:
        """Remove and return an adapter from the registry."""
        adapter = self._adapters.pop(slug, None)
        if adapter:
            logger.info("Unregistered adapter: %s", slug)
        return adapter

    def get(self, slug: str) -> ToolAdapter | None:
        return self._adapters.get(slug)

    def all(self) -> list[ToolAdapter]:
        return list(self._adapters.values())

    def enabled(self) -> list[ToolAdapter]:
        return list(self._adapters.values())

    def slugs(self) -> list[str]:
        return list(self._adapters.keys())

    def __len__(self) -> int:
        return len(self._adapters)

    def __contains__(self, slug: str) -> bool:
        return slug in self._adapters
