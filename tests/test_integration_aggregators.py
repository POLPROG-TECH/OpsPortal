"""Tests for cross-tool aggregators: calendar, tags, release notes."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from opsportal.adapters.base import (
    IntegrationCapability,
    IntegrationEndpoint,
)
from opsportal.services.calendar_aggregator import CalendarAggregator
from opsportal.services.integration_gateway import (
    GatewayResponse,
    IntegrationGateway,
)
from opsportal.services.release_notes_orchestrator import ReleaseNotesOrchestrator
from opsportal.services.tags_aggregator import TagsAggregator
from tests._integration_fakes import FakeAdapter


class TestCalendarAggregator:
    """Tests for the calendar aggregator service."""

    @staticmethod
    def _mock_gateway(milestone_data: list[dict]) -> IntegrationGateway:
        gw = MagicMock(spec=IntegrationGateway)
        gw.fetch_from_capable = AsyncMock(
            return_value=[
                GatewayResponse(
                    success=True,
                    data={"milestones": milestone_data},
                    source_tool="releaseboard",
                )
            ]
        )
        return gw

    """GIVEN a gateway returning two milestones from a capable tool"""

    @pytest.mark.asyncio
    async def test_milestones_success(self):
        gw = self._mock_gateway(
            [
                {
                    "phase": "dev_freeze",
                    "date": "2025-01-20",
                    "label": "Dev Freeze",
                    "days_remaining": 5,
                },
                {
                    "phase": "release",
                    "date": "2025-01-25",
                    "label": "Release",
                    "days_remaining": 10,
                },
            ]
        )
        agg = CalendarAggregator(gw)

        """WHEN fetching milestones"""
        result = await agg.get_milestones()

        """THEN milestones are returned sorted by days_remaining with source"""
        assert result["ok"] is True
        assert len(result["milestones"]) == 2
        m0 = result["milestones"][0]["days_remaining"]
        m1 = result["milestones"][1]["days_remaining"]
        assert m0 <= m1
        assert result["milestones"][0]["source"] == "releaseboard"

    """GIVEN a gateway where one tool succeeds and another fails"""

    @pytest.mark.asyncio
    async def test_milestones_partial_failure(self):
        gw = MagicMock(spec=IntegrationGateway)
        gw.fetch_from_capable = AsyncMock(
            return_value=[
                GatewayResponse(
                    success=True,
                    data={
                        "milestones": [
                            {
                                "phase": "release",
                                "date": "2025-01-25",
                                "label": "Release",
                                "days_remaining": 3,
                            },
                        ]
                    },
                    source_tool="tool-a",
                ),
                GatewayResponse(success=False, error="Connection refused", source_tool="tool-b"),
            ]
        )
        agg = CalendarAggregator(gw)

        """WHEN fetching milestones"""
        result = await agg.get_milestones()

        """THEN successful milestones are returned alongside errors from failed tools"""
        assert result["ok"] is True
        assert len(result["milestones"]) == 1
        assert len(result["errors"]) == 1
        assert result["errors"][0]["tool"] == "tool-b"

    """GIVEN a gateway where every capable tool fails"""

    @pytest.mark.asyncio
    async def test_milestones_all_fail(self):
        gw = MagicMock(spec=IntegrationGateway)
        gw.fetch_from_capable = AsyncMock(
            return_value=[
                GatewayResponse(success=False, error="timeout", source_tool="tool-x"),
            ]
        )
        agg = CalendarAggregator(gw)

        """WHEN fetching milestones"""
        result = await agg.get_milestones()

        """THEN the result is not ok and milestones list is empty"""
        assert result["ok"] is False
        assert len(result["milestones"]) == 0

    """GIVEN a gateway that returns no capable tool responses"""

    @pytest.mark.asyncio
    async def test_milestones_empty(self):
        gw = MagicMock(spec=IntegrationGateway)
        gw.fetch_from_capable = AsyncMock(return_value=[])
        agg = CalendarAggregator(gw)

        """WHEN fetching milestones"""
        result = await agg.get_milestones()

        """THEN the result is ok with an empty milestones list"""
        assert result["ok"] is True
        assert result["milestones"] == []

    """GIVEN a gateway returning a successful full calendar response"""

    @pytest.mark.asyncio
    async def test_full_calendar_success(self):
        gw = MagicMock(spec=IntegrationGateway)
        gw.fetch_from_capable = AsyncMock(
            return_value=[
                GatewayResponse(
                    success=True,
                    data={"release_calendar": {"sprint": "S1"}},
                    source_tool="rb",
                )
            ]
        )
        agg = CalendarAggregator(gw)

        """WHEN fetching the full calendar"""
        result = await agg.get_full_calendar()

        """THEN the result is ok and includes the source tool"""
        assert result["ok"] is True
        assert result["source"] == "rb"

    """GIVEN a gateway where the capable tool returns a failure"""

    @pytest.mark.asyncio
    async def test_full_calendar_failure(self):
        gw = MagicMock(spec=IntegrationGateway)
        gw.fetch_from_capable = AsyncMock(
            return_value=[
                GatewayResponse(success=False, error="down", source_tool="rb"),
            ]
        )
        agg = CalendarAggregator(gw)

        """WHEN fetching the full calendar"""
        result = await agg.get_full_calendar()

        """THEN the result indicates failure"""
        assert result["ok"] is False


# ---------------------------------------------------------------------------
# Tags aggregator tests
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Tags aggregator tests
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Tags aggregator tests
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Tags aggregator tests
# ---------------------------------------------------------------------------


class TestTagsAggregator:
    """Tests for the tags aggregator service."""

    """GIVEN a gateway returning tag analyses with one tagged and one untagged repo"""

    @pytest.mark.asyncio
    async def test_tags_with_data(self):
        gw = MagicMock(spec=IntegrationGateway)
        gw.fetch_from_capable = AsyncMock(
            return_value=[
                GatewayResponse(
                    success=True,
                    data={
                        "ok": True,
                        "analyses": [
                            {
                                "name": "repo-a",
                                "layer": "backend",
                                "branch_exists": True,
                                "latest_tag": {
                                    "name": "v1.2.0",
                                    "committed_date": "2025-01-15",
                                    "message": "Release v1.2.0",
                                },
                            },
                            {
                                "name": "repo-b",
                                "layer": "frontend",
                                "branch_exists": True,
                                "latest_tag": None,
                            },
                        ],
                    },
                    source_tool="releaseboard",
                )
            ]
        )
        agg = TagsAggregator(gw)

        """WHEN fetching the tags summary"""
        result = await agg.get_tags_summary()

        """THEN the summary is ok with tagged repos sorted first"""
        assert result["ok"] is True
        assert result["total"] == 2
        assert result["tagged"] == 1
        # Tagged repos should come first
        assert result["tags"][0]["tag_name"] == "v1.2.0"
        assert result["tags"][1]["tag_name"] is None

    """GIVEN a gateway where the tags-capable tool returns an error"""

    @pytest.mark.asyncio
    async def test_tags_all_fail(self):
        gw = MagicMock(spec=IntegrationGateway)
        gw.fetch_from_capable = AsyncMock(
            return_value=[
                GatewayResponse(success=False, error="err", source_tool="x"),
            ]
        )
        agg = TagsAggregator(gw)

        """WHEN fetching the tags summary"""
        result = await agg.get_tags_summary()

        """THEN the result is not ok with zero total tags"""
        assert result["ok"] is False
        assert result["total"] == 0

    """GIVEN a gateway that returns no capable tool responses"""

    @pytest.mark.asyncio
    async def test_tags_empty(self):
        gw = MagicMock(spec=IntegrationGateway)
        gw.fetch_from_capable = AsyncMock(return_value=[])
        agg = TagsAggregator(gw)

        """WHEN fetching the tags summary"""
        result = await agg.get_tags_summary()

        """THEN the result is ok with an empty tags list"""
        assert result["ok"] is True
        assert result["tags"] == []


# ---------------------------------------------------------------------------
# Release notes orchestrator tests
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Release notes orchestrator tests
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Release notes orchestrator tests
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Release notes orchestrator tests
# ---------------------------------------------------------------------------


class TestReleaseNotesOrchestrator:
    """Tests for the release notes orchestrator."""

    @staticmethod
    def _make_gw(
        caps_available: bool = True,
        analyses: list[dict] | None = None,
        gen_success: bool = True,
    ) -> IntegrationGateway:
        gw = MagicMock(spec=IntegrationGateway)
        ep = IntegrationEndpoint(
            capability=IntegrationCapability.RELEASE_NOTES,
            path="/api/release-pilot/prepare",
            method="POST",
        )
        adapter = FakeAdapter("rb", endpoints=[ep])
        gw.tools_with_capability = MagicMock(return_value=[adapter])

        if analyses is None:
            analyses = [
                {"name": "repo-x", "branch_exists": True, "actual_branch": "release/1.0"},
            ]

        def side_effect(slug, path, **kwargs):
            if "capabilities" in path:
                return GatewayResponse(
                    success=True,
                    data={"available": caps_available},
                    source_tool=slug,
                )
            if "results" in path:
                return GatewayResponse(
                    success=True,
                    data={"ok": True, "analyses": analyses},
                    source_tool=slug,
                )
            if "repo-context" in path:
                return GatewayResponse(
                    success=True,
                    data={
                        "context": {
                            "url": "https://example.com/repo",
                            "actual_branch": "release/1.0",
                        },
                    },
                    source_tool=slug,
                )
            if "prepare" in path:
                if gen_success:
                    return GatewayResponse(
                        success=True,
                        data={"success": True, "content": "# Release Notes", "total_changes": 5},
                        source_tool=slug,
                    )
                return GatewayResponse(success=False, error="Generation failed", source_tool=slug)
            return GatewayResponse(success=False, error="Unknown path", source_tool=slug)

        gw.fetch = AsyncMock(side_effect=side_effect)
        return gw

    """GIVEN a gateway with a capable tool that returns analysis and generation data"""

    @pytest.mark.asyncio
    async def test_generate_success(self):
        gw = self._make_gw()
        orch = ReleaseNotesOrchestrator(gw)

        """WHEN generating release notes for all repos"""
        result = await orch.generate_all()

        """THEN generation succeeds with one repo and its content"""
        assert result["ok"] is True
        assert result["summary"]["total_repos"] == 1
        assert result["summary"]["succeeded"] == 1
        assert result["results"][0]["repos"][0]["content"] == "# Release Notes"

    """GIVEN a gateway where the tool reports capabilities as unavailable"""

    @pytest.mark.asyncio
    async def test_generate_caps_unavailable(self):
        gw = self._make_gw(caps_available=False)
        orch = ReleaseNotesOrchestrator(gw)

        """WHEN generating release notes"""
        result = await orch.generate_all()

        """THEN errors include a 'not available' message"""
        assert len(result["errors"]) == 1
        assert "not available" in result["errors"][0]["error"]

    """GIVEN a gateway returning an empty analyses list"""

    @pytest.mark.asyncio
    async def test_generate_no_repos(self):
        gw = self._make_gw(analyses=[])
        orch = ReleaseNotesOrchestrator(gw)

        """WHEN generating release notes"""
        result = await orch.generate_all()

        """THEN generation succeeds with zero repos processed"""
        assert result["ok"] is True
        assert result["summary"]["total_repos"] == 0

    """GIVEN a gateway with one repo and an app filter that matches nothing"""

    @pytest.mark.asyncio
    async def test_generate_with_app_filter(self):
        gw = self._make_gw()
        orch = ReleaseNotesOrchestrator(gw)

        """WHEN generating release notes with a non-matching app filter"""
        result = await orch.generate_all(app_filter=["not-this-one"])

        """THEN no repos are processed"""
        assert result["summary"]["total_repos"] == 0

    """GIVEN a gateway where the prepare endpoint fails"""

    @pytest.mark.asyncio
    async def test_generation_failure(self):
        gw = self._make_gw(gen_success=False)
        orch = ReleaseNotesOrchestrator(gw)

        """WHEN generating release notes"""
        result = await orch.generate_all()

        """THEN zero repos succeed and one fails"""
        assert result["summary"]["succeeded"] == 0
        assert result["summary"]["failed"] == 1
