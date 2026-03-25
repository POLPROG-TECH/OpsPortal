"""Tests for remote-managed tool sourcing — ToolSource, ToolInstaller, manifest."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# ToolSource model tests
# ---------------------------------------------------------------------------


class TestToolSource:
    """Validate ToolSource model and pip spec generation."""

    def test_github_git_url(self):
        """GIVEN the github git url scenario."""
        from opsportal.config.manifest import ToolSource

        """WHEN executing."""
        src = ToolSource(
            repository="POLPROG-TECH/ReleasePilot",
            ref="v1.1.0",
            package="releasepilot",
        )

        """THEN the result is correct."""
        assert src.git_url == "git+https://github.com/POLPROG-TECH/ReleasePilot.git@v1.1.0"

    def test_pip_spec_with_extras(self):
        """GIVEN the pip spec with extras scenario."""
        from opsportal.config.manifest import ToolSource

        """WHEN executing."""
        src = ToolSource(
            repository="POLPROG-TECH/ReleasePilot",
            ref="v1.1.0",
            package="releasepilot",
            extras=["all"],
        )

        """THEN the result is correct."""
        assert "[all]" in src.pip_spec
        assert "@v1.1.0" in src.pip_spec

    def test_pip_spec_registry_strategy(self):
        """GIVEN the pip spec registry strategy scenario."""
        from opsportal.config.manifest import InstallStrategy, ToolSource

        """WHEN executing."""
        src = ToolSource(
            repository="POLPROG-TECH/ReleasePilot",
            ref="1.1.0",
            package="releasepilot",
            install_strategy=InstallStrategy.PIP_REGISTRY,
        )

        """THEN the result is correct."""
        assert src.pip_spec == "releasepilot==1.1.0"

    def test_invalid_repository_format(self):
        """GIVEN the invalid repository format scenario."""

        """WHEN executing."""
        from opsportal.config.manifest import ToolSource

        """THEN the result is correct."""
        with pytest.raises(ValueError, match="owner/name"):
            ToolSource(
                repository="just-a-name",
                package="test",
            )

    def test_gitlab_provider(self):
        """GIVEN the gitlab provider scenario."""
        from opsportal.config.manifest import SourceProvider, ToolSource

        """WHEN executing."""
        src = ToolSource(
            provider=SourceProvider.GITLAB,
            repository="org/repo",
            ref="main",
            package="mypackage",
        )

        """THEN the result is correct."""
        assert "gitlab.com" in src.git_url

    def test_is_remote_managed_property(self):
        """GIVEN the is remote managed property scenario."""
        from opsportal.config.manifest import ToolConfig, ToolSource

        source = ToolSource(repository="a/b", package="test")

        """WHEN executing."""
        tc = ToolConfig(
            slug="test",
            display_name="Test",
            integration_mode="subprocess_web",
            source=source,
        )

        """THEN the result is correct."""
        assert tc.is_remote_managed is True

    def test_local_dev_not_remote_managed(self):
        """GIVEN the local dev not remote managed scenario."""
        from opsportal.config.manifest import ToolConfig

        """WHEN executing."""
        tc = ToolConfig(
            slug="test",
            display_name="Test",
            integration_mode="subprocess_web",
            repo_path="/tmp/test",
        )

        """THEN the result is correct."""
        assert tc.is_remote_managed is False


# ---------------------------------------------------------------------------
# ToolInstaller tests
# ---------------------------------------------------------------------------


class TestToolInstaller:
    """Validate ToolInstaller service."""

    def test_work_dir_creation(self, tmp_path: Path):
        """GIVEN the work dir creation scenario."""
        from opsportal.services.tool_installer import ToolInstaller

        installer = ToolInstaller(tmp_path / "tools")

        """WHEN executing."""
        wd = installer.work_dir_for("releasepilot")

        """THEN the result is correct."""
        assert wd.exists()
        assert wd.name == "releasepilot"

    def test_is_installed_true(self, tmp_path: Path):
        """GIVEN the is installed true scenario."""
        from opsportal.services.tool_installer import ToolInstaller

        """WHEN executing."""
        installer = ToolInstaller(tmp_path)

        """THEN the result is correct."""
        with patch("importlib.metadata.distribution"):
            assert installer.is_installed("releasepilot") is True

    def test_is_installed_false(self, tmp_path: Path):
        """GIVEN the is installed false scenario."""
        from opsportal.services.tool_installer import ToolInstaller

        """WHEN executing."""
        installer = ToolInstaller(tmp_path)

        """THEN the result is correct."""
        with patch("importlib.metadata.distribution", side_effect=Exception):
            assert installer.is_installed("nonexistent-package") is False

    def test_pre_installed_strategy_verifies(self, tmp_path: Path):
        """GIVEN the pre installed strategy verifies scenario."""
        from opsportal.config.manifest import InstallStrategy, ToolSource
        from opsportal.services.tool_installer import ToolInstaller

        installer = ToolInstaller(tmp_path)
        src = ToolSource(
            repository="a/b",
            package="releasepilot",
            install_strategy=InstallStrategy.PRE_INSTALLED,
        )

        """WHEN executing."""
        with (
            patch.object(installer, "is_installed", return_value=True),
            patch.object(installer, "installed_version", return_value="1.0.0"),
        ):
            result = installer.install(src)

        """THEN the result is correct."""
        assert result["action"] == "verified"

    def test_ensure_installed_skips_if_present(self, tmp_path: Path):
        """GIVEN the ensure installed skips if present scenario."""
        from opsportal.config.manifest import ToolSource
        from opsportal.services.tool_installer import ToolInstaller

        installer = ToolInstaller(tmp_path)
        src = ToolSource(
            repository="a/b",
            ref="v1.0.0",
            package="releasepilot",
        )

        """WHEN executing."""
        with (
            patch.object(installer, "is_installed", return_value=True),
            patch.object(installer, "installed_version", return_value="1.0.0"),
        ):
            result = installer.ensure_installed(src)

        """THEN the result is correct."""
        assert result["action"] == "already_installed"


# ---------------------------------------------------------------------------
# Manifest loading with source block
# ---------------------------------------------------------------------------


class TestManifestSourceParsing:
    """Verify manifest loader handles source blocks correctly."""

    def test_load_with_source_no_repo_path(self, tmp_path: Path):
        """GIVEN the load with source no repo path scenario."""
        from opsportal.config.manifest import load_manifest

        manifest_yaml = tmp_path / "opsportal.yaml"
        manifest_yaml.write_text("""
