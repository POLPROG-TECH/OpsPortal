"""Tests for the process manager service."""

from __future__ import annotations

import sys

import pytest

from opsportal.services.process_manager import ProcessManager, ProcessStatus


@pytest.mark.asyncio
async def test_start_and_stop_process() -> None:
    """GIVEN the start and stop process scenario."""
    pm = ProcessManager()

    """WHEN executing."""
    proc = await pm.start(
        "test-echo",
        [sys.executable, "-c", "import time; time.sleep(60)"],
    )

    """THEN the result is correct."""
    assert proc.status == ProcessStatus.RUNNING
    assert proc.pid is not None

    await pm.stop("test-echo")
    assert proc.status == ProcessStatus.STOPPED


@pytest.mark.asyncio
async def test_start_failing_command() -> None:
    """GIVEN the start failing command scenario."""
    pm = ProcessManager()

    """WHEN executing."""
    proc = await pm.start("bad", [sys.executable, "-c", "raise SystemExit(1)"])
    # Process may be FAILED or RUNNING briefly then die

    """THEN the result is correct."""
    assert proc.status in (ProcessStatus.FAILED, ProcessStatus.RUNNING)
    await pm.shutdown_all()


@pytest.mark.asyncio
async def test_get_unknown_process() -> None:
    """GIVEN the get unknown process scenario."""

    """WHEN executing."""
    pm = ProcessManager()

    """THEN the result is correct."""
    assert pm.get("nope") is None


@pytest.mark.asyncio
async def test_get_logs_empty() -> None:
    """GIVEN the get logs empty scenario."""

    """WHEN executing."""
    pm = ProcessManager()

    """THEN the result is correct."""
    assert pm.get_logs("nope") == []


@pytest.mark.asyncio
async def test_shutdown_all() -> None:
    """GIVEN the shutdown all scenario."""

    """WHEN executing."""
    pm = ProcessManager()
    await pm.start("a", [sys.executable, "-c", "import time; time.sleep(60)"])
    await pm.start("b", [sys.executable, "-c", "import time; time.sleep(60)"])
    await pm.shutdown_all()

    """THEN the result is correct."""
    for name in ("a", "b"):
        p = pm.get(name)
        assert p is not None
        assert p.status == ProcessStatus.STOPPED
