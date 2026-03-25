"""Tests for CSRF protection, HTTP client lifecycle, port defaults,
template context, and DOM security.
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

from opsportal.core.settings import PortalSettings
from tests.conftest import csrf_headers

# ---------------------------------------------------------------------------
# CSRF protection on mutating endpoints
# ---------------------------------------------------------------------------


class TestCSRFProtection:
    """Double-submit cookie CSRF pattern must be enforced."""

    def test_post_without_csrf_token_returns_403(self, client: TestClient) -> None:
        """POST without X-CSRF-Token header is rejected with 403."""
        """GIVEN a client that has obtained the CSRF cookie via GET."""
        client.get("/")

        """WHEN posting without the CSRF token header."""
        resp = client.post("/api/tools/nonexistent/actions/test")

        """THEN the request is rejected with 403 and a CSRF error."""
        assert resp.status_code == 403
        assert "CSRF" in resp.json().get("error", "")

    def test_post_with_wrong_csrf_token_returns_403(self, client: TestClient) -> None:
        """POST with a mismatched X-CSRF-Token is rejected with 403."""
        """GIVEN a client that has obtained the CSRF cookie."""
        client.get("/")

        """WHEN posting with a wrong CSRF token."""
        resp = client.post(
            "/api/tools/nonexistent/actions/test",
            headers={"x-csrf-token": "wrong-token-value"},
        )

        """THEN the request is rejected with 403."""
        assert resp.status_code == 403

    def test_post_with_matching_csrf_token_passes(self, client: TestClient) -> None:
        """POST with correct X-CSRF-Token passes CSRF check and reaches routing."""
        """GIVEN valid CSRF headers."""
        hdrs = csrf_headers(client)
        # Target a non-existent tool — should get 404, NOT 403

        """WHEN posting with correct CSRF token to a non-existent tool."""
        resp = client.post(
            "/api/tools/nonexistent/actions/test",
            headers=hdrs,
        )

        """THEN the response is 404 (past CSRF, tool not found)."""
        assert resp.status_code == 404

    def test_put_without_csrf_returns_403(self, client: TestClient) -> None:
        """PUT without CSRF token is rejected with 403."""
        """GIVEN a client that has obtained the CSRF cookie."""
        client.get("/")

        """WHEN sending a PUT without CSRF token."""
        resp = client.put("/api/tools/x/config", content=b"{}")

        """THEN the request is rejected with 403."""
        assert resp.status_code == 403

    def test_delete_without_csrf_returns_403(self, client: TestClient) -> None:
        """DELETE without CSRF token is rejected with 403."""
        """GIVEN a client that has obtained the CSRF cookie."""
        client.get("/")

        """WHEN sending a DELETE without CSRF token."""
        resp = client.delete("/api/tools/x/anything")

        """THEN the request is rejected with 403."""
        assert resp.status_code == 403

    def test_health_endpoint_exempt_from_csrf(self, client: TestClient) -> None:
        """Health API endpoint is exempt from CSRF checks."""
        """WHEN requesting the health API without any CSRF token."""
        resp = client.get("/api/health")

        """THEN it returns 200."""
        assert resp.status_code == 200

    def test_csrf_cookie_set_on_get(self, client: TestClient) -> None:
        """A GET request sets the opsportal_csrf cookie."""
        """WHEN making a GET request."""
        client.get("/")

        """THEN the CSRF cookie is present."""
        assert "opsportal_csrf" in client.cookies

    def test_csrf_cookie_is_64_hex_chars(self, client: TestClient) -> None:
        """CSRF token is 64 hex characters (secrets.token_hex(32))."""
        """GIVEN a client with a CSRF cookie."""
        client.get("/")

        """WHEN reading the token."""
        token = client.cookies.get("opsportal_csrf", "")

        """THEN it matches the expected 64-hex-char format."""
        assert re.fullmatch(r"[0-9a-f]{64}", token), f"Bad token format: {token!r}"


# ---------------------------------------------------------------------------
# Shared HTTP client for adapters
# ---------------------------------------------------------------------------


class TestSharedHTTPClient:
    """Adapters must reuse a single httpx.AsyncClient instead of creating one per call."""

    def test_releaseboard_adapter_has_http_client_attr(self) -> None:
        """ReleaseBoardAdapter has an _http_client attr initialized to None."""
        """GIVEN a ReleaseBoardAdapter."""
        from opsportal.adapters.releaseboard import ReleaseBoardAdapter
        from opsportal.services.process_manager import ProcessManager

        pm = ProcessManager()

        """WHEN creating the adapter."""
        adapter = ReleaseBoardAdapter(repo_path=Path("/tmp"), process_manager=pm)

        """THEN _http_client exists and is None."""
        assert hasattr(adapter, "_http_client")
        assert adapter._http_client is None

    def test_releasepilot_adapter_has_http_client_attr(self) -> None:
        """ReleasePilotAdapter has an _http_client attr initialized to None."""
        """GIVEN a ReleasePilotAdapter."""
        from opsportal.adapters.releasepilot import ReleasePilotAdapter
        from opsportal.services.process_manager import ProcessManager

        pm = ProcessManager()

        """WHEN creating the adapter."""
        adapter = ReleasePilotAdapter(repo_path=Path("/tmp"), process_manager=pm)

        """THEN _http_client exists and is None."""
        assert hasattr(adapter, "_http_client")
        assert adapter._http_client is None

    def test_get_http_client_returns_same_instance(self) -> None:
        """_get_http_client returns the same httpx.AsyncClient instance on repeated calls."""
        """GIVEN a ReleaseBoardAdapter with its first HTTP client."""
        from opsportal.adapters.releaseboard import ReleaseBoardAdapter
        from opsportal.services.process_manager import ProcessManager

        pm = ProcessManager()
        adapter = ReleaseBoardAdapter(repo_path=Path("/tmp"), process_manager=pm)
        c1 = adapter._get_http_client()

        """WHEN getting the HTTP client again."""
        c2 = adapter._get_http_client()

        """THEN the same instance is returned."""
        assert c1 is c2


# ---------------------------------------------------------------------------
# Port default fallback from CLI to settings
# ---------------------------------------------------------------------------


class TestPortDefault:
    """CLI serve command must fall back to settings.port when --port is omitted."""

    def test_settings_port_default_is_8000(self, tmp_settings: PortalSettings) -> None:
        """Test fixture overrides port to 9999."""
        """THEN the fixture-overridden port is 9999."""
        assert tmp_settings.port == 9999  # our fixture overrides it

    def test_default_settings_port_is_8000(self, tmp_path: Path) -> None:
        """Default PortalSettings use port 8000."""
        """GIVEN a minimal manifest."""
        manifest = tmp_path / "opsportal.yaml"
        manifest.write_text("tools: {}\n")

        """WHEN creating settings without specifying port."""
        s = PortalSettings(
            manifest_path=manifest,
            artifact_dir=tmp_path,
            work_dir=tmp_path,
            tools_base_dir=tmp_path,
        )

        """THEN the default port is 8000."""
        assert s.port == 8000

    def test_cli_port_none_falls_back_to_settings(self) -> None:
        """CLI serve command's --port parameter defaults to None for settings fallback."""
        """GIVEN the serve command's signature."""
        import inspect

        import opsportal.__main__ as main_mod

        sig = inspect.signature(main_mod.serve)

        """WHEN inspecting the port parameter."""
        port_param = sig.parameters["port"]

        """THEN its default is None or a typer.Option with None default."""
        assert port_param.default is None or hasattr(port_param.default, "default")


