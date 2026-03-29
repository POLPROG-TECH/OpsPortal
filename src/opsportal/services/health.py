"""Health check service — aggregates health from all registered adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from opsportal.adapters.base import HealthResult
from opsportal.adapters.registry import AdapterRegistry
from opsportal.core.errors import get_logger

logger = get_logger("services.health")


@dataclass
class PortalHealth:
    overall: bool
    tools: dict[str, HealthResult] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "healthy": self.overall,
            "tools": {
                slug: {"healthy": r.healthy, "message": r.message, "details": r.details}
                for slug, r in self.tools.items()
            },
            "errors": self.errors,
        }


async def check_all_health(registry: AdapterRegistry) -> PortalHealth:
    """Run health checks across all registered adapters."""
    results: dict[str, HealthResult] = {}
    errors: list[str] = []

    for adapter in registry.all():
        slug = adapter.slug
        try:
            result = await adapter.health_check()
            results[slug] = result
        except (OSError, RuntimeError) as exc:
            logger.exception("Health check failed for %s", slug)
            results[slug] = HealthResult(healthy=False, message=str(exc))
            errors.append(f"{slug}: {exc}")

    overall = all(r.healthy for r in results.values()) if results else True
    return PortalHealth(overall=overall, tools=results, errors=errors)
