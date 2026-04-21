"""Tests for integration services: widget registry, gateway, translation proxy."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from opsportal.adapters.base import (
    EnsureReadyResult,
    IntegrationCapability,
    IntegrationEndpoint,
    ToolAdapter,
    ToolStatus,
)
from opsportal.services.integration_gateway import (
    GatewayResponse,
    IntegrationGateway,
)
from opsportal.services.translation_proxy import (
    TranslationProxy,
    _flatten_json,
    _unflatten_json,
)
from opsportal.services.widget_registry import (
    WidgetDefinition,
    WidgetRegistry,
    WidgetSize,
    create_default_registry,
)
from tests._integration_fakes import FakeAdapter, FakeRegistry

# ---------------------------------------------------------------------------
# Widget registry tests
# ---------------------------------------------------------------------------


class TestWidgetRegistry:
    """Tests for the widget registry."""

    """GIVEN the default widget registry factory"""

    def test_create_default_registry(self):
        """WHEN creating a new registry"""
        reg = create_default_registry()

        """THEN it contains 4 built-in widgets with expected IDs"""
        assert len(reg) == 4
        ids = {w.id for w in reg.all()}
        assert ids == {"release-calendar", "tags-overview", "release-notes", "translation"}

    """GIVEN an empty widget registry and a widget definition"""

    def test_register_and_get(self):
        reg = WidgetRegistry()
        w = WidgetDefinition(
            id="test-w",
            title="Test",
            icon="box",
            capability=IntegrationCapability.RELEASE_CALENDAR,
        )

        """WHEN registering the widget"""
        reg.register(w)

        """THEN it can be retrieved by ID and the registry has one entry"""
        assert reg.get("test-w") is w
        assert len(reg) == 1

    """GIVEN a registry with a widget registered under ID 'dup'"""

    def test_replace_widget(self):
        reg = WidgetRegistry()
        w1 = WidgetDefinition(
            id="dup",
            title="First",
            icon="box",
            capability=IntegrationCapability.TAGS,
        )
        w2 = WidgetDefinition(
            id="dup",
            title="Second",
            icon="tag",
            capability=IntegrationCapability.TAGS,
        )
        reg.register(w1)

        """WHEN registering another widget with the same ID"""
        reg.register(w2)

        """THEN the registry still has one entry and it is the second widget"""
        assert len(reg) == 1
        assert reg.get("dup").title == "Second"

    """GIVEN a registry with two widgets registered in reverse order"""

    def test_all_sorted_by_order(self):
        reg = WidgetRegistry()
        reg.register(
            WidgetDefinition(
                id="b",
                title="B",
                icon="b",
                capability=IntegrationCapability.TAGS,
                order=20,
            )
        )
        reg.register(
            WidgetDefinition(
                id="a",
                title="A",
                icon="a",
                capability=IntegrationCapability.RELEASE_CALENDAR,
                order=10,
            )
        )

        """WHEN retrieving all widgets"""

        """THEN they are sorted by order field ascending"""
        assert [w.id for w in reg.all()] == ["a", "b"]

    """GIVEN the default widget registry"""

    def test_for_capability(self):
        reg = create_default_registry()

        """WHEN filtering widgets by RELEASE_CALENDAR capability"""
        cal = reg.for_capability(IntegrationCapability.RELEASE_CALENDAR)

        """THEN exactly one matching widget is returned"""
        assert len(cal) == 1
        assert cal[0].id == "release-calendar"

    """GIVEN the WidgetSize enum"""

    def test_widget_size_values(self):
        """WHEN accessing enum member values"""

        """THEN small, medium, and large have the expected string values"""
        assert WidgetSize.SMALL.value == "small"
        assert WidgetSize.MEDIUM.value == "medium"
        assert WidgetSize.LARGE.value == "large"


# ---------------------------------------------------------------------------
# JSON flatten/unflatten tests
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# JSON flatten/unflatten tests
# ---------------------------------------------------------------------------


class TestJsonFlatten:
    """Tests for the JSON flattening helper."""

    """GIVEN a flat JSON object with no nesting"""

    def test_flat_object(self):
        data = {"a": "1", "b": "2"}

        """WHEN flattening the object"""
        flat = _flatten_json(data)

        """THEN the output is identical to the input"""
        assert flat == {"a": "1", "b": "2"}

    """GIVEN a deeply nested JSON object"""

    def test_nested_object(self):
        data = {"a": {"b": {"c": "deep"}}}

        """WHEN flattening the object"""
        flat = _flatten_json(data)

        """THEN nested keys are joined with dots"""
        assert flat == {"a.b.c": "deep"}

    """GIVEN a flat JSON object with mixed value types"""

    def test_mixed_types(self):
        data = {"str": "hello", "num": 42, "bool": True, "null": None}

        """WHEN flattening the object"""
        flat = _flatten_json(data)

        """THEN non-dict values are preserved as-is"""
        assert flat == {"str": "hello", "num": 42, "bool": True, "null": None}

    """GIVEN a flat dictionary with no dotted keys"""

    def test_unflatten_simple(self):
        flat = {"a": "1", "b": "2"}

        """WHEN unflattening the dictionary"""
        result = _unflatten_json(flat)

        """THEN the output is identical to the input"""
        assert result == {"a": "1", "b": "2"}

    """GIVEN a flat dictionary with dotted keys representing nesting"""

    def test_unflatten_nested(self):
        flat = {"a.b.c": "deep", "a.b.d": "another", "x": "top"}

        """WHEN unflattening the dictionary"""
        result = _unflatten_json(flat)

        """THEN nested structure is reconstructed from dotted keys"""
        assert result == {"a": {"b": {"c": "deep", "d": "another"}}, "x": "top"}

    """GIVEN a nested JSON structure with multiple levels"""

    def test_roundtrip(self):
        data = {
            "greeting": "Hello",
            "nested": {
                "level1": {
                    "level2": "deep value",
                },
                "sibling": "side",
            },
            "top": 42,
        }

        """WHEN flattening then unflattening the data"""
        result = _unflatten_json(_flatten_json(data))

        """THEN the original structure is preserved"""
        assert result == data

    """GIVEN an empty dictionary"""

    def test_empty_dict(self):
        """WHEN flattening and unflattening it"""

        """THEN both operations return an empty dictionary"""
        assert _flatten_json({}) == {}
        assert _unflatten_json({}) == {}


# ---------------------------------------------------------------------------
# Integration gateway tests
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Integration gateway tests
# ---------------------------------------------------------------------------


class TestIntegrationGateway:
    """Tests for the integration gateway."""

    def _make_gateway(self, adapters: list[ToolAdapter] | None = None):
        registry = FakeRegistry(adapters or [])
        return IntegrationGateway(registry)

    """GIVEN a gateway with no registered adapters"""

    @pytest.mark.asyncio
    async def test_fetch_unknown_tool(self):
        gw = self._make_gateway()

        """WHEN fetching from a nonexistent tool slug"""
        resp = await gw.fetch("nonexistent", "/api/test")

        """THEN the response indicates failure with 'not registered' error"""
        assert not resp.success
        assert "not registered" in resp.error

    """GIVEN a gateway with one adapter exposing RELEASE_CALENDAR capability"""

    @pytest.mark.asyncio
    async def test_tools_with_capability(self):
        ep = IntegrationEndpoint(
            capability=IntegrationCapability.RELEASE_CALENDAR,
            path="/api/release-calendar/milestones",
            method="GET",
        )
        a = FakeAdapter("rb", endpoints=[ep])
        gw = self._make_gateway([a])

        """WHEN querying tools with RELEASE_CALENDAR capability"""
        found = gw.tools_with_capability(IntegrationCapability.RELEASE_CALENDAR)

        """THEN exactly one matching tool is returned"""
        assert len(found) == 1
        assert found[0].slug == "rb"

    """GIVEN a gateway with one adapter that has no integration endpoints"""

    @pytest.mark.asyncio
    async def test_tools_with_capability_empty(self):
        a = FakeAdapter("plain")
        gw = self._make_gateway([a])

        """WHEN querying tools with TAGS capability"""
        found = gw.tools_with_capability(IntegrationCapability.TAGS)

        """THEN no tools are returned"""
        assert found == []

    """GIVEN a gateway with a tool adapter in ERROR status and no web URL"""

    @pytest.mark.asyncio
    async def test_fetch_tool_unavailable(self):
        a = FakeAdapter("down", status=ToolStatus.ERROR, web_url=None)
        a.ensure_ready = AsyncMock(return_value=EnsureReadyResult(ready=False, web_url=None))
        a.get_web_url = MagicMock(return_value=None)
        gw = self._make_gateway([a])

        """WHEN fetching from that unavailable tool"""
        resp = await gw.fetch("down", "/api/test")

        """THEN the response indicates failure with 'not available' error"""
        assert not resp.success
        assert "not available" in resp.error

    """GIVEN an IntegrationGateway constructed with a specific registry"""

    @pytest.mark.asyncio
    async def test_registry_property(self):
        reg = FakeRegistry([])
        gw = IntegrationGateway(reg)

        """WHEN accessing the gateway's registry property"""

        """THEN it returns the same registry instance"""
        assert gw.registry is reg