tools:
  releasepilot:
    display_name: ReleasePilot
    description: Test tool
    integration_mode: subprocess_web
    port: 8082
    source:
      repository: POLPROG-TECH/ReleasePilot
      ref: v1.1.0
      package: releasepilot
      extras: [all]
""")
        manifest = load_manifest(manifest_yaml, tmp_path)

        """WHEN executing."""
        tool = manifest.get_tool("releasepilot")

        """THEN the result is correct."""
        assert tool is not None
        assert tool.source is not None
        assert tool.repo_path is None
        assert tool.is_remote_managed is True
        assert tool.source.repository == "POLPROG-TECH/ReleasePilot"

    def test_load_with_both_source_and_repo_path(self, tmp_path: Path):
        """GIVEN the load with both source and repo path scenario."""
        from opsportal.config.manifest import load_manifest

        repo = tmp_path / "ReleasePilot"
        repo.mkdir()
        manifest_yaml = tmp_path / "opsportal.yaml"
        manifest_yaml.write_text(f"""
tools:
  releasepilot:
    display_name: ReleasePilot
    integration_mode: subprocess_web
    port: 8082
    repo_path: {repo}
    source:
      repository: POLPROG-TECH/ReleasePilot
      ref: v1.1.0
      package: releasepilot
""")
        manifest = load_manifest(manifest_yaml, tmp_path)

        """WHEN executing."""
        tool = manifest.get_tool("releasepilot")

        """THEN the result is correct."""
        assert tool is not None
        assert tool.source is not None
        assert tool.repo_path is not None
        # Not remote-managed because repo_path is set
        assert tool.is_remote_managed is False

    def test_load_legacy_repo_path_only(self, tmp_path: Path):
        """GIVEN the load legacy repo path only scenario."""
        from opsportal.config.manifest import load_manifest

        repo = tmp_path / "MyTool"
        repo.mkdir()
        manifest_yaml = tmp_path / "opsportal.yaml"
        manifest_yaml.write_text(f"""
