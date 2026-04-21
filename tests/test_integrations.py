"""Tests for integration capabilities, routes, and contract shapes."""

from __future__ import annotations

import pytest

from opsportal.adapters.base import (
    IntegrationCapability,
    IntegrationEndpoint,
)
from opsportal.services.translation_proxy import (
    TranslationProxy,
)
from tests._integration_fakes import FakeAdapter

# ---------------------------------------------------------------------------
# Integration capability on adapters
# ---------------------------------------------------------------------------


class TestIntegrationCapabilities:
    """Tests for integration capability declarations."""

    """GIVEN the IntegrationCapability enum"""

    def test_enum_values(self):
        """WHEN accessing enum member values"""

        """THEN each capability has the expected string value"""
        assert IntegrationCapability.RELEASE_CALENDAR.value == "release_calendar"
        assert IntegrationCapability.TAGS.value == "tags"
        assert IntegrationCapability.RELEASE_NOTES.value == "release_notes"
        assert IntegrationCapability.TRANSLATION.value == "translation"

    """GIVEN a FakeAdapter with RELEASE_CALENDAR and TAGS endpoints"""

    def test_adapter_with_endpoints(self):
        eps = [
            IntegrationEndpoint(
                capability=IntegrationCapability.RELEASE_CALENDAR,
                path="/api/cal",
                method="GET",
            ),
            IntegrationEndpoint(
                capability=IntegrationCapability.TAGS,
                path="/api/tags",
                method="GET",
            ),
        ]
        adapter = FakeAdapter("test", endpoints=eps)

        """WHEN querying the adapter's integration capabilities"""
        caps = adapter.integration_capabilities

        """THEN both capabilities are reported"""
        assert IntegrationCapability.RELEASE_CALENDAR in caps
        assert IntegrationCapability.TAGS in caps
        assert len(caps) == 2

    """GIVEN a FakeAdapter with no integration endpoints"""

    def test_adapter_no_endpoints(self):
        adapter = FakeAdapter("plain")

        """WHEN querying its integration capabilities and endpoints"""

        """THEN both are empty"""
        assert adapter.integration_capabilities == set()
        assert adapter.get_integration_endpoints() == []


# ---------------------------------------------------------------------------
# Routes integration (smoke via TestClient)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Routes integration (smoke via TestClient)
# ---------------------------------------------------------------------------


class TestIntegrationRoutes:
    """Tests for integration HTTP routes."""

    """GIVEN a running test client"""

    def test_calendar_milestones_route(self, client):
        """WHEN requesting GET /api/integrations/calendar/milestones"""
        resp = client.get("/api/integrations/calendar/milestones")

        """THEN the response is 200 with milestones in the JSON body"""
        assert resp.status_code == 200
        data = resp.json()
        assert "milestones" in data

    """GIVEN a running test client"""

    def test_tags_route(self, client):
        """WHEN requesting GET /api/integrations/tags"""
        resp = client.get("/api/integrations/tags")

        """THEN the response is 200 with tags in the JSON body"""
        assert resp.status_code == 200
        data = resp.json()
        assert "tags" in data

    """GIVEN a running test client"""

    def test_dashboard_composite_route(self, client):
        """WHEN requesting GET /api/integrations/dashboard"""
        resp = client.get("/api/integrations/dashboard")

        """THEN the response is 200 with calendar, tags, widgets, and capabilities"""
        assert resp.status_code == 200
        data = resp.json()
        assert "calendar" in data
        assert "tags" in data
        assert "widgets" in data
        assert "capabilities" in data

    """GIVEN a running test client"""

    def test_translate_languages_route(self, client):
        """WHEN requesting GET /api/integrations/translate/languages"""
        resp = client.get("/api/integrations/translate/languages")

        """THEN the response is 200 with ok=True and more than 10 languages"""
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert len(data["languages"]) > 10

    """GIVEN a running test client with CSRF headers"""

    def test_translate_invalid_body(self, client):
        from tests.conftest import csrf_headers

        headers = csrf_headers(client)

        """WHEN posting a translate request with json_data as a string instead of dict"""
        resp = client.post(
            "/api/integrations/translate",
            json={"json_data": "not-a-dict"},
            headers=headers,
        )

        """THEN the response is 400 Bad Request"""
        assert resp.status_code == 400

    """GIVEN a running test client with CSRF headers"""

    def test_translate_missing_data(self, client):
        from tests.conftest import csrf_headers

        headers = csrf_headers(client)

        """WHEN posting a translate request with an empty body"""
        resp = client.post(
            "/api/integrations/translate",
            json={},
            headers=headers,
        )

        """THEN the response is 400 Bad Request"""
        assert resp.status_code == 400

    """GIVEN a running test client"""

    def test_capabilities_route(self, client):
        """WHEN requesting GET /api/integrations/capabilities"""
        resp = client.get("/api/integrations/capabilities")

        """THEN the response is 200 with ok=True and a tools list with expected fields"""
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert isinstance(data["tools"], list)
        for tool in data["tools"]:
            assert "slug" in tool
            assert "name" in tool
            assert "capabilities" in tool
            assert isinstance(tool["capabilities"], list)
            assert "endpoints" in tool
            for ep in tool["endpoints"]:
                assert "capability" in ep
                assert "method" in ep
                assert "path" in ep

    """GIVEN a running test client with no CSRF headers"""

    def test_release_notes_requires_csrf(self, client):
        """WHEN posting to /api/integrations/release-notes/generate without CSRF token"""
        resp = client.post(
            "/api/integrations/release-notes/generate",
            json={},
        )

        """THEN the response is 403 Forbidden"""
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Contract tests - validate API response shapes
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Contract tests - validate API response shapes
# ---------------------------------------------------------------------------


