"""Release notes orchestrator - cross-app generation via connected tools.

Fans out release-notes generation requests to all connected tools that
declare the RELEASE_NOTES capability, aggregates results, and handles
partial failures gracefully.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from opsportal.adapters.base import IntegrationCapability
from opsportal.core.errors import get_logger
from opsportal.services.integration_gateway import IntegrationGateway

logger = get_logger("services.release_notes_orchestrator")

# Max concurrent release-note generation tasks per tool
_MAX_CONCURRENT_PER_TOOL = 3


class ReleaseNotesOrchestrator:
    """Orchestrates release notes generation across connected applications."""

    def __init__(self, gateway: IntegrationGateway) -> None:
        self._gw = gateway

    async def generate_all(
        self,
        *,
        audience: str = "changelog",
        output_format: str = "markdown",
        language: str = "en",
        app_filter: list[str] | None = None,
    ) -> dict[str, Any]:
        """Generate release notes from all tools with release-notes capability.

        Steps per tool:
        1. Check release-pilot capabilities
        2. Get analysis results (for repo list)
        3. For each repo with a branch: get context → prepare release notes
        4. Aggregate all results
        """
        results: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []

        capable_tools = self._gw.tools_with_capability(IntegrationCapability.RELEASE_NOTES)

        for adapter in capable_tools:
            slug = adapter.slug
            if app_filter and slug not in app_filter:
                continue

            tool_result = await self._generate_for_tool(
                slug,
                audience=audience,
                output_format=output_format,
                language=language,
            )
            if tool_result.get("error"):
                errors.append({"app": slug, "error": tool_result["error"]})
            else:
                results.append(tool_result)

        total_repos = sum(len(r.get("repos", [])) for r in results)
        succeeded = sum(1 for r in results for repo in r.get("repos", []) if repo.get("success"))

        return {
            "ok": True,
            "results": results,
            "errors": errors,
            "summary": {
                "total_apps": len(results),
                "total_repos": total_repos,
                "succeeded": succeeded,
                "failed": total_repos - succeeded,
            },
        }

    async def generate_all_streaming(
        self,
        *,
        audience: str = "changelog",
        output_format: str = "markdown",
        language: str = "en",
        app_filter: list[str] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Async generator yielding progress events per repo."""
        capable_tools = self._gw.tools_with_capability(
            IntegrationCapability.RELEASE_NOTES,
        )
        filtered = [a for a in capable_tools if not app_filter or a.slug in app_filter]

        total_repos = 0
        tool_analyses: dict[str, list[dict[str, Any]]] = {}
        for adapter in filtered:
            slug = adapter.slug
            caps_resp = await self._gw.fetch(
                slug,
                "/api/release-pilot/capabilities",
            )
            if not caps_resp.success or not (caps_resp.data or {}).get(
                "available",
            ):
                yield {
                    "type": "error",
                    "app": slug,
                    "error": f"Cannot reach {slug}",
                }
                continue
            analysis_resp = await self._gw.fetch(
                slug,
                "/api/analyze/results",
            )
            if not analysis_resp.success or not (analysis_resp.data or {}).get("ok"):
                yield {
                    "type": "error",
                    "app": slug,
                    "error": "No analysis results - run analysis first",
                }
                continue
            analyses = (analysis_resp.data or {}).get("analyses", [])
            repos = [a for a in analyses if a.get("branch_exists")]
            tool_analyses[slug] = repos
            total_repos += len(repos)

        if total_repos == 0:
            empty: dict[str, Any] = {
                "type": "complete",
                "results": [],
                "errors": [],
                "summary": {
                    "total_apps": 0,
                    "total_repos": 0,
                    "succeeded": 0,
                    "failed": 0,
                },
            }
            yield empty
            return

        yield {
            "type": "start",
            "total_repos": total_repos,
            "total_apps": len(tool_analyses),
        }

        processed = 0
        all_results: list[dict[str, Any]] = []
        for slug, repos in tool_analyses.items():
            tool_repos: list[dict[str, Any]] = []
            for analysis in repos:
                repo_name = analysis.get("name", "unknown")
                pct = int(processed / total_repos * 100)
                yield {
                    "type": "progress",
                    "processed": processed,
                    "total": total_repos,
                    "progress": pct,
                    "current_repo": repo_name,
                    "current_app": slug,
                }
                result = await self._generate_one_repo(
                    slug,
                    analysis,
                    audience=audience,
                    output_format=output_format,
                    language=language,
                )
                tool_repos.append(result)
                processed += 1
                pct = int(processed / total_repos * 100)
                yield {
                    "type": "progress",
                    "processed": processed,
                    "total": total_repos,
                    "progress": pct,
                    "current_repo": repo_name,
                    "current_app": slug,
                }
            all_results.append(
                {"app": slug, "repos": tool_repos, "error": ""},
            )

        succeeded = sum(
            1 for r in all_results for repo in r.get("repos", []) if repo.get("success")
        )
        yield {
            "type": "complete",
            "results": all_results,
            "errors": [],
            "summary": {
                "total_apps": len(all_results),
                "total_repos": total_repos,
                "succeeded": succeeded,
                "failed": total_repos - succeeded,
            },
        }

    async def _generate_for_tool(
        self,
        tool_slug: str,
        *,
        audience: str,
        output_format: str,
        language: str,
    ) -> dict[str, Any]:
        """Generate release notes for all repos in a single tool."""
        # 1. Check capabilities
        caps_resp = await self._gw.fetch(tool_slug, "/api/release-pilot/capabilities")
        if not caps_resp.success:
            return {"app": tool_slug, "error": f"Cannot reach {tool_slug}", "repos": []}
        if not (caps_resp.data or {}).get("available"):
            return {
                "app": tool_slug,
                "error": "ReleasePilot integration not available",
                "repos": [],
            }

        # 2. Get analysis results for repo list
        analysis_resp = await self._gw.fetch(tool_slug, "/api/analyze/results")
        if not analysis_resp.success or not (analysis_resp.data or {}).get("ok"):
            return {
                "app": tool_slug,
                "error": "No analysis results - run analysis first",
                "repos": [],
            }

        analyses = (analysis_resp.data or {}).get("analyses", [])
        repos_with_branch = [a for a in analyses if a.get("branch_exists")]

        if not repos_with_branch:
            return {"app": tool_slug, "repos": [], "error": ""}

        # 3. Generate for each repo (with concurrency limit)
        sem = asyncio.Semaphore(_MAX_CONCURRENT_PER_TOOL)

        async def _gen_one(analysis: dict[str, Any]) -> dict[str, Any]:
            async with sem:
                return await self._generate_one_repo(
                    tool_slug,
                    analysis,
                    audience=audience,
                    output_format=output_format,
                    language=language,
                )

        repo_results = await asyncio.gather(
            *[_gen_one(a) for a in repos_with_branch],
            return_exceptions=True,
        )

        processed: list[dict[str, Any]] = []
        for r in repo_results:
            if isinstance(r, Exception):
                processed.append(
                    {
                        "repo_name": "unknown",
                        "success": False,
                        "error_message": str(r),
                    }
                )
            else:
                processed.append(r)

        return {"app": tool_slug, "repos": processed, "error": ""}

    async def _generate_one_repo(
        self,
        tool_slug: str,
        analysis: dict[str, Any],
        *,
        audience: str,
        output_format: str,
        language: str,
    ) -> dict[str, Any]:
        """Generate release notes for one repository."""
        repo_name = analysis.get("name", "unknown")

        # Get repo context
        ctx_resp = await self._gw.fetch(tool_slug, f"/api/release-pilot/repo-context/{repo_name}")
        if not ctx_resp.success:
            return {
                "repo_name": repo_name,
                "success": False,
                "error_message": f"Could not get repo context: {ctx_resp.error}",
            }

        ctx = (ctx_resp.data or {}).get("context", {})
        branch = (
            ctx.get("actual_branch")
            or ctx.get("expected_branch")
            or analysis.get("actual_branch", "")
        )

        prep_body = {
            "repo_name": repo_name,
            "repo_url": ctx.get("url", ""),
            "release_title": f"{repo_name} Release Notes",
            "release_version": "",
            "audience": audience,
            "output_format": output_format,
            "language": language,
            "branch": branch,
        }

        gen_resp = await self._gw.fetch(
            tool_slug,
            "/api/release-pilot/prepare",
            method="POST",
            json_body=prep_body,
            timeout=60.0,  # generation can be slow
        )

        if gen_resp.success and gen_resp.data:
            return {
                "repo_name": repo_name,
                "success": gen_resp.data.get("success", False),
                "content": gen_resp.data.get("content", ""),
                "total_changes": gen_resp.data.get("total_changes", 0),
                "error_message": gen_resp.data.get("error_message", ""),
            }

        return {
            "repo_name": repo_name,
            "success": False,
            "error_message": gen_resp.error or "Generation failed",
        }