# ---------------------------------------------------------------------------
# Calendar aggregator tests
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Translation proxy tests
# ---------------------------------------------------------------------------


class TestTranslationProxy:
    """Tests for the translation proxy service."""

    """GIVEN a TranslationProxy instance"""

    def test_supported_languages(self):
        proxy = TranslationProxy()

        """WHEN requesting supported languages"""
        langs = proxy.supported_languages()

        """THEN more than 10 languages are returned including en, pl, and de"""
        assert len(langs) > 10
        codes = {lang["code"] for lang in langs}
        assert "en" in codes
        assert "pl" in codes
        assert "de" in codes

    """GIVEN a TranslationProxy with a mocked translator"""

    @pytest.mark.asyncio
    async def test_translate_preserves_structure(self):
        proxy = TranslationProxy()

        # Patch translator to uppercase strings instead of actually translating
        def fake_translate(text, src, tgt):
            return text.upper()

        """WHEN translating a nested JSON structure"""
        with patch(
            "opsportal.services.translation_proxy.TranslationProxy._translate_sync"
        ) as mock:
            mock.return_value = {
                "success": True,
                "translated_json": {
                    "greeting": "HELLO",
                    "nested": {"message": "WORLD"},
                    "count": 42,
                },
                "keys_translated": 2,
                "keys_skipped": 1,
                "error": "",
            }

            result = await proxy.translate_json(
                {"greeting": "hello", "nested": {"message": "world"}, "count": 42},
                "pl",
            )

        """THEN the JSON keys and nesting are preserved with non-string values intact"""
        assert result["success"] is True
        tj = result["translated_json"]
        assert "greeting" in tj
        assert "nested" in tj
        assert "message" in tj["nested"]
        assert tj["count"] == 42

    """GIVEN a TranslationProxy with a mocked translator and empty input"""

    @pytest.mark.asyncio
    async def test_translate_empty_json(self):
        proxy = TranslationProxy()

        """WHEN translating an empty JSON object"""
        with patch(
            "opsportal.services.translation_proxy.TranslationProxy._translate_sync"
        ) as mock:
            mock.return_value = {
                "success": True,
                "translated_json": {},
                "keys_translated": 0,
                "keys_skipped": 0,
                "error": "",
            }

            result = await proxy.translate_json({}, "pl")

        """THEN translation succeeds with an empty result"""
        assert result["success"] is True
        assert result["translated_json"] == {}


