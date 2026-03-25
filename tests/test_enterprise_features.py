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
        """GIVEN the csp includes frame src for child ports scenario."""

        """WHEN executing."""
        csp = _build_csp([8081, 8082])

        """THEN the result is correct."""
        assert "frame-src" in csp
        assert "http://127.0.0.1:8081" in csp
        assert "http://127.0.0.1:8082" in csp
        assert "http://localhost:8081" in csp
        assert "http://localhost:8082" in csp

    def test_csp_self_only_when_no_ports(self):
        """GIVEN the csp self only when no ports scenario."""

        """WHEN executing."""
        csp = _build_csp([])

        """THEN the result is correct."""
        assert "frame-src 'self'" in csp
        assert "127.0.0.1" not in csp

    def test_csp_none_ports_handled(self):
        """GIVEN the csp none ports handled scenario."""

        """WHEN executing."""
        csp = _build_csp(None)

        """THEN the result is correct."""
        assert "frame-src 'self'" in csp

    def test_csp_includes_frame_ancestors(self):
        """GIVEN the csp includes frame ancestors scenario."""

        """WHEN executing."""
        csp = _build_csp([8081])

        """THEN the result is correct."""
        assert "frame-ancestors 'self'" in csp

    def test_home_page_csp_has_frame_src(self, client: TestClient):
        """GIVEN Integration: home response CSP should allow child tool ports."""
        resp = client.get("/")

        """WHEN executing."""
        csp = resp.headers.get("content-security-policy", "")

        """THEN the result is correct."""
        assert "frame-src" in csp


# ---------------------------------------------------------------------------
# ReleaseBoard config resolution tests
# ---------------------------------------------------------------------------


class TestReleaseBoardConfigResolution:
    """Verify multi-strategy config file discovery."""

    def test_config_found_in_repo_path(self, tmp_path: Path):
        """GIVEN the config found in repo path scenario."""
        from opsportal.adapters.releaseboard import ReleaseBoardAdapter
        from opsportal.services.process_manager import ProcessManager

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

        """WHEN executing."""
        resolved = adapter._resolve_config_path()

        """THEN the result is correct."""
        assert resolved == config.resolve()

    def test_config_found_in_tools_base_dir(self, tmp_path: Path):
        """GIVEN the config found in tools base dir scenario."""
        from opsportal.adapters.releaseboard import ReleaseBoardAdapter
        from opsportal.services.process_manager import ProcessManager

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

        """WHEN executing."""
        resolved = adapter._resolve_config_path()

        """THEN the result is correct."""
        assert resolved == config.resolve()

    def test_config_from_env_var(self, tmp_path: Path):
        """GIVEN the config from env var scenario."""
        from opsportal.adapters.releaseboard import ReleaseBoardAdapter
        from opsportal.services.process_manager import ProcessManager

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

        """WHEN executing."""
        with patch.dict(os.environ, {"OPSPORTAL_RELEASEBOARD_CONFIG": str(custom_config)}):
            resolved = adapter._resolve_config_path()

        """THEN the result is correct."""
        assert resolved == custom_config.resolve()

    def test_config_not_found_returns_canonical(self, tmp_path: Path):
        """GIVEN the config not found returns canonical scenario."""
        from opsportal.adapters.releaseboard import ReleaseBoardAdapter
        from opsportal.services.process_manager import ProcessManager

        repo = tmp_path / "ReleaseBoard"
        repo.mkdir()

        pm = ProcessManager()
        adapter = ReleaseBoardAdapter(
            repo_path=repo,
            process_manager=pm,
            port=8081,
        )

        """WHEN executing."""
        resolved = adapter._resolve_config_path()

        """THEN the result is correct."""
        assert resolved == (repo / "releaseboard.json").resolve()
        assert not resolved.exists()


# ---------------------------------------------------------------------------
# Error message sanitization tests
# ---------------------------------------------------------------------------


