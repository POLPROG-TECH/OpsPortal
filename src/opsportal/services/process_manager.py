"""Process manager - lifecycle management for subprocess-backed tools."""

from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

import httpx

from opsportal.core.errors import get_logger
from opsportal.core.network import ssl_proxy_env

if TYPE_CHECKING:
    from pathlib import Path

logger = get_logger("services.process_manager")


class ProcessStatus(StrEnum):
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass
class ManagedProcess:
    """State container for a supervised child process."""

    name: str
    command: list[str]
    cwd: Path | None = None
    env: dict[str, str] = field(default_factory=dict)
    port: int | None = None
    health_endpoint: str | None = None
    status: ProcessStatus = ProcessStatus.STOPPED
    process: asyncio.subprocess.Process | None = field(default=None, repr=False)
    started_at: float | None = None
    logs: deque[str] = field(default_factory=lambda: deque(maxlen=5000))
    _reader_tasks: list[asyncio.Task[None]] = field(default_factory=list, repr=False)

    @property
    def pid(self) -> int | None:
        return self.process.pid if self.process else None

    @property
    def uptime_seconds(self) -> float:
        return time.time() - self.started_at if self.started_at else 0.0


class ProcessManager:
    """Manages lifecycle of subprocess-backed tools."""

    def __init__(self, log_buffer_size: int = 5000) -> None:
        self._processes: dict[str, ManagedProcess] = {}
        self._log_buffer_size = log_buffer_size
        self._start_locks: dict[str, asyncio.Lock] = {}

    def _lock_for(self, name: str) -> asyncio.Lock:
        """Return a per-process lock to prevent duplicate starts."""
        if name not in self._start_locks:
            self._start_locks[name] = asyncio.Lock()
        return self._start_locks[name]

    async def start(
        self,
        name: str,
        command: list[str],
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        port: int | None = None,
        health_endpoint: str | None = None,
        startup_timeout: int = 30,
    ) -> ManagedProcess:
        """Start a managed subprocess."""
        if name in self._processes and self._processes[name].status == ProcessStatus.RUNNING:
            logger.warning("Process %r already running, stopping first", name)
            await self.stop(name)

        import os
        import shutil

        # Merge: base OS env → SSL/proxy vars → caller-supplied overrides.
        # This ensures child tools can connect through corporate proxies
        # and use corporate CA bundles without explicit configuration.
        full_env = {**os.environ, **ssl_proxy_env(), **(env or {})}

        # Resolve the binary to its full path - uvloop requires absolute paths
        resolved_bin = shutil.which(command[0])
        if not resolved_bin:
            raise FileNotFoundError(f"Command not found in PATH: {command[0]}")
        resolved_command = [resolved_bin, *command[1:]]

        managed = ManagedProcess(
            name=name,
            command=resolved_command,
            cwd=cwd,
            env=env or {},
            port=port,
            health_endpoint=health_endpoint,
            status=ProcessStatus.STARTING,
            logs=deque(maxlen=self._log_buffer_size),
        )
        self._processes[name] = managed

        logger.info("Starting process %r: %s", name, " ".join(resolved_command))

        try:
            proc = await asyncio.create_subprocess_exec(
                *resolved_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(cwd) if cwd else None,
                env=full_env,
            )
            managed.process = proc
            managed.started_at = time.time()
            managed.status = ProcessStatus.RUNNING

            # Background tasks to capture stdout/stderr
            managed._reader_tasks = [
                asyncio.create_task(self._read_stream(managed, proc.stdout, "stdout")),
                asyncio.create_task(self._read_stream(managed, proc.stderr, "stderr")),
            ]

            # Wait briefly to see if process exits immediately (bad startup)
            try:
                await asyncio.wait_for(asyncio.shield(proc.wait()), timeout=1.0)
                # If we get here, the process exited within 1s
                if proc.returncode != 0:
                    managed.status = ProcessStatus.FAILED
                    logger.error(
                        "Process %r exited immediately with code %d", name, proc.returncode
                    )
            except (TimeoutError, asyncio.CancelledError):
                pass  # Good - process is still running

            logger.info("Process %r started (PID %d)", name, proc.pid)

        except (OSError, ValueError) as exc:
            managed.status = ProcessStatus.FAILED
            managed.logs.append(f"Failed to start: {exc}")
            logger.exception("Failed to start process %r", name)

        return managed

    async def ensure_running(
        self,
        name: str,
        command: list[str],
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        port: int | None = None,
        health_endpoint: str | None = None,
        startup_timeout: int = 30,
    ) -> ManagedProcess:
        """Ensure a process is running and healthy. Start it if not.

        Uses a per-process lock to prevent duplicate concurrent starts.
        If ``health_endpoint`` is given, polls it until healthy or timeout.
        """
        async with self._lock_for(name):
            managed = self._processes.get(name)

            # Already running - check if process is still alive
            reuse = await self._check_existing(managed, name, port, health_endpoint)
            if reuse is not None:
                return reuse

            # Before starting, check if port already has a healthy service
            # (e.g. zombie from previous session, or manually started)
            adopted = await self._try_adopt_existing(
                managed, name, command, cwd, env, port, health_endpoint
            )
            if adopted is not None:
                return adopted

            # Need to start
            managed = await self.start(
                name,
                command,
                cwd=cwd,
                env=env,
                port=port,
                health_endpoint=health_endpoint,
                startup_timeout=startup_timeout,
            )

            if managed.status == ProcessStatus.FAILED:
                return managed

            # Wait for readiness
            await self._await_readiness(managed, port, health_endpoint, startup_timeout)
            return managed

    async def _check_existing(
        self,
        managed: ManagedProcess | None,
        name: str,
        port: int | None,
        health_endpoint: str | None,
    ) -> ManagedProcess | None:
        """Return the managed process if it's already alive and healthy, else None."""
        if not managed or managed.status != ProcessStatus.RUNNING or not managed.process:
            return None

        if managed.process.returncode is not None:
            managed.status = ProcessStatus.FAILED
            logger.warning("Process %r found dead (rc=%d)", name, managed.process.returncode)
            return None

        # Process still alive - optionally verify health
        if not (health_endpoint and port):
            return managed

        if await self._probe_health(port, health_endpoint):
            return managed

        # Process alive but not healthy - restart
        logger.warning("Process %r alive but health check failed, restarting", name)
        await self.stop(name)
        return None

    async def _try_adopt_existing(
        self,
        managed: ManagedProcess | None,
        name: str,
        command: list[str],
        cwd: Path | None,
        env: dict[str, str] | None,
        port: int | None,
        health_endpoint: str | None,
    ) -> ManagedProcess | None:
        """Adopt an already-healthy service on the expected port, if any."""
        if not (port and health_endpoint and await self._probe_health(port, health_endpoint)):
            return None

        logger.info("Healthy service already on port %d, adopting for %r", port, name)
        if not managed:
            managed = ManagedProcess(
                name=name,
                command=command,
                cwd=cwd,
                env=env or {},
                port=port,
                health_endpoint=health_endpoint,
            )
            self._processes[name] = managed
        managed.status = ProcessStatus.RUNNING
        managed.started_at = managed.started_at or time.time()
        return managed

    async def _await_readiness(
        self,
        managed: ManagedProcess,
        port: int | None,
        health_endpoint: str | None,
        startup_timeout: int,
    ) -> None:
        """Wait for the started process to become ready."""
        if health_endpoint and port:
            ready = await self._wait_for_health(
                port, health_endpoint, timeout=startup_timeout, process=managed
            )
            if not ready:
                managed.status = ProcessStatus.FAILED
                managed.logs.append(
                    f"[portal] Health endpoint {health_endpoint} not ready "
                    f"after {startup_timeout}s"
                )
                logger.error(
                    "Process %r started but health endpoint never became ready", managed.name
                )
        elif port:
            ready = await self._wait_for_port(port, timeout=startup_timeout, process=managed)
            if not ready:
                managed.status = ProcessStatus.FAILED
                managed.logs.append(f"[portal] Port {port} not ready after {startup_timeout}s")

    async def stop(self, name: str, *, port: int | None = None) -> None:
        """Gracefully stop a managed process."""
        managed = self._processes.get(name)
        if not managed:
            # No managed entry - try to kill by port as a last resort
            if port:
                pid = await self._find_pid_on_port(port)
                if pid:
                    logger.info("Stopping orphan on port %d (PID %d) for %r", port, pid, name)
                    await self._kill_pid(pid)
            return

        if managed.status not in (ProcessStatus.RUNNING, ProcessStatus.STARTING):
            return

        managed.status = ProcessStatus.STOPPING

        if managed.process:
            # We have a direct subprocess handle - terminate it
            proc = managed.process
            logger.info("Stopping process %r (PID %d)", name, proc.pid)
            try:
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=10.0)
                except TimeoutError:
                    logger.warning("Process %r did not exit after SIGTERM, sending SIGKILL", name)
                    proc.kill()
                    await proc.wait()
            except ProcessLookupError:
                pass  # Already dead
        elif managed.port:
            # Adopted process - find PID by port and kill it
            pid = await self._find_pid_on_port(managed.port)
            if pid:
                logger.info(
                    "Stopping adopted process %r (PID %d on port %d)",
                    name,
                    pid,
                    managed.port,
                )
                await self._kill_pid(pid)
            else:
                logger.warning(
                    "Cannot stop %r: no subprocess handle and no PID found on port %d",
                    name,
                    managed.port,
                )

        # Cancel reader tasks
        for task in managed._reader_tasks:
            task.cancel()
        managed._reader_tasks.clear()

        managed.status = ProcessStatus.STOPPED
        managed.process = None
        logger.info("Process %r stopped", name)

    @staticmethod
    async def _find_pid_on_port(port: int) -> int | None:
        """Find the PID of a process listening on the given port."""
        import subprocess as _sp

        try:
            result = await asyncio.to_thread(
                _sp.run,
                ["lsof", "-ti", f"tcp:{port}", "-sTCP:LISTEN"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                return int(result.stdout.strip().split("\n")[0])
        except (ValueError, OSError, _sp.TimeoutExpired):
            pass
        return None

    @staticmethod
    async def _kill_pid(pid: int) -> None:
        """Send SIGTERM then SIGKILL to a process by PID."""
        import os
        import signal

        try:
            os.kill(pid, signal.SIGTERM)
            # Wait for process to exit
            for _ in range(20):  # 10 seconds max
                await asyncio.sleep(0.5)
                try:
                    os.kill(pid, 0)  # Check if still alive
                except ProcessLookupError:
                    return  # Process exited
            # Still alive - force kill
            logger.warning("PID %d did not exit after SIGTERM, sending SIGKILL", pid)
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass  # Already dead

    async def restart(self, name: str) -> ManagedProcess:
        managed = self._processes.get(name)
        if not managed:
            msg = f"Unknown process: {name!r}"
            raise KeyError(msg)
        await self.stop(name)
        return await self.start(
            name,
            managed.command,
            cwd=managed.cwd,
            env=managed.env,
            port=managed.port,
            health_endpoint=managed.health_endpoint,
        )

    def get(self, name: str) -> ManagedProcess | None:
        return self._processes.get(name)

    def get_all(self) -> dict[str, ManagedProcess]:
        return dict(self._processes)

    def get_logs(self, name: str, tail: int = 200) -> list[str]:
        managed = self._processes.get(name)
        if not managed:
            return []
        items = list(managed.logs)
        return items[-tail:] if tail < len(items) else items

    async def shutdown_all(self) -> None:
        """Stop all managed processes (called during portal shutdown)."""
        names = [
            (n, p.port) for n, p in self._processes.items() if p.status == ProcessStatus.RUNNING
        ]
        if names:
            logger.info("Shutting down %d managed process(es)", len(names))
            await asyncio.gather(
                *(self.stop(n, port=port) for n, port in names), return_exceptions=True
            )

    # -- Internal health / readiness ----------------------------------------

    async def _probe_health(self, port: int, endpoint: str) -> bool:
        """Single health probe - returns True if endpoint responds 2xx."""
        url = f"http://127.0.0.1:{port}{endpoint}"
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(url)
                return 200 <= resp.status_code < 300
        except (httpx.HTTPError, OSError) as exc:
            logger.debug("Health probe failed for %s: %s", url, exc)
            return False

    async def _wait_for_health(
        self,
        port: int,
        endpoint: str,
        *,
        timeout: int = 30,
        process: ManagedProcess | None = None,
    ) -> bool:
        """Poll a health endpoint until it returns 2xx or timeout expires."""
        deadline = time.monotonic() + timeout
        interval = 0.5
        while time.monotonic() < deadline:
            # Check if process died while we're waiting
            if process and process.process and process.process.returncode is not None:
                logger.error(
                    "Process %r died (rc=%d) while waiting for health",
                    process.name,
                    process.process.returncode,
                )
                return False
            if await self._probe_health(port, endpoint):
                logger.info("Health endpoint %s:%d%s ready", "127.0.0.1", port, endpoint)
                return True
            await asyncio.sleep(interval)
            interval = min(interval * 1.5, 3.0)
        return False

    async def _wait_for_port(
        self,
        port: int,
        *,
        timeout: int = 30,
        process: ManagedProcess | None = None,
    ) -> bool:
        """Poll a TCP port until it accepts connections or timeout expires."""
        deadline = time.monotonic() + timeout
        interval = 0.5
        while time.monotonic() < deadline:
            if process and process.process and process.process.returncode is not None:
                return False
            try:
                _, writer = await asyncio.wait_for(
                    asyncio.open_connection("127.0.0.1", port), timeout=2.0
                )
                writer.close()
                await writer.wait_closed()
                logger.info("Port %d ready", port)
                return True
            except (OSError, TimeoutError):
                pass
            await asyncio.sleep(interval)
            interval = min(interval * 1.5, 3.0)
        return False

    async def _read_stream(
        self,
        managed: ManagedProcess,
        stream: asyncio.StreamReader | None,
        label: str,
    ) -> None:
        """Continuously read a subprocess stream and append to the log buffer."""
        if stream is None:
            return
        try:
            while True:
                line_bytes = await stream.readline()
                if not line_bytes:
                    break
                line = line_bytes.decode("utf-8", errors="replace").rstrip()
                managed.logs.append(f"[{label}] {line}")
        except asyncio.CancelledError:
            pass
        except OSError:
            logger.exception("Error reading %s for process %r", label, managed.name)
