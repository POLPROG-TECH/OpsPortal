"""Networking utilities for OpsPortal — environment propagation, HTTP client factory.

OpsPortal is an orchestrator that launches child tools (ReleasePilot, ReleaseBoard)
 as subprocesses.Those child tools make their own outbound HTTPS calls to
 GitLab, Jira, Google Translate, etc.

For child tools to work correctly in corporate network environments
(Zscaler, Netskope, VPN, proxy), OpsPortal must propagate the relevant
SSL and proxy environment variables into each child process.

This module provides:

- ``ssl_proxy_env()`` — collects the SSL/proxy env vars that must be
  forwarded to child processes.
- ``make_http_client()`` — shared ``httpx.AsyncClient`` factory with
  consistent timeout and SSL defaults (for OpsPortal's own health checks).

Configuration
-------------
The following environment variables are automatically propagated to all
child tool processes when set in the OpsPortal environment:

- ``SSL_CERT_FILE`` — path to a custom CA bundle PEM file
- ``REQUESTS_CA_BUNDLE`` — same, used by ``requests``-based tools
- ``CURL_CA_BUNDLE`` — same, used by ``curl``
- ``HTTP_PROXY`` / ``http_proxy`` — HTTP proxy URL
- ``HTTPS_PROXY`` / ``https_proxy`` — HTTPS proxy URL
- ``NO_PROXY`` / ``no_proxy`` — comma-separated list of hostnames to bypass
- ``NODE_EXTRA_CA_CERTS`` — for Node.js-based tools (if any in the future)

No OpsPortal configuration is needed — if these env vars are set in the
shell that runs OpsPortal, they are automatically forwarded.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import httpx

logger = logging.getLogger(__name__)

# Environment variables that must be propagated to child tool processes
# for corporate network / SSL / proxy compatibility.
_SSL_PROXY_ENV_VARS = (
    "SSL_CERT_FILE",
    "REQUESTS_CA_BUNDLE",
    "CURL_CA_BUNDLE",
    "NODE_EXTRA_CA_CERTS",
    "HTTP_PROXY",
    "http_proxy",
    "HTTPS_PROXY",
    "https_proxy",
    "NO_PROXY",
    "no_proxy",
)


def ssl_proxy_env() -> dict[str, str]:
    """Collect SSL and proxy environment variables for child processes.

    Returns a dict of env vars that are set in the current process and
    should be forwarded to subprocess environments.  This ensures that
    child tools (ReleasePilot, ReleaseBoard) can
    connect to internal services through corporate proxies and with
    corporate CA bundles.

    Usage::

        import os
        child_env = {**os.environ, **custom_env, **ssl_proxy_env()}
    """
    env: dict[str, str] = {}
    for var in _SSL_PROXY_ENV_VARS:
        val = os.environ.get(var)
        if val:
            env[var] = val
    if env:
        logger.debug("SSL/proxy env vars for child processes: %s", list(env.keys()))
    return env


def make_http_client(*, timeout: float = 5.0) -> httpx.AsyncClient:
    """Create an ``httpx.AsyncClient`` with consistent defaults.

    This is a factory for OpsPortal's own HTTP clients — specifically
    for **localhost** health checks and probes.  All adapters should use
    this instead of creating ``httpx.AsyncClient`` instances directly.

    .. note::
        This client is intended for ``http://127.0.0.1:…`` only.
        It does not configure custom CA bundles.  For outbound HTTPS
        to external services, child tools have their own SSL configuration.
    """
    import httpx as _httpx

    return _httpx.AsyncClient(timeout=timeout)
