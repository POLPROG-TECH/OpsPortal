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
        """GIVEN Non-HTML artifact content must be HTML-escaped inside <pre>."""
        am: ArtifactManager = client.app.state.artifact_manager
        payload = "<script>alert('xss')</script>"
        am.store_content("testtool", payload, "evil.txt", content_type="text/plain")

        # Register a minimal adapter so the route finds the tool
        from tests.conftest import StubAdapter

        adapter = StubAdapter(slug="testtool")
        client.app.state.registry.register(adapter)

        """WHEN executing."""
        resp = client.get("/tools/testtool/artifacts/evil.txt")

        """THEN the result is correct."""
        assert resp.status_code == 200
        assert "<script>" not in resp.text
        assert "&lt;script&gt;" in resp.text

    def test_html_artifact_has_sandbox_csp(self, client: TestClient, tmp_path: Path) -> None:
        """GIVEN HTML artifacts must be served with a restrictive CSP header."""
        am: ArtifactManager = client.app.state.artifact_manager
        am.store_content("testtool", "<h1>Report</h1>", "report.html", content_type="text/html")

        from tests.conftest import StubAdapter

        adapter = StubAdapter(slug="testtool")
        with contextlib.suppress(Exception):
            client.app.state.registry.register(adapter)

        """WHEN executing."""
        resp = client.get("/tools/testtool/artifacts/report.html")

        """THEN the result is correct."""
        assert resp.status_code == 200
        assert "sandbox" in resp.headers.get("content-security-policy", "")


# ---------------------------------------------------------------------------
# Path traversal prevention in artifact retrieval
# ---------------------------------------------------------------------------


class TestPathTraversal:
    def test_traversal_returns_none(self, tmp_path: Path) -> None:
        """GIVEN Artifact manager must reject path-traversal names."""
        am = ArtifactManager(tmp_path / "artifacts")

        """WHEN executing."""
        am.store_content("tool", "legit", "ok.txt")

        """THEN the result is correct."""
        assert am.get_artifact("tool", "../../etc/passwd") is None
        assert am.get_artifact("tool", "../other_tool/secret.txt") is None

    def test_valid_artifact_still_works(self, tmp_path: Path) -> None:
        """GIVEN the valid artifact still works scenario."""
        am = ArtifactManager(tmp_path / "artifacts")
        am.store_content("tool", "hello", "readme.txt")

        """WHEN executing."""
        entry = am.get_artifact("tool", "readme.txt")

        """THEN the result is correct."""
        assert entry is not None
        assert entry.name == "readme.txt"


# ---------------------------------------------------------------------------
# Malformed JSON request handling
# ---------------------------------------------------------------------------


class TestMalformedJSON:
    def test_config_validate_bad_json(self, client: TestClient) -> None:
        """GIVEN POST with invalid JSON must return 400, not 500."""
        from tests.conftest import StubAdapter

        adapter = StubAdapter(slug="jsontool")
        with contextlib.suppress(Exception):
            client.app.state.registry.register(adapter)

        hdrs = csrf_headers(client)
        hdrs["content-type"] = "application/json"

        """WHEN executing."""
        resp = client.post(
            "/api/tools/jsontool/config/validate",
            content=b"{bad json",
            headers=hdrs,
        )

        """THEN the result is correct."""
        assert resp.status_code == 400
        assert "Invalid JSON" in resp.json().get("error", "")

    def test_config_save_bad_json(self, client: TestClient) -> None:
        """GIVEN the config save bad json scenario."""
        from tests.conftest import StubAdapter

        adapter = StubAdapter(slug="jsontool2")
        with contextlib.suppress(Exception):
            client.app.state.registry.register(adapter)

        hdrs = csrf_headers(client)
        hdrs["content-type"] = "application/json"

        """WHEN executing."""
        resp = client.put(
            "/api/tools/jsontool2/config",
            content=b"not-json",
            headers=hdrs,
        )

        """THEN the result is correct."""
        assert resp.status_code == 400

    def test_action_bad_json(self, client: TestClient) -> None:
        """GIVEN the action bad json scenario."""
        from tests.conftest import StubAdapter

        adapter = StubAdapter(slug="jsontool3")
        with contextlib.suppress(Exception):
            client.app.state.registry.register(adapter)

        hdrs = csrf_headers(client)
        hdrs["content-type"] = "application/json"

        """WHEN executing."""
        resp = client.post(
            "/api/tools/jsontool3/actions/run",
            content=b"{bad",
            headers=hdrs,
        )

        """THEN the result is correct."""
        assert resp.status_code == 400

    def test_action_no_content_type_is_fine(self, client: TestClient) -> None:
        """GIVEN Non-JSON content-type should default to empty body, not error."""
        from tests.conftest import StubAdapter

        adapter = StubAdapter(slug="jsontool4")
        with contextlib.suppress(Exception):
            client.app.state.registry.register(adapter)

        hdrs = csrf_headers(client)
        hdrs["content-type"] = "text/plain"

        """WHEN executing."""
        resp = client.post(
            "/api/tools/jsontool4/actions/run",
            content=b"",
            headers=hdrs,
        )
        # The adapter doesn't implement run_action so we expect 500,
        # but critically NOT a 400 JSON error

        """THEN the result is correct."""
        assert resp.status_code != 400


# ---------------------------------------------------------------------------
# Content Security Policy headers
# ---------------------------------------------------------------------------


class TestCSPHeaders:
    def test_home_has_csp_header(self, client: TestClient) -> None:
        """GIVEN the home has csp header scenario."""

        """WHEN executing."""
        resp = client.get("/")

        """THEN the result is correct."""
        assert "content-security-policy" in resp.headers
        csp = resp.headers["content-security-policy"]
        assert "default-src" in csp

    def test_no_deprecated_xss_protection(self, client: TestClient) -> None:
        """GIVEN the no deprecated xss protection scenario."""

        """WHEN executing."""
        resp = client.get("/")

        """THEN the result is correct."""
        assert "x-xss-protection" not in resp.headers

    def test_x_frame_options_present(self, client: TestClient) -> None:
        """GIVEN the x frame options present scenario."""

        """WHEN executing."""
        resp = client.get("/")

        """THEN the result is correct."""
        assert resp.headers.get("x-frame-options", "").upper() == "SAMEORIGIN"


# ---------------------------------------------------------------------------
# Custom error page rendering
# ---------------------------------------------------------------------------


class TestCustomErrorPage:
    def test_404_uses_error_template(self, client: TestClient) -> None:
        """GIVEN the 404 uses error template scenario."""

        """WHEN executing."""
        resp = client.get("/nonexistent-page-xyz")

        """THEN the result is correct."""
        assert resp.status_code == 404
        assert "Something went wrong" in resp.text or "error" in resp.text.lower()


# ---------------------------------------------------------------------------
# Config mixin error handling for corrupt files
# ---------------------------------------------------------------------------


class TestConfigMixinErrorHandling:
    def test_read_raw_config_corrupt_json(self, tmp_path: Path) -> None:
        """GIVEN _read_raw_config must return {} for corrupt JSON, not raise."""
        from opsportal.adapters._config_mixin import JsonSchemaConfigMixin

        class FakeAdapter(JsonSchemaConfigMixin):
            _repo_path = tmp_path
            _config_file = "broken.json"
            _schema_paths: ClassVar[list[Path]] = []
            _validate_fn = None

        (tmp_path / "broken.json").write_text("{bad json!", encoding="utf-8")
        adapter = FakeAdapter()

        """WHEN executing."""
        result = adapter._read_raw_config()

        """THEN the result is correct."""
        assert result == {}
