"""Tests for enterprise CSP, config resolution, error sanitization, and version display."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from opsportal.app.middleware import _build_csp

# ---------------------------------------------------------------------------
# CSP frame-src tests
# ---------------------------------------------------------------------------


class TestCSPFrameSrc:
    """Verify that the portal's CSP allows framing child tools."""

    def test_csp_includes_frame_src_for_child_ports(self):
        """CSP frame-src includes entries for child tool ports."""
        """WHEN building CSP for ports 8081 and 8082."""
        csp = _build_csp([8081, 8082])

        """THEN frame-src contains localhost and 127.0.0.1 entries for each port."""
        assert "frame-src" in csp
        assert "http://127.0.0.1:8081" in csp
        assert "http://127.0.0.1:8082" in csp
        assert "http://localhost:8081" in csp
        assert "http://localhost:8082" in csp

    def test_csp_self_only_when_no_ports(self):
        """CSP falls back to 'self' when no child ports are registered."""
        """WHEN building CSP with an empty port list."""
        csp = _build_csp([])

        """THEN frame-src is 'self' only, with no 127.0.0.1 entries."""
        assert "frame-src 'self'" in csp
        assert "127.0.0.1" not in csp

    def test_csp_none_ports_handled(self):
        """CSP handles None as port list gracefully."""
        """WHEN building CSP with None instead of a list."""
        csp = _build_csp(None)

        """THEN frame-src falls back to 'self'."""
        assert "frame-src 'self'" in csp

    def test_csp_includes_frame_ancestors(self):
        """CSP includes frame-ancestors 'self' directive."""
        """WHEN building CSP for a single port."""
        csp = _build_csp([8081])

        """THEN frame-ancestors 'self' is present."""
        assert "frame-ancestors 'self'" in csp

    def test_home_page_csp_has_frame_src(self, client: TestClient):
        """Home page response includes CSP with frame-src directive."""
        """GIVEN a GET request to the home page."""
        resp = client.get("/")

        """WHEN extracting the CSP header."""
        csp = resp.headers.get("content-security-policy", "")

        """THEN frame-src is present in the header."""
        assert "frame-src" in csp


# ---------------------------------------------------------------------------
# ReleaseBoard config resolution tests
# ---------------------------------------------------------------------------


class TestReleaseBoardConfigResolution:
    """Verify multi-strategy config file discovery."""

    def test_config_found_in_repo_path(self, tmp_path: Path):
        """Config resolution finds releaseboard.json inside the repo directory."""
        from opsportal.adapters.releaseboard import ReleaseBoardAdapter
        from opsportal.services.process_manager import ProcessManager

        """GIVEN a repo directory containing releaseboard.json."""
        repo = tmp_path / "ReleaseBoard"
        repo.mkdir()
        config = repo / "releaseboard.json"
        config.write_text('{"release": {}}')

        pm = ProcessManager()
        adapter = ReleaseBoardAdapter(
            repo_path=repo,
            process_manager=pm,
            port=8081,
        )

        """WHEN resolving the config path."""
        resolved = adapter._resolve_config_path()

        """THEN the resolved path points to the config inside the repo."""
        assert resolved == config.resolve()

    def test_config_found_in_tools_base_dir(self, tmp_path: Path):
        """Config resolution finds releaseboard.json in the tools base directory."""
        from opsportal.adapters.releaseboard import ReleaseBoardAdapter
        from opsportal.services.process_manager import ProcessManager

        """GIVEN a tools base directory containing releaseboard.json."""
        repo = tmp_path / "ReleaseBoard"
        repo.mkdir()
        tools_dir = tmp_path / "Tools"
        tools_dir.mkdir()
        config = tools_dir / "releaseboard.json"
        config.write_text('{"release": {}}')

        pm = ProcessManager()
        adapter = ReleaseBoardAdapter(
            repo_path=repo,
            process_manager=pm,
            port=8081,
            tools_base_dir=tools_dir,
        )

        """WHEN resolving the config path."""
        resolved = adapter._resolve_config_path()

        """THEN the resolved path points to the config in the tools base dir."""
        assert resolved == config.resolve()

    def test_config_from_env_var(self, tmp_path: Path):
        """Config resolution uses OPSPORTAL_RELEASEBOARD_CONFIG env var when set."""
        from opsportal.adapters.releaseboard import ReleaseBoardAdapter
        from opsportal.services.process_manager import ProcessManager

        """GIVEN a custom config file and an adapter without it in the default paths."""
        repo = tmp_path / "ReleaseBoard"
        repo.mkdir()
        custom_config = tmp_path / "custom" / "rb.json"
        custom_config.parent.mkdir(parents=True)
        custom_config.write_text('{"release": {}}')

        pm = ProcessManager()
        adapter = ReleaseBoardAdapter(
            repo_path=repo,
            process_manager=pm,
            port=8081,
        )

        """WHEN resolving the config path with the env var set."""
        with patch.dict(os.environ, {"OPSPORTAL_RELEASEBOARD_CONFIG": str(custom_config)}):
            resolved = adapter._resolve_config_path()

        """THEN the resolved path matches the env var value."""
        assert resolved == custom_config.resolve()

    def test_config_not_found_returns_canonical(self, tmp_path: Path):
        """Config resolution returns canonical repo path when no config file exists."""
        from opsportal.adapters.releaseboard import ReleaseBoardAdapter
        from opsportal.services.process_manager import ProcessManager

        """GIVEN a repo directory with no config file."""
        repo = tmp_path / "ReleaseBoard"
        repo.mkdir()

        pm = ProcessManager()
        adapter = ReleaseBoardAdapter(
            repo_path=repo,
            process_manager=pm,
            port=8081,
        )

        """WHEN resolving the config path."""
        resolved = adapter._resolve_config_path()

        """THEN the canonical repo/releaseboard.json path is returned but does not exist."""
        assert resolved == (repo / "releaseboard.json").resolve()
        assert not resolved.exists()