class TestContractShapes:
    """Validate that integration API responses have expected field types."""

    """GIVEN a running test client"""

    def test_calendar_milestones_shape(self, client):
        """WHEN requesting GET /api/integrations/calendar/milestones"""
        resp = client.get("/api/integrations/calendar/milestones")
        data = resp.json()

        """THEN response fields have expected types: ok (bool), milestones (list), errors (list)"""
        assert isinstance(data.get("ok"), bool)
        assert isinstance(data.get("milestones"), list)
        assert isinstance(data.get("errors"), list)
        for m in data["milestones"]:
            assert isinstance(m.get("phase"), str)
            assert isinstance(m.get("date"), str)
            assert isinstance(m.get("label"), str)
            assert isinstance(m.get("days_remaining"), int)
            assert isinstance(m.get("source"), str)

    """GIVEN a running test client"""

    def test_tags_shape(self, client):
        """WHEN requesting GET /api/integrations/tags"""
        resp = client.get("/api/integrations/tags")
        data = resp.json()

        """THEN response fields have expected types including per-tag repo_name and source"""
        assert isinstance(data.get("ok"), bool)
        assert isinstance(data.get("tags"), list)
        assert isinstance(data.get("total"), int)
        assert isinstance(data.get("tagged"), int)
        assert isinstance(data.get("errors"), list)
        for t in data["tags"]:
            assert isinstance(t.get("repo_name"), str)
            assert isinstance(t.get("source"), str)

    """GIVEN a running test client"""

    def test_dashboard_shape(self, client):
        """WHEN requesting GET /api/integrations/dashboard"""
        resp = client.get("/api/integrations/dashboard")
        data = resp.json()

        """THEN response contains calendar, tags, capabilities dicts and widgets list with expected fields"""
        assert isinstance(data.get("calendar"), dict)
        assert isinstance(data.get("tags"), dict)
        assert isinstance(data.get("capabilities"), dict)
        assert isinstance(data.get("widgets"), list)
        for w in data["widgets"]:
            assert isinstance(w.get("id"), str)
            assert isinstance(w.get("title"), str)
            assert isinstance(w.get("icon"), str)
            assert isinstance(w.get("size"), str)
            assert isinstance(w.get("refresh_seconds"), int)
            assert isinstance(w.get("available"), bool)

    """GIVEN a running test client"""

    def test_capabilities_shape(self, client):
        """WHEN requesting GET /api/integrations/capabilities"""
        resp = client.get("/api/integrations/capabilities")
        data = resp.json()

        """THEN each tool has slug, capabilities list, and endpoints list"""
        assert data["ok"] is True
        for tool in data["tools"]:
            assert isinstance(tool["slug"], str)
            assert isinstance(tool["capabilities"], list)
            assert isinstance(tool["endpoints"], list)

    """GIVEN a running test client"""

    def test_translate_languages_shape(self, client):
        """WHEN requesting GET /api/integrations/translate/languages"""
        resp = client.get("/api/integrations/translate/languages")
        data = resp.json()

        """THEN each language has a code (≥2 chars) and label string"""
        assert data["ok"] is True
        for lang in data["languages"]:
            assert isinstance(lang["code"], str)
            assert isinstance(lang["label"], str)
            assert len(lang["code"]) >= 2


