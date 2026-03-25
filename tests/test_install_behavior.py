"""Tests for installed-package behavior, config scaffolding, and production onboarding.

These tests verify that OpsPortal works correctly when installed via pip
(not just from a local source checkout), including:
- Config scaffolding from schema defaults
- Config resolution across multiple strategies
- Missing-config user experience
- Setup command behavior
- Static asset packaging
- Manifest bootstrap
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from opsportal.adapters.releaseboard import ReleaseBoardAdapter
from opsportal.adapters.releasepilot import ReleasePilotAdapter
from opsportal.config.manifest import DEFAULT_MANIFEST_YAML, load_manifest
from opsportal.services.process_manager import ProcessManager

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def pm() -> ProcessManager:
    return ProcessManager()


@pytest.fixture()
def work_dir(tmp_path: Path) -> Path:
    d = tmp_path / "work" / "tools" / "test-tool"
    d.mkdir(parents=True)
    return d


@pytest.fixture()
def schema_dir(tmp_path: Path) -> Path:
    d = tmp_path / "schemas"
    d.mkdir()
    return d


def _write_schema(path: Path, required: list[str] | None = None, defaults: dict | None = None):
    """Write a minimal JSON Schema file."""
    props = {}
    for key, value in (defaults or {}).items():
        props[key] = {"type": "string", "default": value}
    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": props,
    }
    if required:
        schema["required"] = required
    path.write_text(json.dumps(schema, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Config scaffolding
# ---------------------------------------------------------------------------


class TestConfigScaffolding:
    """Config scaffolding creates default config files from schema defaults."""

    def test_scaffold_creates_config_from_schema_defaults(self, pm, work_dir, schema_dir):
        """GIVEN a schema with defaults and no existing config."""
        schema_path = schema_dir / "releasepilot.schema.json"
        _write_schema(
            schema_path,
            defaults={"output_format": "markdown", "include_authors": "true"},
        )
        adapter = ReleasePilotAdapter(pm, work_dir=work_dir, port=8082, cli_binary="releasepilot")
        adapter._schema_paths = [schema_path]

        """WHEN scaffold_default_config is called."""
        result = adapter.scaffold_default_config()

        """THEN a config file is created with default values."""
        assert result is True
        config_path = work_dir / ".releasepilot.json"
        assert config_path.exists()
        data = json.loads(config_path.read_text())
        assert data["output_format"] == "markdown"
        assert data["include_authors"] == "true"

    def test_scaffold_skips_if_config_exists(self, pm, work_dir, schema_dir):
        """GIVEN an existing config file."""
        config_path = work_dir / ".releasepilot.json"
        config_path.write_text('{"existing": true}\n')
        schema_path = schema_dir / "releasepilot.schema.json"
        _write_schema(schema_path, defaults={"output_format": "markdown"})

        """WHEN scaffold_default_config is called."""
        adapter = ReleasePilotAdapter(pm, work_dir=work_dir, port=8082, cli_binary="releasepilot")
        adapter._schema_paths = [schema_path]

        """THEN no new file is created."""
        result = adapter.scaffold_default_config()

        assert result is False
        data = json.loads(config_path.read_text())
        assert data == {"existing": True}

    def test_scaffold_uses_builtin_defaults_without_schema(self, pm, work_dir):
        """GIVEN no schema file available but built-in defaults exist."""
        adapter = ReleasePilotAdapter(pm, work_dir=work_dir, port=8082, cli_binary="releasepilot")
        adapter._schema_paths = []

        """WHEN scaffold_default_config is called."""
        result = adapter.scaffold_default_config()

        """THEN a config file is created from built-in defaults."""
        assert result is True
        config_path = work_dir / ".releasepilot.json"
        assert config_path.exists()
        data = json.loads(config_path.read_text())
        assert "app_name" in data

    def test_scaffold_falls_back_to_builtin_when_schema_incomplete(self, pm, work_dir, schema_dir):
        """GIVEN a schema with required fields that have no defaults."""
        schema_path = schema_dir / "releasepilot.schema.json"
        _write_schema(
            schema_path,
            required=["auth_token"],
            defaults={"output_format": "markdown"},
        )

        """WHEN scaffold_default_config is called."""
        adapter = ReleasePilotAdapter(pm, work_dir=work_dir, port=8082, cli_binary="releasepilot")
        adapter._schema_paths = [schema_path]

        """THEN built-in defaults are used as fallback."""
        result = adapter.scaffold_default_config()

        assert result is True
        config_path = work_dir / ".releasepilot.json"
        data = json.loads(config_path.read_text())
        # Built-in defaults used, not schema defaults (which were incomplete)
        assert "app_name" in data

    def test_releaseboard_scaffold_creates_config(self, pm, work_dir, schema_dir):
        """GIVEN a ReleaseBoard schema with defaults."""
        schema_path = schema_dir / "schema.json"
        _write_schema(
            schema_path,
            defaults={"title": "Release Dashboard", "refresh_interval": "30"},
        )
        adapter = ReleaseBoardAdapter(pm, work_dir=work_dir, port=8081, cli_binary="releaseboard")
        adapter._schema_paths = [schema_path]

        """WHEN scaffold_default_config is called."""
        result = adapter.scaffold_default_config()

        """THEN a releaseboard.json config file is created."""
        assert result is True
        config_path = work_dir / "releaseboard.json"
        assert config_path.exists()
        data = json.loads(config_path.read_text())
        assert data["title"] == "Release Dashboard"


# ---------------------------------------------------------------------------
# Config resolution (multi-strategy)
# ---------------------------------------------------------------------------


class TestConfigResolution:
    """Config resolution finds config files across multiple locations."""

    def test_releasepilot_finds_config_in_work_dir(self, pm, work_dir):
        """GIVEN a config file in work_dir."""
        config = work_dir / ".releasepilot.json"
        config.write_text('{"found": true}\n')

        """WHEN _resolve_config_path is called."""
        adapter = ReleasePilotAdapter(pm, work_dir=work_dir, port=8082, cli_binary="releasepilot")
        resolved = adapter._resolve_config_path()
        assert resolved == config.resolve()

        """THEN it returns the work_dir path."""

    def test_releasepilot_prefers_env_var(self, pm, work_dir, tmp_path):
        """GIVEN OPSPORTAL_RELEASEPILOT_CONFIG env var pointing to a file."""
        env_config = tmp_path / "custom" / ".releasepilot.json"
        env_config.parent.mkdir(parents=True)
        env_config.write_text('{"from_env": true}\n')

        """WHEN _resolve_config_path is called."""
        adapter = ReleasePilotAdapter(pm, work_dir=work_dir, port=8082, cli_binary="releasepilot")

        """THEN it returns the env var path."""
        with patch.dict("os.environ", {"OPSPORTAL_RELEASEPILOT_CONFIG": str(env_config)}):
            resolved = adapter._resolve_config_path()
        assert resolved == env_config.resolve()

    def test_releasepilot_falls_back_to_work_dir_canonical(self, pm, work_dir):
        """GIVEN no config file exists anywhere."""
        adapter = ReleasePilotAdapter(pm, work_dir=work_dir, port=8082, cli_binary="releasepilot")
        resolved = adapter._resolve_config_path()
        expected = (work_dir / ".releasepilot.json").resolve()
        assert resolved == expected

        """WHEN _resolve_config_path is called."""

    def test_releaseboard_finds_config_in_work_dir(self, pm, work_dir):
        """GIVEN a config file in work_dir."""
        config = work_dir / "releaseboard.json"
        config.write_text('{"found": true}\n')

        """WHEN _resolve_config_path is called."""
        adapter = ReleaseBoardAdapter(pm, work_dir=work_dir, port=8081, cli_binary="releaseboard")
        resolved = adapter._resolve_config_path()
        assert resolved == config.resolve()

        """THEN it returns the work_dir path."""

    def test_releaseboard_prefers_env_var(self, pm, work_dir, tmp_path):
        """GIVEN OPSPORTAL_RELEASEBOARD_CONFIG env var pointing to a file."""
        env_config = tmp_path / "custom" / "releaseboard.json"
        env_config.parent.mkdir(parents=True)
        env_config.write_text('{"from_env": true}\n')

        """WHEN _resolve_config_path is called."""
        adapter = ReleaseBoardAdapter(pm, work_dir=work_dir, port=8081, cli_binary="releaseboard")

        """THEN it returns the env var path."""
        with patch.dict("os.environ", {"OPSPORTAL_RELEASEBOARD_CONFIG": str(env_config)}):
            resolved = adapter._resolve_config_path()
        assert resolved == env_config.resolve()


# ---------------------------------------------------------------------------
# Config issues detection
# ---------------------------------------------------------------------------


class TestConfigIssues:
    """Dashboard config issue detection is accurate and actionable."""

    def test_no_issues_when_config_exists(self, pm, work_dir, schema_dir):
        """GIVEN a tool with existing config file."""
        from opsportal.app.routes import _config_issues

        """WHEN _config_issues is checked."""
        config = work_dir / ".releasepilot.json"
        config.write_text('{"valid": true}\n')
        schema_path = schema_dir / "releasepilot.schema.json"
        _write_schema(schema_path, defaults={"output_format": "markdown"})

        """THEN no issues are reported."""
        adapter = ReleasePilotAdapter(pm, work_dir=work_dir, port=8082, cli_binary="releasepilot")
        adapter._schema_paths = [schema_path]

        issues = _config_issues(adapter)
        assert len(issues) == 0

    def test_scaffolds_from_builtins_when_no_schema(self, pm, work_dir):
        """GIVEN a tool with missing config and no schema but built-in defaults."""
        from opsportal.app.routes import _config_issues

        """WHEN _config_issues is checked."""
        adapter = ReleasePilotAdapter(pm, work_dir=work_dir, port=8082, cli_binary="releasepilot")
        adapter._schema_paths = []

        """THEN config is auto-scaffolded and no issue is reported."""
        issues = _config_issues(adapter)
        assert len(issues) == 0
        assert (work_dir / ".releasepilot.json").exists()

    def test_issues_auto_scaffold_when_possible(self, pm, work_dir, schema_dir):
        """GIVEN a tool with missing config but available schema with defaults."""
        from opsportal.app.routes import _config_issues

        """WHEN _config_issues is checked."""
        schema_path = schema_dir / "releasepilot.schema.json"
        _write_schema(schema_path, defaults={"output_format": "markdown"})

        """THEN config is auto-scaffolded and no issue is reported."""
        adapter = ReleasePilotAdapter(pm, work_dir=work_dir, port=8082, cli_binary="releasepilot")
        adapter._schema_paths = [schema_path]

        issues = _config_issues(adapter)
        assert len(issues) == 0
        # Config should have been created
        assert (work_dir / ".releasepilot.json").exists()

    def test_no_issues_for_first_run_wizard_tool(self, pm, work_dir):
        """GIVEN a tool with missing config but has_first_run_wizard=True."""
        from opsportal.app.routes import _config_issues

        """WHEN _config_issues is checked."""
        adapter = ReleaseBoardAdapter(pm, work_dir=work_dir, port=8081, cli_binary="releaseboard")
        adapter._schema_paths = []

        """THEN no issue is reported (the tool handles setup itself)."""
        issues = _config_issues(adapter)
        assert len(issues) == 0
        assert not (work_dir / "releaseboard.json").exists()


# ---------------------------------------------------------------------------
# Startup lifecycle scaffolding
# ---------------------------------------------------------------------------


class TestStartupScaffolding:
    """Adapter startup() proactively scaffolds config."""

    @pytest.mark.asyncio
    async def test_releasepilot_startup_scaffolds(self, pm, work_dir, schema_dir):
        """GIVEN a ReleasePilot adapter with schema but no config."""
        schema_path = schema_dir / "releasepilot.schema.json"
        _write_schema(schema_path, defaults={"format": "html"})

        """WHEN startup() is called."""
        adapter = ReleasePilotAdapter(pm, work_dir=work_dir, port=8082, cli_binary="releasepilot")
        adapter._schema_paths = [schema_path]

        """THEN config is scaffolded."""
        await adapter.startup()

        assert (work_dir / ".releasepilot.json").exists()

    @pytest.mark.asyncio
    async def test_releaseboard_startup_creates_work_dir(self, pm, tmp_path):
        """GIVEN a ReleaseBoard adapter with a non-existent work directory."""
        work_dir = tmp_path / "releaseboard_work"
        adapter = ReleaseBoardAdapter(pm, work_dir=work_dir, port=8081, cli_binary="releaseboard")

        """WHEN startup() is called."""
        await adapter.startup()

        """THEN the work directory is created (for first-run wizard mode)."""
        assert work_dir.exists()
        assert not (work_dir / "releaseboard.json").exists()  # no scaffold


# ---------------------------------------------------------------------------
# Manifest bootstrap
# ---------------------------------------------------------------------------


class TestManifestBootstrap:
    """Default manifest bootstraps correctly in fresh environments."""

    def test_default_manifest_has_both_tools(self, tmp_path):
        """GIVEN the default manifest template."""
        manifest_path = tmp_path / "opsportal.yaml"
        manifest_path.write_text(DEFAULT_MANIFEST_YAML)

        """WHEN loaded."""
        m = load_manifest(manifest_path, tmp_path, tools_work_dir=tmp_path / "tools")

        """THEN both releasepilot and releaseboard are registered."""
        assert len(m.enabled_tools) == 2
        slugs = {t.slug for t in m.enabled_tools}
        assert "releasepilot" in slugs
        assert "releaseboard" in slugs

    def test_default_manifest_tools_have_sources(self, tmp_path):
        """GIVEN the default manifest."""
        manifest_path = tmp_path / "opsportal.yaml"
        manifest_path.write_text(DEFAULT_MANIFEST_YAML)

        """WHEN loaded."""
        m = load_manifest(manifest_path, tmp_path)

        """THEN all tools have source definitions for remote install."""
        for tool in m.enabled_tools:
            assert tool.source is not None, f"{tool.slug} missing source"
            assert tool.source.repository, f"{tool.slug} missing repository"
            assert tool.source.ref, f"{tool.slug} missing ref"
            assert tool.source.package, f"{tool.slug} missing package name"

    def test_default_manifest_tools_have_ports(self, tmp_path):
        """GIVEN the default manifest."""
        manifest_path = tmp_path / "opsportal.yaml"
        manifest_path.write_text(DEFAULT_MANIFEST_YAML)

        """WHEN loaded."""
        m = load_manifest(manifest_path, tmp_path)

        """THEN all subprocess_web tools have port assignments."""
        for tool in m.enabled_tools:
            assert tool.port is not None, f"{tool.slug} missing port"

    def test_default_manifest_no_duplicate_ports(self, tmp_path):
        """GIVEN the default manifest."""
        manifest_path = tmp_path / "opsportal.yaml"
        manifest_path.write_text(DEFAULT_MANIFEST_YAML)

        """WHEN validated."""
        m = load_manifest(manifest_path, tmp_path)
        diagnostics = m.validate()

        """THEN there are no duplicate port assignments."""
        port_issues = [d for d in diagnostics if "Duplicate port" in d]
        assert len(port_issues) == 0


# ---------------------------------------------------------------------------
# Static asset packaging
# ---------------------------------------------------------------------------


class TestStaticAssets:
    """Static assets are available from the installed package."""

    def test_templates_directory_exists(self):
        """GIVEN the installed opsportal package."""
        ui_dir = Path(__file__).resolve().parent.parent / "src" / "opsportal" / "ui"
        templates = ui_dir / "templates"
        assert templates.is_dir()
        assert (templates / "home.html").is_file()
        assert (templates / "base.html").is_file()
        assert (templates / "tool_web.html").is_file()
        assert (templates / "tool_config.html").is_file()

        """WHEN checking ui/templates."""

    def test_static_directory_exists(self):
        """GIVEN the installed opsportal package."""
        ui_dir = Path(__file__).resolve().parent.parent / "src" / "opsportal" / "ui"
        static = ui_dir / "static"
        assert static.is_dir()
        assert (static / "css" / "portal-base.css").is_file()
        assert (static / "js" / "portal.js").is_file()

        """WHEN checking ui/static."""

        """THEN the directory exists with expected files."""


# ---------------------------------------------------------------------------
# Setup command
# ---------------------------------------------------------------------------


class TestSetupCommand:
    """The opsportal setup command bootstraps a fresh environment."""

    def test_setup_creates_manifest(self, tmp_path):
        """GIVEN no manifest file exists."""
        from opsportal.__main__ import _ensure_manifest

        """WHEN _ensure_manifest is called."""
        manifest = tmp_path / "opsportal.yaml"
        _ensure_manifest(manifest)
        assert manifest.exists()
        content = manifest.read_text()
        assert "releasepilot" in content
        assert "releaseboard" in content

        """THEN a manifest file is created."""

    def test_setup_preserves_existing_manifest(self, tmp_path):
        """GIVEN an existing manifest file."""
        from opsportal.__main__ import _ensure_manifest

        """WHEN _ensure_manifest is called."""
        manifest = tmp_path / "custom.yaml"
        manifest.write_text("tools: {custom: true}\n")

        """THEN the file is not overwritten."""
        _ensure_manifest(manifest)
        assert manifest.read_text() == "tools: {custom: true}\n"


# ---------------------------------------------------------------------------
# Built-in default config templates
# ---------------------------------------------------------------------------


class TestBuiltinDefaults:
    """Built-in default configs ensure tools never dead-end on missing config."""

    def test_releasepilot_builtin_defaults_scaffold(self, pm, work_dir):
        """GIVEN a ReleasePilot adapter with no schema and no existing config."""
        adapter = ReleasePilotAdapter(pm, work_dir=work_dir, port=8082, cli_binary="releasepilot")
        adapter._schema_paths = []

        """WHEN scaffold_default_config is called."""
        result = adapter.scaffold_default_config()

        """THEN built-in defaults create a valid config file."""
        assert result is True
        config_path = work_dir / ".releasepilot.json"
        assert config_path.exists()
        data = json.loads(config_path.read_text())
        assert data["app_name"] == "Release Notes"
        assert data["language"] == "en"

    def test_releaseboard_no_builtin_scaffold_uses_first_run_wizard(self, pm, work_dir):
        """GIVEN a ReleaseBoard adapter with no schema and no existing config."""
        adapter = ReleaseBoardAdapter(pm, work_dir=work_dir, port=8081, cli_binary="releaseboard")
        adapter._schema_paths = []

        """WHEN scaffold_default_config is called."""
        result = adapter.scaffold_default_config()

        """THEN no config is created because ReleaseBoard uses its own first-run wizard."""
        assert result is False
        config_path = work_dir / "releaseboard.json"
        assert not config_path.exists()
        assert adapter.has_first_run_wizard is True

    def test_schema_defaults_take_priority_over_builtins(self, pm, work_dir, schema_dir):
        """GIVEN a schema with complete defaults."""
        schema_path = schema_dir / "releasepilot.schema.json"
        _write_schema(schema_path, defaults={"custom_field": "from_schema"})

        """WHEN scaffold_default_config is called."""
        adapter = ReleasePilotAdapter(pm, work_dir=work_dir, port=8082, cli_binary="releasepilot")
        adapter._schema_paths = [schema_path]

        """THEN schema defaults are used, not built-in defaults."""
        result = adapter.scaffold_default_config()

        assert result is True
        data = json.loads((work_dir / ".releasepilot.json").read_text())
        assert data["custom_field"] == "from_schema"
        assert "app_name" not in data  # built-in key not present

    def test_no_scaffold_without_builtin_or_schema(self, pm, work_dir):
        """GIVEN an adapter with no schema and no built-in defaults."""
        adapter = ReleasePilotAdapter(pm, work_dir=work_dir, port=8082, cli_binary="releasepilot")
        adapter._schema_paths = []
        adapter._builtin_default_config = None

        """WHEN scaffold_default_config is called."""
        result = adapter.scaffold_default_config()

        """THEN no config file is created."""
        assert result is False
        assert not (work_dir / ".releasepilot.json").exists()
