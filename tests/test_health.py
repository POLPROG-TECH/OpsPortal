"""Tests for the health check service."""

from __future__ import annotations

import pytest

from opsportal.adapters.registry import AdapterRegistry
from opsportal.services.health import check_all_health
from tests.conftest import StubAdapter


@pytest.mark.asyncio
async def test_health_all_healthy() -> None:
    """All-healthy registry produces overall=True with all tools healthy."""
    """GIVEN a registry with two healthy adapters."""
    reg = AdapterRegistry()
    reg.register(StubAdapter("a", available=True))
    reg.register(StubAdapter("b", available=True))

    """WHEN checking health of all adapters."""
    result = await check_all_health(reg)

    """THEN overall is True and both tools are healthy."""
    assert result.overall is True
    assert len(result.tools) == 2
    assert all(r.healthy for r in result.tools.values())


@pytest.mark.asyncio
async def test_health_partial_failure() -> None:
    """One unhealthy adapter makes overall=False while the other stays healthy."""
    """GIVEN a registry with one healthy and one unhealthy adapter."""
    reg = AdapterRegistry()
    reg.register(StubAdapter("ok", available=True))
    reg.register(StubAdapter("bad", available=False))

    """WHEN checking health of all adapters."""
    result = await check_all_health(reg)

    """THEN overall is False, healthy tool is True, unhealthy is False."""
    assert result.overall is False
    assert result.tools["ok"].healthy is True
    assert result.tools["bad"].healthy is False


@pytest.mark.asyncio
async def test_health_empty_registry() -> None:
    """Empty registry produces overall=True with no tool results."""
    """GIVEN an empty registry."""
    reg = AdapterRegistry()

    """WHEN checking health."""
    result = await check_all_health(reg)

    """THEN overall is True and there are no tools."""
    assert result.overall is True
    assert len(result.tools) == 0
