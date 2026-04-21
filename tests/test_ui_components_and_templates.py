"""Tests for enterprise UI - product cards, iframe fallback/width, skeleton, config UX."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

UI_DIR = Path(__file__).resolve().parent.parent / "src" / "opsportal" / "ui"


# ---------------------------------------------------------------------------
# Product card UX tests
# ---------------------------------------------------------------------------


class TestProductCardUX:
    """Verify the product card HTML structure after redesign."""

    """GIVEN a running OpsPortal app"""

    def test_home_has_no_product_action_launch(self, client: TestClient):
        """WHEN requesting the home page"""
        resp = client.get("/")

        """THEN the response succeeds and does not contain product-action-launch"""
        assert resp.status_code == 200
        assert "product-action-launch" not in resp.text

    """GIVEN a running OpsPortal app"""

    def test_home_has_no_product_action_open(self, client: TestClient):
        """WHEN requesting the home page"""
        resp = client.get("/")

        """THEN the response succeeds and does not contain product-action-open"""
        assert resp.status_code == 200
        assert "product-action-open" not in resp.text

    """GIVEN the portal-base.css file"""

    def test_home_has_product_version_class(self):
        css_path = (
            Path(__file__).parent.parent
            / "src"
            / "opsportal"
            / "ui"
            / "static"
            / "css"
            / "portal-base.css"
        )

        """WHEN reading the CSS content"""
        css = css_path.read_text()

        """THEN .product-version is defined"""
        assert ".product-version" in css

    """GIVEN the portal-base.css file"""

    def test_home_has_product_status_label_class(self):
        css_path = (
            Path(__file__).parent.parent
            / "src"
            / "opsportal"
            / "ui"
            / "static"
            / "css"
            / "portal-base.css"
        )

        """WHEN reading the CSS content"""
        css = css_path.read_text()

        """THEN .product-status-label is defined"""
        assert ".product-status-label" in css


# ---------------------------------------------------------------------------
# Iframe fallback tests
# ---------------------------------------------------------------------------


class TestIframeFallback:
    """Verify the iframe fallback UI is present in templates."""

    """GIVEN the tool_web.html template path"""

    def test_tool_web_template_has_fallback(self):
        template_path = (
            Path(__file__).parent.parent
            / "src"
            / "opsportal"
            / "ui"
            / "templates"
            / "tool_web.html"
        )

        """WHEN reading the template content"""
        content = template_path.read_text()

        """THEN fallback elements for embed blocking are present"""
        assert "iframe-fallback" in content
        assert "tool.embed_blocked" in content
        assert "tool.open_new_tab" in content

    """GIVEN the portal-pages.css file"""

    def test_iframe_fallback_css_exists(self):
        css_path = (
            Path(__file__).parent.parent
            / "src"
            / "opsportal"
            / "ui"
            / "static"
            / "css"
            / "portal-pages.css"
        )

        """WHEN reading the CSS content"""
        css = css_path.read_text()

        """THEN .iframe-fallback is defined"""
        assert ".iframe-fallback" in css

    """GIVEN the English i18n JS file"""

    def test_i18n_has_embed_blocked_keys(self):
        js_path = (
            Path(__file__).parent.parent
            / "src"
            / "opsportal"
            / "ui"
            / "static"
            / "js"
            / "portal-i18n.js"
        )

        """WHEN reading the JS content"""
        js = js_path.read_text()

        """THEN embed_blocked and open_new_tab keys are present"""
        assert '"tool.embed_blocked"' in js
        assert '"tool.open_new_tab"' in js

    """GIVEN the Polish i18n JS file"""

    def test_i18n_pl_has_embed_blocked_keys(self):
        js_path = (
            Path(__file__).parent.parent
            / "src"
            / "opsportal"
            / "ui"
            / "static"
            / "js"
            / "portal-i18n-pl.js"
        )

        """WHEN reading the JS content"""
        js = js_path.read_text()

        """THEN embed_blocked and open_new_tab keys are present"""
        assert '"tool.embed_blocked"' in js
        assert '"tool.open_new_tab"' in js


# ---------------------------------------------------------------------------
# Iframe width expansion controls
# ---------------------------------------------------------------------------


class TestIframeWidthControls:
    """Verify the iframe width control UI is present in templates."""

    """GIVEN the tool_web.html template path"""

    def test_tool_web_has_width_controls(self):
        template_path = (
            Path(__file__).parent.parent
            / "src"
            / "opsportal"
            / "ui"
            / "templates"
            / "tool_web.html"
        )

        """WHEN reading the template content"""
        content = template_path.read_text()

        """THEN width control elements are present"""
        assert "iframe-controls" in content
        assert "expand-left" in content
        assert "expand-right" in content
        assert "setFrameWidth" in content

    """GIVEN the portal-pages.css file"""

    def test_iframe_controls_css_exists(self):
        css_path = (
            Path(__file__).parent.parent
            / "src"
            / "opsportal"
            / "ui"
            / "static"
            / "css"
            / "portal-pages.css"
        )

        """WHEN reading the CSS content"""
        css = css_path.read_text()

        """THEN iframe control classes are defined"""
        assert ".iframe-controls" in css
        assert ".iframe-control-btn" in css
        assert ".frame-expand-left" in css
        assert ".frame-expand-right" in css

    """GIVEN the English i18n JS file"""

    def test_width_control_i18n_keys_en(self):
        js_path = (
            Path(__file__).parent.parent
            / "src"
            / "opsportal"
            / "ui"
            / "static"
            / "js"
            / "portal-i18n.js"
        )

        """WHEN reading the JS content"""
        js = js_path.read_text()

        """THEN expand_left, expand_right, and reset_width keys are present"""
        assert '"tool.expand_left"' in js
        assert '"tool.expand_right"' in js
        assert '"tool.reset_width"' in js

    """GIVEN the Polish i18n JS file"""

    def test_width_control_i18n_keys_pl(self):
        js_path = (
            Path(__file__).parent.parent
            / "src"
            / "opsportal"
            / "ui"
            / "static"
            / "js"
            / "portal-i18n-pl.js"
        )

        """WHEN reading the JS content"""
        js = js_path.read_text()

        """THEN expand_left, expand_right, and reset_width keys are present"""
        assert '"tool.expand_left"' in js
        assert '"tool.expand_right"' in js
        assert '"tool.reset_width"' in js


# ---------------------------------------------------------------------------
# Loading skeleton - shimmer pattern
# ---------------------------------------------------------------------------


class TestLoadingSkeleton:
    """Verify the shimmer-based loading skeleton is present."""

    """GIVEN the portal-pages.css file"""

    def test_skeleton_shimmer_css_exists(self):
        css_path = (
            Path(__file__).parent.parent
            / "src"
            / "opsportal"
            / "ui"
            / "static"
            / "css"
            / "portal-pages.css"
        )

        """WHEN reading the CSS content"""
        css = css_path.read_text()

        """THEN shimmer keyframes and skeleton classes are defined"""
        assert "@keyframes shimmer" in css
        assert ".skeleton-shimmer" in css
        assert ".skeleton-card" in css

    """GIVEN the tool_web.html template path"""

    def test_tool_web_uses_shimmer_skeleton(self):
        template_path = (
            Path(__file__).parent.parent
            / "src"
            / "opsportal"
            / "ui"
            / "templates"
            / "tool_web.html"
        )

        """WHEN reading the template content"""
        content = template_path.read_text()

        """THEN skeleton shimmer elements are present"""
        assert "skeleton-shimmer" in content
        assert "skeleton-card" in content
        assert "skeleton-row" in content


# ---------------------------------------------------------------------------
# Product card metadata display
# ---------------------------------------------------------------------------


class TestProductCardMetadata:
    """Verify enhanced product card metadata display."""

    """GIVEN the home.html template"""

    def test_home_template_has_product_meta(self):
        template_path = (
            Path(__file__).parent.parent / "src" / "opsportal" / "ui" / "templates" / "home.html"
        )

        """WHEN reading the template content"""
        content = template_path.read_text()

        """THEN product-meta element is present"""
        assert "product-meta" in content

    """GIVEN the portal-base.css file"""

    def test_product_meta_css_exists(self):
        css_path = (
            Path(__file__).parent.parent
            / "src"
            / "opsportal"
            / "ui"
            / "static"
            / "css"
            / "portal-base.css"
        )

        """WHEN reading the CSS content"""
        css = css_path.read_text()

        """THEN product-meta classes are defined"""
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

    """GIVEN the tool_config.html template loaded at class level"""

    def test_save_and_restart_button_present(self) -> None:
        """WHEN inspecting the template content"""

        """THEN the template contains saveConfig(true) and a save_restart label"""
        assert "saveConfig(true)" in self.TEMPLATE
        assert (
            "save_restart" in self.TEMPLATE
            or "save &amp; restart" in self.TEMPLATE.lower()
            or "Save &amp; Restart" in self.TEMPLATE
        )

    """GIVEN the tool_config.html template and English i18n bundle"""

    def test_restart_hint_banner_present(self) -> None:
        """WHEN inspecting the template and i18n content"""

        """THEN the restart-hint element and i18n key are present"""
        assert "restart-hint" in self.TEMPLATE
        assert "restart_hint" in self.I18N_EN

    """GIVEN the tool_config.html template loaded at class level"""

    def test_restart_tool_function_present(self) -> None:
        """WHEN inspecting the template content"""

        """THEN restartTool function and restart endpoint are present"""
        assert "restartTool" in self.TEMPLATE
        assert "/actions/restart" in self.TEMPLATE

    """GIVEN the English and Polish i18n bundles loaded at class level"""

    def test_restart_i18n_keys_present(self) -> None:
        """WHEN inspecting i18n keys"""

        """THEN all restart keys are present in both locales"""
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

    """GIVEN the tool_config.html template loaded at class level"""

    def test_section_map_defined(self) -> None:
        """WHEN inspecting the template content"""

        """THEN SECTION_MAP is defined in the template"""
        assert "SECTION_MAP" in self.TEMPLATE

    """GIVEN the tool_config.html template loaded at class level"""

    def test_section_labels_defined(self) -> None:
        """WHEN inspecting the template content"""

        """THEN SECTION_LABELS is defined in the template"""
        assert "SECTION_LABELS" in self.TEMPLATE

    """GIVEN the portal-pages.css file loaded at class level"""

    def test_config_section_heading_css(self) -> None:
        """WHEN inspecting the CSS content"""

        """THEN .config-section-heading is defined"""
        assert ".config-section-heading" in self.CSS

    """GIVEN the portal-pages.css file loaded at class level"""

    def test_section_group_css(self) -> None:
        """WHEN inspecting the CSS content"""

        """THEN .config-section-group is defined"""
        assert ".config-section-group" in self.CSS


# ---------------------------------------------------------------------------
# Config schema validation
# ---------------------------------------------------------------------------


class TestConfigSchemaValidation:
    """Config validation must be schema-based and produce actionable errors."""

    TEMPLATE = (UI_DIR / "templates" / "tool_config.html").read_text(encoding="utf-8")

    """GIVEN the tool_config.html template loaded at class level"""

    def test_validate_button_present(self) -> None:
        """WHEN inspecting the template content"""

        """THEN validateConfig() is present in the template"""
        assert "validateConfig()" in self.TEMPLATE

    """GIVEN the tool_config.html template loaded at class level"""

    def test_validation_banner_present(self) -> None:
        """WHEN inspecting the template content"""

        """THEN validation-banner and validation-errors elements are present"""
        assert "validation-banner" in self.TEMPLATE
        assert "validation-errors" in self.TEMPLATE

    """GIVEN the JsonSchemaConfigMixin save_config method"""

    def test_save_validates_before_write(self) -> None:
        import inspect

        from opsportal.adapters._config_mixin import JsonSchemaConfigMixin

        """WHEN inspecting the save_config source code"""
        source = inspect.getsource(JsonSchemaConfigMixin.save_config)

        """THEN validate_config is called within save_config"""
        assert "validate_config" in source