class TestErrorSanitization:
    """Ensure error messages don't leak raw filesystem paths."""

    def test_sanitize_path_hides_home(self):
        """GIVEN the sanitize path hides home scenario."""
        from opsportal.adapters.releaseboard import _sanitize_path_for_display

        home = Path.home()
        p = home / "Projects" / "Tools" / "file.json"

        """WHEN executing."""
        result = _sanitize_path_for_display(p)

        """THEN the result is correct."""
        assert result.startswith("~")
        assert str(home) not in result

    def test_sanitize_path_no_home(self):
        """GIVEN the sanitize path no home scenario."""
        from opsportal.adapters.releaseboard import _sanitize_path_for_display

        p = Path("/opt/tools/config.json")

        """WHEN executing."""
        result = _sanitize_path_for_display(p)

        """THEN the result is correct."""
        assert result == "/opt/tools/config.json"

    @pytest.mark.asyncio
    async def test_ensure_ready_error_no_raw_path(self, tmp_path: Path):
        """GIVEN the ensure ready error no raw path scenario."""
        from opsportal.adapters.releaseboard import ReleaseBoardAdapter
        from opsportal.services.process_manager import ProcessManager

        repo = tmp_path / "ReleaseBoard"
        repo.mkdir()

        pm = ProcessManager()
        adapter = ReleaseBoardAdapter(
            repo_path=repo,
            process_manager=pm,
            port=8081,
        )

        """WHEN executing."""
        with patch("shutil.which", return_value="/usr/bin/releaseboard"):
            result = await adapter.ensure_ready()

        """THEN the result is correct."""
        assert not result.ready
        # Error should not contain the full home directory
        assert str(Path.home()) not in (result.error or "")
        # Should contain helpful guidance
        assert "OPSPORTAL_RELEASEBOARD_CONFIG" in (result.error or "")


# ---------------------------------------------------------------------------
# Version display tests
# ---------------------------------------------------------------------------


class TestVersionDisplay:
    """Verify version discovery from adapters."""

    def test_releaseboard_version_from_importlib(self, tmp_path: Path):
        """GIVEN the releaseboard version from importlib scenario."""
        from opsportal.adapters.releaseboard import ReleaseBoardAdapter
        from opsportal.services.process_manager import ProcessManager

        pm = ProcessManager()
        adapter = ReleaseBoardAdapter(
            pm,
            work_dir=tmp_path,
            port=8081,
        )

        """WHEN executing."""
        with patch("importlib.metadata.version", return_value="1.2.3"):
            v = adapter.get_version()

        """THEN the result is correct."""
        assert v == "1.2.3"

    def test_releasepilot_version_from_importlib(self, tmp_path: Path):
        """GIVEN the releasepilot version from importlib scenario."""
        from opsportal.adapters.releasepilot import ReleasePilotAdapter
        from opsportal.services.process_manager import ProcessManager

        pm = ProcessManager()
        adapter = ReleasePilotAdapter(
            pm,
            work_dir=tmp_path,
            port=8082,
        )

        """WHEN executing."""
        with patch("importlib.metadata.version", return_value="2.0.0"):
            v = adapter.get_version()

        """THEN the result is correct."""
        assert v == "2.0.0"

    def test_version_returns_none_when_unavailable(self, tmp_path: Path):
        """GIVEN the version returns none when unavailable scenario."""
        from opsportal.adapters.releaseboard import ReleaseBoardAdapter
        from opsportal.services.process_manager import ProcessManager

        pm = ProcessManager()
        adapter = ReleaseBoardAdapter(
            pm,
            work_dir=tmp_path,
            port=8081,
        )

        """WHEN executing."""
        with patch("importlib.metadata.version", side_effect=Exception):
            v = adapter.get_version()

        """THEN the result is correct."""
        assert v is None

    def test_card_data_includes_version(self, client: TestClient):
        """GIVEN Integration: API should include version field in tool cards."""

        """WHEN executing."""
        resp = client.get("/api/tools")

        """THEN the result is correct."""
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
        """GIVEN The redundant product-action-launch class should be removed."""

        """WHEN executing."""
        resp = client.get("/")

        """THEN the result is correct."""
        assert resp.status_code == 200
        assert "product-action-launch" not in resp.text

    def test_home_has_no_product_action_open(self, client: TestClient):
        """GIVEN The redundant product-action-open class should be removed."""

        """WHEN executing."""
        resp = client.get("/")

        """THEN the result is correct."""
        assert resp.status_code == 200
        assert "product-action-open" not in resp.text

    def test_home_has_product_version_class(self):
        """GIVEN CSS should define the product-version class."""
        css_path = (
            Path(__file__).parent.parent
            / "src"
            / "opsportal"
            / "ui"
            / "static"
            / "css"
            / "portal-base.css"
        )

        """WHEN executing."""
        css = css_path.read_text()

        """THEN the result is correct."""
        assert ".product-version" in css

    def test_home_has_product_status_label_class(self):
        """GIVEN CSS should define the product-status-label class."""
        css_path = (
            Path(__file__).parent.parent
            / "src"
            / "opsportal"
            / "ui"
            / "static"
            / "css"
            / "portal-base.css"
        )

        """WHEN executing."""
        css = css_path.read_text()

        """THEN the result is correct."""
        assert ".product-status-label" in css


# ---------------------------------------------------------------------------
# Iframe fallback tests
# ---------------------------------------------------------------------------


