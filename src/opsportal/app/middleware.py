"""Shared middleware for the portal application."""

from __future__ import annotations

import base64
import secrets
from http.cookies import SimpleCookie

from starlette.datastructures import MutableHeaders
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

_CSRF_COOKIE = "opsportal_csrf"
_CSRF_HEADER = "x-csrf-token"
_MUTATING_METHODS = {"POST", "PUT", "DELETE"}

# Paths that bypass authentication (metrics, health probes)
_AUTH_EXEMPT_PATHS = {"/api/health", "/metrics"}


def _build_csp(child_tool_ports: list[int] | None = None) -> str:
    """Build Content-Security-Policy with frame-src for child tool ports.

    Child tools are served on localhost but on different ports, which makes
    them cross-origin.  The portal must explicitly allow framing them.
    """
    frame_sources = ["'self'"]
    for port in child_tool_ports or []:
        frame_sources.append(f"http://127.0.0.1:{port}")
        frame_sources.append(f"http://localhost:{port}")
    frame_src = " ".join(frame_sources)

    cdn_hosts = "https://cdn.jsdelivr.net"

    return (
        f"default-src 'self'; "
        f"script-src 'self' 'unsafe-inline' {cdn_hosts}; "
        f"style-src 'self' 'unsafe-inline' {cdn_hosts}; "
        f"img-src 'self' data:; "
        f"frame-src {frame_src}; "
        f"frame-ancestors 'self'"
    )


class PortalSecurityMiddleware:
    """Add baseline security headers, CSRF protection, and optional auth."""

    def __init__(
        self,
        app: ASGIApp,
        child_tool_ports: list[int] | None = None,
        auth_enabled: bool = False,
        auth_username: str = "",
        auth_password: str = "",
    ) -> None:
        self.app = app
        self._csp = _build_csp(child_tool_ports)
        self._auth_enabled = auth_enabled and bool(auth_password)
        self._auth_username = auth_username
        self._auth_password = auth_password

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET")
        path = scope.get("path", "")
        raw_headers = dict(scope.get("headers", []))

        # -- Basic Authentication (#12) --
        if self._auth_enabled and path not in _AUTH_EXEMPT_PATHS:
            auth_header = raw_headers.get(b"authorization", b"").decode("latin-1")
            if not self._check_auth(auth_header):
                resp = Response(
                    "Unauthorized",
                    status_code=401,
                    headers={"WWW-Authenticate": 'Basic realm="OpsPortal"'},
                )
                await resp(scope, receive, send)
                return

        cookie_header = raw_headers.get(b"cookie", b"").decode("latin-1")

        # Parse existing CSRF cookie
        sc = SimpleCookie(cookie_header)
        csrf_cookie = sc[_CSRF_COOKIE].value if _CSRF_COOKIE in sc else ""
        if not csrf_cookie:
            csrf_cookie = secrets.token_hex(32)

        # CSRF validation for mutating methods (exempt health endpoints)
        if method in _MUTATING_METHODS and not path.startswith("/api/health"):
            header_token = ""
            for key, val in scope.get("headers", []):
                if key == b"x-csrf-token":
                    header_token = val.decode("latin-1")
                    break
            if not header_token or header_token != csrf_cookie:
                resp = JSONResponse({"error": "CSRF validation failed"}, status_code=403)
                await resp(scope, receive, send)
                return

        csp = self._csp

        async def add_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.setdefault("x-content-type-options", "nosniff")
                headers.setdefault("referrer-policy", "strict-origin-when-cross-origin")
                headers.setdefault("content-security-policy", csp)
                headers.setdefault("x-frame-options", "SAMEORIGIN")
                headers.append(
                    "set-cookie",
                    f"{_CSRF_COOKIE}={csrf_cookie}; Path=/; SameSite=Strict; Max-Age=86400",
                )
            await send(message)

        await self.app(scope, receive, add_headers)

    def _check_auth(self, auth_header: str) -> bool:
        """Validate Basic auth header."""
        if not auth_header.startswith("Basic "):
            return False
        try:
            decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
            username, password = decoded.split(":", 1)
            return secrets.compare_digest(
                username, self._auth_username
            ) and secrets.compare_digest(password, self._auth_password)
        except (ValueError, UnicodeDecodeError):
            return False
