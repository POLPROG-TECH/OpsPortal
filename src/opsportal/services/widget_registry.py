"""Widget registry — generic dashboard widget system for OPSPortal.

Each widget declares its data source (integration capability), a refresh
interval, size hints, and a render function.  The dashboard composer uses
the registry to build the operations overview.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any

from opsportal.adapters.base import IntegrationCapability
from opsportal.core.errors import get_logger

logger = get_logger("services.widget_registry")


class WidgetSize(enum.StrEnum):
    SMALL = "small"  # 1/3 width
    MEDIUM = "medium"  # 1/2 width
    LARGE = "large"  # full width


@dataclass(frozen=True, slots=True)
class WidgetDefinition:
    """Describes a dashboard widget."""

    id: str
    title: str
    icon: str
    capability: IntegrationCapability
    size: WidgetSize = WidgetSize.MEDIUM
    refresh_seconds: int = 60
    order: int = 0
    description: str = ""


@dataclass(slots=True)
class WidgetData:
    """Runtime data for a rendered widget."""

    widget_id: str
    title: str
    icon: str
    size: str
    available: bool = True
    loading: bool = False
    error: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    source_tool: str = ""
    refresh_seconds: int = 60


class WidgetRegistry:
    """Central registry for dashboard widgets."""

    def __init__(self) -> None:
        self._widgets: dict[str, WidgetDefinition] = {}

    def register(self, widget: WidgetDefinition) -> None:
        if widget.id in self._widgets:
            logger.warning("Replacing widget %s", widget.id)
        self._widgets[widget.id] = widget
        logger.info("Registered widget: %s", widget.id)

    def get(self, widget_id: str) -> WidgetDefinition | None:
        return self._widgets.get(widget_id)

    def all(self) -> list[WidgetDefinition]:
        return sorted(self._widgets.values(), key=lambda w: w.order)

    def for_capability(self, cap: IntegrationCapability) -> list[WidgetDefinition]:
        return [w for w in self.all() if w.capability == cap]

    def __len__(self) -> int:
        return len(self._widgets)


# ---------------------------------------------------------------------------
# Built-in widget definitions
# ---------------------------------------------------------------------------

BUILTIN_WIDGETS = [
    WidgetDefinition(
        id="release-calendar",
        title="Release Calendar",
        icon="calendar",
        capability=IntegrationCapability.RELEASE_CALENDAR,
        size=WidgetSize.MEDIUM,
        refresh_seconds=60,
        order=10,
        description="Upcoming release milestones from connected tools",
    ),
    WidgetDefinition(
        id="tags-overview",
        title="Tags Overview",
        icon="tag",
        capability=IntegrationCapability.TAGS,
        size=WidgetSize.MEDIUM,
        refresh_seconds=120,
        order=20,
        description="Latest Git tags per repository",
    ),
    WidgetDefinition(
        id="release-notes",
        title="Release Notes",
        icon="file-text",
        capability=IntegrationCapability.RELEASE_NOTES,
        size=WidgetSize.LARGE,
        refresh_seconds=0,  # on-demand only
        order=30,
        description="Generate release notes across connected applications",
    ),
    WidgetDefinition(
        id="translation",
        title="JSON Translation",
        icon="globe",
        capability=IntegrationCapability.TRANSLATION,
        size=WidgetSize.LARGE,
        refresh_seconds=0,  # on-demand only
        order=40,
        description="Translate JSON files preserving structure",
    ),
]


def create_default_registry() -> WidgetRegistry:
    """Create a widget registry pre-loaded with built-in widgets."""
    registry = WidgetRegistry()
    for widget in BUILTIN_WIDGETS:
        registry.register(widget)
    return registry