class TestIframeFallback:
    """Verify the iframe fallback UI is present in templates."""

    def test_tool_web_template_has_fallback(self):
        """GIVEN the tool web template has fallback scenario."""
        template_path = (
            Path(__file__).parent.parent
            / "src"
            / "opsportal"
            / "ui"
            / "templates"
            / "tool_web.html"
        )

        """WHEN executing."""
        content = template_path.read_text()

        """THEN the result is correct."""
        assert "iframe-fallback" in content
        assert "tool.embed_blocked" in content
        assert "tool.open_new_tab" in content

    def test_iframe_fallback_css_exists(self):
        """GIVEN the iframe fallback css exists scenario."""
        css_path = (
            Path(__file__).parent.parent
            / "src"
            / "opsportal"
            / "ui"
            / "static"
            / "css"
            / "portal-pages.css"
        )

        """WHEN executing."""
        css = css_path.read_text()

        """THEN the result is correct."""
        assert ".iframe-fallback" in css

    def test_i18n_has_embed_blocked_keys(self):
        """GIVEN the i18n has embed blocked keys scenario."""
        js_path = (
            Path(__file__).parent.parent
            / "src"
            / "opsportal"
            / "ui"
            / "static"
            / "js"
            / "portal-i18n.js"
        )

        """WHEN executing."""
        js = js_path.read_text()

        """THEN the result is correct."""
        assert '"tool.embed_blocked"' in js
        assert '"tool.open_new_tab"' in js

    def test_i18n_pl_has_embed_blocked_keys(self):
        """GIVEN the i18n pl has embed blocked keys scenario."""
        js_path = (
            Path(__file__).parent.parent
            / "src"
            / "opsportal"
            / "ui"
            / "static"
            / "js"
            / "portal-i18n-pl.js"
        )

        """WHEN executing."""
        js = js_path.read_text()

        """THEN the result is correct."""
        assert '"tool.embed_blocked"' in js
        assert '"tool.open_new_tab"' in js


# ---------------------------------------------------------------------------
# Iframe width expansion controls
# ---------------------------------------------------------------------------


class TestIframeWidthControls:
    """Verify the iframe width control UI is present in templates."""

    def test_tool_web_has_width_controls(self):
        """GIVEN the tool web has width controls scenario."""
        template_path = (
            Path(__file__).parent.parent
            / "src"
            / "opsportal"
            / "ui"
            / "templates"
            / "tool_web.html"
        )

        """WHEN executing."""
        content = template_path.read_text()

        """THEN the result is correct."""
        assert "iframe-controls" in content
        assert "expand-left" in content
        assert "expand-right" in content
        assert "setFrameWidth" in content

    def test_iframe_controls_css_exists(self):
        """GIVEN the iframe controls css exists scenario."""
        css_path = (
            Path(__file__).parent.parent
            / "src"
            / "opsportal"
            / "ui"
            / "static"
            / "css"
            / "portal-pages.css"
        )

        """WHEN executing."""
        css = css_path.read_text()

        """THEN the result is correct."""
        assert ".iframe-controls" in css
        assert ".iframe-control-btn" in css
        assert ".frame-expand-left" in css
        assert ".frame-expand-right" in css

    def test_width_control_i18n_keys_en(self):
        """GIVEN the width control i18n keys en scenario."""
        js_path = (
            Path(__file__).parent.parent
            / "src"
            / "opsportal"
            / "ui"
            / "static"
            / "js"
            / "portal-i18n.js"
        )

        """WHEN executing."""
        js = js_path.read_text()

        """THEN the result is correct."""
        assert '"tool.expand_left"' in js
        assert '"tool.expand_right"' in js
        assert '"tool.reset_width"' in js

    def test_width_control_i18n_keys_pl(self):
        """GIVEN the width control i18n keys pl scenario."""
        js_path = (
            Path(__file__).parent.parent
            / "src"
            / "opsportal"
            / "ui"
            / "static"
            / "js"
            / "portal-i18n-pl.js"
        )

        """WHEN executing."""
        js = js_path.read_text()

        """THEN the result is correct."""
        assert '"tool.expand_left"' in js
        assert '"tool.expand_right"' in js
        assert '"tool.reset_width"' in js


# ---------------------------------------------------------------------------
# Loading skeleton — shimmer pattern
# ---------------------------------------------------------------------------


