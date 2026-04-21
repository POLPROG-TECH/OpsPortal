"""Integration gateway - HTTP proxy to child tool APIs with health-aware routing.

Central service that fetches data from running child tools through their REST
endpoints.  Uses the adapter registry for URL resolution and auto-starts tools
on demand via ``ensure_ready()``.

Features:
- Response caching with configurable TTL (GET requests only)
- Retry with exponential backoff for transient failures
- Health-aware routing with auto-start
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import httpx

from opsportal.adapters.base import (
    IntegrationCapability,
    ToolAdapter,
    ToolStatus,
)
from opsportal.adapters.registry import AdapterRegistry
from opsportal.core.errors import get_logger

logger = get_logger("services.integration_gateway")

GATEWAY_TIMEOUT = 15.0  # seconds
DEFAULT_CACHE_TTL = 30.0  # seconds - for GET responses
MAX_RETRIES = 3
RETRY_BASE_DELAY = 0.5  # seconds - exponential backoff base


@dataclass(frozen=True, slots=True)
class GatewayResponse:
    """Result of a proxied HTTP call to a child tool."""

    success: bool
    data: dict[str, Any] | None = None
    error: str = ""
    source_tool: str = ""
    http_status: int | None = None
    cached: bool = False


class IntegrationGateway:
    """Proxies HTTP requests to child tool APIs."""

    def __init__(
        self,
        registry: AdapterRegistry,
        *,
        cache: Any | None = None,
        cache_ttl: float = DEFAULT_CACHE_TTL,
    ) -> None:
        self._registry = registry
        self._client: httpx.AsyncClient | None = None
        self._cache = cache
        self._cache_ttl = cache_ttl

    @property
    def registry(self) -> AdapterRegistry:
        return self._registry

    async def startup(self) -> None:
        from opsportal.core.network import make_http_client

        self._client = make_http_client()

    async def shutdown(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            from opsportal.core.network import make_http_client

            self._client = make_http_client()
        return self._client

    def _cache_key(self, tool_slug: str, path: str) -> str:
        return f"gw:{tool_slug}:{path}"

    def clear_cache(self) -> None:
        """Invalidate all cached gateway responses."""
        if self._cache is not None:
            self._cache.clear()

    async def _ensure_tool_running(self, adapter: ToolAdapter) -> str | None:
        """Ensure tool is running and return its base URL, or *None* on failure."""
        status = await adapter.get_status()
        if status == ToolStatus.RUNNING:
            url = adapter.get_web_url()
            if url:
                return url

        try:
            result = await adapter.ensure_ready()
        except (OSError, RuntimeError) as exc:
            logger.warning("Failed to start %s: %s", adapter.slug, exc)
            return None

        if not result.ready:
            return None
        return result.web_url or adapter.get_web_url()

    async def fetch(
        self,
        tool_slug: str,
        path: str,
        *,
        method: str = "GET",
        json_body: dict[str, Any] | None = None,
        timeout: float = GATEWAY_TIMEOUT,
        use_cache: bool = True,
    ) -> GatewayResponse:
        """Fetch data from a child tool's API endpoint.

        GET requests are cached by default (TTL-based). POST requests
        bypass the cache. Transient failures are retried with backoff.
        """
        is_get = method.upper() == "GET"

        # Check cache for GET requests
        if is_get and use_cache and self._cache is not None:
            key = self._cache_key(tool_slug, path)
            cached = self._cache.get(key)
            if cached is not None:
                return GatewayResponse(
                    success=True,
                    data=cached,
                    source_tool=tool_slug,
                    http_status=200,
                    cached=True,
                )

        adapter = self._registry.get(tool_slug)
        if not adapter:
            return GatewayResponse(
                success=False,
                error=f"Tool '{tool_slug}' not registered",
                source_tool=tool_slug,
            )

        base_url = await self._ensure_tool_running(adapter)
        if not base_url:
            return GatewayResponse(
                success=False,
                error=f"Tool '{tool_slug}' is not available",
                source_tool=tool_slug,
            )

        url = f"{base_url}{path}"
        result = await self._fetch_with_retry(url, tool_slug, method, json_body, timeout)

        # Cache successful GET responses
        if result.success and is_get and use_cache and self._cache is not None:
            key = self._cache_key(tool_slug, path)
            self._cache.set(key, result.data, self._cache_ttl)

        return result

    async def _fetch_with_retry(
        self,
        url: str,
        tool_slug: str,
        method: str,
        json_body: dict[str, Any] | None,
        timeout: float,
    ) -> GatewayResponse:
        """Execute HTTP request with exponential backoff retry."""
        client = self._get_client()
        last_error = ""

        for attempt in range(MAX_RETRIES):
            try:
                if method.upper() == "GET":
                    resp = await client.get(url, timeout=timeout)
                elif method.upper() == "POST":
                    resp = await client.post(url, json=json_body or {}, timeout=timeout)
                else:
                    return GatewayResponse(
                        success=False,
                        error=f"Unsupported HTTP method: {method}",
                        source_tool=tool_slug,
                    )

                if resp.status_code == 200:
                    return GatewayResponse(
                        success=True,
                        data=resp.json(),
                        source_tool=tool_slug,
                        http_status=200,
                    )

                # Non-retryable HTTP errors (4xx)
                if 400 <= resp.status_code < 500:
                    return GatewayResponse(
                        success=False,
                        error=f"HTTP {resp.status_code}",
                        source_tool=tool_slug,
                        http_status=resp.status_code,
                    )

                # Server errors (5xx) - retryable
                last_error = f"HTTP {resp.status_code}"

            except httpx.TimeoutException:
                last_error = "Request timed out"
            except (httpx.HTTPError, OSError) as exc:
                last_error = str(exc)

            # Backoff before retry (skip on last attempt)
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_BASE_DELAY * (2**attempt)
                logger.debug(
                    "Retry %d/%d for %s %s: %s (backoff %.1fs)",
                    attempt + 1,
                    MAX_RETRIES,
                    method,
                    url,
                    last_error,
                    delay,
                )
                await asyncio.sleep(delay)

        return GatewayResponse(success=False, error=last_error, source_tool=tool_slug)

    async def fetch_from_capable(
        self,
        capability: IntegrationCapability,
        path: str,
        *,
        method: str = "GET",
        json_body: dict[str, Any] | None = None,
    ) -> list[GatewayResponse]:
        """Fetch from ALL tools that declare a given integration capability."""
        responses: list[GatewayResponse] = []
        for adapter in self._registry.all():
            endpoints = adapter.get_integration_endpoints()
            if any(ep.capability == capability for ep in endpoints):
                resp = await self.fetch(adapter.slug, path, method=method, json_body=json_body)
                responses.append(resp)
        return responses

    def tools_with_capability(self, capability: IntegrationCapability) -> list[ToolAdapter]:
        """Return adapters that declare a given integration capability."""
        return [a for a in self._registry.all() if capability in a.integration_capabilities]
