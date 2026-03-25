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

from opsportal.adapters.base import IntegrationMode, ToolCapability, ToolStatus
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
]


def _make_adapter(cls, repo: Path, pm: ProcessManager, port: int, cli: str):
    """Factory to create any adapter with the right constructor."""
    return cls(repo_path=repo, process_manager=pm, port=port, cli_binary=cli)


@pytest.mark.parametrize("slug,cls,cli,port", _ADAPTER_CLASSES)
def test_all_adapters_are_subprocess_web(slug, cls, cli, port, repo, pm):
    """GIVEN the all adapters are subprocess web scenario."""

    """WHEN executing."""
    adapter = _make_adapter(cls, repo, pm, port, cli)

    """THEN the result is correct."""
    assert adapter.integration_mode == IntegrationMode.SUBPROCESS_WEB


@pytest.mark.parametrize("slug,cls,cli,port", _ADAPTER_CLASSES)
def test_all_adapters_have_web_capabilities(slug, cls, cli, port, repo, pm):
    """GIVEN the all adapters have web capabilities scenario."""
    adapter = _make_adapter(cls, repo, pm, port, cli)

    """WHEN executing."""
    caps = adapter.capabilities

    """THEN the result is correct."""
    assert ToolCapability.WEB_UI in caps
    assert ToolCapability.HEALTH_CHECK in caps
    assert ToolCapability.PROCESS in caps


@pytest.mark.parametrize("slug,cls,cli,port", _ADAPTER_CLASSES)
def test_all_adapters_have_correct_slug(slug, cls, cli, port, repo, pm):
    """GIVEN the all adapters have correct slug scenario."""

    """WHEN executing."""
    adapter = _make_adapter(cls, repo, pm, port, cli)

    """THEN the result is correct."""
    assert adapter.slug == slug


@pytest.mark.parametrize("slug,cls,cli,port", _ADAPTER_CLASSES)
def test_all_adapters_have_stop_restart_actions(slug, cls, cli, port, repo, pm):
    """GIVEN the all adapters have stop restart actions scenario."""
    adapter = _make_adapter(cls, repo, pm, port, cli)
    actions = adapter.get_actions()

    """WHEN executing."""
    action_names = {a.name for a in actions}

    """THEN the result is correct."""
    assert "stop" in action_names
    assert "restart" in action_names


@pytest.mark.parametrize("slug,cls,cli,port", _ADAPTER_CLASSES)
@pytest.mark.asyncio
async def test_status_stopped_when_no_process(slug, cls, cli, port, repo, pm):
    """GIVEN the status stopped when no process scenario."""
    adapter = _make_adapter(cls, repo, pm, port, cli)

    """WHEN executing."""
    status = await adapter.get_status()

    """THEN the result is correct."""
    assert status == ToolStatus.STOPPED


@pytest.mark.parametrize("slug,cls,cli,port", _ADAPTER_CLASSES)
@pytest.mark.asyncio
async def test_health_not_running(slug, cls, cli, port, repo, pm):
    """GIVEN the health not running scenario."""
    adapter = _make_adapter(cls, repo, pm, port, cli)

    """WHEN executing."""
    h = await adapter.health_check()

    """THEN the result is correct."""
    assert h.healthy is False
    assert "not running" in h.message.lower()


@pytest.mark.parametrize("slug,cls,cli,port", _ADAPTER_CLASSES)
@pytest.mark.asyncio
async def test_web_url_none_when_not_running(slug, cls, cli, port, repo, pm):
    """GIVEN the web url none when not running scenario."""

    """WHEN executing."""
    adapter = _make_adapter(cls, repo, pm, port, cli)

    """THEN the result is correct."""
    assert adapter.get_web_url() is None


@pytest.mark.parametrize("slug,cls,cli,port", _ADAPTER_CLASSES)
@pytest.mark.asyncio
async def test_ensure_ready_fails_when_cli_missing(slug, cls, cli, port, repo, pm):
    """GIVEN the ensure ready fails when cli missing scenario."""
    adapter = _make_adapter(cls, repo, pm, port, "nonexistent-binary-xyz")

    """WHEN executing."""
    result = await adapter.ensure_ready()

    """THEN the result is correct."""
    assert result.ready is False
    assert "not found" in result.error.lower()


# ---------------------------------------------------------------------------
# ALLOW_FRAMING env var is set for each adapter
# ---------------------------------------------------------------------------


def test_releasepilot_sets_allow_framing(repo, pm):
    """GIVEN the releasepilot sets allow framing scenario."""

    """WHEN executing."""
    adapter = ReleasePilotAdapter(repo_path=repo, process_manager=pm)

    """THEN the result is correct."""
    assert adapter._env.get("RELEASEPILOT_ALLOW_FRAMING") == "true"


def test_releaseboard_sets_allow_framing(repo, pm):
    """GIVEN the releaseboard sets allow framing scenario."""

    """WHEN executing."""
    adapter = ReleaseBoardAdapter(repo_path=repo, process_manager=pm)

    """THEN the result is correct."""
    assert adapter._env.get("RELEASEBOARD_ALLOW_FRAMING") == "true"


# ---------------------------------------------------------------------------
# Integration: ensure_ready delegates to process_manager.ensure_running
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ensure_ready_calls_process_manager(repo, pm):
    """GIVEN Verify that ensure_ready uses process_manager.ensure_running."""
    managed = ManagedProcess(
        name="releasepilot",
        command=["releasepilot", "serve", "--port", "8082"],
        status=ProcessStatus.RUNNING,
    )
    pm.ensure_running = AsyncMock(return_value=managed)

    """WHEN executing."""
    with patch("shutil.which", return_value="/usr/bin/releasepilot"):
        adapter = ReleasePilotAdapter(repo_path=repo, process_manager=pm, port=8082)
        result = await adapter.ensure_ready()

    """THEN the result is correct."""
    assert result.ready is True
    assert result.web_url == "http://127.0.0.1:8082"
    pm.ensure_running.assert_called_once()
    call_args = pm.ensure_running.call_args
    assert call_args[0][0] == "releasepilot"  # process name
    assert "--port" in call_args[0][1]
    assert "8082" in call_args[0][1]


@pytest.mark.asyncio
async def test_ensure_ready_returns_error_on_failure(repo, pm):
    """GIVEN When process manager reports FAILED, ensure_ready returns not ready."""
    managed = ManagedProcess(
        name="releasepilot",
        command=["releasepilot", "serve", "--port", "8082"],
        status=ProcessStatus.FAILED,
    )
    pm.ensure_running = AsyncMock(return_value=managed)
    pm.get_logs = MagicMock(return_value=["error: bind failed"])

    """WHEN executing."""
    with patch("shutil.which", return_value="/usr/bin/releasepilot"):
        adapter = ReleasePilotAdapter(repo_path=repo, process_manager=pm, port=8082)
        result = await adapter.ensure_ready()

    """THEN the result is correct."""
    assert result.ready is False
    assert "failed to start" in result.error.lower()