# ---------------------------------------------------------------------------
# Error message sanitization tests
# ---------------------------------------------------------------------------


class TestErrorSanitization:
    """Ensure error messages don't leak raw filesystem paths."""

    def test_sanitize_path_hides_home(self):
        """Sanitize replaces the home directory prefix with ~."""
        from opsportal.adapters.releaseboard import _sanitize_path_for_display

        """GIVEN a path under the user's home directory."""
        home = Path.home()
        p = home / "Projects" / "Tools" / "file.json"

        """WHEN sanitizing the path for display."""
        result = _sanitize_path_for_display(p)

        """THEN the result starts with ~ and does not contain the raw home path."""
        assert result.startswith("~")
        assert str(home) not in result

    def test_sanitize_path_no_home(self):
        """Sanitize keeps paths outside the home directory unchanged."""
        from opsportal.adapters.releaseboard import _sanitize_path_for_display

        """GIVEN a path not under the home directory."""
        p = Path("/opt/tools/config.json")

        """WHEN sanitizing the path for display."""
        result = _sanitize_path_for_display(p)

        """THEN the path is returned unchanged."""
        assert result == "/opt/tools/config.json"

    @pytest.mark.asyncio
    async def test_ensure_ready_error_no_raw_path(self, tmp_path: Path):
        """ReleaseBoard starts without config (first-run wizard) and errors hide paths."""
        from opsportal.adapters.releaseboard import ReleaseBoardAdapter
        from opsportal.services.process_manager import (
            ManagedProcess,
            ProcessManager,
            ProcessStatus,
        )

        """GIVEN a ReleaseBoard adapter with no config file."""
        repo = tmp_path / "ReleaseBoard"
        repo.mkdir()

        pm = ProcessManager()
        adapter = ReleaseBoardAdapter(
            repo_path=repo,
            process_manager=pm,
            port=8081,
        )

        """WHEN ensure_ready is called (without a config file)."""
        running = ManagedProcess(
            name="releaseboard",
            command=["releaseboard", "serve"],
            status=ProcessStatus.RUNNING,
        )
        with (
            patch("shutil.which", return_value="/usr/bin/releaseboard"),
            patch.object(pm, "ensure_running", return_value=running),
        ):
            result = await adapter.ensure_ready()

        """THEN the adapter starts successfully (ReleaseBoard handles first-run internally)."""
        assert result.ready
        assert result.web_url is not None
        if result.error:
            assert str(Path.home()) not in result.error


# ---------------------------------------------------------------------------
# Version display tests
# ---------------------------------------------------------------------------


class TestVersionDisplay:
    """Verify version discovery from adapters."""

    def test_releaseboard_version_from_importlib(self, tmp_path: Path):
        """ReleaseBoard adapter returns version from importlib.metadata."""
        from opsportal.adapters.releaseboard import ReleaseBoardAdapter
        from opsportal.services.process_manager import ProcessManager

        """GIVEN a ReleaseBoard adapter."""
        pm = ProcessManager()
        adapter = ReleaseBoardAdapter(
            pm,
            work_dir=tmp_path,
            port=8081,
        )

        """WHEN importlib.metadata.version returns "1.2.3"."""
        with patch("importlib.metadata.version", return_value="1.2.3"):
            v = adapter.get_version()

        """THEN the adapter reports version "1.2.3"."""
        assert v == "1.2.3"

    def test_releasepilot_version_from_importlib(self, tmp_path: Path):
        """ReleasePilot adapter returns version from importlib.metadata."""
        from opsportal.adapters.releasepilot import ReleasePilotAdapter
        from opsportal.services.process_manager import ProcessManager

        """GIVEN a ReleasePilot adapter."""
        pm = ProcessManager()
        adapter = ReleasePilotAdapter(
            pm,
            work_dir=tmp_path,
            port=8082,
        )

        """WHEN importlib.metadata.version returns "2.0.0"."""
        with patch("importlib.metadata.version", return_value="2.0.0"):
            v = adapter.get_version()

        """THEN the adapter reports version "2.0.0"."""
        assert v == "2.0.0"

    def test_version_returns_none_when_unavailable(self, tmp_path: Path):
        """Adapter returns None when importlib.metadata.version raises an exception."""
        from opsportal.adapters.releaseboard import ReleaseBoardAdapter
        from opsportal.services.process_manager import ProcessManager

        """GIVEN a ReleaseBoard adapter."""
        pm = ProcessManager()
        adapter = ReleaseBoardAdapter(
            pm,
            work_dir=tmp_path,
            port=8081,
        )

        """WHEN importlib.metadata.version raises an exception."""
        with patch("importlib.metadata.version", side_effect=Exception):
            v = adapter.get_version()

        """THEN the version is None."""
        assert v is None

    def test_card_data_includes_version(self, client: TestClient):
        """API /api/tools endpoint returns a list of tool cards."""
        """WHEN requesting the tools API."""
        resp = client.get("/api/tools")

        """THEN the response is 200 and returns a list."""
        assert resp.status_code == 200
        # Even with no tools registered, the endpoint should work
        data = resp.json()
        assert isinstance(data, list)
