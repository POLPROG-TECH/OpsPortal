"""Calendar aggregator - fetches release calendar data from connected tools."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from opsportal.adapters.base import IntegrationCapability
from opsportal.services.integration_gateway import IntegrationGateway


@dataclass(frozen=True, slots=True)
class CalendarMilestone:
    """A single release milestone from a connected tool."""

    phase: str
    date: str
    label: str
    days_remaining: int
    source_tool: str = ""


class CalendarAggregator:
    """Fetches upcoming milestones from tools with calendar capability."""

    def __init__(self, gateway: IntegrationGateway) -> None:
        self._gw = gateway

    async def get_milestones(self) -> dict[str, Any]:
        """Return upcoming milestones aggregated from all capable tools."""
        responses = await self._gw.fetch_from_capable(
            IntegrationCapability.RELEASE_CALENDAR,
            "/api/release-calendar/milestones",
        )

        all_milestones: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []

        for resp in responses:
            if resp.success and resp.data:
                for m in resp.data.get("milestones", []):
                    all_milestones.append(
                        {
                            "phase": m.get("phase", ""),
                            "date": m.get("date", ""),
                            "label": m.get("label", ""),
                            "days_remaining": m.get("days_remaining", 0),
                            "source": resp.source_tool,
                        }
                    )
            elif not resp.success:
                errors.append({"tool": resp.source_tool, "error": resp.error})

        all_milestones.sort(key=lambda m: m["days_remaining"])

        return {
            "ok": len(all_milestones) > 0 or len(errors) == 0,
            "milestones": all_milestones,
            "errors": errors,
        }

    async def get_full_calendar(self) -> dict[str, Any]:
        """Return the full calendar data from the first capable tool."""
        responses = await self._gw.fetch_from_capable(
            IntegrationCapability.RELEASE_CALENDAR,
            "/api/release-calendar",
        )

        for resp in responses:
            if resp.success and resp.data:
                return {
                    "ok": True,
                    "source": resp.source_tool,
                    "release_calendar": resp.data.get("release_calendar", {}),
                }

        errors = [{"tool": r.source_tool, "error": r.error} for r in responses if not r.success]
        return {"ok": False, "release_calendar": {}, "errors": errors}