tools:
  mytool:
    display_name: MyTool
    integration_mode: subprocess_web
    repo_path: {repo}
""")
        manifest = load_manifest(manifest_yaml, tmp_path)

        """WHEN executing."""
        tool = manifest.get_tool("mytool")

        """THEN the result is correct."""
        assert tool is not None
        assert tool.source is None
        assert tool.repo_path is not None


# ---------------------------------------------------------------------------
# Adapter work_dir support
# ---------------------------------------------------------------------------


class TestAdapterWorkDir:
    """Verify adapters work with work_dir instead of repo_path."""

    def test_releasepilot_effective_cwd_uses_work_dir(self, tmp_path: Path):
        """GIVEN the releasepilot effective cwd uses work dir scenario."""
        from opsportal.adapters.releasepilot import ReleasePilotAdapter
        from opsportal.services.process_manager import ProcessManager

        pm = ProcessManager()
        wd = tmp_path / "rp"
        wd.mkdir()

        """WHEN executing."""
        adapter = ReleasePilotAdapter(pm, work_dir=wd, port=8082)

        """THEN the result is correct."""
        assert adapter.effective_cwd == wd
        assert adapter.repo_path is None

    def test_releaseboard_effective_cwd_prefers_repo_path(self, tmp_path: Path):
        """GIVEN the releaseboard effective cwd prefers repo path scenario."""
        from opsportal.adapters.releaseboard import ReleaseBoardAdapter
        from opsportal.services.process_manager import ProcessManager

        pm = ProcessManager()
        repo = tmp_path / "repo"
        repo.mkdir()
        wd = tmp_path / "work"
        wd.mkdir()

        """WHEN executing."""
        adapter = ReleaseBoardAdapter(pm, repo_path=repo, work_dir=wd, port=8081)

        """THEN the result is correct."""
        assert adapter.effective_cwd == repo

    def test_config_mixin_uses_work_dir(self, tmp_path: Path):
        """GIVEN the config mixin uses work dir scenario."""
        from opsportal.adapters.releasepilot import ReleasePilotAdapter
        from opsportal.services.process_manager import ProcessManager

        pm = ProcessManager()
        wd = tmp_path / "rp"
        wd.mkdir()
        adapter = ReleasePilotAdapter(pm, work_dir=wd, port=8082)
        # Config path should resolve to work_dir

        """WHEN executing."""
        cfg_path = adapter._resolve_config_path()

        """THEN the result is correct."""
        assert str(wd) in str(cfg_path)

    def test_scaffold_default_config_creates_file(self, tmp_path: Path):
        """GIVEN the scaffold default config creates file scenario."""
        from opsportal.adapters.releasepilot import ReleasePilotAdapter
        from opsportal.services.process_manager import ProcessManager

        pm = ProcessManager()
        wd = tmp_path / "rp"
        wd.mkdir()

        """WHEN executing."""
        adapter = ReleasePilotAdapter(pm, work_dir=wd, port=8082)
        # Before scaffold — no config

        """THEN the result is correct."""
        assert adapter.config_file_path() is None
        # Scaffold creates default from schema
        created = adapter.scaffold_default_config()
        if adapter.config_schema() is not None:
            assert created is True
            assert adapter.config_file_path() is not None
            import json

            data = json.loads(adapter.config_file_path().read_text())
            assert "language" in data  # schema default field

    def test_scaffold_skips_existing_config(self, tmp_path: Path):
        """GIVEN the scaffold skips existing config scenario."""
        from opsportal.adapters.releasepilot import ReleasePilotAdapter
        from opsportal.services.process_manager import ProcessManager

        pm = ProcessManager()
        wd = tmp_path / "rp"
        wd.mkdir()
        (wd / ".releasepilot.json").write_text('{"language": "pl"}')
        adapter = ReleasePilotAdapter(pm, work_dir=wd, port=8082)

        """WHEN executing."""
        created = adapter.scaffold_default_config()

        """THEN the result is correct."""
        assert created is False
        # Original content preserved
        import json

        data = json.loads((wd / ".releasepilot.json").read_text())
        assert data["language"] == "pl"


# ---------------------------------------------------------------------------
# Settings work dir
# ---------------------------------------------------------------------------


class TestSettingsWorkDir:
    """Verify tools_work_dir derivation in settings."""

    def test_default_tools_work_dir(self, tmp_path: Path, monkeypatch):
        """GIVEN the default tools work dir scenario."""
        monkeypatch.chdir(tmp_path)
        from opsportal.core.settings import PortalSettings

        """WHEN executing."""
        s = PortalSettings()
        # tools_work_dir should be work_dir / "tools"

        """THEN the result is correct."""
        assert s.tools_work_dir == s.work_dir / "tools"


# ---------------------------------------------------------------------------
# Default manifest generation and CLI bootstrap
# ---------------------------------------------------------------------------


class TestDefaultManifest:
    """Verify DEFAULT_MANIFEST_YAML and CLI init / auto-bootstrap."""

    def test_default_manifest_is_valid_yaml(self):
        """GIVEN the default manifest is valid yaml scenario."""
        import yaml

        from opsportal.config.manifest import DEFAULT_MANIFEST_YAML

        """WHEN executing."""
        data = yaml.safe_load(DEFAULT_MANIFEST_YAML)

        """THEN the result is correct."""
        assert "tools" in data
        assert "releasepilot" in data["tools"]
        assert "releaseboard" in data["tools"]

    def test_default_manifest_has_source_blocks(self):
        """GIVEN the default manifest has source blocks scenario."""

        """WHEN executing."""
        import yaml

        from opsportal.config.manifest import DEFAULT_MANIFEST_YAML

        data = yaml.safe_load(DEFAULT_MANIFEST_YAML)

        """THEN the result is correct."""
        for slug in ("releasepilot", "releaseboard"):
            src = data["tools"][slug].get("source")
            assert src is not None, f"{slug} missing source block"
            assert "repository" in src
            assert "ref" in src

    def test_ensure_manifest_creates_file(self, tmp_path: Path):
        """GIVEN the ensure manifest creates file scenario."""

        """WHEN executing."""
        manifest = tmp_path / "opsportal.yaml"

        """THEN the result is correct."""
        assert not manifest.exists()

        from opsportal.__main__ import _ensure_manifest

        _ensure_manifest(manifest)
        assert manifest.exists()
        import yaml

        data = yaml.safe_load(manifest.read_text())
        assert "tools" in data

    def test_ensure_manifest_skips_existing(self, tmp_path: Path):
        """GIVEN the ensure manifest skips existing scenario."""
        manifest = tmp_path / "opsportal.yaml"
        manifest.write_text("tools: {}")

        from opsportal.__main__ import _ensure_manifest

        """WHEN executing."""
        _ensure_manifest(manifest)

        """THEN the result is correct."""
        assert manifest.read_text() == "tools: {}"

    def test_init_command_creates_manifest(self, tmp_path: Path):
        """GIVEN the init command creates manifest scenario."""
        from typer.testing import CliRunner

        from opsportal.__main__ import app

        runner = CliRunner()
        target = tmp_path / "opsportal.yaml"

        """WHEN executing."""
        result = runner.invoke(app, ["init", str(target)])

        """THEN the result is correct."""
        assert result.exit_code == 0
        assert target.exists()
        assert "Created" in result.output

    def test_init_refuses_overwrite_without_force(self, tmp_path: Path):
        """GIVEN the init refuses overwrite without force scenario."""
        from typer.testing import CliRunner

        from opsportal.__main__ import app

        runner = CliRunner()
        target = tmp_path / "opsportal.yaml"
        target.write_text("tools: {}")

        """WHEN executing."""
        result = runner.invoke(app, ["init", str(target)])

        """THEN the result is correct."""
        assert result.exit_code != 0
        assert "already exists" in result.output

    def test_init_force_overwrites(self, tmp_path: Path):
        """GIVEN the init force overwrites scenario."""
        from typer.testing import CliRunner

        from opsportal.__main__ import app

        runner = CliRunner()
        target = tmp_path / "opsportal.yaml"
        target.write_text("tools: {}")

        """WHEN executing."""
        result = runner.invoke(app, ["init", "--force", str(target)])

        """THEN the result is correct."""
        assert result.exit_code == 0
        import yaml

        data = yaml.safe_load(target.read_text())
        assert "releasepilot" in data["tools"]
