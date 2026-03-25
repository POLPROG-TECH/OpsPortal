"""Tests for the process manager service."""

from __future__ import annotations

import sys

import pytest

from opsportal.services.process_manager import ProcessManager, ProcessStatus


@pytest.mark.asyncio
async def test_start_and_stop_process() -> None:
    """ProcessManager can start a process and stop it cleanly."""
    """GIVEN a process manager."""
    pm = ProcessManager()

    """WHEN starting a long-running process."""
    proc = await pm.start(
        "test-echo",
        [sys.executable, "-c", "import time; time.sleep(60)"],
    )

    """THEN the process is running with a valid PID."""
    assert proc.status == ProcessStatus.RUNNING
    assert proc.pid is not None

    """WHEN stopping the process."""
    await pm.stop("test-echo")

    """THEN the process is stopped."""
    assert proc.status == ProcessStatus.STOPPED


@pytest.mark.asyncio
async def test_start_failing_command() -> None:
    """Starting a command that exits immediately produces FAILED or RUNNING status."""
    """GIVEN a process manager."""
    pm = ProcessManager()

    """WHEN starting a command that raises SystemExit(1)."""
    proc = await pm.start("bad", [sys.executable, "-c", "raise SystemExit(1)"])
    # Process may be FAILED or RUNNING briefly then die

    """THEN status is FAILED or briefly RUNNING."""
    assert proc.status in (ProcessStatus.FAILED, ProcessStatus.RUNNING)
    await pm.shutdown_all()


@pytest.mark.asyncio
async def test_get_unknown_process() -> None:
    """Getting an unregistered process name returns None."""
    """GIVEN an empty process manager."""
    pm = ProcessManager()

    """THEN looking up a non-existent process returns None."""
    assert pm.get("nope") is None


@pytest.mark.asyncio
async def test_get_logs_empty() -> None:
    """Getting logs for an unknown process returns an empty list."""
    """GIVEN an empty process manager."""
    pm = ProcessManager()

    """THEN logs for a non-existent process are empty."""
    assert pm.get_logs("nope") == []


@pytest.mark.asyncio
async def test_shutdown_all() -> None:
    """shutdown_all stops every running process."""
    """GIVEN a process manager with two running processes."""
    pm = ProcessManager()
    await pm.start("a", [sys.executable, "-c", "import time; time.sleep(60)"])
    await pm.start("b", [sys.executable, "-c", "import time; time.sleep(60)"])

    """WHEN shutting down all processes."""
    await pm.shutdown_all()

    """THEN both processes are stopped."""
    for name in ("a", "b"):
        p = pm.get(name)
        assert p is not None
        assert p.status == ProcessStatus.STOPPED
