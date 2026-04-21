"""Tests for LocaleSync adapter - config scaffolding, version handling, setup flow."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from opsportal.adapters.base import IntegrationMode, ToolCapability
from opsportal.adapters.localesync import (
    _LOCALESYNC_DEFAULT_CONFIG,
    LocaleSyncAdapter,
)
from opsportal.services.process_manager import (
    ManagedProcess,
    ProcessManager,
    ProcessStatus,
)


@pytest.fixture()
def pm() -> ProcessManager:
    return ProcessManager()


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    d = tmp_path / "repo"
    d.mkdir()
    return d


# ---------------------------------------------------------------------------
# Identity & Metadata
# ---------------------------------------------------------------------------


"""GIVEN a LocaleSync adapter instance"""


def test_slug_is_localesync(repo: Path, pm: ProcessManager) -> None:
    adapter = LocaleSyncAdapter(repo_path=repo, process_manager=pm)

    """WHEN reading the slug property"""

    """THEN its slug is 'localesync'"""
    assert adapter.slug == "localesync"


"""GIVEN a LocaleSync adapter instance"""


def test_display_name(repo: Path, pm: ProcessManager) -> None:
    adapter = LocaleSyncAdapter(repo_path=repo, process_manager=pm)

    """WHEN reading the display_name property"""

    """THEN its display name is 'LocaleSync'"""
    assert adapter.display_name == "LocaleSync"


"""GIVEN a LocaleSync adapter instance"""


def test_color_is_teal(repo: Path, pm: ProcessManager) -> None:
    adapter = LocaleSyncAdapter(repo_path=repo, process_manager=pm)

    """WHEN reading the color property"""

    """THEN its color is the expected teal hex"""
    assert adapter.color == "#0891B2"


"""GIVEN a LocaleSync adapter instance"""


def test_icon_is_globe(repo: Path, pm: ProcessManager) -> None:
    adapter = LocaleSyncAdapter(repo_path=repo, process_manager=pm)

    """WHEN reading the icon property"""

    """THEN its icon is 'globe'"""
    assert adapter.icon == "globe"


"""GIVEN a LocaleSync adapter instance"""


def test_description_is_meaningful(repo: Path, pm: ProcessManager) -> None:
    adapter = LocaleSyncAdapter(repo_path=repo, process_manager=pm)

    """WHEN reading the description property"""

    """THEN its description mentions relevant keywords"""
    desc = adapter.description.lower()
    assert "translation" in desc or "locale" in desc


"""GIVEN a LocaleSync adapter instance"""


def test_integration_mode_is_subprocess_web(repo: Path, pm: ProcessManager) -> None:
    adapter = LocaleSyncAdapter(repo_path=repo, process_manager=pm)

    """WHEN reading the integration_mode property"""

    """THEN its integration mode is SUBPROCESS_WEB"""
    assert adapter.integration_mode == IntegrationMode.SUBPROCESS_WEB


"""GIVEN a LocaleSync adapter instance"""


def test_capabilities_include_configurable(repo: Path, pm: ProcessManager) -> None:
    adapter = LocaleSyncAdapter(repo_path=repo, process_manager=pm)

    """WHEN reading the capabilities set"""

    """THEN CONFIGURABLE is present in capabilities"""
    assert ToolCapability.CONFIGURABLE in adapter.capabilities


# ---------------------------------------------------------------------------
# Port configuration
# ---------------------------------------------------------------------------


"""GIVEN a LocaleSync adapter with default port"""


def test_default_port_is_8083(repo: Path, pm: ProcessManager) -> None:
    adapter = LocaleSyncAdapter(repo_path=repo, process_manager=pm)

    """WHEN reading the internal port"""

    """THEN the internal port is 8083"""
    assert adapter._port == 8083


"""GIVEN a custom port"""


def test_custom_port(repo: Path, pm: ProcessManager) -> None:
    adapter = LocaleSyncAdapter(repo_path=repo, process_manager=pm, port=9090)

    """WHEN reading the internal port"""

    """THEN the adapter uses the custom port"""
    assert adapter._port == 9090


# ---------------------------------------------------------------------------
# Config scaffolding
# ---------------------------------------------------------------------------


"""GIVEN an adapter pointing to an empty work directory"""


def test_scaffold_creates_default_config(tmp_path: Path, pm: ProcessManager) -> None:
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    adapter = LocaleSyncAdapter(work_dir=work_dir, process_manager=pm)

    """WHEN scaffolding the default config"""
    created = adapter.scaffold_default_config()

    """THEN a config file is created with the expected defaults"""
    assert created is True
    config_path = work_dir / "localesync.json"
    assert config_path.exists()
    data = json.loads(config_path.read_text())
    assert data["source_locale"] == "en"
    assert "pl" in data["target_locales"]


"""GIVEN a work directory with an existing config"""


def test_scaffold_does_not_overwrite_existing(tmp_path: Path, pm: ProcessManager) -> None:
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    config_path = work_dir / "localesync.json"
    config_path.write_text('{"source_locale": "fr"}')
    adapter = LocaleSyncAdapter(work_dir=work_dir, process_manager=pm)

    """WHEN scaffolding is attempted"""
    created = adapter.scaffold_default_config()

    """THEN no file is created and the original content is preserved"""
    assert created is False
    data = json.loads(config_path.read_text())
    assert data["source_locale"] == "fr"


"""GIVEN the default config constant"""


def test_builtin_default_config_has_required_keys() -> None:
    """WHEN inspecting the config keys"""

    """THEN it includes source_locale, target_locales, and format"""
    assert "source_locale" in _LOCALESYNC_DEFAULT_CONFIG
    assert "target_locales" in _LOCALESYNC_DEFAULT_CONFIG
    assert "format" in _LOCALESYNC_DEFAULT_CONFIG


# ---------------------------------------------------------------------------
# Config resolution
# ---------------------------------------------------------------------------


"""GIVEN a repo with an existing config file"""


def test_config_resolves_to_repo_path(tmp_path: Path, pm: ProcessManager) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    config = repo / "localesync.json"
    config.write_text("{}")
    adapter = LocaleSyncAdapter(repo_path=repo, process_manager=pm)

    """WHEN resolving the config file path"""

    """THEN config_file_path returns the repo-based path"""
    assert adapter.config_file_path() == config


"""GIVEN a work directory with a config file but no repo_path"""


def test_config_resolves_to_work_dir(tmp_path: Path, pm: ProcessManager) -> None:
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    config = work_dir / "localesync.json"
    config.write_text("{}")
    adapter = LocaleSyncAdapter(work_dir=work_dir, process_manager=pm)

    """WHEN resolving the config file path"""

    """THEN config_file_path returns the work_dir-based path"""
    assert adapter.config_file_path() == config


"""GIVEN an env var pointing to a config file"""


def test_config_env_override(tmp_path: Path, pm: ProcessManager) -> None:
    env_config = tmp_path / "custom.json"
    env_config.write_text("{}")
    adapter = LocaleSyncAdapter(process_manager=pm)

    """WHEN the env var is set"""
    with patch.dict("os.environ", {"OPSPORTAL_LOCALESYNC_CONFIG": str(env_config)}):
        path = adapter._resolve_config_path()

    """THEN the resolved path matches the env var"""
    assert path == env_config.resolve()


# ---------------------------------------------------------------------------
# Version handling
# ---------------------------------------------------------------------------


"""GIVEN a LocaleSync adapter"""


def test_version_returns_installed_version(repo: Path, pm: ProcessManager) -> None:
    adapter = LocaleSyncAdapter(repo_path=repo, process_manager=pm)

    """WHEN importlib.metadata.version finds the package"""
    with patch("importlib.metadata.version", return_value="1.1.0"):
        version = adapter.get_version()

    """THEN it returns the installed version string"""
    assert version == "1.1.0"


"""GIVEN a LocaleSync adapter"""


def test_version_returns_string_when_available(repo: Path, pm: ProcessManager) -> None:
    adapter = LocaleSyncAdapter(repo_path=repo, process_manager=pm)

    """WHEN importlib.metadata.version returns a value"""
    with patch(
        "opsportal.adapters.localesync.LocaleSyncAdapter.get_version",
        return_value="1.0.0",
    ):
        version = adapter.get_version()

    """THEN it returns the version string"""
    assert version == "1.0.0"


# ---------------------------------------------------------------------------
# Process lifecycle
# ---------------------------------------------------------------------------


"""GIVEN a mocked process_manager returning a RUNNING process"""


@pytest.mark.asyncio
async def test_ensure_ready_delegates_to_process_manager(repo: Path, pm: ProcessManager) -> None:
    managed = ManagedProcess(
        name="localesync",
        command=["locale-sync", "serve", "--port", "8083"],
        status=ProcessStatus.RUNNING,
    )
    pm.ensure_running = AsyncMock(return_value=managed)

    """WHEN calling ensure_ready with a valid CLI binary"""
    with patch("shutil.which", return_value="/usr/bin/locale-sync"):
        adapter = LocaleSyncAdapter(repo_path=repo, process_manager=pm, port=8083)
        result = await adapter.ensure_ready()

    """THEN it reports ready with the expected web URL"""
    assert result.ready is True
    assert result.web_url == "http://127.0.0.1:8083"
    pm.ensure_running.assert_called_once()
    call_args = pm.ensure_running.call_args
    assert call_args[0][0] == "localesync"
    assert "--port" in call_args[0][1]
    assert "8083" in call_args[0][1]


"""GIVEN a mocked process_manager returning a FAILED process"""


@pytest.mark.asyncio
async def test_ensure_ready_returns_error_on_failure(repo: Path, pm: ProcessManager) -> None:
    managed = ManagedProcess(
        name="localesync",
        command=["locale-sync", "serve", "--port", "8083"],
        status=ProcessStatus.FAILED,
    )
    pm.ensure_running = AsyncMock(return_value=managed)
    pm.get_logs = MagicMock(return_value=["error: bind failed"])

    """WHEN calling ensure_ready"""
    with patch("shutil.which", return_value="/usr/bin/locale-sync"):
        adapter = LocaleSyncAdapter(repo_path=repo, process_manager=pm, port=8083)
        result = await adapter.ensure_ready()

    """THEN it reports not ready with a 'failed to start' error"""
    assert result.ready is False
    assert "failed to start" in result.error.lower()


"""GIVEN an adapter with a non-existent CLI binary"""


@pytest.mark.asyncio
async def test_ensure_ready_fails_when_cli_missing(repo: Path, pm: ProcessManager) -> None:
    adapter = LocaleSyncAdapter(
        repo_path=repo, process_manager=pm, cli_binary="nonexistent-binary"
    )

    """WHEN calling ensure_ready"""
    result = await adapter.ensure_ready()

    """THEN it reports not ready with 'not found' in the error"""
    assert result.ready is False
    assert "not found" in result.error.lower()


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------


"""GIVEN a LocaleSync adapter"""


def test_actions_include_stop_and_restart(repo: Path, pm: ProcessManager) -> None:
    adapter = LocaleSyncAdapter(repo_path=repo, process_manager=pm)

    """WHEN listing actions"""
    action_names = {a.name for a in adapter.get_actions()}

    """THEN stop and restart are available"""
    assert "stop" in action_names
    assert "restart" in action_names


"""GIVEN a mocked process_manager"""


@pytest.mark.asyncio
async def test_stop_action_delegates_to_process_manager(repo: Path, pm: ProcessManager) -> None:
    pm.stop = AsyncMock()
    adapter = LocaleSyncAdapter(repo_path=repo, process_manager=pm)

    """WHEN running the stop action"""
    result = await adapter.run_action("stop", {})

    """THEN the stop was successful"""
    assert result.success is True
    pm.stop.assert_called_once_with("localesync", port=8083)


"""GIVEN a LocaleSync adapter"""


@pytest.mark.asyncio
async def test_unknown_action_returns_error(repo: Path, pm: ProcessManager) -> None:
    adapter = LocaleSyncAdapter(repo_path=repo, process_manager=pm)

    """WHEN running an unknown action"""
    result = await adapter.run_action("explode", {})

    """THEN it returns an error"""
    assert result.success is False
    assert "unknown" in result.error.lower()


# ---------------------------------------------------------------------------
# Environment variable propagation
# ---------------------------------------------------------------------------


"""GIVEN a LocaleSync adapter with custom portal origins"""


def test_cors_origins_propagated(repo: Path, pm: ProcessManager) -> None:
    adapter = LocaleSyncAdapter(
        repo_path=repo,
        process_manager=pm,
        portal_origins="http://portal:8000,http://localhost:8000",
    )

    """WHEN inspecting the adapter environment variables"""

    """THEN LOCALESYNC_CORS_ORIGINS is set to the provided origins"""
    assert adapter._env["LOCALESYNC_CORS_ORIGINS"] == "http://portal:8000,http://localhost:8000"


"""GIVEN custom env vars"""


def test_custom_env_vars_merged(repo: Path, pm: ProcessManager) -> None:
    adapter = LocaleSyncAdapter(
        repo_path=repo,
        process_manager=pm,
        env={"MY_VAR": "hello"},
    )

    """WHEN inspecting the adapter environment variables"""

    """THEN the custom var is present alongside framing/CORS vars"""
    assert adapter._env["MY_VAR"] == "hello"
    assert adapter._env["LOCALESYNC_ALLOW_FRAMING"] == "true"


# ---------------------------------------------------------------------------
# Web URL
# ---------------------------------------------------------------------------


"""GIVEN a LocaleSync adapter with no running process"""


def test_web_url_none_when_stopped(repo: Path, pm: ProcessManager) -> None:
    adapter = LocaleSyncAdapter(repo_path=repo, process_manager=pm)

    """WHEN calling get_web_url"""

    """THEN get_web_url returns None"""
    assert adapter.get_web_url() is None


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


"""GIVEN a LocaleSync adapter with no running process"""


@pytest.mark.asyncio
async def test_health_unhealthy_when_stopped(repo: Path, pm: ProcessManager) -> None:
    adapter = LocaleSyncAdapter(repo_path=repo, process_manager=pm)

    """WHEN checking health"""
    result = await adapter.health_check()

    """THEN it is unhealthy with 'not running' message"""
    assert result.healthy is False
    assert "not running" in result.message.lower()


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


"""GIVEN an adapter with an empty work directory"""


@pytest.mark.asyncio
async def test_startup_scaffolds_config(tmp_path: Path, pm: ProcessManager) -> None:
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    adapter = LocaleSyncAdapter(work_dir=work_dir, process_manager=pm)

    """WHEN startup is called"""
    await adapter.startup()

    """THEN a config file is created"""
    assert (work_dir / "localesync.json").exists()


"""GIVEN a mocked process_manager"""


@pytest.mark.asyncio
async def test_shutdown_stops_server(repo: Path, pm: ProcessManager) -> None:
    pm.stop = AsyncMock()
    adapter = LocaleSyncAdapter(repo_path=repo, process_manager=pm)

    """WHEN shutdown is called"""
    await adapter.shutdown()

    """THEN the process was stopped"""
    pm.stop.assert_called_once_with("localesync", port=8083)
