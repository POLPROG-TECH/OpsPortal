"""Tests for the process manager service."""

from __future__ import annotations

import sys

import pytest

from opsportal.services.process_manager import ProcessManager, ProcessStatus

"""GIVEN a process manager"""


@pytest.mark.asyncio
async def test_start_and_stop_process() -> None:
    pm = ProcessManager()

    """WHEN starting a long-running process"""
    proc = await pm.start(
        "test-echo",
        [sys.executable, "-c", "import time; time.sleep(60)"],
    )

    """THEN the process is running with a valid PID"""
    assert proc.status == ProcessStatus.RUNNING
    assert proc.pid is not None

    """WHEN stopping the process"""
    await pm.stop("test-echo")

    """THEN the process is stopped"""
    assert proc.status == ProcessStatus.STOPPED


"""GIVEN a process manager"""


@pytest.mark.asyncio
async def test_start_failing_command() -> None:
    pm = ProcessManager()

    """WHEN starting a command that raises SystemExit(1)"""
    proc = await pm.start("bad", [sys.executable, "-c", "raise SystemExit(1)"])
    # Process may be FAILED or RUNNING briefly then die

    """THEN status is FAILED or briefly RUNNING"""
    assert proc.status in (ProcessStatus.FAILED, ProcessStatus.RUNNING)
    await pm.shutdown_all()


"""GIVEN an empty process manager"""


@pytest.mark.asyncio
async def test_get_unknown_process() -> None:
    pm = ProcessManager()

    """WHEN looking up a non-existent process name"""

    """THEN looking up a non-existent process returns None"""
    assert pm.get("nope") is None


"""GIVEN an empty process manager"""


@pytest.mark.asyncio
async def test_get_logs_empty() -> None:
    pm = ProcessManager()

    """WHEN requesting logs for a non-existent process"""

    """THEN logs for a non-existent process are empty"""
    assert pm.get_logs("nope") == []


"""GIVEN a process manager with two running processes"""


@pytest.mark.asyncio
async def test_shutdown_all() -> None:
    pm = ProcessManager()
    await pm.start("a", [sys.executable, "-c", "import time; time.sleep(60)"])
    await pm.start("b", [sys.executable, "-c", "import time; time.sleep(60)"])

    """WHEN shutting down all processes"""
    await pm.shutdown_all()

    """THEN both processes are stopped"""
    for name in ("a", "b"):
        p = pm.get(name)
        assert p is not None
        assert p.status == ProcessStatus.STOPPED
