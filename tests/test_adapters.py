"""Tests for the adapter system and registry."""

from __future__ import annotations

import pytest

from opsportal.adapters.base import IntegrationMode, ToolCapability, ToolStatus
from opsportal.adapters.registry import AdapterRegistry
from tests.conftest import StubAdapter

"""GIVEN an empty registry and a stub adapter"""


def test_registry_register_and_get() -> None:
    reg = AdapterRegistry()
    adapter = StubAdapter("test-tool")

    """WHEN registering the adapter"""
    reg.register(adapter)

    """THEN the adapter is retrievable by slug"""
    assert "test-tool" in reg
    assert reg.get("test-tool") is adapter
    assert len(reg) == 1


"""GIVEN a registry with one adapter already registered"""


def test_registry_duplicate_raises() -> None:
    reg = AdapterRegistry()
    reg.register(StubAdapter("dup"))

    """WHEN registering another adapter with the same slug"""
    """THEN a ValueError is raised"""
    with pytest.raises(ValueError, match="Duplicate"):
        reg.register(StubAdapter("dup"))


"""GIVEN an empty registry"""


def test_registry_get_unknown_returns_none() -> None:
    reg = AdapterRegistry()

    """WHEN looking up a non-existent slug"""

    """THEN looking up a non-existent slug returns None"""
    assert reg.get("nope") is None


"""GIVEN a registry with one adapter"""


def test_registry_all() -> None:
    reg = AdapterRegistry()
    reg.register(StubAdapter("a"))

    """WHEN registering a second adapter"""
    reg.register(StubAdapter("b"))

    """THEN all() returns both adapters"""
    assert len(reg.all()) == 2


"""GIVEN an available stub adapter"""


@pytest.mark.asyncio
async def test_stub_adapter_status() -> None:
    adapter = StubAdapter("t", available=True)

    """WHEN checking status"""

    """THEN status is AVAILABLE"""
    assert await adapter.get_status() == ToolStatus.AVAILABLE

    """GIVEN an unavailable stub adapter"""
    adapter2 = StubAdapter("t2", available=False)

    """WHEN checking status"""

    """THEN status is ERROR"""
    assert await adapter2.get_status() == ToolStatus.ERROR


"""GIVEN an available stub adapter"""


@pytest.mark.asyncio
async def test_stub_adapter_health() -> None:
    adapter = StubAdapter("t", available=True)

    """WHEN running a health check"""
    h = await adapter.health_check()

    """THEN healthy is True"""
    assert h.healthy is True

    """GIVEN an unavailable stub adapter"""
    adapter2 = StubAdapter("t2", available=False)
    h2 = await adapter2.health_check()

    """THEN healthy is False"""
    assert h2.healthy is False


"""GIVEN a stub adapter"""


def test_stub_adapter_properties() -> None:
    adapter = StubAdapter("my-tool")

    """WHEN reading adapter properties"""

    """THEN its properties match expected defaults"""
    assert adapter.slug == "my-tool"
    assert adapter.display_name == "Stub Tool"
    assert adapter.integration_mode == IntegrationMode.CLI_TASK
    assert ToolCapability.CLI_COMMANDS in adapter.capabilities