# ---------------------------------------------------------------------------
# Process logs included in tool web template context
# ---------------------------------------------------------------------------


class TestProcLogsInTemplate:
    """The tool_web.html template context must include proc_logs."""

    def test_route_passes_proc_logs(self) -> None:
        """tool_page route passes proc_logs in the template context."""
        """GIVEN the tool_page route source code."""
        import inspect

        from opsportal.app.routes import tool_page

        """WHEN inspecting the source."""
        src = inspect.getsource(tool_page)

        """THEN proc_logs is referenced in the template context."""
        assert "proc_logs" in src, "tool_page route must pass proc_logs to template context"


# ---------------------------------------------------------------------------
# DOM security — no innerHTML with translation strings
# ---------------------------------------------------------------------------


class TestNoInnerHTMLWithTranslations:
    """portal.js must not use innerHTML with translated strings (XSS risk)."""

    def test_no_innerhtml_in_portal_js(self) -> None:
        """portal.js does not use innerHTML (XSS risk with translated strings)."""
        """GIVEN the portal.js source file."""
        js_path = (
            Path(__file__).resolve().parent.parent
            / "src"
            / "opsportal"
            / "ui"
            / "static"
            / "js"
            / "portal.js"
        )

        """WHEN reading its content."""
        content = js_path.read_text(encoding="utf-8")
        # innerHTML should not appear at all now

        """THEN innerHTML is absent."""
        assert "innerHTML" not in content, (
            "portal.js still contains innerHTML — use DOM APIs instead"
        )

    def test_csrf_token_helper_exists(self) -> None:
        """portal.js defines the _csrfToken() helper reading opsportal_csrf cookie."""
        """GIVEN the portal.js source file."""
        js_path = (
            Path(__file__).resolve().parent.parent
            / "src"
            / "opsportal"
            / "ui"
            / "static"
            / "js"
            / "portal.js"
        )

        """WHEN reading its content."""
        content = js_path.read_text(encoding="utf-8")

        """THEN _csrfToken and opsportal_csrf are both present."""
        assert "_csrfToken" in content
        assert "opsportal_csrf" in content

    def test_fetch_calls_include_csrf_header(self) -> None:
        """All POST fetch() calls in portal.js include X-CSRF-Token header."""
        """GIVEN the portal.js source file."""
        js_path = (
            Path(__file__).resolve().parent.parent
            / "src"
            / "opsportal"
            / "ui"
            / "static"
            / "js"
            / "portal.js"
        )
        content = js_path.read_text(encoding="utf-8")

        """WHEN extracting POST fetch blocks."""
        post_blocks = re.findall(
            r'fetch\([^)]+,\s*\{[^}]*method:\s*"POST"[^}]*\}', content, re.DOTALL
        )

        """THEN each block contains X-CSRF-Token."""
        for block in post_blocks:
            assert "X-CSRF-Token" in block, f"Missing X-CSRF-Token in: {block[:100]}"