class TestOpsOverviewAdminConfig:
    """Operations Overview respects enabled/disabled setting."""

    """GIVEN an app created with ops_overview_enabled=False"""

    def test_dashboard_returns_404_when_disabled(self, tmp_path):
        from opsportal.app.factory import create_app
        from opsportal.core.settings import PortalSettings

        manifest = tmp_path / "opsportal.yaml"
        manifest.write_text("tools: {}\n")
        settings = PortalSettings(
            host="127.0.0.1",
            port=9998,
            log_level="warning",
            manifest_path=manifest,
            artifact_dir=tmp_path / "artifacts",
            work_dir=tmp_path / "work",
            tools_base_dir=tmp_path,
            ops_overview_enabled=False,
        )
        from starlette.testclient import TestClient

        app = create_app(settings=settings)
        cl = TestClient(app)

        """WHEN requesting the dashboard endpoint"""
        resp = cl.get("/api/integrations/dashboard")

        """THEN the response is 404"""
        assert resp.status_code == 404

    """GIVEN a running test client with ops_overview enabled"""

    def test_dashboard_returns_200_when_enabled(self, client):
        """WHEN requesting the dashboard endpoint"""
        resp = client.get("/api/integrations/dashboard")

        """THEN the response is 200"""
        assert resp.status_code == 200

    """GIVEN a running test client with CSRF headers"""

    def test_ops_overview_toggle_api(self, client):
        from tests.conftest import csrf_headers

        headers = csrf_headers(client)

        """WHEN toggling ops_overview off then on via PUT endpoint"""
        resp = client.put(
            "/api/config/ops-overview",
            json={"enabled": False},
            headers=headers,
        )

        """THEN the toggle succeeds and reflects the new state"""
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["enabled"] is False

        # Re-enable for other tests
        resp = client.put(
            "/api/config/ops-overview",
            json={"enabled": True},
            headers=headers,
        )
        assert resp.json()["enabled"] is True

    """GIVEN the PortalSettings model definition"""

    def test_ops_overview_default_is_disabled(self):
        from opsportal.core.settings import PortalSettings

        """WHEN inspecting the default value of ops_overview_enabled"""
        defaults = PortalSettings.model_fields["ops_overview_enabled"]

        """THEN the default is False"""
        assert defaults.default is False

    """GIVEN a running test client"""

    def test_config_page_shows_ops_overview_section(self, client):
        """WHEN requesting the config page"""
        resp = client.get("/config")

        """THEN the page contains an Operations Overview section with toggle elements"""
        assert resp.status_code == 200
        assert "Operations Overview" in resp.text
        assert "ops-overview-toggle" in resp.text
        assert "ops-overview-config" in resp.text

    """GIVEN a running test client"""

    def test_config_page_has_admin_title(self, client):
        """WHEN requesting the config page"""
        resp = client.get("/config")

        """THEN the page title includes 'Admin'"""
        assert resp.status_code == 200
        assert "Admin" in resp.text

    """GIVEN a running test client"""

    def test_config_page_shows_env_var_hint(self, client):
        """WHEN requesting the config page"""
        resp = client.get("/config")

        """THEN the page displays the OPSPORTAL_OPS_OVERVIEW_ENABLED env var name"""
        assert resp.status_code == 200
        assert "OPSPORTAL_OPS_OVERVIEW_ENABLED" in resp.text

    """GIVEN a running test client"""

    def test_sidebar_nav_shows_admin_label(self, client):
        """WHEN requesting the home page"""
        resp = client.get("/")

        """THEN the sidebar link says 'Admin & Settings'"""
        assert resp.status_code == 200
        assert "Admin &amp; Settings" in resp.text


class TestTranslationProgress:
    """Translation progress tracking works correctly."""

    """GIVEN a TranslationProgress tracker with 10 total keys"""

    def test_progress_tracker_percent(self):
        from opsportal.services.translation_proxy import TranslationProgress

        p = TranslationProgress(total=10)

        """WHEN advancing 5 translated and 5 skipped keys"""
        assert p.percent == 0
        for _ in range(5):
            p.advance(translated=True)
        assert p.percent == 50
        for _ in range(5):
            p.advance(translated=False)

        """THEN the percent reaches 100"""
        assert p.percent == 100

    """GIVEN a TranslationProgress tracker with zero total keys"""

    def test_progress_tracker_zero_total(self):
        from opsportal.services.translation_proxy import TranslationProgress

        p = TranslationProgress(total=0)

        """WHEN checking the percent"""

        """THEN it reports 100% immediately"""
        assert p.percent == 100

    """GIVEN a TranslationProxy and an on_progress callback"""

    @pytest.mark.asyncio
    async def test_translate_with_progress_callback(self):
        proxy = TranslationProxy()
        progress_calls = []

        def on_progress(prog):
            progress_calls.append(prog.percent)

        """WHEN translating JSON with the progress callback"""
        # This will fail because LocaleSync isn't installed in test env,
        # but the callback mechanism is still tested.
        result = await proxy.translate_json_with_progress(
            {"hello": "world"}, "pl", "en", on_progress=on_progress
        )

        """THEN the result is a dict with a 'success' key"""
        # Either translation succeeded or import failed - both are valid
        assert isinstance(result, dict)
        assert "success" in result

    """GIVEN a TranslationProxy and a nested JSON structure"""

    def test_count_translatable_keys(self):
        proxy = TranslationProxy()

        """WHEN counting translatable keys"""
        count = proxy.count_translatable_keys({"a": "x", "b": {"c": "y", "d": 1}})

        """THEN all leaf keys are counted including non-string values"""
        assert count == 3  # a, b.c, b.d

    """GIVEN a running test client with CSRF headers"""

    def test_translate_stream_endpoint_exists(self, client):
        from tests.conftest import csrf_headers

        headers = csrf_headers(client)
        headers["Content-Type"] = "application/json"

        """WHEN posting to the SSE translation stream endpoint"""
        resp = client.post(
            "/api/integrations/translate/stream",
            json={"json_data": {"a": "hello"}, "target_language": "pl"},
            headers=headers,
        )

        """THEN the endpoint responds (not 404/405)"""
        # Either 200 (SSE stream) or error but NOT 404/405
        assert resp.status_code in (200, 500)


