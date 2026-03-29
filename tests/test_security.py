"""Security tests for OpsPortal.

Covers: XSS escaping, path traversal prevention, malformed JSON handling,
CSP headers, custom error pages, and config error handling.
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import ClassVar

from fastapi.testclient import TestClient

from opsportal.services.artifact_manager import ArtifactManager
from tests.conftest import csrf_headers

# ---------------------------------------------------------------------------
# XSS escaping in artifact rendering
# ---------------------------------------------------------------------------


class TestXSSEscaping:
    def test_non_html_artifact_is_escaped(self, client: TestClient, tmp_path: Path) -> None:
        """Non-HTML artifact content is HTML-escaped inside <pre>."""
        """GIVEN an artifact with an XSS payload stored as text/plain."""
        am: ArtifactManager = client.app.state.artifact_manager
        payload = "<script>alert('xss')</script>"
        am.store_content("testtool", payload, "evil.txt", content_type="text/plain")

        # Register a minimal adapter so the route finds the tool
        from tests.conftest import StubAdapter

        adapter = StubAdapter(slug="testtool")
        client.app.state.registry.register(adapter)

        """WHEN requesting the artifact."""
        resp = client.get("/tools/testtool/artifacts/evil.txt")

        """THEN the raw <script> tag is escaped."""
        assert resp.status_code == 200
        assert "<script>" not in resp.text
        assert "&lt;script&gt;" in resp.text

    def test_html_artifact_has_sandbox_csp(self, client: TestClient, tmp_path: Path) -> None:
        """HTML artifacts are served with a restrictive sandbox CSP header."""
        """GIVEN an HTML artifact."""
        am: ArtifactManager = client.app.state.artifact_manager
        am.store_content("testtool", "<h1>Report</h1>", "report.html", content_type="text/html")

        from tests.conftest import StubAdapter

        adapter = StubAdapter(slug="testtool")
        with contextlib.suppress(Exception):
            client.app.state.registry.register(adapter)

        """WHEN requesting the HTML artifact."""
        resp = client.get("/tools/testtool/artifacts/report.html")

        """THEN the CSP header includes sandbox."""
        assert resp.status_code == 200
        assert "sandbox" in resp.headers.get("content-security-policy", "")


# ---------------------------------------------------------------------------
# Path traversal prevention in artifact retrieval
# ---------------------------------------------------------------------------


class TestPathTraversal:
    def test_traversal_returns_none(self, tmp_path: Path) -> None:
        """Artifact manager rejects path-traversal filenames."""
        """GIVEN an artifact manager with a stored artifact."""
        am = ArtifactManager(tmp_path / "artifacts")
        am.store_content("tool", "legit", "ok.txt")

        """WHEN requesting with path-traversal names."""
        """THEN both attempts return None."""
        assert am.get_artifact("tool", "../../etc/passwd") is None
        assert am.get_artifact("tool", "../other_tool/secret.txt") is None

    def test_valid_artifact_still_works(self, tmp_path: Path) -> None:
        """Valid artifact names are retrieved correctly."""
        """GIVEN an artifact manager with a stored artifact."""
        am = ArtifactManager(tmp_path / "artifacts")
        am.store_content("tool", "hello", "readme.txt")

        """WHEN requesting the artifact by its valid name."""
        entry = am.get_artifact("tool", "readme.txt")

        """THEN it returns the artifact with the correct name."""
        assert entry is not None
        assert entry.name == "readme.txt"


# ---------------------------------------------------------------------------
# Malformed JSON request handling
# ---------------------------------------------------------------------------


class TestMalformedJSON:
    def test_config_validate_bad_json(self, client: TestClient) -> None:
        """POST with invalid JSON to config validate returns 400, not 500."""
        """GIVEN a registered tool and CSRF headers."""
        from tests.conftest import StubAdapter

        adapter = StubAdapter(slug="jsontool")
        with contextlib.suppress(Exception):
            client.app.state.registry.register(adapter)

        hdrs = csrf_headers(client)
        hdrs["content-type"] = "application/json"

        """WHEN posting malformed JSON to the validate endpoint."""
        resp = client.post(
            "/api/tools/jsontool/config/validate",
            content=b"{bad json",
            headers=hdrs,
        )

        """THEN it returns 400 with an 'Invalid JSON' error."""
        assert resp.status_code == 400
        assert "Invalid JSON" in resp.json().get("error", "")

    def test_config_save_bad_json(self, client: TestClient) -> None:
        """PUT with invalid JSON to config save returns 400."""
        """GIVEN a registered tool and CSRF headers."""
        from tests.conftest import StubAdapter

        adapter = StubAdapter(slug="jsontool2")
        with contextlib.suppress(Exception):
            client.app.state.registry.register(adapter)

        hdrs = csrf_headers(client)
        hdrs["content-type"] = "application/json"

        """WHEN putting malformed JSON to the config endpoint."""
        resp = client.put(
            "/api/tools/jsontool2/config",
            content=b"not-json",
            headers=hdrs,
        )

        """THEN it returns 400."""
        assert resp.status_code == 400

    def test_action_bad_json(self, client: TestClient) -> None:
        """POST with invalid JSON to an action endpoint returns 400."""
        """GIVEN a registered tool and CSRF headers."""
        from tests.conftest import StubAdapter

        adapter = StubAdapter(slug="jsontool3")
        with contextlib.suppress(Exception):
            client.app.state.registry.register(adapter)

        hdrs = csrf_headers(client)
        hdrs["content-type"] = "application/json"

        """WHEN posting malformed JSON to the action endpoint."""
        resp = client.post(
            "/api/tools/jsontool3/actions/run",
            content=b"{bad",
            headers=hdrs,
        )

        """THEN it returns 400."""
        assert resp.status_code == 400

    def test_action_no_content_type_is_fine(self, client: TestClient) -> None:
        """Non-JSON content-type defaults to empty body, not a JSON parse error."""
        """GIVEN a registered tool and CSRF headers with text/plain content type."""
        from tests.conftest import StubAdapter

        adapter = StubAdapter(slug="jsontool4")
        with contextlib.suppress(Exception):
            client.app.state.registry.register(adapter)

        hdrs = csrf_headers(client)
        hdrs["content-type"] = "text/plain"

        """WHEN posting empty text content to the action endpoint."""
        resp = client.post(
            "/api/tools/jsontool4/actions/run",
            content=b"",
            headers=hdrs,
        )
        # The adapter doesn't implement run_action so we expect 500,
        # but critically NOT a 400 JSON error

        """THEN the response is not a 400 JSON error."""
        assert resp.status_code != 400


# ---------------------------------------------------------------------------
# Content Security Policy headers
# ---------------------------------------------------------------------------


class TestCSPHeaders:
    def test_home_has_csp_header(self, client: TestClient) -> None:
        """GIVEN a running OpsPortal app."""

        """WHEN requesting the home page."""
        resp = client.get("/")

        """THEN the CSP header contains default-src."""
        assert "content-security-policy" in resp.headers
        csp = resp.headers["content-security-policy"]
        assert "default-src" in csp

    def test_no_deprecated_xss_protection(self, client: TestClient) -> None:
        """GIVEN a running OpsPortal app."""

        """WHEN requesting the home page."""
        resp = client.get("/")

        """THEN X-XSS-Protection is absent."""
        assert "x-xss-protection" not in resp.headers

    def test_x_frame_options_present(self, client: TestClient) -> None:
        """GIVEN a running OpsPortal app."""

        """WHEN requesting the home page."""
        resp = client.get("/")

        """THEN X-Frame-Options is SAMEORIGIN."""
        assert resp.headers.get("x-frame-options", "").upper() == "SAMEORIGIN"


# ---------------------------------------------------------------------------
# Custom error page rendering
# ---------------------------------------------------------------------------


class TestCustomErrorPage:
    def test_404_uses_error_template(self, client: TestClient) -> None:
        """GIVEN a running OpsPortal app."""

        """WHEN requesting a non-existent page."""
        resp = client.get("/nonexistent-page-xyz")

        """THEN it returns 404 with an error indication."""
        assert resp.status_code == 404
        assert "Something went wrong" in resp.text or "error" in resp.text.lower()


# ---------------------------------------------------------------------------
# Config mixin error handling for corrupt files
# ---------------------------------------------------------------------------


class TestConfigMixinErrorHandling:
    def test_read_raw_config_corrupt_json(self, tmp_path: Path) -> None:
        """_read_raw_config returns {} for corrupt JSON files, not raising."""
        """GIVEN a FakeAdapter with a corrupt JSON config file."""
        from opsportal.adapters._config_mixin import JsonSchemaConfigMixin

        class FakeAdapter(JsonSchemaConfigMixin):
            _repo_path = tmp_path
            _config_file = "broken.json"
            _schema_paths: ClassVar[list[Path]] = []
            _validate_fn = None

        (tmp_path / "broken.json").write_text("{bad json!", encoding="utf-8")
        adapter = FakeAdapter()

        """WHEN reading the raw config."""
        result = adapter._read_raw_config()

        """THEN it returns an empty dict."""
        assert result == {}
