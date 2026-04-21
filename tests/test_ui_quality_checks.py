"""Validates that CSS classes referenced in templates exist in stylesheets,
accessibility attributes are present, and i18n coverage is complete.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

UI_DIR = Path(__file__).resolve().parent.parent / "src" / "opsportal" / "ui"
TEMPLATE_DIR = UI_DIR / "templates"
CSS_DIR = UI_DIR / "static" / "css"
JS_DIR = UI_DIR / "static" / "js"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_all(directory: Path, glob: str) -> str:
    """Concatenate all files matching glob under directory."""
    parts = []
    for f in sorted(directory.rglob(glob)):
        parts.append(f.read_text(encoding="utf-8"))
    return "\n".join(parts)


def _extract_css_classes(css_text: str) -> set[str]:
    """Extract all class selectors from CSS text."""
    # Match .class-name in selectors (not inside property values)
    return set(re.findall(r"\.([a-zA-Z_][\w-]*)", css_text))


def _extract_html_classes(html_text: str) -> set[str]:
    """Extract all class names used in class='' attributes."""
    classes: set[str] = set()
    # Match individual Jinja tags: {{ ... }}, {% ... %}, {# ... #}
    jinja_tag = re.compile(r"\{\{.*?\}\}|\{%.*?%\}|\{#.*?#\}")
    for match in re.findall(r'class="([^"]*)"', html_text):
        cleaned = jinja_tag.sub(" ", match)
        for cls in cleaned.split():
            if "{" in cls or "%" in cls or "}" in cls:
                continue
            if (
                cls in ("if", "else", "endif", "lower", "==", "|")
                or cls.startswith("'")
                or cls.endswith("'")
                or cls.endswith("-")
                or "." in cls
                or cls in (">=", "<=", "!=", ">", "<", "+", "-")
                or cls.isdigit()
            ):
                continue
            classes.add(cls)
    return classes


# ---------------------------------------------------------------------------
# CSS class coverage
# ---------------------------------------------------------------------------


class TestCSSClassCoverage:
    """Verify CSS classes referenced in templates are defined in CSS."""

    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        self.css_text = _read_all(CSS_DIR, "*.css")
        self.css_classes = _extract_css_classes(self.css_text)
        self.html_text = _read_all(TEMPLATE_DIR, "*.html")
        self.html_classes = _extract_html_classes(self.html_text)

    """GIVEN allowed dynamic/external classes"""

    def test_no_missing_css_classes(self) -> None:
        allowed_missing = {
            # Jinja-generated dynamic classes (e.g., status-{{ card.status }})
            "status",
        }

        """WHEN computing the set of template classes missing from CSS"""
        missing = self.html_classes - self.css_classes - allowed_missing

        """THEN no classes are missing"""
        assert not missing, f"Template classes missing from CSS ({len(missing)}): " + ", ".join(
            sorted(missing)
        )


# ---------------------------------------------------------------------------
# Accessibility attributes
# ---------------------------------------------------------------------------


class TestAccessibility:
    """Verify accessibility attributes are present in templates."""

    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        self.templates: dict[str, str] = {}
        for f in sorted(TEMPLATE_DIR.glob("*.html")):
            self.templates[f.name] = f.read_text(encoding="utf-8")

    """GIVEN all loaded templates"""

    def test_all_svgs_have_aria_hidden(self) -> None:
        """WHEN scanning for <svg> tags"""

        """THEN every <svg> tag includes aria-hidden="true"."""
        for name, html in self.templates.items():
            svgs = re.findall(r"<svg[^>]*>", html)
            for svg_tag in svgs:
                assert 'aria-hidden="true"' in svg_tag, (
                    f"{name}: SVG missing aria-hidden='true': {svg_tag[:80]}..."
                )

    """GIVEN all loaded templates"""

    def test_toast_container_has_aria_live(self) -> None:
        """WHEN reading base.html"""
        base = self.templates.get("base.html", "")

        """THEN it contains aria-live and toast-container"""
        assert "aria-live" in base and "toast-container" in base

    """GIVEN all loaded templates"""

    def test_modal_has_dialog_role(self) -> None:
        """WHEN reading base.html"""
        base = self.templates.get("base.html", "")

        """THEN it contains dialog role and aria-modal"""
        assert 'role="dialog"' in base
        assert 'aria-modal="true"' in base

    """GIVEN error templates"""

    def test_error_pages_have_alert_role(self) -> None:
        """WHEN scanning for role attributes"""

        """THEN each error template includes role="alert"."""
        for name in ("error.html", "tool_error.html"):
            html = self.templates.get(name, "")
            assert 'role="alert"' in html, f"{name}: missing role='alert'"

    """GIVEN all loaded templates"""

    def test_buttons_have_type(self) -> None:
        """WHEN scanning for <button> tags"""

        """THEN every button tag has a type attribute"""
        for name, html in self.templates.items():
            buttons = re.findall(r"<button[^>]*>", html)
            for btn in buttons:
                assert 'type="' in btn, f"{name}: button missing type: {btn[:80]}..."

    """GIVEN all loaded templates"""

    def test_target_blank_has_rel(self) -> None:
        """WHEN scanning for target="_blank" links."""

        """THEN every target="_blank" link has rel="noopener"."""
        for name, html in self.templates.items():
            links = re.findall(r'<a[^>]*target="_blank"[^>]*>', html)
            for link in links:
                assert "noopener" in link, (
                    f"{name}: target=_blank missing rel=noopener: {link[:80]}..."
                )


# ---------------------------------------------------------------------------
# i18n coverage
# ---------------------------------------------------------------------------


class TestI18nCoverage:
    """Verify i18n key coverage."""

    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        self.i18n_js = (JS_DIR / "portal-i18n.js").read_text(encoding="utf-8")
        self.pl_js = (JS_DIR / "portal-i18n-pl.js").read_text(encoding="utf-8")

    """GIVEN the loaded i18n JS files"""

    def test_both_locales_present(self) -> None:
        """WHEN inspecting locale dictionaries"""

        """THEN en locale and PL locale are present"""
        assert "en:" in self.i18n_js or '"en"' in self.i18n_js
        assert "__OPS_PL" in self.pl_js

    """GIVEN the loaded i18n JS files"""

    def test_t_function_exported(self) -> None:
        """WHEN inspecting exported functions"""

        """THEN t() function exists"""
        assert "function t(" in self.i18n_js or "window.t" in self.i18n_js

    """GIVEN extracted key sets from both locale files"""

    def test_en_pl_key_parity(self) -> None:
        en_keys = set(re.findall(r'"([\w.]+)":\s*"', self.i18n_js))
        pl_keys = set(re.findall(r'"([\w.]+)":\s*"', self.pl_js))

        """WHEN computing key differences"""
        missing_in_pl = en_keys - pl_keys
        missing_in_en = pl_keys - en_keys

        """THEN no keys are missing in either direction"""
        assert not missing_in_pl, f"Keys in en but not pl: {sorted(missing_in_pl)}"
        assert not missing_in_en, f"Keys in pl but not en: {sorted(missing_in_en)}"

    """GIVEN the loaded i18n JS files"""

    def test_apply_language_handles_placeholder(self) -> None:
        """WHEN inspecting applyLanguage functionality"""

        """THEN data-i18n-placeholder is referenced in the i18n module"""
        assert "data-i18n-placeholder" in self.i18n_js

    """GIVEN the loaded i18n JS files"""

    def test_apply_language_handles_doc_title(self) -> None:
        """WHEN inspecting applyLanguage functionality"""

        """THEN data-i18n-doc-title is referenced in the i18n module"""
        assert "data-i18n-doc-title" in self.i18n_js

    """GIVEN the loaded i18n JS files"""

    def test_apply_language_handles_map(self) -> None:
        """WHEN inspecting applyLanguage functionality"""

        """THEN data-i18n-map is referenced in the i18n module"""
        assert "data-i18n-map" in self.i18n_js

    """GIVEN the loaded i18n JS files"""

    def test_locale_cookie_set(self) -> None:
        """WHEN inspecting cookie handling"""

        """THEN i18n module references opsportal_lang= and cookie"""
        assert "opsportal_lang=" in self.i18n_js and "cookie" in self.i18n_js

    """GIVEN the loaded i18n JS files"""

    def test_browser_lang_detection(self) -> None:
        """WHEN inspecting language detection"""

        """THEN _detectBrowserLang is referenced in the i18n module"""
        assert "_detectBrowserLang" in self.i18n_js

    """GIVEN the loaded i18n JS files"""

    def test_pluralization_support(self) -> None:
        """WHEN inspecting pluralization support"""

        """THEN tp() function exists"""
        assert "function tp(" in self.i18n_js or "window.tp" in self.i18n_js

    """GIVEN the loaded i18n JS files"""

    def test_number_formatting_support(self) -> None:
        """WHEN inspecting number formatting support"""

        """THEN formatNumber exists"""
        assert "formatNumber" in self.i18n_js


# ---------------------------------------------------------------------------
# File size limits
# ---------------------------------------------------------------------------


class TestFileSizeLimits:
    """Enforce the 600-line maximum per file."""

    MAX_LINES = 600

    """GIVEN a directory of UI files"""

    @pytest.mark.parametrize(
        "subdir,glob_pattern",
        [
            (CSS_DIR, "*.css"),
            (JS_DIR, "*.js"),
            (TEMPLATE_DIR, "*.html"),
        ],
    )
    def test_files_under_limit(self, subdir: Path, glob_pattern: str) -> None:
        # i18n dictionary files are pure data and grow with translation coverage
        i18n_data_files = {"portal-i18n.js", "portal-i18n-pl.js"}
        violations = []

        """WHEN checking line counts for each file"""
        for f in sorted(subdir.rglob(glob_pattern)):
            if f.name in i18n_data_files:
                continue
            lines = len(f.read_text(encoding="utf-8").splitlines())
            if lines > self.MAX_LINES:
                violations.append(f"{f.name}: {lines} lines")

        """THEN no files exceed the limit"""
        assert not violations, f"Files exceeding {self.MAX_LINES} lines: " + "; ".join(violations)