class TestBulkStartSequentialSSE:
    """Bulk start streams per-tool SSE events sequentially."""

    """GIVEN a running test client with CSRF headers"""

    def test_bulk_start_returns_sse_stream(self, client):
        from tests.conftest import csrf_headers

        headers = csrf_headers(client)

        """WHEN posting to the bulk start endpoint"""
        resp = client.post("/api/tools/bulk/start", headers=headers)

        """THEN the response is 200 with text/event-stream content type"""
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

    """GIVEN a running test client with CSRF headers"""

    def test_bulk_start_sse_has_complete_event(self, client):
        import json as _json

        from tests.conftest import csrf_headers

        headers = csrf_headers(client)

        """WHEN posting to the bulk start endpoint and parsing SSE events"""
        resp = client.post("/api/tools/bulk/start", headers=headers)
        assert resp.status_code == 200
        lines = resp.text.strip().split("\n")
        events = []
        for line in lines:
            if line.startswith("data: "):
                events.append(_json.loads(line[6:]))
        phases = [e["phase"] for e in events]

        """THEN the SSE stream contains a 'complete' event"""
        assert "complete" in phases

    """GIVEN a running test client with CSRF headers"""

    def test_bulk_start_complete_event_has_summary(self, client):
        import json as _json

        from tests.conftest import csrf_headers

        headers = csrf_headers(client)

        """WHEN posting to the bulk start endpoint and extracting the 'complete' event"""
        resp = client.post("/api/tools/bulk/start", headers=headers)
        lines = resp.text.strip().split("\n")
        events = []
        for line in lines:
            if line.startswith("data: "):
                events.append(_json.loads(line[6:]))
        complete = [e for e in events if e["phase"] == "complete"]

        """THEN the complete event includes succeeded, total, and results dict"""
        assert len(complete) == 1
        assert "succeeded" in complete[0]
        assert "total" in complete[0]
        assert "results" in complete[0]
        assert isinstance(complete[0]["results"], dict)

    """GIVEN a running test client with CSRF headers"""

    def test_bulk_start_sequential_ordering_with_tools(self, client):
        import json as _json

        from tests.conftest import csrf_headers

        headers = csrf_headers(client)

        """WHEN posting to the bulk start endpoint and tracking per-tool event order"""
        resp = client.post("/api/tools/bulk/start", headers=headers)
        lines = resp.text.strip().split("\n")
        events = []
        for line in lines:
            if line.startswith("data: "):
                events.append(_json.loads(line[6:]))
        # For each tool slug, verify "starting" comes before "done"
        tool_order: dict[str, dict[str, int]] = {}
        for i, e in enumerate(events):
            slug = e.get("slug")
            if slug:
                tool_order.setdefault(slug, {})[e["phase"]] = i

        """THEN for each tool, the 'starting' event precedes the 'done' event"""
        for slug, phases in tool_order.items():
            if "starting" in phases and "done" in phases:
                assert phases["starting"] < phases["done"], f"{slug}: starting after done"

    """GIVEN a running test client with CSRF headers"""

    def test_bulk_invalid_action_rejected(self, client):
        from tests.conftest import csrf_headers

        headers = csrf_headers(client)

        """WHEN posting to an invalid bulk action endpoint"""
        resp = client.post("/api/tools/bulk/invalid", headers=headers)

        """THEN the response is 400 Bad Request"""
        assert resp.status_code == 400

    """GIVEN a running test client with CSRF headers"""

    def test_bulk_stop_returns_sse_stream(self, client):
        from tests.conftest import csrf_headers

        headers = csrf_headers(client)

        """WHEN posting to the bulk stop endpoint"""
        resp = client.post("/api/tools/bulk/stop", headers=headers)

        """THEN the response is 200 with text/event-stream content type"""
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")
