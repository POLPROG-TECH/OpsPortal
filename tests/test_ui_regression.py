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
    for match in re.findall(r'class="([^"]*)"', html_text):
        for cls in match.split():
            # Skip Jinja expressions and template tokens
            if "{" in cls or "%" in cls or "}" in cls:
                continue
            # Skip if it looks like Jinja syntax (operators, filters, variables)
            if (
                cls in ("if", "else", "endif", "lower", "==", "|", "}}")
                or cls.startswith("'")
                or "." in cls
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

    def test_no_missing_css_classes(self) -> None:
        """GIVEN All classes used in templates must be defined in CSS."""
        # Classes that are legitimately dynamic or from external sources
        allowed_missing = {
            # Jinja-generated dynamic classes (e.g., status-{{ card.status }})
            "status",
        }

        """WHEN executing."""
        missing = self.html_classes - self.css_classes - allowed_missing

        """THEN the result is correct."""
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

    def test_all_svgs_have_aria_hidden(self) -> None:
        """GIVEN Decorative SVGs must have aria-hidden='true'."""

        """THEN the result is correct."""

        """WHEN executing."""
        for name, html in self.templates.items():
            svgs = re.findall(r"<svg[^>]*>", html)
            for svg_tag in svgs:
                assert 'aria-hidden="true"' in svg_tag, (
                    f"{name}: SVG missing aria-hidden='true': {svg_tag[:80]}..."
                )

    def test_toast_container_has_aria_live(self) -> None:
        """GIVEN Toast container must have aria-live for screen readers."""

        """WHEN executing."""
        base = self.templates.get("base.html", "")

        """THEN the result is correct."""
        assert "aria-live" in base and "toast-container" in base

    def test_modal_has_dialog_role(self) -> None:
        """GIVEN Modal must have role='dialog' and aria-modal."""

        """WHEN executing."""
        base = self.templates.get("base.html", "")

        """THEN the result is correct."""
        assert 'role="dialog"' in base
        assert 'aria-modal="true"' in base

    def test_error_pages_have_alert_role(self) -> None:
        """GIVEN Error containers must have role='alert'."""

        """THEN the result is correct."""

        """WHEN executing."""
        for name in ("error.html", "tool_error.html"):
            html = self.templates.get(name, "")
            assert 'role="alert"' in html, f"{name}: missing role='alert'"

    def test_buttons_have_type(self) -> None:
        """GIVEN All <button> elements should have explicit type attribute."""

        """THEN the result is correct."""

        """WHEN executing."""
        for name, html in self.templates.items():
            buttons = re.findall(r"<button[^>]*>", html)
            for btn in buttons:
                assert 'type="' in btn, f"{name}: button missing type: {btn[:80]}..."

    def test_target_blank_has_rel(self) -> None:
        """GIVEN Links with target='_blank' must have rel='noopener noreferrer'."""

        """THEN the result is correct."""

        """WHEN executing."""
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

    def test_both_locales_present(self) -> None:
        """GIVEN Both en and pl locale dictionaries must exist."""

        """THEN the result is correct."""

        """WHEN executing."""
        assert "en:" in self.i18n_js or '"en"' in self.i18n_js
        assert "__OPS_PL" in self.pl_js

    def test_t_function_exported(self) -> None:
        """GIVEN The t() translation function must be defined."""

        """THEN the result is correct."""

        """WHEN executing."""
        assert "function t(" in self.i18n_js or "window.t" in self.i18n_js

    def test_en_pl_key_parity(self) -> None:
        """GIVEN Every key in en must exist in pl and vice versa."""
        en_keys = set(re.findall(r'"([\w.]+)":\s*"', self.i18n_js))
        pl_keys = set(re.findall(r'"([\w.]+)":\s*"', self.pl_js))
        missing_in_pl = en_keys - pl_keys

        """WHEN executing."""
        missing_in_en = pl_keys - en_keys

        """THEN the result is correct."""
        assert not missing_in_pl, f"Keys in en but not pl: {sorted(missing_in_pl)}"
        assert not missing_in_en, f"Keys in pl but not en: {sorted(missing_in_en)}"

    def test_apply_language_handles_placeholder(self) -> None:
        """GIVEN applyLanguage must support data-i18n-placeholder."""

        """THEN the result is correct."""

        """WHEN executing."""
        assert "data-i18n-placeholder" in self.i18n_js

    def test_apply_language_handles_doc_title(self) -> None:
        """GIVEN applyLanguage must support document.title updates."""

        """THEN the result is correct."""

        """WHEN executing."""
        assert "data-i18n-doc-title" in self.i18n_js

    def test_apply_language_handles_map(self) -> None:
        """GIVEN applyLanguage must support data-i18n-map for dynamic content."""

        """THEN the result is correct."""

        """WHEN executing."""
        assert "data-i18n-map" in self.i18n_js

    def test_locale_cookie_set(self) -> None:
        """GIVEN applyLanguage must set a cookie for server-side locale."""

        """THEN the result is correct."""

        """WHEN executing."""
        assert "opsportal_lang=" in self.i18n_js and "cookie" in self.i18n_js

    def test_browser_lang_detection(self) -> None:
        """GIVEN getLang must detect browser language."""

        """THEN the result is correct."""

        """WHEN executing."""
        assert "_detectBrowserLang" in self.i18n_js

    def test_pluralization_support(self) -> None:
        """GIVEN Pluralization function must exist."""

        """THEN the result is correct."""

        """WHEN executing."""
        assert "function tp(" in self.i18n_js or "window.tp" in self.i18n_js

    def test_number_formatting_support(self) -> None:
        """GIVEN Number formatting function must exist."""

        """THEN the result is correct."""

        """WHEN executing."""
        assert "formatNumber" in self.i18n_js


# ---------------------------------------------------------------------------
# File size limits
# ---------------------------------------------------------------------------


class TestFileSizeLimits:
    """Enforce the 600-line maximum per file."""

    MAX_LINES = 600

    @pytest.mark.parametrize(
        "subdir,glob_pattern",
        [
            (CSS_DIR, "*.css"),
            (JS_DIR, "*.js"),
            (TEMPLATE_DIR, "*.html"),
        ],
    )
    def test_files_under_limit(self, subdir: Path, glob_pattern: str) -> None:
        """GIVEN the files under limit scenario."""
        violations = []

        """WHEN executing."""
        for f in sorted(subdir.rglob(glob_pattern)):
            lines = len(f.read_text(encoding="utf-8").splitlines())
            if lines > self.MAX_LINES:
                violations.append(f"{f.name}: {lines} lines")

        """THEN the result is correct."""
        assert not violations, f"Files exceeding {self.MAX_LINES} lines: " + "; ".join(violations)
