"""Shared fake adapters and registries for integration tests."""

from __future__ import annotations

from pathlib import Path

from opsportal.adapters.base import (
    EnsureReadyResult,
    HealthResult,
    IntegrationEndpoint,
    IntegrationMode,
    ToolAdapter,
    ToolCapability,
    ToolStatus,
)


class FakeAdapter(ToolAdapter):
    """Minimal adapter stub with configurable integration endpoints."""

    def __init__(
        self,
        slug: str,
        *,
        endpoints: list[IntegrationEndpoint] | None = None,
        web_url: str = "http://localhost:9999",
        status: ToolStatus = ToolStatus.RUNNING,
    ) -> None:
        self._slug = slug
        self._endpoints = endpoints or []
        self._web_url = web_url
        self._status = status

    @property
    def slug(self) -> str:
        return self._slug

    @property
    def display_name(self) -> str:
        return self._slug.title()

    @property
    def description(self) -> str:
        return ""

    @property
    def integration_mode(self) -> IntegrationMode:
        return IntegrationMode.SUBPROCESS_WEB

    @property
    def capabilities(self) -> set[ToolCapability]:
        return set()

    @property
    def icon(self) -> str:
        return "box"

    @property
    def color(self) -> str:
        return "#000"

    @property
    def repo_path(self) -> Path:
        return Path("/tmp/fake")

    async def get_status(self) -> ToolStatus:
        return self._status

    async def health_check(self) -> HealthResult:
        return HealthResult(healthy=True, message="ok")

    def get_web_url(self) -> str | None:
        return self._web_url

    def get_integration_endpoints(self) -> list[IntegrationEndpoint]:
        return self._endpoints

    async def ensure_ready(self) -> EnsureReadyResult:
        return EnsureReadyResult(ready=True, web_url=self._web_url)


class FakeRegistry:
    """In-memory adapter registry for tests."""

    def __init__(self, adapters: list[ToolAdapter] | None = None) -> None:
        self._adapters = {a.slug: a for a in (adapters or [])}

    def all(self) -> list[ToolAdapter]:
        return list(self._adapters.values())

    def get(self, slug: str) -> ToolAdapter | None:
        return self._adapters.get(slug)
