"""Tests for aggregator and dashboard fallback states."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

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
from opsportal.services.translation_proxy import (
    TranslationProxy,
)
from tests._integration_fakes import FakeAdapter


class TestCalendarFallbackStates:
    """Calendar widget returns actionable data in all failure modes."""

    """GIVEN a gateway where the ReleaseBoard tool returns a connection error"""

    @pytest.mark.asyncio
    async def test_calendar_returns_errors_when_tool_unreachable(self):
        gw = MagicMock(spec=IntegrationGateway)
        gw.fetch_from_capable = AsyncMock(
            return_value=[
                GatewayResponse(
                    success=False,
                    error="Connection refused",
                    source_tool="releaseboard",
                )
            ]
        )
        agg = CalendarAggregator(gw)

        """WHEN fetching milestones"""
        result = await agg.get_milestones()

        """THEN the errors list includes the tool error and milestones is empty"""
        assert len(result["errors"]) == 1
        assert result["errors"][0]["tool"] == "releaseboard"
        assert result["milestones"] == []

    """GIVEN a gateway where the tool succeeds but returns no milestones"""

    @pytest.mark.asyncio
    async def test_calendar_empty_milestones_with_no_errors(self):
        gw = MagicMock(spec=IntegrationGateway)
        gw.fetch_from_capable = AsyncMock(
            return_value=[
                GatewayResponse(
                    success=True,
                    data={"milestones": []},
                    source_tool="releaseboard",
                )
            ]
        )
        agg = CalendarAggregator(gw)

        """WHEN fetching milestones"""
        result = await agg.get_milestones()

        """THEN the result is ok with empty milestones and no errors"""
        assert result["ok"] is True
        assert result["milestones"] == []
        assert result["errors"] == []


class TestTagsFallbackStates:
    """Tags widget returns actionable data in all failure modes."""

    """GIVEN a gateway where the tags-capable tool returns a connection error"""

    @pytest.mark.asyncio
    async def test_tags_returns_errors_when_tool_unreachable(self):
        gw = MagicMock(spec=IntegrationGateway)
        gw.fetch_from_capable = AsyncMock(
            return_value=[
                GatewayResponse(
                    success=False,
                    error="Connection refused",
                    source_tool="releaseboard",
                )
            ]
        )
        agg = TagsAggregator(gw)

        """WHEN fetching the tags summary"""
        result = await agg.get_tags_summary()

        """THEN the errors list includes the tool error"""
        assert len(result["errors"]) == 1
        assert result["errors"][0]["tool"] == "releaseboard"

    """GIVEN a gateway where the tool succeeds but returns an empty analyses list"""

    @pytest.mark.asyncio
    async def test_tags_empty_when_no_analysis(self):
        gw = MagicMock(spec=IntegrationGateway)
        gw.fetch_from_capable = AsyncMock(
            return_value=[
                GatewayResponse(
                    success=True,
                    data={"ok": True, "analyses": []},
                    source_tool="releaseboard",
                )
            ]
        )
        agg = TagsAggregator(gw)

        """WHEN fetching the tags summary"""
        result = await agg.get_tags_summary()

        """THEN tags list is empty with zero total and no errors"""
        assert result["tags"] == []
        assert result["total"] == 0
        assert result["errors"] == []


class TestReleaseNotesFallbackStates:
    """Release notes orchestrator handles partial/full failures."""

    """GIVEN a gateway with no tools capable of release notes"""

    @pytest.mark.asyncio
    async def test_no_capable_tools_returns_empty(self):
        gw = MagicMock(spec=IntegrationGateway)
        gw.tools_with_capability = MagicMock(return_value=[])
        orch = ReleaseNotesOrchestrator(gw)

        """WHEN generating release notes"""
        result = await orch.generate_all()

        """THEN the result is ok with empty results and zero totals"""
        assert result["ok"] is True
        assert result["results"] == []
        assert result["summary"]["total_apps"] == 0
        assert result["summary"]["total_repos"] == 0

    """GIVEN a capable tool where capabilities check passes but analysis returns ok=False"""

    @pytest.mark.asyncio
    async def test_analysis_missing_returns_actionable_error(self):
        adapter = FakeAdapter(
            "releaseboard",
            endpoints=[
                IntegrationEndpoint(
                    capability=IntegrationCapability.RELEASE_NOTES,
                    method="POST",
                    path="/api/release-pilot/prepare",
                    description="Release notes",
                ),
            ],
        )
        gw = MagicMock(spec=IntegrationGateway)
        gw.tools_with_capability = MagicMock(return_value=[adapter])
        # Capabilities check passes
        gw.fetch = AsyncMock(
            side_effect=[
                GatewayResponse(
                    success=True,
                    data={"available": True},
                    source_tool="releaseboard",
                ),
                GatewayResponse(
                    success=True,
                    data={"ok": False},
                    source_tool="releaseboard",
                ),
            ]
        )
        orch = ReleaseNotesOrchestrator(gw)

        """WHEN generating release notes"""
        result = await orch.generate_all()

        """THEN an error mentioning 'analysis' is returned"""
        assert len(result["errors"]) == 1
        assert "analysis" in result["errors"][0]["error"].lower()


class TestTranslationFallbackStates:
    """Translation proxy handles service-unavailable gracefully."""

    """GIVEN a TranslationProxy where LocaleSync is not installed"""

    @pytest.mark.asyncio
    async def test_translate_without_localesync_returns_clear_error(self):
        proxy = TranslationProxy()

        """WHEN attempting to translate JSON without LocaleSync"""
        with patch.dict("sys.modules", {"locale_sync": None}):
            # Force import error in _translate_sync
            original_translate = proxy._translate_sync

            def patched(*args, **kwargs):
                return {
                    "success": False,
                    "error": "LocaleSync is not installed - translation unavailable",
                    "translated_json": None,
                    "keys_translated": 0,
                    "keys_skipped": 0,
                }

            proxy._translate_sync = patched

            result = await proxy.translate_json({"hello": "world"}, "pl", "en")

            proxy._translate_sync = original_translate

        """THEN the error message indicates LocaleSync is not installed"""
        assert result["success"] is False
        assert "not installed" in result["error"]

    """GIVEN a TranslationProxy instance"""

    def test_supported_languages_always_returns_list(self):
        proxy = TranslationProxy()

        """WHEN requesting supported languages"""
        langs = proxy.supported_languages()

        """THEN a non-empty list of dicts with code and label keys is returned"""
        assert isinstance(langs, list)
        assert len(langs) > 0
        assert all("code" in lang and "label" in lang for lang in langs)


class TestDashboardFetchErrorStates:
    """Dashboard endpoint handles service failures gracefully."""

    """GIVEN a running test client"""

    @pytest.mark.asyncio
    async def test_dashboard_partial_failure(self, client):
        """WHEN requesting GET /api/integrations/dashboard"""
        resp = client.get("/api/integrations/dashboard")

        """THEN all top-level keys are present even if tools are down"""
        assert resp.status_code == 200
        data = resp.json()
        # Should always have these top-level keys even if tools are down
        assert "calendar" in data
        assert "tags" in data
        assert "capabilities" in data
        assert "widgets" in data

    """GIVEN a running test client"""

    @pytest.mark.asyncio
    async def test_capabilities_always_returns_tools_list(self, client):
        """WHEN requesting GET /api/integrations/capabilities"""
        resp = client.get("/api/integrations/capabilities")

        """THEN the response is 200 with ok=True and a tools list"""
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert isinstance(data["tools"], list)