# ---------------------------------------------------------------------------
# Integration capability on adapters
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Gateway caching + retry tests
# ---------------------------------------------------------------------------


class TestGatewayCaching:
    """Tests for integration gateway caching behaviour."""

    """GIVEN a GatewayResponse constructed with cached=True"""

    def test_cached_field_in_response(self):
        resp = GatewayResponse(success=True, data={"test": 1}, cached=True)

        """WHEN accessing the cached field"""

        """THEN it returns True"""
        assert resp.cached is True

    """GIVEN a gateway with a pre-populated in-memory cache"""

    @pytest.mark.asyncio
    async def test_cache_hit(self):

        class FakeCache:
            def __init__(self):
                self._store = {}

            def get(self, key):
                return self._store.get(key)

            def set(self, key, value, ttl=None):
                self._store[key] = value

        cache = FakeCache()
        from opsportal.services.integration_gateway import IntegrationGateway

        gw = IntegrationGateway(FakeRegistry([]), cache=cache, cache_ttl=60)

        # Prime cache manually
        cache.set("gw:tool:/api/test", {"cached_data": True})

        """WHEN fetching a path that exists in the cache"""
        # Register a tool but it won't be called since cache hits
        resp = await gw.fetch("tool", "/api/test")

        """THEN the cached response is returned with cached=True"""
        # Tool not registered, but cache should hit first
        assert resp.success is True
        assert resp.cached is True
        assert resp.data == {"cached_data": True}

    """GIVEN a gateway with an empty cache and no registered tools"""

    @pytest.mark.asyncio
    async def test_cache_miss_falls_through(self):

        class EmptyCache:
            def get(self, key):
                return None

            def set(self, key, value, ttl=None):
                pass

        from opsportal.services.integration_gateway import IntegrationGateway

        gw = IntegrationGateway(FakeRegistry([]), cache=EmptyCache())

        """WHEN fetching a nonexistent tool path"""
        resp = await gw.fetch("nonexistent", "/api/test")

        """THEN the fetch falls through to normal lookup and fails with 'not registered'"""
        assert not resp.success
        assert "not registered" in resp.error
