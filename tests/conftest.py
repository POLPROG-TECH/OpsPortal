"""Shared test fixtures for OpsPortal."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from opsportal.adapters.base import (
    HealthResult,
    IntegrationMode,
    ToolAdapter,
    ToolCapability,
    ToolStatus,
)
from opsportal.app.factory import create_app
from opsportal.core.settings import PortalSettings


@pytest.fixture()
def tmp_settings(tmp_path: Path) -> PortalSettings:
    """Portal settings pointing at temp directories."""
    manifest = tmp_path / "opsportal.yaml"
    manifest.write_text("tools: {}\n")
    return PortalSettings(
        host="127.0.0.1",
        port=9999,
        debug=False,
        log_level="warning",
        manifest_path=manifest,
        artifact_dir=tmp_path / "artifacts",
        work_dir=tmp_path / "work",
        tools_base_dir=tmp_path,
    )


@pytest.fixture()
def app(tmp_settings: PortalSettings):
    """A minimal portal app for testing (no real tools)."""
    return create_app(settings=tmp_settings)


@pytest.fixture()
def client(app) -> TestClient:
    """Synchronous test client."""
    return TestClient(app)


def csrf_headers(client: TestClient) -> dict[str, str]:
    """Do a GET to establish the CSRF cookie and return headers for mutating requests."""
    client.get("/")
    token = client.cookies.get("opsportal_csrf", "")
    return {"x-csrf-token": token}


@pytest.fixture()
async def async_client(app) -> AsyncGenerator[AsyncClient, None]:
    """Async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class StubAdapter(ToolAdapter):
    """A simple stub adapter for testing."""

    def __init__(self, slug: str = "stub-tool", available: bool = True) -> None:
        self._slug = slug
        self._available = available

    @property
    def slug(self) -> str:
        return self._slug

    @property
    def display_name(self) -> str:
        return "Stub Tool"

    @property
    def description(self) -> str:
        return "A stub tool for testing"

    @property
    def integration_mode(self) -> IntegrationMode:
        return IntegrationMode.CLI_TASK

    @property
    def capabilities(self) -> set[ToolCapability]:
        return {ToolCapability.CLI_COMMANDS}

    @property
    def icon(self) -> str:
        return "box"

    @property
    def color(self) -> str:
        return "#888888"

    @property
    def repo_path(self) -> Path:
        return Path("/tmp/stub")

    async def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if self._available else ToolStatus.ERROR

    async def health_check(self) -> HealthResult:
        if self._available:
            return HealthResult(healthy=True, message="OK")
        return HealthResult(healthy=False, message="Not available")
