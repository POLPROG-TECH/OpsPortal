"""Tests for the adapter system and registry."""

from __future__ import annotations

import pytest

from opsportal.adapters.base import IntegrationMode, ToolCapability, ToolStatus
from opsportal.adapters.registry import AdapterRegistry
from tests.conftest import StubAdapter


def test_registry_register_and_get() -> None:
    """GIVEN the registry register and get scenario."""
    reg = AdapterRegistry()
    adapter = StubAdapter("test-tool")

    """WHEN executing."""
    reg.register(adapter)

    """THEN the result is correct."""
    assert "test-tool" in reg
    assert reg.get("test-tool") is adapter
    assert len(reg) == 1


def test_registry_duplicate_raises() -> None:
    """GIVEN the registry duplicate raises scenario."""

    """WHEN executing."""
    reg = AdapterRegistry()
    reg.register(StubAdapter("dup"))

    """THEN the result is correct."""
    with pytest.raises(ValueError, match="Duplicate"):
        reg.register(StubAdapter("dup"))


def test_registry_get_unknown_returns_none() -> None:
    """GIVEN the registry get unknown returns none scenario."""

    """WHEN executing."""
    reg = AdapterRegistry()

    """THEN the result is correct."""
    assert reg.get("nope") is None


def test_registry_all() -> None:
    """GIVEN the registry all scenario."""
    reg = AdapterRegistry()
    reg.register(StubAdapter("a"))

    """WHEN executing."""
    reg.register(StubAdapter("b"))

    """THEN the result is correct."""
    assert len(reg.all()) == 2


@pytest.mark.asyncio
async def test_stub_adapter_status() -> None:
    """GIVEN the stub adapter status scenario."""

    """WHEN executing."""
    adapter = StubAdapter("t", available=True)

    """THEN the result is correct."""
    assert await adapter.get_status() == ToolStatus.AVAILABLE

    adapter2 = StubAdapter("t2", available=False)
    assert await adapter2.get_status() == ToolStatus.ERROR


@pytest.mark.asyncio
async def test_stub_adapter_health() -> None:
    """GIVEN the stub adapter health scenario."""
    adapter = StubAdapter("t", available=True)

    """WHEN executing."""
    h = await adapter.health_check()

    """THEN the result is correct."""
    assert h.healthy is True

    adapter2 = StubAdapter("t2", available=False)
    h2 = await adapter2.health_check()
    assert h2.healthy is False


def test_stub_adapter_properties() -> None:
    """GIVEN the stub adapter properties scenario."""

    """WHEN executing."""
    adapter = StubAdapter("my-tool")

    """THEN the result is correct."""
    assert adapter.slug == "my-tool"
    assert adapter.display_name == "Stub Tool"
    assert adapter.integration_mode == IntegrationMode.CLI_TASK
    assert ToolCapability.CLI_COMMANDS in adapter.capabilities
