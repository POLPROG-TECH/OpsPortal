"""Tests for the unified SUBPROCESS_WEB adapter architecture.

Both tool adapters follow the same pattern:
- SUBPROCESS_WEB integration mode
- WEB_UI + HEALTH_CHECK + PROCESS capabilities
- Process manager + port-based lifecycle
- Health check via HTTP /health/live
- ensure_ready() auto-starts the tool server
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from opsportal.adapters.appsecone import AppSecOneAdapter
from opsportal.adapters.base import IntegrationMode, ToolCapability, ToolStatus
from opsportal.adapters.flowboard import FlowBoardAdapter
from opsportal.adapters.localesync import LocaleSyncAdapter
from opsportal.adapters.releaseboard import ReleaseBoardAdapter
from opsportal.adapters.releasepilot import ReleasePilotAdapter
from opsportal.services.process_manager import ManagedProcess, ProcessManager, ProcessStatus


@pytest.fixture()
def pm() -> ProcessManager:
    return ProcessManager()


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    d = tmp_path / "repo"
    d.mkdir()
    return d


# ---------------------------------------------------------------------------
# All adapters share the same integration surface
# ---------------------------------------------------------------------------

_ADAPTER_CLASSES = [
    ("releasepilot", ReleasePilotAdapter, "releasepilot", 8082),
    ("releaseboard", ReleaseBoardAdapter, "releaseboard", 8081),
    ("localesync", LocaleSyncAdapter, "locale-sync", 8083),
    ("flowboard", FlowBoardAdapter, "flowboard", 8084),
    ("appsecone", AppSecOneAdapter, "appsecone", 8085),
]


def _make_adapter(cls, repo: Path, pm: ProcessManager, port: int, cli: str):
    """Factory to create any adapter with the right constructor."""
    return cls(repo_path=repo, process_manager=pm, port=port, cli_binary=cli)


"""GIVEN an adapter instance"""


@pytest.mark.parametrize("slug,cls,cli,port", _ADAPTER_CLASSES)
def test_all_adapters_are_subprocess_web(slug, cls, cli, port, repo, pm):
    adapter = _make_adapter(cls, repo, pm, port, cli)

    """WHEN inspecting the integration mode"""

    """THEN its integration mode is SUBPROCESS_WEB"""
    assert adapter.integration_mode == IntegrationMode.SUBPROCESS_WEB


"""GIVEN an adapter instance"""


@pytest.mark.parametrize("slug,cls,cli,port", _ADAPTER_CLASSES)
def test_all_adapters_have_web_capabilities(slug, cls, cli, port, repo, pm):
    adapter = _make_adapter(cls, repo, pm, port, cli)

    """WHEN inspecting capabilities"""
    caps = adapter.capabilities

    """THEN all expected capabilities are present"""
    assert ToolCapability.WEB_UI in caps
    assert ToolCapability.HEALTH_CHECK in caps
    assert ToolCapability.PROCESS in caps


"""GIVEN an adapter instance"""


@pytest.mark.parametrize("slug,cls,cli,port", _ADAPTER_CLASSES)
def test_all_adapters_have_correct_slug(slug, cls, cli, port, repo, pm):
    adapter = _make_adapter(cls, repo, pm, port, cli)

    """WHEN inspecting the slug"""

    """THEN its slug matches the parametrized value"""
    assert adapter.slug == slug


"""GIVEN an adapter instance"""


@pytest.mark.parametrize("slug,cls,cli,port", _ADAPTER_CLASSES)
def test_all_adapters_have_stop_restart_actions(slug, cls, cli, port, repo, pm):
    adapter = _make_adapter(cls, repo, pm, port, cli)
    actions = adapter.get_actions()

    """WHEN collecting action names"""
    action_names = {a.name for a in actions}

    """THEN stop and restart are available"""
    assert "stop" in action_names
    assert "restart" in action_names


"""GIVEN an adapter with no running process"""


@pytest.mark.parametrize("slug,cls,cli,port", _ADAPTER_CLASSES)
@pytest.mark.asyncio
async def test_status_stopped_when_no_process(slug, cls, cli, port, repo, pm):
    adapter = _make_adapter(cls, repo, pm, port, cli)

    """WHEN checking status"""
    status = await adapter.get_status()

    """THEN it is STOPPED"""
    assert status == ToolStatus.STOPPED


"""GIVEN an adapter with no running process"""


@pytest.mark.parametrize("slug,cls,cli,port", _ADAPTER_CLASSES)
@pytest.mark.asyncio
async def test_health_not_running(slug, cls, cli, port, repo, pm):
    adapter = _make_adapter(cls, repo, pm, port, cli)

    """WHEN running a health check"""
    h = await adapter.health_check()

    """THEN it reports unhealthy with a 'not running' message"""
    assert h.healthy is False
    assert "not running" in h.message.lower()


"""GIVEN an adapter with no running process"""


@pytest.mark.parametrize("slug,cls,cli,port", _ADAPTER_CLASSES)
@pytest.mark.asyncio
async def test_web_url_none_when_not_running(slug, cls, cli, port, repo, pm):
    adapter = _make_adapter(cls, repo, pm, port, cli)

    """WHEN requesting the web URL"""

    """THEN get_web_url returns None"""
    assert adapter.get_web_url() is None


"""GIVEN an adapter configured with a non-existent CLI binary"""


@pytest.mark.parametrize("slug,cls,cli,port", _ADAPTER_CLASSES)
@pytest.mark.asyncio
async def test_ensure_ready_fails_when_cli_missing(slug, cls, cli, port, repo, pm):
    adapter = _make_adapter(cls, repo, pm, port, "nonexistent-binary-xyz")

    """WHEN calling ensure_ready"""
    result = await adapter.ensure_ready()

    """THEN it reports not ready with a 'not found' error"""
    assert result.ready is False
    assert "not found" in result.error.lower()


# ---------------------------------------------------------------------------
# ALLOW_FRAMING env var is set for each adapter
# ---------------------------------------------------------------------------


"""GIVEN a ReleasePilot adapter"""


def test_releasepilot_sets_allow_framing(repo, pm):
    adapter = ReleasePilotAdapter(repo_path=repo, process_manager=pm)

    """WHEN inspecting the environment variables"""

    """THEN RELEASEPILOT_ALLOW_FRAMING is set to 'true'"""
    assert adapter._env.get("RELEASEPILOT_ALLOW_FRAMING") == "true"


"""GIVEN a ReleaseBoard adapter"""


def test_releaseboard_sets_allow_framing(repo, pm):
    adapter = ReleaseBoardAdapter(repo_path=repo, process_manager=pm)

    """WHEN inspecting the environment variables"""

    """THEN RELEASEBOARD_ALLOW_FRAMING is set to 'true'"""
    assert adapter._env.get("RELEASEBOARD_ALLOW_FRAMING") == "true"


"""GIVEN a LocaleSync adapter"""


def test_localesync_sets_allow_framing(repo, pm):
    adapter = LocaleSyncAdapter(repo_path=repo, process_manager=pm)

    """WHEN inspecting the environment variables"""

    """THEN LOCALESYNC_ALLOW_FRAMING is set to 'true'"""
    assert adapter._env.get("LOCALESYNC_ALLOW_FRAMING") == "true"


"""GIVEN a FlowBoard adapter"""


def test_flowboard_sets_allow_framing(repo, pm):
    adapter = FlowBoardAdapter(repo_path=repo, process_manager=pm)

    """WHEN inspecting the environment variables"""

    """THEN FLOWBOARD_ALLOW_FRAMING is set to 'true'"""
    assert adapter._env.get("FLOWBOARD_ALLOW_FRAMING") == "true"


"""GIVEN an AppSecOne adapter"""


def test_appsecone_sets_allow_framing(repo, pm):
    adapter = AppSecOneAdapter(repo_path=repo, process_manager=pm)

    """WHEN inspecting the environment variables"""

    """THEN APPSECONE_ALLOW_FRAMING is set to 'true'"""
    assert adapter._env.get("APPSECONE_ALLOW_FRAMING") == "true"


# ---------------------------------------------------------------------------
# Integration: ensure_ready delegates to process_manager.ensure_running
# ---------------------------------------------------------------------------


"""GIVEN a mocked process_manager returning a RUNNING process"""


@pytest.mark.asyncio
async def test_ensure_ready_calls_process_manager(repo, pm):
    managed = ManagedProcess(
        name="releasepilot",
        command=["releasepilot", "serve", "--port", "8082"],
        status=ProcessStatus.RUNNING,
    )
    pm.ensure_running = AsyncMock(return_value=managed)

    """WHEN calling ensure_ready with a valid CLI binary"""
    with patch("shutil.which", return_value="/usr/bin/releasepilot"):
        adapter = ReleasePilotAdapter(repo_path=repo, process_manager=pm, port=8082)
        result = await adapter.ensure_ready()

    """THEN it reports ready with the expected web URL and correct process args"""
    assert result.ready is True
    assert result.web_url == "http://127.0.0.1:8082"
    pm.ensure_running.assert_called_once()
    call_args = pm.ensure_running.call_args
    assert call_args[0][0] == "releasepilot"  # process name
    assert "--port" in call_args[0][1]
    assert "8082" in call_args[0][1]


"""GIVEN a mocked process_manager returning a FAILED process"""


@pytest.mark.asyncio
async def test_ensure_ready_returns_error_on_failure(repo, pm):
    managed = ManagedProcess(
        name="releasepilot",
        command=["releasepilot", "serve", "--port", "8082"],
        status=ProcessStatus.FAILED,
    )
    pm.ensure_running = AsyncMock(return_value=managed)
    pm.get_logs = MagicMock(return_value=["error: bind failed"])

    """WHEN calling ensure_ready"""
    with patch("shutil.which", return_value="/usr/bin/releasepilot"):
        adapter = ReleasePilotAdapter(repo_path=repo, process_manager=pm, port=8082)
        result = await adapter.ensure_ready()

    """THEN it reports not ready with a 'failed to start' error"""
    assert result.ready is False
    assert "failed to start" in result.error.lower()
