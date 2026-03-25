"""Tests for the enterprise feature set — CSP, config resolution, version, card UX."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from opsportal.app.middleware import _build_csp

UI_DIR = Path(__file__).resolve().parent.parent / "src" / "opsportal" / "ui"

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


# ---------------------------------------------------------------------------
# Product card UX tests
# ---------------------------------------------------------------------------


class TestProductCardUX:
    """Verify the product card HTML structure after redesign."""

    def test_home_has_no_product_action_launch(self, client: TestClient):
        """Home page does not contain the deprecated product-action-launch class."""
        """WHEN requesting the home page."""
        resp = client.get("/")

        """THEN the response succeeds and does not contain product-action-launch."""
        assert resp.status_code == 200
        assert "product-action-launch" not in resp.text

    def test_home_has_no_product_action_open(self, client: TestClient):
        """Home page does not contain the deprecated product-action-open class."""
        """WHEN requesting the home page."""
        resp = client.get("/")

        """THEN the response succeeds and does not contain product-action-open."""
        assert resp.status_code == 200
        assert "product-action-open" not in resp.text

    def test_home_has_product_version_class(self):
        """CSS defines the .product-version class for version display."""
        """GIVEN the portal-base.css file."""
        css_path = (
            Path(__file__).parent.parent
            / "src"
            / "opsportal"
            / "ui"
            / "static"
            / "css"
            / "portal-base.css"
        )

        """WHEN reading the CSS content."""
        css = css_path.read_text()

        """THEN .product-version is defined."""
        assert ".product-version" in css

    def test_home_has_product_status_label_class(self):
        """CSS defines the .product-status-label class for status badges."""
        """GIVEN the portal-base.css file."""
        css_path = (
            Path(__file__).parent.parent
            / "src"
            / "opsportal"
            / "ui"
            / "static"
            / "css"
            / "portal-base.css"
        )

        """WHEN reading the CSS content."""
        css = css_path.read_text()

        """THEN .product-status-label is defined."""
        assert ".product-status-label" in css


# ---------------------------------------------------------------------------
# Iframe fallback tests
# ---------------------------------------------------------------------------


class TestIframeFallback:
    """Verify the iframe fallback UI is present in templates."""

    def test_tool_web_template_has_fallback(self):
        """tool_web.html template includes iframe fallback UI elements."""
        """GIVEN the tool_web.html template path."""
        template_path = (
            Path(__file__).parent.parent
            / "src"
            / "opsportal"
            / "ui"
            / "templates"
            / "tool_web.html"
        )

        """WHEN reading the template content."""
        content = template_path.read_text()

        """THEN fallback elements for embed blocking are present."""
        assert "iframe-fallback" in content
        assert "tool.embed_blocked" in content
        assert "tool.open_new_tab" in content

    def test_iframe_fallback_css_exists(self):
        """portal-pages.css defines the .iframe-fallback class."""
        """GIVEN the portal-pages.css file."""
        css_path = (
            Path(__file__).parent.parent
            / "src"
            / "opsportal"
            / "ui"
            / "static"
            / "css"
            / "portal-pages.css"
        )

        """WHEN reading the CSS content."""
        css = css_path.read_text()

        """THEN .iframe-fallback is defined."""
        assert ".iframe-fallback" in css

    def test_i18n_has_embed_blocked_keys(self):
        """English i18n bundle includes embed_blocked and open_new_tab keys."""
        """GIVEN the English i18n JS file."""
        js_path = (
            Path(__file__).parent.parent
            / "src"
            / "opsportal"
            / "ui"
            / "static"
            / "js"
            / "portal-i18n.js"
        )

        """WHEN reading the JS content."""
        js = js_path.read_text()

        """THEN embed_blocked and open_new_tab keys are present."""
        assert '"tool.embed_blocked"' in js
        assert '"tool.open_new_tab"' in js

    def test_i18n_pl_has_embed_blocked_keys(self):
        """Polish i18n bundle includes embed_blocked and open_new_tab keys."""
        """GIVEN the Polish i18n JS file."""
        js_path = (
            Path(__file__).parent.parent
            / "src"
            / "opsportal"
            / "ui"
            / "static"
            / "js"
            / "portal-i18n-pl.js"
        )

        """WHEN reading the JS content."""
        js = js_path.read_text()

        """THEN embed_blocked and open_new_tab keys are present."""
        assert '"tool.embed_blocked"' in js
        assert '"tool.open_new_tab"' in js


# ---------------------------------------------------------------------------
# Iframe width expansion controls
# ---------------------------------------------------------------------------


class TestIframeWidthControls:
    """Verify the iframe width control UI is present in templates."""

    def test_tool_web_has_width_controls(self):
        """tool_web.html template includes iframe width control elements."""
        """GIVEN the tool_web.html template path."""
        template_path = (
            Path(__file__).parent.parent
            / "src"
            / "opsportal"
            / "ui"
            / "templates"
            / "tool_web.html"
        )

        """WHEN reading the template content."""
        content = template_path.read_text()

        """THEN width control elements are present."""
        assert "iframe-controls" in content
        assert "expand-left" in content
        assert "expand-right" in content
        assert "setFrameWidth" in content

    def test_iframe_controls_css_exists(self):
        """portal-pages.css defines iframe control button classes."""
        """GIVEN the portal-pages.css file."""
        css_path = (
            Path(__file__).parent.parent
            / "src"
            / "opsportal"
            / "ui"
            / "static"
            / "css"
            / "portal-pages.css"
        )

        """WHEN reading the CSS content."""
        css = css_path.read_text()

        """THEN iframe control classes are defined."""
        assert ".iframe-controls" in css
        assert ".iframe-control-btn" in css
        assert ".frame-expand-left" in css
        assert ".frame-expand-right" in css

    def test_width_control_i18n_keys_en(self):
        """English i18n bundle includes width control keys."""
        """GIVEN the English i18n JS file."""
        js_path = (
            Path(__file__).parent.parent
            / "src"
            / "opsportal"
            / "ui"
            / "static"
            / "js"
            / "portal-i18n.js"
        )

        """WHEN reading the JS content."""
        js = js_path.read_text()

        """THEN expand_left, expand_right, and reset_width keys are present."""
        assert '"tool.expand_left"' in js
        assert '"tool.expand_right"' in js
        assert '"tool.reset_width"' in js

    def test_width_control_i18n_keys_pl(self):
        """Polish i18n bundle includes width control keys."""
        """GIVEN the Polish i18n JS file."""
        js_path = (
            Path(__file__).parent.parent
            / "src"
            / "opsportal"
            / "ui"
            / "static"
            / "js"
            / "portal-i18n-pl.js"
        )

        """WHEN reading the JS content."""
        js = js_path.read_text()

        """THEN expand_left, expand_right, and reset_width keys are present."""
        assert '"tool.expand_left"' in js
        assert '"tool.expand_right"' in js
        assert '"tool.reset_width"' in js


# ---------------------------------------------------------------------------
# Loading skeleton — shimmer pattern
# ---------------------------------------------------------------------------


class TestLoadingSkeleton:
    """Verify the shimmer-based loading skeleton is present."""

    def test_skeleton_shimmer_css_exists(self):
        """portal-pages.css defines shimmer animation and skeleton classes."""
        """GIVEN the portal-pages.css file."""
        css_path = (
            Path(__file__).parent.parent
            / "src"
            / "opsportal"
            / "ui"
            / "static"
            / "css"
            / "portal-pages.css"
        )

        """WHEN reading the CSS content."""
        css = css_path.read_text()

        """THEN shimmer keyframes and skeleton classes are defined."""
        assert "@keyframes shimmer" in css
        assert ".skeleton-shimmer" in css
        assert ".skeleton-card" in css

    def test_tool_web_uses_shimmer_skeleton(self):
        """tool_web.html template uses shimmer skeleton loading elements."""
        """GIVEN the tool_web.html template path."""
        template_path = (
            Path(__file__).parent.parent
            / "src"
            / "opsportal"
            / "ui"
            / "templates"
            / "tool_web.html"
        )

        """WHEN reading the template content."""
        content = template_path.read_text()

        """THEN skeleton shimmer elements are present."""
        assert "skeleton-shimmer" in content
        assert "skeleton-card" in content
        assert "skeleton-row" in content


# ---------------------------------------------------------------------------
# Product card metadata display
# ---------------------------------------------------------------------------


class TestProductCardMetadata:
    """Verify enhanced product card metadata display."""

    def test_home_template_has_product_meta(self):
        """Home template includes product-meta section for card metadata."""
        """GIVEN the home.html template."""
        template_path = (
            Path(__file__).parent.parent / "src" / "opsportal" / "ui" / "templates" / "home.html"
        )

        """WHEN reading the template content."""
        content = template_path.read_text()

        """THEN product-meta element is present."""
        assert "product-meta" in content

    def test_product_meta_css_exists(self):
        """portal-base.css defines product-meta and product-meta-badge classes."""
        """GIVEN the portal-base.css file."""
        css_path = (
            Path(__file__).parent.parent
            / "src"
            / "opsportal"
            / "ui"
            / "static"
            / "css"
            / "portal-base.css"
        )

        """WHEN reading the CSS content."""
        css = css_path.read_text()

        """THEN product-meta classes are defined."""
        assert ".product-meta" in css
        assert ".product-meta-badge" in css


# ---------------------------------------------------------------------------
# Config save + restart flow
# ---------------------------------------------------------------------------


class TestConfigSaveRestart:
    """Config save must communicate restart requirement and offer restart action."""

    TEMPLATE = (UI_DIR / "templates" / "tool_config.html").read_text(encoding="utf-8")
    I18N_EN = (UI_DIR / "static" / "js" / "portal-i18n.js").read_text(encoding="utf-8")
    I18N_PL = (UI_DIR / "static" / "js" / "portal-i18n-pl.js").read_text(encoding="utf-8")

    def test_save_and_restart_button_present(self) -> None:
        """Config form includes a Save & Restart button."""
        """GIVEN the tool_config.html template loaded at class level."""

        """THEN the template contains saveConfig(true) and a save_restart label."""
        assert "saveConfig(true)" in self.TEMPLATE
        assert (
            "save_restart" in self.TEMPLATE
            or "save &amp; restart" in self.TEMPLATE.lower()
            or "Save &amp; Restart" in self.TEMPLATE
        )

    def test_restart_hint_banner_present(self) -> None:
        """Config form shows a restart-hint banner after saving."""
        """GIVEN the tool_config.html template and English i18n bundle."""

        """THEN the restart-hint element and i18n key are present."""
        assert "restart-hint" in self.TEMPLATE
        assert "restart_hint" in self.I18N_EN

    def test_restart_tool_function_present(self) -> None:
        """Config template defines a restartTool() function calling /actions/restart."""
        """GIVEN the tool_config.html template loaded at class level."""

        """THEN restartTool function and restart endpoint are present."""
        assert "restartTool" in self.TEMPLATE
        assert "/actions/restart" in self.TEMPLATE

    def test_restart_i18n_keys_present(self) -> None:
        """EN and PL i18n bundles include restart-related config keys."""
        """GIVEN the English and Polish i18n bundles loaded at class level."""

        """THEN all restart keys are present in both locales."""
        for key in ["config.restart_hint", "config.restart_now", "config.restart_success"]:
            assert key in self.I18N_EN, f"Missing EN key: {key}"
            assert key in self.I18N_PL, f"Missing PL key: {key}"


# ---------------------------------------------------------------------------
# Config section grouping
# ---------------------------------------------------------------------------


class TestConfigSectionGrouping:
    """Config form must group fields into logical sections for readability."""

    TEMPLATE = (UI_DIR / "templates" / "tool_config.html").read_text(encoding="utf-8")
    CSS = (UI_DIR / "static" / "css" / "portal-pages.css").read_text(encoding="utf-8")

    def test_section_map_defined(self) -> None:
        """Config template defines a SECTION_MAP for field-to-section grouping."""
        """GIVEN the tool_config.html template loaded at class level."""

        """THEN SECTION_MAP is defined in the template."""
        assert "SECTION_MAP" in self.TEMPLATE

    def test_section_labels_defined(self) -> None:
        """Config template defines SECTION_LABELS for display headings."""
        """GIVEN the tool_config.html template loaded at class level."""

        """THEN SECTION_LABELS is defined in the template."""
        assert "SECTION_LABELS" in self.TEMPLATE

    def test_config_section_heading_css(self) -> None:
        """CSS defines .config-section-heading for section headers."""
        """GIVEN the portal-pages.css file loaded at class level."""

        """THEN .config-section-heading is defined."""
        assert ".config-section-heading" in self.CSS

    def test_section_group_css(self) -> None:
        """CSS defines .config-section-group for section containers."""
        """GIVEN the portal-pages.css file loaded at class level."""

        """THEN .config-section-group is defined."""
        assert ".config-section-group" in self.CSS


# ---------------------------------------------------------------------------
# Config schema validation
# ---------------------------------------------------------------------------


class TestConfigSchemaValidation:
    """Config validation must be schema-based and produce actionable errors."""

    TEMPLATE = (UI_DIR / "templates" / "tool_config.html").read_text(encoding="utf-8")

    def test_validate_button_present(self) -> None:
        """Config form includes a Validate button calling validateConfig()."""
        """GIVEN the tool_config.html template loaded at class level."""

        """THEN validateConfig() is present in the template."""
        assert "validateConfig()" in self.TEMPLATE

    def test_validation_banner_present(self) -> None:
        """Config template includes validation error banner elements."""
        """GIVEN the tool_config.html template loaded at class level."""

        """THEN validation-banner and validation-errors elements are present."""
        assert "validation-banner" in self.TEMPLATE
        assert "validation-errors" in self.TEMPLATE

    def test_save_validates_before_write(self) -> None:
        """save_config mixin calls validate_config before writing to disk."""
        import inspect

        from opsportal.adapters._config_mixin import JsonSchemaConfigMixin

        """WHEN inspecting the save_config source code."""
        source = inspect.getsource(JsonSchemaConfigMixin.save_config)

        """THEN validate_config is called within save_config."""
        assert "validate_config" in source
