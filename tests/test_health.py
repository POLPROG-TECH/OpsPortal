"""Tests for the health check service."""

from __future__ import annotations

import pytest

from opsportal.adapters.registry import AdapterRegistry
from opsportal.services.health import check_all_health
from tests.conftest import StubAdapter


@pytest.mark.asyncio
async def test_health_all_healthy() -> None:
    """GIVEN the health all healthy scenario."""
    reg = AdapterRegistry()
    reg.register(StubAdapter("a", available=True))
    reg.register(StubAdapter("b", available=True))

    """WHEN executing."""
    result = await check_all_health(reg)

    """THEN the result is correct."""
    assert result.overall is True
    assert len(result.tools) == 2
    assert all(r.healthy for r in result.tools.values())


@pytest.mark.asyncio
async def test_health_partial_failure() -> None:
    """GIVEN the health partial failure scenario."""
    reg = AdapterRegistry()
    reg.register(StubAdapter("ok", available=True))
    reg.register(StubAdapter("bad", available=False))

    """WHEN executing."""
    result = await check_all_health(reg)

    """THEN the result is correct."""
    assert result.overall is False
    assert result.tools["ok"].healthy is True
    assert result.tools["bad"].healthy is False


@pytest.mark.asyncio
async def test_health_empty_registry() -> None:
    """GIVEN the health empty registry scenario."""
    reg = AdapterRegistry()

    """WHEN executing."""
    result = await check_all_health(reg)

    """THEN the result is correct."""
    assert result.overall is True
    assert len(result.tools) == 0
