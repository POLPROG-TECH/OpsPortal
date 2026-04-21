"""Tags aggregator - extracts tag summaries from connected tool analysis results."""

from __future__ import annotations

from typing import Any

from opsportal.adapters.base import IntegrationCapability
from opsportal.services.integration_gateway import IntegrationGateway


class TagsAggregator:
    """Fetches latest Git tags per repository from tools with tags capability."""

    def __init__(self, gateway: IntegrationGateway) -> None:
        self._gw = gateway

    async def get_tags_summary(self) -> dict[str, Any]:
        """Return latest tag per repo from all tools declaring tags capability."""
        responses = await self._gw.fetch_from_capable(
            IntegrationCapability.TAGS,
            "/api/analyze/results",
        )

        all_tags: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        needs_analysis: list[str] = []

        for resp in responses:
            if resp.success and resp.data and resp.data.get("ok"):
                for analysis in resp.data.get("analyses", []):
                    tag_data: dict[str, Any] = {
                        "repo_name": analysis.get("name", ""),
                        "layer": analysis.get("layer", ""),
                        "branch_exists": analysis.get("branch_exists", False),
                        "source": resp.source_tool,
                    }
                    latest_tag = analysis.get("latest_tag")
                    if latest_tag and isinstance(latest_tag, dict):
                        tag_data["tag_name"] = latest_tag.get("name")
                        tag_data["committed_date"] = latest_tag.get("committed_date")
                        tag_data["message"] = latest_tag.get("message")
                    else:
                        tag_data["tag_name"] = None
                        tag_data["committed_date"] = None
                        tag_data["message"] = None
                    all_tags.append(tag_data)
            elif resp.success and resp.data and not resp.data.get("ok"):
                needs_analysis.append(resp.source_tool)
            elif not resp.success:
                if "404" in (resp.error or ""):
                    needs_analysis.append(resp.source_tool)
                else:
                    errors.append({"tool": resp.source_tool, "error": resp.error})

        # Fallback: fetch repos from config for tools that need analysis
        for tool_slug in needs_analysis:
            config_resp = await self._gw.fetch(tool_slug, "/api/config")
            repos: list[dict[str, Any]] = []
            if config_resp.success and config_resp.data:
                cfg = config_resp.data
                repos = (cfg.get("persisted") or cfg).get("repositories", [])
                for r in repos:
                    all_tags.append(
                        {
                            "repo_name": r.get("name", ""),
                            "layer": r.get("layer", ""),
                            "branch_exists": False,
                            "source": tool_slug,
                            "tag_name": None,
                            "committed_date": None,
                            "message": None,
                            "pending_analysis": True,
                        }
                    )
            if not repos:
                errors.append({"tool": tool_slug, "error": "no_data"})

        # Sort: repos with tags first (by date descending), then without
        all_tags.sort(
            key=lambda t: (
                t["committed_date"] is None,
                t.get("committed_date") or "",
            ),
            reverse=False,
        )
        tagged = [t for t in all_tags if t["tag_name"]]
        tagged.sort(key=lambda t: t.get("committed_date") or "", reverse=True)
        untagged = [t for t in all_tags if not t["tag_name"]]
        sorted_tags = tagged + untagged

        return {
            "ok": len(all_tags) > 0 or len(errors) == 0,
            "tags": sorted_tags,
            "total": len(all_tags),
            "tagged": len(tagged),
            "errors": errors,
        }