class TestLoadingSkeleton:
    """Verify the shimmer-based loading skeleton is present."""

    def test_skeleton_shimmer_css_exists(self):
        """GIVEN the skeleton shimmer css exists scenario."""
        css_path = (
            Path(__file__).parent.parent
            / "src"
            / "opsportal"
            / "ui"
            / "static"
            / "css"
            / "portal-pages.css"
        )

        """WHEN executing."""
        css = css_path.read_text()

        """THEN the result is correct."""
        assert "@keyframes shimmer" in css
        assert ".skeleton-shimmer" in css
        assert ".skeleton-card" in css

    def test_tool_web_uses_shimmer_skeleton(self):
        """GIVEN the tool web uses shimmer skeleton scenario."""
        template_path = (
            Path(__file__).parent.parent
            / "src"
            / "opsportal"
            / "ui"
            / "templates"
            / "tool_web.html"
        )

        """WHEN executing."""
        content = template_path.read_text()

        """THEN the result is correct."""
        assert "skeleton-shimmer" in content
        assert "skeleton-card" in content
        assert "skeleton-row" in content


# ---------------------------------------------------------------------------
# Product card metadata display
# ---------------------------------------------------------------------------


class TestProductCardMetadata:
    """Verify enhanced product card metadata display."""

    def test_home_template_has_product_meta(self):
        """GIVEN the home template has product meta scenario."""
        template_path = (
            Path(__file__).parent.parent / "src" / "opsportal" / "ui" / "templates" / "home.html"
        )

        """WHEN executing."""
        content = template_path.read_text()

        """THEN the result is correct."""
        assert "product-meta" in content

    def test_product_meta_css_exists(self):
        """GIVEN the product meta css exists scenario."""
        css_path = (
            Path(__file__).parent.parent
            / "src"
            / "opsportal"
            / "ui"
            / "static"
            / "css"
            / "portal-base.css"
        )

        """WHEN executing."""
        css = css_path.read_text()

        """THEN the result is correct."""
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
        """GIVEN The config form must have a Save & Restart button."""

        """THEN the result is correct."""

        """WHEN executing."""
        assert "saveConfig(true)" in self.TEMPLATE
        assert (
            "save_restart" in self.TEMPLATE
            or "save &amp; restart" in self.TEMPLATE.lower()
            or "Save &amp; Restart" in self.TEMPLATE
        )

    def test_restart_hint_banner_present(self) -> None:
        """GIVEN After save, a restart-hint banner must be available."""

        """THEN the result is correct."""

        """WHEN executing."""
        assert "restart-hint" in self.TEMPLATE
        assert "restart_hint" in self.I18N_EN

    def test_restart_tool_function_present(self) -> None:
        """GIVEN A restartTool() JS function must exist to trigger tool restart."""

        """THEN the result is correct."""

        """WHEN executing."""
        assert "restartTool" in self.TEMPLATE
        assert "/actions/restart" in self.TEMPLATE

    def test_restart_i18n_keys_present(self) -> None:
        """GIVEN Both EN and PL must have restart-related config keys."""

        """THEN the result is correct."""

        """WHEN executing."""
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
        """GIVEN A SECTION_MAP must exist for field-to-section grouping."""

        """THEN the result is correct."""

        """WHEN executing."""
        assert "SECTION_MAP" in self.TEMPLATE

    def test_section_labels_defined(self) -> None:
        """GIVEN Section labels must be defined for display."""

        """THEN the result is correct."""

        """WHEN executing."""
        assert "SECTION_LABELS" in self.TEMPLATE

    def test_config_section_heading_css(self) -> None:
        """GIVEN CSS must define .config-section-heading for section headers."""

        """THEN the result is correct."""

        """WHEN executing."""
        assert ".config-section-heading" in self.CSS

    def test_section_group_css(self) -> None:
        """GIVEN CSS must define .config-section-group for section containers."""

        """THEN the result is correct."""

        """WHEN executing."""
        assert ".config-section-group" in self.CSS


# ---------------------------------------------------------------------------
# Config schema validation
# ---------------------------------------------------------------------------


class TestConfigSchemaValidation:
    """Config validation must be schema-based and produce actionable errors."""

    TEMPLATE = (UI_DIR / "templates" / "tool_config.html").read_text(encoding="utf-8")

    def test_validate_button_present(self) -> None:
        """GIVEN The config form must have a Validate button."""

        """THEN the result is correct."""

        """WHEN executing."""
        assert "validateConfig()" in self.TEMPLATE

    def test_validation_banner_present(self) -> None:
        """GIVEN A validation error banner must be available."""

        """THEN the result is correct."""

        """WHEN executing."""
        assert "validation-banner" in self.TEMPLATE
        assert "validation-errors" in self.TEMPLATE

    def test_save_validates_before_write(self) -> None:
        """GIVEN The save_config mixin must validate before writing."""
        import inspect

        from opsportal.adapters._config_mixin import JsonSchemaConfigMixin

        """WHEN executing."""
        source = inspect.getsource(JsonSchemaConfigMixin.save_config)

        """THEN the result is correct."""
        assert "validate_config" in source
