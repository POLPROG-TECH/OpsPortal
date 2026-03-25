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
        """All classes used in templates are defined in CSS."""
        """GIVEN allowed dynamic/external classes."""
        allowed_missing = {
            # Jinja-generated dynamic classes (e.g., status-{{ card.status }})
            "status",
        }

        """WHEN computing the set of template classes missing from CSS."""
        missing = self.html_classes - self.css_classes - allowed_missing

        """THEN no classes are missing."""
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
        """Decorative SVGs in templates have aria-hidden='true'."""
        """GIVEN all loaded templates."""
        """THEN every <svg> tag includes aria-hidden="true"."""
        for name, html in self.templates.items():
            svgs = re.findall(r"<svg[^>]*>", html)
            for svg_tag in svgs:
                assert 'aria-hidden="true"' in svg_tag, (
                    f"{name}: SVG missing aria-hidden='true': {svg_tag[:80]}..."
                )

    def test_toast_container_has_aria_live(self) -> None:
        """Toast container in base.html has aria-live for screen readers."""
        """WHEN reading base.html."""
        base = self.templates.get("base.html", "")

        """THEN it contains aria-live and toast-container."""
        assert "aria-live" in base and "toast-container" in base

    def test_modal_has_dialog_role(self) -> None:
        """Modal in base.html has role='dialog' and aria-modal='true'."""
        """WHEN reading base.html."""
        base = self.templates.get("base.html", "")

        """THEN it contains dialog role and aria-modal."""
        assert 'role="dialog"' in base
        assert 'aria-modal="true"' in base

    def test_error_pages_have_alert_role(self) -> None:
        """Error page templates contain role='alert'."""
        """GIVEN error templates."""
        """THEN each error template includes role="alert"."""
        for name in ("error.html", "tool_error.html"):
            html = self.templates.get(name, "")
            assert 'role="alert"' in html, f"{name}: missing role='alert'"

    def test_buttons_have_type(self) -> None:
        """All <button> elements in templates have an explicit type attribute."""
        """GIVEN all loaded templates."""
        """THEN every button tag has a type attribute."""
        for name, html in self.templates.items():
            buttons = re.findall(r"<button[^>]*>", html)
            for btn in buttons:
                assert 'type="' in btn, f"{name}: button missing type: {btn[:80]}..."

    def test_target_blank_has_rel(self) -> None:
        """Links with target='_blank' include rel='noopener noreferrer'."""
        """GIVEN all loaded templates."""
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

    def test_both_locales_present(self) -> None:
        """Both en and pl locale dictionaries exist in i18n files."""
        """THEN en locale and PL locale are present."""
        assert "en:" in self.i18n_js or '"en"' in self.i18n_js
        assert "__OPS_PL" in self.pl_js

    def test_t_function_exported(self) -> None:
        """The t() translation function is defined in the i18n module."""
        """THEN t() function exists."""
        assert "function t(" in self.i18n_js or "window.t" in self.i18n_js

    def test_en_pl_key_parity(self) -> None:
        """Every key in en exists in pl and vice versa."""
        """GIVEN extracted key sets from both locale files."""
        en_keys = set(re.findall(r'"([\w.]+)":\s*"', self.i18n_js))
        pl_keys = set(re.findall(r'"([\w.]+)":\s*"', self.pl_js))

        """WHEN computing key differences."""
        missing_in_pl = en_keys - pl_keys
        missing_in_en = pl_keys - en_keys

        """THEN no keys are missing in either direction."""
        assert not missing_in_pl, f"Keys in en but not pl: {sorted(missing_in_pl)}"
        assert not missing_in_en, f"Keys in pl but not en: {sorted(missing_in_en)}"

    def test_apply_language_handles_placeholder(self) -> None:
        """applyLanguage supports data-i18n-placeholder attribute."""
        """THEN data-i18n-placeholder is referenced in the i18n module."""
        assert "data-i18n-placeholder" in self.i18n_js

    def test_apply_language_handles_doc_title(self) -> None:
        """applyLanguage supports document.title updates via data-i18n-doc-title."""
        """THEN data-i18n-doc-title is referenced in the i18n module."""
        assert "data-i18n-doc-title" in self.i18n_js

    def test_apply_language_handles_map(self) -> None:
        """applyLanguage supports data-i18n-map for dynamic content."""
        """THEN data-i18n-map is referenced in the i18n module."""
        assert "data-i18n-map" in self.i18n_js

    def test_locale_cookie_set(self) -> None:
        """applyLanguage sets an opsportal_lang cookie for server-side locale."""
        """THEN i18n module references opsportal_lang= and cookie."""
        assert "opsportal_lang=" in self.i18n_js and "cookie" in self.i18n_js

    def test_browser_lang_detection(self) -> None:
        """getLang detects browser language via _detectBrowserLang."""
        """THEN _detectBrowserLang is referenced in the i18n module."""
        assert "_detectBrowserLang" in self.i18n_js

    def test_pluralization_support(self) -> None:
        """Pluralization function tp() is defined in the i18n module."""
        """THEN tp() function exists."""
        assert "function tp(" in self.i18n_js or "window.tp" in self.i18n_js

    def test_number_formatting_support(self) -> None:
        """Number formatting function formatNumber is defined in the i18n module."""
        """THEN formatNumber exists."""
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
        """UI files do not exceed the 600-line limit."""
        """GIVEN a directory of UI files."""
        violations = []

        """WHEN checking line counts for each file."""
        for f in sorted(subdir.rglob(glob_pattern)):
            lines = len(f.read_text(encoding="utf-8").splitlines())
            if lines > self.MAX_LINES:
                violations.append(f"{f.name}: {lines} lines")

        """THEN no files exceed the limit."""
        assert not violations, f"Files exceeding {self.MAX_LINES} lines: " + "; ".join(violations)